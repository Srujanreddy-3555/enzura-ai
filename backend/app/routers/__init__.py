# Router imports for multi-tenant support
from .clients import router as clients_router
from .auth import router as auth_router
from .calls import router as calls_router
from .insights import router as insights_router
from .transcripts import router as transcripts_router
from .uploads import router as uploads_router
from .users import router as users_router
from .s3_monitoring import router as s3_monitoring_router

__all__ = [
    "clients_router",
    "auth_router", 
    "calls_router",
    "insights_router",
    "transcripts_router",
    "uploads_router",
    "users_router",
    "s3_monitoring_router"
]
