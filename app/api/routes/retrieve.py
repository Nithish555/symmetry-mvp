"""
Retrieve endpoint - Search memory and knowledge, return context.

Supports four modes:
- query: Returns context similar to a specific query
- full: Returns ALL user's knowledge (decisions, facts, entities, recent conversations)
- session: Returns all conversations in a specific session
- conversation: Returns full history of a specific conversation
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
import logging

from app.api.dependencies import get_postgres, get_neo4j, get_current_user_id, get_config
from app.db.postgres import PostgresDB
from app.db.neo4j import Neo4jDB
from app.config import Settings
from app.models.requests import RetrieveRequest
from app.models.responses import (
    RetrieveResponse, 
    DecisionInfo, 
    FactInfo, 
    SourceInfo,
    SessionInfo,
    ContradictionWarning,
    KnowledgeQuality,
    ChunkInfo
)
from app.services.embedding import generate_embedding
from app.services.summarization import generate_context_summary


router = APIRouter()
logger = logging.getLogger(__name__)


def _build_context_prompt(
    decisions: list,
    facts: list,
    entities: list,
    chunks: list,
    conversations: list = None,
    session: dict = None,
    mode: str = "query",
    contradictions: list = None,
    unverified_count: int = 0,
    custom_note: str = None,
    max_length: int = None
) -> str:
    """
    Build a ready-to-inject context prompt for cross-LLM conversations.
    
    Automatically:
    - Separates confirmed vs unconfirmed decisions
    - Shows contradiction warnings
    - Filters low-confidence items
    - Supports user customization (custom notes, length limits)
    """
    sections = []
    
    # Header
    sections.append("[CONTEXT FROM PREVIOUS AI CONVERSATIONS - PROVIDED BY SYMMETRY]")
    sections.append("")
    
    # ─────────────────────────────────────────────────────────────
    # USER'S CUSTOM NOTE (if provided)
    # ─────────────────────────────────────────────────────────────
    if custom_note:
        sections.append("## 📝 User Note:")
        sections.append(custom_note)
        sections.append("")
    
    # ─────────────────────────────────────────────────────────────
    # WARNINGS SECTION (if any issues detected)
    # ─────────────────────────────────────────────────────────────
    warnings = []
    if contradictions:
        for c in contradictions:
            warnings.append(f"⚠️ Contradiction: {c.message}")
    if unverified_count > 0:
        warnings.append(f"ℹ️ {unverified_count} item(s) have low confidence and are not verified")
    
    if warnings:
        sections.append("## ⚠️ Important Notes:")
        for w in warnings:
            sections.append(f"- {w}")
        sections.append("")
    
    # Session info if applicable
    if session and mode == "session":
        sections.append(f"## Session: {session.get('name', 'Unknown')}")
        if session.get("description"):
            sections.append(f"Description: {session['description']}")
        if session.get("topics"):
            sections.append(f"Topics: {', '.join(session['topics'])}")
        sections.append(f"Conversations in session: {session.get('conversation_count', 0)}")
        sections.append("")
    
    # For SESSION mode, include all conversations in order
    if mode == "session" and conversations:
        sections.append("## Complete Session History (chronological):")
        sections.append("")
        for conv in conversations:
            source = conv.get("source", "unknown")
            created = conv.get("created_at", "")
            sections.append(f"### [{source}] - {created}")
            messages = conv.get("raw_messages", [])
            for msg in messages:
                role = msg.get("role", "unknown").upper()
                content = msg.get("content", "")
                if len(content) > 800:
                    content = content[:800] + "... [truncated]"
                sections.append(f"**{role}**: {content}")
            sections.append("")
    
    # For FULL mode, include complete conversation history
    elif mode == "full" and conversations:
        sections.append("## Complete Conversation History:")
        sections.append("")
        for conv in conversations:
            source = conv.get("source", "unknown")
            messages = conv.get("raw_messages", [])
            sections.append(f"### Conversation from {source}:")
            for msg in messages:
                role = msg.get("role", "unknown").upper()
                content = msg.get("content", "")
                if len(content) > 500:
                    content = content[:500] + "... [truncated]"
                sections.append(f"**{role}**: {content}")
            sections.append("")
    
    # For CONVERSATION mode, include the specific conversation
    elif mode == "conversation" and conversations:
        sections.append("## Full Conversation:")
        sections.append("")
        for conv in conversations:
            messages = conv.get("raw_messages", [])
            for msg in messages:
                role = msg.get("role", "unknown").upper()
                content = msg.get("content", "")
                sections.append(f"**{role}**: {content}")
            sections.append("")
    
    # ─────────────────────────────────────────────────────────────
    # DECISIONS SECTION - Separated by confidence/status
    # ─────────────────────────────────────────────────────────────
    if decisions:
        # Separate confirmed decisions from uncertain ones
        confirmed = []
        exploring = []
        rejected = []
        
        for d in decisions:
            status = getattr(d, 'status', None) or 'decided'
            confidence = getattr(d, 'confidence', None) or 1.0
            verified = getattr(d, 'verified', None)
            
            if status == 'rejected':
                rejected.append(d)
            elif status == 'exploring' or confidence < 0.7:
                exploring.append(d)
            else:
                confirmed.append(d)
        
        # Show confirmed decisions prominently
        if confirmed:
            sections.append("## ✅ Confirmed Decisions:")
            for d in confirmed:
                reason_part = f" (Reason: {d.reason})" if d.reason else ""
                source_part = f" [via {d.source}]" if d.source else ""
                verified_mark = " ✓" if getattr(d, 'verified', False) else ""
                sections.append(f"- {d.content}{reason_part}{source_part}{verified_mark}")
            sections.append("")
        
        # Show exploring items with lower prominence
        if exploring:
            sections.append("## 🔍 Being Considered (not decided):")
            for d in exploring:
                confidence = getattr(d, 'confidence', 0.5)
                sections.append(f"- {d.content} (confidence: {confidence:.0%})")
            sections.append("")
        
        # Optionally show rejected items
        if rejected:
            sections.append("## ❌ Rejected Options:")
            for d in rejected:
                reason_part = f" - Reason: {d.reason}" if d.reason else ""
                sections.append(f"- {d.content}{reason_part}")
            sections.append("")
    
    # Facts section
    if facts:
        sections.append("## Current Facts:")
        for f in facts:
            sections.append(f"- {f.subject} {f.predicate} {f.object}")
        sections.append("")
    
    # Entities section
    if entities:
        sections.append("## Key Entities/Topics:")
        sections.append(f"- {', '.join(entities)}")
        sections.append("")
    
    # Relevant conversation snippets (for query mode)
    if mode == "query" and chunks:
        sections.append("## Relevant Past Discussions:")
        for c in chunks[:5]:
            content = c.get("content", "")
            if len(content) > 300:
                content = content[:300] + "..."
            sections.append(f"- {content}")
        sections.append("")
    
    # Instructions for the LLM
    sections.append("## Instructions:")
    sections.append("- Use this context to maintain conversation continuity")
    sections.append("- Don't ask questions the user has already answered")
    sections.append("- Reference past decisions when relevant")
    sections.append("- If the user contradicts a past decision, acknowledge it")
    if mode in ["full", "session"]:
        sections.append("- This is the user's COMPLETE context - use all of it as needed")
    sections.append("")
    sections.append("[END SYMMETRY CONTEXT]")
    
    result = "\n".join(sections)
    
    # ─────────────────────────────────────────────────────────────
    # APPLY LENGTH LIMIT (if specified)
    # ─────────────────────────────────────────────────────────────
    if max_length and len(result) > max_length:
        # Truncate intelligently - keep header and footer
        header = "[CONTEXT FROM PREVIOUS AI CONVERSATIONS - PROVIDED BY SYMMETRY]\n\n"
        footer = "\n\n[TRUNCATED - Context exceeded max length]\n[END SYMMETRY CONTEXT]"
        available = max_length - len(header) - len(footer)
        if available > 100:
            result = header + result[len(header):len(header) + available] + footer
        else:
            result = result[:max_length]
    
    return result


def _to_str(val):
    """Convert Neo4j DateTime or other types to string."""
    if val is None:
        return None
    return str(val)


def _extract_keywords(query: str) -> List[str]:
    """
    Extract meaningful keywords from a query for knowledge graph lookup.
    
    Simple approach:
    1. Remove common stop words
    2. Keep words with 3+ characters
    3. Return unique keywords
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
    
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for kw in keywords:
        if kw and kw not in seen:
            seen.add(kw)
            unique.append(kw)
    
    return unique[:10]  # Limit to 10 keywords


