"""Authentication schemas."""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class AuthUrlResponse(BaseModel):
    """Response with OAuth authorization URL."""
    auth_url: str


class TokenResponse(BaseModel):
    """OAuth token response."""
    access_token: str
    token_type: str
    expires_in: int
    scope: str
    expires_at: datetime


class AuthStatus(BaseModel):
    """Authentication status."""
    is_authenticated: bool
    expires_at: Optional[datetime] = None
    refresh_expires_at: Optional[datetime] = None
    scope: Optional[str] = None