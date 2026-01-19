"""
Knowledge API routes.
Manage extracted knowledge: verify, correct, delete.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel, Field

from app.api.dependencies import get_neo4j, get_current_user_id
from app.db.neo4j import Neo4jDB


router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class UpdateKnowledgeRequest(BaseModel):
    """Request to update a knowledge relationship."""
    status: Optional[str] = Field(None, description="New status: decided, exploring, rejected")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence 0.0-1.0")
    reason: Optional[str] = Field(None, description="Updated reason")


class VerifyKnowledgeRequest(BaseModel):
    """Request to verify extracted knowledge."""
    is_correct: bool = Field(..., description="Is this knowledge correct?")


class KnowledgeItem(BaseModel):
    """A piece of extracted knowledge."""
    id: str
    relationship_type: str
    source: Optional[str] = "User"
    target: str
    status: Optional[str] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None
    verified: Optional[bool] = None
    platform: Optional[str] = None
    created_at: Optional[str] = None


class ContradictionItem(BaseModel):
    """A detected contradiction."""
    old_id: str
    old_decision: Optional[str] = None
    old_date: Optional[str] = None
    old_reason: Optional[str] = None
    new_id: str
    new_decision: Optional[str] = None
    new_date: Optional[str] = None
    new_reason: Optional[str] = None
    category: Optional[str] = None
    conflict_type: str
    target: Optional[str] = None


class DecisionHistoryItem(BaseModel):
    """A single item in decision history."""
    id: str
    action: str
    status: Optional[str] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None
    source: Optional[str] = None
    date: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/unverified", response_model=List[KnowledgeItem])
async def get_unverified_knowledge(
    limit: int = 20,
    user_id: str = Depends(get_current_user_id),
    neo4j: Neo4jDB = Depends(get_neo4j)
):
    """
    Get extracted knowledge that hasn't been verified.
    
    Returns knowledge sorted by confidence (lowest first) so users
    can verify uncertain extractions first.
    """
    if not neo4j or not neo4j.driver:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "NEO4J_UNAVAILABLE", "message": "Knowledge layer not available"}}
        )
    
    items = await neo4j.get_unverified_knowledge(user_id, limit)
    return [
        KnowledgeItem(
            id=item["id"],
            relationship_type=item["relationship_type"],
            target=item["target"],
            status=item.get("status"),
            confidence=item.get("confidence"),
            reason=item.get("reason"),
            platform=item.get("source"),
            created_at=str(item["created_at"]) if item.get("created_at") else None
        )
        for item in items
    ]


@router.get("/contradictions", response_model=List[ContradictionItem])
async def get_contradictions(
    user_id: str = Depends(get_current_user_id),
    neo4j: Neo4jDB = Depends(get_neo4j)
):
    """
    Detect contradictory decisions.
    
    Returns pairs of decisions that might conflict, such as:
    - Choosing PostgreSQL, then later choosing MySQL
    - Rejecting something, then later choosing it
    """
    if not neo4j or not neo4j.driver:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "NEO4J_UNAVAILABLE", "message": "Knowledge layer not available"}}
        )
    
    conflicts = await neo4j.detect_contradictions(user_id)
    return [
        ContradictionItem(
            old_id=c["old_id"],
            old_decision=c.get("old_decision"),
            old_date=str(c["old_date"]) if c.get("old_date") else None,
            old_reason=c.get("old_reason"),
            new_id=c["new_id"],
            new_decision=c.get("new_decision"),
            new_date=str(c["new_date"]) if c.get("new_date") else None,
            new_reason=c.get("new_reason"),
            category=c.get("category"),
            conflict_type=c["conflict_type"],
            target=c.get("target")
        )
        for c in conflicts
    ]


@router.get("/history/{entity_name}", response_model=List[DecisionHistoryItem])
async def get_decision_history(
    entity_name: str,
    user_id: str = Depends(get_current_user_id),
    neo4j: Neo4jDB = Depends(get_neo4j)
):
    """
    Get the history of decisions about a specific entity.
    
    Shows how your opinion/decision about something changed over time.
    """
    if not neo4j or not neo4j.driver:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "NEO4J_UNAVAILABLE", "message": "Knowledge layer not available"}}
        )
    
    history = await neo4j.get_decision_history(user_id, entity_name)
    return [
        DecisionHistoryItem(
            id=h["id"],
            action=h["action"],
            status=h.get("status"),
            confidence=h.get("confidence"),
            reason=h.get("reason"),
            source=h.get("source"),
            date=str(h["date"]) if h.get("date") else None
        )
        for h in history
    ]


@router.get("/{relationship_id}", response_model=KnowledgeItem)
async def get_knowledge(
    relationship_id: str,
    user_id: str = Depends(get_current_user_id),
    neo4j: Neo4jDB = Depends(get_neo4j)
):
    """Get a specific knowledge relationship."""
    if not neo4j or not neo4j.driver:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "NEO4J_UNAVAILABLE", "message": "Knowledge layer not available"}}
        )
    
    item = await neo4j.get_relationship_by_id(relationship_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Knowledge not found"}}
        )
    
    return KnowledgeItem(
        id=item["id"],
        relationship_type=item["relationship_type"],
        source=item.get("source", "User"),
        target=item["target"],
        status=item.get("status"),
        confidence=item.get("confidence"),
        reason=item.get("reason"),
        verified=item.get("verified"),
        platform=item.get("platform"),
        created_at=str(item["created_at"]) if item.get("created_at") else None
    )


@router.patch("/{relationship_id}", response_model=KnowledgeItem)
async def update_knowledge(
    relationship_id: str,
    request: UpdateKnowledgeRequest,
    user_id: str = Depends(get_current_user_id),
    neo4j: Neo4jDB = Depends(get_neo4j)
):
    """
    Update a knowledge relationship.
    
    Use this to correct extraction errors:
    - Change status from "decided" to "exploring" if it was wrong
    - Adjust confidence level
    - Update the reason
    """
    if not neo4j or not neo4j.driver:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "NEO4J_UNAVAILABLE", "message": "Knowledge layer not available"}}
        )
    
    # Validate status if provided
    if request.status and request.status not in ["decided", "exploring", "rejected", "preference"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_STATUS", "message": "Status must be: decided, exploring, rejected, or preference"}}
        )
    
    result = await neo4j.update_relationship(
        user_id=user_id,
        relationship_id=relationship_id,
        status=request.status,
        confidence=request.confidence,
        reason=request.reason
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Knowledge not found"}}
        )
    
    return KnowledgeItem(
        id=result["id"],
        relationship_type=result["type"],
        target="",  # Not returned from update
        status=result.get("status"),
        confidence=result.get("confidence"),
        reason=result.get("reason"),
        verified=result.get("verified")
    )


@router.post("/{relationship_id}/verify")
async def verify_knowledge(
    relationship_id: str,
    request: VerifyKnowledgeRequest,
    user_id: str = Depends(get_current_user_id),
    neo4j: Neo4jDB = Depends(get_neo4j)
):
    """
    Verify or mark knowledge as incorrect.
    
    - is_correct=true: 
      - Marks as verified (won't show in unverified list)
      - Boosts confidence to 0.95
      - Changes status to "decided"
      
    - is_correct=false: 
      - Marks as incorrect (for review/deletion)
      - Drops confidence to 0.1
    """
    if not neo4j or not neo4j.driver:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "NEO4J_UNAVAILABLE", "message": "Knowledge layer not available"}}
        )
    
    result = await neo4j.verify_relationship(user_id, relationship_id, request.is_correct)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Knowledge not found"}}
        )
    
    if request.is_correct:
        return {
            "id": result["id"],
            "verified": result.get("verified"),
            "confidence": result.get("confidence"),
            "status": result.get("status"),
            "message": "✅ Knowledge verified and confirmed as a decision"
        }
    else:
        return {
            "id": result["id"],
            "verified": False,
            "marked_incorrect": result.get("marked_incorrect", False),
            "message": "❌ Knowledge marked as incorrect - you can delete it or update it"
        }


@router.post("/{relationship_id}/mark-exploring")
async def mark_as_exploring(
    relationship_id: str,
    user_id: str = Depends(get_current_user_id),
    neo4j: Neo4jDB = Depends(get_neo4j)
):
    """
    Quick action: Mark knowledge as "exploring" (not a decision).
    
    Use when the system incorrectly marked something as a decision
    but you were just considering it.
    
    This will:
    - Change status to "exploring"
    - Lower confidence to 0.4
    - Mark as verified (you confirmed this status)
    """
    if not neo4j or not neo4j.driver:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "NEO4J_UNAVAILABLE", "message": "Knowledge layer not available"}}
        )
    
    result = await neo4j.update_relationship(
        user_id=user_id,
        relationship_id=relationship_id,
        status="exploring",
        confidence=0.4,
        verified=True
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Knowledge not found"}}
        )
    
    return {
        "id": result["id"],
        "status": "exploring",
        "confidence": 0.4,
        "verified": True,
        "message": "🔍 Marked as 'exploring' - will show as being considered, not a decision"
    }


@router.post("/{relationship_id}/mark-rejected")
async def mark_as_rejected(
    relationship_id: str,
    user_id: str = Depends(get_current_user_id),
    neo4j: Neo4jDB = Depends(get_neo4j)
):
    """
    Quick action: Mark knowledge as "rejected".
    
    Use when you explicitly decided NOT to use something.
    
    This will:
    - Change status to "rejected"
    - Keep confidence high (you're sure about rejecting)
    - Mark as verified
    """
    if not neo4j or not neo4j.driver:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "NEO4J_UNAVAILABLE", "message": "Knowledge layer not available"}}
        )
    
    result = await neo4j.update_relationship(
        user_id=user_id,
        relationship_id=relationship_id,
        status="rejected",
        confidence=0.9,
        verified=True
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Knowledge not found"}}
        )
    
    return {
        "id": result["id"],
        "status": "rejected",
        "confidence": 0.9,
        "verified": True,
        "message": "❌ Marked as 'rejected' - will show in rejected options"
    }


@router.delete("/{relationship_id}")
async def delete_knowledge(
    relationship_id: str,
    user_id: str = Depends(get_current_user_id),
    neo4j: Neo4jDB = Depends(get_neo4j)
):
    """
    Delete a knowledge relationship.
    
    Use this to completely remove incorrect extractions.
    """
    if not neo4j or not neo4j.driver:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "NEO4J_UNAVAILABLE", "message": "Knowledge layer not available"}}
        )
    
    deleted = await neo4j.delete_relationship(user_id, relationship_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Knowledge not found"}}
        )
    
    return {"status": "deleted", "id": relationship_id}
