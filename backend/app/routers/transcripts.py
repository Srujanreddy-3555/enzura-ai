from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
import json
import logging

from ..database import get_db
from ..models import Transcript, TranscriptCreate, Call, User, UserRole
from ..auth import get_current_active_user

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/call/{call_id}")
async def get_transcript_by_call_id(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get transcript for a specific call (with multi-tenant access control)"""
    
    # Build query based on user role and client (same logic as calls router)
    if current_user.role == UserRole.ADMIN:
        # Admin can see all calls
        call_statement = select(Call).where(Call.id == call_id)
    elif current_user.role == UserRole.CLIENT:
        # Client users see all calls within their client
        if current_user.client_id:
            call_statement = select(Call).where(
                Call.id == call_id,
                Call.client_id == current_user.client_id
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found"
            )
    else:
        # Reps see only their own calls - strict isolation by user_id AND client_id
        if current_user.client_id:
            call_statement = select(Call).where(
                Call.id == call_id,
                Call.user_id == current_user.id,
                Call.client_id == current_user.client_id
            )
        else:
            # If rep has no client_id, only show their own calls
            call_statement = select(Call).where(
                Call.id == call_id,
                Call.user_id == current_user.id
            )
    
    call = db.exec(call_statement).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    # Get the transcript
    transcript_statement = select(Transcript).where(Transcript.call_id == call_id)
    transcript = db.exec(transcript_statement).first()
    
    if not transcript:
        # Check if call exists and queue for processing
        logger.warning(f"Transcript not found for call {call_id}, queueing for processing...")
        # Queue the call for processing
        try:
            from ..services.processing_service import enqueue_call_for_processing
            await enqueue_call_for_processing(call_id)
            logger.info(f"Queued call {call_id} for processing")
            raise HTTPException(
                status_code=status.HTTP_202_ACCEPTED,
                detail="Transcript is being generated. Please wait 60-90 seconds and refresh the page."
            )
        except HTTPException:
            raise
        except Exception as queue_error:
            logger.error(f"Failed to queue call for processing: {queue_error}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transcript not found. Call may still be processing."
            )
    
    # Parse speaker labels if they exist
    speaker_labels = None
    if transcript.speaker_labels:
        try:
            speaker_labels = json.loads(transcript.speaker_labels)
        except json.JSONDecodeError:
            speaker_labels = None
    
    return {
        "call_id": call_id,
        "text": transcript.text,
        "speaker_labels": speaker_labels,
        "created_at": transcript.created_at
    }

@router.post("/", response_model=dict)
async def create_transcript(
    transcript_data: TranscriptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new transcript"""
    
    # Verify the call belongs to the user
    call_statement = select(Call).where(
        Call.id == transcript_data.call_id,
        Call.user_id == current_user.id
    )
    call = db.exec(call_statement).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    # Check if transcript already exists
    existing_transcript = db.exec(
        select(Transcript).where(Transcript.call_id == transcript_data.call_id)
    ).first()
    
    if existing_transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcript already exists for this call"
        )
    
    # Create new transcript
    new_transcript = Transcript(
        call_id=transcript_data.call_id,
        text=transcript_data.text,
        speaker_labels=transcript_data.speaker_labels
    )
    
    db.add(new_transcript)
    db.commit()
    db.refresh(new_transcript)
    
    return {
        "id": new_transcript.id,
        "call_id": new_transcript.call_id,
        "message": "Transcript created successfully"
    }

@router.put("/call/{call_id}")
async def update_transcript(
    call_id: int,
    text: str,
    speaker_labels: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update transcript for a specific call"""
    
    # Verify the call belongs to the user
    call_statement = select(Call).where(
        Call.id == call_id,
        Call.user_id == current_user.id
    )
    call = db.exec(call_statement).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    # Get the transcript
    transcript_statement = select(Transcript).where(Transcript.call_id == call_id)
    transcript = db.exec(transcript_statement).first()
    
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found"
        )
    
    # Update transcript
    transcript.text = text
    if speaker_labels:
        transcript.speaker_labels = speaker_labels
    
    db.add(transcript)
    db.commit()
    db.refresh(transcript)
    
    return {"message": "Transcript updated successfully"}

@router.delete("/call/{call_id}")
async def delete_transcript(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete transcript for a specific call"""
    
    # Verify the call belongs to the user
    call_statement = select(Call).where(
        Call.id == call_id,
        Call.user_id == current_user.id
    )
    call = db.exec(call_statement).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    # Get and delete the transcript
    transcript_statement = select(Transcript).where(Transcript.call_id == call_id)
    transcript = db.exec(transcript_statement).first()
    
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found"
        )
    
    db.delete(transcript)
    db.commit()
    
    return {"message": "Transcript deleted successfully"}

@router.get("/search")
async def search_transcripts(
    query: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Search transcripts by text content"""
    
    # Get all calls for the user
    user_calls_statement = select(Call).where(Call.user_id == current_user.id)
    user_calls = db.exec(user_calls_statement).all()
    user_call_ids = [call.id for call in user_calls]
    
    if not user_call_ids:
        return {"results": [], "total": 0}
    
    # Search transcripts
    transcript_statement = select(Transcript).where(
        Transcript.call_id.in_(user_call_ids),
        Transcript.text.ilike(f"%{query}%")
    )
    transcripts = db.exec(transcript_statement).all()
    
    results = []
    for transcript in transcripts:
        results.append({
            "call_id": transcript.call_id,
            "text_snippet": transcript.text[:200] + "..." if len(transcript.text) > 200 else transcript.text,
            "created_at": transcript.created_at
        })
    
    return {
        "results": results,
        "total": len(results),
        "query": query
    }
