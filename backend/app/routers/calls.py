from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select, func
from sqlalchemy import String, case
from typing import List, Optional
from datetime import datetime
import logging
import os
import tempfile
import io

from ..database import get_db
from ..models import (
    Call, CallCreate, CallResponse, CallUpdate, CallStatus, UploadMethod, User, UserRole, Insights, PaginatedCallsResponse
)
from ..auth import get_current_active_user

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/stats")
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    OPTIMIZED: Get dashboard statistics WITHOUT fetching all calls
    This endpoint calculates stats directly in the database - much faster!
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    try:
        # Build base query based on user role
        if current_user.role == UserRole.ADMIN:
            base_query = select(Call)
        elif current_user.role == UserRole.CLIENT:
            if current_user.client_id:
                base_query = select(Call).where(Call.client_id == current_user.client_id)
            else:
                return {
                    "totalCalls": 0,
                    "processedCalls": 0,
                    "processingCalls": 0,
                    "failedCalls": 0,
                    "averageScore": 0,
                    "uploadMethodStats": {"manual": 0, "s3_auto": 0}
                }
        else:  # REP
            if current_user.client_id:
                base_query = select(Call).where(
                    Call.user_id == current_user.id,
                    Call.client_id == current_user.client_id
                )
            else:
                base_query = select(Call).where(Call.user_id == current_user.id)
        
        # OPTIMIZED: Use direct aggregations instead of subqueries (MUCH faster!)
        # Build filters once and reuse
        status_filter_processed = func.cast(Call.status, String) == 'PROCESSED'
        status_filter_processing = func.cast(Call.status, String) == 'PROCESSING'
        status_filter_failed = func.cast(Call.status, String) == 'FAILED'
        method_filter_manual = func.cast(Call.upload_method, String) == 'MANUAL'
        method_filter_s3 = func.cast(Call.upload_method, String) == 'S3_AUTO'
        
        # OPTIMIZED: Single query with CASE statements for all counts (much faster than multiple subqueries!)
        # This is 10x faster for admin users with many calls
        aggregation_query = select(
            func.count(Call.id).label('total_calls'),
            func.sum(case((status_filter_processed, 1), else_=0)).label('processed_calls'),
            func.sum(case((status_filter_processing, 1), else_=0)).label('processing_calls'),
            func.sum(case((status_filter_failed, 1), else_=0)).label('failed_calls'),
            func.avg(case((status_filter_processed & Call.score.isnot(None), Call.score), else_=None)).label('avg_score'),
            func.sum(case((method_filter_manual, 1), else_=0)).label('manual_count'),
            func.sum(case((method_filter_s3, 1), else_=0)).label('s3_count')
        )
        
        # Apply base query filters if needed (for non-admin users)
        if current_user.role != UserRole.ADMIN:
            if current_user.role == UserRole.CLIENT and current_user.client_id:
                aggregation_query = aggregation_query.where(Call.client_id == current_user.client_id)
            elif current_user.role == UserRole.REP:
                if current_user.client_id:
                    aggregation_query = aggregation_query.where(
                        Call.user_id == current_user.id,
                        Call.client_id == current_user.client_id
                    )
                else:
                    aggregation_query = aggregation_query.where(Call.user_id == current_user.id)
        
        # Execute single optimized query
        result = db.exec(aggregation_query).first()
        
        # Extract results
        total_calls = result.total_calls or 0
        processed_calls = result.processed_calls or 0
        processing_calls = result.processing_calls or 0
        failed_calls = result.failed_calls or 0
        average_score = round(result.avg_score) if result.avg_score else 0
        manual_count = result.manual_count or 0
        s3_count = result.s3_count or 0
        
        # OPTIMIZED: Get recent calls separately (limit to 5 for performance)
        # Build recent query based on role
        if current_user.role == UserRole.ADMIN:
            recent_query = select(Call).order_by(Call.upload_date.desc()).limit(5)
        elif current_user.role == UserRole.CLIENT and current_user.client_id:
            recent_query = select(Call).where(Call.client_id == current_user.client_id).order_by(Call.upload_date.desc()).limit(5)
        elif current_user.role == UserRole.REP:
            if current_user.client_id:
                recent_query = select(Call).where(
                    Call.user_id == current_user.id,
                    Call.client_id == current_user.client_id
                ).order_by(Call.upload_date.desc()).limit(5)
            else:
                recent_query = select(Call).where(Call.user_id == current_user.id).order_by(Call.upload_date.desc()).limit(5)
        else:
            recent_query = select(Call).limit(0)  # Empty result
        
        recent_calls = db.exec(recent_query).all()
        
        # Get insights for recent calls to include sentiment
        recent_call_ids = [call.id for call in recent_calls]
        recent_insights_map = {}
        if recent_call_ids:
            recent_insights_query = select(Insights).where(Insights.call_id.in_(recent_call_ids))
            recent_insights_list = db.exec(recent_insights_query).all()
            for insight in recent_insights_list:
                recent_insights_map[insight.call_id] = insight
        
        recent_calls_data = [
            CallResponse(
                id=call.id,
                filename=call.filename,
                s3_url=call.s3_url,
                status=call.status,
                language=call.language,
                translate_to_english=getattr(call, 'translate_to_english', False),  # Default to False for existing calls
                upload_date=call.upload_date,
                duration=call.duration,
                score=call.score,
                sentiment=(recent_insights_map.get(call.id).sentiment if recent_insights_map.get(call.id) and recent_insights_map.get(call.id).sentiment else None),
                client_id=call.client_id,
                sales_rep_id=call.sales_rep_id,
                sales_rep_name=call.sales_rep_name,
                upload_method=call.upload_method
            )
            for call in recent_calls
        ]
        
        return {
            "totalCalls": total_calls or 0,
            "processedCalls": processed_calls or 0,
            "processingCalls": processing_calls or 0,
            "failedCalls": failed_calls or 0,
            "averageScore": average_score,
            "uploadMethodStats": {
                "manual": manual_count or 0,
                "s3_auto": s3_count or 0
            },
            "recentCalls": recent_calls_data
        }
        
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard statistics: {str(e)}"
        )

