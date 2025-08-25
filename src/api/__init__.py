"""API module for the trading system.

This module contains FastAPI endpoints, routers, and WebSocket handlers
for the personal stock trading system.
"""

from .main import app

__all__ = ["app"]