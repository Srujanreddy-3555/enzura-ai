from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Dict, Optional
import json
import logging

from ..database import get_db
from ..auth import get_current_active_user
from ..models import User, Insights, UserRole, Call, Transcript

router = APIRouter(tags=["insights"])  # No prefix - main.py adds /api/insights
logger = logging.getLogger(__name__)

@router.get("/batch", response_model=Dict[int, dict])
async def get_batch_insights(
    call_ids: str,  # Comma-separated call IDs
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get insights for multiple calls in a single request (batch API)
    This solves the N+1 query problem when fetching insights for many calls
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    try:
        # Parse call IDs
        call_id_list = [int(id.strip()) for id in call_ids.split(',') if id.strip().isdigit()]
        
        if not call_id_list:
            return {}
        
        # Fetch all insights in one query
        statement = select(Insights).where(Insights.call_id.in_(call_id_list))
        insights = db.exec(statement).all()
        
        # Build result dictionary with ALL fields
        result = {}
        
        def parse_json_field(field_value):
            """Parse JSON string field back to object/list"""
            if field_value is None:
                return None
            if isinstance(field_value, str):
                try:
                    return json.loads(field_value)
                except (json.JSONDecodeError, TypeError):
                    return field_value
            return field_value
        
        for insight in insights:
            # Convert to dict, handling JSON fields - include ALL fields
            # Convert enum to string value for JSON serialization
            sentiment_value = insight.sentiment.value if hasattr(insight.sentiment, 'value') else str(insight.sentiment)
            
            insight_dict = {
                "call_id": insight.call_id,
                "client_id": insight.client_id,
                "sentiment": sentiment_value,
                "overall_score": insight.overall_score,
                "summary": insight.summary,
                "key_topics": parse_json_field(insight.key_topics),
                "improvement_areas": parse_json_field(insight.improvement_areas),
                "action_items": parse_json_field(insight.action_items),
                # Performance Metrics
                "talk_time_ratio": insight.talk_time_ratio,
                "question_effectiveness": insight.question_effectiveness,
                "objection_handling": insight.objection_handling,
                "closing_attempts": insight.closing_attempts,
                "engagement_score": insight.engagement_score,
                "commitment_level": insight.commitment_level,
                # BANT Qualification
                "bant_qualification": parse_json_field(insight.bant_qualification),
                # Sales Performance
                "value_proposition_score": insight.value_proposition_score,
                "trust_building_moments": parse_json_field(insight.trust_building_moments),
                "interest_indicators": parse_json_field(insight.interest_indicators),
                "concern_indicators": parse_json_field(insight.concern_indicators),
                # Conversation Flow
                "conversation_pace": insight.conversation_pace,
                "interruption_count": insight.interruption_count,
                "silence_periods": insight.silence_periods,
                # Predictive Analytics
                "deal_probability": insight.deal_probability,
                "follow_up_urgency": insight.follow_up_urgency,
                "upsell_opportunities": parse_json_field(insight.upsell_opportunities),
                # Legacy fields
                "satisfaction_score": insight.satisfaction_score,
            }
            result[insight.call_id] = insight_dict
        
        return result
        
    except Exception as e:
        logger.error(f"Error in batch insights: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch batch insights: {str(e)}"
        )

@router.get("/call/{call_id}")
async def get_insight_by_call_id(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get insights for a specific call (with multi-tenant access control)"""
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    # Build query based on user role and client (multi-tenant access control)
    if current_user.role == UserRole.ADMIN:
        statement = select(Insights).where(Insights.call_id == call_id)
    elif current_user.role == UserRole.CLIENT:
        if current_user.client_id:
            # Client can see insights for all calls in their client
            statement = select(Insights).where(
                Insights.call_id == call_id,
                Insights.client_id == current_user.client_id
            )
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    else:  # REP
        # Rep can only see insights for their own calls
        # First check if the call belongs to this rep
        call_statement = select(Call).where(
            Call.id == call_id,
            Call.user_id == current_user.id,
            Call.client_id == current_user.client_id  # Ensure client_id is also matched
        )
        user_call = db.exec(call_statement).first()
        if not user_call:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        statement = select(Insights).where(Insights.call_id == call_id)
    
    # Fetch insights
    insights = db.exec(statement).first()
    
    logger.info(f"🔍 Fetching insights for call {call_id}, user: {current_user.email}, role: {current_user.role}")
    logger.info(f"🔍 Insights found: {insights is not None}")
    
    if not insights:
        logger.warning(f"⚠️ No insights found for call {call_id}")
        # Check if transcript exists (to determine if processing is needed)
        transcript = db.exec(select(Transcript).where(Transcript.call_id == call_id)).first()
        
        if not transcript:
            # No transcript, needs processing
            from ..services.processing_service import enqueue_call_for_processing
            import asyncio
            asyncio.create_task(enqueue_call_for_processing(call_id))
            raise HTTPException(
                status_code=status.HTTP_202_ACCEPTED,
                detail="Insights are being generated. Please check again in a moment."
            )
        else:
            # Transcript exists but no insights - try to create them
            try:
                from ..services.processing_service import ProcessingService
                processing_service = ProcessingService()
                # Trigger insights generation
                import asyncio
                asyncio.create_task(enqueue_call_for_processing(call_id))
                raise HTTPException(
                    status_code=status.HTTP_202_ACCEPTED,
                    detail="Insights are being generated. Please check again in a moment."
                )
            except Exception as e:
                logger.error(f"Error creating missing insights for call {call_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Unable to generate insights for this call"
                )
    
    # Return ALL insights fields - CRITICAL for frontend to display all analysis sections
    # Parse JSON strings back to objects for frontend consumption
    def parse_json_field(field_value):
        """Parse JSON string field back to object/list"""
        if field_value is None:
            return None
        if isinstance(field_value, str):
            try:
                return json.loads(field_value)
            except (json.JSONDecodeError, TypeError):
                return field_value
        return field_value
    
    # Log insights data for debugging
    logger.info(f"✅ Returning insights for call {call_id}")
    logger.info(f"   - Overall Score: {insights.overall_score}")
    logger.info(f"   - Sentiment: {insights.sentiment}")
    logger.info(f"   - Sentiment type: {type(insights.sentiment)}")
    
    try:
        # Convert enum to string value for JSON serialization - SAFE VERSION
        if hasattr(insights.sentiment, 'value'):
            sentiment_value = insights.sentiment.value
        elif isinstance(insights.sentiment, str):
            sentiment_value = insights.sentiment
        else:
            sentiment_value = str(insights.sentiment)
        
        logger.info(f"   - Sentiment value (converted): {sentiment_value}")
        
        # Build result dictionary with error handling for each field
        result = {}
        
        try:
            result["call_id"] = insights.call_id
            result["client_id"] = insights.client_id
            result["sentiment"] = sentiment_value
            result["overall_score"] = insights.overall_score
            result["summary"] = insights.summary
            result["key_topics"] = parse_json_field(insights.key_topics)
            result["improvement_areas"] = parse_json_field(insights.improvement_areas)
            result["action_items"] = parse_json_field(insights.action_items)
            
            # Performance Metrics
            result["talk_time_ratio"] = insights.talk_time_ratio
            result["question_effectiveness"] = insights.question_effectiveness
            result["objection_handling"] = insights.objection_handling
            result["closing_attempts"] = insights.closing_attempts
            result["engagement_score"] = insights.engagement_score
            result["commitment_level"] = insights.commitment_level
            
            # BANT Qualification
            result["bant_qualification"] = parse_json_field(insights.bant_qualification)
            
            # Sales Performance
            result["value_proposition_score"] = insights.value_proposition_score
            result["trust_building_moments"] = parse_json_field(insights.trust_building_moments)
            result["interest_indicators"] = parse_json_field(insights.interest_indicators)
            result["concern_indicators"] = parse_json_field(insights.concern_indicators)
            
            # Conversation Flow
            result["conversation_pace"] = insights.conversation_pace
            result["interruption_count"] = insights.interruption_count
            result["silence_periods"] = insights.silence_periods
            
            # Predictive Analytics
            result["deal_probability"] = insights.deal_probability
            result["follow_up_urgency"] = insights.follow_up_urgency
            result["upsell_opportunities"] = parse_json_field(insights.upsell_opportunities)
            
            # Legacy fields
            result["satisfaction_score"] = insights.satisfaction_score
            
        except Exception as field_error:
            logger.error(f"❌ Error building result dict for call {call_id}: {field_error}")
            logger.error(f"   Error type: {type(field_error).__name__}")
            import traceback
            logger.error(traceback.format_exc())
            raise
        
        logger.info(f"✅ Successfully built result dict with {len(result)} fields")
        logger.info(f"✅ Returning insights for call {call_id}")
        return result
        
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR in insights endpoint for call {call_id}: {e}")
        logger.error(f"   Error type: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing insights: {str(e)}"
        )
