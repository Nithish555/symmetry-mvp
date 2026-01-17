"""
User management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
import secrets

from app.api.dependencies import get_postgres, get_current_user
from app.db.postgres import PostgresDB
from app.models.requests import UserRegisterRequest
from app.models.responses import UserResponse, UserRegistrationResponse


router = APIRouter()


def generate_api_key() -> str:
    """Generate a secure API key."""
    return f"sk_{secrets.token_urlsafe(32)}"


@router.post("/register", response_model=UserRegistrationResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    request: UserRegisterRequest,
    postgres: PostgresDB = Depends(get_postgres)
):
    """
    Register a new user and return their API key.
    
    The API key is only shown once - store it securely!
    """
    # Check if email already exists
    existing = await postgres.get_user_by_email(request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "EMAIL_EXISTS",
                    "message": "A user with this email already exists"
                }
            }
        )
    
    # Generate API key
    api_key = generate_api_key()
    
    # Create user
    user = await postgres.create_user(
        email=request.email,
        api_key=api_key
    )
    
    return UserRegistrationResponse(
        user_id=str(user["id"]),
        email=user["email"],
        api_key=api_key,
        message="Store your API key securely - it won't be shown again!"
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    user: dict = Depends(get_current_user)
):
    """Get current user information."""
    return UserResponse(
        user_id=str(user["id"]),
        email=user["email"],
        created_at=user["created_at"]
    )


@router.post("/api-key/rotate", response_model=UserRegistrationResponse)
async def rotate_api_key(
    user: dict = Depends(get_current_user),
    postgres: PostgresDB = Depends(get_postgres)
):
    """
    Generate a new API key for the current user.
    
    The old API key will be invalidated immediately.
    """
    new_api_key = generate_api_key()
    
    await postgres.update_user_api_key(
        user_id=user["id"],
        new_api_key=new_api_key
    )
    
    return UserRegistrationResponse(
        user_id=str(user["id"]),
        email=user["email"],
        api_key=new_api_key,
        message="Your API key has been rotated. Store the new key securely!"
    )
