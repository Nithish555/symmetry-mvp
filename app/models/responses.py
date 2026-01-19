"""
Response models for API endpoints.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime


# =========================================================================
# User responses
# =========================================================================

class UserResponse(BaseModel):
    """User information response."""
    user_id: str
    email: str
    created_at: Optional[datetime] = None


class UserRegistrationResponse(BaseModel):
    """Response after user registration."""
    user_id: str
    email: str
    api_key: str
    message: str


# =========================================================================
# Session responses
# =========================================================================

class SessionInfo(BaseModel):
    """Session information."""
    id: str
    name: str
    description: Optional[str] = None
    topics: List[str] = []
    entities: List[str] = []
    conversation_count: int = 0
    created_at: datetime
    last_activity: Optional[datetime] = None


class SessionListResponse(BaseModel):
    """Response with list of sessions."""
    sessions: List[SessionInfo]
    total: int


class SessionSuggestion(BaseModel):
    """A suggested session for linking."""
    session_id: str
    name: str
    score: float
    topics: List[str] = []
    conversation_count: int = 0


class SessionSuggestionResponse(BaseModel):
    """Response with session suggestions."""
    suggested_session: Optional[SessionInfo] = None
    confidence: float
    auto_linked: bool
    all_suggestions: List[SessionSuggestion] = []
    reason: str


# =========================================================================
# Ingest responses
# =========================================================================

class IngestResponse(BaseModel):
    """Response after ingesting a conversation."""
    conversation_id: str
    chunks_created: int
    entities_extracted: int
    relationships_created: int
    status: str  # "success", "appended", "no_new_messages"
    message: Optional[str] = None  # Optional message for status details
    # Session suggestion info
    session_suggestion: Optional[SessionSuggestionResponse] = None
    linked_session_id: Optional[str] = None
    # Append mode info
    is_append: bool = False
    new_messages_count: int = 0


# =========================================================================
# Retrieve responses
# =========================================================================

class DecisionInfo(BaseModel):
    """Information about a decision with full metadata."""
    content: str
    reason: Optional[str] = None
    date: Optional[str] = None
    source: Optional[str] = None  # Platform (claude, chatgpt, etc.)
    confidence: Optional[float] = None  # 0.0-1.0
    status: Optional[str] = None  # decided, exploring, rejected
    verified: Optional[bool] = None  # User has verified this
    attributed_to: Optional[str] = None  # user, colleague, article, ai_suggestion
    temporal: Optional[str] = None  # current, past, future
    note: Optional[str] = None  # Additional context (e.g., "hypothetical")


class ContradictionWarning(BaseModel):
    """Warning about contradictory decisions."""
    old_decision: str
    old_date: Optional[str] = None
    new_decision: str
    new_date: Optional[str] = None
    category: Optional[str] = None
    message: str


class FactInfo(BaseModel):
    """Information about a fact."""
    subject: str
    predicate: str
    object: str
    since: Optional[str] = None


class SourceInfo(BaseModel):
    """Source information for context."""
    source: str
    date: Optional[datetime] = None


class KnowledgeQuality(BaseModel):
    """
    Quality indicators for the returned knowledge.
    Helps users understand how reliable the context is.
    """
    total_decisions: int = 0
    confirmed_decisions: int = 0  # High confidence, verified
    exploring_count: int = 0  # Items being considered
    rejected_count: int = 0  # Explicitly rejected items
    unverified_count: int = 0  # Not verified by user
    contradictions_count: int = 0  # Conflicting decisions
    others_suggestions: int = 0  # Attributed to colleagues/articles
    past_items: int = 0  # Historical, not current
    
    # Quality score (0-100)
    quality_score: int = 100
    quality_notes: List[str] = []


class ChunkInfo(BaseModel):
    """Information about a retrieved chunk."""
    id: Optional[str] = None
    content: str
    source: Optional[str] = None
    conversation_id: Optional[str] = None
    similarity: Optional[float] = None


class RetrieveResponse(BaseModel):
    """Response with retrieved context."""
    summary: str
    context_prompt: str = ""
    decisions: List[DecisionInfo] = []
    facts: List[FactInfo] = []
    entities: List[str] = []
    sources: List[SourceInfo] = []
    chunks_found: int
    # Session info if applicable
    session: Optional[SessionInfo] = None
    # Warnings about potential issues
    contradictions: List[ContradictionWarning] = []
    unverified_count: int = 0  # Number of unverified knowledge items
    # Knowledge quality summary
    knowledge_quality: Optional[KnowledgeQuality] = None
    # Raw chunks for custom prompt building (optional)
    chunks: List[ChunkInfo] = []


# =========================================================================
# Recommendation responses
# =========================================================================

class ScoreBreakdown(BaseModel):
    """Score breakdown for a recommendation."""
    relevance: float
    recency: float
    quality: float
    final: float


class RecommendationItem(BaseModel):
    """A single recommendation."""
    id: str
    type: str  # 'conversation' or 'session'
    name: str
    summary: Optional[str] = None
    source: Optional[str] = None
    topics: List[str] = []
    entities: List[str] = []
    score: ScoreBreakdown
    auto_select: bool = False
    conversation_count: int = 1
    last_activity: Optional[str] = None


class QueryAnalysis(BaseModel):
    """Analysis of the query."""
    topics: List[str] = []
    entities: List[str] = []


class RecommendResponse(BaseModel):
    """Response with recommendations."""
    recommendations: List[RecommendationItem]
    auto_selected: Optional[RecommendationItem] = None
    query_analysis: QueryAnalysis


# =========================================================================
# Memory responses
# =========================================================================

class MemoryItem(BaseModel):
    """A single memory item."""
    id: str
    type: str  # decision, fact, preference
    content: str
    metadata: Optional[dict] = None
    source: Optional[str] = None
    date: Optional[str] = None


class MemoriesListResponse(BaseModel):
    """Response with list of memories."""
    memories: List[MemoryItem]
    total: int


# =========================================================================
# Conversation responses
# =========================================================================

class ConversationItem(BaseModel):
    """Summary of a conversation."""
    id: str
    source: str
    message_count: int
    summary: Optional[str] = None
    topics: List[str] = []
    session_id: Optional[str] = None
    session_status: str = "standalone"
    created_at: datetime


class ConversationsListResponse(BaseModel):
    """Response with list of conversations."""
    conversations: List[ConversationItem]
    total: int
    limit: int
    offset: int


class ConversationDetailResponse(BaseModel):
    """Detailed conversation with messages."""
    id: str
    source: str
    messages: List[dict]
    summary: Optional[str] = None
    topics: List[str] = []
    entities: List[str] = []
    session_id: Optional[str] = None
    session_status: str = "standalone"
    created_at: datetime


# =========================================================================
# Generic responses
# =========================================================================

class DeleteResponse(BaseModel):
    """Response after deletion."""
    status: str
    id: str
    message: Optional[str] = None


class ErrorDetail(BaseModel):
    """Error detail."""
    code: str
    message: str


class ErrorResponse(BaseModel):
    """Error response."""
    error: ErrorDetail
