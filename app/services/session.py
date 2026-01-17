"""
Session service for auto-detection and management.
Handles session suggestion, linking, and embedding updates.
"""

from typing import List, Optional, Tuple
from datetime import datetime, timedelta
import logging

from app.db.postgres import PostgresDB
from app.services.embedding import generate_embedding

logger = logging.getLogger(__name__)


class SessionService:
    """Service for session management and auto-detection."""
    
    # Thresholds for session matching
    HIGH_CONFIDENCE_THRESHOLD = 0.85  # Auto-link without asking
    MEDIUM_CONFIDENCE_THRESHOLD = 0.70  # Suggest to user
    LOW_CONFIDENCE_THRESHOLD = 0.50  # Include in options but don't suggest
    
    # Time-based relevance decay
    RECENT_HOURS = 24  # Conversations within this time get a boost
    RECENCY_BOOST = 0.1  # Score boost for recent sessions
    
    def __init__(
        self,
        postgres: PostgresDB,
        embedding_config: dict
    ):
        self.postgres = postgres
        self.embedding_config = embedding_config
    
    async def analyze_conversation(
        self,
        messages: List[dict],
        user_id: str
    ) -> dict:
        """
        Analyze a conversation and suggest session linking.
        
        Returns:
            {
                "suggested_session": {...} or None,
                "confidence": float,
                "all_matches": [...],
                "auto_link": bool,
                "reason": str
            }
        """
        # Generate conversation embedding from summary/content
        conv_text = self._messages_to_text(messages)
        conv_embedding = await generate_embedding(
            text=conv_text[:8000],  # Limit text length
            **self.embedding_config
        )
        
        # Search for similar sessions
        similar_sessions = await self.postgres.search_sessions_by_embedding(
            user_id=user_id,
            embedding=conv_embedding,
            limit=5,
            threshold=self.LOW_CONFIDENCE_THRESHOLD
        )
        
        # Also search for similar conversations (might belong to same session)
        similar_convs = await self.postgres.search_conversations_by_embedding(
            user_id=user_id,
            embedding=conv_embedding,
            limit=5,
            threshold=self.LOW_CONFIDENCE_THRESHOLD
        )
        
        # Collect session candidates from both searches
        session_scores = {}
        
        # Direct session matches
        for session in similar_sessions:
            session_id = str(session["id"])
            base_score = session.get("similarity", 0)
            recency_score = self._calculate_recency_score(session.get("last_activity"))
            final_score = base_score + recency_score
            session_scores[session_id] = {
                "session": session,
                "score": final_score,
                "match_type": "direct"
            }
        
        # Sessions from similar conversations
        for conv in similar_convs:
            if conv.get("session_id"):
                session_id = str(conv["session_id"])
                conv_similarity = conv.get("similarity", 0)
                
                if session_id in session_scores:
                    # Boost existing score
                    session_scores[session_id]["score"] += conv_similarity * 0.3
                else:
                    # Get session details
                    session = await self.postgres.get_session(session_id, user_id)
                    if session:
                        recency_score = self._calculate_recency_score(session.get("last_activity"))
                        session_scores[session_id] = {
                            "session": session,
                            "score": conv_similarity * 0.8 + recency_score,
                            "match_type": "conversation"
                        }
        
        # Sort by score
        sorted_sessions = sorted(
            session_scores.values(),
            key=lambda x: x["score"],
            reverse=True
        )
        
        # Determine suggestion
        if not sorted_sessions:
            return {
                "suggested_session": None,
                "confidence": 0.0,
                "all_matches": [],
                "auto_link": False,
                "reason": "no_matching_sessions"
            }
        
        top_match = sorted_sessions[0]
        confidence = min(top_match["score"], 1.0)  # Cap at 1.0
        
        # Determine if we should auto-link
        auto_link = confidence >= self.HIGH_CONFIDENCE_THRESHOLD
        
        # Check for ambiguity (multiple high-scoring sessions)
        if len(sorted_sessions) > 1:
            second_score = sorted_sessions[1]["score"]
            if confidence - second_score < 0.15:  # Too close to call
                auto_link = False
        
        return {
            "suggested_session": top_match["session"],
            "confidence": confidence,
            "all_matches": [
                {
                    "session_id": str(s["session"]["id"]),
                    "name": s["session"]["name"],
                    "score": s["score"],
                    "topics": s["session"].get("topics", []),
                    "conversation_count": s["session"].get("conversation_count", 0)
                }
                for s in sorted_sessions[:5]
            ],
            "auto_link": auto_link,
            "reason": "high_confidence" if auto_link else "needs_confirmation"
        }
    
    async def link_to_session(
        self,
        conversation_id: str,
        session_id: str,
        user_id: str
    ) -> dict:
        """Link a conversation to a session and update session embedding."""
        # Link conversation
        conv = await self.postgres.link_conversation_to_session(
            conversation_id=conversation_id,
            user_id=user_id,
            session_id=session_id
        )
        
        if not conv:
            raise ValueError("Failed to link conversation to session")
        
        # Update session embedding (average of all conversation embeddings)
        await self._update_session_embedding(session_id, user_id)
        
        return conv
    
    async def create_and_link_session(
        self,
        conversation_id: str,
        user_id: str,
        session_name: str,
        description: Optional[str] = None
    ) -> Tuple[dict, dict]:
        """Create a new session and link the conversation to it."""
        # Create session
        session = await self.postgres.create_session(
            user_id=user_id,
            name=session_name,
            description=description
        )
        
        # Link conversation
        conv = await self.postgres.link_conversation_to_session(
            conversation_id=conversation_id,
            user_id=user_id,
            session_id=str(session["id"])
        )
        
        return session, conv
    
    async def _update_session_embedding(self, session_id: str, user_id: str):
        """Update session embedding based on all linked conversations."""
        # Get all conversations in session
        conversations = await self.postgres.get_conversations_by_session(
            session_id=session_id,
            user_id=user_id
        )
        
        if not conversations:
            return
        
        # Combine all conversation summaries/content
        combined_text = []
        for conv in conversations:
            if conv.get("summary"):
                combined_text.append(conv["summary"])
            else:
                text = self._messages_to_text(conv.get("raw_messages", []))
                combined_text.append(text[:2000])
        
        full_text = "\n\n".join(combined_text)[:8000]
        
        # Generate new embedding
        embedding = await generate_embedding(
            text=full_text,
            **self.embedding_config
        )
        
        # Update session
        await self.postgres.update_session_embedding(
            session_id=session_id,
            user_id=user_id,
            embedding=embedding
        )
    
    def _messages_to_text(self, messages: List[dict]) -> str:
        """Convert messages to searchable text."""
        parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            parts.append(f"{role}: {content}")
        return "\n".join(parts)
    
    def _calculate_recency_score(self, last_activity) -> float:
        """Calculate recency boost score."""
        if not last_activity:
            return 0.0
        
        if isinstance(last_activity, str):
            try:
                last_activity = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return 0.0
        
        now = datetime.now(last_activity.tzinfo) if last_activity.tzinfo else datetime.now()
        hours_ago = (now - last_activity).total_seconds() / 3600
        
        if hours_ago <= self.RECENT_HOURS:
            # Linear decay within recent window
            return self.RECENCY_BOOST * (1 - hours_ago / self.RECENT_HOURS)
        return 0.0


async def get_session_service(
    postgres: PostgresDB,
    config
) -> SessionService:
    """Factory function to create SessionService with config."""
    embedding_config = {
        "api_key": config.openai_api_key,
        "model": config.embedding_model,
        "azure_endpoint": config.get_embedding_endpoint(),
        "azure_api_key": config.get_embedding_api_key(),
        "azure_api_version": config.azure_openai_api_version,
        "azure_deployment": config.get_embedding_deployment(),
        "provider": config.llm_provider
    }
    return SessionService(postgres, embedding_config)
