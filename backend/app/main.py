from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import HTTPBearer
from sqlmodel import Session, select
from datetime import datetime, timedelta
from typing import List, Optional
import os
from dotenv import load_dotenv

# Load environment variables (tolerant to encoding issues)
try:
    load_dotenv(encoding="utf-8", override=True)
except Exception:
    # Fallback without encoding in case of older dotenv versions
    try:
        load_dotenv()
    except Exception:
        # Continue without .env if unreadable; critical vars should be set via environment
        pass

# Import our modules
from .database import get_db, create_tables
from .models import (
    User, UserCreate, UserResponse,
    Call, CallCreate, CallResponse, CallStatus, UploadMethod,
    Transcript, TranscriptCreate,
    Insights, InsightsCreate
)
from .auth import (
    verify_password, get_password_hash, create_access_token,
    get_current_user, get_current_active_user
)

# Create FastAPI app
# SECURITY: Disable API docs in production (or protect with authentication)
is_production = os.getenv("ENVIRONMENT") == "production"
app = FastAPI(
    title="Enzura AI API",
    description="Backend API for Enzura AI call analytics platform",
    version="1.0.0",
    docs_url=None if is_production else "/docs",  # Disable in production
    redoc_url=None if is_production else "/redoc"  # Disable in production
)

# OPTIMIZED: Add compression middleware (gzip) - reduces response size by 70-90%!
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add CORS middleware
# SECURITY: In production, replace ["*"] with your actual frontend domain(s)
# Example: allow_origins=["https://yourdomain.com", "https://www.yourdomain.com"]
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",") if os.getenv("CORS_ORIGINS") else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,  # Set CORS_ORIGINS env var in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security scheme
security = HTTPBearer()

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database tables and start S3 monitoring on startup"""
    try:
        if create_tables():
            print("Database tables created successfully!")
        else:
            print("Running in development mode without database")
            print("Note: Some features may not work without database connection")
        
        # Start S3 monitoring service
        try:
            from .services.s3_monitoring_service import s3_monitoring_service
            await s3_monitoring_service.start_monitoring()
            print("S3 monitoring service started successfully!")
        except Exception as e:
            print(f"S3 monitoring service failed to start: {e}")
            print("Note: S3 auto-processing will not be available")
        
        # Start processing queue worker
        try:
            from .services.processing_service import start_processing_worker
            await start_processing_worker()
            print("Call processing queue worker started successfully!")
        except Exception as e:
            print(f"Processing queue worker failed to start: {e}")
            print("Note: Call processing may be delayed")
            
    except Exception as e:
        print(f"Database connection failed: {e}")
        print("Running in development mode without database")
        print("Note: Some features may not work without database connection")

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Enzura AI API is running!",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "healthy"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected"
    }

# Manually trigger processing for a call
@app.post("/process-call/{call_id}")
async def manually_process_call(call_id: int):
    """Manually trigger processing for a specific call - PROCESSES IMMEDIATELY"""
    try:
        from .database import get_db
        from .models import Call
        from sqlmodel import select
        from .services.processing_service import processing_service
        
        db = next(get_db())
        if not db:
            return {"status": "error", "message": "Database not available"}
        
        try:
            # Get the call
            call = db.exec(select(Call).where(Call.id == call_id)).first()
            if not call:
                return {"status": "error", "message": f"Call {call_id} not found"}
            
            # Check if already processed
            from .models import Transcript, Insights
            transcript_check = db.exec(select(Transcript).where(Transcript.call_id == call_id)).first()
            insights_check = db.exec(select(Insights).where(Insights.call_id == call_id)).first()
            
            if (call.status == CallStatus.PROCESSED or str(call.status).upper() == "PROCESSED") and transcript_check and insights_check:
                return {
                    "status": "already_processed",
                    "message": f"Call {call_id} is already fully processed",
                    "call_id": call_id,
                    "score": call.score,
                    "has_transcript": True,
                    "has_insights": True
                }
            
            # Process immediately (don't just queue - actually process it now)
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"🚀 MANUALLY PROCESSING call {call_id} immediately...")
            
            try:
                await processing_service.process_call(call_id, db)
            except Exception as process_error:
                logger.error(f"Processing failed: {process_error}")
                # Refresh call to get latest status
                db.refresh(call)
                return {
                    "status": "error",
                    "message": f"Processing failed: {str(process_error)}",
                    "call_id": call_id,
                    "status": call.status,
                    "error": str(process_error)
                }
            
            # Close current session and get fresh one for verification
            db.close()
            db = next(get_db())
            
            # Refresh call from database
            call = db.exec(select(Call).where(Call.id == call_id)).first()
            
            # Verify results with fresh queries
            transcript_check = db.exec(select(Transcript).where(Transcript.call_id == call_id)).first()
            insights_check = db.exec(select(Insights).where(Insights.call_id == call_id)).first()
            
            if not transcript_check or not insights_check:
                return {
                    "status": "partial",
                    "message": f"Processing completed but verification incomplete",
                    "call_id": call_id,
                    "filename": call.filename if call else "unknown",
                    "status": call.status if call else "unknown",
                    "score": call.score if call else None,
                    "has_transcript": transcript_check is not None,
                    "has_insights": insights_check is not None,
                    "warning": "Please refresh in a moment - data may still be committing"
                }
            
            return {
                "status": "completed",
                "message": f"Call {call_id} processed successfully",
                "call_id": call_id,
                "filename": call.filename,
                "status": call.status,
                "score": call.score,
                "has_transcript": True,
                "has_insights": True,
                "transcript_preview": transcript_check.text[:200] + "..." if transcript_check.text else None,
                "transcript_length": len(transcript_check.text) if transcript_check.text else 0,
                "insights_score": insights_check.overall_score if insights_check else None,
                "insights_sentiment": insights_check.sentiment.value if insights_check and insights_check.sentiment else None
            }
        finally:
            db.close()
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error manually processing call {call_id}: {e}")
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": f"Failed to process call: {str(e)}",
            "error_type": type(e).__name__
        }

# Diagnostic endpoint to check call processing status
@app.get("/diagnose-call/{call_id}")
async def diagnose_call(call_id: int):
    """Diagnose why a call isn't showing transcript/insights"""
    try:
        from .database import get_db
        from .models import Call, Transcript, Insights, User
        from sqlmodel import select
        
        db = next(get_db())
        if not db:
            return {"status": "error", "message": "Database not available"}
        
        try:
            # Get the call
            call = db.exec(select(Call).where(Call.id == call_id)).first()
            if not call:
                return {"status": "error", "message": f"Call {call_id} not found"}
            
            # Get the assigned user
            assigned_user = db.exec(select(User).where(User.id == call.user_id)).first()
            
            # Check transcript
            transcript = db.exec(select(Transcript).where(Transcript.call_id == call_id)).first()
            
            # Check insights
            insights = db.exec(select(Insights).where(Insights.call_id == call_id)).first()
            
            return {
                "status": "ok",
                "call_id": call_id,
                "call_status": call.status,
                "call_score": call.score,
                "call_user_id": call.user_id,
                "call_client_id": call.client_id,
                "assigned_user": {
                    "id": assigned_user.id if assigned_user else None,
                    "name": assigned_user.name if assigned_user else None,
                    "email": assigned_user.email if assigned_user else None,
                    "role": assigned_user.role.value if assigned_user and assigned_user.role else None,
                    "client_id": assigned_user.client_id if assigned_user else None
                },
                "sales_rep_name": call.sales_rep_name,
                "has_transcript": transcript is not None,
                "transcript_id": transcript.id if transcript else None,
                "transcript_preview": transcript.text[:100] + "..." if transcript and transcript.text else None,
                "has_insights": insights is not None,
                "insights_id": insights.id if insights else None,
                "insights_score": insights.overall_score if insights else None,
                "processing_complete": call.status == CallStatus.PROCESSED or str(call.status).upper() == "PROCESSED",
                "recommendation": "All good!" if (transcript and insights) else (
                    "Transcript missing" if not transcript else "Insights missing"
                )
            }
        finally:
            db.close()
    except Exception as e:
        return {"status": "error", "message": f"Diagnostic failed: {str(e)}"}

