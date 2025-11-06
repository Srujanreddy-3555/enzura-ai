from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select
from datetime import timedelta
from typing import Optional
import os

from ..database import get_db
from ..models import User, UserCreate, UserResponse, UserRole, Client
from ..auth import (
    verify_password, get_password_hash, create_access_token,
    get_current_user, get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter()
security = HTTPBearer()

# Token response model
from pydantic import BaseModel

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class AdminCreateUserRequest(BaseModel):
    name: str
    email: str
    password: str
    client_id: int
    role: str = "REP"  # accept flexible casing; normalize in handler

@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Register a new user"""
    
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # Check if user already exists
    existing_user = db.exec(select(User).where(User.email == user_data.email)).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        name=user_data.name,
        role=user_data.role,
        client_id=None  # Will be assigned by admin later
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Get client name if client_id exists
    client_name = None
    if new_user.client_id:
        client = db.get(Client, new_user.client_id)
        client_name = client.name if client else None
    
    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        name=new_user.name,
        role=new_user.role,
        client_id=new_user.client_id,
        client_name=client_name,
        created_at=new_user.created_at
    )

@router.post("/login", response_model=TokenResponse)
async def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login user and return access token"""
    
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # Find user by email
    user = db.exec(select(User).where(User.email == form_data.username)).first()

    # Verify password safely (avoid 500s if hash is missing/invalid)
    is_valid = False
    if user and user.password_hash:
        try:
            is_valid = verify_password(form_data.password, user.password_hash)
        except Exception:
            is_valid = False

    if not user or not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    # Get client name if client_id exists
    client_name = None
    if user.client_id:
        client = db.get(Client, user.client_id)
        client_name = client.name if client else None
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            client_id=user.client_id,
            client_name=client_name,
            created_at=user.created_at
        )
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user information"""
    
    # Get client name if client_id exists
    client_name = None
    if current_user.client_id and db:
        client = db.get(Client, current_user.client_id)
        client_name = client.name if client else None
    
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        client_id=current_user.client_id,
        client_name=client_name,
        created_at=current_user.created_at
    )

@router.post("/logout")
async def logout_user():
    """Logout user (client-side token removal)"""
    return {"message": "Successfully logged out"}

@router.get("/verify-token")
async def verify_token(
    current_user: User = Depends(get_current_active_user)
):
    """Verify if token is valid"""
    return {
        "valid": True,
        "user_id": current_user.id,
        "email": current_user.email,
        "client_id": current_user.client_id
    }

# Multi-tenant user management endpoints

@router.post("/admin-create-user", response_model=UserResponse)
async def admin_create_user(
    payload: AdminCreateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Admin creates a user (rep by default) with a password and assigns to a client."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create users"
        )

    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )

    # Ensure client exists
    client = db.get(Client, payload.client_id)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    # Ensure email is unique
    existing = db.exec(select(User).where(User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # Normalize role to enum (accept 'client'/'rep'/'admin' in any case)
    try:
        role_upper = (payload.role or "REP").upper()
        if role_upper not in {"ADMIN", "CLIENT", "REP"}:
            raise ValueError("invalid role")
        role_enum = UserRole(role_upper)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role value")

    hashed_password = get_password_hash(payload.password)
    user = User(
        email=payload.email,
        password_hash=hashed_password,
        name=payload.name,
        role=role_enum,
        client_id=payload.client_id
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        client_id=user.client_id,
        client_name=client.name,
        created_at=user.created_at
    )

@router.put("/assign-client/{user_id}")
async def assign_user_to_client(
    user_id: int,
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Assign a user to a client (admin only)"""
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can assign users to clients"
        )
    
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # Check if user exists
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if client exists
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Assign user to client
    user.client_id = client_id
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return {
        "message": f"User {user.email} assigned to client {client.name}",
        "user_id": user.id,
        "client_id": client_id,
        "client_name": client.name
    }

@router.get("/unassigned-users")
async def get_unassigned_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all users not assigned to any client (admin only)"""
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view unassigned users"
        )
    
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # Get users without client assignment
    unassigned_users = db.exec(
        select(User).where(User.client_id.is_(None))
    ).all()
    
    return [
        UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            client_id=user.client_id,
            client_name=None,
            created_at=user.created_at
        )
        for user in unassigned_users
    ]