@router.post("/retrieve", response_model=RetrieveResponse, summary="Retrieve context for cross-LLM conversations")
async def retrieve_context(
    request: RetrieveRequest,
    user_id: str = Depends(get_current_user_id),
    postgres: PostgresDB = Depends(get_postgres),
    neo4j: Neo4jDB = Depends(get_neo4j),
    config: Settings = Depends(get_config)
):
    """
    Retrieve relevant context for continuing conversations across LLMs.
    
    **Modes:**
    - `query`: Returns context similar to the query (semantic search)
    - `full`: Returns ALL user's knowledge - decisions, facts, entities, and recent conversations
    - `session`: Returns all conversations in a specific session (chronological order)
    - `conversation`: Returns the complete history of a specific conversation
    
    **Use Cases:**
    - `query` mode: "What database did I choose?" → Returns PostgreSQL decision
    - `full` mode: "Continue my project" → Returns EVERYTHING about the project
    - `session` mode: "Continue this project session" → Returns all related conversations
    - `conversation` mode: "Continue this specific chat" → Returns full chat history
    """
    
    try:
        chunks = []
        conversations = []
        session = None
        
        # ═══════════════════════════════════════════════════════════════
        # MODE: QUERY - Semantic search with Knowledge Graph expansion
        # ═══════════════════════════════════════════════════════════════
        if request.mode == "query":
            if not request.query or not request.query.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": {
                            "code": "EMPTY_QUERY",
                            "message": "Query is required for 'query' mode"
                        }
                    }
                )
            
            logger.info(f"Query mode: searching for '{request.query[:50]}...'")
            
            # ─────────────────────────────────────────────────────────────
            # Step 1: Extract keywords from query
            # ─────────────────────────────────────────────────────────────
            query_keywords = _extract_keywords(request.query)
            logger.info(f"Extracted keywords: {query_keywords}")
            
            # ─────────────────────────────────────────────────────────────
            # Step 2: Expand query using Knowledge Graph (if available)
            # ─────────────────────────────────────────────────────────────
            expanded_terms = []
            if neo4j and neo4j.driver and query_keywords:
                try:
                    related_entities = await neo4j.find_related_entities(
                        user_id=user_id,
                        search_terms=query_keywords,
                        max_hops=2,
                        limit=10
                    )
                    expanded_terms = related_entities
                    if expanded_terms:
                        logger.info(f"Knowledge graph expansion: {expanded_terms}")
                except Exception as kg_error:
                    logger.warning(f"Knowledge graph expansion failed (non-critical): {kg_error}")
            
            # ─────────────────────────────────────────────────────────────
            # Step 3: Generate embedding for original query
            # ─────────────────────────────────────────────────────────────
            query_embedding = await generate_embedding(
                text=request.query,
                api_key=config.openai_api_key,
                model=config.embedding_model,
                azure_endpoint=config.get_embedding_endpoint(),
                azure_api_key=config.get_embedding_api_key(),
                azure_api_version=config.azure_openai_api_version,
                azure_deployment=config.get_embedding_deployment(),
                provider=config.llm_provider
            )
            
            # ─────────────────────────────────────────────────────────────
            # Step 4: Search with hybrid approach (semantic + keywords)
            # ─────────────────────────────────────────────────────────────
            # Combine original keywords with graph-expanded terms
            all_search_terms = list(set(query_keywords + expanded_terms))
            
            if all_search_terms:
                # Use hybrid search with knowledge graph expanded terms
                chunks = await postgres.search_chunks_hybrid(
                    user_id=user_id,
                    embedding=query_embedding,
                    keywords=all_search_terms,
                    limit=request.limit,
                    semantic_weight=0.7  # 70% semantic, 30% keyword
                )
                logger.info(f"Hybrid search with {len(all_search_terms)} terms, found {len(chunks)} chunks")
            else:
                # Fallback to pure semantic search
                chunks = await postgres.search_chunks(
                    user_id=user_id,
                    embedding=query_embedding,
                    limit=request.limit,
                    threshold=config.similarity_threshold
                )
        
        # ═══════════════════════════════════════════════════════════════
        # MODE: FULL - Return ALL user's context
        # ═══════════════════════════════════════════════════════════════
        elif request.mode == "full":
            logger.info("Full mode: retrieving all context")
            
            # Get recent conversations (full messages)
            conversations = await postgres.get_recent_conversations(
                user_id=user_id,
                limit=request.limit
            )
        
        # ═══════════════════════════════════════════════════════════════
        # MODE: SESSION - Return all conversations in a session
        # ═══════════════════════════════════════════════════════════════
        elif request.mode == "session":
            if not request.session_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": {
                            "code": "MISSING_SESSION_ID",
                            "message": "session_id is required for 'session' mode"
                        }
                    }
                )
            
            logger.info(f"Session mode: retrieving session {request.session_id}")
            
            # Get session details
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
            
            # Get all conversations in session (chronological order)
            conversations = await postgres.get_conversations_by_session(
                session_id=request.session_id,
                user_id=user_id
            )
        
        # ═══════════════════════════════════════════════════════════════
        # MODE: CONVERSATION - Return specific conversation
        # ═══════════════════════════════════════════════════════════════
        elif request.mode == "conversation":
            if not request.conversation_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": {
                            "code": "MISSING_CONVERSATION_ID",
                            "message": "conversation_id is required for 'conversation' mode"
                        }
                    }
                )
            
            logger.info(f"Conversation mode: retrieving conversation {request.conversation_id}")
            
            # Get specific conversation
            conversation = await postgres.get_conversation(
                conversation_id=request.conversation_id,
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
            
            conversations = [conversation]
            
            # If conversation is in a session, get session info
            if conversation.get("session_id"):
                session = await postgres.get_session(
                    str(conversation["session_id"]), 
                    user_id
                )
        
        # ═══════════════════════════════════════════════════════════════
        # KNOWLEDGE LAYER - Fetch if available (optional)
        # ═══════════════════════════════════════════════════════════════
        decisions = []
        facts = []
        entities = []
        contradictions_raw = []
        unverified_items = []
        
        # Also fetch exploring and rejected items for full context
        exploring_items = []
        rejected_items = []
        
        if neo4j and neo4j.driver:
            try:
                # Get all categorized knowledge
                # Apply user's customization preferences
                decisions = await neo4j.get_decisions(
                    user_id, 
                    include_low_confidence=False,
                    include_past=False,
                    include_others_suggestions=request.include_others_suggestions
                )
                
                # Filter by verified if requested
                if request.only_verified:
                    decisions = [d for d in decisions if d.get("verified")]
                
                # Also get exploring items (if user wants them)
                if request.include_exploring:
                    exploring_items = await neo4j.get_exploring(user_id)
                    if request.only_verified:
                        exploring_items = [e for e in exploring_items if e.get("verified")]
                
                # And rejected items (if user wants them)
                if request.include_rejected:
                    rejected_items = await neo4j.get_rejected(user_id)
                
                facts = await neo4j.get_current_facts(user_id)
                entities = await neo4j.get_entities(user_id)
                
                # Check for contradictions
                contradictions_raw = await neo4j.detect_contradictions(user_id)
                
                # Get unverified knowledge count
                unverified_items = await neo4j.get_unverified_knowledge(user_id, limit=100)
                
                # ═══════════════════════════════════════════════════════════
                # APPLY USER EXCLUSIONS
                # ═══════════════════════════════════════════════════════════
                if request.exclude_entities:
                    exclude_set = set(e.lower() for e in request.exclude_entities)
                    decisions = [d for d in decisions 
                                 if d.get("target", "").lower() not in exclude_set 
                                 and d.get("decision", "").lower() not in exclude_set]
                    exploring_items = [e for e in exploring_items 
                                       if e.get("target", "").lower() not in exclude_set]
                    rejected_items = [r for r in rejected_items 
                                      if r.get("target", "").lower() not in exclude_set]
                    entities = [e for e in entities 
                                if e.get("name", "").lower() not in exclude_set]
                
                if request.exclude_decision_ids:
                    exclude_ids = set(request.exclude_decision_ids)
                    decisions = [d for d in decisions if d.get("id") not in exclude_ids]
                    exploring_items = [e for e in exploring_items if e.get("id") not in exclude_ids]
                    rejected_items = [r for r in rejected_items if r.get("id") not in exclude_ids]
                    
            except Exception as neo4j_error:
                logger.warning(f"Neo4j query failed (non-critical): {neo4j_error}")
                # Continue with empty knowledge - Memory Layer still works
        else:
            logger.info("Neo4j not available - returning Memory Layer only")
        
        # ═══════════════════════════════════════════════════════════════
        # FORMAT RESPONSE
        # ═══════════════════════════════════════════════════════════════
        # Build decision list with full metadata
        decision_list = []
        
        # Add confirmed decisions (status=decided)
        for d in decisions:
            decision_list.append(DecisionInfo(
                content=d.get("decision", d.get("target", "")),
                reason=_to_str(d.get("reason")),
                date=_to_str(d.get("date")),
                source=_to_str(d.get("source")),
                confidence=d.get("confidence"),
                status="decided",
                verified=d.get("verified"),
                attributed_to=d.get("attributed_to"),
                temporal=d.get("temporal"),
                note=None
            ))
        
        # Add exploring items (status=exploring)
        for e in exploring_items:
            decision_list.append(DecisionInfo(
                content=e.get("target", ""),
                reason=_to_str(e.get("reason")),
                date=_to_str(e.get("date")),
                source=_to_str(e.get("source")),
                confidence=e.get("confidence"),
                status="exploring",
                verified=False,
                attributed_to=e.get("attributed_to"),
                temporal="current",
                note="Being considered, not decided"
            ))
        
        # Add rejected items (status=rejected)
        for r in rejected_items:
            decision_list.append(DecisionInfo(
                content=r.get("target", ""),
                reason=_to_str(r.get("reason")),
                date=_to_str(r.get("date")),
                source=_to_str(r.get("source")),
                confidence=r.get("confidence"),
                status="rejected",
                verified=False,
                attributed_to="user",
                temporal="current",
                note="User explicitly rejected this"
            ))
        
        # Format contradictions
        contradiction_list = [
            ContradictionWarning(
                old_decision=c.get("old_decision", c.get("target", "")),
                old_date=_to_str(c.get("old_date", c.get("rejected_date"))),
                new_decision=c.get("new_decision", c.get("target", "")),
                new_date=_to_str(c.get("new_date", c.get("chose_date"))),
                category=c.get("category"),
                message=f"You previously {'rejected' if c.get('conflict_type') == 'rejected_then_chose' else 'chose'} {c.get('old_decision', c.get('target', 'this'))}, but later chose {c.get('new_decision', c.get('target', 'something else'))}"
            )
            for c in contradictions_raw
        ]
        
        fact_list = [
            FactInfo(
                subject=f.get("subject", ""),
                predicate=f.get("predicate", ""),
                object=f.get("object", ""),
                since=_to_str(f.get("since"))
            )
            for f in facts
        ]
        
        entity_list = [e.get("name", "") for e in entities]
        
        source_list = [
            SourceInfo(
                source=c.get("source", "unknown"),
                date=c.get("created_at")
            )
            for c in (chunks if chunks else conversations)
        ]
        
        # Build context_prompt based on mode
        # Include warnings so LLMs are aware of potential issues
        context_prompt = _build_context_prompt(
            decisions=decision_list,
            facts=fact_list,
            entities=entity_list,
            chunks=chunks,
            conversations=conversations,
            session=session,
            mode=request.mode,
            contradictions=contradiction_list,
            unverified_count=len(unverified_items),
            custom_note=request.custom_note,
            max_length=request.max_context_length
        )
        
        # ═══════════════════════════════════════════════════════════════
        # SUMMARY GENERATION (with user customization options)
        # ═══════════════════════════════════════════════════════════════
        summary = ""
        
        if request.custom_summary:
            # User provided their own summary - use it directly
            summary = request.custom_summary
            logger.info("Using user-provided custom summary")
        
        elif request.skip_summary_generation:
            # Skip LLM call - use stored summary from conversation/session
            if request.mode == "conversation" and conversations:
                summary = conversations[0].get("summary", "") or "No stored summary available"
            elif request.mode == "session" and session:
                summary = session.get("description", "") or "No session description available"
            else:
                summary = "Summary generation skipped"
            logger.info("Using stored summary (skip_summary_generation=true)")
        
        else:
            # Generate summary using LLM (default behavior)
            summary_query = request.query if request.mode == "query" else "Provide full context summary"
            summary = await generate_context_summary(
                query=summary_query,
                chunks=chunks,
                decisions=decisions,
                facts=facts,
                entities=entities,
                api_key=config.openai_api_key,
                model=config.llm_model,
                azure_endpoint=config.azure_openai_endpoint,
                azure_api_key=config.azure_openai_api_key,
                azure_api_version=config.azure_openai_api_version,
                azure_deployment=config.azure_openai_deployment,
                provider=config.llm_provider
            )
        
        # Session info for response
        session_info = None
        if session:
            session_info = SessionInfo(
                id=str(session["id"]),
                name=session["name"],
                description=session.get("description"),
                topics=session.get("topics", []),
                entities=session.get("entities", []),
                conversation_count=session.get("conversation_count", 0),
                created_at=session["created_at"],
                last_activity=session.get("last_activity")
            )
        
        # ═══════════════════════════════════════════════════════════════
        # CALCULATE KNOWLEDGE QUALITY
        # ═══════════════════════════════════════════════════════════════
        confirmed_count = sum(1 for d in decision_list if d.status == "decided" and d.confidence and d.confidence >= 0.8)
        exploring_count = sum(1 for d in decision_list if d.status == "exploring")
        rejected_count = sum(1 for d in decision_list if d.status == "rejected")
        others_count = sum(1 for d in decision_list if d.attributed_to and d.attributed_to != "user")
        past_count = sum(1 for d in decision_list if d.temporal == "past")
        
        # Calculate quality score (0-100)
        quality_score = 100
        quality_notes = []
        
        if len(contradiction_list) > 0:
            quality_score -= 15 * len(contradiction_list)
            quality_notes.append(f"{len(contradiction_list)} contradiction(s) detected")
        
        if len(unverified_items) > 5:
            quality_score -= 10
            quality_notes.append(f"{len(unverified_items)} items not verified by user")
        
        if exploring_count > confirmed_count:
            quality_score -= 5
            quality_notes.append("More items being explored than decided")
        
        if others_count > 0:
            quality_notes.append(f"{others_count} item(s) from others (colleagues/articles)")
        
        if past_count > 0:
            quality_notes.append(f"{past_count} historical item(s) included")
        
        quality_score = max(0, min(100, quality_score))  # Clamp to 0-100
        
        knowledge_quality = KnowledgeQuality(
            total_decisions=len(decision_list),
            confirmed_decisions=confirmed_count,
            exploring_count=exploring_count,
            rejected_count=rejected_count,
            unverified_count=len(unverified_items),
            contradictions_count=len(contradiction_list),
            others_suggestions=others_count,
            past_items=past_count,
            quality_score=quality_score,
            quality_notes=quality_notes
        )
        
        # Build chunk list for custom prompt building
        chunk_list = [
            ChunkInfo(
                id=str(c.get("id", "")),
                content=c.get("content", ""),
                source=c.get("source"),
                conversation_id=str(c.get("conversation_id", "")) if c.get("conversation_id") else None,
                similarity=c.get("similarity") or c.get("semantic_similarity")
            )
            for c in (chunks or [])
        ]
        
        return RetrieveResponse(
            summary=summary,
            context_prompt=context_prompt,
            decisions=decision_list,
            facts=fact_list,
            entities=entity_list,
            sources=source_list,
            chunks_found=len(chunks) if chunks else len(conversations),
            session=session_info,
            contradictions=contradiction_list,
            unverified_count=len(unverified_items),
            knowledge_quality=knowledge_quality,
            chunks=chunk_list
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Retrieval failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "RETRIEVAL_FAILED",
                    "message": f"Failed to retrieve context: {str(e)}"
                }
            }
        )