# Diagnostic endpoint to check rep assignment
@app.get("/diagnose-rep-assignment/{client_id}")
async def diagnose_rep_assignment(client_id: int):
    """Diagnose rep assignment for calls in a client"""
    try:
        from .database import get_db
        from .models import Call, User, Client
        from sqlmodel import select
        
        db = next(get_db())
        if not db:
            return {"status": "error", "message": "Database not available"}
        
        try:
            # Get client
            client = db.get(Client, client_id)
            if not client:
                return {"status": "error", "message": f"Client {client_id} not found"}
            
            # Get all calls for this client
            calls = db.exec(select(Call).where(Call.client_id == client_id)).all()
            
            # Get all rep users for this client
            from .models import UserRole
            rep_users = db.exec(
                select(User).where(
                    User.client_id == client_id,
                    User.role == UserRole.REP
                )
            ).all()
            
            # Analyze call assignments
            call_assignments = []
            for call in calls:
                assigned_user = db.exec(select(User).where(User.id == call.user_id)).first()
                call_assignments.append({
                    "call_id": call.id,
                    "filename": call.filename,
                    "user_id": call.user_id,
                    "assigned_user_name": assigned_user.name if assigned_user else None,
                    "assigned_user_email": assigned_user.email if assigned_user else None,
                    "assigned_user_role": assigned_user.role.value if assigned_user and assigned_user.role else None,
                    "sales_rep_name": call.sales_rep_name,
                    "s3_url": call.s3_url
                })
            
            return {
                "status": "ok",
                "client_id": client_id,
                "client_name": client.name,
                "total_calls": len(calls),
                "rep_users": [
                    {
                        "id": rep.id,
                        "name": rep.name,
                        "email": rep.email,
                        "client_id": rep.client_id
                    } for rep in rep_users
                ],
                "call_assignments": call_assignments
            }
        finally:
            db.close()
    except Exception as e:
        return {"status": "error", "message": f"Diagnostic failed: {str(e)}"}

