"""Custom exceptions for authentication module."""


class AuthenticationError(Exception):
    """Base exception for authentication errors."""
    pass


class TokenExpiredError(AuthenticationError):
    """Raised when token has expired."""
    pass


class TokenRefreshError(AuthenticationError):
    """Raised when token refresh fails."""
    pass


class OAuthFlowError(AuthenticationError):
    """Raised when OAuth flow fails."""
    pass


class ClientInitializationError(AuthenticationError):
    """Raised when client initialization fails."""
    pass


class TokenStorageError(AuthenticationError):
    """Raised when token storage operations fail."""
    pass


class APITestError(AuthenticationError):
    """Raised when API test calls fail during authentication."""
    pass