from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models import (
    Client, ClientCreate, ClientResponse, ClientUpdate,
    SalesRep, SalesRepCreate, SalesRepResponse, SalesRepUpdate,
    User, UserRole, CallStatus
)
from app.auth import get_current_active_user

router = APIRouter(prefix="/clients", tags=["clients"])

# Client Management Endpoints

@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client(
    client_data: ClientCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new client (admin only)."""
    # Only admins can create clients
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create clients"
        )
    
    # Check if client name already exists
    existing_client = session.exec(
        select(Client).where(Client.name == client_data.name)
    ).first()
    
    if existing_client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client with this name already exists"
        )
    
    # Check if S3 bucket name already exists
    existing_bucket = session.exec(
        select(Client).where(Client.s3_bucket_name == client_data.s3_bucket_name)
    ).first()
    
    if existing_bucket:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="S3 bucket name already in use"
        )
    
    # Create new client
    client = Client(
        name=client_data.name,
        s3_bucket_name=client_data.s3_bucket_name,
        s3_region=client_data.s3_region,
        aws_access_key=client_data.aws_access_key,
        aws_secret_key=client_data.aws_secret_key,
        processing_schedule=client_data.processing_schedule,
        timezone=client_data.timezone,
        status="active"
    )
    
    session.add(client)
    session.commit()
    session.refresh(client)
    
    return client

@router.get("/", response_model=List[ClientResponse])
def get_clients(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all clients (admin only) or client for current user."""
    if current_user.role == UserRole.ADMIN:
        # Admin can see all clients
        clients = session.exec(select(Client)).all()
    else:
        # Regular users can only see their own client
        if not current_user.client_id:
            return []
        client = session.get(Client, current_user.client_id)
        clients = [client] if client else []
    
    return clients

@router.get("/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific client by ID."""
    client = session.get(Client, client_id)
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Check permissions
    if current_user.role != UserRole.ADMIN and current_user.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return client

@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: int,
    client_update: ClientUpdate,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update a client (admin only)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update clients"
        )
    
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Update fields
    update_data = client_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)
    
    client.updated_at = datetime.utcnow()
    session.add(client)
    session.commit()
    session.refresh(client)
    
    return client

@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a client (admin only)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete clients"
        )
    
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Cascade delete related data: calls, transcripts, insights, users, sales reps
    from app.models import Call, Transcript, Insights

    # Delete insights and transcripts linked to client's calls
    calls = session.exec(select(Call).where(Call.client_id == client_id)).all()
    call_ids = [c.id for c in calls]
    if call_ids:
        for t in session.exec(select(Transcript).where(Transcript.call_id.in_(call_ids))).all():
            session.delete(t)
        for ins in session.exec(select(Insights).where(Insights.call_id.in_(call_ids))).all():
            session.delete(ins)
        for c in calls:
            session.delete(c)

    # Delete users linked to this client
    for u in session.exec(select(User).where(User.client_id == client_id)).all():
        session.delete(u)

    # Delete sales reps linked to this client
    for r in session.exec(select(SalesRep).where(SalesRep.client_id == client_id)).all():
        session.delete(r)

    # Finally, delete client
    session.delete(client)
    session.commit()

# Sales Rep Management Endpoints

