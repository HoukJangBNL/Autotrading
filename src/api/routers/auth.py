"""Authentication router for Schwab OAuth integration."""

import logging
from typing import Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse

from ...auth import AuthService, get_auth_service
from ...auth.schwab_auth_flow import SchwabAuthFlow
from ..schemas.auth import TokenResponse, AuthStatus, AuthUrlResponse
from ..dependencies import get_current_user

logger = logging.getLogger(__name__)

# Global instance of SchwabAuthFlow - create once at module level
_schwab_auth = SchwabAuthFlow()

def get_schwab_auth() -> SchwabAuthFlow:
    """Get singleton SchwabAuthFlow instance."""
    return _schwab_auth

router = APIRouter()


@router.get("/login", response_model=AuthUrlResponse)
async def login(
    schwab_auth: SchwabAuthFlow = Depends(get_schwab_auth)
) -> AuthUrlResponse:
    """
    Get Schwab OAuth login URL.
    
    Returns the authorization URL to redirect the user for Schwab login.
    """
    try:
        auth_url = schwab_auth.get_auth_url()
        return AuthUrlResponse(auth_url=auth_url)
    except Exception as e:
        logger.error(f"Failed to generate auth URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate authorization URL"
        )


@router.get("/callback")
async def oauth_callback(
    request: Request,
    code: str,
    state: str = None,
    schwab_auth: SchwabAuthFlow = Depends(get_schwab_auth)
) -> RedirectResponse:
    """
    Handle OAuth callback from Schwab.
    
    Uses schwab-py's built-in OAuth completion to handle token properly.
    """
    try:
        # Log the callback attempt
        logger.info(f"OAuth callback received with code: {code[:10]}...")
        
        # Construct the full callback URL for schwab-py
        callback_url = str(request.url)
        logger.info(f"Full callback URL: {callback_url}")
        
        # Complete authentication using schwab-py
        client = await schwab_auth.complete_auth(callback_url)
        
        # Test that authentication worked
        resp = await client.get_account_numbers()
        resp.raise_for_status()
        accounts = resp.json()
        logger.info(f"OAuth successful, found {len(accounts)} account(s)")
        
        # Redirect to frontend with success
        # Honor X-Forwarded-* headers if behind proxy to compute scheme/host
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host", request.url.hostname or "localhost")
        port = request.headers.get("x-forwarded-port")
        if port and ":" not in host:
            host = f"{host}:{port}"
        frontend_url = f"{scheme}://{host}/auth/success"
        logger.info(f"OAuth successful, redirecting to {frontend_url}")
        return RedirectResponse(url=frontend_url)
        
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}", exc_info=True)
        # Redirect to frontend with error; compute origin from request/proxy headers
        import urllib.parse
        error_msg = urllib.parse.quote(str(e))
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host", request.url.hostname or "localhost")
        port = request.headers.get("x-forwarded-port")
        if port and ":" not in host:
            host = f"{host}:{port}"
        frontend_url = f"{scheme}://{host}/auth/error?error={error_msg}"
        return RedirectResponse(url=frontend_url)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    auth_service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    """
    Refresh the access token using the refresh token.
    
    This should be called when the access token expires.
    """
    try:
        await auth_service.ensure_authenticated()
        
        # Get token info
        token_info = auth_service.token_manager.get_token_info()
        if not token_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No valid tokens found"
            )
        
        return TokenResponse(
            access_token=token_info["access_token"],
            token_type="Bearer",
            expires_in=token_info.get("expires_in", 1800),
            scope=token_info.get("scope", ""),
            expires_at=datetime.fromtimestamp(token_info.get("expires_at", 0))
        )
        
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to refresh token"
        )


@router.get("/status", response_model=AuthStatus)
async def auth_status(
    schwab_auth: SchwabAuthFlow = Depends(get_schwab_auth)
) -> AuthStatus:
    """
    Check authentication status.
    
    Returns whether the user is authenticated and token expiry info.
    """
    try:
        # Simply check if we have a client loaded (either from token file or memory)
        # Don't make API calls here to avoid repeated auth checks
        client = schwab_auth.load_existing_client()
        is_authenticated = client is not None
        
        if is_authenticated:
            logger.info("Auth status: Authenticated (client loaded from token)")
        else:
            logger.info("Auth status: Not authenticated (no valid token found)")
        
        # schwab-py doesn't expose token expiry info directly
        # We just return authenticated status
        return AuthStatus(
            is_authenticated=is_authenticated,
            expires_at=None,  # schwab-py handles token refresh automatically
            refresh_expires_at=None,
            scope=None
        )
        
    except Exception as e:
        logger.error(f"Failed to get auth status: {e}")
        return AuthStatus(
            is_authenticated=False,
            expires_at=None,
            refresh_expires_at=None,
            scope=None
        )


@router.post("/logout")
async def logout(
    response: Response,
    schwab_auth: SchwabAuthFlow = Depends(get_schwab_auth)
) -> Dict[str, str]:
    """
    Logout user by clearing tokens.
    
    This doesn't revoke tokens with Schwab, just clears local storage.
    """
    try:
        # Clear token file
        schwab_auth.clear_token()
        
        # Clear any session cookies
        response.delete_cookie("session")
        
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to logout"
        )


@router.get("/me", response_model=Dict[str, Any])
async def get_current_user_info(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get current user information.
    
    Requires authentication.
    """
    return current_user


@router.get("/debug/oauth")
async def debug_oauth_config(
    auth_service: AuthService = Depends(get_auth_service)
) -> Dict[str, Any]:
    """
    Debug endpoint to check OAuth configuration.
    
    Returns current OAuth settings and status.
    """
    import os
    from pathlib import Path
    
    # Check if PKCE file exists
    pkce_file = Path("config/pkce_temp.json")
    pkce_exists = pkce_file.exists()
    
    # Check environment variables
    env_vars = {
        "SCHWAB_API_KEY": os.getenv("SCHWAB_API_KEY", "NOT_SET")[:10] + "...",
        "SCHWAB_APP_SECRET": "SET" if os.getenv("SCHWAB_APP_SECRET") else "NOT_SET",
        "SCHWAB_CALLBACK_URL": os.getenv("SCHWAB_CALLBACK_URL", "NOT_SET"),
    }
    
    # Check token file
    token_file = Path("config/schwab_token.json")
    token_exists = token_file.exists()
    
    return {
        "oauth_config": {
            "callback_url": auth_service.oauth_manager.settings.schwab.callback_url,
            "api_key_prefix": auth_service.oauth_manager.settings.schwab.api_key[:10] + "...",
            "app_secret_set": bool(auth_service.oauth_manager.settings.schwab.app_secret),
        },
        "environment": env_vars,
        "files": {
            "pkce_temp_exists": pkce_exists,
            "token_file_exists": token_exists,
        },
        "status": {
            "initialized": auth_service.is_initialized(),
            "authenticated": auth_service.is_authenticated(),
        },
        "instructions": {
            "1": "Make sure Schwab Developer Portal has callback URL: https://127.0.0.1:8182/api/auth/callback",
            "2": "API Key and Secret must match what's in the Schwab Developer Portal",
            "3": "Use /api/auth/login to get the authorization URL",
            "4": "After Schwab login, you'll be redirected back to the callback URL",
        }
    }