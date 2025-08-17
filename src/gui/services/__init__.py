"""GUI service layer for backend integration."""

from .gui_service import GUIService
from .websocket_client import GUIWebSocketClient

__all__ = ['GUIService', 'GUIWebSocketClient']