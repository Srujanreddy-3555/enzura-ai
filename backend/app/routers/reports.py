from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Dict, Any

from ..database import get_db
from ..models import User, UserRole, Client, Call, Insights
from ..auth import get_current_active_user

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/client/{client_id}/rep-performance")
async def get_rep_performance(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Admin-only: Per-rep performance (total calls, avg overall score) for a client."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not available")

    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    # Aggregate per rep
    # Using raw SQL via session.exec for convenience
    query = (
        """
        SELECT u.id as user_id,
               u.name as rep_name,
               u.email as rep_email,
               COUNT(c.id) AS total_calls,
               COALESCE(AVG(i.overall_score), 0) AS avg_overall_score
        FROM "user" u
        JOIN call c ON c.user_id = u.id AND c.client_id = :client_id
        LEFT JOIN insights i ON i.call_id = c.id
        WHERE u.client_id = :client_id AND u.role = 'rep'
        GROUP BY u.id, u.name, u.email
        ORDER BY avg_overall_score DESC NULLS LAST, total_calls DESC
        """
    )

    rows = db.exec(query, {"client_id": client_id}).all()
    results = [
        {
            "user_id": r.user_id,
            "rep_name": r.rep_name,
            "rep_email": r.rep_email,
            "total_calls": int(r.total_calls) if r.total_calls is not None else 0,
            "avg_overall_score": int(r.avg_overall_score) if r.avg_overall_score is not None else 0,
        }
        for r in rows
    ]

    return {"client_id": client_id, "results": results}


