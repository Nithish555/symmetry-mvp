"""
Ingest endpoint - Store conversations and extract knowledge.
Enhanced with session suggestion and auto-linking.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import logging

from app.api.dependencies import get_postgres, get_neo4j, get_current_user_id, get_config
from app.db.postgres import PostgresDB
from app.db.neo4j import Neo4jDB
from app.config import Settings
from app.models.requests import IngestRequest, Message
from app.models.responses import (
    IngestResponse, 
    SessionSuggestionResponse, 
    SessionSuggestion,
    SessionInfo
)
from app.services.chunking import chunk_conversation
from app.services.embedding import generate_embeddings, generate_embedding
from app.services.extraction import extract_knowledge, generate_conversation_summary
from app.services.session import get_session_service


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_conversation(
    request: IngestRequest,
    user_id: str = Depends(get_current_user_id),
    postgres: PostgresDB = Depends(get_postgres),
    neo4j: Neo4jDB = Depends(get_neo4j),
    config: Settings = Depends(get_config)
):
    """
    Ingest a conversation into Symmetry.
    
    This endpoint:
    1. Stores the raw conversation (Memory Layer)
    2. Generates summary and extracts topics/entities
    3. Chunks and embeds the text for semantic search
    4. Extracts entities and relationships (Knowledge Layer)
    5. Stores knowledge in the graph database
    6. Suggests session linking (if auto_link_session is true)
    
    **Session Handling:**
    - If `session_id` is provided, the conversation is linked to that session
    - If `auto_link_session` is true (default), the system analyzes the conversation
      and suggests linking to an existing session if a good match is found
    - High-confidence matches (>85%) are auto-linked
    - Medium-confidence matches (70-85%) are suggested for user confirmation
    """
    
    if not request.messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "EMPTY_MESSAGES",
                    "message": "At least one message is required"
                }
            }
        )
    
    # ═══════════════════════════════════════════════════════════════
    # APPEND MODE: If conversation_id provided, handle appending
    # ═══════════════════════════════════════════════════════════════
    # 
    # Two sub-modes:
    # 1. append_only=false (default): messages contains ALL messages, we find new ones
    # 2. append_only=true: messages contains ONLY new messages to append directly
    #
    # ═══════════════════════════════════════════════════════════════
    
    existing_conversation = None
    messages_to_process = request.messages
    all_messages_for_summary = request.messages  # For generating summary
    is_append = False
    
    if request.conversation_id:
        logger.info(f"Append mode: checking existing conversation {request.conversation_id}")
        existing_conversation = await postgres.get_conversation(request.conversation_id, user_id)
        
        if not existing_conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "CONVERSATION_NOT_FOUND",
                        "message": f"Conversation {request.conversation_id} not found"
                    }
                }
            )
        
        existing_messages = existing_conversation.get("raw_messages", [])
        existing_count = len(existing_messages)
        
        if request.append_only:
            # ─────────────────────────────────────────────────────────────
            # APPEND_ONLY MODE: messages contains ONLY new messages
            # Extension sends just the new messages, we append directly
            # ─────────────────────────────────────────────────────────────
            logger.info(f"Append-only mode: {len(request.messages)} new messages to append")
            
            if not request.messages:
                return IngestResponse(
                    conversation_id=request.conversation_id,
                    chunks_created=0,
                    entities_extracted=0,
                    relationships_created=0,
                    status="no_new_messages",
                    message="No new messages provided."
                )
            
            # Messages to process = all incoming (they're all new)
            messages_to_process = request.messages
            
            # For summary, combine existing + new
            existing_as_models = [
                Message(role=m["role"], content=m["content"]) 
                for m in existing_messages
            ]
            all_messages_for_summary = existing_as_models + list(request.messages)
            is_append = True
            
            logger.info(f"Append-only: {existing_count} existing + {len(request.messages)} new = {len(all_messages_for_summary)} total")
        
        else:
            # ─────────────────────────────────────────────────────────────
            # COMPARE MODE (default): messages contains ALL messages
            # We compare with existing to find which are new
            # ─────────────────────────────────────────────────────────────
            new_count = len(request.messages)
            
            if new_count <= existing_count:
                # No new messages
                return IngestResponse(
                    conversation_id=request.conversation_id,
                    chunks_created=0,
                    entities_extracted=0,
                    relationships_created=0,
                    status="no_new_messages",
                    message="No new messages to process. Conversation unchanged."
                )
            
            # Extract only the NEW messages (messages after the existing ones)
            new_messages = request.messages[existing_count:]
            messages_to_process = new_messages
            all_messages_for_summary = request.messages  # Already has all
            is_append = True
            
            logger.info(f"Compare mode: {existing_count} existing, {len(new_messages)} new messages to process")
    
    try:
        # ═══════════════════════════════════════════════════════════════
        # Step 1: Generate summary and extract metadata
        # ═══════════════════════════════════════════════════════════════
        # Use all_messages_for_summary (includes existing + new in append mode)
        logger.info("Generating conversation summary...")
        summary_result = await generate_conversation_summary(
            messages=[msg.model_dump() for msg in all_messages_for_summary],
            api_key=config.openai_api_key,
            model=config.llm_model,
            azure_endpoint=config.azure_openai_endpoint,
            azure_api_key=config.azure_openai_api_key,
            azure_api_version=config.azure_openai_api_version,
            azure_deployment=config.azure_openai_deployment,
            provider=config.llm_provider
        )
        
        summary = summary_result.get("summary", "")
        topics = summary_result.get("topics", [])
        entities = summary_result.get("entities", [])
        
        # ═══════════════════════════════════════════════════════════════
        # Step 2: Generate conversation-level embedding
        # ═══════════════════════════════════════════════════════════════
        # Use all_messages_for_summary for embedding (includes existing + new in append mode)
        logger.info("Generating conversation embedding...")
        conv_text = summary if summary else "\n".join([
            f"{m.role}: {m.content}" for m in all_messages_for_summary
        ])[:4000]
        
        conv_embedding = await generate_embedding(
            text=conv_text,
            api_key=config.openai_api_key,
            model=config.embedding_model,
            azure_endpoint=config.get_embedding_endpoint(),
            azure_api_key=config.get_embedding_api_key(),
            azure_api_version=config.azure_openai_api_version,
            azure_deployment=config.get_embedding_deployment(),
            provider=config.llm_provider
        )
        
        # ═══════════════════════════════════════════════════════════════
        # Step 3: Session linking logic
        # ═══════════════════════════════════════════════════════════════
        # 
        # Behavior:
        # - If session_id provided: Link to that session (explicit)
        # - Otherwise: ALWAYS analyze and provide suggestions
        #   - If auto_link_session=true AND confidence>85%: Auto-link
        #   - If auto_link_session=false OR confidence<=85%: Just suggest, don't link
        #
        # This ensures users ALWAYS get suggestions for informed decisions,
        # but retain control when auto_link_session=false.
        # ═══════════════════════════════════════════════════════════════
        
        session_id = request.session_id
        session_suggestion = None
        linked_session_id = None
        auto_linked = False
        
        if request.session_id:
            # User explicitly specified a session - use it directly
            session = await postgres.get_session(request.session_id, user_id)
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": {
                            "code": "SESSION_NOT_FOUND",
                            "message": "Specified session not found"
                        }
                    }
                )
            linked_session_id = request.session_id
            logger.info(f"Using explicitly specified session: {request.session_id}")
        
        else:
            # ALWAYS analyze for suggestions (regardless of auto_link_session)
            # This ensures users always get recommendations to make informed decisions
            logger.info("Analyzing conversation for session suggestions...")
            session_service = await get_session_service(postgres, config)
            
            try:
                analysis = await session_service.analyze_conversation(
                    messages=[msg.model_dump() for msg in request.messages],
                    user_id=user_id
                )
                
                if analysis["suggested_session"]:
                    suggested = analysis["suggested_session"]
                    
                    # Determine if we should auto-link:
                    # Only auto-link if BOTH conditions are met:
                    # 1. auto_link_session is True (user wants auto-linking)
                    # 2. confidence is high enough (analysis["auto_link"] = True)
                    should_auto_link = request.auto_link_session and analysis["auto_link"]
                    
                    # Build session suggestion response
                    from datetime import datetime
                    session_suggestion = SessionSuggestionResponse(
                        suggested_session=SessionInfo(
                            id=str(suggested["id"]),
                            name=suggested["name"],
                            description=suggested.get("description"),
                            topics=suggested.get("topics", []),
                            entities=suggested.get("entities", []),
                            conversation_count=suggested.get("conversation_count", 0),
                            created_at=suggested.get("created_at") or datetime.now(),
                            last_activity=suggested.get("last_activity")
                        ),
                        confidence=analysis["confidence"],
                        auto_linked=should_auto_link,  # Reflects actual linking decision
                        all_suggestions=[
                            SessionSuggestion(
                                session_id=s["session_id"],
                                name=s["name"],
                                score=s["score"],
                                topics=s.get("topics", []),
                                conversation_count=s.get("conversation_count", 0)
                            )
                            for s in analysis["all_matches"]
                        ],
                        reason=analysis["reason"]
                    )
                    
                    # Only auto-link if user enabled it AND confidence is high
                    if should_auto_link:
                        session_id = str(suggested["id"])
                        linked_session_id = session_id
                        auto_linked = True
                        logger.info(f"Auto-linking to session: {suggested['name']} (confidence: {analysis['confidence']:.2f})")
                    else:
                        # Log why we didn't auto-link
                        if not request.auto_link_session:
                            logger.info(f"Suggestion available but auto_link_session=false. User can manually link to: {suggested['name']}")
                        else:
                            logger.info(f"Suggestion available but confidence too low ({analysis['confidence']:.2f}). Suggesting: {suggested['name']}")
                else:
                    logger.info("No similar sessions found - conversation will be standalone")
                    
            except Exception as session_error:
                logger.warning(f"Session analysis failed (non-critical): {session_error}")
                # Continue without session linking - conversation will be standalone
        
        # ═══════════════════════════════════════════════════════════════
        # Step 4: Store conversation (CREATE or UPDATE)
        # ═══════════════════════════════════════════════════════════════
        
        if is_append and existing_conversation:
            # APPEND MODE: Update existing conversation
            logger.info(f"Appending to existing conversation {request.conversation_id}...")
            
            # Merge old and new messages
            all_messages = existing_conversation.get("raw_messages", []) + [msg.model_dump() for msg in messages_to_process]
            
            # Merge topics and entities (deduplicate)
            merged_topics = list(set(existing_conversation.get("topics", []) + topics))
            merged_entities = list(set(existing_conversation.get("entities", []) + entities))
            
            # Update conversation with all data
            await postgres.update_conversation(
                conversation_id=request.conversation_id,
                user_id=user_id,
                raw_messages=all_messages,
                summary=summary,  # New summary covers full conversation
                topics=merged_topics,
                entities=merged_entities,
                embedding=conv_embedding
            )
            conversation_id = request.conversation_id
            
            # Keep existing session_id if not explicitly changing
            if not session_id and existing_conversation.get("session_id"):
                session_id = str(existing_conversation["session_id"])
                linked_session_id = session_id
        else:
            # CREATE MODE: New conversation
            logger.info("Storing new conversation...")
            conversation = await postgres.create_conversation(
                user_id=user_id,
                source=request.source,
                raw_messages=[msg.model_dump() for msg in request.messages],
                session_id=session_id,
                summary=summary,
                topics=topics,
                entities=entities
            )
            conversation_id = str(conversation["id"])
            
            # Update with embedding
            await postgres.update_conversation(
                conversation_id=conversation_id,
                user_id=user_id,
                embedding=conv_embedding
            )
        
        # ═══════════════════════════════════════════════════════════════
        # Step 5: Record session suggestion for learning
        # ═══════════════════════════════════════════════════════════════
        if session_suggestion and session_suggestion.suggested_session:
            await postgres.create_session_suggestion(
                conversation_id=conversation_id,
                suggested_session_id=session_suggestion.suggested_session.id,
                confidence=session_suggestion.confidence
            )
            
            # If auto-linked, mark as accepted
            if auto_linked:
                await postgres.update_session_suggestion(
                    conversation_id=conversation_id,
                    accepted=True,
                    actual_session_id=linked_session_id
                )
        
        # ═══════════════════════════════════════════════════════════════
        # Step 6: Chunk and embed for semantic search
        # ═══════════════════════════════════════════════════════════════
        # In APPEND mode: only chunk the NEW messages
        # In CREATE mode: chunk all messages
        
        logger.info("Chunking conversation...")
        chunks = chunk_conversation(
            messages=messages_to_process,  # Only new messages in append mode
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap
        )
        
        # Get starting chunk index (for append mode, continue from existing chunks)
        chunk_start_index = 0
        if is_append:
            # Get count of existing chunks for this conversation
            existing_chunks = await postgres.get_chunks_by_conversation(conversation_id, user_id)
            chunk_start_index = len(existing_chunks) if existing_chunks else 0
            logger.info(f"Append mode: starting chunk index at {chunk_start_index}")
        
        logger.info(f"Generating embeddings for {len(chunks)} chunks...")
        embeddings = await generate_embeddings(
            texts=chunks,
            api_key=config.openai_api_key,
            model=config.embedding_model,
            azure_endpoint=config.get_embedding_endpoint(),
            azure_api_key=config.get_embedding_api_key(),
            azure_api_version=config.azure_openai_api_version,
            azure_deployment=config.get_embedding_deployment(),
            provider=config.llm_provider
        )
        
        # Store chunks (with correct index for append mode)
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            await postgres.create_chunk(
                conversation_id=conversation_id,
                user_id=user_id,
                content=chunk_text,
                embedding=embedding,
                chunk_index=chunk_start_index + idx
            )
        
        # ═══════════════════════════════════════════════════════════════
        # Step 7: Extract knowledge (entities, relationships, facts)
        # ═══════════════════════════════════════════════════════════════
        entities_created = 0
        relationships_created = 0
        knowledge = {"entities": [], "relationships": [], "facts": []}
        
        # Knowledge extraction and Neo4j storage is optional
        # System works without it (Memory Layer only)
        if neo4j and neo4j.driver:
            try:
                logger.info("Extracting knowledge...")
                knowledge = await extract_knowledge(
                    messages=request.messages,
                    api_key=config.openai_api_key,
                    model=config.llm_model,
                    azure_endpoint=config.azure_openai_endpoint,
                    azure_api_key=config.azure_openai_api_key,
                    azure_api_version=config.azure_openai_api_version,
                    azure_deployment=config.azure_openai_deployment,
                    provider=config.llm_provider
                )
                
                # ═══════════════════════════════════════════════════════════════
                # Step 8: Store knowledge in Neo4j
                # ═══════════════════════════════════════════════════════════════
                # Ensure User node exists
                await neo4j.ensure_user_node(user_id)
                
                # Create entity nodes
                for entity in knowledge.get("entities", []):
                    await neo4j.create_entity(
                        user_id=user_id,
                        name=entity["name"],
                        entity_type=entity["type"],
                        description=entity.get("description")
                    )
                    entities_created += 1
                
                # Create relationships with full metadata
                for rel in knowledge.get("relationships", []):
                    # Extract all metadata from extraction
                    confidence = rel.get("confidence", 0.5)  # Default to medium confidence
                    status = rel.get("status", "exploring")  # Default to exploring (safe)
                    attributed_to = rel.get("attributed_to", "user")  # Who said this
                    temporal = rel.get("temporal", "current")  # Is this current or past
                    
                    # Map relationship type to status if not explicitly provided
                    if status == "exploring" and rel["type"] in ["CHOSE", "DECIDED"]:
                        status = "decided"
                    elif rel["type"] == "REJECTED":
                        status = "rejected"
                    elif rel["type"] == "CONSIDERING":
                        status = "exploring"
                    elif rel["type"] == "USED":
                        temporal = "past"  # USED implies past usage
                    
                    await neo4j.create_relationship(
                        user_id=user_id,
                        source_name=rel["source"],
                        target_name=rel["target"],
                        relationship_type=rel["type"],
                        properties=rel.get("properties", {}),
                        conversation_id=conversation_id,
                        source_platform=request.source,
                        confidence=confidence,
                        status=status,
                        attributed_to=attributed_to,
                        temporal=temporal
                    )
                    relationships_created += 1
                
                # Create temporal facts
                for fact in knowledge.get("facts", []):
                    await neo4j.create_temporal_fact(
                        user_id=user_id,
                        subject=fact["subject"],
                        predicate=fact["predicate"],
                        obj=fact["object"],
                        valid_from=fact.get("valid_from"),
                        valid_to=fact.get("valid_to")
                    )
            except Exception as neo4j_error:
                logger.warning(f"Neo4j knowledge extraction failed (non-critical): {neo4j_error}")
                # Continue without knowledge layer - Memory Layer still works
        else:
            logger.info("Neo4j not available - skipping knowledge extraction")
        
        # Update conversation flags (if knowledge was extracted)
        if knowledge.get("relationships") or knowledge.get("facts"):
            has_decisions = any(
                rel["type"] in ["CHOSE", "DECIDED"] 
                for rel in knowledge.get("relationships", [])
            )
            has_facts = len(knowledge.get("facts", [])) > 0
            
            if has_decisions or has_facts:
                await postgres.update_conversation(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    has_decisions=has_decisions,
                    has_facts=has_facts
                )
        
        # ═══════════════════════════════════════════════════════════════
        # Step 9: Update session embedding if linked
        # ═══════════════════════════════════════════════════════════════
        if linked_session_id:
            session_service = await get_session_service(postgres, config)
            await session_service._update_session_embedding(linked_session_id, user_id)
        
        logger.info(f"Ingestion complete: {len(chunks)} chunks, {entities_created} entities, append={is_append}")
        
        return IngestResponse(
            conversation_id=conversation_id,
            chunks_created=len(chunks),
            entities_extracted=entities_created,
            relationships_created=relationships_created,
            status="appended" if is_append else "success",
            message=f"Appended {len(messages_to_process)} new messages" if is_append else None,
            session_suggestion=session_suggestion,
            linked_session_id=linked_session_id,
            is_append=is_append,
            new_messages_count=len(messages_to_process) if is_append else len(request.messages)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ingestion failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INGESTION_FAILED",
                    "message": f"Failed to ingest conversation: {str(e)}"
                }
            }
        )
