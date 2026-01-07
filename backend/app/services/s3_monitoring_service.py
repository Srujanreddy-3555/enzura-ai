"""
S3 Monitoring Service for Multi-Tenant Call Processing
This service monitors client S3 buckets for new audio files and processes them automatically.
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from sqlmodel import Session, select
import json

from ..database import get_db
from ..models import (
    Client, Call, CallStatus, UploadMethod, 
    Transcript, Insights, SalesRep, User, UserRole
)
from ..services.processing_service import processing_service, enqueue_call_for_processing
from ..services.s3_service import s3_service

logger = logging.getLogger(__name__)

class S3MonitoringService:
    """Service for monitoring client S3 buckets and processing new audio files."""
    
    def __init__(self):
        self.processing_queue = asyncio.Queue()
        self.is_running = False
        self.scan_tasks = {}
        
    async def start_monitoring(self):
        """Start the S3 monitoring service."""
        if self.is_running:
            logger.warning("S3 monitoring service is already running")
            return
        
        self.is_running = True
        logger.info("Starting S3 monitoring service...")
        
        # Start the processing queue worker
        asyncio.create_task(self._process_queue())
        
        # Start monitoring all active clients
        await self._start_client_monitoring()
        
        logger.info("S3 monitoring service started successfully")
    
    async def stop_monitoring(self):
        """Stop the S3 monitoring service."""
        if not self.is_running:
            return
        
        self.is_running = False
        logger.info("Stopping S3 monitoring service...")
        
        # Cancel all scan tasks
        for task in self.scan_tasks.values():
            task.cancel()
        
        self.scan_tasks.clear()
        logger.info("S3 monitoring service stopped")
    
    async def _start_client_monitoring(self):
        """Start monitoring for all active clients."""
        db = next(get_db())
        if not db:
            logger.error("Database not available for client monitoring")
            return
        
        try:
            # Get all active clients
            clients = db.exec(
                select(Client).where(Client.status == "active")
            ).all()
            
            logger.info(f"Found {len(clients)} active clients to monitor")
            
            # Update any clients with old schedule to realtime for immediate processing
            updated_count = 0
            for client in clients:
                if client.processing_schedule in ["daily", "hourly"]:
                    logger.info(f"Updating client {client.name} schedule from '{client.processing_schedule}' to 'realtime' for immediate processing")
                    client.processing_schedule = "realtime"
                    db.add(client)
                    updated_count += 1
            
            if updated_count > 0:
                db.commit()
                logger.info(f"Updated {updated_count} clients to use realtime processing schedule")
            
            # Start monitoring for all clients
            for client in clients:
                await self._start_client_scan(client)
                
        except Exception as e:
            logger.error(f"Error starting client monitoring: {e}")
        finally:
            db.close()
    
    async def _start_client_scan(self, client: Client):
        """Start monitoring for a specific client."""
        if client.id in self.scan_tasks:
            logger.warning(f"Client {client.id} is already being monitored")
            return
        
        # Create scan task based on client's processing schedule
        interval = self._get_scan_interval(client.processing_schedule)
        
        task = asyncio.create_task(
            self._scan_client_bucket(client, interval)
        )
        
        self.scan_tasks[client.id] = task
        logger.info(f"Started monitoring client {client.name} (ID: {client.id}) with {client.processing_schedule} schedule")
    
    def _get_scan_interval(self, schedule: str) -> int:
        """Convert processing schedule to seconds."""
        schedule_map = {
            "realtime": 30,          # 30 seconds - for immediate processing
            "continuous": 30,        # 30 seconds - alias for realtime
            "every_minute": 60,       # 1 minute
            "every_5_minutes": 300,  # 5 minutes
            "hourly": 3600,           # 1 hour
            "daily": 86400,           # 24 hours
            "twice_daily": 43200,     # 12 hours
            "every_6_hours": 21600,   # 6 hours
            "every_2_hours": 7200,    # 2 hours
        }
        return schedule_map.get(schedule.lower(), 30)  # Default to 30 seconds for immediate processing
    
    async def _scan_client_bucket(self, client: Client, interval: int):
        """Continuously scan a client's S3 bucket for new files."""
        logger.info(f"Starting continuous bucket scan for client {client.name} (interval: {interval}s)")
        
        # Do an immediate scan when starting
        try:
            logger.info(f"Performing initial scan for client {client.name}...")
            await self._scan_bucket_once(client)
        except Exception as e:
            logger.error(f"Error in initial scan for client {client.name}: {e}")
        
        # Then scan continuously at the specified interval
        while self.is_running:
            try:
                await asyncio.sleep(interval)
                await self._scan_bucket_once(client)
            except asyncio.CancelledError:
                logger.info(f"Scan task cancelled for client {client.name}")
                break
            except Exception as e:
                logger.error(f"Error scanning bucket for client {client.name}: {e}")
                await asyncio.sleep(min(interval, 60))  # Wait before retrying (max 1 minute)
    
    async def _scan_bucket_once(self, client: Client):
        """Perform a single scan of a client's S3 bucket."""
        logger.info(f"=== Scanning bucket {client.s3_bucket_name} for client {client.name} (ID: {client.id}) ===")
        
        try:
            # Create S3 client for this specific client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=client.aws_access_key,
                aws_secret_access_key=client.aws_secret_key,
                region_name=client.s3_region
            )
            
            logger.info(f"Created S3 client for region {client.s3_region}")
            
            # Get list of objects in the bucket
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=client.s3_bucket_name)
            
            all_files = []
            new_files = []
            
            for page in pages:
                if 'Contents' not in page:
                    logger.debug("No contents in this page")
                    continue
                
                logger.debug(f"Processing page with {len(page['Contents'])} objects")
                
                for obj in page['Contents']:
                    key = obj['Key']
                    all_files.append(key)
                    
                    # Check if this is an audio file
                    if self._is_audio_file(key):
                        logger.debug(f"Found audio file: {key}")
                        # Check if we've already processed this file
                        is_new = await self._is_new_file(client.id, key, obj['LastModified'])
                        if is_new:
                            logger.info(f"NEW FILE DETECTED: {key} (size: {obj['Size']} bytes)")
                            new_files.append({
                                'key': key,
                                'size': obj['Size'],
                                'last_modified': obj['LastModified'],
                                'etag': obj['ETag']
                            })
                        else:
                            logger.debug(f"File {key} already processed, skipping")
                    else:
                        logger.debug(f"File {key} is not an audio file, skipping")
            
            logger.info(f"=== SCAN COMPLETE === Total files: {len(all_files)}, Audio files: {len([f for f in all_files if self._is_audio_file(f)])}, New files: {len(new_files)} ===")
            
            # Process new files
            if new_files:
                logger.info(f"Queuing {len(new_files)} new files for processing")
                for file_info in new_files:
                    await self._queue_file_for_processing(client, file_info)
            else:
                logger.info("No new files to process")
                
        except NoCredentialsError as e:
            logger.error(f"Invalid AWS credentials for client {client.name}: {e}")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"AWS error scanning bucket for client {client.name}: {error_code} - {error_msg}")
        except Exception as e:
            logger.error(f"Unexpected error scanning bucket for client {client.name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _is_audio_file(self, key: str) -> bool:
        """Check if a file is an audio file based on its extension."""
        audio_extensions = {'.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.wma'}
        file_extension = Path(key).suffix.lower()
        return file_extension in audio_extensions
    
    async def _is_new_file(self, client_id: int, s3_key: str, last_modified: datetime) -> bool:
        """Check if a file is new (not already processed)."""
        db = next(get_db())
        if not db:
            logger.warning("Database not available for checking new files")
            return False
        
        try:
            # Check if we already have a call record for this file
            # Match by client_id and s3_key (which should be in the s3_url)
            existing_call = db.exec(
                select(Call).where(
                    Call.client_id == client_id,
                    Call.s3_url.contains(s3_key)  # More reliable than LIKE
                )
            ).first()
            
            if existing_call:
                logger.debug(f"File {s3_key} already processed as call {existing_call.id}")
                return False
            
            logger.debug(f"File {s3_key} is new, will be processed")
            return True
            
        except Exception as e:
            logger.error(f"Error checking if file is new: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        finally:
            db.close()
    
    async def _queue_file_for_processing(self, client: Client, file_info: Dict[str, Any]):
        """Queue a file for processing."""
        processing_item = {
            'client': client,
            'file_info': file_info,
            'timestamp': datetime.utcnow()
        }
        
        await self.processing_queue.put(processing_item)
        logger.info(f"Queued file {file_info['key']} for processing")
    
    async def _process_queue(self):
        """Process files from the queue."""
        logger.info("Starting file processing queue worker")
        
        while self.is_running:
            try:
                # Wait for items in the queue
                processing_item = await asyncio.wait_for(
                    self.processing_queue.get(), 
                    timeout=1.0
                )
                
                await self._process_file(processing_item)
                
            except asyncio.TimeoutError:
                # No items in queue, continue
                continue
            except Exception as e:
                logger.error(f"Error processing queue item: {e}")
    
    async def _process_file(self, processing_item: Dict[str, Any]):
        """Process a single file."""
        client = processing_item['client']
        file_info = processing_item['file_info']
        
        logger.info(f"Processing file {file_info['key']} for client {client.name}")
        
        try:
            # Detect rep email from key prefix and fallback to name detection
            rep_email = self._extract_rep_email(file_info['key'])
            sales_rep_name = self._detect_sales_rep(client.id, file_info['key'])
            
            logger.info(f"=== FILE PROCESSING DEBUG === Key: {file_info['key']}, Extracted Email: {rep_email}, Detected Name: {sales_rep_name}")
            
            # Create call record
            call_record = await self._create_call_record(client, file_info, sales_rep_name, rep_email)
            
            if call_record:
                logger.info(f"=== CALL ASSIGNMENT VERIFICATION === Call ID: {call_record.id}, User ID: {call_record.user_id}, Client ID: {call_record.client_id}, Sales Rep ID: {call_record.sales_rep_id}")
            else:
                logger.error("=" * 60)
                logger.error(f"=== CALL CREATION FAILED ===")
                logger.error(f"Could not create call record for: {file_info['key']}")
                logger.error("Check the logs ABOVE this message for detailed error information.")
                logger.error("Look for '❌❌❌ CALL CREATION ERROR ❌❌❌' section.")
                logger.error("=" * 60)
            
            if call_record:
                # Extract ID before session closes to avoid lazy loading errors
                call_id = call_record.id
                # Enqueue for unified processing queue to ensure ordering & resilience
                await enqueue_call_for_processing(call_id)
                
        except Exception as e:
            logger.error(f"Error processing file {file_info['key']}: {e}")
    
    def _detect_sales_rep(self, client_id: int, s3_key: str) -> Optional[str]:
        """Detect sales rep name from S3 key path."""
        db = next(get_db())
        if not db:
            return None
        
        try:
            # Get sales reps for this client
            sales_reps = db.exec(
                select(SalesRep).where(SalesRep.client_id == client_id)
            ).all()
            
            if not sales_reps:
                return None
            
            # Try to match sales rep name in the path
            # Common patterns: /john-smith/call.mp3, /sales-rep-name/, etc.
            path_parts = s3_key.lower().split('/')
            
            for sales_rep in sales_reps:
                rep_name_lower = sales_rep.name.lower().replace(' ', '-')
                
                # Check if sales rep name appears in any path part
                for part in path_parts:
                    if rep_name_lower in part or part in rep_name_lower:
                        return sales_rep.name
            
            # If no match found, try to extract from filename
            filename = Path(s3_key).stem.lower()
            for sales_rep in sales_reps:
                rep_name_lower = sales_rep.name.lower().replace(' ', '-')
                if rep_name_lower in filename:
                    return sales_rep.name
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting sales rep: {e}")
            return None
        finally:
            db.close()
    
    async def _create_call_record(self, client: Client, file_info: Dict[str, Any], sales_rep_name: Optional[str], rep_email: Optional[str] = None) -> Optional[Call]:
        """Create a call record for the new file."""
        db = next(get_db())
        if not db:
            logger.error("Database not available for creating call record")
            return None
        
        try:
            # Create S3 URL
            s3_url = f"https://{client.s3_bucket_name}.s3.{client.s3_region}.amazonaws.com/{file_info['key']}"
            
            logger.info(f"Creating call record for file: {file_info['key']}, rep_email: {rep_email}, rep_name: {sales_rep_name}")
            
            # Determine user_id from rep email within this client, else fallback to client-level user, else system user (1)
            resolved_user_id = 1
            resolved_sales_rep_id = None

            if rep_email:
                logger.info(f"Looking for rep user with email {rep_email} in client {client.id}")
                
                # Try exact email match first
                rep_user = db.exec(
                    select(User).where(
                        User.client_id == client.id,
                        User.role == UserRole.REP,
                        User.email == rep_email
                    )
                ).first()
                
                # If no exact match, try comprehensive partial matching
                if not rep_user:
                    logger.info(f"No exact match for {rep_email}, trying comprehensive matching...")
                    all_rep_users = db.exec(
                        select(User).where(
                            User.client_id == client.id,
                            User.role == UserRole.REP
                        )
                    ).all()
                    
                    logger.info(f"Found {len(all_rep_users)} rep users to match against")
                    
                    # Extract username and domain parts for better matching
                    rep_username = rep_email.split('@')[0].lower() if '@' in rep_email else rep_email.lower()
                    rep_domain = rep_email.split('@')[1].lower() if '@' in rep_email and len(rep_email.split('@')) > 1 else None
                    
                    # Strategy 1: Username match (most reliable) - rep@domain matches rep@anything.com
                    if not rep_user:
                        for user in all_rep_users:
                            if user.email:
                                user_email_lower = user.email.lower()
                                user_username = user_email_lower.split('@')[0] if '@' in user_email_lower else user_email_lower
                                if user_username == rep_username:
                                    rep_user = user
                                    logger.info(f"✅ Found username match: '{rep_username}' from '{rep_email}' matches '{user.email}'")
                                    break
                    
                    # Strategy 2: Prefix match - rep@domain matches rep@domain.com or rep@domain.anything
                    if not rep_user and rep_domain:
                        for user in all_rep_users:
                            if user.email:
                                user_email_lower = user.email.lower()
                                # Check if rep_email is a prefix (rep@domain matches rep@domain.com)
                                if user_email_lower.startswith(rep_email):
                                    rep_user = user
                                    logger.info(f"✅ Found prefix match: '{rep_email}' is prefix of '{user.email}'")
                                    break
                                # Check if user email starts with rep_email pattern
                                if user_email_lower.startswith(f"{rep_username}@{rep_domain}"):
                                    rep_user = user
                                    logger.info(f"✅ Found domain prefix match: '{rep_email}' pattern matches '{user.email}'")
                                    break
                    
                    # Strategy 3: Contains match - rep@domain is contained in user email
                    if not rep_user:
                        for user in all_rep_users:
                            if user.email:
                                user_email_lower = user.email.lower()
                                if rep_email in user_email_lower:
                                    rep_user = user
                                    logger.info(f"✅ Found contains match: '{rep_email}' is in '{user.email}'")
                                    break
                    
                    # Strategy 4: Reverse - check if user email without TLD matches
                    if not rep_user and rep_domain:
                        for user in all_rep_users:
                            if user.email:
                                user_email_lower = user.email.lower()
                                # Remove common TLDs and compare
                                user_email_no_tld = user_email_lower.replace('.com', '').replace('.net', '').replace('.org', '')
                                if user_email_no_tld == rep_email:
                                    rep_user = user
                                    logger.info(f"✅ Found reverse match (no TLD): '{rep_email}' matches '{user.email}' (without TLD)")
                                    break
                    
                    # Strategy 5: Fuzzy match - check if domain parts match
                    if not rep_user and rep_domain:
                        for user in all_rep_users:
                            if user.email:
                                user_email_lower = user.email.lower()
                                if '@' in user_email_lower:
                                    user_domain = user_email_lower.split('@')[1]
                                    # Check if domains match or are similar (domain matches domain.com)
                                    if rep_domain in user_domain or user_domain.startswith(rep_domain):
                                        rep_user = user
                                        logger.info(f"✅ Found fuzzy domain match: '{rep_email}' domain matches '{user.email}'")
                                        break
                    
                    if not rep_user:
                        logger.warning(f"❌ NO MATCH FOUND for '{rep_email}' among {len(all_rep_users)} rep users")
                        logger.warning(f"   Available rep emails: {[u.email for u in all_rep_users]}")
                    else:
                        logger.info(f"✅ SUCCESSFULLY MATCHED: '{rep_email}' -> User ID {rep_user.id} ({rep_user.email})")
                
                if rep_user:
                    resolved_user_id = rep_user.id
                    logger.info(f"Found rep user: {rep_user.id} ({rep_user.name}, email: {rep_user.email})")
                    if not sales_rep_name:
                        sales_rep_name = rep_user.name

                # Try to resolve SalesRep entity by email too (with same partial matching logic)
                rep_entity = db.exec(
                    select(SalesRep).where(
                        SalesRep.client_id == client.id,
                        SalesRep.email == rep_email
                    )
                ).first()
                
                # Try partial matching for SalesRep too
                if not rep_entity:
                    all_sales_reps = db.exec(
                        select(SalesRep).where(
                            SalesRep.client_id == client.id
                        )
                    ).all()
                    
                    for sr in all_sales_reps:
                        if sr.email:
                            if rep_email in sr.email.lower() or sr.email.lower().startswith(rep_email):
                                rep_entity = sr
                                logger.info(f"Found sales rep entity with partial match: {sr.email}")
                                break
                
                if rep_entity:
                    resolved_sales_rep_id = rep_entity.id
                    logger.info(f"Found sales rep entity: {rep_entity.id} ({rep_entity.name}, email: {rep_entity.email})")
                    if not sales_rep_name:
                        sales_rep_name = rep_entity.name
                
                if not rep_user:
                    logger.error(f"❌ CRITICAL: No rep user found with email pattern '{rep_email}' for client {client.id}")
                    logger.error(f"   This call will be assigned to a client user or system user instead of a rep!")
                if not rep_entity:
                    logger.warning(f"No sales rep entity found with email pattern '{rep_email}' for client {client.id}")

            # If no rep user matched, attach to a client-level user (role CLIENT) for visibility
            if resolved_user_id == 1:
                logger.info(f"No rep user matched, looking for client-level user for client {client.id}")
                client_user = db.exec(
                    select(User).where(
                        User.client_id == client.id,
                        User.role == UserRole.CLIENT
                    ).order_by(User.id.asc())
                ).first()
                if client_user:
                    resolved_user_id = client_user.id
                    logger.info(f"Assigned to client user: {client_user.id} ({client_user.name})")
                else:
                    logger.warning(f"No client-level user found for client {client.id}, using system user (1)")

            # Validate user_id exists before creating call
            user_exists = db.get(User, resolved_user_id)
            if not user_exists:
                logger.error(f"❌ CRITICAL: User ID {resolved_user_id} does not exist in database!")
                logger.error(f"   Cannot create call record. File: {file_info['key']}")
                logger.error(f"   Looking for alternative user...")
                
                # Try to find ANY user for this client (REP or CLIENT role)
                any_user = db.exec(
                    select(User).where(
                        User.client_id == client.id
                    ).order_by(User.id.asc())
                ).first()
                
                if any_user:
                    resolved_user_id = any_user.id
                    logger.info(f"✅ Found alternative user: {any_user.id} ({any_user.name}, role: {any_user.role})")
                else:
                    # Last resort: create a temporary admin user check or use first available admin
                    admin_user = db.exec(
                        select(User).where(
                            User.role == UserRole.ADMIN
                        ).order_by(User.id.asc())
                    ).first()
                    
                    if admin_user:
                        resolved_user_id = admin_user.id
                        logger.warning(f"⚠️ Using admin user {admin_user.id} as fallback (no client users found)")
                    else:
                        logger.error(f"❌ NO USERS FOUND IN DATABASE! Cannot create call record.")
                        logger.error(f"   Please create at least one user (admin, client, or rep) before uploading calls.")
                        raise ValueError(f"No users found in database. Please create a user first.")

            # Log all values before creating call record
            filename = Path(file_info['key']).name
            logger.info(f"📝 Creating call record with:")
            logger.info(f"   - Filename: {filename}")
            logger.info(f"   - User ID: {resolved_user_id}")
            logger.info(f"   - Client ID: {client.id}")
            logger.info(f"   - Sales Rep ID: {resolved_sales_rep_id}")
            logger.info(f"   - Sales Rep Name: {sales_rep_name}")
            logger.info(f"   - S3 URL: {s3_url}")
            logger.info(f"   - Language: None (auto-detect)")
            logger.info(f"   - Translate to English: True (for insights generation)")

            # Create call record
            try:
                call = Call(
                    user_id=resolved_user_id,
                    client_id=client.id,
                    sales_rep_id=resolved_sales_rep_id,
                    sales_rep_name=sales_rep_name,
                    filename=filename,
                    s3_url=s3_url,
                    status=CallStatus.PROCESSING,
                    language=None,  # Auto-detect language (supports Arabic "ar" and 100+ languages)
                    translate_to_english=True,  # Translate to English for insights generation
                    upload_date=datetime.utcnow(),
                    upload_method=UploadMethod.S3_AUTO
                )
                
                db.add(call)
                db.commit()
                db.refresh(call)
                logger.info(f"✅ Call record created successfully: ID {call.id}")
                
            except Exception as create_error:
                logger.error(f"❌ ERROR creating Call object: {create_error}")
                logger.error(f"   Type: {type(create_error).__name__}")
                import traceback
                logger.error(f"   Traceback:\n{traceback.format_exc()}")
                raise  # Re-raise to be caught by outer exception handler
            
            # CRITICAL: Extract duration IMMEDIATELY after call creation (outside try-except for call creation)
            # This ensures duration extraction runs even if there were issues during call creation
            if call:
                try:
                    from ..utils.file_utils import AudioProcessor
                    import boto3
                    import tempfile
                    from urllib.parse import urlparse
                    
                    logger.info(f"⏱️ Extracting duration for call {call.id} immediately after creation...")
                    
                    # Parse S3 URL (same logic as manual script)
                    if call.s3_url.startswith('http://') or call.s3_url.startswith('https://'):
                        parsed = urlparse(call.s3_url)
                        s3_key = parsed.path.lstrip('/')
                        if s3_key.startswith(client.s3_bucket_name + '/'):
                            s3_key = s3_key[len(client.s3_bucket_name) + 1:]
                    else:
                        s3_key = call.s3_url
                    
                    # Download from S3 (same logic as manual script)
                    s3_client = boto3.client(
                        's3',
                        aws_access_key_id=client.aws_access_key,
                        aws_secret_access_key=client.aws_secret_key,
                        region_name=client.s3_region
                    )
                    
                    audio_bytes = None
                    try:
                        response = s3_client.get_object(Bucket=client.s3_bucket_name, Key=s3_key)
                        audio_bytes = response['Body'].read()
                        logger.info(f"⏱️ Downloaded {len(audio_bytes)} bytes from S3")
                    except Exception as s3_err:
                        # Try alternative keys (same as manual script)
                        alternative_keys = [
                            f"calls/{call.filename}",
                            call.filename,
                        ]
                        for alt_key in alternative_keys:
                            try:
                                response = s3_client.get_object(Bucket=client.s3_bucket_name, Key=alt_key)
                                audio_bytes = response['Body'].read()
                                logger.info(f"⏱️ Found with alternative key: {alt_key} ({len(audio_bytes)} bytes)")
                                s3_key = alt_key
                                break
                            except Exception:
                                continue
                    
                    if audio_bytes:
                        # Save to temp file and extract (same as manual script)
                        file_extension = os.path.splitext(call.filename)[1] or '.mp3'
                        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                            temp_file.write(audio_bytes)
                            temp_file_path = temp_file.name
                        
                        try:
                            # Extract duration using the same method as manual script
                            duration = AudioProcessor.get_audio_duration(temp_file_path)
                            if duration and duration > 0:
                                # Save to database (same as manual script)
                                call.duration = duration
                                db.add(call)
                                db.commit()
                                db.refresh(call)
                                
                                if call.duration == duration:
                                    logger.info(f"⏱️ ✅✅✅ Duration extracted and saved: {duration}s ({duration // 60}:{(duration % 60):02d})")
                                else:
                                    logger.error(f"⏱️ ❌ Duration save verification failed")
                            else:
                                logger.warning(f"⏱️ Duration extraction returned: {duration}")
                        finally:
                            # Cleanup temp file
                            try:
                                os.unlink(temp_file_path)
                            except:
                                pass
                    else:
                        logger.warning(f"⏱️ Could not download audio from S3 for duration extraction")
                except Exception as extract_error:
                    # Don't fail call creation if duration extraction fails
                    logger.error(f"⏱️ Error extracting duration during S3 call creation: {extract_error}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            logger.info(f"=== CREATED CALL RECORD {call.id} === File: {file_info['key']}, User ID: {resolved_user_id}, Client ID: {client.id}, Sales Rep: {sales_rep_name} ===")
            return call
            
        except Exception as e:
            logger.error("=" * 60)
            logger.error("❌❌❌ CALL CREATION ERROR ❌❌❌")
            logger.error("=" * 60)
            logger.error(f"Error Type: {type(e).__name__}")
            logger.error(f"Error Message: {str(e)}")
            logger.error(f"File: {file_info.get('key', 'unknown')}")
            import traceback
            logger.error("Full Traceback:")
            logger.error(traceback.format_exc())
            logger.error("=" * 60)
            db.rollback()
            return None
        finally:
            db.close()

    def _extract_rep_email(self, s3_key: str) -> Optional[str]:
        """Extract a rep email from S3 key by looking for a path segment that looks like an email.
        Examples: 
        
        """
        try:
            parts = [p for p in s3_key.split('/') if p]
            for part in parts:
                candidate = part.strip()
                # Check if it contains @ symbol (email-like pattern)
                if '@' in candidate:
                    # First priority: full email format (has @ and . after @)
                    if '.' in candidate.split('@')[1]:  # Has dot in domain part
                        return candidate.lower()
                    # Second priority: partial email (has @ but no . in domain)
                    # This handles cases like "hanish@innovar"
                    return candidate.lower()
            return None
        except Exception:
            return None
    
    async def _process_audio_file(self, client: Client, file_info: Dict[str, Any], call: Call):
        """Process the audio file (transcription and insights)."""
        logger.info(f"Processing audio file for call {call.id}")
        
        try:
            # Create S3 client for this client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=client.aws_access_key,
                aws_secret_access_key=client.aws_secret_key,
                region_name=client.s3_region
            )
            
            # Download file to temporary location
            temp_file_path = await self._download_file(s3_client, client.s3_bucket_name, file_info['key'])
            
            if temp_file_path:
                # Process the file
                await self._process_with_ai(temp_file_path, call)
                
                # Clean up temporary file
                os.unlink(temp_file_path)
            
        except Exception as e:
            logger.error(f"Error processing audio file: {e}")
            # Update call status to failed
            await self._update_call_status(call.id, CallStatus.FAILED)
    
    async def _download_file(self, s3_client, bucket_name: str, key: str) -> Optional[str]:
        """Download file from S3 to temporary location."""
        try:
            # Create temporary file
            temp_dir = Path("/tmp") / "enzura_processing"
            temp_dir.mkdir(exist_ok=True)
            
            temp_file_path = temp_dir / f"{datetime.utcnow().timestamp()}_{Path(key).name}"
            
            # Download file
            s3_client.download_file(bucket_name, key, str(temp_file_path))
            
            logger.info(f"Downloaded file to {temp_file_path}")
            return str(temp_file_path)
            
        except Exception as e:
            logger.error(f"Error downloading file {key}: {e}")
            return None
    
    async def _process_with_ai(self, file_path: str, call: Call):
        """Process the audio file with AI (transcription and insights)."""
        try:
            # Use existing processing service
            result = await processing_service.process_audio_file(file_path, call.language)
            
            if result:
                # Update call with results
                await self._update_call_with_results(call, result)
                logger.info(f"Successfully processed call {call.id}")
            else:
                logger.error(f"Failed to process call {call.id}")
                await self._update_call_status(call.id, CallStatus.FAILED)
                
        except Exception as e:
            logger.error(f"Error processing with AI: {e}")
            await self._update_call_status(call.id, CallStatus.FAILED)
    
    async def _update_call_with_results(self, call: Call, result: Dict[str, Any]):
        """Update call record with processing results."""
        db = next(get_db())
        if not db:
            return
        
        try:
            # Update call status and score
            call.status = CallStatus.PROCESSED
            call.score = result.get('overall_score', 0)
            call.duration = result.get('duration', 0)
            
            db.add(call)
            db.commit()
            
            logger.info(f"Updated call {call.id} with processing results")
            
        except Exception as e:
            logger.error(f"Error updating call with results: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def _update_call_status(self, call_id: int, status: CallStatus):
        """Update call status."""
        db = next(get_db())
        if not db:
            return
        
        try:
            call = db.get(Call, call_id)
            if call:
                call.status = status
                db.add(call)
                db.commit()
                logger.info(f"Updated call {call_id} status to {status}")
            
        except Exception as e:
            logger.error(f"Error updating call status: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def add_client_monitoring(self, client: Client):
        """Add a new client to monitoring."""
        await self._start_client_scan(client)
    
    async def remove_client_monitoring(self, client_id: int):
        """Remove a client from monitoring."""
        if client_id in self.scan_tasks:
            self.scan_tasks[client_id].cancel()
            del self.scan_tasks[client_id]
            logger.info(f"Removed client {client_id} from monitoring")

# Global instance
s3_monitoring_service = S3MonitoringService()
