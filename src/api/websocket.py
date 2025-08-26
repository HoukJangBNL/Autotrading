"""WebSocket handlers for real-time communication."""

from fastapi import WebSocket, WebSocketDisconnect, Depends, status
from typing import Set, Dict, Any, Optional, List
import json
import asyncio
import redis.asyncio as redis
from datetime import datetime

from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with Redis pub/sub integration."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[WebSocket, Set[str]] = {}
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.pubsub_task: Optional[asyncio.Task] = None
        self.settings = get_settings()
    
    async def initialize(self):
        """Initialize Redis connection for pub/sub."""
        if not self.redis_client:
            self.redis_client = await redis.from_url(
                self.settings.database.redis_url,
                decode_responses=True
            )
            self.pubsub = self.redis_client.pubsub()
            
            # Subscribe to general candle channel
            await self.pubsub.subscribe("candles:all")
            
            # Start message listener
            self.pubsub_task = asyncio.create_task(self._listen_to_pubsub())
            
            logger.info("ConnectionManager initialized with Redis pub/sub")
    
    async def connect(self, websocket: WebSocket, user_id: Optional[str] = None):
        """Accept and register a new connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.subscriptions[websocket] = set()
        
        # Store user info if authenticated
        if user_id:
            websocket.user_id = user_id  # type: ignore
        
        logger.info(f"WebSocket connected: {websocket.client} (user: {user_id})")
        
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "timestamp": datetime.now().isoformat(),
            "message": "Connected to real-time streaming"
        })
    
    def disconnect(self, websocket: WebSocket):
        """Remove a connection."""
        self.active_connections.discard(websocket)
        self.subscriptions.pop(websocket, None)
        logger.info(f"WebSocket disconnected: {websocket.client}")
    
    async def subscribe(self, websocket: WebSocket, symbols: Set[str]):
        """Subscribe a connection to specific symbols."""
        # Update local subscription tracking
        old_symbols = self.subscriptions.get(websocket, set())
        self.subscriptions[websocket] = symbols
        
        # Subscribe to new symbols via Redis
        new_symbols = symbols - old_symbols
        for symbol in new_symbols:
            channel = f"candles:{symbol}"
            # Simply subscribe - Redis handles duplicate subscriptions gracefully
            await self.pubsub.subscribe(channel)
            logger.info(f"Subscribed to Redis channel: {channel}")
        
        # Unsubscribe from removed symbols
        removed_symbols = old_symbols - symbols
        for symbol in removed_symbols:
            channel = f"candles:{symbol}"
            # Only unsubscribe if no other connections need it
            still_needed = any(
                symbol in subs and ws != websocket
                for ws, subs in self.subscriptions.items()
            )
            if not still_needed:
                await self.pubsub.unsubscribe(channel)
                logger.info(f"Unsubscribed from Redis channel: {channel}")
        
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
    
    async def _listen_to_pubsub(self):
        """Listen to Redis pub/sub messages and broadcast to clients."""
        logger.info("Started Redis pub/sub listener")
        
        try:
            async for message in self.pubsub.listen():
                if message['type'] == 'message':
                    try:
                        # Parse the message
                        data = json.loads(message['data'])
                        channel = message['channel']
                        
                        # Extract symbol from channel name
                        if channel.startswith('candles:'):
                            symbol = channel.split(':', 1)[1]
                            
                            # Broadcast to subscribed connections
                            if symbol == 'all':
                                # Broadcast to all connections
                                await self.broadcast(data)
                            else:
                                # Broadcast to symbol-specific subscribers
                                await self.broadcast(data, symbol)
                        
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in pub/sub message: {message['data']}")
                    except Exception as e:
                        logger.error(f"Error processing pub/sub message: {e}")
        
        except asyncio.CancelledError:
            logger.info("Redis pub/sub listener cancelled")
        except Exception as e:
            logger.error(f"Error in pub/sub listener: {e}")
    
    async def shutdown(self):
        """Cleanup resources."""
        logger.info("Shutting down ConnectionManager")
        
        # Cancel pub/sub listener
        if self.pubsub_task:
            self.pubsub_task.cancel()
            try:
                await self.pubsub_task
            except asyncio.CancelledError:
                pass
        
        # Close pub/sub
        if self.pubsub:
            await self.pubsub.close()
        
        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()
        
        # Disconnect all websockets
        for websocket in list(self.active_connections):
            try:
                await websocket.close()
            except Exception:
                pass


# Global connection manager
manager = ConnectionManager()


async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = None
):
    """Main WebSocket endpoint handler with optional authentication."""
    user_id = None
    logger.debug(f"WebSocket endpoint called with token: {token}")
    
    # Try to authenticate if token provided
    if token:
        try:
            # Verify token and get user info
            # This is simplified - in production, properly verify JWT token
            if token == get_settings().system.api_key:
                user_id = "authenticated_user"
            else:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        except Exception as e:
            logger.error(f"WebSocket authentication error: {e}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Receive message from client
            logger.debug("Waiting for client message...")
            data = await websocket.receive_json()
            logger.debug(f"Received message: {data}")
            
            message_type = data.get("type")
            
            if message_type == "subscribe":
                # Handle subscription request
                symbols = set(data.get("symbols", []))
                await manager.subscribe(websocket, symbols)
                await websocket.send_json({
                    "type": "subscription_confirmed",
                    "symbols": list(symbols)
                })
            
            elif message_type == "start_streaming":
                # Start streaming for symbols
                symbols = data.get("symbols", [])
                await start_streaming_endpoint(websocket, symbols)
            
            elif message_type == "stop_streaming":
                # Stop streaming
                await stop_streaming_endpoint(websocket)
            
            elif message_type == "get_status":
                # Get streaming status
                await get_streaming_status_endpoint(websocket)
            
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
        await websocket.close()


# Initialize manager on module load
async def initialize_websocket_manager():
    """Initialize the global connection manager."""
    await manager.initialize()


# Streaming control endpoints
async def start_streaming_endpoint(
    websocket: WebSocket,
    symbols: List[str]
):
    """Start streaming for specific symbols."""
    try:
        from ..services.streaming_service import start_streaming, StreamingMode
        
        # Start streaming service
        service = await start_streaming(symbols, StreamingMode.BOTH)
        
        # Notify client
        await websocket.send_json({
            "type": "streaming_started",
            "symbols": symbols,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Started streaming for symbols: {symbols}")
        
    except Exception as e:
        logger.error(f"Failed to start streaming: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to start streaming: {str(e)}"
        })


async def stop_streaming_endpoint(websocket: WebSocket):
    """Stop streaming service."""
    try:
        from ..services.streaming_service import stop_streaming
        
        await stop_streaming()
        
        await websocket.send_json({
            "type": "streaming_stopped",
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info("Stopped streaming service")
        
    except Exception as e:
        logger.error(f"Failed to stop streaming: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to stop streaming: {str(e)}"
        })


async def get_streaming_status_endpoint(websocket: WebSocket):
    """Get streaming service status."""
    try:
        from ..services.streaming_service import get_streaming_service
        
        service = await get_streaming_service()
        status = await service.get_status()
        
        await websocket.send_json({
            "type": "streaming_status",
            "data": status,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get streaming status: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to get status: {str(e)}"
        })