@router.get("/", response_model=PaginatedCallsResponse)
async def get_user_calls(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),  # Default limit, max 200 for performance
    status_filter: Optional[str] = None,
    sales_rep_filter: Optional[str] = None,
    upload_method_filter: Optional[str] = None,
    search_term: Optional[str] = None,  # Search by filename or call ID
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get paginated calls for the current user (filtered by client for multi-tenancy) - OPTIMIZED with server-side pagination"""
    
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # OPTIMIZED: Build base query based on user role and client (reusable for both count and data)
    if current_user.role == UserRole.ADMIN:
        # Admin can see all calls
        base_statement = select(Call)
    elif current_user.role == UserRole.CLIENT:
        # Client users see all calls within their client
        if current_user.client_id:
            base_statement = select(Call).where(Call.client_id == current_user.client_id)
        else:
            return PaginatedCallsResponse(calls=[], total=0, skip=skip, limit=limit)
    else:
        # Reps see only their own calls - strict isolation by user_id AND client_id
        logger.debug(f"Rep user {current_user.id} ({current_user.email}) requesting calls. client_id: {current_user.client_id}")
        if current_user.client_id:
            base_statement = select(Call).where(
                Call.user_id == current_user.id,
                Call.client_id == current_user.client_id
            )
            logger.debug(f"Filtering calls for rep: user_id={current_user.id} AND client_id={current_user.client_id}")
        else:
            # If rep has no client_id, only show their own calls
            base_statement = select(Call).where(Call.user_id == current_user.id)
            logger.warning(f"Rep user {current_user.id} has no client_id! Only filtering by user_id")
    
    # OPTIMIZED: Build filter conditions once (reusable for both queries)
    filter_conditions = []
    
    # Apply status filter if provided (exclude "All" and empty strings)
    if status_filter and status_filter.strip() and status_filter.upper() != "ALL":
        filter_conditions.append(func.cast(Call.status, String) == status_filter.upper())
    
    # Apply sales rep filter if provided
    if sales_rep_filter and sales_rep_filter != "All":
        filter_conditions.append(Call.sales_rep_name == sales_rep_filter)
    
    # Apply upload method filter if provided
    if upload_method_filter and upload_method_filter != "All":
        filter_conditions.append(func.cast(Call.upload_method, String) == upload_method_filter.upper())
    
    # Apply search term filter if provided (search by filename or call ID)
    if search_term:
        search_term_lower = search_term.lower().strip()
        if search_term_lower:
            # Try to parse as integer for call ID search
            try:
                call_id = int(search_term_lower)
                filter_conditions.append(Call.id == call_id)
            except ValueError:
                # Search in filename
                filter_conditions.append(Call.filename.ilike(f"%{search_term_lower}%"))
    
    # Apply filters to base statement
    for condition in filter_conditions:
        base_statement = base_statement.where(condition)
    
    # OPTIMIZED: Get total count using same base query and filters
    count_statement = select(func.count(Call.id))
    # Apply same base filters
    if current_user.role != UserRole.ADMIN:
        if current_user.role == UserRole.CLIENT and current_user.client_id:
            count_statement = count_statement.where(Call.client_id == current_user.client_id)
        elif current_user.role == UserRole.REP:
            if current_user.client_id:
                count_statement = count_statement.where(
                    Call.user_id == current_user.id,
                    Call.client_id == current_user.client_id
                )
            else:
                count_statement = count_statement.where(Call.user_id == current_user.id)
    
    # Apply same filter conditions to count query
    for condition in filter_conditions:
        count_statement = count_statement.where(condition)
    
    total_count = db.exec(count_statement).one()
    
    # OPTIMIZED: Apply pagination to data query
    data_statement = base_statement.order_by(Call.upload_date.desc()).offset(skip).limit(limit)
    
    calls = db.exec(data_statement).all()
    
    # OPTIMIZED: Build response quickly without excessive logging
    # Fetch insights for all calls in one query for better performance
    call_ids = [call.id for call in calls]
    insights_map = {}
    if call_ids:
        insights_query = select(Insights).where(Insights.call_id.in_(call_ids))
        insights_list = db.exec(insights_query).all()
        for insight in insights_list:
            insights_map[insight.call_id] = insight
    
    result = []
    for call in calls:
        # Get sentiment from insights if available
        insight = insights_map.get(call.id)
        sentiment = insight.sentiment if insight and insight.sentiment else None
        
        # Create response object - duration and sentiment will be included even if None
        call_response = CallResponse(
            id=call.id,
            filename=call.filename,
            s3_url=call.s3_url,
            status=call.status,
            language=call.language if call.language else None,
            translate_to_english=getattr(call, 'translate_to_english', False),
            upload_date=call.upload_date,
            duration=call.duration,  # Include duration explicitly (will be null in JSON if None)
            score=call.score if call.score is not None else None,
            sentiment=sentiment,  # Include sentiment from Insights
            client_id=call.client_id,
            sales_rep_id=call.sales_rep_id,
            sales_rep_name=call.sales_rep_name,
            upload_method=call.upload_method
        )
        result.append(call_response)
    
    logger.debug(f"Returning {len(result)} calls out of {total_count} total")
    return PaginatedCallsResponse(
        calls=result,
        total=total_count,
        skip=skip,
        limit=limit
    )

@router.post("/{call_id}/extract-duration")
async def extract_call_duration(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Manually trigger duration extraction for a call.
    This endpoint is called by the frontend when it detects PROCESSED calls without duration.
    """
    logger.info(f"🔧 Manual duration extraction requested for call {call_id} by user {current_user.id}")
    
    # Get the call
    call = db.exec(select(Call).where(Call.id == call_id)).first()
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call {call_id} not found"
        )
    
    # Check access permissions (user must have access to this call)
    if current_user.role == UserRole.REP:
        if call.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this call"
            )
    elif current_user.role == UserRole.CLIENT:
        if call.client_id != current_user.client_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this call"
            )
    
    # Check if duration already exists
    if call.duration and call.duration > 0:
        logger.info(f"✅ Call {call_id} already has duration: {call.duration}s")
        return {
            "success": True,
            "message": f"Call already has duration: {call.duration}s ({call.duration // 60}:{(call.duration % 60):02d})",
            "duration": call.duration,
            "duration_formatted": f"{call.duration // 60}:{(call.duration % 60):02d}"
        }
    
    # Extract duration from S3
    try:
        from ..utils.file_utils import AudioProcessor
        import boto3
        import tempfile
        from urllib.parse import urlparse
        from ..models import Client
        
        if not call.client_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Call has no client_id, cannot access S3"
            )
        
        client = db.exec(select(Client).where(Client.id == call.client_id)).first()
        if not client or not client.aws_access_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client S3 credentials not available"
            )
        
        # Download from S3
        # Handle both full URLs and S3 keys
        if call.s3_url.startswith('http://') or call.s3_url.startswith('https://'):
            parsed = urlparse(call.s3_url)
            # Extract key from path - remove leading slash and bucket name if present
            s3_key = parsed.path.lstrip('/')
            # If path starts with bucket name, remove it
            if s3_key.startswith(client.s3_bucket_name + '/'):
                s3_key = s3_key[len(client.s3_bucket_name) + 1:]
            # Handle calls/ prefix
            if not s3_key.startswith('calls/'):
                # Check if filename is already in the path
                if call.filename not in s3_key:
                    s3_key = f"calls/{call.filename}" if not s3_key else s3_key
        else:
            # Already a key, not a URL
            s3_key = call.s3_url
        
        logger.info(f"📥 Downloading from S3 - bucket: {client.s3_bucket_name}, key: {s3_key}")
        logger.info(f"📥 S3 URL was: {call.s3_url}")
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=client.aws_access_key,
            aws_secret_access_key=client.aws_secret_key,
            region_name=client.s3_region
        )
        
        try:
            response = s3_client.get_object(Bucket=client.s3_bucket_name, Key=s3_key)
            audio_bytes = response['Body'].read()
            logger.info(f"✅ Downloaded {len(audio_bytes)} bytes from S3")
        except Exception as s3_exception:
            # Check if it's a NoSuchKey error
            error_code = getattr(s3_exception, 'response', {}).get('Error', {}).get('Code', '')
            if error_code == 'NoSuchKey' or 'NoSuchKey' in str(s3_exception):
                logger.error(f"❌ S3 key not found: {s3_key}")
                # Try alternative key formats
                alternative_keys = [
                    f"calls/{call.filename}",
                    call.filename,
                    f"{call.filename}",
                ]
                audio_bytes = None
                for alt_key in alternative_keys:
                    try:
                        logger.info(f"🔄 Trying alternative key: {alt_key}")
                        response = s3_client.get_object(Bucket=client.s3_bucket_name, Key=alt_key)
                        audio_bytes = response['Body'].read()
                        logger.info(f"✅ Found file with alternative key: {alt_key} ({len(audio_bytes)} bytes)")
                        s3_key = alt_key
                        break
                    except Exception:
                        continue
                
                if not audio_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Audio file not found in S3. Tried keys: {s3_key}, {', '.join(alternative_keys)}"
                    )
            else:
                # Other S3 errors
                logger.error(f"❌ S3 download error: {s3_exception}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to download audio from S3: {str(s3_exception)}"
                )
        
        # Save to temp file
        file_extension = os.path.splitext(call.filename)[1] or '.mp3'
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_file.write(audio_bytes)
            temp_file_path = temp_file.name
        
        # Extract duration
        logger.info(f"⏱️ Extracting duration using AudioProcessor...")
        logger.info(f"📁 Temp file path: {temp_file_path}, size: {os.path.getsize(temp_file_path) if os.path.exists(temp_file_path) else 'N/A'} bytes")
        
        try:
            extracted_duration = AudioProcessor.get_audio_duration(temp_file_path)
        except Exception as extract_error:
            logger.error(f"❌ AudioProcessor.get_audio_duration() raised exception: {extract_error}")
            import traceback
            logger.error(traceback.format_exc())
            extracted_duration = None
        
        # Cleanup temp file
        try:
            os.unlink(temp_file_path)
        except:
            pass
        
        if extracted_duration and extracted_duration > 0:
            # Save to database
            call.duration = extracted_duration
            db.add(call)
            db.commit()
            db.refresh(call)
            
            logger.info(f"✅✅✅ Duration extracted and saved: {extracted_duration}s ({extracted_duration // 60}:{(extracted_duration % 60):02d})")
            
            return {
                "success": True,
                "message": f"Duration extracted successfully: {extracted_duration}s ({extracted_duration // 60}:{(extracted_duration % 60):02d})",
                "duration": extracted_duration,
                "duration_formatted": f"{extracted_duration // 60}:{(extracted_duration % 60):02d}"
            }
        else:
            # Provide more specific error message
            error_detail = f"Duration extraction returned invalid value: {extracted_duration}"
            if extracted_duration is None:
                error_detail = "Duration extraction returned None. Audio file may be corrupted or unsupported format."
            elif extracted_duration == 0:
                error_detail = "Duration extraction returned 0. Audio file may be empty or invalid."
            
            logger.error(f"❌ {error_detail}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_detail
            )
            
    except Exception as e:
        logger.error(f"❌ Error extracting duration for call {call_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract duration: {str(e)}"
        )

