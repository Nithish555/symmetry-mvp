"""
Sessions API routes.
CRUD operations for session management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel, Field

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


@router.post("/{session_id}/generate-summary")
async def generate_session_summary(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    postgres: PostgresDB = Depends(get_postgres),
    config: Settings = Depends(get_config)
):
    """
    Generate a combined summary from all conversations in the session.
    
    This creates a unified summary that covers all discussions in the session.
    The generated summary is saved as the session's description.
    """
    from app.services.extraction import generate_conversation_summary
    
    # Get session
    session = await postgres.get_session(session_id, user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Session not found"}}
        )
    
    # Get all conversations in session
    conversations = await postgres.get_conversations_by_session(session_id, user_id)
    
    if not conversations:
        return {
            "session_id": session_id,
            "summary": "No conversations in this session yet.",
            "conversation_count": 0,
            "message": "Session has no conversations to summarize"
        }
    
    # Combine all conversation summaries and key info
    combined_text = f"Session: {session['name']}\n\n"
    
    all_topics = set()
    all_entities = set()
    
    for i, conv in enumerate(conversations, 1):
        source = conv.get("source", "unknown")
        summary = conv.get("summary", "")
        topics = conv.get("topics", [])
        entities = conv.get("entities", [])
        
        combined_text += f"Conversation {i} ({source}):\n"
        if summary:
            combined_text += f"{summary}\n"
        else:
            # Use first few messages if no summary
            messages = conv.get("raw_messages", [])[:3]
            for msg in messages:
                combined_text += f"- {msg.get('role', 'user')}: {msg.get('content', '')[:200]}\n"
        combined_text += "\n"
        
        all_topics.update(topics)
        all_entities.update(entities)
    
    # Generate unified summary using LLM
    import httpx
    
    prompt = f"""Create a unified summary of this session that covers all conversations.
The summary should:
1. Capture the main objective/project
2. List key decisions made
3. Note important topics discussed
4. Be concise (2-4 sentences)

Session content:
{combined_text[:4000]}

Topics covered: {', '.join(all_topics) if all_topics else 'Not specified'}
Key entities: {', '.join(all_entities) if all_entities else 'Not specified'}

Return only the summary text, no formatting."""

    async with httpx.AsyncClient() as client:
        if config.llm_provider == "azure_openai":
            url = f"{config.azure_openai_endpoint.rstrip('/')}/openai/deployments/{config.azure_openai_deployment}/chat/completions?api-version={config.azure_openai_api_version}"
            headers = {"api-key": config.azure_openai_api_key, "Content-Type": "application/json"}
        else:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {config.openai_api_key}", "Content-Type": "application/json"}
        
        json_body = {
            "messages": [
                {"role": "system", "content": "You create concise, informative summaries of multi-conversation sessions."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 500
        }
        
        if config.llm_provider != "azure_openai":
            json_body["model"] = config.llm_model
        
        response = await client.post(url, headers=headers, json=json_body, timeout=60.0)
        response.raise_for_status()
        data = response.json()
        
        generated_summary = data["choices"][0]["message"]["content"].strip()
    
    # Save the generated summary as session description
    await postgres.update_session(
        session_id=session_id,
        user_id=user_id,
        description=generated_summary
    )
    
    return {
        "session_id": session_id,
        "summary": generated_summary,
        "conversation_count": len(conversations),
        "topics": list(all_topics),
        "entities": list(all_entities),
        "message": "✅ Session summary generated and saved"
    }


class UpdateSessionSummaryRequest(BaseModel):
    """Request to update session summary."""
    summary: str = Field(..., min_length=1, max_length=5000)


@router.patch("/{session_id}/summary")
async def update_session_summary(
    session_id: str,
    request: UpdateSessionSummaryRequest,
    user_id: str = Depends(get_current_user_id),
    postgres: PostgresDB = Depends(get_postgres)
):
    """
    Manually update/edit the session summary.
    
    Use this to correct or customize the auto-generated summary.
    """
    # Get session
    session = await postgres.get_session(session_id, user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Session not found"}}
        )
    
    # Update description (which serves as summary)
    await postgres.update_session(
        session_id=session_id,
        user_id=user_id,
        description=request.summary
    )
    
    return {
        "session_id": session_id,
        "summary": request.summary,
        "message": "✅ Session summary updated"
    }


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
