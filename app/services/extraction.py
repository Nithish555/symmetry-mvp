"""
Knowledge extraction service.
Uses LLM to extract entities and relationships from conversations.

Production-level extraction with:
- Confidence scoring
- Source attribution
- Temporal markers
- Validation and normalization
"""

from typing import List, Dict, Any
import httpx
import json
import logging

from app.models.requests import Message
from app.prompts.extraction import EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


def format_messages_for_extraction(messages: List[Message]) -> str:
    """Format messages for the extraction prompt."""
    parts = []
    for msg in messages:
        role = msg.role.upper()
        content = msg.content.strip()
        parts.append(f"{role}: {content}")
    return "\n\n".join(parts)


def _normalize_relationship(rel: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize and validate a relationship extracted by the LLM.
    Ensures all required fields exist with sensible defaults.
    """
    # Default values
    normalized = {
        "source": rel.get("source", "User"),
        "target": rel.get("target", "Unknown"),
        "type": rel.get("type", "RELATED_TO"),
        "status": rel.get("status", "exploring"),
        "confidence": rel.get("confidence", 0.5),
        "attributed_to": rel.get("attributed_to", "user"),
        "temporal": rel.get("temporal", "current"),
        "properties": rel.get("properties", {}),
        "verified": False  # Always starts unverified
    }
    
    # Normalize type
    type_upper = normalized["type"].upper()
    valid_types = {"CHOSE", "DECIDED", "CONSIDERING", "REJECTED", "PREFERS", 
                   "USES", "BUILDS", "WORKS_AT", "RELATED_TO", "USED"}
    if type_upper not in valid_types:
        normalized["type"] = "RELATED_TO"
    else:
        normalized["type"] = type_upper
    
    # Normalize status based on type
    if normalized["type"] in ("CHOSE", "DECIDED"):
        if normalized["status"] not in ("decided", "exploring"):
            normalized["status"] = "decided"
    elif normalized["type"] == "REJECTED":
        normalized["status"] = "rejected"
    elif normalized["type"] == "CONSIDERING":
        normalized["status"] = "exploring"
    elif normalized["type"] == "USED":
        normalized["temporal"] = "past"
    
    # Clamp confidence to valid range
    try:
        conf = float(normalized["confidence"])
        normalized["confidence"] = max(0.0, min(1.0, conf))
    except (ValueError, TypeError):
        normalized["confidence"] = 0.5
    
    # Validate attributed_to
    valid_sources = {"user", "colleague", "article", "docs", "ai_suggestion", "other"}
    if normalized["attributed_to"] not in valid_sources:
        normalized["attributed_to"] = "user"
    
    # Validate temporal
    if normalized["temporal"] not in ("current", "past", "future"):
        normalized["temporal"] = "current"
    
    # Ensure properties is a dict
    if not isinstance(normalized["properties"], dict):
        normalized["properties"] = {}
    
    return normalized


def _normalize_fact(fact: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a fact extracted by the LLM."""
    return {
        "subject": fact.get("subject", "User"),
        "predicate": fact.get("predicate", "RELATED_TO"),
        "object": fact.get("object", "Unknown"),
        "confidence": max(0.0, min(1.0, float(fact.get("confidence", 0.8)))),
        "temporal": fact.get("temporal", "current"),
        "valid_from": fact.get("valid_from"),
        "valid_to": fact.get("valid_to")
    }


def _normalize_entity(entity: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize an entity extracted by the LLM."""
    valid_types = {"Tool", "Project", "Company", "Person", "Concept", "Technology", "Other"}
    entity_type = entity.get("type", "Other")
    if entity_type not in valid_types:
        entity_type = "Other"
    
    return {
        "name": entity.get("name", "Unknown"),
        "type": entity_type,
        "description": entity.get("description", ""),
        "first_mentioned": entity.get("first_mentioned", "")
    }


async def extract_knowledge(
    messages: List[Message],
    api_key: str = None,
    model: str = "gpt-4o-mini",
    # Azure OpenAI params
    azure_endpoint: str = None,
    azure_api_key: str = None,
    azure_api_version: str = None,
    azure_deployment: str = None,
    provider: str = "openai"
) -> dict:
    """
    Extract structured knowledge from a conversation.
    
    Args:
        messages: List of conversation messages
        api_key: OpenAI API key (for OpenAI provider)
        model: LLM model to use
        azure_*: Azure OpenAI parameters
        provider: "openai" or "azure_openai"
    
    Returns:
        Dictionary containing:
        - entities: List of extracted entities
        - relationships: List of relationships between entities
        - facts: List of temporal facts
    """
    conversation_text = format_messages_for_extraction(messages)
    
    prompt = EXTRACTION_PROMPT.format(conversation=conversation_text)
    
    async with httpx.AsyncClient() as client:
        if provider == "azure_openai":
            # Azure OpenAI endpoint
            url = f"{azure_endpoint.rstrip('/')}/openai/deployments/{azure_deployment}/chat/completions?api-version={azure_api_version}"
            headers = {
                "api-key": azure_api_key,
                "Content-Type": "application/json"
            }
        else:
            # Standard OpenAI endpoint
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        
        json_body = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a knowledge extraction assistant. Extract structured information from conversations. Always return valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 2000
        }
        
        # Add model for OpenAI (Azure uses deployment in URL)
        if provider != "azure_openai":
            json_body["model"] = model
        
        response = await client.post(url, headers=headers, json=json_body, timeout=60.0)
        response.raise_for_status()
        data = response.json()
        
        content = data["choices"][0]["message"]["content"]
        
        try:
            knowledge = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM extraction response as JSON")
            knowledge = {
                "entities": [],
                "relationships": [],
                "facts": [],
                "warnings": []
            }
        
        # Ensure all required keys exist
        if "entities" not in knowledge:
            knowledge["entities"] = []
        if "relationships" not in knowledge:
            knowledge["relationships"] = []
        if "facts" not in knowledge:
            knowledge["facts"] = []
        if "warnings" not in knowledge:
            knowledge["warnings"] = []
        
        # ═══════════════════════════════════════════════════════════════
        # NORMALIZE AND VALIDATE ALL EXTRACTED DATA
        # ═══════════════════════════════════════════════════════════════
        
        # Normalize entities
        knowledge["entities"] = [
            _normalize_entity(e) for e in knowledge["entities"]
            if isinstance(e, dict) and e.get("name")
        ]
        
        # Normalize relationships with validation
        normalized_rels = []
        for rel in knowledge["relationships"]:
            if isinstance(rel, dict) and rel.get("target"):
                normalized = _normalize_relationship(rel)
                normalized_rels.append(normalized)
                
                # Log low-confidence extractions
                if normalized["confidence"] < 0.5:
                    logger.debug(f"Low confidence extraction: {normalized['target']} ({normalized['confidence']})")
        
        knowledge["relationships"] = normalized_rels
        
        # Normalize facts
        knowledge["facts"] = [
            _normalize_fact(f) for f in knowledge["facts"]
            if isinstance(f, dict) and f.get("object")
        ]
        
        # Add extraction metadata
        knowledge["_metadata"] = {
            "entities_count": len(knowledge["entities"]),
            "relationships_count": len(knowledge["relationships"]),
            "facts_count": len(knowledge["facts"]),
            "high_confidence_count": sum(1 for r in knowledge["relationships"] if r["confidence"] >= 0.8),
            "low_confidence_count": sum(1 for r in knowledge["relationships"] if r["confidence"] < 0.5),
            "has_warnings": len(knowledge.get("warnings", [])) > 0
        }
        
        logger.info(
            f"Extracted: {knowledge['_metadata']['entities_count']} entities, "
            f"{knowledge['_metadata']['relationships_count']} relationships "
            f"({knowledge['_metadata']['high_confidence_count']} high confidence)"
        )
        
        return knowledge


async def extract_topics_and_entities(
    text: str,
    api_key: str = None,
    model: str = "gpt-4o-mini",
    azure_endpoint: str = None,
    azure_api_key: str = None,
    azure_api_version: str = None,
    azure_deployment: str = None,
    provider: str = "openai"
) -> dict:
    """
    Extract topics and entities from text for recommendation matching.
    
    Returns:
        {"topics": [...], "entities": [...]}
    """
    prompt = f"""Analyze this text and extract:
1. Main topics (general subjects being discussed)
2. Key entities (specific things like technologies, products, names)

Text: {text[:2000]}

Return JSON:
{{"topics": ["topic1", "topic2"], "entities": ["entity1", "entity2"]}}"""
    
    async with httpx.AsyncClient() as client:
        if provider == "azure_openai":
            url = f"{azure_endpoint.rstrip('/')}/openai/deployments/{azure_deployment}/chat/completions?api-version={azure_api_version}"
            headers = {"api-key": azure_api_key, "Content-Type": "application/json"}
        else:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        json_body = {
            "messages": [
                {"role": "system", "content": "Extract topics and entities. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 500
        }
        
        if provider != "azure_openai":
            json_body["model"] = model
        
        response = await client.post(url, headers=headers, json=json_body, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        
        content = data["choices"][0]["message"]["content"]
        
        try:
            result = json.loads(content)
            return {
                "topics": result.get("topics", []),
                "entities": result.get("entities", [])
            }
        except json.JSONDecodeError:
            return {"topics": [], "entities": []}


async def generate_conversation_summary(
    messages: list,
    api_key: str = None,
    model: str = "gpt-4o-mini",
    azure_endpoint: str = None,
    azure_api_key: str = None,
    azure_api_version: str = None,
    azure_deployment: str = None,
    provider: str = "openai"
) -> dict:
    """
    Generate a summary and extract metadata from a conversation.
    
    Returns:
        {"summary": "...", "topics": [...], "entities": [...]}
    """
    # Format conversation
    conv_text = "\n".join([
        f"{m.get('role', m.role if hasattr(m, 'role') else 'unknown').upper()}: {m.get('content', m.content if hasattr(m, 'content') else '')}"
        for m in messages
    ])[:6000]
    
    prompt = f"""Analyze this conversation and provide:
1. A concise summary (2-3 sentences)
2. Main topics discussed
3. Key entities mentioned (technologies, products, names, etc.)

Conversation:
{conv_text}

Return JSON:
{{"summary": "...", "topics": ["topic1"], "entities": ["entity1"]}}"""
    
    async with httpx.AsyncClient() as client:
        if provider == "azure_openai":
            url = f"{azure_endpoint.rstrip('/')}/openai/deployments/{azure_deployment}/chat/completions?api-version={azure_api_version}"
            headers = {"api-key": azure_api_key, "Content-Type": "application/json"}
        else:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        json_body = {
            "messages": [
                {"role": "system", "content": "Summarize conversations and extract metadata. Return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
            "max_tokens": 1000
        }
        
        if provider != "azure_openai":
            json_body["model"] = model
        
        response = await client.post(url, headers=headers, json=json_body, timeout=60.0)
        response.raise_for_status()
        data = response.json()
        
        content = data["choices"][0]["message"]["content"]
        
        try:
            result = json.loads(content)
            return {
                "summary": result.get("summary", ""),
                "topics": result.get("topics", []),
                "entities": result.get("entities", [])
            }
        except json.JSONDecodeError:
            return {"summary": "", "topics": [], "entities": []}
