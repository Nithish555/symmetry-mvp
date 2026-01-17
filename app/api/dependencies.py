"""
API Dependencies - Authentication and database access.
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from app.db.postgres import PostgresDB
from app.db.neo4j import Neo4jDB
from app.config import get_settings, Settings


security = HTTPBearer()


def get_postgres(request: Request) -> PostgresDB:
    """Get PostgreSQL database instance."""
    return request.app.state.postgres


def get_neo4j(request: Request) -> Neo4jDB:
    """Get Neo4j database instance."""
    return request.app.state.neo4j


def get_config() -> Settings:
    """Get application settings."""
    return get_settings()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    postgres: PostgresDB = Depends(get_postgres)
) -> dict:
    """
    Validate API key and return current user.
    
    Raises HTTPException if API key is invalid.
    """
    api_key = credentials.credentials
    
    if not api_key.startswith("sk_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_API_KEY_FORMAT",
                    "message": "API key must start with 'sk_'"
                }
            }
        )
    
    # Look up user by API key
    user = await postgres.get_user_by_api_key(api_key)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_API_KEY",
                    "message": "The provided API key is invalid or expired"
                }
            }
        )
    
    return user


async def get_current_user_id(
    user: dict = Depends(get_current_user)
) -> str:
    """Get just the user ID from the current user."""
    return str(user["id"])
