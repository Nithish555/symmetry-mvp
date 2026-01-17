"""
Configuration management for Symmetry MVP.
Loads environment variables and provides typed config.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Supabase
    supabase_url: str
    supabase_key: str
    database_url: str
    
    # Neo4j
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    
    # LLM Provider (openai or azure_openai)
    llm_provider: str = "openai"
    
    # OpenAI (if using OpenAI directly)
    openai_api_key: Optional[str] = None
    
    # Azure OpenAI - Chat
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    azure_openai_api_version: str = "2024-12-01-preview"
    azure_openai_deployment: str = "gpt-4.1-mini"
    
    # Azure OpenAI - Embeddings (can be different endpoint)
    azure_openai_embedding_endpoint: Optional[str] = None
    azure_openai_embedding_api_key: Optional[str] = None  # If different from chat
    azure_openai_embedding_deployment: Optional[str] = None
    
    # App settings
    chunk_size: int = 500
    chunk_overlap: int = 50
    embedding_model: str = "text-embedding-3-large"
    llm_model: str = "gpt-4o-mini"
    similarity_threshold: float = 0.7
    max_chunks_to_retrieve: int = 5
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    def get_embedding_endpoint(self) -> str:
        """Get the embedding endpoint (might be different from chat endpoint)."""
        return self.azure_openai_embedding_endpoint or self.azure_openai_endpoint
    
    def get_embedding_api_key(self) -> str:
        """Get the embedding API key (might be different from chat API key)."""
        return self.azure_openai_embedding_api_key or self.azure_openai_api_key
    
    def get_embedding_deployment(self) -> str:
        """Get the embedding deployment name."""
        return self.azure_openai_embedding_deployment or "text-embedding-3-large"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