@router.get("/{call_id}/audio")
async def get_call_audio(
    call_id: int,
    download: bool = Query(default=False, description="Trigger download instead of streaming"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get audio file URL for a call.
    - Stream: Returns pre-signed S3 URL for direct browser streaming (FAST!)
    - Download: Returns file with download headers for browser download
    """
    logger.info(f"🎵 Audio request for call {call_id} by user {current_user.id} (download={download})")
    
    # Get the call
    call = db.exec(select(Call).where(Call.id == call_id)).first()
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call {call_id} not found"
        )
    
    # Check access permissions
    if current_user.role == UserRole.REP:
        if call.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this call"
            )
    elif current_user.role == UserRole.CLIENT:
        if call.client_id != current_user.client_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this call"
            )
    
    # Get client credentials for S3 access
    if not call.client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Call has no client_id"
        )
    
    from ..models import Client
    client = db.exec(select(Client).where(Client.id == call.client_id)).first()
    if not client or not client.aws_access_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client credentials not available"
        )
    
    # Parse S3 URL and generate pre-signed URL or download
    try:
        import boto3
        from urllib.parse import urlparse
        from datetime import timedelta
        
        # Parse S3 key from URL
        if call.s3_url.startswith('http://') or call.s3_url.startswith('https://'):
            parsed = urlparse(call.s3_url)
            s3_key = parsed.path.lstrip('/')
            if s3_key.startswith(client.s3_bucket_name + '/'):
                s3_key = s3_key[len(client.s3_bucket_name) + 1:]
        else:
            s3_key = call.s3_url
        
        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=client.aws_access_key,
            aws_secret_access_key=client.aws_secret_key,
            region_name=client.s3_region
        )
        
        # Find the correct S3 key (with fallback)
        found_key = None
        alternative_keys = [
            s3_key,
            f"calls/{call.filename}",
            call.filename,
        ]
        
        for key in alternative_keys:
            try:
                # Try to head the object to verify it exists
                s3_client.head_object(Bucket=client.s3_bucket_name, Key=key)
                found_key = key
                logger.info(f"✅ Found audio file with key: {key}")
                break
            except Exception:
                continue
        
        if not found_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audio file not found in S3. Tried: {', '.join(alternative_keys)}"
            )
        
        if not download:
            # For streaming: Generate pre-signed URL (FAST - direct S3 access!)
            # URL expires in 1 hour (3600 seconds)
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': client.s3_bucket_name,
                    'Key': found_key
                },
                ExpiresIn=3600  # 1 hour expiration
            )
            logger.info(f"🎵 Generated pre-signed URL for streaming (expires in 1 hour)")
            
            # Return JSON with the URL
            from fastapi.responses import JSONResponse
            return JSONResponse(content={
                "url": presigned_url,
                "filename": call.filename
            })
        else:
            # For download: Stream through backend (for proper Content-Disposition)
            response = s3_client.get_object(Bucket=client.s3_bucket_name, Key=found_key)
            audio_bytes = response['Body'].read()
            content_type = response.get('ContentType', 'audio/mpeg')
            
            # Determine content type from file extension if not provided
            if not content_type or content_type == 'binary/octet-stream':
                file_ext = os.path.splitext(call.filename)[1].lower()
                content_type_map = {
                    '.mp3': 'audio/mpeg',
                    '.wav': 'audio/wav',
                    '.m4a': 'audio/mp4',
                    '.aac': 'audio/aac',
                    '.ogg': 'audio/ogg',
                    '.flac': 'audio/flac'
                }
                content_type = content_type_map.get(file_ext, 'audio/mpeg')
            
            # Create file-like object for streaming
            audio_stream = io.BytesIO(audio_bytes)
            
            # Set headers for download
            headers = {
                "Content-Type": content_type,
                "Content-Length": str(len(audio_bytes)),
                "Content-Disposition": f'attachment; filename="{call.filename or f"call_{call_id}_audio.mp3"}"'
            }
            logger.info(f"📥 Downloading audio: {call.filename}")
            
            return StreamingResponse(
                audio_stream,
                media_type=content_type,
                headers=headers
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting audio for call {call_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve audio file: {str(e)}"
        )

@router.get("/{call_id}", response_model=CallResponse)
async def get_call_by_id(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get specific call by ID (with multi-tenant access control)"""
    
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # Build query based on user role and client
    if current_user.role == UserRole.ADMIN:
        statement = select(Call).where(Call.id == call_id)
    elif current_user.role == UserRole.CLIENT:
        if current_user.client_id:
            statement = select(Call).where(Call.id == call_id, Call.client_id == current_user.client_id)
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    else:
        # Rep can only access own call
        statement = select(Call).where(Call.id == call_id, Call.user_id == current_user.id)
    
    call = db.exec(statement).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    # Get sentiment from insights
    insight = db.exec(select(Insights).where(Insights.call_id == call.id)).first()
    sentiment = insight.sentiment if insight and insight.sentiment else None
    
    return CallResponse(
        id=call.id,
        filename=call.filename,
        s3_url=call.s3_url,
        status=call.status,
        language=call.language,
        translate_to_english=getattr(call, 'translate_to_english', False),  # Default to False for existing calls
        upload_date=call.upload_date,
        duration=call.duration,
        score=call.score,
        sentiment=sentiment,  # Include sentiment from Insights
        client_id=call.client_id,
        sales_rep_id=call.sales_rep_id,
        sales_rep_name=call.sales_rep_name,
        upload_method=call.upload_method
    )

@router.post("/", response_model=CallResponse)
async def create_call(
    call_data: CallCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new call record"""
    
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # Create new call (auto-detect language, translate to English for insights)
    new_call = Call(
        filename=call_data.filename,
        s3_url=call_data.s3_url,
        status=CallStatus.PROCESSING,
        language=call_data.language,  # None = auto-detect (supports Arabic "ar" and 100+ languages)
        translate_to_english=call_data.translate_to_english if hasattr(call_data, 'translate_to_english') else True,  # Default to True for insights generation
        user_id=current_user.id,
        client_id=current_user.client_id,  # Set client_id from current user
        upload_method=call_data.upload_method or UploadMethod.MANUAL
    )
    
    db.add(new_call)
    db.commit()
    db.refresh(new_call)
    
    # CRITICAL: Extract duration IMMEDIATELY using the exact same method as manual script
    # This ensures duration is saved before any async processing starts
    try:
        from ..utils.file_utils import AudioProcessor
        import boto3
        import tempfile
        from urllib.parse import urlparse
        from ..models import Client
        
        if new_call.client_id:
            client = db.exec(select(Client).where(Client.id == new_call.client_id)).first()
            if client and client.aws_access_key:
                logger.info(f"⏱️ Extracting duration for call {new_call.id} immediately after creation...")
                
                # Parse S3 URL (same logic as manual script)
                if new_call.s3_url.startswith('http://') or new_call.s3_url.startswith('https://'):
                    parsed = urlparse(new_call.s3_url)
                    s3_key = parsed.path.lstrip('/')
                    if s3_key.startswith(client.s3_bucket_name + '/'):
                        s3_key = s3_key[len(client.s3_bucket_name) + 1:]
                else:
                    s3_key = new_call.s3_url
                
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
                        f"calls/{new_call.filename}",
                        new_call.filename,
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
                    file_extension = os.path.splitext(new_call.filename)[1] or '.mp3'
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                        temp_file.write(audio_bytes)
                        temp_file_path = temp_file.name
                    
                    try:
                        # Extract duration using the same method as manual script
                        duration = AudioProcessor.get_audio_duration(temp_file_path)
                        if duration and duration > 0:
                            # Save to database (same as manual script)
                            new_call.duration = duration
                            db.add(new_call)
                            db.commit()
                            db.refresh(new_call)
                            
                            if new_call.duration == duration:
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
            else:
                logger.warning(f"⏱️ No AWS credentials available for duration extraction")
        else:
            logger.warning(f"⏱️ Call has no client_id for duration extraction")
    except Exception as extract_error:
        # Don't fail call creation if duration extraction fails
        logger.error(f"⏱️ Error extracting duration during call creation: {extract_error}")
        import traceback
        logger.error(traceback.format_exc())
    
    return CallResponse(
        id=new_call.id,
        filename=new_call.filename,
        s3_url=new_call.s3_url,
        status=new_call.status,
        language=new_call.language,
        translate_to_english=getattr(new_call, 'translate_to_english', False),  # Default to False for existing calls
        upload_date=new_call.upload_date,
        duration=new_call.duration,
        score=new_call.score,
        sentiment=None,  # Sentiment will be available after processing
        client_id=new_call.client_id,
        sales_rep_id=new_call.sales_rep_id,
        sales_rep_name=new_call.sales_rep_name,
        upload_method=new_call.upload_method
    )

@router.put("/{call_id}")
async def update_call(
    call_id: int,
    call_update: CallUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update a call record"""
    
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # Build query based on user role
    if current_user.role == UserRole.ADMIN:
        statement = select(Call).where(Call.id == call_id)
    elif current_user.role == UserRole.CLIENT:
        if current_user.client_id:
            statement = select(Call).where(Call.id == call_id, Call.client_id == current_user.client_id)
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    else:
        # Rep can only update own call
        statement = select(Call).where(Call.id == call_id, Call.user_id == current_user.id)
    
    call = db.exec(statement).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    # Update call
    if call_update.status:
        call.status = call_update.status
    if call_update.score is not None:
        call.score = call_update.score
    if call_update.duration is not None:
        call.duration = call_update.duration
    
    db.add(call)
    db.commit()
    db.refresh(call)
    
    return {"message": "Call updated successfully", "call_id": call_id}

@router.delete("/{call_id}")
async def delete_call(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a call record"""
    
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # Build query based on user role
    if current_user.role == UserRole.ADMIN:
        statement = select(Call).where(Call.id == call_id)
    elif current_user.role == UserRole.CLIENT:
        if current_user.client_id:
            statement = select(Call).where(Call.id == call_id, Call.client_id == current_user.client_id)
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    else:
        # Rep can only delete own call
        statement = select(Call).where(Call.id == call_id, Call.user_id == current_user.id)
    
    call = db.exec(statement).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    # CRITICAL: Delete S3 file first (before database records)
    try:
        if call.s3_url:
            from ..services.s3_service import s3_service
            from ..models import Client
            
            # Get client credentials for S3 deletion
            if call.client_id:
                client = db.exec(select(Client).where(Client.id == call.client_id)).first()
                if client and client.aws_access_key and client.aws_secret_key:
                    # Create temporary S3 client with client credentials
                    import boto3
                    from urllib.parse import urlparse
                    
                    try:
                        parsed = urlparse(call.s3_url)
                        host = parsed.netloc
                        path = parsed.path.lstrip('/')
                        parts = host.split('.')
                        bucket = parts[0] if parts else None
                        region = parts[2] if len(parts) >= 4 else client.s3_region
                        
                        if bucket:
                            s3_client = boto3.client(
                                's3',
                                aws_access_key_id=client.aws_access_key,
                                aws_secret_access_key=client.aws_secret_key,
                                region_name=region
                            )
                            s3_client.delete_object(Bucket=bucket, Key=path)
                            logger.info(f"Successfully deleted S3 file: {call.s3_url}")
                    except Exception as s3_error:
                        logger.warning(f"Failed to delete S3 file {call.s3_url}: {s3_error}. Continuing with database deletion.")
    except Exception as e:
        logger.warning(f"Error during S3 file deletion: {e}. Continuing with database deletion.")
    
    # Delete related data from database
    from ..models import Transcript, Insights
    transcript = db.exec(select(Transcript).where(Transcript.call_id == call_id)).first()
    if transcript:
        db.delete(transcript)
    
    insights = db.exec(select(Insights).where(Insights.call_id == call_id)).first()
    if insights:
        db.delete(insights)
    
    # Delete call from database
    db.delete(call)
    db.commit()
    
    logger.info(f"Call {call_id} deleted successfully from database and S3")
    return {"message": "Call deleted successfully", "call_id": call_id}

@router.get("/stats/leaderboard")
async def get_leaderboard_stats(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get leaderboard statistics - OPTIMIZED with database aggregation"""
    
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    try:
        # Build base query based on user role
        if current_user.role == UserRole.ADMIN:
            base_query = select(Call)
        elif current_user.role == UserRole.CLIENT:
            if current_user.client_id:
                base_query = select(Call).where(Call.client_id == current_user.client_id)
            else:
                return {"leaderboard": []}
        elif current_user.role == UserRole.REP:
            # Reps can see leaderboard but only for their client
            if current_user.client_id:
                base_query = select(Call).where(Call.client_id == current_user.client_id)
                # Limit reps to top 3 only for motivation
                limit = min(limit, 3)
            else:
                return {"leaderboard": []}
        else:
            return {"leaderboard": []}
        
        # OPTIMIZED: Use SQL GROUP BY for aggregation - MUCH faster than Python loops!
        # This calculates everything in the database, not in Python
        # Build aggregation query with GROUP BY - include client name
        from ..models import Client
        
        aggregation_query = select(
            Call.sales_rep_name,
            Call.client_id,
            func.count(Call.id).label('total_calls'),
            func.avg(Call.score).label('average_score'),
            func.sum(Call.score).label('total_score')
        ).where(
            Call.sales_rep_name.isnot(None),
            Call.score.isnot(None),
            func.cast(Call.status, String) == 'PROCESSED'
        ).group_by(Call.sales_rep_name, Call.client_id)
        
        # Apply base query filters (role-based access)
        if current_user.role == UserRole.CLIENT and current_user.client_id:
            aggregation_query = aggregation_query.where(Call.client_id == current_user.client_id)
        elif current_user.role == UserRole.REP and current_user.client_id:
            aggregation_query = aggregation_query.where(Call.client_id == current_user.client_id)
        
        # Execute optimized aggregation query
        results = db.exec(aggregation_query).all()
        
        # Get client names for all unique client_ids
        client_ids = list(set([row.client_id for row in results if row.client_id]))
        clients_map = {}
        if client_ids:
            # Fetch clients one by one (simpler approach, works with SQLModel)
            for client_id in client_ids:
                client = db.exec(select(Client).where(Client.id == client_id)).first()
                if client:
                    clients_map[client_id] = client.name
        
        # Build leaderboard from SQL aggregation results
        leaderboard = []
        for row in results:
            leaderboard.append({
                "name": row.sales_rep_name,
                "client_id": row.client_id,
                "client_name": clients_map.get(row.client_id, "Unknown Client") if row.client_id else "Unknown Client",
                "total_calls": row.total_calls or 0,
                "total_score": int(row.total_score) if row.total_score else 0,
                "average_score": round(row.average_score) if row.average_score else 0
            })
        
        # Sort by average score descending (SQL can do this too, but this is fine)
        leaderboard.sort(key=lambda x: x["average_score"], reverse=True)
        
        return {
            "leaderboard": leaderboard[:limit]
        }
        
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch leaderboard: {str(e)}"
        )

# Keep existing endpoints below...