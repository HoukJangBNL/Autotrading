"""WebSocket message handlers and Redis integration."""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

import redis.asyncio as redis
from fastapi import WebSocket

from .manager import ConnectionManager
from ...data.models import TimeFrame

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """Handles WebSocket messages and Redis pub/sub integration."""
    
    def __init__(self, manager: ConnectionManager, redis_client: redis.Redis):
        self.manager = manager
        self.redis_client = redis_client
        self.pubsub: Optional[redis.client.PubSub] = None
        self.running = False
        self.tasks = []
    
    async def start(self):
        """Start listening to Redis channels."""
        try:
            self.pubsub = self.redis_client.pubsub()
            self.running = True
            
            # Subscribe to Redis channels
            await self.pubsub.subscribe(
                "market_data:*",
                "strategy:signals",
                "trading:orders",
                "trading:positions",
                "portfolio:updates"
            )
            
            # Start listening task
            listen_task = asyncio.create_task(self._listen_to_redis())
            self.tasks.append(listen_task)
            
            logger.info("WebSocket handler started")
            
        except Exception as e:
            logger.error(f"Failed to start WebSocket handler: {e}")
            raise
    
    async def stop(self):
        """Stop listening to Redis channels."""
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Unsubscribe and close pubsub
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        
        logger.info("WebSocket handler stopped")
    
    async def _listen_to_redis(self):
        """Listen for Redis pub/sub messages and broadcast to WebSocket clients."""
        logger.info("Started listening to Redis channels")
        
        while self.running:
            try:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                
                if message is None:
                    continue
                
                # Parse channel and data
                channel = message["channel"].decode() if isinstance(message["channel"], bytes) else message["channel"]
                data = message["data"]
                
                # Decode data if it's bytes
                if isinstance(data, bytes):
                    data = data.decode()
                
                # Route message based on channel
                if channel.startswith("market_data:"):
                    await self._handle_market_data(channel, data)
                elif channel == "strategy:signals":
                    await self._handle_strategy_signal(data)
                elif channel == "trading:orders":
                    await self._handle_order_update(data)
                elif channel == "trading:positions":
                    await self._handle_position_update(data)
                elif channel == "portfolio:updates":
                    await self._handle_portfolio_update(data)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Redis listener: {e}")
                await asyncio.sleep(1)  # Prevent tight loop on error
        
        logger.info("Stopped listening to Redis channels")
    
    async def _handle_market_data(self, channel: str, data: str):
        """Handle market data from Redis and broadcast to subscribers."""
        try:
            # Parse channel to get symbol and timeframe
            # Format: market_data:SYMBOL:TIMEFRAME
            parts = channel.split(":")
            if len(parts) >= 3:
                symbol = parts[1]
                timeframe = parts[2] if len(parts) > 2 else "1min"
                
                # Parse data
                candle_data = json.loads(data)
                
                # Create WebSocket message
                message = {
                    "type": "market_data",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "data": candle_data
                }
                
                # Broadcast to market_data subscribers
                await self.manager.broadcast_to_topic("market_data", message)
                
        except Exception as e:
            logger.error(f"Error handling market data: {e}")
    
    async def _handle_strategy_signal(self, data: str):
        """Handle strategy signals and broadcast to subscribers."""
        try:
            signal_data = json.loads(data)
            
            # Create WebSocket message
            message = {
                "type": "strategy_signal",
                "data": signal_data
            }
            
            # Broadcast to strategy_signals subscribers
            await self.manager.broadcast_to_topic("strategy_signals", message)
            
        except Exception as e:
            logger.error(f"Error handling strategy signal: {e}")
    
    async def _handle_order_update(self, data: str):
        """Handle order updates and broadcast to subscribers."""
        try:
            order_data = json.loads(data)
            
            # Create WebSocket message
            message = {
                "type": "order_update",
                "data": order_data
            }
            
            # Broadcast to order_updates subscribers
            await self.manager.broadcast_to_topic("order_updates", message)
            
        except Exception as e:
            logger.error(f"Error handling order update: {e}")
    
    async def _handle_position_update(self, data: str):
        """Handle position updates and broadcast to subscribers."""
        try:
            position_data = json.loads(data)
            
            # Create WebSocket message
            message = {
                "type": "position_update",
                "data": position_data
            }
            
            # Broadcast to portfolio_updates subscribers
            await self.manager.broadcast_to_topic("portfolio_updates", message)
            
        except Exception as e:
            logger.error(f"Error handling position update: {e}")
    
    async def _handle_portfolio_update(self, data: str):
        """Handle portfolio updates and broadcast to subscribers."""
        try:
            portfolio_data = json.loads(data)
            
            # Create WebSocket message
            message = {
                "type": "portfolio_update",
                "data": portfolio_data
            }
            
            # Broadcast to portfolio_updates subscribers
            await self.manager.broadcast_to_topic("portfolio_updates", message)
            
        except Exception as e:
            logger.error(f"Error handling portfolio update: {e}")
    
    async def handle_message(self, websocket: WebSocket, message: str):
        """Handle incoming WebSocket messages from clients."""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "subscribe":
                topic = data.get("topic")
                if topic:
                    await self.manager.subscribe(websocket, topic)
                else:
                    await self.manager.send_personal_message(websocket, {
                        "type": "error",
                        "message": "Missing topic in subscribe message"
                    })
            
            elif message_type == "unsubscribe":
                topic = data.get("topic")
                if topic:
                    await self.manager.unsubscribe(websocket, topic)
                else:
                    await self.manager.send_personal_message(websocket, {
                        "type": "error",
                        "message": "Missing topic in unsubscribe message"
                    })
            
            elif message_type == "ping":
                # Respond with pong
                await self.manager.send_personal_message(websocket, {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
            
            elif message_type == "subscribe_symbol":
                # Subscribe to specific symbol market data
                symbol = data.get("symbol")
                timeframe = data.get("timeframe", "1min")
                if symbol:
                    # This would trigger subscription to specific Redis channel
                    # For now, just acknowledge
                    await self.manager.send_personal_message(websocket, {
                        "type": "subscribed",
                        "symbol": symbol,
                        "timeframe": timeframe
                    })
            
            else:
                await self.manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })
        
        except json.JSONDecodeError:
            await self.manager.send_personal_message(websocket, {
                "type": "error",
                "message": "Invalid JSON message"
            })
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await self.manager.send_personal_message(websocket, {
                "type": "error",
                "message": "Internal server error"
            })