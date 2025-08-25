"""WebSocket handlers for real-time communication."""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Set, Dict, Any
import json
import asyncio

from src.utils.logger import logger


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[WebSocket, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket):
        """Accept and register a new connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.subscriptions[websocket] = set()
        logger.info(f"WebSocket connected: {websocket.client}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a connection."""
        self.active_connections.discard(websocket)
        self.subscriptions.pop(websocket, None)
        logger.info(f"WebSocket disconnected: {websocket.client}")
    
    async def subscribe(self, websocket: WebSocket, symbols: Set[str]):
        """Subscribe a connection to specific symbols."""
        self.subscriptions[websocket] = symbols
        logger.info(f"WebSocket subscribed to: {symbols}")
    
    async def broadcast(self, message: Dict[str, Any], symbol: str = None):
        """Broadcast message to relevant connections."""
        dead_connections = set()
        
        for connection in self.active_connections:
            # If symbol is specified, only send to subscribed connections
            if symbol and symbol not in self.subscriptions.get(connection, set()):
                continue
            
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                dead_connections.add(connection)
        
        # Clean up dead connections
        for connection in dead_connections:
            self.disconnect(connection)


# Global connection manager
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint handler."""
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            message_type = data.get("type")
            
            if message_type == "subscribe":
                # Handle subscription request
                symbols = set(data.get("symbols", []))
                await manager.subscribe(websocket, symbols)
                await websocket.send_json({
                    "type": "subscription_confirmed",
                    "symbols": list(symbols)
                })
            
            elif message_type == "ping":
                # Handle ping/pong for connection health
                await websocket.send_json({"type": "pong"})
            
            else:
                # Echo unknown messages for now
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)