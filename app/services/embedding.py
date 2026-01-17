"""
Embedding service.
Generates vector embeddings using OpenAI or Azure OpenAI.
"""

from typing import List
import httpx


async def generate_embedding(
    text: str,
    api_key: str = None,
    model: str = "text-embedding-3-large",
    # Azure OpenAI params
    azure_endpoint: str = None,
    azure_api_key: str = None,
    azure_api_version: str = None,
    azure_deployment: str = None,
    provider: str = "openai"
) -> List[float]:
    """
    Generate embedding for a single text.
    
    Args:
        text: Text to embed
        api_key: OpenAI API key (for OpenAI provider)
        model: Embedding model to use
        azure_*: Azure OpenAI parameters
        provider: "openai" or "azure_openai"
    
    Returns:
        List of floats representing the embedding vector
    """
    async with httpx.AsyncClient() as client:
        if provider == "azure_openai":
            # Azure OpenAI endpoint
            url = f"{azure_endpoint.rstrip('/')}/openai/deployments/{azure_deployment}/embeddings?api-version={azure_api_version}"
            headers = {
                "api-key": azure_api_key,
                "Content-Type": "application/json"
            }
            json_body = {"input": text}
        else:
            # Standard OpenAI endpoint
            url = "https://api.openai.com/v1/embeddings"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            json_body = {"model": model, "input": text}
        
        response = await client.post(url, headers=headers, json=json_body, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]


async def generate_embeddings(
    texts: List[str],
    api_key: str = None,
    model: str = "text-embedding-3-large",
    # Azure OpenAI params
    azure_endpoint: str = None,
    azure_api_key: str = None,
    azure_api_version: str = None,
    azure_deployment: str = None,
    provider: str = "openai"
) -> List[List[float]]:
    """
    Generate embeddings for multiple texts.
    
    Args:
        texts: List of texts to embed
        api_key: OpenAI API key (for OpenAI provider)
        model: Embedding model to use
        azure_*: Azure OpenAI parameters
        provider: "openai" or "azure_openai"
    
    Returns:
        List of embedding vectors
    """
    if not texts:
        return []
    
    async with httpx.AsyncClient() as client:
        if provider == "azure_openai":
            # Azure OpenAI endpoint
            url = f"{azure_endpoint.rstrip('/')}/openai/deployments/{azure_deployment}/embeddings?api-version={azure_api_version}"
            headers = {
                "api-key": azure_api_key,
                "Content-Type": "application/json"
            }
            json_body = {"input": texts}
        else:
            # Standard OpenAI endpoint
            url = "https://api.openai.com/v1/embeddings"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            json_body = {"model": model, "input": texts}
        
        response = await client.post(url, headers=headers, json=json_body, timeout=60.0)
        response.raise_for_status()
        data = response.json()
        
        # Sort by index to maintain order
        embeddings_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in embeddings_data]
