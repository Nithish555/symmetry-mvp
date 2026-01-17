"""
Request models for API endpoints.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Literal


class Message(BaseModel):
    """A single message in a conversation."""
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1)


class UserRegisterRequest(BaseModel):
    """Request to register a new user."""
    email: EmailStr


class IngestRequest(BaseModel):
    """Request to ingest a conversation."""
    source: str = Field(
        ..., 
        description="Source of the conversation: chatgpt, claude, cursor, etc.",
        examples=["chatgpt", "claude", "cursor"]
    )
    messages: List[Message] = Field(
        ..., 
        min_length=1,
        description="List of messages in the conversation"
    )
    session_id: Optional[str] = Field(
        None,
        description="Optional: ID of session to link this conversation to"
    )
    auto_link_session: bool = Field(
        True,
        description="If true, automatically suggest/link to existing sessions"
    )


class RetrieveRequest(BaseModel):
    """Request to retrieve context."""
    query: str = Field(
        default="",
        description="The query to find relevant context for (required for 'query' mode)"
    )
    mode: Literal["query", "full", "session", "conversation"] = Field(
        default="query",
        description="""
        Retrieval mode:
        - 'query': Returns context similar to the query (default)
        - 'full': Returns ALL user's knowledge (decisions, facts, entities)
        - 'session': Returns all conversations in a specific session
        - 'conversation': Returns full conversation history for a specific conversation
        """
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Required for 'session' mode - the session to retrieve"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Required for 'conversation' mode - the conversation to retrieve"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of items to return"
    )


class RecommendRequest(BaseModel):
    """Request to get recommendations for continuing a conversation."""
    query: str = Field(
        ...,
        min_length=1,
        description="The query/topic to find relevant context for"
    )
    include_sessions: bool = Field(
        default=True,
        description="Include session recommendations"
    )
    include_conversations: bool = Field(
        default=True,
        description="Include standalone conversation recommendations"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum number of recommendations"
    )


# Session requests
class CreateSessionRequest(BaseModel):
    """Request to create a new session."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name/title for the session"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional description of what this session is about"
    )


class UpdateSessionRequest(BaseModel):
    """Request to update a session."""
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="New name for the session"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="New description for the session"
    )


class LinkConversationRequest(BaseModel):
    """Request to link a conversation to a session."""
    conversation_id: str = Field(
        ...,
        description="ID of the conversation to link"
    )


class ConfirmSessionLinkRequest(BaseModel):
    """Request to confirm or reject a session link suggestion."""
    conversation_id: str = Field(
        ...,
        description="ID of the conversation"
    )
    action: Literal["accept", "reject", "create_new"] = Field(
        ...,
        description="Action to take: accept suggestion, reject it, or create a new session"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID to link to (required if action is 'accept' with different session)"
    )
    new_session_name: Optional[str] = Field(
        None,
        description="Name for new session (required if action is 'create_new')"
    )
    new_session_description: Optional[str] = Field(
        None,
        description="Description for new session (optional if action is 'create_new')"
    )
