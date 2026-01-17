"""
Memories endpoints - View and manage extracted knowledge.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional

from app.api.dependencies import get_neo4j, get_current_user_id
from app.db.neo4j import Neo4jDB
from app.models.responses import MemoriesListResponse, MemoryItem, DeleteResponse


router = APIRouter()


@router.get("", response_model=MemoriesListResponse)
async def list_memories(
    memory_type: Optional[str] = Query(None, description="Filter by type: decision, fact, preference"),
    limit: int = Query(50, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    neo4j: Neo4jDB = Depends(get_neo4j)
):
    """
    List all extracted memories for the current user.
    
    Memories include:
    - Decisions: Things the user decided or chose
    - Facts: Factual information about the user or their projects
    - Preferences: Things the user likes or prefers
    """
    
    try:
        memories = []
        
        # Get decisions
        if memory_type is None or memory_type == "decision":
            decisions = await neo4j.get_decisions(user_id, limit=limit)
            for d in decisions:
                memories.append(MemoryItem(
                    id=d.get("id", ""),
                    type="decision",
                    content=d.get("decision", ""),
                    metadata={
                        "reason": d.get("reason"),
                        "target": d.get("target")
                    },
                    source=d.get("source"),
                    date=d.get("date")
                ))
        
        # Get facts
        if memory_type is None or memory_type == "fact":
            facts = await neo4j.get_current_facts(user_id, limit=limit)
            for f in facts:
                memories.append(MemoryItem(
                    id=f.get("id", ""),
                    type="fact",
                    content=f"{f.get('subject', '')} {f.get('predicate', '')} {f.get('object', '')}",
                    metadata={
                        "subject": f.get("subject"),
                        "predicate": f.get("predicate"),
                        "object": f.get("object")
                    },
                    date=f.get("since")
                ))
        
        # Get preferences
        if memory_type is None or memory_type == "preference":
            preferences = await neo4j.get_preferences(user_id, limit=limit)
            for p in preferences:
                memories.append(MemoryItem(
                    id=p.get("id", ""),
                    type="preference",
                    content=f"Prefers {p.get('target', '')}",
                    metadata={
                        "reason": p.get("reason"),
                        "strength": p.get("strength")
                    }
                ))
        
        return MemoriesListResponse(
            memories=memories,
            total=len(memories)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "LIST_MEMORIES_FAILED",
                    "message": f"Failed to list memories: {str(e)}"
                }
            }
        )


@router.delete("/{memory_id}", response_model=DeleteResponse)
async def delete_memory(
    memory_id: str,
    user_id: str = Depends(get_current_user_id),
    neo4j: Neo4jDB = Depends(get_neo4j)
):
    """
    Delete a specific memory/relationship from the knowledge graph.
    """
    
    try:
        deleted = await neo4j.delete_relationship(
            user_id=user_id,
            relationship_id=memory_id
        )
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "MEMORY_NOT_FOUND",
                        "message": "Memory not found or already deleted"
                    }
                }
            )
        
        return DeleteResponse(
            status="deleted",
            id=memory_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "DELETE_MEMORY_FAILED",
                    "message": f"Failed to delete memory: {str(e)}"
                }
            }
        )


@router.delete("", response_model=DeleteResponse)
async def delete_all_memories(
    user_id: str = Depends(get_current_user_id),
    neo4j: Neo4jDB = Depends(get_neo4j)
):
    """
    Delete all memories for the current user.
    
    ⚠️ This action cannot be undone!
    """
    
    try:
        count = await neo4j.delete_all_user_data(user_id)
        
        return DeleteResponse(
            status="deleted",
            id="all",
            message=f"Deleted {count} memories"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "DELETE_ALL_FAILED",
                    "message": f"Failed to delete memories: {str(e)}"
                }
            }
        )
