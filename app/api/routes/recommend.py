"""
Recommend endpoint - Find relevant conversations/sessions for a query.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_postgres, get_neo4j, get_current_user_id, get_config
from app.db.postgres import PostgresDB
from app.db.neo4j import Neo4jDB
from app.config import Settings
from app.models.requests import RecommendRequest
from app.models.responses import (
    RecommendResponse, 
    RecommendationItem, 
    ScoreBreakdown,
    QueryAnalysis
)
from app.services.recommendation import get_recommendation_service


router = APIRouter()


@router.post("/recommend", response_model=RecommendResponse)
async def get_recommendations(
    request: RecommendRequest,
    user_id: str = Depends(get_current_user_id),
    postgres: PostgresDB = Depends(get_postgres),
    neo4j: Neo4jDB = Depends(get_neo4j),
    config: Settings = Depends(get_config)
):
    """
    Get recommendations for relevant conversations/sessions based on a query.
    
    This endpoint analyzes your query and finds the most relevant past
    conversations and sessions that could provide context.
    
    **Use Cases:**
    - Before starting a new conversation, check if there's relevant context
    - Find which session to continue when switching LLMs
    - Discover related past discussions
    
    **Scoring:**
    The recommendations are scored based on:
    - **Relevance (60%)**: Semantic similarity to your query
    - **Recency (25%)**: How recently the conversation/session was active
    - **Quality (15%)**: Richness of content (summaries, topics, etc.)
    
    **Auto-Selection:**
    If one recommendation has a very high score (>0.85) AND is clearly
    better than others (margin >0.20), it will be auto-selected.
    """
    try:
        # Get recommendation service
        rec_service = await get_recommendation_service(postgres, neo4j, config)
        
        # Get recommendations
        result = await rec_service.recommend(
            user_id=user_id,
            query=request.query,
            include_sessions=request.include_sessions,
            include_conversations=request.include_conversations,
            limit=request.limit
        )
        
        # Convert to response models
        recommendations = []
        for rec in result["recommendations"]:
            recommendations.append(RecommendationItem(
                id=rec["id"],
                type=rec["type"],
                name=rec["name"],
                summary=rec.get("summary"),
                source=rec.get("source"),
                topics=rec.get("topics", []),
                entities=rec.get("entities", []),
                score=ScoreBreakdown(
                    relevance=rec["score"]["relevance"],
                    recency=rec["score"]["recency"],
                    quality=rec["score"]["quality"],
                    final=rec["score"]["final"]
                ),
                auto_select=bool(rec.get("auto_select")),
                conversation_count=rec.get("conversation_count", 1),
                last_activity=rec.get("last_activity")
            ))
        
        # Auto-selected item
        auto_selected = None
        if result.get("auto_selected"):
            auto = result["auto_selected"]
            auto_selected = RecommendationItem(
                id=auto["id"],
                type=auto["type"],
                name=auto["name"],
                summary=auto.get("summary"),
                source=auto.get("source"),
                topics=auto.get("topics", []),
                entities=auto.get("entities", []),
                score=ScoreBreakdown(
                    relevance=auto["score"]["relevance"],
                    recency=auto["score"]["recency"],
                    quality=auto["score"]["quality"],
                    final=auto["score"]["final"]
                ),
                auto_select=True,
                conversation_count=auto.get("conversation_count", 1),
                last_activity=auto.get("last_activity")
            )
        
        # Query analysis
        query_analysis = QueryAnalysis(
            topics=result.get("query_analysis", {}).get("topics", []),
            entities=result.get("query_analysis", {}).get("entities", [])
        )
        
        return RecommendResponse(
            recommendations=recommendations,
            auto_selected=auto_selected,
            query_analysis=query_analysis
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "RECOMMENDATION_FAILED",
                    "message": f"Failed to get recommendations: {str(e)}"
                }
            }
        )
