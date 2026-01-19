"""
Recommendation service for finding relevant conversations and sessions.
Implements the scoring algorithm for conversation/session recommendations.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass

from app.db.postgres import PostgresDB
from app.db.neo4j import Neo4jDB
from app.services.embedding import generate_embedding
from app.services.extraction import extract_topics_and_entities

logger = logging.getLogger(__name__)


@dataclass
class RecommendationScore:
    """Score breakdown for a recommendation."""
    relevance_score: float  # Semantic similarity (0-1)
    recency_score: float    # Time-based score (0-1)
    quality_score: float    # Content quality (0-1)
    final_score: float      # Weighted combination
    
    def to_dict(self) -> dict:
        return {
            "relevance": round(self.relevance_score, 3),
            "recency": round(self.recency_score, 3),
            "quality": round(self.quality_score, 3),
            "final": round(self.final_score, 3)
        }


@dataclass
class Recommendation:
    """A single recommendation item."""
    id: str
    type: str  # 'conversation' or 'session'
    name: str
    summary: Optional[str]
    source: Optional[str]
    topics: List[str]
    entities: List[str]
    score: RecommendationScore
    auto_select: bool
    conversation_count: int = 1
    last_activity: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "summary": self.summary,
            "source": self.source,
            "topics": self.topics,
            "entities": self.entities,
            "score": self.score.to_dict(),
            "auto_select": self.auto_select,
            "conversation_count": self.conversation_count,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None
        }


class RecommendationService:
    """Service for recommending relevant conversations and sessions."""
    
    # Scoring weights (should sum to 1.0)
    RELEVANCE_WEIGHT = 0.60
    RECENCY_WEIGHT = 0.25
    QUALITY_WEIGHT = 0.15
    
    # Auto-selection thresholds
    AUTO_SELECT_THRESHOLD = 0.85
    AUTO_SELECT_MARGIN = 0.20  # Minimum gap from second-best
    
    # Recency decay parameters
    RECENT_HOURS = 24
    DECAY_DAYS = 30  # After this, recency score is 0
    
    def __init__(
        self,
        postgres: PostgresDB,
        neo4j: Neo4jDB,
        embedding_config: dict,
        extraction_config: dict
    ):
        self.postgres = postgres
        self.neo4j = neo4j
        self.embedding_config = embedding_config
        self.extraction_config = extraction_config
    
    async def recommend(
        self,
        user_id: str,
        query: str,
        include_sessions: bool = True,
        include_conversations: bool = True,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get recommendations for a query.
        
        Uses Knowledge Graph expansion for better recall:
        1. Extract keywords from query
        2. Find related entities in user's knowledge graph
        3. Use expanded terms for better matching
        
        Args:
            user_id: User ID
            query: The query text (what user is about to discuss)
            include_sessions: Include session recommendations
            include_conversations: Include conversation recommendations
            limit: Maximum number of recommendations
        
        Returns:
            {
                "recommendations": [...],
                "auto_selected": {...} or None,
                "query_analysis": {...}
            }
        """
        # Step 1: Analyze the query
        query_embedding = await generate_embedding(
            text=query,
            **self.embedding_config
        )
        
        # Extract topics and entities from query
        query_analysis = await self._analyze_query(query)
        
        # ─────────────────────────────────────────────────────────────
        # Step 1.5: Knowledge Graph Expansion
        # Find related entities from user's knowledge graph
        # ─────────────────────────────────────────────────────────────
        expanded_entities = []
        if self.neo4j and self.neo4j.driver:
            try:
                # Extract keywords from query
                query_keywords = self._extract_keywords(query)
                
                # Find related entities in knowledge graph
                if query_keywords:
                    expanded_entities = await self.neo4j.find_related_entities(
                        user_id=user_id,
                        search_terms=query_keywords,
                        max_hops=2,
                        limit=10
                    )
                    if expanded_entities:
                        logger.info(f"KG expansion for recommend: {expanded_entities}")
                        # Add to query analysis for transparency
                        query_analysis["kg_expanded_entities"] = expanded_entities
            except Exception as kg_error:
                logger.warning(f"Knowledge graph expansion failed: {kg_error}")
        
        recommendations = []
        
        # Combine topics with expanded entities for better matching
        all_topics = list(set(
            query_analysis.get("topics", []) + 
            query_analysis.get("entities", []) +
            expanded_entities
        ))
        
        # Step 2: Find similar sessions
        if include_sessions:
            session_recs = await self._recommend_sessions(
                user_id=user_id,
                embedding=query_embedding,
                topics=all_topics,  # Use expanded topics
                limit=limit
            )
            recommendations.extend(session_recs)
        
        # Step 3: Find similar conversations (not in sessions)
        if include_conversations:
            conv_recs = await self._recommend_conversations(
                user_id=user_id,
                embedding=query_embedding,
                topics=all_topics,  # Use expanded topics
                exclude_session_convs=include_sessions,  # Don't duplicate
                limit=limit
            )
            recommendations.extend(conv_recs)
        
        # Step 4: Sort by final score
        recommendations.sort(key=lambda r: r.score.final_score, reverse=True)
        recommendations = recommendations[:limit]
        
        # Step 5: Determine auto-selection
        auto_selected = self._determine_auto_select(recommendations)
        
        # Mark auto-selected item
        for rec in recommendations:
            rec.auto_select = (auto_selected and rec.id == auto_selected.id)
        
        return {
            "recommendations": [r.to_dict() for r in recommendations],
            "auto_selected": auto_selected.to_dict() if auto_selected else None,
            "query_analysis": query_analysis
        }
    
    async def _analyze_query(self, query: str) -> dict:
        """Extract topics and entities from query."""
        try:
            result = await extract_topics_and_entities(
                text=query,
                **self.extraction_config
            )
            return result
        except Exception as e:
            logger.warning(f"Query analysis failed: {e}")
            return {"topics": [], "entities": []}
    
    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract meaningful keywords from query for knowledge graph lookup.
        Simple approach: remove stop words, keep 3+ char words.
        """
        stop_words = {
            "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "shall", "can", "need", "to", "of",
            "in", "for", "on", "with", "at", "by", "from", "as", "into", "through",
            "during", "before", "after", "above", "below", "between", "under",
            "again", "further", "then", "once", "here", "there", "when", "where",
            "why", "how", "all", "each", "few", "more", "most", "other", "some",
            "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
            "very", "just", "and", "but", "if", "or", "because", "until", "while",
            "about", "what", "which", "who", "whom", "this", "that", "these",
            "those", "am", "i", "me", "my", "myself", "we", "our", "ours", "you",
            "your", "yours", "he", "him", "his", "she", "her", "hers", "it", "its",
            "they", "them", "their", "theirs"
        }
        
        words = query.lower().split()
        keywords = [
            word.strip(".,!?;:'\"()[]{}") 
            for word in words 
            if word.lower() not in stop_words and len(word) >= 3
        ]
        
        # Remove duplicates
        return list(dict.fromkeys(keywords))[:10]
    
    async def _recommend_sessions(
        self,
        user_id: str,
        embedding: List[float],
        topics: List[str],
        limit: int
    ) -> List[Recommendation]:
        """Get session recommendations."""
        recommendations = []
        
        # Semantic search
        similar_sessions = await self.postgres.search_sessions_by_embedding(
            user_id=user_id,
            embedding=embedding,
            limit=limit,
            threshold=0.3  # Lower threshold, we'll filter later
        )
        
        for session in similar_sessions:
            relevance = session.get("similarity", 0)
            recency = self._calculate_recency_score(session.get("last_activity"))
            quality = self._calculate_session_quality(session)
            
            # Topic bonus
            session_topics = session.get("topics", [])
            topic_overlap = len(set(topics) & set(session_topics))
            if topic_overlap > 0:
                relevance = min(1.0, relevance + 0.1 * topic_overlap)
            
            final = (
                relevance * self.RELEVANCE_WEIGHT +
                recency * self.RECENCY_WEIGHT +
                quality * self.QUALITY_WEIGHT
            )
            
            rec = Recommendation(
                id=str(session["id"]),
                type="session",
                name=session["name"],
                summary=session.get("description"),
                source=None,
                topics=session_topics,
                entities=session.get("entities", []),
                score=RecommendationScore(
                    relevance_score=relevance,
                    recency_score=recency,
                    quality_score=quality,
                    final_score=final
                ),
                auto_select=False,
                conversation_count=session.get("conversation_count", 0),
                last_activity=session.get("last_activity")
            )
            recommendations.append(rec)
        
        return recommendations
    
    async def _recommend_conversations(
        self,
        user_id: str,
        embedding: List[float],
        topics: List[str],
        exclude_session_convs: bool,
        limit: int
    ) -> List[Recommendation]:
        """Get conversation recommendations."""
        recommendations = []
        
        # Semantic search
        similar_convs = await self.postgres.search_conversations_by_embedding(
            user_id=user_id,
            embedding=embedding,
            limit=limit * 2,  # Get more, we'll filter
            threshold=0.3
        )
        
        for conv in similar_convs:
            # Skip if part of a session and we're including sessions
            if exclude_session_convs and conv.get("session_id"):
                continue
            
            relevance = conv.get("similarity", 0)
            recency = self._calculate_recency_score(conv.get("created_at"))
            quality = self._calculate_conversation_quality(conv)
            
            # Topic bonus
            conv_topics = conv.get("topics", [])
            topic_overlap = len(set(topics) & set(conv_topics))
            if topic_overlap > 0:
                relevance = min(1.0, relevance + 0.1 * topic_overlap)
            
            final = (
                relevance * self.RELEVANCE_WEIGHT +
                recency * self.RECENCY_WEIGHT +
                quality * self.QUALITY_WEIGHT
            )
            
            # Generate name from summary or first message
            name = conv.get("summary", "")[:50] if conv.get("summary") else "Conversation"
            if not name or name == "Conversation":
                messages = conv.get("raw_messages", [])
                if messages:
                    first_msg = messages[0].get("content", "")[:50]
                    name = first_msg + "..." if len(first_msg) == 50 else first_msg
            
            rec = Recommendation(
                id=str(conv["id"]),
                type="conversation",
                name=name,
                summary=conv.get("summary"),
                source=conv.get("source"),
                topics=conv_topics,
                entities=conv.get("entities", []),
                score=RecommendationScore(
                    relevance_score=relevance,
                    recency_score=recency,
                    quality_score=quality,
                    final_score=final
                ),
                auto_select=False,
                conversation_count=1,
                last_activity=conv.get("created_at")
            )
            recommendations.append(rec)
        
        return recommendations[:limit]
    
    def _calculate_recency_score(self, timestamp) -> float:
        """Calculate recency score (0-1)."""
        if not timestamp:
            return 0.0
        
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return 0.0
        
        now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo else datetime.now()
        hours_ago = (now - timestamp).total_seconds() / 3600
        
        if hours_ago <= self.RECENT_HOURS:
            # High score for very recent
            return 1.0
        
        days_ago = hours_ago / 24
        if days_ago >= self.DECAY_DAYS:
            return 0.0
        
        # Linear decay
        return 1.0 - (days_ago / self.DECAY_DAYS)
    
    def _calculate_session_quality(self, session: dict) -> float:
        """Calculate quality score for a session."""
        score = 0.0
        
        # More conversations = higher quality
        conv_count = session.get("conversation_count", 0)
        if conv_count >= 5:
            score += 0.4
        elif conv_count >= 3:
            score += 0.3
        elif conv_count >= 1:
            score += 0.2
        
        # Has description
        if session.get("description"):
            score += 0.2
        
        # Has topics
        if session.get("topics"):
            score += 0.2
        
        # Has entities
        if session.get("entities"):
            score += 0.2
        
        return min(1.0, score)
    
    def _calculate_conversation_quality(self, conv: dict) -> float:
        """Calculate quality score for a conversation."""
        score = 0.0
        
        # Has summary
        if conv.get("summary"):
            score += 0.3
        
        # Has topics
        if conv.get("topics"):
            score += 0.2
        
        # Has entities
        if conv.get("entities"):
            score += 0.2
        
        # Message count (more = richer context)
        msg_count = conv.get("message_count", 0)
        if msg_count >= 10:
            score += 0.3
        elif msg_count >= 5:
            score += 0.2
        elif msg_count >= 2:
            score += 0.1
        
        return min(1.0, score)
    
    def _determine_auto_select(self, recommendations: List[Recommendation]) -> Optional[Recommendation]:
        """Determine if we should auto-select a recommendation."""
        if not recommendations:
            return None
        
        top = recommendations[0]
        
        # Must exceed threshold
        if top.score.final_score < self.AUTO_SELECT_THRESHOLD:
            return None
        
        # Must have clear margin over second-best
        if len(recommendations) > 1:
            second = recommendations[1]
            margin = top.score.final_score - second.score.final_score
            if margin < self.AUTO_SELECT_MARGIN:
                return None
        
        return top


async def get_recommendation_service(
    postgres: PostgresDB,
    neo4j: Neo4jDB,
    config
) -> RecommendationService:
    """Factory function to create RecommendationService."""
    embedding_config = {
        "api_key": config.openai_api_key,
        "model": config.embedding_model,
        "azure_endpoint": config.get_embedding_endpoint(),
        "azure_api_key": config.get_embedding_api_key(),
        "azure_api_version": config.azure_openai_api_version,
        "azure_deployment": config.get_embedding_deployment(),
        "provider": config.llm_provider
    }
    
    extraction_config = {
        "api_key": config.openai_api_key,
        "model": config.llm_model,
        "azure_endpoint": config.azure_openai_endpoint,
        "azure_api_key": config.azure_openai_api_key,
        "azure_api_version": config.azure_openai_api_version,
        "azure_deployment": config.azure_openai_deployment,
        "provider": config.llm_provider
    }
    
    return RecommendationService(postgres, neo4j, embedding_config, extraction_config)
