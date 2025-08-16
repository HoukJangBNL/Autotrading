"""Authentication module for Schwab API integration."""

from .auth_service import AuthService, get_auth_service, get_authenticated_client
from .oauth_manager import OAuthManager
from .token_store import TokenStore
from .exceptions import (
    AuthenticationError,
    TokenExpiredError,
    TokenRefreshError,
    OAuthFlowError,
    ClientInitializationError,
    TokenStorageError,
    APITestError
)

__all__ = [
    'AuthService',
    'OAuthManager', 
    'TokenStore',
    'get_auth_service',
    'get_authenticated_client',
    'AuthenticationError',
    'TokenExpiredError',
    'TokenRefreshError',
    'OAuthFlowError',
    'ClientInitializationError',
    'TokenStorageError',
    'APITestError'
]