"""
Conversations endpoints - View and manage stored conversations.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional

from app.api.dependencies import get_postgres, get_current_user_id
from app.db.postgres import PostgresDB
from app.models.responses import (
    ConversationsListResponse, 
    ConversationItem, 
    ConversationDetailResponse,
    DeleteResponse
)


router = APIRouter()


@router.get("", response_model=ConversationsListResponse)
async def list_conversations(
    source: Optional[str] = Query(None, description="Filter by source: chatgpt, claude, cursor"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
    postgres: PostgresDB = Depends(get_postgres)
):
    """
    List all stored conversations for the current user.
    
    Can filter by source (chatgpt, claude, cursor) or session_id.
    """
    
    try:
        conversations = await postgres.list_conversations(
            user_id=user_id,
            source=source,
            session_id=session_id,
            limit=limit,
            offset=offset
        )
        
        total = await postgres.count_conversations(user_id=user_id, source=source)
        
        items = [
            ConversationItem(
                id=str(c["id"]),
                source=c["source"],
                message_count=c.get("message_count", len(c.get("raw_messages", []))),
                summary=c.get("summary"),
                topics=c.get("topics", []),
                session_id=str(c["session_id"]) if c.get("session_id") else None,
                session_status=c.get("session_status", "standalone"),
                created_at=c["created_at"]
            )
            for c in conversations
        ]
        
        return ConversationsListResponse(
            conversations=items,
            total=total,
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "LIST_CONVERSATIONS_FAILED",
                    "message": f"Failed to list conversations: {str(e)}"
                }
            }
        )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    postgres: PostgresDB = Depends(get_postgres)
):
    """
    Get details of a specific conversation including original messages.
    """
    
    try:
        conversation = await postgres.get_conversation(
            conversation_id=conversation_id,
            user_id=user_id
        )
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "CONVERSATION_NOT_FOUND",
                        "message": "Conversation not found"
                    }
                }
            )
        
        return ConversationDetailResponse(
            id=str(conversation["id"]),
            source=conversation["source"],
            messages=conversation["raw_messages"],
            summary=conversation.get("summary"),
            topics=conversation.get("topics", []),
            entities=conversation.get("entities", []),
            session_id=str(conversation["session_id"]) if conversation.get("session_id") else None,
            session_status=conversation.get("session_status", "standalone"),
            created_at=conversation["created_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "GET_CONVERSATION_FAILED",
                    "message": f"Failed to get conversation: {str(e)}"
                }
            }
        )


@router.delete("/{conversation_id}", response_model=DeleteResponse)
async def delete_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    postgres: PostgresDB = Depends(get_postgres)
):
    """
    Delete a conversation and all its chunks.
    
    Note: This does not delete extracted knowledge from the graph.
    Use DELETE /memories to remove knowledge.
    """
    
    try:
        deleted = await postgres.delete_conversation(
            conversation_id=conversation_id,
            user_id=user_id
        )
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "CONVERSATION_NOT_FOUND",
                        "message": "Conversation not found or already deleted"
                    }
                }
            )
        
        return DeleteResponse(
            status="deleted",
            id=conversation_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "DELETE_CONVERSATION_FAILED",
                    "message": f"Failed to delete conversation: {str(e)}"
                }
            }
        )