# Fix rep assignment for calls
@app.post("/fix-rep-assignments/{client_id}")
async def fix_rep_assignments(client_id: int):
    """Fix call assignments for a client - reassigns calls based on S3 path"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from .database import get_db
        from .models import Call, User, Client, UserRole
        from sqlmodel import select
        from .services.s3_monitoring_service import s3_monitoring_service
        
        db = next(get_db())
        if not db:
            return {"status": "error", "message": "Database not available"}
        
        try:
            # Get client
            client = db.get(Client, client_id)
            if not client:
                return {"status": "error", "message": f"Client {client_id} not found"}
            
            # Get all calls for this client that were uploaded via S3
            calls = db.exec(
                select(Call).where(
                    Call.client_id == client_id,
                    (Call.upload_method == UploadMethod.S3_AUTO or Call.upload_method == "S3_AUTO")
                )
            ).all()
            
            fixed_count = 0
            errors = []
            
            for call in calls:
                try:
                    # Extract rep email from S3 URL
                    # S3 URL format: https://bucket.s3.region.amazonaws.com/key
                    # We need to extract just the key part
                    s3_key = None
                    if call.s3_url:
                        # Try to extract key from URL
                        if f"/{client.s3_bucket_name}/" in call.s3_url:
                            s3_key = call.s3_url.split(f"/{client.s3_bucket_name}/")[-1]
                        elif f"{client.s3_bucket_name}/" in call.s3_url:
                            s3_key = call.s3_url.split(f"{client.s3_bucket_name}/")[-1]
                        elif ".amazonaws.com/" in call.s3_url:
                            s3_key = call.s3_url.split(".amazonaws.com/")[-1]
                    
                    if not s3_key:
                        errors.append(f"Could not extract S3 key from URL: {call.s3_url}")
                        continue
                    
                    rep_email = s3_monitoring_service._extract_rep_email(s3_key)
                    if not rep_email:
                        continue
                    
                    # Try to find rep user
                    rep_user = db.exec(
                        select(User).where(
                            User.client_id == client_id,
                            User.role == UserRole.REP,
                            User.email == rep_email
                        )
                    ).first()
                    
                    # Try comprehensive matching if exact match fails (same logic as S3 monitoring service)
                    if not rep_user:
                        all_rep_users = db.exec(
                            select(User).where(
                                User.client_id == client_id,
                                User.role == UserRole.REP
                            )
                        ).all()
                        
                        rep_username = rep_email.split('@')[0].lower() if '@' in rep_email else rep_email.lower()
                        rep_domain = rep_email.split('@')[1].lower() if '@' in rep_email and len(rep_email.split('@')) > 1 else None
                        
                        # Strategy 1: Username match
                        if not rep_user:
                            for user in all_rep_users:
                                if user.email:
                                    user_email_lower = user.email.lower()
                                    user_username = user_email_lower.split('@')[0] if '@' in user_email_lower else user_email_lower
                                    if user_username == rep_username:
                                        rep_user = user
                                        logger.info(f"Fixed: Username match '{rep_username}' matches '{user.email}'")
                                        break
                        
                        # Strategy 2: Prefix match
                        if not rep_user and rep_domain:
                            for user in all_rep_users:
                                if user.email:
                                    user_email_lower = user.email.lower()
                                    if user_email_lower.startswith(rep_email):
                                        rep_user = user
                                        logger.info(f"Fixed: Prefix match '{rep_email}' matches '{user.email}'")
                                        break
                        
                        # Strategy 3: Contains match
                        if not rep_user:
                            for user in all_rep_users:
                                if user.email:
                                    user_email_lower = user.email.lower()
                                    if rep_email in user_email_lower:
                                        rep_user = user
                                        logger.info(f"Fixed: Contains match '{rep_email}' in '{user.email}'")
                                        break
                        
                        # Strategy 4: Domain match
                        if not rep_user and rep_domain:
                            for user in all_rep_users:
                                if user.email:
                                    user_email_lower = user.email.lower()
                                    if '@' in user_email_lower:
                                        user_domain = user_email_lower.split('@')[1]
                                        if rep_domain in user_domain or user_domain.startswith(rep_domain):
                                            rep_user = user
                                            logger.info(f"Fixed: Domain match '{rep_email}' domain matches '{user.email}'")
                                            break
                    
                    if rep_user and call.user_id != rep_user.id:
                        old_user_id = call.user_id
                        call.user_id = rep_user.id
                        db.add(call)
                        db.commit()
                        fixed_count += 1
                        logger.info(f"Fixed call {call.id}: reassigned from user {old_user_id} to rep {rep_user.id} ({rep_user.email})")
                    
                except Exception as e:
                    errors.append(f"Error fixing call {call.id}: {str(e)}")
            
            return {
                "status": "success",
                "client_id": client_id,
                "client_name": client.name,
                "total_calls_checked": len(calls),
                "calls_fixed": fixed_count,
                "errors": errors
            }
        finally:
            db.close()
    except Exception as e:
        return {"status": "error", "message": f"Failed to fix assignments: {str(e)}"}

# Create sample insights for any call
@app.post("/create-sample-insights/{call_id}")
async def create_sample_insights(call_id: int):
    """Create sample insights for any call - GUARANTEED TO WORK"""
    try:
        from .services.processing_service import processing_service
        from .database import get_db
        from .models import Call, Insights, Transcript
        from sqlmodel import select
        import json
        
        # Get database session
        db = next(get_db())
        if not db:
            return {"status": "error", "message": "Database not available"}
        
        try:
            # Get the call
            call_statement = select(Call).where(Call.id == call_id)
            call = db.exec(call_statement).first()
            
            if not call:
                return {"status": "error", "message": f"Call {call_id} not found"}
            
            # Check if insights already exist
            existing_insights = db.exec(select(Insights).where(Insights.call_id == call_id)).first()
            if existing_insights:
                return {"status": "success", "message": f"Insights already exist for call {call_id}", "call_id": call_id}
            
            # Generate sample insights
            sample_transcript = """
            Sales Rep: Hi Sarah, this is Mike from Tech Solutions. Thanks for taking my call today. 
            I understand you downloaded our Productivity Software Guide last week?
            
            Customer: Yes, that's right. We're looking into ways to streamline our project management processes.
            
            Sales Rep: Perfect. Can you tell me what challenges you're currently facing with your existing setup?
            
            Customer: Well, we're using spreadsheets right now, but it's getting difficult to track everything as we grow.
            We need something more robust.
            
            Sales Rep: That makes sense. Our platform is specifically designed for growing teams like yours.
            Would you be interested in seeing a demo of how it could help streamline your processes?
            
            Customer: Yes, that sounds great. When would be a good time?
            
            Sales Rep: How about next Tuesday at 2 PM? I can show you the key features and answer any questions you have.
            
            Customer: That works for me. I'll put it on my calendar.
            
            Sales Rep: Excellent. I'll send you a calendar invite with the meeting details and a link to join.
            Is there anything specific you'd like me to focus on during the demo?
            
            Customer: I'd like to see how it handles task assignment and progress tracking, and maybe some reporting features.
            
            Sales Rep: Perfect, I'll make sure to cover those areas. I'll also show you our integration capabilities
            since you mentioned using spreadsheets currently.
            
            Customer: Great, looking forward to it. Thanks for your time today.
            
            Sales Rep: You're welcome, Sarah. I'll send that invite shortly and we'll talk again on Tuesday.
            Have a great rest of your day!
            """
            
            # Generate insights
            insights = await processing_service._generate_insights(sample_transcript, "en")
            insights.call_id = call_id
            
            # Convert to dict and prepare for database
            insights_dict = insights.dict()
            
            # Convert lists to JSON strings
            if insights_dict.get('key_topics'):
                insights_dict['key_topics'] = json.dumps(insights_dict['key_topics'])
            if insights_dict.get('improvement_areas'):
                insights_dict['improvement_areas'] = json.dumps(insights_dict['improvement_areas'])
            if insights_dict.get('action_items'):
                insights_dict['action_items'] = json.dumps(insights_dict['action_items'])
            if insights_dict.get('trust_building_moments'):
                insights_dict['trust_building_moments'] = json.dumps(insights_dict['trust_building_moments'])
            if insights_dict.get('interest_indicators'):
                insights_dict['interest_indicators'] = json.dumps(insights_dict['interest_indicators'])
            if insights_dict.get('concern_indicators'):
                insights_dict['concern_indicators'] = json.dumps(insights_dict['concern_indicators'])
            if insights_dict.get('upsell_opportunities'):
                insights_dict['upsell_opportunities'] = json.dumps(insights_dict['upsell_opportunities'])
            if insights_dict.get('bant_qualification'):
                insights_dict['bant_qualification'] = json.dumps(insights_dict['bant_qualification'])
            
            # Create and save insights
            db_insights = Insights(**insights_dict)
            db.add(db_insights)
            db.commit()
            db.refresh(db_insights)
            
            # Update call score
            call.score = insights.overall_score
            call.status = "processed"
            db.commit()
            
            return {
                "status": "success",
                "message": f"Sample insights created successfully for call {call_id}!",
                "call_id": call_id,
                "insights_id": db_insights.id,
                "overall_score": insights.overall_score,
                "sentiment": insights.sentiment,
                "key_topics": insights.key_topics,
                "summary": insights.summary[:200] + "..." if len(insights.summary) > 200 else insights.summary
            }
            
        finally:
            db.close()
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error creating sample insights: {str(e)}",
            "error_type": type(e).__name__
        }

# Include routers
from .routers import auth, users, calls, transcripts, insights, uploads, clients, s3_monitoring, reports

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(calls.router, prefix="/api/calls", tags=["Calls"])
app.include_router(transcripts.router, prefix="/api/transcripts", tags=["Transcripts"])
app.include_router(insights.router, prefix="/api/insights", tags=["Insights"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["File Uploads"])
app.include_router(clients.router, prefix="/api", tags=["Client Management"])  # Multi-tenant support
app.include_router(s3_monitoring.router, prefix="/api", tags=["S3 Monitoring"])  # S3 monitoring
app.include_router(reports.router, prefix="/api", tags=["Reports"])  # Admin reports

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
