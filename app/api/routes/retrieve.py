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
    SessionInfo
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
    mode: str = "query"
) -> str:
    """
    Build a ready-to-inject context prompt for cross-LLM conversations.
    """
    sections = []
    
    # Header
    sections.append("[CONTEXT FROM PREVIOUS AI CONVERSATIONS - PROVIDED BY SYMMETRY]")
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
    
    # Decisions section
    if decisions:
        sections.append("## Key Decisions Made:")
        for d in decisions:
            reason_part = f" (Reason: {d.reason})" if d.reason else ""
            source_part = f" [via {d.source}]" if d.source else ""
            sections.append(f"- {d.content}{reason_part}{source_part}")
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
    
    return "\n".join(sections)


def _to_str(val):
    """Convert Neo4j DateTime or other types to string."""
    if val is None:
        return None
    return str(val)


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
        # MODE: QUERY - Semantic search for relevant context
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
            
            # Generate embedding for query
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
            
            # Search for relevant chunks
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
        
        if neo4j and neo4j.driver:
            try:
                decisions = await neo4j.get_decisions(user_id)
                facts = await neo4j.get_current_facts(user_id)
                entities = await neo4j.get_entities(user_id)
            except Exception as neo4j_error:
                logger.warning(f"Neo4j query failed (non-critical): {neo4j_error}")
                # Continue with empty knowledge - Memory Layer still works
        else:
            logger.info("Neo4j not available - returning Memory Layer only")
        
        # ═══════════════════════════════════════════════════════════════
        # FORMAT RESPONSE
        # ═══════════════════════════════════════════════════════════════
        decision_list = [
            DecisionInfo(
                content=d.get("decision", ""),
                reason=_to_str(d.get("reason")),
                date=_to_str(d.get("date")),
                source=_to_str(d.get("source"))
            )
            for d in decisions
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
        context_prompt = _build_context_prompt(
            decisions=decision_list,
            facts=fact_list,
            entities=entity_list,
            chunks=chunks,
            conversations=conversations,
            session=session,
            mode=request.mode
        )
        
        # Generate summary
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
        
        return RetrieveResponse(
            summary=summary,
            context_prompt=context_prompt,
            decisions=decision_list,
            facts=fact_list,
            entities=entity_list,
            sources=source_list,
            chunks_found=len(chunks) if chunks else len(conversations),
            session=session_info
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
