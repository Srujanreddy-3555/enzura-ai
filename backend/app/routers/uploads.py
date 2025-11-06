import os
import tempfile
import asyncio
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
import logging
from datetime import datetime

from ..database import get_db
from ..models import Call, CallStatus, User, FileUploadResponse, FileUploadProgress, FileValidationError, UploadMethod, Client
from ..auth import get_current_active_user
from ..services.s3_service import s3_service
from ..services.processing_service import enqueue_call_for_processing
from ..utils.file_utils import FileValidator, AudioProcessor, sanitize_filename, is_audio_file

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload", response_model=FileUploadResponse)
async def upload_audio_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload a single audio file
    """
    logger.info(f"Starting upload for user {current_user.id}, file: {file.filename}")
    
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    try:
        # Step 1: Validate file
        logger.info(f"Validating file: {file.filename}")
        validation_result = await validate_uploaded_file(file)
        if not validation_result["valid"]:
            logger.warning(f"File validation failed for {file.filename}: {validation_result['error']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation_result["error"]
            )
        logger.info(f"File validation successful for {file.filename}")
        
        # Step 2: Sanitize filename
        sanitized_filename = sanitize_filename(file.filename)
        logger.info(f"Sanitized filename: {sanitized_filename}")
        
        # Step 3: Upload to S3
        logger.info(f"Starting S3 upload for {sanitized_filename}")
        
        # Ensure file is ready for upload
        await file.seek(0)
        
        # Resolve client's S3 credentials
        client: Client = db.get(Client, current_user.client_id) if current_user.client_id else None
        if not client:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not assigned to a client")

        s3_url = await s3_service.upload_file_for_client(
            file_content=file,
            filename=sanitized_filename,
            user_id=current_user.id,
            bucket_name=client.s3_bucket_name,
            region=client.s3_region,
            access_key=client.aws_access_key,
            secret_key=client.aws_secret_key
        )
        
        if not s3_url:
            logger.error(f"S3 upload failed for {sanitized_filename}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload file to cloud storage. Please check your connection and try again."
            )
        
        logger.info(f"S3 upload successful for {sanitized_filename}: {s3_url}")
        
        # Create call record in database (English only)
        call = Call(
            user_id=current_user.id,
            client_id=current_user.client_id,
            filename=sanitized_filename,
            s3_url=s3_url,
            status=CallStatus.PROCESSING,
            language="en",  # English only
            translate_to_english=False,  # No translation needed
            upload_method=UploadMethod.MANUAL
        )
        
        db.add(call)
        db.commit()
        db.refresh(call)
        
        # Enqueue for ordered background processing (sequential worker)
        # Fire and forget - don't block the response
        asyncio.create_task(enqueue_call_for_processing(call.id))
        logger.info(f"Enqueued call {call.id} for background processing (queue worker will process it)")
        
        logger.info(f"Successfully uploaded file {sanitized_filename} for user {current_user.id}")
        
        return FileUploadResponse(
            call_id=call.id,
            filename=sanitized_filename,
            s3_url=s3_url,
            status=CallStatus.PROCESSING,
            message="File uploaded successfully. Processing in background..."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/upload-multiple", response_model=List[FileUploadResponse])
async def upload_multiple_audio_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload multiple audio files
    """
    logger.info(f"Starting multiple upload for user {current_user.id}, {len(files)} files")
    
    if len(files) > 10:  # Limit to 10 files per request
        logger.warning(f"Too many files uploaded by user {current_user.id}: {len(files)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 files allowed per upload"
        )
    
    results = []
    errors = []

    # Resolve client's S3 credentials once
    client: Client = db.get(Client, current_user.client_id) if current_user.client_id else None
    if not client:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not assigned to a client")
    
    for file in files:
        try:
            logger.info(f"Processing file: {file.filename}")
            
            # Validate file
            validation_result = await validate_uploaded_file(file)
            if not validation_result["valid"]:
                logger.warning(f"File validation failed for {file.filename}: {validation_result['error']}")
                errors.append(FileValidationError(
                    filename=file.filename,
                    error=validation_result["error"]
                ))
                continue
            
            # Sanitize filename
            sanitized_filename = sanitize_filename(file.filename)
            logger.info(f"Sanitized filename: {sanitized_filename}")
            
            # Upload to S3 (pass the file object directly)
            logger.info(f"Starting S3 upload for {sanitized_filename}")
            
            # Ensure file is ready for upload
            await file.seek(0)
            
            s3_url = await s3_service.upload_file_for_client(
                file_content=file,
                filename=sanitized_filename,
                user_id=current_user.id,
                bucket_name=client.s3_bucket_name,
                region=client.s3_region,
                access_key=client.aws_access_key,
                secret_key=client.aws_secret_key
            )
            
            if not s3_url:
                logger.error(f"S3 upload failed for {sanitized_filename}")
                errors.append(FileValidationError(
                    filename=file.filename,
                    error="Failed to upload file to cloud storage. Please check your connection and try again."
                ))
                continue
            
            logger.info(f"S3 upload successful for {sanitized_filename}: {s3_url}")
            
            # Create call record in database (English only)
            call = Call(
                user_id=current_user.id,
                client_id=current_user.client_id,
                filename=sanitized_filename,
                s3_url=s3_url,
                status=CallStatus.PROCESSING,
                language="en",  # English only
                translate_to_english=False,  # No translation needed
                upload_method=UploadMethod.MANUAL
            )
            
            db.add(call)
            db.commit()
            db.refresh(call)
            
            # Enqueue for ordered background processing (sequential worker)
            # Fire and forget - don't block the response
            asyncio.create_task(enqueue_call_for_processing(call.id))
            logger.info(f"Enqueued call {call.id} for background processing (queue worker will process it)")
            
            results.append(FileUploadResponse(
                call_id=call.id,
                filename=sanitized_filename,
                s3_url=s3_url,
                status=CallStatus.PROCESSING,
                message="File uploaded successfully. Processing in background..."
            ))
            
        except Exception as e:
            logger.error(f"Error uploading file {file.filename}: {e}")
            errors.append(FileValidationError(
                filename=file.filename,
                error=f"Upload failed: {str(e)}"
            ))
    
    # If there are errors, include them in the response
    if errors:
        return JSONResponse(
            status_code=status.HTTP_207_MULTI_STATUS,
            content={
                "successful_uploads": [result.dict() for result in results],
                "errors": [error.dict() for error in errors]
            }
        )
    
    return results

