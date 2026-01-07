"""
S3 Monitoring Management Router
Provides endpoints to manage the S3 monitoring service.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Dict, Any
import asyncio

from ..database import get_db
from ..models import Client, User, UserRole
from ..auth import get_current_active_user
from ..services.s3_monitoring_service import s3_monitoring_service

router = APIRouter(prefix="/s3-monitoring", tags=["S3 Monitoring"])

@router.post("/start")
async def start_s3_monitoring(
    current_user: User = Depends(get_current_active_user)
):
    """Start the S3 monitoring service (admin only)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can start S3 monitoring"
        )
    
    try:
        await s3_monitoring_service.start_monitoring()
        return {
            "message": "S3 monitoring service started successfully",
            "status": "running"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start S3 monitoring: {str(e)}"
        )

@router.post("/stop")
async def stop_s3_monitoring(
    current_user: User = Depends(get_current_active_user)
):
    """Stop the S3 monitoring service (admin only)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can stop S3 monitoring"
        )
    
    try:
        await s3_monitoring_service.stop_monitoring()
        return {
            "message": "S3 monitoring service stopped successfully",
            "status": "stopped"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop S3 monitoring: {str(e)}"
        )

@router.get("/status")
async def get_monitoring_status(
    current_user: User = Depends(get_current_active_user)
):
    """Get the current status of the S3 monitoring service."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view monitoring status"
        )
    
    return {
        "is_running": s3_monitoring_service.is_running,
        "monitored_clients": list(s3_monitoring_service.scan_tasks.keys()),
        "queue_size": s3_monitoring_service.processing_queue.qsize() if s3_monitoring_service.is_running else 0
    }

@router.post("/add-client/{client_id}")
async def add_client_to_monitoring(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Add a client to S3 monitoring (admin only)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can add clients to monitoring"
        )
    
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # Get client
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    if client.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only active clients can be added to monitoring"
        )
    
    try:
        await s3_monitoring_service.add_client_monitoring(client)
        return {
            "message": f"Client {client.name} added to S3 monitoring",
            "client_id": client_id,
            "client_name": client.name
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add client to monitoring: {str(e)}"
        )

@router.delete("/remove-client/{client_id}")
async def remove_client_from_monitoring(
    client_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """Remove a client from S3 monitoring (admin only)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can remove clients from monitoring"
        )
    
    try:
        await s3_monitoring_service.remove_client_monitoring(client_id)
        return {
            "message": f"Client {client_id} removed from S3 monitoring",
            "client_id": client_id
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove client from monitoring: {str(e)}"
        )

@router.post("/scan-client/{client_id}")
async def manual_scan_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Manually trigger a scan of a client's S3 bucket (admin only)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can trigger manual scans"
        )
    
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # Get client
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    try:
        # Perform a single scan
        await s3_monitoring_service._scan_bucket_once(client)
        return {
            "message": f"Manual scan completed for client {client.name}",
            "client_id": client_id,
            "client_name": client.name
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scan client bucket: {str(e)}"
        )

@router.get("/clients")
async def get_monitored_clients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get list of clients being monitored (admin only)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view monitored clients"
        )
    
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    try:
        # Get all clients
        clients = db.exec(select(Client)).all()
        
        monitored_client_ids = set(s3_monitoring_service.scan_tasks.keys())
        
        client_info = []
        for client in clients:
            client_info.append({
                "id": client.id,
                "name": client.name,
                "s3_bucket_name": client.s3_bucket_name,
                "s3_region": client.s3_region,
                "processing_schedule": client.processing_schedule,
                "status": client.status,
                "is_monitored": client.id in monitored_client_ids,
                "is_active": s3_monitoring_service.is_running and client.id in monitored_client_ids
            })
        
        return {
            "clients": client_info,
            "monitoring_active": s3_monitoring_service.is_running,
            "total_clients": len(clients),
            "monitored_clients": len(monitored_client_ids)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get monitored clients: {str(e)}"
        )

@router.get("/logs")
async def get_monitoring_logs(
    limit: int = 100,
    current_user: User = Depends(get_current_active_user)
):
    """Get recent monitoring logs (admin only)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view monitoring logs"
        )
    
    # This would typically read from a log file or database
    # For now, return a placeholder response
    return {
        "message": "Log retrieval not implemented yet",
        "limit": limit,
        "note": "Logs would be retrieved from the monitoring service"
    }

