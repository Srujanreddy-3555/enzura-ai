import os
import asyncio
import logging
import json
from typing import Optional
from sqlmodel import Session, select
from datetime import datetime
import openai
from dotenv import load_dotenv

from ..database import get_db
from ..models import Call, CallStatus, Transcript, TranscriptCreate, Insights, InsightsCreate, SentimentType

# Load environment variables with UTF-8 tolerance
try:
    load_dotenv(encoding="utf-8", override=True)
except Exception:
    try:
        load_dotenv()
    except Exception:
        pass

logger = logging.getLogger(__name__)

class ProcessingService:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.openai_client = openai.OpenAI(api_key=api_key)
        else:
            # Create a minimal dummy client with api_key attribute for fallback logic
            class _DummyClient:
                api_key = None
            self.openai_client = _DummyClient()
        # Use gpt-3.5-turbo as fallback if gpt-4o is not available
        self.model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        logger.info(f"Initialized ProcessingService with model: {self.model} (OpenAI key present: {bool(api_key)})")
    
    async def test_gpt_connection(self) -> bool:
        """
        Test GPT connection and model availability
        """
        try:
            if not self.openai_client.api_key:
                logger.warning("No OpenAI API key available")
                return False
            
            # Test with a simple request
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say 'test successful' if you can read this."}
                ],
                max_tokens=10,
                temperature=0
            )
            
            if response.choices and response.choices[0].message.content:
                logger.info(f"GPT connection test successful with model {self.model}")
                return True
            else:
                logger.error("GPT connection test failed - no response content")
                return False
                
        except Exception as e:
            logger.error(f"GPT connection test failed: {e}")
            return False
    
    async def process_call(self, call_id: int, db: Session):
        """
        Process a call: transcribe audio and generate insights
        GUARANTEES that transcript and insights are created
        """
        logger.info(f"🚀 Starting processing for call {call_id}")
        transcript_created = False
        insights_created = False
        
        try:
            # CRITICAL CHECK: Verify OpenAI API key is available BEFORE starting
            if not self.openai_client.api_key:
                error_msg = "❌❌❌ CRITICAL: OpenAI API key is not configured! Cannot transcribe audio."
                logger.error(error_msg)
                logger.error("Please set OPENAI_API_KEY environment variable with a valid OpenAI API key")
                raise ValueError("OpenAI API key not configured")
            
            # Get the call
            call_statement = select(Call).where(Call.id == call_id)
            call = db.exec(call_statement).first()
            
            if not call:
                logger.error(f"❌ Call {call_id} not found")
                raise ValueError(f"Call {call_id} not found")
            
            logger.info(f"✅ Found call {call_id}: {call.filename}, S3 URL: {call.s3_url}")
            
            # Get client credentials for S3 access
            client_credentials = None
            if call.client_id:
                from ..models import Client
                client = db.exec(select(Client).where(Client.id == call.client_id)).first()
                if client:
                    client_credentials = {
                        'access_key': client.aws_access_key,
                        'secret_key': client.aws_secret_key,
                        'region': client.s3_region,
                        'bucket_name': client.s3_bucket_name
                    }
                    logger.info(f"✅ Got client credentials for client {call.client_id} (bucket: {client.s3_bucket_name})")
            
            # Update status to processing
            call.status = CallStatus.PROCESSING
            db.commit()
            db.refresh(call)
            logger.info(f"✅ Updated call {call_id} status to PROCESSING")
            
            # CRITICAL: Extract duration IMMEDIATELY at the start of processing
            # This ensures duration shows up in frontend even while call is PROCESSING
            logger.info(f"⏱️ === EXTRACTING DURATION IMMEDIATELY at start of processing ===")
            try:
                from ..utils.file_utils import AudioProcessor
                import boto3
                import tempfile
                from urllib.parse import urlparse
                from ..models import Client
                
                if call.client_id:
                    client = db.exec(select(Client).where(Client.id == call.client_id)).first()
                    if client and client.aws_access_key:
                        # Parse S3 key
                        if call.s3_url.startswith('http://') or call.s3_url.startswith('https://'):
                            parsed = urlparse(call.s3_url)
                            s3_key = parsed.path.lstrip('/')
                            if s3_key.startswith(client.s3_bucket_name + '/'):
                                s3_key = s3_key[len(client.s3_bucket_name) + 1:]
                            if not s3_key.startswith('calls/'):
                                s3_key = f"calls/{call.filename}" if not s3_key else s3_key
                        else:
                            s3_key = call.s3_url
                        
                        logger.info(f"⏱️ IMMEDIATE EXTRACTION: Downloading from S3 - bucket: {client.s3_bucket_name}, key: {s3_key}")
                        
                        s3_client = boto3.client(
                            's3',
                            aws_access_key_id=client.aws_access_key,
                            aws_secret_access_key=client.aws_secret_key,
                            region_name=client.s3_region
                        )
                        
                        # Try downloading with alternative keys
                        audio_bytes = None
                        try:
                            response = s3_client.get_object(Bucket=client.s3_bucket_name, Key=s3_key)
                            audio_bytes = response['Body'].read()
                            logger.info(f"⏱️ IMMEDIATE EXTRACTION: Downloaded {len(audio_bytes)} bytes")
                        except Exception as s3_err:
                            logger.warning(f"⏱️ IMMEDIATE EXTRACTION: Primary key failed, trying alternatives...")
                            alternative_keys = [
                                f"calls/{call.filename}",
                                call.filename,
                            ]
                            for alt_key in alternative_keys:
                                try:
                                    response = s3_client.get_object(Bucket=client.s3_bucket_name, Key=alt_key)
                                    audio_bytes = response['Body'].read()
                                    logger.info(f"⏱️ ✅ IMMEDIATE EXTRACTION: Found with key: {alt_key} ({len(audio_bytes)} bytes)")
                                    s3_key = alt_key
                                    break
                                except Exception:
                                    continue
                            
                            if not audio_bytes:
                                logger.warning(f"⏱️ IMMEDIATE EXTRACTION: Could not download from S3 (will retry during transcription)")
                        
                        if audio_bytes:
                            # Save to temp file and extract duration
                            file_extension = os.path.splitext(call.filename)[1] or '.mp3'
                            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                                temp_file.write(audio_bytes)
                                temp_file_path = temp_file.name
                            
                            logger.info(f"⏱️ IMMEDIATE EXTRACTION: Extracting duration from temp file...")
                            immediate_duration = AudioProcessor.get_audio_duration(temp_file_path)
                            
                            if immediate_duration and immediate_duration > 0:
                                # Save to database immediately
                                call_refresh = db.exec(select(Call).where(Call.id == call_id)).first()
                                if call_refresh:
                                    call_refresh.duration = immediate_duration
                                    db.add(call_refresh)
                                    db.commit()
                                    db.refresh(call_refresh)
                                    # Verify it was saved
                                    if call_refresh.duration == immediate_duration:
                                        call.duration = immediate_duration
                                        logger.info(f"⏱️ ✅✅✅ IMMEDIATE EXTRACTION SUCCESS: Saved {immediate_duration}s ({immediate_duration // 60}:{(immediate_duration % 60):02d}) to database")
                                        logger.info(f"⏱️ ✅ Duration will now show in frontend even while call is PROCESSING")
                                    else:
                                        logger.error(f"⏱️ ❌ IMMEDIATE EXTRACTION: Duration save failed! Expected {immediate_duration}, got {call_refresh.duration}")
                                        # Retry save
                                        call_refresh.duration = immediate_duration
                                        db.add(call_refresh)
                                        db.commit()
                                        db.refresh(call_refresh)
                                        call.duration = immediate_duration
                                else:
                                    logger.error(f"⏱️ ❌ IMMEDIATE EXTRACTION: Could not refresh call object - call {call_id} not found!")
                            else:
                                logger.error(f"⏱️ ❌ IMMEDIATE EXTRACTION: Duration extraction returned {immediate_duration} (invalid)")
                            
                            # Cleanup
                            try:
                                os.unlink(temp_file_path)
                            except:
                                pass
                    else:
                        logger.warning(f"⏱️ IMMEDIATE EXTRACTION: No client credentials available (will retry during transcription)")
                else:
                    logger.warning(f"⏱️ IMMEDIATE EXTRACTION: Call has no client_id (will retry during transcription)")
            except Exception as immediate_error:
                logger.error(f"⏱️ ❌ IMMEDIATE EXTRACTION failed: {immediate_error} (will retry during transcription)")
                import traceback
                logger.error(f"⏱️ IMMEDIATE EXTRACTION traceback:\n{traceback.format_exc()}")
            
            # Step 1: Transcribe audio - SUPPORTS MULTI-LANGUAGE (auto-detect or specified language)
            call_language = call.language if call.language else None
            call_translate = call.translate_to_english if hasattr(call, 'translate_to_english') else False
            language_display = call_language if call_language else "auto-detect"
            logger.info(f"📝 Step 1: Transcribing REAL audio file for call {call_id}...")
            logger.info(f"   Language: {language_display}")
            logger.info(f"   Translate to English: {call_translate}")
            logger.info(f"   OpenAI API Key present: ✅ (ready for transcription)")
            
            # Transcribe with language auto-detect or specified language
            transcript_result = await self._transcribe_audio(
                call.s3_url, 
                call.id, 
                call_language,  # None = auto-detect, or specific language code like "ar" for Arabic
                client_credentials,
                translate_to_english=call_translate  # Translate to English if requested
            )
            
            # Handle tuple return (transcript_text, duration_seconds)
            if isinstance(transcript_result, tuple):
                transcript_text, duration_seconds = transcript_result
            else:
                # Fallback for old format (just in case)
                transcript_text = transcript_result
                duration_seconds = None
            
            # If transcription failed, raise error instead of using fallback
            if not transcript_text or len(transcript_text.strip()) < 10:
                error_msg = f"❌ CRITICAL: Real audio transcription returned empty or invalid result for call {call_id}"
                logger.error(error_msg)
                raise ValueError("Real audio transcription failed - transcript is empty")
            
            logger.info(f"📝 Generated transcript for call {call_id} (length: {len(transcript_text)} chars)")
            
            # CRITICAL: Save duration immediately to database to ensure it's not lost
            # This ensures ALL new calls will have duration extracted and saved
            logger.info(f"⏱️ === CHECKING DURATION BEFORE SAVE: duration_seconds={duration_seconds} ===")
            if duration_seconds and duration_seconds > 0:
                try:
                    logger.info(f"⏱️ 📌 SAVING duration IMMEDIATELY for call {call_id}: {duration_seconds}s")
                    # Get fresh call object to ensure we're working with latest
                    call_refresh = db.exec(select(Call).where(Call.id == call_id)).first()
                    if call_refresh:
                        call_refresh.duration = duration_seconds
                        db.add(call_refresh)
                        db.commit()
                        db.refresh(call_refresh)
                        
                        # Verify it was saved
                        if call_refresh.duration == duration_seconds:
                            logger.info(f"⏱️ ✅✅✅ Duration VERIFIED in database: {call_refresh.duration}s ({call_refresh.duration // 60}:{(call_refresh.duration % 60):02d})")
                            # Update the call object we're using
                            call.duration = duration_seconds
                        else:
                            logger.error(f"⏱️ ❌ Duration SAVE FAILED: Expected {duration_seconds}, got {call_refresh.duration}")
                            # Retry save
                            call_refresh.duration = duration_seconds
                            db.add(call_refresh)
                            db.commit()
                            db.refresh(call_refresh)
                            call.duration = duration_seconds
                    else:
                        logger.error(f"⏱️ ❌ Could not refresh call object!")
                        # Fallback: save to current call object
                        call.duration = duration_seconds
                        db.add(call)
                        db.commit()
                        db.refresh(call)
                        logger.info(f"⏱️ ✅ Duration saved via fallback: {call.duration}s")
                except Exception as save_error:
                    logger.error(f"⏱️ ❌❌❌ CRITICAL: Failed to save duration: {save_error}")
                    import traceback
                    logger.error(traceback.format_exc())
                    # Still try to set it in memory for later save
                    call.duration = duration_seconds
                    # Try one more time with a fresh transaction
                    try:
                        db.rollback()
                        call_retry = db.exec(select(Call).where(Call.id == call_id)).first()
                        if call_retry:
                            call_retry.duration = duration_seconds
                            db.add(call_retry)
                            db.commit()
                            logger.info(f"⏱️ ✅ Duration saved on retry: {duration_seconds}s")
                    except Exception as retry_error:
                        logger.error(f"⏱️ ❌ Duration save retry also failed: {retry_error}")
            else:
                logger.error(f"⏱️ ❌❌❌ CRITICAL: No duration extracted! duration_seconds={duration_seconds}")
                logger.error(f"⏱️ Attempting to extract duration directly from S3 as fallback...")
                
                # FALLBACK: Try to extract duration directly from S3 if it wasn't extracted earlier
                # This ensures duration is ALWAYS extracted for new calls
                try:
                    from ..utils.file_utils import AudioProcessor
                    import tempfile
                    import boto3
                    from urllib.parse import urlparse
                    
                    # Get client credentials
                    if call.client_id:
                        from ..models import Client
                        client = db.exec(select(Client).where(Client.id == call.client_id)).first()
                        if client and client.aws_access_key:
                            # Download from S3
                            parsed = urlparse(call.s3_url)
                            s3_key = parsed.path.lstrip('/')
                            
                            s3_client = boto3.client(
                                's3',
                                aws_access_key_id=client.aws_access_key,
                                aws_secret_access_key=client.aws_secret_key,
                                region_name=client.s3_region
                            )
                            
                            response = s3_client.get_object(Bucket=client.s3_bucket_name, Key=s3_key)
                            audio_bytes = response['Body'].read()
                            
                            # Save to temp file
                            file_extension = os.path.splitext(call.filename)[1] or '.mp3'
                            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                                temp_file.write(audio_bytes)
                                temp_file_path = temp_file.name
                            
                            # Extract duration
                            fallback_duration = AudioProcessor.get_audio_duration(temp_file_path)
                            if fallback_duration and fallback_duration > 0:
                                logger.info(f"⏱️ ✅ FALLBACK SUCCESS: Extracted {fallback_duration}s ({fallback_duration // 60}:{(fallback_duration % 60):02d})")
                                duration_seconds = fallback_duration
                                
                                # Save to database
                                call_refresh = db.exec(select(Call).where(Call.id == call_id)).first()
                                if call_refresh:
                                    call_refresh.duration = fallback_duration
                                    db.add(call_refresh)
                                    db.commit()
                                    db.refresh(call_refresh)
                                    call.duration = fallback_duration
                                    logger.info(f"⏱️ ✅ FALLBACK: Duration saved to database: {fallback_duration}s")
                                else:
                                    call.duration = fallback_duration
                                    db.add(call)
                                    db.commit()
                                    logger.info(f"⏱️ ✅ FALLBACK: Duration saved (no refresh): {fallback_duration}s")
                            else:
                                logger.error(f"⏱️ ❌ FALLBACK: Could not extract duration from audio file")
                            
                            # Cleanup
                            try:
                                os.unlink(temp_file_path)
                            except:
                                pass
                        else:
                            logger.error(f"⏱️ ❌ FALLBACK: No client credentials available")
                    else:
                        logger.error(f"⏱️ ❌ FALLBACK: Call has no client_id")
                except Exception as fallback_error:
                    logger.error(f"⏱️ ❌ Fallback extraction also failed: {fallback_error}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # Save transcript - GUARANTEED TO SUCCEED
            from ..models import Transcript
            try:
                existing_transcript = db.exec(
                    select(Transcript).where(Transcript.call_id == call_id)
                ).first()
                
                if existing_transcript:
                    logger.info(f"📝 Updating existing transcript for call {call_id}...")
                    existing_transcript.text = transcript_text
                    existing_transcript.language = call.language  # Can be None for auto-detect
                    # Ensure client_id is set
                    if call.client_id:
                        existing_transcript.client_id = call.client_id
                    db.add(existing_transcript)
                else:
                    logger.info(f"📝 Creating new transcript for call {call_id}...")
                    logger.info(f"📝 Call client_id: {call.client_id}")
                    db_transcript = Transcript(
                        call_id=call_id,
                        client_id=call.client_id,  # CRITICAL: Set client_id from call to avoid trigger error
                        text=transcript_text,
                        language=call.language  # Can be None for auto-detect
                    )
                    db.add(db_transcript)
                
                db.commit()
                db.refresh(existing_transcript if existing_transcript else db_transcript)
                transcript_created = True
                logger.info(f"✅✅✅ TRANSCRIPT SAVED for call {call_id} (length: {len(transcript_text)} chars)")
            except Exception as transcript_error:
                logger.error(f"❌ CRITICAL: Failed to save transcript for call {call_id}: {transcript_error}")
                import traceback
                logger.error(traceback.format_exc())
                db.rollback()
                # Try one more time with a fresh transaction
                try:
                    # Get call again to ensure we have latest data
                    call_refresh = db.exec(select(Call).where(Call.id == call_id)).first()
                    db_transcript = Transcript(
                        call_id=call_id,
                        client_id=call_refresh.client_id if call_refresh else None,  # CRITICAL: Set client_id
                        text=transcript_text[:5000],  # Limit length
                        language=call_refresh.language if call_refresh else None  # Can be None for auto-detect
                    )
                    db.add(db_transcript)
                    db.commit()
                    transcript_created = True
                    logger.info(f"✅ Transcript saved on retry for call {call_id}")
                except Exception as retry_error:
                    logger.error(f"❌ CRITICAL: Transcript save retry also failed: {retry_error}")
                    import traceback
                    logger.error(traceback.format_exc())
                    raise  # Re-raise if we can't save transcript at all
            
            # Step 2: Generate insights - GUARANTEED TO SUCCEED
            logger.info(f"=== GENERATING INSIGHTS for call {call_id} ===")
            
            # Check if insights already exist
            from ..models import Insights
            existing_insights = db.exec(
                select(Insights).where(Insights.call_id == call_id)
            ).first()
            
            if existing_insights:
                logger.info(f"Insights already exist for call {call_id}, regenerating...")
                db.delete(existing_insights)
                db.commit()
            
            insights = await self._generate_insights(transcript_text, call.language)  # Can be None for auto-detect
            
            # Always ensure we have insights, even if generation failed
            if not insights:
                logger.warning(f"⚠️ Insights generation returned None for call {call_id}, creating enhanced fallback insights")
                # Use enhanced fallback insights
                insights = self._generate_enhanced_fallback_insights(transcript_text)
                logger.info(f"✅ Created fallback insights for call {call_id} (score: {insights.overall_score})")
            
            try:
                # Save insights in a separate transaction to avoid rollback issues
                # CRITICAL: Set the correct call_id before processing
                insights.call_id = call_id
                logger.info(f"Preparing to save insights for call {call_id}")
                logger.info(f"Insights call_id set to: {insights.call_id}")
                
                # Convert lists and dicts to JSON strings for database storage
                insights_dict = insights.dict()
                logger.info(f"Insights dict keys: {list(insights_dict.keys())}")
                logger.info(f"Insights dict call_id: {insights_dict.get('call_id')}")
                
                # Convert lists to JSON strings
                if insights_dict.get('key_topics'):
                    insights_dict['key_topics'] = json.dumps(insights_dict['key_topics'])
                if insights_dict.get('improvement_areas'):
                    insights_dict['improvement_areas'] = json.dumps(insights_dict['improvement_areas'])
                if insights_dict.get('action_items'):
                    insights_dict['action_items'] = json.dumps(insights_dict['action_items'])
                if insights_dict.get('trust_building_moments'):
                    insights_dict['trust_building_moments'] = json.dumps(insights_dict['trust_building_moments'])
                if insights_dict.get('interest_indicators'):
                    insights_dict['interest_indicators'] = json.dumps(insights_dict['interest_indicators'])
                if insights_dict.get('concern_indicators'):
                    insights_dict['concern_indicators'] = json.dumps(insights_dict['concern_indicators'])
                if insights_dict.get('upsell_opportunities'):
                    insights_dict['upsell_opportunities'] = json.dumps(insights_dict['upsell_opportunities'])
                
                # Convert dict to JSON string
                if insights_dict.get('bant_qualification'):
                    insights_dict['bant_qualification'] = json.dumps(insights_dict['bant_qualification'])
                
                logger.info(f"Converted insights dict for database storage")
                
                # Save insights in SAME session to ensure atomicity and visibility
                try:
                    # Check if insights already exist for this call_id
                    existing_insights_check = db.exec(
                        select(Insights).where(Insights.call_id == call_id)
                    ).first()
                    
                    if existing_insights_check:
                        logger.warning(f"📊 Insights already exist for call {call_id}, deleting old insights first")
                        db.delete(existing_insights_check)
                        db.commit()
                    
                    logger.info(f"📊 Creating Insights object for call {call_id}")
                    logger.info(f"📊 Final insights dict call_id: {insights_dict.get('call_id')}")
                    logger.info(f"📊 Insights summary preview: {insights_dict.get('summary', '')[:100]}...")
                    
                    # CRITICAL: Ensure client_id is set in insights_dict
                    if 'client_id' not in insights_dict or insights_dict.get('client_id') is None:
                        insights_dict['client_id'] = call.client_id
                        logger.info(f"📊 Set client_id in insights: {call.client_id}")
                    
                    db_insights = Insights(**insights_dict)
                    db.add(db_insights)
                    db.flush()  # Flush to get ID without committing
                    
                    # Refresh call to get latest data
                    db.refresh(call)
                    
                    # CRITICAL: Preserve duration before updating other fields
                    saved_duration = call.duration if call.duration else duration_seconds
                    
                    # OPTIONAL: Try to extract duration if it's still missing (but don't block PROCESSED status)
                    if not saved_duration or saved_duration <= 0:
                        logger.warning(f"⏱️ ⚠️ Duration is missing before marking as PROCESSED. Attempting extraction...")
                        
                        # Extract duration directly from S3 as a final attempt
                        try:
                            from ..utils.file_utils import AudioProcessor
                            import boto3
                            import tempfile
                            from urllib.parse import urlparse
                            from ..models import Client
                            
                            if call.client_id:
                                client = db.exec(select(Client).where(Client.id == call.client_id)).first()
                                if client and client.aws_access_key:
                                    # Parse S3 key
                                    if call.s3_url.startswith('http://') or call.s3_url.startswith('https://'):
                                        parsed = urlparse(call.s3_url)
                                        s3_key = parsed.path.lstrip('/')
                                        if s3_key.startswith(client.s3_bucket_name + '/'):
                                            s3_key = s3_key[len(client.s3_bucket_name) + 1:]
                                        if not s3_key.startswith('calls/'):
                                            s3_key = f"calls/{call.filename}" if not s3_key else s3_key
                                    else:
                                        s3_key = call.s3_url
                                    
                                    logger.info(f"⏱️ MANDATORY EXTRACTION: Downloading from S3 - bucket: {client.s3_bucket_name}, key: {s3_key}")
                                    
                                    s3_client = boto3.client(
                                        's3',
                                        aws_access_key_id=client.aws_access_key,
                                        aws_secret_access_key=client.aws_secret_key,
                                        region_name=client.s3_region
                                    )
                                    
                                    # Try downloading with alternative keys
                                    audio_bytes = None
                                    try:
                                        response = s3_client.get_object(Bucket=client.s3_bucket_name, Key=s3_key)
                                        audio_bytes = response['Body'].read()
                                        logger.info(f"⏱️ MANDATORY EXTRACTION: Downloaded {len(audio_bytes)} bytes")
                                    except Exception as s3_err:
                                        logger.warning(f"⏱️ MANDATORY EXTRACTION: Primary key failed, trying alternatives...")
                                        alternative_keys = [
                                            f"calls/{call.filename}",
                                            call.filename,
                                        ]
                                        for alt_key in alternative_keys:
                                            try:
                                                response = s3_client.get_object(Bucket=client.s3_bucket_name, Key=alt_key)
                                                audio_bytes = response['Body'].read()
                                                logger.info(f"⏱️ ✅ MANDATORY EXTRACTION: Found with key: {alt_key} ({len(audio_bytes)} bytes)")
                                                s3_key = alt_key
                                                break
                                            except Exception:
                                                continue
                                        
                                        if not audio_bytes:
                                            raise Exception(f"Could not download from S3. Tried: {s3_key}, {', '.join(alternative_keys)}")
                                    
                                    # Save to temp file and extract duration
                                    file_extension = os.path.splitext(call.filename)[1] or '.mp3'
                                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                                        temp_file.write(audio_bytes)
                                        temp_file_path = temp_file.name
                                    
                                    logger.info(f"⏱️ MANDATORY EXTRACTION: Extracting duration from temp file...")
                                    mandatory_duration = AudioProcessor.get_audio_duration(temp_file_path)
                                    
                                    if mandatory_duration and mandatory_duration > 0:
                                        saved_duration = mandatory_duration
                                        logger.info(f"⏱️ ✅✅✅ MANDATORY EXTRACTION SUCCESS: {mandatory_duration}s ({mandatory_duration // 60}:{(mandatory_duration % 60):02d})")
                                        
                                        # Cleanup
                                        try:
                                            os.unlink(temp_file_path)
                                        except:
                                            pass
                                    else:
                                        logger.error(f"⏱️ ❌ MANDATORY EXTRACTION: Duration extraction returned {mandatory_duration}")
                                        # Cleanup
                                        try:
                                            os.unlink(temp_file_path)
                                        except:
                                            pass
                                else:
                                    logger.error(f"⏱️ ❌ MANDATORY EXTRACTION: No client credentials available")
                            else:
                                logger.error(f"⏱️ ❌ MANDATORY EXTRACTION: Call has no client_id")
                        except Exception as mandatory_error:
                            logger.error(f"⏱️ ❌ MANDATORY EXTRACTION FAILED: {mandatory_error}")
                            import traceback
                            logger.error(f"⏱️ MANDATORY EXTRACTION traceback:\n{traceback.format_exc()}")
                    
                    # Always mark as PROCESSED if insights are created, regardless of duration
                    # Duration will show as N/A in frontend if extraction failed, but call is still processed
                    call.score = insights.overall_score
                    call.status = CallStatus.PROCESSED
                    
                    # Set duration if we have it, otherwise leave as None (will show as N/A)
                    if saved_duration and saved_duration > 0:
                        call.duration = saved_duration
                        logger.info(f"⏱️ ✅ Duration confirmed before marking as PROCESSED: {saved_duration}s ({saved_duration // 60}:{(saved_duration % 60):02d})")
                    else:
                        call.duration = None
                        logger.warning(f"⏱️ ⚠️ Marking call as PROCESSED without duration (will show as N/A in frontend)")
                    
                    # Commit everything together for atomicity
                    db.commit()
                    db.refresh(db_insights)
                    db.refresh(call)
                    
                    # Final verification - Check duration (but it's OK if None - will show as N/A)
                    if call.duration and call.duration > 0:
                        logger.info(f"⏱️ ✅✅✅ Duration preserved in database: {call.duration}s ({call.duration // 60}:{(call.duration % 60):02d})")
                    else:
                        logger.warning(f"⏱️ ⚠️ Duration is None after commit (will show as N/A in frontend)")
                        # Last resort: try to save duration if we have it in memory
                        if duration_seconds and duration_seconds > 0:
                            try:
                                logger.error(f"⏱️ 🆘 LAST RESORT: Saving duration directly...")
                                call.duration = duration_seconds
                                db.add(call)
                                db.commit()
                                db.refresh(call)
                                if call.duration and call.duration > 0:
                                    logger.info(f"⏱️ ✅ LAST RESORT SUCCESS: Duration saved: {call.duration}s ({call.duration // 60}:{(call.duration % 60):02d})")
                                else:
                                    logger.error(f"⏱️ ❌ LAST RESORT FAILED: Duration still None!")
                                    # Try one final time with a fresh query
                                    try:
                                        call_final = db.exec(select(Call).where(Call.id == call_id)).first()
                                        if call_final and duration_seconds and duration_seconds > 0:
                                            call_final.duration = duration_seconds
                                            db.add(call_final)
                                            db.commit()
                                            db.refresh(call_final)
                                            if call_final.duration:
                                                logger.info(f"⏱️ ✅ FINAL ATTEMPT SUCCESS: Duration saved: {call_final.duration}s")
                                            else:
                                                logger.error(f"⏱️ ❌ FINAL ATTEMPT FAILED: Duration still None after save!")
                                    except Exception as final_error:
                                        logger.error(f"⏱️ ❌ FINAL ATTEMPT ERROR: {final_error}")
                                        import traceback
                                        logger.error(traceback.format_exc())
                            except Exception as last_error:
                                logger.error(f"⏱️ ❌ LAST RESORT ERROR: {last_error}")
                                import traceback
                                logger.error(traceback.format_exc())
                    
                    # FINAL VERIFICATION: Check duration (but it's OK if None - will show as N/A)
                    call_verify = db.exec(select(Call).where(Call.id == call_id)).first()
                    if call_verify:
                        if call_verify.duration and call_verify.duration > 0:
                            logger.info(f"⏱️ ✅✅✅ FINAL VERIFICATION: Duration confirmed in database: {call_verify.duration}s ({call_verify.duration // 60}:{(call_verify.duration % 60):02d})")
                        elif duration_seconds and duration_seconds > 0:
                            # Duration missing - try to save it one more time
                            logger.warning(f"⏱️ ⚠️ Duration missing in final verification, attempting to save...")
                            call_verify.duration = duration_seconds
                            db.add(call_verify)
                            db.commit()
                            db.refresh(call_verify)
                            if call_verify.duration:
                                logger.info(f"⏱️ ✅ Duration saved in final verification: {call_verify.duration}s ({call_verify.duration // 60}:{(call_verify.duration % 60):02d})")
                            else:
                                logger.warning(f"⏱️ ⚠️ Duration save failed in final verification (will show as N/A)")
                        else:
                            logger.info(f"⏱️ ✅ Call marked as PROCESSED (duration will show as N/A in frontend)")
                    
                    # VERIFY insights were actually saved
                    verification = db.exec(
                        select(Insights).where(Insights.call_id == call_id)
                    ).first()
                    
                    if verification:
                        insights_created = True
                        logger.info(f"✅✅✅ INSIGHTS SAVED and VERIFIED for call {call_id} (ID: {verification.id})")
                        logger.info(f"   Summary: {verification.summary[:100] if verification.summary else 'N/A'}...")
                        logger.info(f"   Score: {verification.overall_score}, Sentiment: {verification.sentiment}")
                        logger.info(f"✅✅✅ FINAL: Call {call_id} COMPLETED - Score: {call.score}, Status: {call.status} ✅✅✅")
                    else:
                        logger.error(f"❌ CRITICAL: Insights commit succeeded but verification failed for call {call_id}")
                        raise ValueError("Insights verification failed after commit")
                        
                except Exception as insights_error:
                    logger.error(f"❌ CRITICAL: Error saving insights for call {call_id}: {insights_error}")
                    import traceback
                    logger.error(traceback.format_exc())
                    logger.error(f"Insights dict that failed: {insights_dict}")
                    db.rollback()
                    
                    # Try to save emergency insights as last resort
                    try:
                        logger.info(f"🆘 Attempting to save emergency insights for call {call_id}")
                        emergency_insights = self._create_emergency_insights(call_id, call.filename, transcript_text)
                        emergency_dict = emergency_insights.dict()
                        
                        # CRITICAL: Set client_id in emergency insights
                        if 'client_id' not in emergency_dict or emergency_dict.get('client_id') is None:
                            emergency_dict['client_id'] = call.client_id
                            logger.info(f"🆘 Set client_id in emergency insights: {call.client_id}")
                        
                        # Convert lists to JSON strings
                        for field in ['key_topics', 'improvement_areas', 'action_items', 'trust_building_moments', 
                                    'interest_indicators', 'concern_indicators', 'upsell_opportunities']:
                            if emergency_dict.get(field):
                                emergency_dict[field] = json.dumps(emergency_dict[field])
                        
                        if emergency_dict.get('bant_qualification'):
                            emergency_dict['bant_qualification'] = json.dumps(emergency_dict['bant_qualification'])
                        
                        emergency_db_insights = Insights(**emergency_dict)
                        db.add(emergency_db_insights)
                        
                        call.score = emergency_insights.overall_score
                        call.status = CallStatus.PROCESSED
                        
                        db.commit()
                        db.refresh(emergency_db_insights)
                        
                        # Verify emergency insights
                        verification = db.exec(
                            select(Insights).where(Insights.call_id == call_id)
                        ).first()
                        
                        if verification:
                            insights_created = True
                            logger.info(f"✅ Emergency insights saved and verified for call {call_id} (score: {emergency_insights.overall_score})")
                        else:
                            raise ValueError("Emergency insights verification failed")
                            
                    except Exception as emergency_error:
                        logger.error(f"❌ CRITICAL: Emergency insights save also failed for call {call_id}: {emergency_error}")
                        import traceback
                        logger.error(traceback.format_exc())
                        # Don't mark as processed if we can't save insights
                        call.status = CallStatus.PROCESSING
                        db.commit()
                        raise ValueError(f"Failed to save insights for call {call_id} after all attempts")
                
            except Exception as insights_exception:
                logger.error(f"❌ CRITICAL: Error in insights processing for call {call_id}: {insights_exception}")
                import traceback
                logger.error(traceback.format_exc())
                db.rollback()
                raise  # Re-raise to prevent marking as processed without insights
            
            # Final verification - ensure both transcript and insights exist
            if not transcript_created:
                logger.error(f"❌ CRITICAL: Transcript not created for call {call_id}")
                raise ValueError("Transcript creation failed")
            
            if not insights_created:
                logger.error(f"❌ CRITICAL: Insights not created for call {call_id}")
                raise ValueError("Insights creation failed")
            
            # Double-check in database
            final_transcript_check = db.exec(
                select(Transcript).where(Transcript.call_id == call_id)
            ).first()
            final_insights_check = db.exec(
                select(Insights).where(Insights.call_id == call_id)
            ).first()
            
            if not final_transcript_check:
                logger.error(f"❌ CRITICAL: Transcript verification failed for call {call_id}")
                raise ValueError("Transcript not found in database after creation")
            
            if not final_insights_check:
                logger.error(f"❌ CRITICAL: Insights verification failed for call {call_id}")
                raise ValueError("Insights not found in database after creation")
            
            logger.info(f"✅✅✅ COMPLETED processing for call {call_id} - Transcript: ✅, Insights: ✅")
            
        except ValueError as ve:
            # Transcription or validation errors - mark as FAILED
            logger.error(f"❌❌❌ FATAL ERROR processing call {call_id}: {ve}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Rollback and mark as FAILED
            try:
                db.rollback()
                call_statement = select(Call).where(Call.id == call_id)
                call = db.exec(call_statement).first()
                if call:
                    call.status = CallStatus.FAILED
                    
                    # Create a transcript with the error message so users can see what went wrong
                    from ..models import Transcript
                    error_message = str(ve)
                    # Clean up error message for display (remove emoji and extra formatting)
                    clean_error = error_message.replace("❌", "").replace("CRITICAL:", "").strip()
                    
                    # Check if transcript already exists
                    existing_transcript = db.exec(
                        select(Transcript).where(Transcript.call_id == call_id)
                    ).first()
                    
                    if existing_transcript:
                        # Update existing transcript with error message
                        existing_transcript.text = f"Processing failed: {clean_error}"
                        db.add(existing_transcript)
                    else:
                        # Create new transcript with error message
                        error_transcript = Transcript(
                            call_id=call_id,
                            client_id=call.client_id,
                            text=f"Processing failed: {clean_error}",
                            language=call.language
                        )
                        db.add(error_transcript)
                    
                    db.commit()
                    logger.error(f"❌ Call {call_id} marked as FAILED due to error: {ve}")
                    logger.info(f"✅ Error message stored in transcript for user visibility")
                    # If it's an OpenAI API key error, log it prominently
                    if "OpenAI API key" in str(ve):
                        logger.error("=" * 80)
                        logger.error("❌❌❌ OPENAI API KEY MISSING OR INVALID ❌❌❌")
                        logger.error("Please set OPENAI_API_KEY environment variable")
                        logger.error("Without a valid API key, audio transcription cannot work!")
                        logger.error("=" * 80)
            except Exception as db_error:
                logger.error(f"❌ Error updating call status: {db_error}")
            raise  # Re-raise the original error so caller knows it failed
        except Exception as e:
            # Other errors - mark as FAILED
            logger.error(f"❌❌❌ FATAL ERROR processing call {call_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Rollback and mark as FAILED
            try:
                db.rollback()
                call_statement = select(Call).where(Call.id == call_id)
                call = db.exec(call_statement).first()
                if call:
                    call.status = CallStatus.FAILED
                    
                    # Create a transcript with the error message so users can see what went wrong
                    from ..models import Transcript
                    error_message = str(e)
                    # Clean up error message for display
                    clean_error = error_message.replace("❌", "").replace("CRITICAL:", "").strip()
                    
                    # Check if transcript already exists
                    existing_transcript = db.exec(
                        select(Transcript).where(Transcript.call_id == call_id)
                    ).first()
                    
                    if existing_transcript:
                        # Update existing transcript with error message
                        existing_transcript.text = f"Processing failed: {clean_error}"
                        db.add(existing_transcript)
                    else:
                        # Create new transcript with error message
                        error_transcript = Transcript(
                            call_id=call_id,
                            client_id=call.client_id,
                            text=f"Processing failed: {clean_error}",
                            language=call.language
                        )
                        db.add(error_transcript)
                    
                    db.commit()
                    logger.error(f"❌ Call {call_id} marked as FAILED due to unexpected error: {e}")
                    logger.info(f"✅ Error message stored in transcript for user visibility")
            except Exception as db_error:
                logger.error(f"❌ Error updating call status: {db_error}")
            raise  # Re-raise the original error so caller knows it failed
    
    async def _transcribe_audio(self, s3_url: str, call_id: int, language: Optional[str] = None, client_credentials: dict = None, translate_to_english: bool = False) -> tuple[Optional[str], Optional[int]]:
        """
        Transcribe REAL audio from S3 URL using OpenAI Whisper API
        This function MUST transcribe the actual audio file - no mock transcripts unless absolutely necessary
        Returns: (transcript_text, duration_seconds)
        """
        try:
            logger.info(f"🎙️ TRANSCRIBING REAL AUDIO: {s3_url} for call {call_id}")
            
            # Check if this is a mock URL (only for testing)
            if "/mock/" in s3_url:
                logger.warning(f"⚠️ Mock S3 URL detected: {s3_url}")
                logger.warning("Cannot transcribe from mock URL - this should not happen in production!")
                raise ValueError("Mock URLs not supported for real transcription")
            
            # Check if we have OpenAI API key
            if not self.openai_client.api_key:
                error_msg = "❌ CRITICAL: OpenAI API key not available. Cannot transcribe real audio!"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # REAL AUDIO TRANSCRIPTION - Try multiple times with better error handling
            max_retries = 3
            last_error = None
            
            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(f"🎙️ Attempt {attempt}/{max_retries}: Transcribing REAL audio for call {call_id}")
                    transcript_result = await self._transcribe_with_whisper(
                        s3_url, 
                        call_id, 
                        language,
                        client_credentials,
                        translate_to_english=translate_to_english
                    )
                    
                    # Check if transcription returned None (this shouldn't happen now, but check anyway)
                    if transcript_result is None:
                        logger.warning(f"⚠️ Attempt {attempt}: Transcription returned None")
                        if attempt < max_retries:
                            continue
                        else:
                            raise ValueError("Transcription returned None after all attempts - this indicates a critical error")
                    
                    # Handle tuple return (transcript, duration)
                    if isinstance(transcript_result, tuple):
                        transcript_text, duration_seconds = transcript_result
                    else:
                        transcript_text = transcript_result
                        duration_seconds = None
                    
                    # Validate transcript text
                    if transcript_text is None:
                        logger.warning(f"⚠️ Attempt {attempt}: Transcript text is None")
                        if attempt < max_retries:
                            continue
                        else:
                            raise ValueError("Transcript text is None - transcription may have failed silently")
                    
                    if transcript_text and len(transcript_text.strip()) > 10:
                        logger.info(f"✅✅✅ SUCCESS: Transcribed REAL audio for call {call_id} ({len(transcript_text)} chars)")
                        logger.info(f"📝 Transcript preview: {transcript_text[:300]}...")
                        if duration_seconds:
                            logger.info(f"⏱️ Duration extracted: {duration_seconds} seconds")
                        return transcript_text, duration_seconds
                    else:
                        transcript_length = len(transcript_text.strip()) if transcript_text else 0
                        logger.warning(f"⚠️ Attempt {attempt}: Transcription result too short or empty (length: {transcript_length})")
                        if attempt < max_retries:
                            continue
                        else:
                            raise ValueError(f"Transcript too short ({transcript_length} chars) - audio may be empty, silent, or unsupported format")
                        
                except Exception as whisper_error:
                    last_error = whisper_error
                    logger.error(f"❌ Attempt {attempt}/{max_retries} failed: {whisper_error}")
                    import traceback
                    logger.error(traceback.format_exc())
                    
                    if attempt < max_retries:
                        logger.info(f"🔄 Retrying transcription in 2 seconds...")
                        import asyncio
                        await asyncio.sleep(2)
                        continue
            
            # ALL ATTEMPTS FAILED - This is a critical error
            error_msg = f"❌❌❌ CRITICAL: Failed to transcribe real audio after {max_retries} attempts for call {call_id}"
            logger.error(error_msg)
            if last_error:
                logger.error(f"Last error type: {type(last_error).__name__}")
                logger.error(f"Last error message: {str(last_error)}")
                # Format error message better
                if "S3" in str(last_error) or "download" in str(last_error).lower():
                    raise ValueError(f"S3 download failed: {str(last_error)}. Check AWS credentials and S3 bucket access.")
                elif "Whisper" in str(last_error) or "transcription" in str(last_error).lower():
                    raise ValueError(f"Whisper API error: {str(last_error)}. Check OpenAI API key and file format.")
                else:
                    raise ValueError(f"Transcription failed: {str(last_error)}")
            else:
                raise ValueError("Transcription failed: Unknown error (all attempts returned None)")
            
        except ValueError as ve:
            # Re-raise ValueError (these are critical errors)
            raise
        except Exception as e:
            logger.error(f"❌ FATAL ERROR transcribing audio for call {call_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise ValueError(f"Transcription service error: {str(e)}")
    
    async def _transcribe_with_whisper(self, s3_url: str, call_id: int, language: Optional[str] = None, client_credentials: dict = None, translate_to_english: bool = False) -> tuple[Optional[str], Optional[int]]:
        """
        Transcribe REAL audio using OpenAI Whisper API
        Downloads the actual audio file from S3 and transcribes it
        Returns: (transcript_text, duration_seconds)
        """
        try:
            logger.info(f"🎙️ Starting REAL Whisper transcription for call {call_id}")
            
            # Import S3 service to download the audio file
            from ..services.s3_service import S3Service
            
            # Create S3 client with client-specific credentials
            if client_credentials:
                logger.info(f"🔑 Using client-specific S3 credentials for download")
                s3_client = S3Service()._client_from_credentials(
                    client_credentials['access_key'],
                    client_credentials['secret_key'],
                    client_credentials['region']
                )
                bucket_name = client_credentials['bucket_name']
                
                # Parse S3 key from URL
                from urllib.parse import urlparse
                parsed = urlparse(s3_url)
                s3_key = parsed.path.lstrip('/')
                
                logger.info(f"📥 Downloading REAL audio file from S3: bucket={bucket_name}, key={s3_key}")
                
                try:
                    response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
                    audio_bytes = response['Body'].read()
                    logger.info(f"✅ Downloaded {len(audio_bytes)} bytes of REAL audio for call {call_id}")
                except Exception as download_error:
                    logger.error(f"❌ Failed to download audio from S3: {download_error}")
                    raise ValueError(f"S3 download failed: {download_error}")
            else:
                # Fallback to global s3_service (shouldn't happen in production)
                logger.warning(f"⚠️ No client credentials provided, using global S3 service (may fail)")
                from ..services.s3_service import s3_service
                logger.info(f"📥 Downloading audio file from S3: {s3_url}")
                audio_bytes = await s3_service.download_file(s3_url)
            
            if not audio_bytes:
                error_msg = f"❌ CRITICAL: Failed to download audio file for call {call_id} from S3. Audio bytes is None or empty."
                logger.error(error_msg)
                logger.error(f"   S3 URL: {s3_url}")
                logger.error(f"   Client credentials provided: {client_credentials is not None}")
                if client_credentials:
                    logger.error(f"   Bucket: {client_credentials.get('bucket_name')}, Region: {client_credentials.get('region')}")
                raise ValueError("S3 download failed: No audio data received")
            
            if len(audio_bytes) < 100:
                error_msg = f"❌ CRITICAL: Downloaded audio file is too small ({len(audio_bytes)} bytes) - file may be corrupted or invalid"
                logger.error(error_msg)
                raise ValueError(f"S3 download failed: File too small ({len(audio_bytes)} bytes)")
            
            logger.info(f"✅ Downloaded {len(audio_bytes)} bytes of audio for call {call_id}")
            
            # Create a temporary file for the audio
            import tempfile
            import os
            
            # Get file extension from S3 URL
            filename = s3_url.split('/')[-1]
            file_extension = os.path.splitext(filename)[1] or '.mp3'
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                temp_file.write(audio_bytes)
                temp_file_path = temp_file.name
            
            # CRITICAL: Extract audio duration BEFORE transcribing - this MUST happen for all calls
            # This ensures EVERY call (manual upload, S3 auto-upload, single or multiple) gets duration
            duration_seconds = None
            try:
                logger.info(f"⏱️ === ATTEMPTING TO EXTRACT DURATION FOR CALL {call_id} ===")
                logger.info(f"⏱️ Temp file path: {temp_file_path}")
                from ..utils.file_utils import AudioProcessor
                
                # Check if file exists and has content
                if os.path.exists(temp_file_path):
                    file_size = os.path.getsize(temp_file_path)
                    logger.info(f"⏱️ Temp audio file exists: {temp_file_path}, size: {file_size} bytes")
                    
                    # Try to extract duration - this is CRITICAL for all new calls
                    duration_seconds = AudioProcessor.get_audio_duration(temp_file_path)
                    
                    if duration_seconds and duration_seconds > 0:
                        logger.info(f"⏱️ ✅✅✅ SUCCESS: Extracted audio duration for call {call_id}: {duration_seconds} seconds ({duration_seconds // 60}:{(duration_seconds % 60):02d})")
                    else:
                        logger.error(f"⏱️ ❌❌❌ DURATION EXTRACTION RETURNED None or 0 for call {call_id}")
                        logger.error(f"⏱️ This will cause N/A to appear in My Calls page!")
                        logger.error(f"⏱️ Attempting manual fallback extraction...")
                        try:
                            from pydub import AudioSegment
                            logger.info(f"⏱️ pydub is available, trying direct extraction...")
                            # Try manual extraction as fallback
                            try:
                                audio = AudioSegment.from_file(temp_file_path)
                                duration_ms = len(audio)
                                duration_seconds = duration_ms // 1000
                                if duration_seconds > 0:
                                    logger.info(f"⏱️ ✅ MANUAL EXTRACTION SUCCESS: {duration_seconds}s ({duration_seconds // 60}:{(duration_seconds % 60):02d})")
                                else:
                                    logger.error(f"⏱️ ❌ Manual extraction also returned 0")
                            except Exception as manual_error:
                                logger.error(f"⏱️ ❌ Manual extraction failed: {manual_error}")
                                import traceback
                                logger.error(f"⏱️ Manual extraction traceback: {traceback.format_exc()}")
                        except ImportError:
                            logger.error(f"⏱️ ❌ pydub is NOT available - duration extraction will fail!")
                else:
                    logger.error(f"⏱️ ❌ Temp audio file does not exist: {temp_file_path}")
            except Exception as dur_error:
                logger.error(f"⏱️ ❌❌❌ CRITICAL ERROR extracting duration for call {call_id}: {dur_error}")
                import traceback
                logger.error(f"⏱️ Duration extraction traceback: {traceback.format_exc()}")
                # Keep duration_seconds as None - fallback will try to extract later
            
            # CRITICAL: If duration wasn't extracted yet, try one more time before transcription
            if not duration_seconds or duration_seconds <= 0:
                logger.warning(f"⏱️ ⚠️ Duration not extracted yet for call {call_id}, trying again before transcription...")
                try:
                    from ..utils.file_utils import AudioProcessor
                    if os.path.exists(temp_file_path):
                        duration_seconds = AudioProcessor.get_audio_duration(temp_file_path)
                        if duration_seconds and duration_seconds > 0:
                            logger.info(f"⏱️ ✅ Duration extracted before transcription: {duration_seconds}s")
                        else:
                            logger.error(f"⏱️ ❌ Duration extraction still failed before transcription")
                except Exception as pre_transcribe_error:
                    logger.error(f"⏱️ ❌ Pre-transcription duration extraction failed: {pre_transcribe_error}")
            
            try:
                logger.info(f"Transcribing audio file with speaker diarization: {temp_file_path}")
                
                # First, try to get detailed transcription with timestamps for speaker diarization
                detailed_transcript = await self._get_detailed_transcription(temp_file_path, language, call_id, translate_to_english)
                
                if detailed_transcript:
                    # Process the detailed transcript for speaker diarization
                    speaker_separated_transcript = await self._perform_speaker_diarization(
                        detailed_transcript, temp_file_path, call_id
                    )
                    
                    if speaker_separated_transcript:
                        logger.info(f"Speaker diarization completed for call {call_id}")
                        # CRITICAL: Ensure duration is returned even if it wasn't extracted earlier
                        if not duration_seconds or duration_seconds <= 0:
                            logger.warning(f"⏱️ ⚠️ Duration still missing after diarization, will be extracted in final check")
                        return speaker_separated_transcript, duration_seconds
                
                # Fallback to standard transcription if diarization fails
                logger.info(f"Falling back to standard transcription for call {call_id}")
                with open(temp_file_path, 'rb') as audio_file:
                    detected_language = None
                    
                    # Try to detect language (optional - don't fail if it doesn't work)
                    # This helps improve accuracy but is not required
                    try:
                        logger.info(f"🔍 Detecting language for call {call_id}...")
                        detection_params = {
                            "model": "whisper-1",
                            "file": audio_file,
                            "response_format": "verbose_json"
                        }
                        # Don't set language for detection - let Whisper auto-detect
                        detection_response = self.openai_client.audio.transcriptions.create(**detection_params)
                        
                        if detection_response and hasattr(detection_response, 'language'):
                            raw_language = detection_response.language
                            logger.info(f"🌐 Detected language (raw): {raw_language}")
                            # Normalize language code (handle "english" -> "en", "arabic" -> "ar")
                            detected_language = self._normalize_language_code(raw_language)
                            logger.info(f"🌐 Normalized language code: {detected_language}")
                            # Validate (non-blocking - just logs, doesn't raise errors)
                            self._validate_language(detected_language, call_id)
                        else:
                            logger.warning(f"⚠️ Language detection did not return language field - proceeding anyway")
                    except Exception as detection_error:
                        # Don't fail if language detection fails - we can still process
                        logger.warning(f"⚠️ Language detection failed: {detection_error} - proceeding without language detection")
                        logger.info(f"✅ Will proceed with transcription/translation anyway (Whisper supports auto-detection)")
                    
                    # Now do the actual transcription/translation
                    audio_file.seek(0)  # Reset file pointer
                    if translate_to_english:
                        logger.info(f"📝 Translating audio to English (detected: {detected_language or language or 'auto-detect'})")
                        # Use translations API - works for ANY language (English, Arabic, etc.)
                        # For English: returns English text
                        # For Arabic: translates to English
                        # For other languages: translates to English
                        whisper_params = {
                            "model": "whisper-1",
                            "file": audio_file,
                            "response_format": "text"
                        }
                        # Optionally set language hint if we detected it (improves accuracy)
                        # But don't require it - translations API works without it
                        if detected_language:
                            whisper_params["language"] = detected_language
                            logger.info(f"📝 Using detected language hint: {detected_language}")
                        elif language:
                            normalized_lang = self._normalize_language_code(language)
                            if normalized_lang:
                                whisper_params["language"] = normalized_lang
                                logger.info(f"📝 Using provided language hint: {normalized_lang}")
                        
                        try:
                            transcript_response = self.openai_client.audio.translations.create(**whisper_params)
                        except Exception as translation_error:
                            error_str = str(translation_error).lower()
                            # If error is related to language parameter, try without it
                            if "language" in error_str or "invalid" in error_str:
                                logger.warning(f"⚠️ Translation with language hint failed: {translation_error}")
                                logger.info(f"🔄 Retrying translation without language hint (auto-detect)...")
                                whisper_params_no_lang = {
                                    "model": "whisper-1",
                                    "file": audio_file,
                                    "response_format": "text"
                                }
                                audio_file.seek(0)
                                transcript_response = self.openai_client.audio.translations.create(**whisper_params_no_lang)
                            else:
                                raise
                    else:
                        logger.info(f"📝 Transcribing audio in original language: {detected_language or language or 'auto-detect'}")
                        # Use transcriptions API to keep original language
                        whisper_params = {
                            "model": "whisper-1",
                            "file": audio_file,
                            "response_format": "text"
                        }
                        # Use detected language if available, otherwise use provided language
                        if detected_language:
                            whisper_params["language"] = detected_language
                        elif language:
                            normalized_lang = self._normalize_language_code(language)
                            if normalized_lang:
                                whisper_params["language"] = normalized_lang
                        transcript_response = self.openai_client.audio.transcriptions.create(**whisper_params)
                
                transcript_text = transcript_response if isinstance(transcript_response, str) else str(transcript_response)
                
                logger.info(f"Standard Whisper transcription completed for call {call_id}: {len(transcript_text)} characters")
                logger.info(f"Transcript preview: {transcript_text[:200]}...")
                
                # CRITICAL: Ensure duration is returned even if extraction failed
                if not duration_seconds or duration_seconds <= 0:
                    logger.warning(f"⏱️ ⚠️ Duration still missing after transcription, will be extracted in final check")
                
                return transcript_text, duration_seconds
                
            finally:
                # Clean up temporary file AFTER we're sure we don't need it
                try:
                    os.unlink(temp_file_path)
                    logger.info(f"Cleaned up temporary file: {temp_file_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up temporary file {temp_file_path}: {cleanup_error}")
            
        except ValueError as ve:
            # Re-raise ValueError (these are already formatted errors)
            logger.error(f"❌ ValueError in Whisper transcription for call {call_id}: {ve}")
            raise
        except Exception as e:
            # Log full error details
            logger.error(f"❌❌❌ ERROR in Whisper transcription for call {call_id}: {e}")
            logger.error(f"   Error type: {type(e).__name__}")
            import traceback
            logger.error(f"   Full traceback:\n{traceback.format_exc()}")
            
            # Provide a helpful error message based on error type
            error_str = str(e).lower()
            if "nosuchkey" in error_str or "accessdenied" in error_str or "invalidaccesskeyid" in error_str:
                error_msg = "Unable to access audio file. Please check your AWS S3 credentials and permissions."
            elif "connection" in error_str or "timeout" in error_str:
                error_msg = "Network connection error. Please check your internet connection and try again."
            elif "audio" in error_str or "format" in error_str or "unsupported" in error_str:
                error_msg = "Audio file format error. Please ensure the file is a valid audio format (MP3, WAV, M4A, AAC, OGG, FLAC) and not corrupted."
            elif "language" in error_str or "translation" in error_str or "not supported" in error_str:
                # Check if it's a specific language validation error
                if "not supported" in error_str and ("arabic" in error_str.lower() or "english" in error_str.lower()):
                    error_msg = "Language processing error. The detected language could not be processed. Please ensure your audio is clear and contains speech."
                else:
                    # Generic language/translation error - don't restrict to Arabic/English since Whisper supports many languages
                    error_msg = "Language processing error. Please ensure your audio contains clear speech in any supported language."
            elif "openai" in error_str or "api key" in error_str:
                error_msg = "AI service configuration error. Please contact your administrator."
            elif "quota" in error_str or "rate limit" in error_str:
                error_msg = "Service temporarily unavailable due to high demand. Please try again in a few minutes."
            else:
                error_msg = f"Processing error: {str(e)}. Please try again or contact support if the problem persists."
            
            raise ValueError(error_msg)
    
    def _normalize_language_code(self, language: Optional[str]) -> Optional[str]:
        """
        Normalize language code from various formats to ISO 639-1 codes.
        Handles variations like "english" -> "en", "arabic" -> "ar"
        Also handles common variations and full language names.
        """
        if language is None:
            return None
        
        # Clean the language string
        language_clean = language.lower().strip() if language else None
        if not language_clean:
            return None
        
        # Comprehensive language mapping - handle full names and variations
        language_mapping = {
            # English variations
            "en": "en",
            "english": "en",
            "eng": "en",
            # Arabic variations
            "ar": "ar",
            "arabic": "ar",
            "ara": "ar",
            # Common other languages (for future support or better handling)
            "es": "es",  # Spanish
            "spanish": "es",
            "fr": "fr",  # French
            "french": "fr",
            "de": "de",  # German
            "german": "de",
            "zh": "zh",  # Chinese
            "chinese": "zh",
            "hi": "hi",  # Hindi
            "hindi": "hi",
            "pt": "pt",  # Portuguese
            "portuguese": "pt",
        }
        
        # First check exact match
        if language_clean in language_mapping:
            return language_mapping[language_clean]
        
        # Check if it starts with a known prefix
        for key, value in language_mapping.items():
            if language_clean.startswith(key) or key in language_clean:
                return value
        
        # If not found, return the cleaned lowercase version (might be valid ISO code)
        # This allows other languages to pass through
        return language_clean
    
    def _validate_language(self, detected_language: Optional[str], call_id: int) -> None:
        """
        Validate language detection result.
        Since we use translate_to_english=True, we can process any language,
        but we prefer Arabic and English. Other languages will be logged as warnings.
        Note: Language should already be normalized before calling this function
        """
        if detected_language is None:
            # If language is None, we can't validate - allow it to proceed
            logger.warning(f"⚠️ Language detection returned None for call {call_id} - proceeding without validation")
            return
        
        preferred_languages = ["ar", "en"]  # Preferred languages
        detected_language_lower = detected_language.lower().strip() if detected_language else None
        
        if detected_language_lower in preferred_languages:
            logger.info(f"✅ Language validated: {detected_language} (preferred language)")
        else:
            # Log a warning but don't fail - we can translate any language to English
            logger.warning(f"⚠️ Detected language '{detected_language}' is not Arabic or English, but will be translated to English anyway")
            logger.info(f"✅ Language '{detected_language}' will be processed and translated to English")
    
    async def _get_detailed_transcription(self, audio_file_path: str, language: Optional[str] = None, call_id: int = 0, translate_to_english: bool = False) -> Optional[dict]:
        """
        Get detailed transcription with timestamps for speaker diarization
        Supports multi-language with auto-detect and translation
        """
        try:
            logger.info(f"Getting detailed transcription for call {call_id} (language: {language or 'auto-detect'}, translate: {translate_to_english})")
            
            with open(audio_file_path, 'rb') as audio_file:
                # Build whisper params for detailed transcription
                whisper_params = {
                    "model": "whisper-1",
                    "file": audio_file,
                    "response_format": "verbose_json",
                    "timestamp_granularities": ["segment", "word"]
                }
                
                # Normalize language if provided (before API call)
                normalized_language = self._normalize_language_code(language) if language else None
                
                # Determine which API to use and set language
                if translate_to_english:
                    logger.info(f"📝 Getting detailed translation to English (original: {normalized_language or language or 'auto-detect'})")
                    # Use translations API to translate to English
                    # Works for ANY language (English, Arabic, etc.)
                    if normalized_language:
                        whisper_params["language"] = normalized_language
                        logger.info(f"📝 Using language hint: {normalized_language}")
                    
                    try:
                        transcript_response = self.openai_client.audio.translations.create(**whisper_params)
                    except Exception as translation_error:
                        error_str = str(translation_error).lower()
                        # If error is related to language parameter, try without it
                        if "language" in error_str or "invalid" in error_str:
                            logger.warning(f"⚠️ Translation with language hint failed: {translation_error}")
                            logger.info(f"🔄 Retrying translation without language hint (auto-detect)...")
                            whisper_params_no_lang = {
                                "model": "whisper-1",
                                "file": audio_file,
                                "response_format": "verbose_json",
                                "timestamp_granularities": ["segment", "word"]
                            }
                            audio_file.seek(0)
                            transcript_response = self.openai_client.audio.translations.create(**whisper_params_no_lang)
                        else:
                            raise
                else:
                    logger.info(f"📝 Getting detailed transcription in original language: {normalized_language or language or 'auto-detect'}")
                    # Use transcriptions API to keep original language
                    # Only set language if specified (not None) - None means auto-detect
                    if normalized_language:
                        whisper_params["language"] = normalized_language
                    transcript_response = self.openai_client.audio.transcriptions.create(**whisper_params)
            
            # Validate detected language (non-blocking - just logs)
            if transcript_response and hasattr(transcript_response, 'language'):
                raw_lang = transcript_response.language
                logger.info(f"🌐 Detected language (raw): {raw_lang}")
                # Normalize language code (handle "english" -> "en", "arabic" -> "ar")
                detected_lang = self._normalize_language_code(raw_lang)
                logger.info(f"🌐 Normalized language code: {detected_lang}")
                # Validate (non-blocking - just logs, doesn't raise errors)
                self._validate_language(detected_lang, call_id)
            
            if transcript_response and hasattr(transcript_response, 'segments'):
                logger.info(f"Detailed transcription retrieved for call {call_id} with {len(transcript_response.segments)} segments")
                return transcript_response
            else:
                logger.warning(f"No detailed segments found for call {call_id}")
                return None
                
        except ValueError as ve:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Error getting detailed transcription for call {call_id}: {e}")
            return None
    
    async def _perform_speaker_diarization(self, detailed_transcript: dict, audio_file_path: str, call_id: int) -> Optional[str]:
        """
        Perform speaker diarization on the detailed transcript
        """
        try:
            logger.info(f"Performing speaker diarization for call {call_id}")
            
            # Extract segments with timestamps
            segments = detailed_transcript.segments if hasattr(detailed_transcript, 'segments') else []
            
            if not segments:
                logger.warning(f"No segments available for speaker diarization in call {call_id}")
                return None
            
            # Analyze segments for speaker changes
            speaker_segments = self._analyze_speaker_changes(segments, call_id)
            
            # Generate speaker-separated transcript
            speaker_transcript = self._generate_speaker_transcript(speaker_segments, call_id)
            
            logger.info(f"Speaker diarization completed for call {call_id}")
            return speaker_transcript
            
        except Exception as e:
            logger.error(f"Error in speaker diarization for call {call_id}: {e}")
            return None
    
    def _analyze_speaker_changes(self, segments: list, call_id: int) -> list:
        """
        Analyze segments to identify speaker changes based on various factors
        """
        try:
            logger.info(f"Analyzing speaker changes for {len(segments)} segments in call {call_id}")
            
            speaker_segments = []
            current_speaker = "Speaker 1"
            speaker_confidence_threshold = 0.3
            
            for i, segment in enumerate(segments):
                # Get segment information
                start_time = segment.start if hasattr(segment, 'start') else 0
                end_time = segment.end if hasattr(segment, 'end') else 0
                text = segment.text if hasattr(segment, 'text') else ""
                
                # Analyze for potential speaker changes
                speaker_change = self._detect_speaker_change(segment, i, segments, call_id)
                
                if speaker_change:
                    # Switch speaker
                    if current_speaker == "Speaker 1":
                        current_speaker = "Speaker 2"
                    else:
                        current_speaker = "Speaker 1"
                
                speaker_segments.append({
                    'speaker': current_speaker,
                    'start_time': start_time,
                    'end_time': end_time,
                    'text': text.strip(),
                    'confidence': getattr(segment, 'no_speech_prob', 0.5) if hasattr(segment, 'no_speech_prob') else 0.5
                })
            
            logger.info(f"Speaker analysis completed for call {call_id}: {len(speaker_segments)} segments analyzed")
            return speaker_segments
            
        except Exception as e:
            logger.error(f"Error analyzing speaker changes for call {call_id}: {e}")
            return []
    
    def _detect_speaker_change(self, current_segment: dict, segment_index: int, all_segments: list, call_id: int) -> bool:
        """
        Detect if there's a speaker change between segments
        """
        try:
            # Skip first segment
            if segment_index == 0:
                return False
            
            current_text = current_segment.text if hasattr(current_segment, 'text') else ""
            current_start = current_segment.start if hasattr(current_segment, 'start') else 0
            
            # Get previous segment
            prev_segment = all_segments[segment_index - 1]
            prev_text = prev_segment.text if hasattr(prev_segment, 'text') else ""
            prev_end = prev_segment.end if hasattr(prev_segment, 'end') else 0
            
            # Calculate gap between segments
            gap = current_start - prev_end
            
            # Speaker change indicators
            speaker_change = False
            
            # 1. Large time gap (more than 2 seconds)
            if gap > 2.0:
                speaker_change = True
                logger.debug(f"Speaker change detected due to time gap: {gap:.2f}s in call {call_id}")
            
            # 2. Question patterns (often indicate speaker change)
            if self._is_question_pattern(current_text) or self._is_question_pattern(prev_text):
                speaker_change = True
                logger.debug(f"Speaker change detected due to question pattern in call {call_id}")
            
            # 3. Greeting patterns
            if self._is_greeting_pattern(current_text) or self._is_greeting_pattern(prev_text):
                speaker_change = True
                logger.debug(f"Speaker change detected due to greeting pattern in call {call_id}")
            
            # 4. Response indicators
            if self._is_response_pattern(current_text):
                speaker_change = True
                logger.debug(f"Speaker change detected due to response pattern in call {call_id}")
            
            # 5. Length-based analysis (short responses often indicate different speaker)
            if len(current_text.strip()) < 20 and gap > 0.5:
                speaker_change = True
                logger.debug(f"Speaker change detected due to short response in call {call_id}")
            
            return speaker_change
            
        except Exception as e:
            logger.error(f"Error detecting speaker change for call {call_id}: {e}")
            return False
    
    def _is_question_pattern(self, text: str) -> bool:
        """Check if text contains question patterns"""
        text_lower = text.lower().strip()
        question_indicators = [
            '?', 'how', 'what', 'when', 'where', 'why', 'who', 'can you', 'could you', 
            'would you', 'do you', 'are you', 'is it', 'was it', 'will you'
        ]
        return any(indicator in text_lower for indicator in question_indicators)
    
    def _is_greeting_pattern(self, text: str) -> bool:
        """Check if text contains greeting patterns"""
        text_lower = text.lower().strip()
        greeting_indicators = [
            'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening',
            'thanks', 'thank you', 'bye', 'goodbye', 'see you', 'talk to you'
        ]
        return any(indicator in text_lower for indicator in greeting_indicators)
    
    def _is_response_pattern(self, text: str) -> bool:
        """Check if text contains response patterns"""
        text_lower = text.lower().strip()
        response_indicators = [
            'yes', 'no', 'okay', 'ok', 'sure', 'absolutely', 'definitely', 
            'of course', 'certainly', 'i see', 'i understand', 'that sounds'
        ]
        return any(indicator in text_lower for indicator in response_indicators)
    
    def _generate_speaker_transcript(self, speaker_segments: list, call_id: int) -> str:
        """
        Generate formatted transcript with speaker labels
        """
        try:
            logger.info(f"Generating speaker transcript for call {call_id}")
            
            transcript_lines = []
            current_speaker = None
            current_text_parts = []
            
            for segment in speaker_segments:
                speaker = segment['speaker']
                text = segment['text']
                start_time = segment['start_time']
                
                # Skip empty or very short segments
                if not text or len(text.strip()) < 3:
                    continue
                
                # If speaker changed, add previous speaker's text
                if current_speaker and current_speaker != speaker:
                    if current_text_parts:
                        combined_text = ' '.join(current_text_parts).strip()
                        if combined_text:
                            transcript_lines.append(f"{current_speaker}: {combined_text}")
                    current_text_parts = []
                
                # Add current text
                current_text_parts.append(text)
                current_speaker = speaker
            
            # Add final speaker's text
            if current_speaker and current_text_parts:
                combined_text = ' '.join(current_text_parts).strip()
                if combined_text:
                    transcript_lines.append(f"{current_speaker}: {combined_text}")
            
            # Join all lines
            final_transcript = '\n\n'.join(transcript_lines)
            
            logger.info(f"Generated speaker transcript for call {call_id}: {len(transcript_lines)} speaker segments")
            return final_transcript
            
        except Exception as e:
            logger.error(f"Error generating speaker transcript for call {call_id}: {e}")
            return ""
    
    def _analyze_speakers_in_transcript(self, transcript_text: str) -> dict:
        """
        Analyze speaker distribution and patterns in the transcript
        """
        try:
            speaker_analysis = {
                'total_speakers': 0,
                'speaker_distribution': {},
                'talk_time_ratio': 0.5,
                'speaker_turns': 0,
                'longest_speaker': None,
                'most_active_speaker': None
            }
            
            # Check if transcript has speaker labels
            if 'Speaker 1:' in transcript_text or 'Speaker 2:' in transcript_text:
                logger.info("Speaker-labeled transcript detected")
                
                # Parse speaker segments
                speaker_segments = []
                current_speaker = None
                current_text = []
                
                lines = transcript_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Check if line starts with speaker label
                    if line.startswith('Speaker 1:') or line.startswith('Speaker 2:'):
                        # Save previous speaker's text
                        if current_speaker and current_text:
                            speaker_segments.append({
                                'speaker': current_speaker,
                                'text': ' '.join(current_text),
                                'length': len(' '.join(current_text))
                            })
                        
                        # Start new speaker
                        speaker_part = line.split(':', 1)[0].strip()
                        current_speaker = speaker_part
                        current_text = [line.split(':', 1)[1].strip()] if ':' in line else []
                    else:
                        # Continue current speaker's text
                        if current_speaker:
                            current_text.append(line)
                
                # Add final speaker's text
                if current_speaker and current_text:
                    speaker_segments.append({
                        'speaker': current_speaker,
                        'text': ' '.join(current_text),
                        'length': len(' '.join(current_text))
                    })
                
                # Analyze speaker distribution
                if speaker_segments:
                    speaker_stats = {}
                    for segment in speaker_segments:
                        speaker = segment['speaker']
                        if speaker not in speaker_stats:
                            speaker_stats[speaker] = {
                                'total_length': 0,
                                'segments': 0,
                                'words': 0
                            }
                        speaker_stats[speaker]['total_length'] += segment['length']
                        speaker_stats[speaker]['segments'] += 1
                        speaker_stats[speaker]['words'] += len(segment['text'].split())
                    
                    speaker_analysis['total_speakers'] = len(speaker_stats)
                    speaker_analysis['speaker_distribution'] = speaker_stats
                    speaker_analysis['speaker_turns'] = len(speaker_segments)
                    
                    # Find most active speaker
                    most_active = max(speaker_stats.items(), key=lambda x: x[1]['total_length'])
                    speaker_analysis['most_active_speaker'] = most_active[0]
                    
                    # Calculate talk time ratio (Speaker 1 vs Speaker 2)
                    if 'Speaker 1' in speaker_stats and 'Speaker 2' in speaker_stats:
                        speaker1_length = speaker_stats['Speaker 1']['total_length']
                        speaker2_length = speaker_stats['Speaker 2']['total_length']
                        total_length = speaker1_length + speaker2_length
                        
                        if total_length > 0:
                            # Assuming Speaker 1 is sales rep, calculate their talk time ratio
                            speaker_analysis['talk_time_ratio'] = speaker1_length / total_length
                    
                    logger.info(f"Speaker analysis completed: {len(speaker_stats)} speakers, {len(speaker_segments)} turns")
                else:
                    logger.warning("No speaker segments found in transcript")
            else:
                logger.info("No speaker labels found in transcript")
            
            return speaker_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing speakers in transcript: {e}")
            return {
                'total_speakers': 0,
                'speaker_distribution': {},
                'talk_time_ratio': 0.5,
                'speaker_turns': 0,
                'longest_speaker': None,
                'most_active_speaker': None
            }
    
    def _generate_unique_transcript_for_call(self, s3_url: str, call_id: int) -> str:
        """Generate a unique transcript specifically for this call ID"""
        import hashlib
        
        # Create unique hash combining S3 URL and call_id
        unique_string = f"{s3_url}_{call_id}"
        unique_hash = hashlib.md5(unique_string.encode()).hexdigest()
        
        filename = s3_url.split('/')[-1] if '/' in s3_url else s3_url
        
        # Generate call-specific transcript
        transcript = f"""
        [Call ID: {call_id}] [File: {filename}] [Hash: {unique_hash[:8]}]
        
        Sales Rep: Hello, this is a call regarding your inquiry about our services. 
        How can I help you today?
        
        Customer: Hi, I'm interested in learning more about your solutions. 
        Can you tell me about your main offerings?
        
        Sales Rep: Absolutely! We specialize in providing comprehensive business solutions 
        tailored to companies like yours. What specific challenges are you facing?
        
        Customer: We're looking to improve our current processes and need something 
        that can scale with our growth.
        
        Sales Rep: That's exactly what we help with. Our platform is designed to grow 
        with your business and adapt to your changing needs.
        
        Customer: That sounds promising. What's the next step?
        
        Sales Rep: I'd love to schedule a demo to show you how our solution can address 
        your specific requirements. When would be a good time?
        
        Customer: How about next week? I'll need to check my calendar.
        
        Sales Rep: Perfect! I'll send you some available time slots and you can choose 
        what works best for you.
        
        Customer: Great, thank you for your time.
        
        Sales Rep: You're welcome! I look forward to speaking with you next week. 
        Have a wonderful day!
        
        [End of Call - Duration: 5 minutes]
        [Unique Call Identifier: {unique_hash}]
        """
        
        logger.info(f"Generated unique transcript for call {call_id} (file: {filename}, hash: {unique_hash[:8]})")
        return transcript.strip()
    
    def _generate_mock_transcript(self, s3_url: str, call_id: int = None) -> str:
        """Generate a UNIQUE mock transcript for each call based on S3 URL and call_id"""
        import hashlib
        import random
        from datetime import datetime
        
        # Create unique hash from S3 URL AND call_id to ensure uniqueness per call
        unique_string = f"{s3_url}_{call_id}" if call_id else s3_url
        url_hash = hashlib.md5(unique_string.encode()).hexdigest()
        
        # Extract filename from S3 URL for context
        filename = s3_url.split('/')[-1] if '/' in s3_url else s3_url
        
        # Use hash to create consistent but unique content
        hash_int = int(url_hash[:8], 16)
        random.seed(hash_int)  # Use hash as seed for consistent results
        
        # Generate unique customer names and companies
        customer_names = ["Sarah", "John", "Emily", "Michael", "Lisa", "David", "Jennifer", "Robert", "Amanda", "Chris"]
        company_names = ["TechCorp", "DataFlow Inc", "CloudSolutions", "BusinessFirst", "InnovateLabs", "ProActive Systems", "SmartWorks", "FutureTech", "DigitalEdge", "NextGen Corp"]
        sales_rep_names = ["Mike", "Alex", "Jordan", "Taylor", "Casey", "Riley", "Morgan", "Jamie", "Avery", "Quinn"]
        products = ["CRM System", "Project Management Tool", "Analytics Platform", "Communication Suite", "Data Management Solution", "Workflow Automation", "Reporting Dashboard", "Integration Hub", "Security Suite", "Cloud Storage"]
        
        # Select based on hash for consistency
        customer_name = customer_names[hash_int % len(customer_names)]
        company_name = company_names[(hash_int // 10) % len(company_names)]
        sales_rep_name = sales_rep_names[(hash_int // 100) % len(sales_rep_names)]
        product = products[(hash_int // 1000) % len(products)]
        
        # Generate unique conversation scenarios
        scenarios = [
            "initial_contact",
            "follow_up_demo", 
            "pricing_discussion",
            "technical_questions",
            "objection_handling",
            "closing_attempt",
            "product_comparison",
            "implementation_timeline"
        ]
        
        scenario = scenarios[hash_int % len(scenarios)]
        
        # Generate unique conversation based on scenario
        if scenario == "initial_contact":
            mock_transcript = f"""
            Sales Rep: Hi {customer_name}, this is {sales_rep_name} from {company_name}. Thanks for taking my call today. 
            I understand you downloaded our {product} guide last week?
            
            Customer: Yes, that's right. We're looking into ways to streamline our business processes.
            
            Sales Rep: Perfect. Can you tell me what challenges you're currently facing with your existing setup?
            
            Customer: Well, we're using manual processes right now, but it's getting difficult to manage everything as we grow.
            We need something more automated.
            
            Sales Rep: That makes sense. Our {product} is specifically designed for growing companies like yours.
            Would you be interested in seeing a demo of how it could help streamline your operations?
            
            Customer: Yes, that sounds interesting. When would be a good time?
            
            Sales Rep: How about next Tuesday at 2 PM? I can show you the key features and answer any questions you have.
            
            Customer: That works for me. I'll put it on my calendar.
            
            Sales Rep: Excellent. I'll send you a calendar invite with the meeting details.
            Is there anything specific you'd like me to focus on during the demo?
            
            Customer: I'd like to see how it handles automation and reporting features.
            
            Sales Rep: Perfect, I'll make sure to cover those areas. I'll also show you our integration capabilities.
            
            Customer: Great, looking forward to it. Thanks for your time today.
            
            Sales Rep: You're welcome, {customer_name}. I'll send that invite shortly and we'll talk again on Tuesday.
            Have a great rest of your day!
            """
            
        elif scenario == "pricing_discussion":
            mock_transcript = f"""
            Sales Rep: Hi {customer_name}, thanks for your interest in our {product}. 
            I wanted to follow up on the pricing discussion we had last week.
            
            Customer: Yes, I've been reviewing the proposal. The price seems a bit high for our budget.
            
            Sales Rep: I understand budget is always a concern. Let me show you how our {product} 
            can actually save you money in the long run through increased efficiency.
            
            Customer: How so? Can you give me some specific examples?
            
            Sales Rep: Absolutely. Based on what you've told me about your current processes, 
            you could save approximately 15-20 hours per week with our automation features.
            
            Customer: That does sound promising. What about implementation costs?
            
            Sales Rep: We offer free setup and training for the first month. Plus, our support team 
            will be available to help with any questions during the transition.
            
            Customer: That helps. Let me discuss this with my team and get back to you.
            
            Sales Rep: Of course. When would be a good time for me to follow up?
            
            Customer: How about next Friday? I should have an answer by then.
            
            Sales Rep: Perfect. I'll call you next Friday. In the meantime, I'll send you 
            some case studies from similar companies that might be helpful.
            
            Customer: That would be great. Thank you.
            
            Sales Rep: You're welcome, {customer_name}. Talk to you soon!
            """
            
        elif scenario == "objection_handling":
            mock_transcript = f"""
            Sales Rep: Hi {customer_name}, I wanted to follow up on our conversation about the {product}.
            
            Customer: Hi {sales_rep_name}. I've been thinking about it, but I'm not sure if it's the right fit for us.
            
            Sales Rep: I understand your concern. What specifically makes you feel it might not be the right fit?
            
            Customer: Well, we're a small company and I'm worried about the complexity. 
            We don't have a lot of technical resources.
            
            Sales Rep: That's actually one of the biggest advantages of our {product}. 
            It's designed to be user-friendly for non-technical users.
            
            Customer: Really? How easy is it to use?
            
            Sales Rep: Most of our customers are up and running within a day. We provide 
            step-by-step guides and video tutorials for every feature.
            
            Customer: What about support? What if we run into problems?
            
            Sales Rep: We offer 24/7 support via chat, email, and phone. Plus, 
            you get a dedicated account manager for the first 90 days.
            
            Customer: That does sound reassuring. What about the cost?
            
            Sales Rep: For a company your size, it would be about $200 per month, 
            which includes everything - the software, support, and training.
            
            Customer: That's actually more reasonable than I expected. Let me think about it.
            
            Sales Rep: Of course. Would it help if I set up a trial account so you can 
            test it with your team for a week?
            
            Customer: Yes, that would be very helpful. Can we do that?
            
            Sales Rep: Absolutely. I'll set that up for you today and send you the login details.
            
            Customer: Perfect. Thank you for being so understanding.
            
            Sales Rep: You're welcome, {customer_name}. I'll be in touch tomorrow with your trial access.
            """
            
        else:  # Default scenario
            mock_transcript = f"""
            Sales Rep: Hi {customer_name}, this is {sales_rep_name} from {company_name}. 
            I'm calling about the {product} we discussed.
            
            Customer: Hi {sales_rep_name}, yes I remember our conversation.
            
            Sales Rep: Great! I wanted to follow up and see if you had any questions 
            about the {product} or if you'd like to move forward.
            
            Customer: I've been reviewing the information you sent. It looks interesting, 
            but I need to discuss it with my team.
            
            Sales Rep: That makes perfect sense. What questions do you have that I might 
            be able to answer before you meet with your team?
            
            Customer: Well, I'm curious about the implementation timeline. 
            How long does it typically take to get up and running?
            
            Sales Rep: Great question. For most companies, it takes about 2-3 weeks 
            to fully implement and train your team. We handle all the setup.
            
            Customer: That's faster than I expected. What about data migration?
            
            Sales Rep: We have a dedicated team that handles all data migration. 
            They'll work with your IT department to ensure everything transfers smoothly.
            
            Customer: That's good to know. When would you need an answer by?
            
            Sales Rep: There's no rush on our end. Take your time to make the right decision. 
            However, we do have a special promotion ending at the end of this month.
            
            Customer: What kind of promotion?
            
            Sales Rep: We're offering 20% off the first year and free implementation. 
            It's a significant savings.
            
            Customer: That does sound like a good deal. Let me talk to my team this week 
            and get back to you.
            
            Sales Rep: Perfect. I'll follow up with you next Monday. In the meantime, 
            feel free to call me if you have any questions.
            
            Customer: Will do. Thanks for all the information, {sales_rep_name}.
            
            Sales Rep: You're welcome, {customer_name}. Have a great day!
            """
        
        # Add unique identifier to transcript
        unique_id = f"[Call ID: {url_hash[:8]}]"
        mock_transcript = f"{unique_id}\n{mock_transcript.strip()}"
        
        logger.info(f"Generated unique mock transcript for {filename} (scenario: {scenario}, hash: {url_hash[:8]})")
        logger.info(f"Mock transcription completed: {len(mock_transcript)} characters")
        
        return mock_transcript
    
    async def _generate_insights(self, transcript_text: str, language: Optional[str] = None) -> Optional[InsightsCreate]:
        """
        Generate insights from transcript - GUARANTEED to return insights
        """
        logger.info("=== STARTING INSIGHTS GENERATION ===")
        logger.info(f"Transcript length: {len(transcript_text)} characters")
        logger.info(f"Transcript preview: {transcript_text[:200]}...")
        
        try:
            # First try GPT-based insights if available
            if self.openai_client.api_key:
                logger.info("Attempting GPT-based insights generation")
                try:
                    gpt_insights = await self._generate_gpt_insights(transcript_text, language)
                    if gpt_insights:
                        logger.info(f"GPT insights generated successfully - Score: {gpt_insights.overall_score}")
                        return gpt_insights
                except Exception as gpt_error:
                    logger.warning(f"GPT insights generation failed: {gpt_error}, falling back to enhanced analysis")
        except Exception as e:
            logger.warning(f"GPT connection failed: {e}, using enhanced fallback insights")
        
        # Always use enhanced fallback insights to guarantee results
        logger.info("Using enhanced fallback insights generation")
        insights = self._generate_enhanced_fallback_insights(transcript_text)
        logger.info(f"Generated insights - Score: {insights.overall_score}, Sentiment: {insights.sentiment}")
        return insights
    
    async def _generate_gpt_insights(self, transcript_text: str, language: Optional[str] = None) -> Optional[InsightsCreate]:
        """
        Generate insights using GPT - with fallback to enhanced analysis
        """
        try:
            logger.info("Generating GPT-based insights")
            
            prompt = f"""You are an elite sales call analyst with 20+ years of experience evaluating B2B and B2C sales conversations. Your task is to analyze this sales call transcript with surgical precision and provide comprehensive insights that help sales teams improve performance and close more deals.

## TRANSCRIPT TO ANALYZE:
{transcript_text[:10000]}

## ANALYSIS FRAMEWORK - Analyze each of these dimensions:

### 1. OVERALL CALL QUALITY ASSESSMENT
- Evaluate the complete conversation flow from opening to closing
- Assess whether the call achieved its intended objectives
- Identify key strengths and critical weaknesses
- Determine if the sales rep followed best practices throughout
- Score: 0-100 based on professional standards

### 2. SENTIMENT ANALYSIS (CRITICAL - BE PRECISE)
Analyze sentiment at THREE levels:

**A. Overall Call Sentiment:**
- Calculate based on: customer tone, engagement level, resistance/acceptance ratio, positive vs negative language
- Consider: frequency of agreement ("yes", "exactly", "that makes sense") vs disagreement ("but", "however", "I'm not sure")
- Account for: enthusiasm indicators, concern indicators, neutral responses
- Return: "positive", "negative", or "neutral" - MUST be accurate based on transcript

**B. Segment-Based Sentiment:**
- Opening (first 20%): How did the call start? Warm/cold/neutral?
- Discovery (middle 40%): Customer engagement and interest level
- Objection Handling (if any): How objections were received and handled
- Closing (last 40%): Customer receptiveness to next steps

**C. Emotional Indicators:**
- Positive: excitement, agreement, asking detailed questions, requesting materials, mentioning budget/timeline
- Negative: skepticism, frequent objections, defensiveness, rushing to end call, vague responses
- Neutral: polite but unengaged, minimal responses, non-committal language

### 3. SALES REP PERFORMANCE METRICS

**A. Talk Time Ratio (0.0-1.0):**
- Calculate: Rep speaking time / Total call time
- Ideal range: 0.3-0.5 (rep should listen 50-70% of time)
- Score high if: Rep asks questions and listens more than talks
- Score low if: Rep dominates conversation (>60% talk time)

**B. Question Effectiveness (0-100):**
Evaluate the quality and strategic value of questions asked:
- Discovery questions: "Can you tell me about your current process?" (good), "What do you do?" (vague)
- Qualifying questions: "What's your budget?" (direct but may be too early), "What happens if you don't solve this?" (better)
- Objection handling questions: "What concerns do you have?" (excellent), "Why not?" (poor)
- Closing questions: "What would it take to move forward?" (excellent), "Ready to buy?" (poor)
- Score: Higher for strategic, open-ended questions that reveal information

**C. Objection Handling (0-100):**
- Identify all objections raised by customer
- Evaluate how rep addressed each: acknowledged vs ignored, empathized vs dismissed, provided solutions vs arguments
- Assess if rep used: LAER (Listen, Acknowledge, Explore, Respond) or similar frameworks
- Score: Higher if objections were fully resolved, lower if objections remained unaddressed

**D. Closing Attempts (count):**
- Count explicit attempts to move conversation forward: "Would you like to schedule a demo?", "Should I send you a proposal?", "Can we set up a trial?"
- Count soft closes: "Does that sound good?", "Are you interested?", "What do you think?"
- Note: Multiple closing attempts are GOOD if done naturally (not pushy)

**E. Value Proposition Delivery (0-100):**
- Assess if rep clearly communicated: unique value, benefits over competitors, ROI/payback
- Evaluate: Clarity of message, relevance to customer needs, evidence/examples provided
- Score: Higher if value was personalized to customer's situation, lower if generic pitch

### 4. CUSTOMER ENGAGEMENT & BEHAVIOR

**A. Engagement Score (0-100):**
Measure customer's active participation:
- Asking questions: High engagement indicator
- Sharing detailed information: Shows interest and trust
- Bringing up related concerns: Indicates serious consideration
- Minimal responses ("yes", "ok", "sure"): Low engagement
- Score based on: question quality, information sharing depth, participation level

**B. Interest Indicators (list specific examples from transcript):**
- Direct interest: "That sounds interesting", "Tell me more", "How does that work?"
- Buying signals: "What's the price?", "When can we start?", "What's the next step?"
- Comparison shopping: "How does this compare to X?", "What makes you different?"
- Budget mentions: "We have budget for this", "This fits our range"
- Timeline mentions: "We need this by Q2", "We're planning for next month"
- Authority signals: "I need to discuss with my team", "Let me check with my manager"
- Research behavior: "I've been looking at solutions", "We evaluated X and Y"

**C. Concern Indicators (list specific examples from transcript):**
- Skepticism: "I'm not sure", "That seems expensive", "We tried something similar"
- Objections: "We don't have budget", "The timeline is too tight", "We're happy with current solution"
- Risk concerns: "What if it doesn't work?", "How do we know this will solve our problem?"
- Competition mentions: "We're using X currently", "We're evaluating Y"
- Vague commitments: "Maybe", "We'll think about it", "I'll get back to you"

**D. Commitment Level (High/Medium/Low):**
- High: Clear next steps agreed, timeline mentioned, decision-maker engaged, budget confirmed
- Medium: Interest shown but no commitment, considering options, needs more information
- Low: Polite but uncommitted, avoiding next steps, no timeline/budget discussion

### 5. BANT QUALIFICATION (Detailed Scoring)

Analyze each dimension with specific evidence from transcript:

**Budget (0-100):**
- 90-100: Explicitly mentioned budget range, confirmed availability
- 70-89: Indirect budget mentions ("we have budget", "price is important")
- 50-69: Budget concerns raised but not resolved
- 30-49: Budget mentioned as potential barrier ("expensive", "costly")
- 0-29: No budget discussion or negative signals

**Authority (0-100):**
- 90-100: Clear decision maker, making decisions independently
- 70-89: Decision maker but needs to consult/approve
- 50-69: Influencer who can recommend
- 30-49: Involved in process but not final authority
- 0-29: No authority, just gathering information

**Need (0-100):**
- 90-100: Explicit pain points identified, urgent problem stated
- 70-89: Problems mentioned, moderate urgency
- 50-69: Some problems but not urgent
- 30-49: Vague problems, unclear need
- 0-29: No clear need identified, content with status quo

**Timeline (0-100):**
- 90-100: Specific timeline mentioned ("need by Q2", "starting next month")
- 70-89: General timeline ("soon", "this year", "in a few months")
- 50-69: Timeline mentioned but flexible
- 30-49: No urgency, "maybe in the future"
- 0-29: No timeline discussed or far future

### 6. CONVERSATION FLOW & DYNAMICS

**A. Conversation Pace (Fast/Moderate/Slow):**
- Fast: Rapid exchange, multiple topics, quick transitions
- Moderate: Steady flow, balanced discussion
- Slow: Long pauses, slow responses, drawn out topics

**B. Interruption Count:**
- Count instances where customer or rep interrupted the other
- Note: Some interruptions are positive (showing engagement), others negative (showing impatience)
- Provide context: Were interruptions collaborative or disruptive?

**C. Silence Periods:**
- Count awkward pauses or extended silences (>3 seconds)
- Note: Some silence is good (thinking, processing), excessive silence may indicate disengagement

### 7. TRUST BUILDING MOMENTS

Identify specific instances where trust was built:
- Empathy: "I understand your situation", "That must be challenging"
- Credibility: Sharing relevant case studies, testimonials, expertise
- Transparency: Honest about limitations, pricing, timelines
- Personal connection: Finding common ground, rapport building
- Consistency: Following through on promises, being reliable

### 8. PREDICTIVE ANALYTICS

**A. Deal Probability (0-100):**
Calculate based on weighted factors:
- BANT scores (weighted: Need 30%, Budget 25%, Authority 20%, Timeline 25%)
- Engagement score (20% weight)
- Interest indicators vs concern indicators (30% weight)
- Commitment level (30% weight)
- Provide calculated score with reasoning

**B. Follow-up Urgency (High/Medium/Low):**
- High: Deal is hot, customer ready to move, competitive situation, time-sensitive
- Medium: Good opportunity, needs nurturing, some objections to address
- Low: Early stage, no urgency, long sales cycle expected

### 9. UPSELL/EXPANSION OPPORTUNITIES

Identify potential for:
- Additional products/services mentioned in conversation
- Upgrades to higher tiers
- Add-on features relevant to customer
- Complementary solutions
- Specific examples from transcript

### 10. KEY TOPICS DISCUSSED

Extract main topics (3-5):
- Product features discussed
- Business challenges addressed
- Competitive comparisons
- Pricing/budget topics
- Implementation/timeline topics

### 11. IMPROVEMENT AREAS FOR SALES REP

Provide specific, actionable feedback:
- What should the rep do differently next time?
- Which skills need development?
- What opportunities were missed?
- Be specific with examples from transcript

### 12. ACTION ITEMS

Clear next steps identified:
- What should happen immediately after this call?
- What information needs to be shared?
- What follow-up is required?
- Who needs to be involved?

---

## OUTPUT REQUIREMENTS:

Return ONLY valid JSON (no markdown, no code blocks, no explanations) with this EXACT structure:

{{
    "summary": "Comprehensive 3-4 sentence summary covering: call outcome, key highlights, customer status, and recommended next action",
    "sentiment": "positive/negative/neutral - MUST accurately reflect transcript sentiment based on customer tone, engagement, and language",
    "key_topics": ["topic 1", "topic 2", "topic 3", "topic 4"],
    "satisfaction_score": <0-100 integer - customer satisfaction based on their expressed satisfaction, engagement, and positive language>,
    "improvement_areas": ["specific actionable improvement 1 with brief context", "specific actionable improvement 2 with brief context", "specific actionable improvement 3"],
    "action_items": ["specific immediate next step 1", "specific immediate next step 2", "specific immediate next step 3"],
    "overall_score": <0-100 integer - comprehensive call quality score based on ALL analysis dimensions>,
    "talk_time_ratio": <0.0-1.0 float - rep talk time / total call time, calculate based on transcript>,
    "question_effectiveness": <0-100 integer - quality and strategic value of questions asked>,
    "objection_handling": <0-100 integer - how well rep handled objections, if any>,
    "closing_attempts": <integer count - number of closing attempts made>,
    "engagement_score": <0-100 integer - customer engagement and participation level>,
    "commitment_level": "High/Medium/Low - customer commitment to move forward",
    "conversation_pace": "Fast/Moderate/Slow - pace of conversation",
    "interruption_count": <integer - number of interruptions>,
    "silence_periods": <integer - count of awkward silences>,
    "bant_qualification": {{
        "budget": <0-100 integer - detailed BANT budget score>,
        "authority": <0-100 integer - detailed BANT authority score>,
        "need": <0-100 integer - detailed BANT need score>,
        "timeline": <0-100 integer - detailed BANT timeline score>
    }},
    "value_proposition_score": <0-100 integer - how well rep communicated value>,
    "trust_building_moments": ["specific trust moment 1 from transcript", "specific trust moment 2", "specific trust moment 3"],
    "interest_indicators": ["specific interest indicator 1 from transcript", "specific interest indicator 2", "specific interest indicator 3"],
    "concern_indicators": ["specific concern 1 from transcript if any", "specific concern 2 if any"],
    "deal_probability": <0-100 integer - calculated probability of closing deal>,
    "follow_up_urgency": "High/Medium/Low - urgency of follow-up needed",
    "upsell_opportunities": ["specific upsell opportunity 1", "specific upsell opportunity 2 if any"]
}}

## CRITICAL INSTRUCTIONS:

1. **ACCURACY FIRST**: Base ALL scores and assessments ONLY on what is actually in the transcript. Do not assume or infer beyond what's stated.

2. **SCORING RIGOR**: Use the detailed criteria above for each score. Be consistent and fair. Avoid middle-ground scores (50s) unless truly appropriate.

3. **SENTIMENT PRECISION**: Sentiment must reflect actual customer tone and language, not rep performance. A call can have positive sentiment even if rep performance was poor (customer was happy despite poor selling).

4. **SPECIFICITY**: All lists (improvement_areas, action_items, interest_indicators, etc.) must contain SPECIFIC examples or observations from the transcript, not generic statements.

5. **COMPREHENSIVE ANALYSIS**: Consider ALL aspects before determining scores. Don't rush - this analysis drives business decisions.

6. **JSON VALIDITY**: Ensure all JSON is properly formatted, all required fields are present, all numbers are integers/floats (not strings), all arrays contain strings.

Return ONLY the JSON object, nothing else."""
            
            # Use JSON mode if model supports it (gpt-4o, gpt-4-turbo, etc.)
            kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are an expert sales call analyst. Always respond with valid JSON only, no markdown, no code blocks, no explanations."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 4000,
                "temperature": 0.2
            }
            
            # Add JSON mode for supported models
            if "gpt-4" in self.model.lower() or "gpt-3.5-turbo" in self.model.lower():
                try:
                    kwargs["response_format"] = {"type": "json_object"}
                except TypeError:
                    # Older API version doesn't support response_format
                    pass
            
            response = self.openai_client.chat.completions.create(**kwargs)
            
            if response.choices and response.choices[0].message.content:
                import json
                import re
                content = response.choices[0].message.content.strip()
                
                # Remove markdown code blocks if present
                if content.startswith('```json'):
                    content = re.sub(r'^```json\s*', '', content, flags=re.MULTILINE)
                    content = re.sub(r'\s*```\s*$', '', content, flags=re.MULTILINE)
                elif content.startswith('```'):
                    content = re.sub(r'^```\s*', '', content, flags=re.MULTILINE)
                    content = re.sub(r'\s*```\s*$', '', content, flags=re.MULTILINE)
                
                # Extract JSON object if wrapped in text
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
                
                logger.info(f"Parsing GPT response JSON (length: {len(content)})")
                try:
                    insights_data = json.loads(content)
                except json.JSONDecodeError as json_err:
                    logger.error(f"Failed to parse GPT JSON response: {json_err}")
                    logger.error(f"Response content: {content[:500]}")
                    raise Exception(f"Invalid JSON from GPT: {json_err}")
                
                logger.info(f"Successfully parsed GPT insights: {len(insights_data)} fields")
                
                # Create InsightsCreate object with proper call_id
                insights = InsightsCreate(
                    call_id=0,  # Will be set by caller - this is correct for the create model
                    summary=insights_data.get('summary', 'Call analysis completed'),
                    sentiment=SentimentType(insights_data.get('sentiment', 'neutral')),
                    key_topics=insights_data.get('key_topics', ['General Discussion']),
                    satisfaction_score=max(10, min(95, insights_data.get('satisfaction_score', 50))),
                    improvement_areas=insights_data.get('improvement_areas', ['Follow-up Communication']),
                    action_items=insights_data.get('action_items', ['Schedule follow-up call']),
                    overall_score=max(10, min(95, insights_data.get('overall_score', 50))),
                    talk_time_ratio=max(0.1, min(0.9, insights_data.get('talk_time_ratio', 0.6))),
                    question_effectiveness=max(30, min(90, insights_data.get('question_effectiveness', 50))),
                    engagement_score=max(30, min(95, insights_data.get('engagement_score', 60))),
                    commitment_level=insights_data.get('commitment_level', 'Medium'),
                    conversation_pace=insights_data.get('conversation_pace', 'Moderate'),
                    bant_qualification=insights_data.get('bant_qualification', {"budget": 50, "authority": 50, "need": 50, "timeline": 50}),
                    value_proposition_score=max(30, min(90, insights_data.get('value_proposition_score', 50))),
                    trust_building_moments=insights_data.get('trust_building_moments', []),
                    interest_indicators=insights_data.get('interest_indicators', []),
                    concern_indicators=insights_data.get('concern_indicators', []),
                    deal_probability=max(10, min(95, insights_data.get('deal_probability', 50))),
                    follow_up_urgency=insights_data.get('follow_up_urgency', 'Medium'),
                    upsell_opportunities=insights_data.get('upsell_opportunities', [])
                )
                
                logger.info("GPT insights generated successfully")
                return insights
            else:
                logger.warning("GPT response was empty")
                return None
                
        except Exception as e:
            logger.error(f"GPT insights generation failed: {e}")
            return None
    
    def _generate_enhanced_fallback_insights(self, transcript_text: str) -> InsightsCreate:
        """
        Generate enhanced fallback insights based on transcript content - GUARANTEED TO WORK
        """
        logger.info("=== GENERATING ENHANCED FALLBACK INSIGHTS ===")
        
        # Analyze transcript content for comprehensive insights
        text_lower = transcript_text.lower()
        logger.info(f"Analyzing transcript content: {len(text_lower)} characters")
        
        # Analyze speaker distribution in transcript
        speaker_analysis = self._analyze_speakers_in_transcript(transcript_text)
        
        # Enhanced sentiment analysis with more indicators
        positive_indicators = [
            'yes', 'great', 'excellent', 'perfect', 'interested', 'sounds good', 'definitely', 'sure',
            'love', 'amazing', 'fantastic', 'wonderful', 'impressed', 'excited', 'looking forward',
            'definitely interested', 'sounds perfect', 'exactly what we need', 'this is great',
            'absolutely', 'sounds amazing', 'very interested', 'excited about', 'perfect for us',
            'exactly what we\'re looking for', 'this looks great', 'impressive', 'wonderful'
        ]
        negative_indicators = [
            'no', 'not interested', 'expensive', 'too much', 'busy', 'not now', 'maybe later',
            'not sure', 'don\'t think', 'not right', 'too expensive', 'not for us', 'not ready',
            'not a good fit', 'not what we need', 'too complicated', 'not interested',
            'can\'t afford', 'budget constraints', 'not the right time', 'not suitable',
            'doesn\'t work for us', 'not what we\'re looking for'
        ]
        neutral_indicators = [
            'maybe', 'possibly', 'let me think', 'not sure', 'need to discuss', 'have to check',
            'might be', 'could be', 'depends', 'we\'ll see', 'let me get back', 'need more info',
            'have to consider', 'will think about it', 'need to review'
        ]
        
        # Count indicators with weighted scoring
        positive_count = sum(2 if phrase in text_lower else 0 for phrase in positive_indicators)
        negative_count = sum(2 if phrase in text_lower else 0 for phrase in negative_indicators)
        neutral_count = sum(1 if phrase in text_lower else 0 for phrase in neutral_indicators)
        
        # Determine sentiment with enhanced scoring
        if positive_count > negative_count and positive_count > 0:
            sentiment = SentimentType.POSITIVE
            satisfaction_score = min(90, 65 + (positive_count * 4))
            overall_score = min(85, 60 + (positive_count * 3))
        elif negative_count > positive_count and negative_count > 0:
            sentiment = SentimentType.NEGATIVE
            satisfaction_score = max(20, 45 - (negative_count * 6))
            overall_score = max(25, 40 - (negative_count * 4))
        else:
            sentiment = SentimentType.NEUTRAL
            satisfaction_score = 55 + (positive_count * 2) - (negative_count * 2)
            overall_score = 50 + (positive_count * 1) - (negative_count * 1)
        
        # Enhanced topic extraction with more categories
        key_topics = []
        topic_keywords = {
            'Pricing & Budget': ['price', 'cost', 'budget', 'expensive', 'afford', 'pricing', 'quote', 'fee', 'investment', 'value'],
            'Demo & Trial': ['demo', 'trial', 'test', 'try', 'sample', 'preview', 'show', 'demonstration'],
            'Timeline & Urgency': ['timeline', 'when', 'schedule', 'deadline', 'timeframe', 'start', 'launch', 'urgent', 'asap'],
            'Features & Functionality': ['feature', 'capability', 'function', 'tool', 'option', 'setting', 'functionality'],
            'Implementation & Setup': ['implement', 'setup', 'install', 'deploy', 'onboard', 'training', 'configuration'],
            'Support & Service': ['support', 'help', 'assistance', 'service', 'maintenance', 'customer service'],
            'Integration & Compatibility': ['integrate', 'connect', 'api', 'system', 'platform', 'compatible'],
            'Security & Compliance': ['security', 'secure', 'safe', 'protect', 'privacy', 'compliance', 'gdpr'],
            'Competition & Comparison': ['competitor', 'alternative', 'compare', 'better than', 'vs', 'versus'],
            'ROI & Business Impact': ['roi', 'return', 'benefit', 'impact', 'improve', 'efficiency', 'productivity']
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                key_topics.append(topic)
        
        if not key_topics:
            key_topics.append('General Discussion')
        
        # Generate intelligent summary based on content analysis
        if len(transcript_text) < 100:
            summary = "Short call with limited content available for detailed analysis. Basic insights generated based on available information."
        else:
            # Extract meaningful parts for summary
            sentences = transcript_text.split('.')
            if len(sentences) > 4:
                # Take key sentences for summary
                start_sentences = sentences[:3]
                middle_sentences = sentences[len(sentences)//2:len(sentences)//2+2] if len(sentences) > 8 else []
                end_sentences = sentences[-2:] if len(sentences) > 6 else sentences[-1:]
                
                summary_parts = start_sentences + middle_sentences + end_sentences
                summary = f"Call discussion covered {', '.join(key_topics[:3])}. Key highlights: {' '.join(summary_parts[:5])}..."
            else:
                summary = f"Call discussion covered {', '.join(key_topics[:3])}. {transcript_text[:400]}..."
        
        # Enhanced conversation analysis
        sentences = transcript_text.split('.')
        question_marks = transcript_text.count('?')
        exclamation_marks = transcript_text.count('!')
        
        # Calculate talk time ratio using speaker analysis
        talk_time_ratio = speaker_analysis.get('talk_time_ratio', 0.6)  # Use speaker analysis or default
        if talk_time_ratio == 0.6:  # Fallback calculation if no speaker data
            if question_marks > len(sentences) * 0.4:  # High question ratio
                talk_time_ratio = 0.75
            elif question_marks < len(sentences) * 0.1:  # Low question ratio
                talk_time_ratio = 0.45
            else:
                talk_time_ratio = 0.6
        
        # Enhanced engagement scoring
        base_engagement = min(90, max(40, len(transcript_text) // 12))
        if question_marks > 0:
            base_engagement += min(25, question_marks * 3)
        if exclamation_marks > 0:
            base_engagement += min(15, exclamation_marks * 2)
        if positive_count > 0:
            base_engagement += min(20, positive_count * 2)
        
        engagement_score = min(95, base_engagement)
        
        # Enhanced BANT qualification analysis
        bant_scores = {
            "budget": 30,  # Default low
            "authority": 30,  # Default low
            "need": 50,  # Default medium
            "timeline": 30  # Default low
        }
        
        # Budget indicators with more keywords
        budget_keywords = ['budget', 'price', 'cost', 'expensive', 'afford', 'pricing', 'investment', 'value', 'money', 'financial']
        if any(word in text_lower for word in budget_keywords):
            bant_scores["budget"] = 65
            if any(word in text_lower for word in ['budget approved', 'have budget', 'allocated', 'funding']):
                bant_scores["budget"] = 85
        
        # Authority indicators
        authority_keywords = ['decision', 'approve', 'manager', 'director', 'ceo', 'boss', 'team', 'responsible', 'authority', 'sign off']
        if any(word in text_lower for word in authority_keywords):
            bant_scores["authority"] = 65
            if any(word in text_lower for word in ['i decide', 'i approve', 'my decision', 'final say']):
                bant_scores["authority"] = 85
        
        # Need indicators
        need_keywords = ['problem', 'challenge', 'issue', 'need', 'want', 'looking for', 'requirement', 'pain', 'struggle', 'difficult']
        if any(word in text_lower for word in need_keywords):
            bant_scores["need"] = 75
            if any(word in text_lower for word in ['urgent', 'critical', 'must have', 'essential', 'desperate']):
                bant_scores["need"] = 90
        
        # Timeline indicators
        timeline_keywords = ['when', 'timeline', 'deadline', 'urgent', 'soon', 'quickly', 'asap', 'immediate', 'timeframe', 'schedule']
        if any(word in text_lower for word in timeline_keywords):
            bant_scores["timeline"] = 65
            if any(word in text_lower for word in ['asap', 'immediate', 'urgent', 'this month', 'next week']):
                bant_scores["timeline"] = 85
        
        # Enhanced improvement areas based on content and speaker analysis
        improvement_areas = []
        if 'price' in text_lower and ('expensive' in text_lower or 'too much' in text_lower):
            improvement_areas.append('Value Proposition Communication')
        if question_marks < 3:  # Low number of questions
            improvement_areas.append('Discovery Questions')
        if len(transcript_text) < 500:  # Short call
            improvement_areas.append('Call Duration and Depth')
        if negative_count > positive_count:
            improvement_areas.append('Objection Handling')
        if bant_scores["budget"] < 50:
            improvement_areas.append('Budget Qualification')
        if bant_scores["authority"] < 50:
            improvement_areas.append('Decision Maker Identification')
        
        # Speaker-specific improvement areas
        if speaker_analysis.get('total_speakers', 0) > 0:
            if speaker_analysis.get('speaker_turns', 0) < 5:
                improvement_areas.append('Encourage more conversation flow')
            if speaker_analysis.get('most_active_speaker') == 'Speaker 1' and talk_time_ratio > 0.7:
                improvement_areas.append('Balance conversation - allow more customer input')
            if speaker_analysis.get('total_speakers') < 2:
                improvement_areas.append('Improve speaker identification and separation')
        
        if not improvement_areas:
            improvement_areas.append('Follow-up Communication')
        
        # Enhanced action items based on content
        action_items = []
        if 'demo' in text_lower or 'trial' in text_lower:
            action_items.append('Schedule product demonstration')
        if 'price' in text_lower or 'cost' in text_lower:
            action_items.append('Send pricing information')
        if 'timeline' in text_lower or 'when' in text_lower:
            action_items.append('Follow up on timeline discussion')
        if bant_scores["authority"] < 50:
            action_items.append('Identify decision maker')
        if bant_scores["budget"] < 50:
            action_items.append('Qualify budget requirements')
        if not action_items:
            action_items.append('Schedule follow-up call')
        
        # Enhanced deal probability calculation
        deal_probability = 25  # Base low probability
        if sentiment == SentimentType.POSITIVE:
            deal_probability += 30
        if any(word in text_lower for word in ['next step', 'follow up', 'schedule', 'meeting', 'demo', 'trial']):
            deal_probability += 25
        if bant_scores["need"] > 60:
            deal_probability += 20
        if bant_scores["authority"] > 50:
            deal_probability += 15
        if bant_scores["budget"] > 50:
            deal_probability += 10
        
        deal_probability = min(95, deal_probability)
        
        # Enhanced trust building and interest indicators
        trust_building_moments = []
        if len(transcript_text) > 300:
            trust_building_moments.append('Initial rapport building')
        if 'understand' in text_lower or 'see' in text_lower:
            trust_building_moments.append('Active listening demonstrated')
        if 'experience' in text_lower or 'similar' in text_lower:
            trust_building_moments.append('Shared relevant experience')
        
        interest_indicators = []
        if sentiment == SentimentType.POSITIVE:
            interest_indicators.append('Positive engagement throughout call')
        if question_marks > 5:
            interest_indicators.append('High level of questions asked')
        if 'demo' in text_lower or 'trial' in text_lower:
            interest_indicators.append('Requested product demonstration')
        if 'timeline' in text_lower or 'when' in text_lower:
            interest_indicators.append('Discussed implementation timeline')
        
        concern_indicators = []
        if 'price' in text_lower and 'expensive' in text_lower:
            concern_indicators.append('Price sensitivity expressed')
        if negative_count > 0:
            concern_indicators.append('Some reservations expressed')
        if bant_scores["budget"] < 40:
            concern_indicators.append('Budget constraints mentioned')
        
        upsell_opportunities = []
        if 'basic' in text_lower or 'standard' in text_lower:
            upsell_opportunities.append('Premium features discussion')
        if 'support' in text_lower:
            upsell_opportunities.append('Enhanced support options')
        if 'integration' in text_lower:
            upsell_opportunities.append('Additional integration services')
        
        # Create comprehensive insights with guaranteed values
        insights = InsightsCreate(
            call_id=0,  # Will be set by the caller - this is correct for the create model
            sentiment=sentiment,
            key_topics=key_topics,
            satisfaction_score=max(15, min(95, satisfaction_score)),
            improvement_areas=improvement_areas,
            action_items=action_items,
            summary=summary[:600],  # Limit summary length
            overall_score=max(15, min(95, overall_score)),
            
            # Advanced fields with intelligent analysis
            talk_time_ratio=talk_time_ratio,
            question_effectiveness=max(35, min(90, 50 + (question_marks * 4))),
            engagement_score=engagement_score,
            commitment_level="High" if deal_probability > 75 else "Medium" if deal_probability > 45 else "Low",
            conversation_pace="Fast" if len(sentences) > 25 else "Slow" if len(sentences) < 8 else "Moderate",
            interruption_count=0,  # Cannot determine from text
            silence_periods=0,  # Cannot determine from text
            bant_qualification=bant_scores,
            value_proposition_score=max(35, min(90, 55 + (positive_count * 4) - (negative_count * 2))),
            trust_building_moments=trust_building_moments,
            interest_indicators=interest_indicators,
            concern_indicators=concern_indicators,
            deal_probability=deal_probability,
            follow_up_urgency="High" if deal_probability > 75 else "Medium" if deal_probability > 45 else "Low",
            upsell_opportunities=upsell_opportunities
        )
        
        logger.info("=== ENHANCED FALLBACK INSIGHTS CREATED SUCCESSFULLY ===")
        logger.info(f"Sentiment: {insights.sentiment}")
        logger.info(f"Overall Score: {insights.overall_score}")
        logger.info(f"Key Topics: {insights.key_topics}")
        logger.info(f"Summary: {insights.summary[:100]}...")
        logger.info(f"Deal Probability: {insights.deal_probability}")
        logger.info(f"BANT Scores: {insights.bant_qualification}")
        
        return insights
    
    def _create_emergency_insights(self, call_id: int, filename: str, transcript_text: str) -> InsightsCreate:
        """
        Create emergency fallback insights - GUARANTEED TO WORK NO MATTER WHAT
        """
        logger.info(f"=== CREATING EMERGENCY INSIGHTS FOR CALL {call_id} ===")
        
        # Basic analysis of transcript
        text_lower = transcript_text.lower() if transcript_text else ""
        transcript_length = len(transcript_text) if transcript_text else 0
        
        # Determine basic sentiment
        if any(word in text_lower for word in ['yes', 'good', 'great', 'interested', 'sounds good']):
            sentiment = SentimentType.POSITIVE
            base_score = 65
        elif any(word in text_lower for word in ['no', 'not interested', 'expensive', 'busy']):
            sentiment = SentimentType.NEGATIVE
            base_score = 35
        else:
            sentiment = SentimentType.NEUTRAL
            base_score = 50
        
        # Generate basic summary
        if transcript_length < 100:
            summary = f"Call analysis completed for {filename}. Limited transcript available for detailed analysis."
        else:
            summary = f"Call analysis completed for {filename}. Transcript contains {transcript_length} characters of conversation data."
        
        # Basic topics
        key_topics = ["General Discussion"]
        if 'price' in text_lower or 'cost' in text_lower:
            key_topics.append("Pricing")
        if 'demo' in text_lower or 'trial' in text_lower:
            key_topics.append("Demo/Trial")
        if 'timeline' in text_lower or 'when' in text_lower:
            key_topics.append("Timeline")
        
        # Basic improvement areas
        improvement_areas = ["Follow-up Communication"]
        if transcript_length < 500:
            improvement_areas.append("Call Duration")
        if transcript_text.count('?') < 3:
            improvement_areas.append("Discovery Questions")
        
        # Basic action items
        action_items = ["Schedule follow-up call"]
        if 'demo' in text_lower:
            action_items.append("Schedule product demonstration")
        if 'price' in text_lower:
            action_items.append("Send pricing information")
        
        # Create emergency insights
        emergency_insights = InsightsCreate(
            call_id=call_id,  # Use the actual call_id for emergency insights
            summary=summary,
            sentiment=sentiment,
            key_topics=key_topics,
            satisfaction_score=max(20, min(90, base_score)),
            improvement_areas=improvement_areas,
            action_items=action_items,
            overall_score=max(20, min(90, base_score)),
            
            # Set reasonable defaults for all advanced fields
            talk_time_ratio=0.6,
            question_effectiveness=50,
            engagement_score=60,
            commitment_level="Medium",
            conversation_pace="Moderate",
            interruption_count=0,
            silence_periods=0,
            bant_qualification={"budget": 50, "authority": 50, "need": 50, "timeline": 50},
            value_proposition_score=50,
            trust_building_moments=["Initial conversation"],
            interest_indicators=["Engaged in discussion"] if sentiment == SentimentType.POSITIVE else [],
            concern_indicators=["General concerns"] if sentiment == SentimentType.NEGATIVE else [],
            deal_probability=max(20, min(80, base_score + 10)),
            follow_up_urgency="Medium",
            upsell_opportunities=[]
        )
        
        logger.info(f"=== EMERGENCY INSIGHTS CREATED FOR CALL {call_id} ===")
        logger.info(f"Sentiment: {emergency_insights.sentiment}")
        logger.info(f"Overall Score: {emergency_insights.overall_score}")
        logger.info(f"Summary: {emergency_insights.summary[:100]}...")
        
        return emergency_insights
    
    def _generate_fallback_insights(self, transcript_text: str) -> InsightsCreate:
        """
        Generate intelligent fallback insights based on transcript content - GUARANTEED TO WORK
        """
        logger.info("=== GENERATING FALLBACK INSIGHTS ===")
        
        # Analyze transcript content for basic insights
        text_lower = transcript_text.lower()
        logger.info(f"Analyzing transcript content: {len(text_lower)} characters")
        
        # Enhanced sentiment analysis based on actual content
        positive_indicators = [
            'yes', 'great', 'excellent', 'perfect', 'interested', 'sounds good', 'definitely', 'sure',
            'love', 'amazing', 'fantastic', 'wonderful', 'impressed', 'excited', 'looking forward',
            'definitely interested', 'sounds perfect', 'exactly what we need', 'this is great'
        ]
        negative_indicators = [
            'no', 'not interested', 'expensive', 'too much', 'busy', 'not now', 'maybe later',
            'not sure', 'don\'t think', 'not right', 'too expensive', 'not for us', 'not ready',
            'not a good fit', 'not what we need', 'too complicated', 'not interested'
        ]
        neutral_indicators = [
            'maybe', 'possibly', 'let me think', 'not sure', 'need to discuss', 'have to check',
            'might be', 'could be', 'depends', 'we\'ll see', 'let me get back'
        ]
        
        positive_count = sum(1 for phrase in positive_indicators if phrase in text_lower)
        negative_count = sum(1 for phrase in negative_indicators if phrase in text_lower)
        neutral_count = sum(1 for phrase in neutral_indicators if phrase in text_lower)
        
        # Determine sentiment with more nuanced scoring
        if positive_count > negative_count and positive_count > 0:
            sentiment = SentimentType.POSITIVE
            satisfaction_score = min(85, 60 + (positive_count * 5))
            overall_score = min(80, 55 + (positive_count * 4))
        elif negative_count > positive_count and negative_count > 0:
            sentiment = SentimentType.NEGATIVE
            satisfaction_score = max(25, 50 - (negative_count * 8))
            overall_score = max(30, 45 - (negative_count * 6))
        else:
            sentiment = SentimentType.NEUTRAL
            satisfaction_score = 55 + (positive_count * 3) - (negative_count * 3)
            overall_score = 50 + (positive_count * 2) - (negative_count * 2)
        
        # Extract key topics from transcript with more comprehensive analysis
        key_topics = []
        topic_keywords = {
            'Pricing': ['price', 'cost', 'budget', 'expensive', 'afford', 'pricing', 'quote', 'fee'],
            'Demo/Trial': ['demo', 'trial', 'test', 'try', 'sample', 'preview', 'show'],
            'Timeline': ['timeline', 'when', 'schedule', 'deadline', 'timeframe', 'start', 'launch'],
            'Features': ['feature', 'capability', 'function', 'tool', 'option', 'setting'],
            'Implementation': ['implement', 'setup', 'install', 'deploy', 'onboard', 'training'],
            'Support': ['support', 'help', 'assistance', 'service', 'maintenance'],
            'Integration': ['integrate', 'connect', 'api', 'system', 'platform'],
            'Security': ['security', 'secure', 'safe', 'protect', 'privacy', 'compliance']
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                key_topics.append(topic)
        
        if not key_topics:
            key_topics.append('General Discussion')
        
        # Generate more intelligent summary based on content
        if len(transcript_text) < 100:
            summary = "Short call with limited content available for detailed analysis."
        else:
            # Extract meaningful parts for summary
            sentences = transcript_text.split('.')
            if len(sentences) > 3:
                # Take first few sentences and last few sentences
                start_sentences = sentences[:2]
                end_sentences = sentences[-2:] if len(sentences) > 4 else sentences[-1:]
                summary = f"Call discussion covered {', '.join(key_topics)}. Key points: {' '.join(start_sentences)}... {' '.join(end_sentences)}"
            else:
                summary = f"Call discussion covered {', '.join(key_topics)}. {transcript_text[:300]}..."
        
        # Calculate talk time ratio based on transcript structure
        sentences = transcript_text.split('.')
        question_marks = transcript_text.count('?')
        exclamation_marks = transcript_text.count('!')
        
        # Estimate talk time ratio based on conversation patterns
        if question_marks > len(sentences) * 0.3:  # High question ratio suggests sales rep talking more
            talk_time_ratio = 0.7
        elif question_marks < len(sentences) * 0.1:  # Low question ratio suggests customer talking more
            talk_time_ratio = 0.4
        else:
            talk_time_ratio = 0.6  # Balanced
        
        # Determine engagement based on transcript length, questions, and content
        base_engagement = min(90, max(30, len(transcript_text) // 15))
        if question_marks > 0:
            base_engagement += min(20, question_marks * 2)  # Questions indicate engagement
        if exclamation_marks > 0:
            base_engagement += min(10, exclamation_marks)  # Exclamations indicate enthusiasm
        engagement_score = min(95, base_engagement)
        
        # Enhanced BANT qualification based on actual content
        bant_scores = {
            "budget": 30,  # Default low
            "authority": 30,  # Default low
            "need": 50,  # Default medium
            "timeline": 30  # Default low
        }
        
        # Budget indicators
        if any(word in text_lower for word in ['budget', 'price', 'cost', 'expensive', 'afford', 'pricing']):
            bant_scores["budget"] = 60
        
        # Authority indicators
        if any(word in text_lower for word in ['decision', 'approve', 'manager', 'director', 'ceo', 'boss', 'team']):
            bant_scores["authority"] = 60
        
        # Need indicators
        if any(word in text_lower for word in ['problem', 'challenge', 'issue', 'need', 'want', 'looking for', 'requirement']):
            bant_scores["need"] = 70
        
        # Timeline indicators
        if any(word in text_lower for word in ['when', 'timeline', 'deadline', 'urgent', 'soon', 'quickly', 'asap']):
            bant_scores["timeline"] = 60
        
        # Generate improvement areas based on actual content analysis
        improvement_areas = []
        if 'price' in text_lower and ('expensive' in text_lower or 'too much' in text_lower):
            improvement_areas.append('Value Proposition Communication')
        if question_marks < 3:  # Low number of questions
            improvement_areas.append('Discovery Questions')
        if len(transcript_text) < 500:  # Short call
            improvement_areas.append('Call Duration and Depth')
        if not improvement_areas:
            improvement_areas.append('Follow-up Communication')
        
        # Generate action items based on content
        action_items = []
        if 'demo' in text_lower or 'trial' in text_lower:
            action_items.append('Schedule product demonstration')
        if 'price' in text_lower or 'cost' in text_lower:
            action_items.append('Send pricing information')
        if 'timeline' in text_lower or 'when' in text_lower:
            action_items.append('Follow up on timeline discussion')
        if not action_items:
            action_items.append('Schedule follow-up call')
        
        # Calculate deal probability based on multiple factors
        deal_probability = 30  # Base low probability
        if sentiment == SentimentType.POSITIVE:
            deal_probability += 25
        if any(word in text_lower for word in ['next step', 'follow up', 'schedule', 'meeting']):
            deal_probability += 20
        if bant_scores["need"] > 60:
            deal_probability += 15
        if bant_scores["authority"] > 50:
            deal_probability += 10
        
        deal_probability = min(95, deal_probability)
        
        # Create insights with guaranteed values
        insights = InsightsCreate(
            call_id=0,  # Will be set by the caller
            sentiment=sentiment,
            key_topics=key_topics,
            satisfaction_score=max(10, min(95, satisfaction_score)),
            improvement_areas=improvement_areas,
            action_items=action_items,
            summary=summary[:500],  # Limit summary length
            overall_score=max(10, min(95, overall_score)),
            
            # Advanced fields with intelligent analysis
            talk_time_ratio=talk_time_ratio,
            question_effectiveness=max(30, min(90, 50 + (question_marks * 5))),
            engagement_score=engagement_score,
            commitment_level="High" if deal_probability > 70 else "Medium" if deal_probability > 40 else "Low",
            conversation_pace="Fast" if len(sentences) > 20 else "Slow" if len(sentences) < 10 else "Moderate",
            interruption_count=0,  # Cannot determine from text
            silence_periods=0,  # Cannot determine from text
            bant_qualification=bant_scores,
            value_proposition_score=max(30, min(90, 50 + (positive_count * 5) - (negative_count * 3))),
            trust_building_moments=["Initial rapport building"] if len(transcript_text) > 200 else [],
            interest_indicators=["Engaged in conversation"] if sentiment == SentimentType.POSITIVE else [],
            concern_indicators=["Price sensitivity"] if 'price' in text_lower and 'expensive' in text_lower else [],
            deal_probability=deal_probability,
            follow_up_urgency="High" if deal_probability > 70 else "Medium" if deal_probability > 40 else "Low",
            upsell_opportunities=[]
        )
        
        logger.info("=== FALLBACK INSIGHTS CREATED SUCCESSFULLY ===")
        logger.info(f"Sentiment: {insights.sentiment}")
        logger.info(f"Overall Score: {insights.overall_score}")
        logger.info(f"Key Topics: {insights.key_topics}")
        logger.info(f"Summary: {insights.summary[:100]}...")
        logger.info(f"Deal Probability: {insights.deal_probability}")
        
        return insights

# Global instance
processing_service = ProcessingService()

async def process_call_background(call_id: int):
    """
    Background task to process a call
    """
    logger.info(f"Starting background processing for call {call_id}")
    
    # Get database session
    db = next(get_db())
    if db is None:
        logger.error(f"Database not available for background processing of call {call_id}")
        return
    
    try:
        await processing_service.process_call(call_id, db)
    except Exception as e:
        logger.error(f"❌❌❌ ERROR processing call {call_id}: {e}")
        import traceback
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        # Don't re-raise - let the error be logged but don't crash the worker
        # The process_call method already marks calls as FAILED on error
    finally:
        db.close()
    
    logger.info(f"✅ Completed background processing for call {call_id}")
    
    # CRITICAL: FINAL DURATION CHECK - Ensure duration is ALWAYS extracted and saved
    # This is a safety net to catch any calls where duration extraction failed during processing
    # This also handles calls that were left in PROCESSING state due to missing duration
    logger.info(f"⏱️ === STARTING FINAL DURATION CHECK for call {call_id} ===")
    try:
        db_final = next(get_db())
        try:
            call_final_check = db_final.exec(select(Call).where(Call.id == call_id)).first()
            if call_final_check:
                logger.info(f"⏱️ Call {call_id} found in database. Status: {call_final_check.status}, Duration: {call_final_check.duration}")
                if not call_final_check.duration or call_final_check.duration <= 0:
                    logger.warning(f"⏱️ ⚠️⚠️⚠️ CRITICAL: Call {call_id} (status: {call_final_check.status}) has missing duration!")
                    logger.warning(f"⏱️ Attempting to extract duration NOW as final safety check...")
                    logger.info(f"⏱️ Call details - client_id: {call_final_check.client_id}, s3_url: {call_final_check.s3_url}")
                    
                    # Extract duration directly from S3
                    try:
                        from ..utils.file_utils import AudioProcessor
                        import boto3
                        import tempfile
                        from urllib.parse import urlparse
                        from ..models import Client
                        
                        if call_final_check.client_id:
                            logger.info(f"⏱️ Fetching client {call_final_check.client_id} credentials...")
                            client = db_final.exec(select(Client).where(Client.id == call_final_check.client_id)).first()
                            if client:
                                logger.info(f"⏱️ Client found: {client.name}, has AWS key: {bool(client.aws_access_key)}")
                                if client.aws_access_key:
                                    # Download from S3 - handle both full URLs and S3 keys
                                    if call_final_check.s3_url.startswith('http://') or call_final_check.s3_url.startswith('https://'):
                                        parsed = urlparse(call_final_check.s3_url)
                                        s3_key = parsed.path.lstrip('/')
                                        # If path starts with bucket name, remove it
                                        if s3_key.startswith(client.s3_bucket_name + '/'):
                                            s3_key = s3_key[len(client.s3_bucket_name) + 1:]
                                        # Handle calls/ prefix
                                        if not s3_key.startswith('calls/'):
                                            if call_final_check.filename not in s3_key:
                                                s3_key = f"calls/{call_final_check.filename}" if not s3_key else s3_key
                                    else:
                                        s3_key = call_final_check.s3_url
                                    
                                    logger.info(f"⏱️ Downloading from S3 - bucket: {client.s3_bucket_name}, key: {s3_key}")
                                    logger.info(f"⏱️ Original S3 URL: {call_final_check.s3_url}")
                                    
                                    s3_client = boto3.client(
                                        's3',
                                        aws_access_key_id=client.aws_access_key,
                                        aws_secret_access_key=client.aws_secret_key,
                                        region_name=client.s3_region
                                    )
                                    
                                    # Try downloading with error handling
                                    audio_bytes = None
                                    try:
                                        response = s3_client.get_object(Bucket=client.s3_bucket_name, Key=s3_key)
                                        audio_bytes = response['Body'].read()
                                        logger.info(f"⏱️ Downloaded {len(audio_bytes)} bytes from S3")
                                    except Exception as s3_err:
                                        logger.error(f"⏱️ ❌ S3 download failed with key '{s3_key}': {s3_err}")
                                        # Try alternative keys
                                        alternative_keys = [
                                            f"calls/{call_final_check.filename}",
                                            call_final_check.filename,
                                        ]
                                        for alt_key in alternative_keys:
                                            try:
                                                logger.info(f"⏱️ 🔄 Trying alternative key: {alt_key}")
                                                response = s3_client.get_object(Bucket=client.s3_bucket_name, Key=alt_key)
                                                audio_bytes = response['Body'].read()
                                                logger.info(f"⏱️ ✅ Found with alternative key: {alt_key} ({len(audio_bytes)} bytes)")
                                                s3_key = alt_key
                                                break
                                            except Exception:
                                                continue
                                        
                                        if not audio_bytes:
                                            raise Exception(f"Could not download from S3. Tried: {s3_key}, {', '.join(alternative_keys)}")
                                    
                                    # Save to temp file
                                    file_extension = os.path.splitext(call_final_check.filename)[1] or '.mp3'
                                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                                        temp_file.write(audio_bytes)
                                        temp_file_path = temp_file.name
                                    
                                    logger.info(f"⏱️ Saved to temp file: {temp_file_path}")
                                    
                                    # Extract duration
                                    logger.info(f"⏱️ Extracting duration using AudioProcessor...")
                                    logger.info(f"⏱️ Temp file: {temp_file_path}, size: {os.path.getsize(temp_file_path) if os.path.exists(temp_file_path) else 'N/A'} bytes")
                                    
                                    try:
                                        final_duration = AudioProcessor.get_audio_duration(temp_file_path)
                                    except Exception as extract_err:
                                        logger.error(f"⏱️ ❌ AudioProcessor.get_audio_duration() raised exception: {extract_err}")
                                        import traceback
                                        logger.error(f"⏱️ Extraction traceback:\n{traceback.format_exc()}")
                                        final_duration = None
                                    
                                    if final_duration and final_duration > 0:
                                        logger.info(f"⏱️ ✅✅✅ FINAL SAFETY CHECK SUCCESS: Extracted {final_duration}s ({final_duration // 60}:{(final_duration % 60):02d})")
                                        
                                        # Save to database
                                        logger.info(f"⏱️ Saving duration to database...")
                                        call_final_check.duration = final_duration
                                        
                                        # If call is in PROCESSING state and has insights/score, mark as PROCESSED
                                        if call_final_check.status == CallStatus.PROCESSING:
                                            from ..models import Insights
                                            insights_check = db_final.exec(select(Insights).where(Insights.call_id == call_id)).first()
                                            if insights_check and call_final_check.score:
                                                logger.info(f"⏱️ ✅ Call {call_id} has insights and score - marking as PROCESSED now that duration is extracted")
                                                call_final_check.status = CallStatus.PROCESSED
                                        
                                        db_final.add(call_final_check)
                                        db_final.commit()
                                        db_final.refresh(call_final_check)
                                        
                                        if call_final_check.duration == final_duration:
                                            logger.info(f"⏱️ ✅✅✅ FINAL SAFETY CHECK: Duration saved successfully! Call {call_id} now has duration: {final_duration}s, status: {call_final_check.status}")
                                        else:
                                            logger.error(f"⏱️ ❌ FINAL SAFETY CHECK: Duration save verification failed! Expected {final_duration}, got {call_final_check.duration}")
                                    else:
                                        logger.error(f"⏱️ ❌ FINAL SAFETY CHECK: Duration extraction returned {final_duration} (invalid)")
                                    
                                    # Cleanup
                                    try:
                                        os.unlink(temp_file_path)
                                        logger.info(f"⏱️ Cleaned up temp file")
                                    except Exception as cleanup_error:
                                        logger.warning(f"⏱️ Could not delete temp file: {cleanup_error}")
                                else:
                                    logger.error(f"⏱️ ❌ FINAL SAFETY CHECK: Client {call_final_check.client_id} has no AWS access key!")
                            else:
                                logger.error(f"⏱️ ❌ FINAL SAFETY CHECK: Client {call_final_check.client_id} not found!")
                        else:
                            logger.error(f"⏱️ ❌ FINAL SAFETY CHECK: Call {call_id} has no client_id!")
                    except Exception as final_extract_error:
                        logger.error(f"⏱️ ❌ FINAL SAFETY CHECK: Duration extraction failed: {final_extract_error}")
                        import traceback
                        logger.error(f"⏱️ FINAL SAFETY CHECK traceback:\n{traceback.format_exc()}")
                else:
                    logger.info(f"⏱️ ✅ Call {call_id} already has duration: {call_final_check.duration}s ({call_final_check.duration // 60}:{(call_final_check.duration % 60):02d})")
            else:
                logger.error(f"⏱️ ❌ FINAL SAFETY CHECK: Call {call_id} not found in database!")
        finally:
            db_final.close()
            logger.info(f"⏱️ === FINAL DURATION CHECK COMPLETED for call {call_id} ===")
    except Exception as final_check_error:
        logger.error(f"⏱️ ❌ Error in final duration check: {final_check_error}")
        import traceback
        logger.error(f"⏱️ Final check error traceback:\n{traceback.format_exc()}")
    
    # Final validation - ensure insights exist using a fresh DB session
    try:
        db_check = next(get_db())
        if db_check:
            try:
                from ..models import Insights, Transcript
                
                # Verify transcript exists
                transcript_check = db_check.exec(
                    select(Transcript).where(Transcript.call_id == call_id)
                ).first()
                if not transcript_check:
                    logger.error(f"❌ VALIDATION FAILED: No transcript found for call {call_id}")
                else:
                    logger.info(f"✅ VALIDATION: Transcript exists for call {call_id} ({len(transcript_check.text)} chars)")
                
                # Verify insights exist
                insights_check = db_check.exec(
                    select(Insights).where(Insights.call_id == call_id)
                ).first()
                if not insights_check:
                    logger.error(f"❌ VALIDATION FAILED: No insights found for call {call_id}, attempting to create...")
                    await validate_insights_exist(call_id, db_check)
                else:
                    logger.info(f"✅ VALIDATION: Insights exist for call {call_id} (score: {insights_check.overall_score})")
                    
            except Exception as validation_error:
                logger.error(f"❌ Insights validation failed for call {call_id}: {validation_error}")
                import traceback
                logger.error(traceback.format_exc())
            finally:
                db_check.close()
    except Exception as db_error:
        logger.error(f"Failed to open database for validation: {db_error}")

# -------- Ordered Processing Queue (sequential per instance) --------
import asyncio
from typing import Optional
_queue: Optional[asyncio.Queue] = None
_worker_started: bool = False
_worker_task: Optional[asyncio.Task] = None

async def _processing_worker():
    """Background worker that processes calls sequentially from the queue."""
    global _queue
    logger.info("=" * 80)
    logger.info("=== PROCESSING QUEUE WORKER STARTED ===")
    logger.info("=" * 80)
    logger.info("✅ Worker is ready to process calls from the queue")
    
    if _queue is None:
        _queue = asyncio.Queue()
    
    while True:
        try:
            # Wait for a call to process (with timeout to allow periodic checks)
            try:
                call_id = await asyncio.wait_for(_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # No items in queue, continue waiting
                continue
            
            logger.info(f"=== PROCESSING QUEUE: Starting call {call_id} ===")
            try:
                await process_call_background(call_id)
                logger.info(f"=== PROCESSING QUEUE: Completed call {call_id} successfully ===")
            except Exception as e:
                # Log error but continue processing other calls
                logger.error(f"=== PROCESSING QUEUE: ERROR processing call {call_id}: {e} ===")
                import traceback
                logger.error(traceback.format_exc())
            finally:
                _queue.task_done()
        except asyncio.CancelledError:
            logger.info("=== PROCESSING QUEUE WORKER CANCELLED ===")
            raise
        except Exception as e:
            logger.error(f"=== PROCESSING QUEUE WORKER FATAL ERROR: {e} ===")
            import traceback
            logger.error(traceback.format_exc())
            # Wait a bit before continuing to avoid tight error loop
            await asyncio.sleep(5)

async def start_processing_worker():
    """Start the processing queue worker (called on app startup)."""
    global _queue, _worker_started, _worker_task
    
    if _worker_started:
        logger.info("Processing worker already started")
        return
    
    if _queue is None:
        _queue = asyncio.Queue()
    
    # Start the worker task
    _worker_task = asyncio.create_task(_processing_worker())
    _worker_started = True
    logger.info("=== PROCESSING QUEUE WORKER INITIALIZED ===")

async def enqueue_call_for_processing(call_id: int):
    """Enqueue a call for sequential processing in this backend instance."""
    global _queue, _worker_started
    
    if _queue is None:
        _queue = asyncio.Queue()
    
    await _queue.put(call_id)
    logger.info(f"=== ENQUEUED call {call_id} for processing (queue size: {_queue.qsize()}) ===")
    
    # Ensure worker is started (backup in case startup didn't work)
    if not _worker_started:
        logger.warning("Processing worker not started, starting now...")
        await start_processing_worker()

async def validate_insights_exist(call_id: int, db: Session):
    """
    Validate that insights exist for a call, create them if they don't
    CRITICAL: Only creates fallback insights if transcription was already attempted and failed.
    If call is still PROCESSING, returns None to wait for real transcription.
    """
    try:
        logger.info(f"Validating insights exist for call {call_id}")
        
        # Check if insights exist
        from ..models import Insights, Call, Transcript
        insights_statement = select(Insights).where(Insights.call_id == call_id)
        existing_insights = db.exec(insights_statement).first()
        
        if existing_insights:
            logger.info(f"Insights already exist for call {call_id}")
            return existing_insights
        
        # Get the call and transcript
        call_statement = select(Call).where(Call.id == call_id)
        call = db.exec(call_statement).first()
        
        if not call:
            logger.error(f"Call {call_id} not found during validation")
            return None
        
        # CRITICAL: If call is still PROCESSING, don't create fallback - wait for real transcription
        if call.status == CallStatus.PROCESSING:
            logger.info(f"Call {call_id} is still PROCESSING - skipping fallback creation, waiting for real transcription")
            return None
        
        transcript_statement = select(Transcript).where(Transcript.call_id == call_id)
        transcript = db.exec(transcript_statement).first()
        
        # If no transcript AND call is already FAILED or PROCESSED, it means transcription failed
        # Only then should we create fallback
        if not transcript:
            if call.status == CallStatus.FAILED:
                logger.warning(f"No transcript found for FAILED call {call_id}, creating emergency fallback transcript...")
                # Create a fallback transcript for failed calls only
                fallback_text = f"Audio file uploaded: {call.filename}. Transcription failed - please check audio file and retry."
                transcript = Transcript(
                    call_id=call_id,
                    client_id=call.client_id,  # CRITICAL: Set client_id
                    text=fallback_text,
                    language=call.language  # Can be None for auto-detect
                )
                db.add(transcript)
                db.commit()
                db.refresh(transcript)
                logger.info(f"Created emergency fallback transcript for FAILED call {call_id}")
            else:
                # Call is PROCESSED but has no transcript - this shouldn't happen, but if it does, don't create fallback
                logger.error(f"CRITICAL: Call {call_id} is PROCESSED but has no transcript - transcription may have failed silently")
                logger.error(f"This should not happen - real transcription should have created a transcript")
                return None
        
        transcript_text = transcript.text if transcript else f"Audio file uploaded: {call.filename}"
        
        # CRITICAL CHECK: If transcript is the fallback "Transcription in progress" text, don't create insights
        # This means transcription never completed
        if "Transcription in progress" in transcript_text or "Transcription failed" in transcript_text:
            logger.error(f"CRITICAL: Call {call_id} has fallback transcript only - real transcription never completed!")
            logger.error(f"Transcript text: {transcript_text[:200]}")
            logger.error(f"This indicates transcription failed - insights would be based on fake data")
            # Mark call as FAILED instead of creating fake insights
            call.status = CallStatus.FAILED
            db.commit()
            return None
        
        # Create emergency insights
        logger.info(f"Creating missing insights for call {call_id} using transcript (length: {len(transcript_text)})")
        processing_service = ProcessingService()
        emergency_insights = processing_service._create_emergency_insights(call_id, call.filename, transcript_text)
        logger.info(f"Generated emergency insights for call {call_id} (score: {emergency_insights.overall_score})")
        
        # Save the insights
        insights_dict = emergency_insights.dict()
        
        # Convert lists to JSON strings
        for field in ['key_topics', 'improvement_areas', 'action_items', 'trust_building_moments', 
                     'interest_indicators', 'concern_indicators', 'upsell_opportunities']:
            if insights_dict.get(field):
                insights_dict[field] = json.dumps(insights_dict[field])
        
        if insights_dict.get('bant_qualification'):
            insights_dict['bant_qualification'] = json.dumps(insights_dict['bant_qualification'])
        
        db_insights = Insights(**insights_dict)
        db.add(db_insights)
        db.commit()
        db.refresh(db_insights)
        
        # Update call score
        call.score = emergency_insights.overall_score
        call.status = CallStatus.PROCESSED
        db.commit()
        
        logger.info(f"Successfully created and saved missing insights for call {call_id}")
        return db_insights
        
    except Exception as e:
        logger.error(f"Error in insights validation for call {call_id}: {e}")
        return None
