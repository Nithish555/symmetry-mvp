"""
Summarization service.
Generates context summaries from retrieved data.
"""

from typing import List
import httpx

from app.prompts.summarization import SUMMARIZATION_PROMPT


async def generate_context_summary(
    query: str,
    chunks: List[dict],
    decisions: List[dict],
    facts: List[dict],
    entities: List[dict],
    api_key: str = None,
    model: str = "gpt-4o-mini",
    # Azure OpenAI params
    azure_endpoint: str = None,
    azure_api_key: str = None,
    azure_api_version: str = None,
    azure_deployment: str = None,
    provider: str = "openai"
) -> str:
    """
    Generate a context summary from retrieved data.
    
    Args:
        query: User's query
        chunks: Retrieved conversation chunks
        decisions: Extracted decisions
        facts: Current facts
        entities: Related entities
        api_key: OpenAI API key (for OpenAI provider)
        model: LLM model to use
        azure_*: Azure OpenAI parameters
        provider: "openai" or "azure_openai"
    
    Returns:
        A concise context summary
    """
    # Format chunks
    chunks_text = "\n\n---\n\n".join([
        f"[{c.get('source', 'unknown')}, {c.get('created_at', 'unknown date')}]\n{c.get('content', '')}"
        for c in chunks
    ]) if chunks else "No relevant conversations found."
    
    # Format decisions
    decisions_text = "\n".join([
        f"• {d.get('decision', '')} ({d.get('reason', 'no reason given')})"
        for d in decisions
    ]) if decisions else "No decisions recorded."
    
    # Format facts
    facts_text = "\n".join([
        f"• {f.get('subject', '')} {f.get('predicate', '')} {f.get('object', '')}"
        for f in facts
    ]) if facts else "No facts recorded."
    
    # Format entities
    entities_text = ", ".join([
        e.get('name', '') for e in entities
    ]) if entities else "None"
    
    prompt = SUMMARIZATION_PROMPT.format(
        query=query,
        chunks=chunks_text,
        decisions=decisions_text,
        facts=facts_text,
        entities=entities_text
    )
    
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
                    "content": "You are a helpful context assistant. Provide concise, relevant summaries of past conversations and decisions. Be specific and actionable."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 500
        }
        
        # Add model for OpenAI (Azure uses deployment in URL)
        if provider != "azure_openai":
            json_body["model"] = model
        
        response = await client.post(url, headers=headers, json=json_body, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        
        return data["choices"][0]["message"]["content"]
