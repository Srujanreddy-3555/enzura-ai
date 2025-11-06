from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List

from ..database import get_db
from ..models import User, UserResponse, UserRole, Call, Client, CallStatus
from ..auth import get_current_active_user

router = APIRouter()

@router.get("/", response_model=List[UserResponse])
async def get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all users (admin only)"""
    
    # Check if user is admin
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    statement = select(User)
    users = db.exec(statement).all()
    
    return [
        UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            client_id=user.client_id,
            client_name=(db.get(Client, user.client_id).name if user.client_id else None),
            created_at=user.created_at
        )
        for user in users
    ]

@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get user by ID"""
    
    # Users can only access their own data unless they're admin
    if current_user.id != user_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    statement = select(User).where(User.id == user_id)
    user = db.exec(statement).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        client_id=user.client_id,
        client_name=(db.get(Client, user.client_id).name if user.client_id else None),
        created_at=user.created_at
    )

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a user (admin only)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Optional: also remove user calls? Keeping calls intact for audit; cascade handled elsewhere when deleting client
    db.delete(user)
    db.commit()

@router.get("/stats/leaderboard")
async def get_leaderboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get leaderboard data for all users"""
    
    # Get all users with their call statistics
    statement = select(User)
    users = db.exec(statement).all()
    
    leaderboard_data = []
    
    for user in users:
        # Get user's calls
        calls_statement = select(Call).where(Call.user_id == user.id)
        user_calls = db.exec(calls_statement).all()
        
        # Calculate stats
        total_calls = len(user_calls)
        processed_calls = [call for call in user_calls if call.status == CallStatus.PROCESSED or str(call.status).upper() == "PROCESSED"]
        avg_score = sum(call.score for call in processed_calls if call.score) / len(processed_calls) if processed_calls else 0
        
        leaderboard_data.append({
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "total_calls": total_calls,
            "processed_calls": len(processed_calls),
            "average_score": round(avg_score, 1) if avg_score else 0
        })
    
    # Sort by average score (descending)
    leaderboard_data.sort(key=lambda x: x["average_score"], reverse=True)
    
    return {
        "leaderboard": leaderboard_data[:10],  # Top 10
        "total_users": len(users)
    }
