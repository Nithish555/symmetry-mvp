"""
Knowledge extraction service.
Uses LLM to extract entities and relationships from conversations.
"""

from typing import List
import httpx
import json

from app.models.requests import Message
from app.prompts.extraction import EXTRACTION_PROMPT


def format_messages_for_extraction(messages: List[Message]) -> str:
    """Format messages for the extraction prompt."""
    parts = []
    for msg in messages:
        role = msg.role.upper()
        content = msg.content.strip()
        parts.append(f"{role}: {content}")
    return "\n\n".join(parts)


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
            # Return empty structure if parsing fails
            knowledge = {
                "entities": [],
                "relationships": [],
                "facts": []
            }
        
        # Ensure all required keys exist
        if "entities" not in knowledge:
            knowledge["entities"] = []
        if "relationships" not in knowledge:
            knowledge["relationships"] = []
        if "facts" not in knowledge:
            knowledge["facts"] = []
        
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
