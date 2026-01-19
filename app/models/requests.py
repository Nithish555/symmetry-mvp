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
    conversation_id: Optional[str] = Field(
        None,
        description=(
            "Optional: ID of existing conversation to append to. "
            "Use with `append_only=false` (default): Send ALL messages, system finds new ones. "
            "Use with `append_only=true`: Send ONLY new messages, system appends directly."
        )
    )
    append_only: bool = Field(
        False,
        description=(
            "Only used when conversation_id is provided. "
            "When false (default): messages contains ALL messages (old+new), system compares to find new ones. "
            "When true: messages contains ONLY new messages to append directly."
        )
    )
    session_id: Optional[str] = Field(
        None,
        description="Optional: ID of session to link this conversation to. If provided, skips session analysis."
    )
    auto_link_session: bool = Field(
        True,
        description=(
            "Controls auto-linking behavior. "
            "When true: Auto-link if confidence >85%, otherwise just suggest. "
            "When false: Always return suggestions but NEVER auto-link (user must confirm manually). "
            "Suggestions are ALWAYS returned regardless of this setting."
        )
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
    
    # ═══════════════════════════════════════════════════════════════
    # CONTEXT CUSTOMIZATION OPTIONS
    # ═══════════════════════════════════════════════════════════════
    include_exploring: bool = Field(
        default=True,
        description="Include items being considered (not decided yet)"
    )
    include_rejected: bool = Field(
        default=True,
        description="Include rejected options"
    )
    include_others_suggestions: bool = Field(
        default=True,
        description="Include suggestions from colleagues/articles (not user's own)"
    )
    only_verified: bool = Field(
        default=False,
        description="Only include user-verified knowledge"
    )
    exclude_entities: List[str] = Field(
        default=[],
        description="List of entity names to exclude from context (e.g., ['MySQL', 'MongoDB'])"
    )
    exclude_decision_ids: List[str] = Field(
        default=[],
        description="List of specific decision IDs to exclude"
    )
    custom_note: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Custom note to add at the top of context_prompt"
    )
    max_context_length: Optional[int] = Field(
        default=None,
        ge=500,
        le=10000,
        description="Maximum length of context_prompt (truncates if exceeded)"
    )
    custom_summary: Optional[str] = Field(
        default=None,
        max_length=5000,
        description=(
            "If provided, use this as the summary instead of generating one. "
            "Useful when user has edited/customized their summary."
        )
    )
    skip_summary_generation: bool = Field(
        default=False,
        description=(
            "If true, skip LLM summary generation (faster response). "
            "Use stored conversation/session summary instead."
        )
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