@router.get("/progress/{call_id}", response_model=FileUploadProgress)
async def get_upload_progress(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get upload progress for a specific call
    """
    call = db.exec(select(Call).where(Call.id == call_id, Call.user_id == current_user.id)).first()
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    # Map call status to progress status
    status_mapping = {
        CallStatus.PROCESSING: "processing",
        CallStatus.PROCESSED: "completed",
        CallStatus.FAILED: "failed"
    }
    
    progress_status = status_mapping.get(call.status, "uploading")
    progress_percentage = 100 if call.status == CallStatus.PROCESSED else 50
    
    return FileUploadProgress(
        filename=call.filename,
        progress=progress_percentage,
        status=progress_status,
        message=f"Call is {call.status.value}"
    )

@router.delete("/{call_id}")
async def delete_uploaded_file(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete an uploaded file and its database record
    """
    call = db.exec(select(Call).where(Call.id == call_id, Call.user_id == current_user.id)).first()
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    try:
        # Delete from S3
        if call.s3_url:
            await s3_service.delete_file(call.s3_url)
        
        # Delete from database
        db.delete(call)
        db.commit()
        
        return {"message": "File deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )

async def validate_uploaded_file(file: UploadFile) -> dict:
    """
    Validate an uploaded file
    """
    try:
        # Check if file is provided
        if not file or not file.filename:
            return {"valid": False, "error": "No file provided"}
        
        # Validate filename
        is_valid, error = FileValidator.validate_filename(file.filename)
        if not is_valid:
            return {"valid": False, "error": error}
        
        # Check if it's an audio file
        if not is_audio_file(file.filename):
            return {"valid": False, "error": "File must be an audio file (MP3, WAV, M4A, AAC, OGG, FLAC)"}
        
        # Read file content for validation
        file_content = await file.read()
        
        # Validate file size
        file_size = len(file_content)
        is_valid, error = FileValidator.validate_file_size(file_size)
        if not is_valid:
            return {"valid": False, "error": error}
        
        # Validate file type
        is_valid, error = FileValidator.validate_file_type(file_content, file.filename)
        if not is_valid:
            return {"valid": False, "error": error}
        
        # Reset file pointer for later use
        await file.seek(0)
        
        return {"valid": True, "error": None}
        
    except Exception as e:
        logger.error(f"Error validating file: {e}")
        return {"valid": False, "error": f"Validation error: {str(e)}"}

@router.get("/supported-formats")
async def get_supported_formats():
    """
    Get list of supported audio formats
    """
    return {
        "supported_formats": [
            {"extension": ".mp3", "mime_type": "audio/mpeg", "description": "MP3 Audio"},
            {"extension": ".wav", "mime_type": "audio/wav", "description": "WAV Audio"},
            {"extension": ".m4a", "mime_type": "audio/mp4", "description": "M4A Audio"},
            {"extension": ".aac", "mime_type": "audio/aac", "description": "AAC Audio"},
            {"extension": ".ogg", "mime_type": "audio/ogg", "description": "OGG Audio"},
            {"extension": ".flac", "mime_type": "audio/flac", "description": "FLAC Audio"}
        ],
        "max_file_size_mb": 100,
        "max_files_per_upload": 10
    }

@router.get("/health")
async def health_check():
    """
    Health check endpoint for uploads service
    """
    return {
        "status": "healthy",
        "service": "uploads",
        "s3_connected": s3_service.is_connected(),
        "timestamp": datetime.utcnow().isoformat()
    }