@router.get("/diagnostics/{client_id}")
async def get_s3_diagnostics(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get comprehensive diagnostics for S3 monitoring of a client (admin only)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view diagnostics"
        )
    
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # Get client
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    try:
        import boto3
        from botocore.exceptions import ClientError
        from sqlmodel import select
        from ..models import Call, CallStatus
        
        diagnostics = {
            "client_id": client_id,
            "client_name": client.name,
            "bucket_name": client.s3_bucket_name,
            "region": client.s3_region,
            "monitoring_status": {
                "is_running": s3_monitoring_service.is_running,
                "is_client_monitored": client_id in s3_monitoring_service.scan_tasks,
                "processing_schedule": client.processing_schedule,
                "scan_interval_seconds": s3_monitoring_service._get_scan_interval(client.processing_schedule)
            },
            "s3_bucket_info": {},
            "recent_calls": [],
            "errors": []
        }
        
        # Try to connect to S3 and list files
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=client.aws_access_key,
                aws_secret_access_key=client.aws_secret_key,
                region_name=client.s3_region
            )
            
            # List objects in bucket
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=client.s3_bucket_name, MaxKeys=50)
            
            all_files = []
            audio_files = []
            
            for page in pages:
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    key = obj['Key']
                    all_files.append({
                        "key": key,
                        "size": obj['Size'],
                        "last_modified": obj['LastModified'].isoformat(),
                        "is_audio": s3_monitoring_service._is_audio_file(key)
                    })
                    
                    if s3_monitoring_service._is_audio_file(key):
                        audio_files.append(key)
            
            diagnostics["s3_bucket_info"] = {
                "total_files": len(all_files),
                "audio_files": len(audio_files),
                "sample_files": all_files[:10],  # First 10 files
                "audio_file_keys": audio_files[:10]  # First 10 audio files
            }
            
        except ClientError as e:
            diagnostics["errors"].append(f"S3 connection error: {e.response.get('Error', {}).get('Message', str(e))}")
        except Exception as e:
            diagnostics["errors"].append(f"Error listing S3 files: {str(e)}")
        
        # Get recent calls from this client
        try:
            recent_calls = db.exec(
                select(Call)
                .where(Call.client_id == client_id)
                .order_by(Call.upload_date.desc())
                .limit(10)
            ).all()
            
            diagnostics["recent_calls"] = [
                {
                    "id": call.id,
                    "filename": call.filename,
                    "status": call.status,
                    "upload_date": call.upload_date.isoformat() if call.upload_date else None,
                    "upload_method": call.upload_method,
                    "s3_url": call.s3_url,
                    "has_transcript": bool(call.id),  # Would need to check transcript table
                    "score": call.score
                }
                for call in recent_calls
            ]
        except Exception as e:
            diagnostics["errors"].append(f"Error fetching recent calls: {str(e)}")
        
        # Check if files in S3 match calls in database
        try:
            if audio_files:
                matched_count = 0
                unmatched_files = []
                
                for audio_key in audio_files[:20]:  # Check first 20
                    existing_call = db.exec(
                        select(Call).where(
                            Call.client_id == client_id,
                            Call.s3_url.contains(audio_key)
                        )
                    ).first()
                    
                    if existing_call:
                        matched_count += 1
                    else:
                        unmatched_files.append(audio_key)
                
                diagnostics["file_matching"] = {
                    "checked_files": min(20, len(audio_files)),
                    "matched_in_database": matched_count,
                    "unmatched_files": unmatched_files[:5]  # First 5 unmatched
                }
        except Exception as e:
            diagnostics["errors"].append(f"Error matching files: {str(e)}")
        
        return diagnostics
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating diagnostics: {str(e)}"
        )