@router.post("/{client_id}/sales-reps", response_model=SalesRepResponse, status_code=status.HTTP_201_CREATED)
def create_sales_rep(
    client_id: int,
    sales_rep_data: SalesRepCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new sales rep for a client."""
    # Check permissions
    if current_user.role != UserRole.ADMIN and current_user.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Verify client exists
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Create sales rep
    sales_rep = SalesRep(
        client_id=client_id,
        name=sales_rep_data.name,
        email=sales_rep_data.email,
        phone=sales_rep_data.phone
    )
    
    session.add(sales_rep)
    session.commit()
    session.refresh(sales_rep)
    
    return sales_rep

@router.get("/{client_id}/sales-reps", response_model=List[SalesRepResponse])
def get_sales_reps(
    client_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all sales reps for a client."""
    # Check permissions
    if current_user.role != UserRole.ADMIN and current_user.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Verify client exists
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    sales_reps = session.exec(
        select(SalesRep).where(SalesRep.client_id == client_id)
    ).all()
    
    return sales_reps

@router.get("/{client_id}/sales-reps/{sales_rep_id}", response_model=SalesRepResponse)
def get_sales_rep(
    client_id: int,
    sales_rep_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific sales rep."""
    # Check permissions
    if current_user.role != UserRole.ADMIN and current_user.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    sales_rep = session.get(SalesRep, sales_rep_id)
    if not sales_rep or sales_rep.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sales rep not found"
        )
    
    return sales_rep

@router.put("/{client_id}/sales-reps/{sales_rep_id}", response_model=SalesRepResponse)
def update_sales_rep(
    client_id: int,
    sales_rep_id: int,
    sales_rep_update: SalesRepUpdate,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update a sales rep."""
    # Check permissions
    if current_user.role != UserRole.ADMIN and current_user.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    sales_rep = session.get(SalesRep, sales_rep_id)
    if not sales_rep or sales_rep.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sales rep not found"
        )
    
    # Update fields
    update_data = sales_rep_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(sales_rep, field, value)
    
    session.add(sales_rep)
    session.commit()
    session.refresh(sales_rep)
    
    return sales_rep

@router.delete("/{client_id}/sales-reps/{sales_rep_id}")
def delete_sales_rep(
    client_id: int,
    sales_rep_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a sales rep."""
    # Check permissions
    if current_user.role != UserRole.ADMIN and current_user.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    sales_rep = session.get(SalesRep, sales_rep_id)
    if not sales_rep or sales_rep.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sales rep not found"
        )
    
    # Store rep name before deletion for success message
    rep_name = sales_rep.name
    
    # Cascade delete: remove calls (and their transcripts/insights) for this rep
    from app.models import Call, Transcript, Insights
    calls = session.exec(select(Call).where(Call.sales_rep_id == sales_rep_id)).all()
    if calls:
        call_ids = [c.id for c in calls]
        for t in session.exec(select(Transcript).where(Transcript.call_id.in_(call_ids))).all():
            session.delete(t)
        for ins in session.exec(select(Insights).where(Insights.call_id.in_(call_ids))).all():
            session.delete(ins)
        for c in calls:
            session.delete(c)

    # Optionally delete linked login user (same email, same client, role REP)
    if sales_rep.email:
        for u in session.exec(
            select(User).where(
                User.client_id == client_id,
                User.email == sales_rep.email,
                User.role == UserRole.REP
            )
        ).all():
            session.delete(u)

    session.delete(sales_rep)
    session.commit()
    
    # Return success message with rep name
    return {
        "message": f"Sales rep '{rep_name}' deleted successfully",
        "rep_name": rep_name
    }

# Client Statistics Endpoints

@router.get("/{client_id}/stats")
def get_client_stats(
    client_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get statistics for a client."""
    # Check permissions
    if current_user.role != UserRole.ADMIN and current_user.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Verify client exists
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Get statistics
    from app.models import Call, Transcript, Insights
    
    # Count calls by status
    calls = session.exec(
        select(Call).where(Call.client_id == client_id)
    ).all()
    
    total_calls = len(calls)
    processed_calls = len([c for c in calls if c.status == "processed"])
    processing_calls = len([c for c in calls if c.status == "processing"])
    failed_calls = len([c for c in calls if c.status == "failed"])
    
    # Count sales reps
    sales_reps = session.exec(
        select(SalesRep).where(SalesRep.client_id == client_id)
    ).all()
    
    # Count users
    users = session.exec(
        select(User).where(User.client_id == client_id)
    ).all()
    
    # Average score
    scores = [c.score for c in calls if c.score is not None]
    avg_score = sum(scores) / len(scores) if scores else 0
    
    return {
        "client_id": client_id,
        "client_name": client.name,
        "total_calls": total_calls,
        "processed_calls": processed_calls,
        "processing_calls": processing_calls,
        "failed_calls": failed_calls,
        "total_sales_reps": len(sales_reps),
        "total_users": len(users),
        "average_score": round(avg_score, 2),
        "processing_schedule": client.processing_schedule,
        "status": client.status
    }
