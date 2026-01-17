"""
Sessions API routes.
CRUD operations for session management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional

from app.api.dependencies import get_postgres, get_neo4j, get_current_user_id, get_config
from app.db.postgres import PostgresDB
from app.db.neo4j import Neo4jDB
from app.config import Settings
from app.models.requests import (
    CreateSessionRequest, 
    UpdateSessionRequest, 
    LinkConversationRequest,
    ConfirmSessionLinkRequest
)
from app.models.responses import (
    SessionInfo, 
    SessionListResponse, 
    ConversationItem,
    DeleteResponse
)
from app.services.session import get_session_service


router = APIRouter()


def _to_session_info(session: dict) -> SessionInfo:
    """Convert database session dict to SessionInfo model."""
    return SessionInfo(
        id=str(session["id"]),
        name=session["name"],
        description=session.get("description"),
        topics=session.get("topics", []),
        entities=session.get("entities", []),
        conversation_count=session.get("conversation_count", 0),
        created_at=session["created_at"],
        last_activity=session.get("last_activity")
    )


@router.post("", response_model=SessionInfo, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: CreateSessionRequest,
    user_id: str = Depends(get_current_user_id),
    postgres: PostgresDB = Depends(get_postgres)
):
    """
    Create a new session.
    
    Sessions group related conversations across different LLMs.
    """
    # Check if session with same name exists
    existing = await postgres.get_session_by_name(user_id, request.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "SESSION_EXISTS",
                    "message": f"Session with name '{request.name}' already exists"
                }
            }
        )
    
    session = await postgres.create_session(
        user_id=user_id,
        name=request.name,
        description=request.description
    )
    
    return _to_session_info(session)


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    postgres: PostgresDB = Depends(get_postgres)
):
    """
    List all sessions for the current user.
    
    Sessions are ordered by last activity (most recent first).
    """
    sessions = await postgres.list_sessions(
        user_id=user_id,
        limit=limit,
        offset=offset
    )
    
    # Get total count (simplified - just use length for now)
    total = len(sessions)
    if len(sessions) == limit:
        # Might be more, but we don't have a count method for sessions
        total = limit + 1  # Indicate there might be more
    
    return SessionListResponse(
        sessions=[_to_session_info(s) for s in sessions],
        total=total
    )


@router.get("/{session_id}", response_model=SessionInfo)
async def get_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    postgres: PostgresDB = Depends(get_postgres)
):
    """
    Get a specific session by ID.
    """
    session = await postgres.get_session(session_id, user_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": "Session not found"
                }
            }
        )
    
    return _to_session_info(session)


@router.patch("/{session_id}", response_model=SessionInfo)
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    user_id: str = Depends(get_current_user_id),
    postgres: PostgresDB = Depends(get_postgres)
):
    """
    Update a session's name or description.
    """
    # Check if session exists
    existing = await postgres.get_session(session_id, user_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": "Session not found"
                }
            }
        )
    
    # Check for name conflict if changing name
    if request.name and request.name != existing["name"]:
        name_exists = await postgres.get_session_by_name(user_id, request.name)
        if name_exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "SESSION_NAME_EXISTS",
                        "message": f"Session with name '{request.name}' already exists"
                    }
                }
            )
    
    session = await postgres.update_session(
        session_id=session_id,
        user_id=user_id,
        name=request.name,
        description=request.description
    )
    
    return _to_session_info(session)


@router.delete("/{session_id}", response_model=DeleteResponse)
async def delete_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    postgres: PostgresDB = Depends(get_postgres)
):
    """
    Delete a session.
    
    Conversations in the session are NOT deleted, they become standalone.
    """
    # Check if session exists
    existing = await postgres.get_session(session_id, user_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": "Session not found"
                }
            }
        )
    
    await postgres.delete_session(session_id, user_id)
    
    return DeleteResponse(
        status="deleted",
        id=session_id,
        message="Session deleted. Conversations have been unlinked."
    )


@router.get("/{session_id}/conversations", response_model=List[ConversationItem])
async def get_session_conversations(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    postgres: PostgresDB = Depends(get_postgres)
):
    """
    Get all conversations in a session, ordered chronologically.
    """
    # Check if session exists
    session = await postgres.get_session(session_id, user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": "Session not found"
                }
            }
        )
    
    conversations = await postgres.get_conversations_by_session(session_id, user_id)
    
    return [
        ConversationItem(
            id=str(c["id"]),
            source=c["source"],
            message_count=c.get("message_count", len(c.get("raw_messages", []))),
            summary=c.get("summary"),
            topics=c.get("topics", []),
            session_id=str(c["session_id"]) if c.get("session_id") else None,
            session_status=c.get("session_status", "linked"),
            created_at=c["created_at"]
        )
        for c in conversations
    ]


@router.post("/{session_id}/conversations", response_model=ConversationItem)
async def link_conversation_to_session(
    session_id: str,
    request: LinkConversationRequest,
    user_id: str = Depends(get_current_user_id),
    postgres: PostgresDB = Depends(get_postgres),
    config: Settings = Depends(get_config)
):
    """
    Link a conversation to this session.
    """
    # Check if session exists
    session = await postgres.get_session(session_id, user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": "Session not found"
                }
            }
        )
    
    # Check if conversation exists
    conversation = await postgres.get_conversation(request.conversation_id, user_id)
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
    
    # Link conversation
    session_service = await get_session_service(postgres, config)
    updated_conv = await session_service.link_to_session(
        conversation_id=request.conversation_id,
        session_id=session_id,
        user_id=user_id
    )
    
    return ConversationItem(
        id=str(updated_conv["id"]),
        source=updated_conv["source"],
        message_count=updated_conv.get("message_count", len(updated_conv.get("raw_messages", []))),
        summary=updated_conv.get("summary"),
        topics=updated_conv.get("topics", []),
        session_id=str(updated_conv["session_id"]) if updated_conv.get("session_id") else None,
        session_status=updated_conv.get("session_status", "linked"),
        created_at=updated_conv["created_at"]
    )


@router.delete("/{session_id}/conversations/{conversation_id}", response_model=ConversationItem)
async def unlink_conversation_from_session(
    session_id: str,
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    postgres: PostgresDB = Depends(get_postgres)
):
    """
    Unlink a conversation from this session.
    
    The conversation is NOT deleted, it becomes standalone.
    """
    # Check if conversation exists and is in this session
    conversation = await postgres.get_conversation(conversation_id, user_id)
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
    
    if str(conversation.get("session_id")) != session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "CONVERSATION_NOT_IN_SESSION",
                    "message": "Conversation is not in this session"
                }
            }
        )
    
    # Unlink
    updated_conv = await postgres.unlink_conversation_from_session(conversation_id, user_id)
    
    return ConversationItem(
        id=str(updated_conv["id"]),
        source=updated_conv["source"],
        message_count=updated_conv.get("message_count", len(updated_conv.get("raw_messages", []))),
        summary=updated_conv.get("summary"),
        topics=updated_conv.get("topics", []),
        session_id=None,
        session_status="standalone",
        created_at=updated_conv["created_at"]
    )


@router.post("/confirm-link", response_model=ConversationItem)
async def confirm_session_link(
    request: ConfirmSessionLinkRequest,
    user_id: str = Depends(get_current_user_id),
    postgres: PostgresDB = Depends(get_postgres),
    config: Settings = Depends(get_config)
):
    """
    Confirm or reject a session link suggestion.
    
    This endpoint is used after ingesting a conversation when the system
    suggests linking it to an existing session.
    
    Actions:
    - `accept`: Link to the suggested session (or specified session_id)
    - `reject`: Keep the conversation standalone
    - `create_new`: Create a new session and link the conversation to it
    """
    # Check if conversation exists
    conversation = await postgres.get_conversation(request.conversation_id, user_id)
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
    
    session_service = await get_session_service(postgres, config)
    
    if request.action == "accept":
        if not request.session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "SESSION_ID_REQUIRED",
                        "message": "session_id is required for 'accept' action"
                    }
                }
            )
        
        # Verify session exists
        session = await postgres.get_session(request.session_id, user_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "SESSION_NOT_FOUND",
                        "message": "Session not found"
                    }
                }
            )
        
        updated_conv = await session_service.link_to_session(
            conversation_id=request.conversation_id,
            session_id=request.session_id,
            user_id=user_id
        )
        
        # Record user's decision for learning
        await postgres.update_session_suggestion(
            conversation_id=request.conversation_id,
            accepted=True,
            actual_session_id=request.session_id
        )
    
    elif request.action == "reject":
        # Keep standalone, record rejection
        updated_conv = conversation
        await postgres.update_session_suggestion(
            conversation_id=request.conversation_id,
            accepted=False,
            actual_session_id=None
        )
    
    elif request.action == "create_new":
        if not request.new_session_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "SESSION_NAME_REQUIRED",
                        "message": "new_session_name is required for 'create_new' action"
                    }
                }
            )
        
        session, updated_conv = await session_service.create_and_link_session(
            conversation_id=request.conversation_id,
            user_id=user_id,
            session_name=request.new_session_name,
            description=request.new_session_description
        )
        
        # Record user's decision
        await postgres.update_session_suggestion(
            conversation_id=request.conversation_id,
            accepted=False,  # Rejected original suggestion
            actual_session_id=str(session["id"])
        )
    
    return ConversationItem(
        id=str(updated_conv["id"]),
        source=updated_conv["source"],
        message_count=updated_conv.get("message_count", len(updated_conv.get("raw_messages", []))),
        summary=updated_conv.get("summary"),
        topics=updated_conv.get("topics", []),
        session_id=str(updated_conv.get("session_id")) if updated_conv.get("session_id") else None,
        session_status=updated_conv.get("session_status", "standalone"),
        created_at=updated_conv["created_at"]
    )