@router.get("/test-connection/{client_id}")
async def test_client_connection(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Test S3 connection for a specific client (admin only)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can test client connections"
        )
    
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # Get client
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError

        # Build client with provided region
        s3_client = boto3.client(
            's3',
            aws_access_key_id=client.aws_access_key,
            aws_secret_access_key=client.aws_secret_key,
            region_name=client.s3_region
        )

        # Step 1: HeadBucket - cheapest existence/access check; also surfaces region mismatch
        try:
            s3_client.head_bucket(Bucket=client.s3_bucket_name)
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            message = e.response.get('Error', {}).get('Message', 'AWS error')
            http_status = e.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 0)
            
            # Check for 403 Forbidden (either by HTTP status or error code)
            if http_status == 403 or error_code in ('AccessDenied', 'AllAccessDisabled', 'Forbidden'):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied to bucket '{client.s3_bucket_name}'. "
                           f"Please verify: 1) IAM user has 's3:HeadBucket' permission, "
                           f"2) Bucket policy allows access, 3) Credentials are correct. "
                           f"AWS Error: {error_code} - {message}"
                )
            
            # Region mismatch often comes as 301 or AuthorizationHeaderMalformed
            if error_code in ('301', 'AuthorizationHeaderMalformed', 'PermanentRedirect'):
                # Try to fetch actual region
                try:
                    loc = s3_client.get_bucket_location(Bucket=client.s3_bucket_name)
                    actual_region = loc.get('LocationConstraint') or 'us-east-1'
                except Exception:
                    actual_region = 'unknown'
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Bucket region mismatch. Configured: {client.s3_region}, Actual: {actual_region}. "
                           f"Please update the client's S3 region setting."
                )
            if error_code == 'NoSuchBucket':
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"S3 bucket '{client.s3_bucket_name}' does not exist in region '{client.s3_region}'. "
                           f"Please verify the bucket name and region."
                )
            if error_code in ('InvalidAccessKeyId', 'SignatureDoesNotMatch', 'InvalidToken'):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid AWS credentials. Error: {error_code}. "
                           f"Please verify: 1) Access Key ID is correct, 2) Secret Access Key is correct, "
                           f"3) System time is synchronized. AWS Message: {message}"
                )
            # Other AWS error
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AWS error during HeadBucket: {error_code} (HTTP {http_status}) - {message}"
            )

        # Step 2: GetBucketLocation to confirm region
        try:
            loc = s3_client.get_bucket_location(Bucket=client.s3_bucket_name)
            actual_region = loc.get('LocationConstraint') or 'us-east-1'
            if actual_region != client.s3_region:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Bucket region mismatch. Configured: {client.s3_region}, Actual: {actual_region}"
                )
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            message = e.response.get('Error', {}).get('Message', 'AWS error')
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get bucket location: {error_code} - {message}"
            )

        # Step 3: Minimal List to validate ListBucket permission
        try:
            response = s3_client.list_objects_v2(Bucket=client.s3_bucket_name, MaxKeys=1)
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            message = e.response.get('Error', {}).get('Message', 'AWS error')
            http_status = e.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 0)
            
            # Check for 403 Forbidden (either by HTTP status or error code)
            if http_status == 403 or error_code in ('AccessDenied', 'AllAccessDisabled', 'Forbidden'):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied to list objects in bucket '{client.s3_bucket_name}'. "
                           f"Please ensure the IAM user/role has 's3:ListBucket' permission. "
                           f"AWS Error: {error_code} - {message}"
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AWS error during ListObjectsV2: {error_code} (HTTP {http_status}) - {message}"
            )

        return {
            "status": "success",
            "message": f"Successfully connected to S3 bucket {client.s3_bucket_name}",
            "client_id": client_id,
            "client_name": client.name,
            "bucket_name": client.s3_bucket_name,
            "region": client.s3_region,
            "object_count": response.get('KeyCount', 0)
        }

    except NoCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid AWS credentials for this client. Please check Access Key ID and Secret Access Key."
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is (they already have proper error messages)
        raise
    except Exception as e:
        # Catch any other unexpected errors
        import traceback
        error_details = traceback.format_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error testing S3 connection: {str(e)}. Please check logs for details."
        )
