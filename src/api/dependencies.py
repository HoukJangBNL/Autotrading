"""API dependencies for authentication and common functionality."""

from typing import Optional, Generator, AsyncGenerator
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import get_auth_service, get_authenticated_client, AuthenticationError
from src.data.database import get_db, get_async_db
from src.utils.logger import logger
from src.config import settings

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    """Get current authenticated user from token.
    
    This is a dependency that can be used in protected endpoints.
    For Schwab OAuth, we check the stored token file instead of JWT.
    
    Args:
        token: OAuth2 bearer token from Authorization header (optional for Schwab OAuth)
        
    Returns:
        User information dictionary
        
    Raises:
        HTTPException: If not authenticated
    """
    try:
        # Import here to avoid circular dependency
        from src.api.routers.auth import get_schwab_auth
        
        # Check if we have a valid Schwab client
        schwab_auth = get_schwab_auth()
        client = schwab_auth.load_existing_client()
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Return user info with the Schwab client
        return {
            "username": "trader",
            "is_authenticated": True,
            "client": client  # Store client for use in endpoints
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during authentication: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during authentication"
        )


async def require_auth(user: dict = Depends(get_current_user)) -> dict:
    """Require authentication for endpoint.
    
    This is a simple dependency that ensures the user is authenticated.
    Use this in endpoints that require authentication.
    
    Args:
        user: Current user from get_current_user dependency
        
    Returns:
        Authenticated user information
    """
    if not user.get("is_authenticated"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_api_key(x_api_key: Optional[str] = Header(None)) -> Optional[str]:
    """Get API key from header.
    
    This is an alternative authentication method using API keys.
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Returns:
        API key if provided
    """
    return x_api_key


async def verify_api_key(api_key: Optional[str] = Depends(get_api_key)) -> bool:
    """Verify API key.
    
    This checks if the provided API key is valid.
    
    Args:
        api_key: API key from get_api_key dependency
        
    Returns:
        True if API key is valid
        
    Raises:
        HTTPException: If API key is invalid or missing
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"X-API-Key": "required"},
        )
    
    # In a real implementation, check API key against database
    # For now, check against settings
    if api_key != settings.system.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    
    return True


# Re-export database dependencies for convenience
__all__ = [
    "get_current_user",
    "require_auth",
    "get_api_key",
    "verify_api_key",
    "get_db",
    "get_async_db",
    "oauth2_scheme"
]