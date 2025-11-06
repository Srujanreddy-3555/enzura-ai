from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    CLIENT = "CLIENT"
    REP = "REP"

class CallStatus(str, Enum):
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"

class SentimentType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"

class UploadMethod(str, Enum):
    MANUAL = "MANUAL"
    S3_AUTO = "S3_AUTO"

# Multi-Tenant Models
class Client(SQLModel, table=True):
    __tablename__ = "client"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    s3_bucket_name: str
    s3_region: str = Field(default="us-east-1")
    aws_access_key: str
    aws_secret_key: str
    processing_schedule: str = Field(default="realtime")  # Default to 30-second scans for immediate processing
    timezone: str = Field(default="UTC")
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    users: List["User"] = Relationship(back_populates="client")
    calls: List["Call"] = Relationship(back_populates="client")
    sales_reps: List["SalesRep"] = Relationship(back_populates="client")

class SalesRep(SQLModel, table=True):
    __tablename__ = "sales_rep"
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="client.id")
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    client: Optional[Client] = Relationship(back_populates="sales_reps")
    calls: List["Call"] = Relationship(back_populates="sales_rep")

# User Model
class User(SQLModel, table=True):
    __tablename__ = "user"
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    name: str
    role: UserRole = Field(default=UserRole.REP)
    client_id: Optional[int] = Field(default=None, foreign_key="client.id")  # Multi-tenant support
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    client: Optional[Client] = Relationship(back_populates="users")  # Multi-tenant support
    calls: List["Call"] = Relationship(back_populates="user")

# Call Model
class Call(SQLModel, table=True):
    __tablename__ = "call"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    client_id: Optional[int] = Field(default=None, foreign_key="client.id")  # Multi-tenant support
    sales_rep_id: Optional[int] = Field(default=None, foreign_key="sales_rep.id")  # Sales rep tracking
    sales_rep_name: Optional[str] = None  # Sales rep name for easy access
    filename: str
    s3_url: str
    status: CallStatus = Field(default=CallStatus.PROCESSING)
    language: Optional[str] = Field(default=None)  # None = auto-detect, supports 100+ languages
    translate_to_english: bool = Field(default=False)  # If True, translate transcript to English
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    duration: Optional[int] = None  # in seconds
    score: Optional[int] = Field(default=None, ge=0, le=100)
    upload_method: UploadMethod = Field(default=UploadMethod.MANUAL)  # Track upload method
    
    # Relationships
    user: Optional[User] = Relationship(back_populates="calls")
    client: Optional[Client] = Relationship(back_populates="calls")  # Multi-tenant support
    sales_rep: Optional[SalesRep] = Relationship(back_populates="calls")  # Sales rep tracking
    transcript: Optional["Transcript"] = Relationship(back_populates="call")
    insights: Optional["Insights"] = Relationship(back_populates="call")

# Transcript Model
class Transcript(SQLModel, table=True):
    __tablename__ = "transcript"
    id: Optional[int] = Field(default=None, primary_key=True)
    call_id: int = Field(foreign_key="call.id")
    client_id: Optional[int] = Field(default=None, foreign_key="client.id")  # Multi-tenant support
    text: str
    language: Optional[str] = Field(default=None)  # None = auto-detect
    speaker_labels: Optional[str] = None  # JSON string
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    call: Optional[Call] = Relationship(back_populates="transcript")
    client: Optional[Client] = Relationship()  # Multi-tenant support

# Insights Model
class Insights(SQLModel, table=True):
    __tablename__ = "insights"
    id: Optional[int] = Field(default=None, primary_key=True)
    call_id: int = Field(foreign_key="call.id")
    client_id: Optional[int] = Field(default=None, foreign_key="client.id")  # Multi-tenant support
    summary: Optional[str] = None
    sentiment: Optional[SentimentType] = None
    key_topics: Optional[str] = None  # JSON string array
    satisfaction_score: Optional[int] = Field(default=None, ge=0, le=100)
    improvement_areas: Optional[str] = None  # JSON string array
    action_items: Optional[str] = None  # JSON string array
    overall_score: Optional[int] = Field(default=None, ge=0, le=100)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Advanced Analysis Fields - Phase 1 (High Impact)
    talk_time_ratio: Optional[float] = None  # Sales rep talk time vs customer (0.0-1.0)
    question_effectiveness: Optional[int] = Field(default=None, ge=0, le=100)  # Quality of questions asked
    objection_handling: Optional[str] = None  # How objections were handled
    closing_attempts: Optional[int] = None  # Number of closing attempts
    engagement_score: Optional[int] = Field(default=None, ge=0, le=100)  # Customer engagement level
    commitment_level: Optional[str] = None  # "High", "Medium", "Low"
    
    # Sales Performance Metrics
    bant_qualification: Optional[str] = None  # JSON string with BANT scores
    value_proposition_score: Optional[int] = Field(default=None, ge=0, le=100)
    trust_building_moments: Optional[str] = None  # JSON string array
    interest_indicators: Optional[str] = None  # JSON string array
    concern_indicators: Optional[str] = None  # JSON string array
    
    # Conversation Flow Analysis
    conversation_pace: Optional[str] = None  # "Fast", "Moderate", "Slow"
    interruption_count: Optional[int] = None
    silence_periods: Optional[int] = None
    
    # Predictive Analytics
    deal_probability: Optional[int] = Field(default=None, ge=0, le=100)
    follow_up_urgency: Optional[str] = None  # "High", "Medium", "Low"
    upsell_opportunities: Optional[str] = None  # JSON string array
    
    # Relationships
    call: Optional[Call] = Relationship(back_populates="insights")
    client: Optional[Client] = Relationship()  # Multi-tenant support

