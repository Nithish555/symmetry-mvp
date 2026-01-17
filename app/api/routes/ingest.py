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
from app.models.requests import IngestRequest
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
    
    try:
        # ═══════════════════════════════════════════════════════════════
        # Step 1: Generate summary and extract metadata
        # ═══════════════════════════════════════════════════════════════
        logger.info("Generating conversation summary...")
        summary_result = await generate_conversation_summary(
            messages=[msg.model_dump() for msg in request.messages],
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
        logger.info("Generating conversation embedding...")
        conv_text = summary if summary else "\n".join([
            f"{m.role}: {m.content}" for m in request.messages
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
        session_id = request.session_id
        session_suggestion = None
        linked_session_id = None
        auto_linked = False
        
        if request.session_id:
            # User explicitly specified a session
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
        
        elif request.auto_link_session:
            # Analyze and suggest session
            logger.info("Analyzing conversation for session linking...")
            session_service = await get_session_service(postgres, config)
            analysis = await session_service.analyze_conversation(
                messages=[msg.model_dump() for msg in request.messages],
                user_id=user_id
            )
            
            if analysis["suggested_session"]:
                suggested = analysis["suggested_session"]
                
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
                    auto_linked=analysis["auto_link"],
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
                
                # Auto-link if high confidence
                if analysis["auto_link"]:
                    session_id = str(suggested["id"])
                    linked_session_id = session_id
                    auto_linked = True
                    logger.info(f"Auto-linking to session: {suggested['name']}")
        
        # ═══════════════════════════════════════════════════════════════
        # Step 4: Store conversation
        # ═══════════════════════════════════════════════════════════════
        logger.info("Storing conversation...")
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
        logger.info("Chunking conversation...")
        chunks = chunk_conversation(
            messages=request.messages,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap
        )
        
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
        
        # Store chunks
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            await postgres.create_chunk(
                conversation_id=conversation_id,
                user_id=user_id,
                content=chunk_text,
                embedding=embedding,
                chunk_index=idx
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
                
                # Create relationships
                for rel in knowledge.get("relationships", []):
                    await neo4j.create_relationship(
                        user_id=user_id,
                        source_name=rel["source"],
                        target_name=rel["target"],
                        relationship_type=rel["type"],
                        properties=rel.get("properties", {}),
                        conversation_id=conversation_id,
                        source_platform=request.source
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
        
        logger.info(f"Ingestion complete: {chunks} chunks, {entities_created} entities")
        
        return IngestResponse(
            conversation_id=conversation_id,
            chunks_created=len(chunks),
            entities_extracted=entities_created,
            relationships_created=relationships_created,
            status="success",
            session_suggestion=session_suggestion,
            linked_session_id=linked_session_id
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
