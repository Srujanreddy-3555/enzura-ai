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
            # Region mismatch often comes as 301 or AuthorizationHeaderMalformed
            if error_code in ('301', 'AuthorizationHeaderMalformed'):
                # Try to fetch actual region
                try:
                    loc = s3_client.get_bucket_location(Bucket=client.s3_bucket_name)
                    actual_region = loc.get('LocationConstraint') or 'us-east-1'
                except Exception:
                    actual_region = 'unknown'
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Bucket region mismatch. Configured: {client.s3_region}, Actual: {actual_region}"
                )
            if error_code == 'NoSuchBucket':
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"S3 bucket {client.s3_bucket_name} does not exist"
                )
            if error_code in ('InvalidAccessKeyId', 'SignatureDoesNotMatch'):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Credentials error: {error_code}. Check Access Key, Secret Key, and time/region."
                )
            if error_code in ('AccessDenied', 'AllAccessDisabled'):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Missing permissions on bucket or objects. AWS: {message}"
                )
            # Other AWS error
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AWS error during HeadBucket: {error_code} - {message}"
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
            if error_code in ('AccessDenied', 'AllAccessDisabled'):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to list objects. Ensure the IAM policy grants s3:ListBucket on the bucket."
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AWS error during ListObjectsV2: {error_code} - {message}"
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
            detail="Invalid AWS credentials for this client"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test connection: {str(e)}"
        )