# Pydantic models for API requests/responses
class UserCreate(SQLModel):
    email: str
    password: str
    name: str
    role: UserRole = UserRole.REP

class UserResponse(SQLModel):
    id: int
    email: str
    name: str
    role: UserRole
    client_id: Optional[int] = None  # Multi-tenant support
    client_name: Optional[str] = None  # Client name for easy access
    created_at: datetime

class CallCreate(SQLModel):
    filename: str
    s3_url: str
    language: Optional[str] = None  # None = auto-detect (supports 100+ languages)
    translate_to_english: bool = False  # If True, translate transcript to English

class CallResponse(SQLModel):
    id: int
    filename: str
    s3_url: str
    status: CallStatus
    language: Optional[str] = None  # None = auto-detect
    translate_to_english: bool = False  # Whether transcript was translated to English
    upload_date: datetime
    duration: Optional[int] = None  # Duration in seconds - MUST be included in response
    score: Optional[int] = None
    sentiment: Optional[SentimentType] = None  # Sentiment from Insights
    client_id: Optional[int] = None
    sales_rep_id: Optional[int] = None
    sales_rep_name: Optional[str] = None
    upload_method: Optional[UploadMethod] = None
    
    class Config:
        # Ensure None values are included in JSON serialization
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
        # CRITICAL: Ensure all fields including None values are serialized
        # This ensures duration is ALWAYS in the JSON response
        json_schema_extra = {
            "example": {
                "id": 1,
                "filename": "call.mp3",
                "s3_url": "https://example.com/call.mp3",
                "status": "PROCESSED",
                "language": "en",
                "translate_to_english": False,
                "upload_date": "2024-01-01T00:00:00",
                "duration": 120,  # Always include duration field
                "score": 85,
                "sentiment": "POSITIVE",  # Always include sentiment field
                "client_id": 1,
                "sales_rep_id": None,
                "sales_rep_name": None,
                "upload_method": "MANUAL"
            }
        }

class CallUpdate(SQLModel):
    status: Optional[CallStatus] = None
    score: Optional[int] = Field(default=None, ge=0, le=100)
    duration: Optional[int] = None

class PaginatedCallsResponse(SQLModel):
    """Response model for paginated calls with total count"""
    calls: List[CallResponse]
    total: int
    skip: int
    limit: int

class TranscriptCreate(SQLModel):
    call_id: int
    text: str
    language: Optional[str] = None  # None = auto-detect
    speaker_labels: Optional[str] = None

class InsightsCreate(SQLModel):
    call_id: int
    summary: Optional[str] = None
    sentiment: Optional[SentimentType] = None
    key_topics: Optional[List[str]] = None
    satisfaction_score: Optional[int] = Field(default=None, ge=0, le=100)
    improvement_areas: Optional[List[str]] = None
    action_items: Optional[List[str]] = None
    overall_score: Optional[int] = Field(default=None, ge=0, le=100)
    
    # Advanced Analysis Fields - Phase 1 (High Impact)
    talk_time_ratio: Optional[float] = None
    question_effectiveness: Optional[int] = Field(default=None, ge=0, le=100)
    objection_handling: Optional[str] = None
    closing_attempts: Optional[int] = None
    engagement_score: Optional[int] = Field(default=None, ge=0, le=100)
    commitment_level: Optional[str] = None
    
    # Sales Performance Metrics
    bant_qualification: Optional[dict] = None  # BANT scores as dict
    value_proposition_score: Optional[int] = Field(default=None, ge=0, le=100)
    trust_building_moments: Optional[List[str]] = None
    interest_indicators: Optional[List[str]] = None
    concern_indicators: Optional[List[str]] = None
    
    # Conversation Flow Analysis
    conversation_pace: Optional[str] = None
    interruption_count: Optional[int] = None
    silence_periods: Optional[int] = None
    
    # Predictive Analytics
    deal_probability: Optional[int] = Field(default=None, ge=0, le=100)
    follow_up_urgency: Optional[str] = None
    upsell_opportunities: Optional[List[str]] = None

# Multi-Tenant Pydantic Models
class ClientCreate(SQLModel):
    name: str
    s3_bucket_name: str
    s3_region: str = "us-east-1"
    aws_access_key: str
    aws_secret_key: str
    processing_schedule: str = "realtime"  # Default to 30-second scans for immediate processing
    timezone: str = "UTC"

class ClientResponse(SQLModel):
    id: int
    name: str
    s3_bucket_name: str
    s3_region: str
    processing_schedule: str
    timezone: str
    status: str
    created_at: datetime

class ClientUpdate(SQLModel):
    name: Optional[str] = None
    s3_bucket_name: Optional[str] = None
    s3_region: Optional[str] = None
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    processing_schedule: Optional[str] = None
    timezone: Optional[str] = None
    status: Optional[str] = None

class SalesRepCreate(SQLModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None

class SalesRepResponse(SQLModel):
    id: int
    client_id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime

class SalesRepUpdate(SQLModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

# File Upload Models
class FileUploadResponse(BaseModel):
    call_id: int
    filename: str
    s3_url: str
    status: CallStatus
    message: str

class FileUploadProgress(BaseModel):
    filename: str
    progress: int  # 0-100
    status: str  # "uploading", "processing", "completed", "failed"
    message: Optional[str] = None

class FileValidationError(BaseModel):
    filename: str
    error: str
    details: Optional[str] = None
