"""WebSocket connection manager."""

import asyncio
import json
import logging
from typing import Dict, List, Set
from datetime import datetime

from fastapi import WebSocket
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[str, Set[WebSocket]] = {
            "market_data": set(),
            "strategy_signals": set(),
            "order_updates": set(),
            "portfolio_updates": set(),
            "portfolio": set(),  # Add portfolio topic
        }
        self.connection_metadata: Dict[WebSocket, Dict] = {}
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_metadata[websocket] = {
            "connected_at": datetime.now(),
            "subscriptions": set()
        }
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from all subscriptions
        for topic, subscribers in self.subscriptions.items():
            subscribers.discard(websocket)
        
        # Remove metadata
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]
        
        logger.info(f"WebSocket client disconnected. Total connections: {len(self.active_connections)}")
    
    async def subscribe(self, websocket: WebSocket, topic: str):
        """Subscribe a connection to a topic."""
        if topic in self.subscriptions:
            self.subscriptions[topic].add(websocket)
            if websocket in self.connection_metadata:
                self.connection_metadata[websocket]["subscriptions"].add(topic)
            logger.info(f"WebSocket subscribed to {topic}")
            
            # Send confirmation
            await self.send_personal_message(websocket, {
                "type": "subscription",
                "topic": topic,
                "status": "subscribed",
                "timestamp": datetime.now().isoformat()
            })
        else:
            await self.send_personal_message(websocket, {
                "type": "error",
                "message": f"Unknown topic: {topic}",
                "timestamp": datetime.now().isoformat()
            })
    
    async def unsubscribe(self, websocket: WebSocket, topic: str):
        """Unsubscribe a connection from a topic."""
        if topic in self.subscriptions:
            self.subscriptions[topic].discard(websocket)
            if websocket in self.connection_metadata:
                self.connection_metadata[websocket]["subscriptions"].discard(topic)
            logger.info(f"WebSocket unsubscribed from {topic}")
            
            # Send confirmation
            await self.send_personal_message(websocket, {
                "type": "subscription",
                "topic": topic,
                "status": "unsubscribed",
                "timestamp": datetime.now().isoformat()
            })
    
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """Send a message to a specific connection."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast_to_topic(self, topic: str, message: dict):
        """Broadcast a message to all subscribers of a topic."""
        if topic not in self.subscriptions:
            logger.warning(f"Attempting to broadcast to unknown topic: {topic}")
            return
        
        # Add topic and timestamp to message
        message["topic"] = topic
        message["timestamp"] = datetime.now().isoformat()
        
        # Send to all subscribers
        disconnected = []
        for websocket in self.subscriptions[topic]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        message["timestamp"] = datetime.now().isoformat()
        
        disconnected = []
        for websocket in self.active_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket)
    
    def get_connection_info(self) -> Dict:
        """Get information about current connections."""
        return {
            "total_connections": len(self.active_connections),
            "subscriptions": {
                topic: len(subscribers) 
                for topic, subscribers in self.subscriptions.items()
            },
            "connections": [
                {
                    "connected_at": metadata["connected_at"].isoformat(),
                    "subscriptions": list(metadata["subscriptions"])
                }
                for metadata in self.connection_metadata.values()
            ]
        }