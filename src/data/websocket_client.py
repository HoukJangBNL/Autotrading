"""
WebSocket client for Schwab streaming API with automatic reconnection and heartbeat management.

This module provides a robust WebSocket connection manager that handles:
- Authentication with Schwab streaming servers
- Automatic reconnection with exponential backoff
- Heartbeat management
- Message queuing during disconnections
- Integration with Stream Processor
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Any, Set
from enum import Enum
import logging
from contextlib import asynccontextmanager

import websockets
from websockets.exceptions import WebSocketException, ConnectionClosed

from ..auth.auth_service import get_auth_service
from ..utils.logger import get_logger
from .stream_processor import StreamProcessor, Tick, TickType

logger = get_logger(__name__)


class ConnectionState(str, Enum):
    """WebSocket connection states."""
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    AUTHENTICATED = "AUTHENTICATED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"


class MessageType(str, Enum):
    """Schwab WebSocket message types."""
    AUTH = "AUTH"
    SUBSCRIBE = "SUBSCRIBE"
    UNSUBSCRIBE = "UNSUBSCRIBE"
    DATA = "DATA"
    RESPONSE = "RESPONSE"
    HEARTBEAT = "HEARTBEAT"
    ERROR = "ERROR"


class SchwabWebSocketClient:
    """
    Manages WebSocket connection to Schwab streaming API.
    
    Features:
    - Automatic reconnection with exponential backoff
    - Heartbeat management to keep connection alive
    - Message queuing during disconnections
    - Integration with Stream Processor for tick data
    """
    
    # Schwab streaming WebSocket endpoint
    # Note: This is a placeholder - actual endpoint from StreamClient initialization
    WS_URL = "wss://streamer-api.schwab.com/ws"
    
    # Connection parameters
    HEARTBEAT_INTERVAL = 30  # seconds
    RECONNECT_MAX_ATTEMPTS = 5
    RECONNECT_BASE_DELAY = 1  # seconds
    RECONNECT_MAX_DELAY = 60  # seconds
    
    # Message queue settings
    MESSAGE_QUEUE_SIZE = 10000
    
    def __init__(
        self,
        stream_processor: StreamProcessor,
        account_id: str,
        auth_service=None
    ):
        """
        Initialize WebSocket client.
        
        Args:
            stream_processor: Stream processor instance for handling ticks
            account_id: Schwab account ID for streaming
            auth_service: Optional auth service instance
        """
        self.stream_processor = stream_processor
        self.account_id = account_id
        self.auth_service = auth_service
        
        # Connection state
        self.websocket: Optional[Any] = None  # WebSocket connection object
        self.state = ConnectionState.DISCONNECTED
        self.streaming_params: Optional[Dict[str, Any]] = None
        
        # Subscriptions
        self.subscriptions: Dict[str, Set[str]] = {}  # service -> symbols
        self.pending_subscriptions: List[Dict[str, Any]] = []
        
        # Tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        
        # Message handling
        self._message_queue = asyncio.Queue(maxsize=self.MESSAGE_QUEUE_SIZE)
        self._message_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        
        # Reconnection
        self._reconnect_attempts = 0
        self._last_connect_time: Optional[float] = None
        
        # Running state
        self._running = False
        self._shutdown_event = asyncio.Event()
        
        logger.info(f"WebSocket client initialized for account {account_id}")
    
    async def connect(self) -> bool:
        """
        Establish WebSocket connection and authenticate.
        
        Returns:
            True if connection established successfully
        """
        if self.state not in [ConnectionState.DISCONNECTED, ConnectionState.RECONNECTING]:
            logger.warning(f"Cannot connect in state {self.state}")
            return False
        
        try:
            self.state = ConnectionState.CONNECTING
            
            # Get streaming parameters from auth service
            if not self.streaming_params:
                await self._get_streaming_params()
            
            # Connect to WebSocket
            logger.info(f"Connecting to WebSocket: {self.WS_URL}")
            self.websocket = await websockets.connect(
                self.WS_URL,
                ping_interval=None,  # We'll manage heartbeat ourselves
                ping_timeout=None,
                close_timeout=10,
                max_size=10 * 1024 * 1024,  # 10MB max message size
                compression=None
            )
            
            self.state = ConnectionState.CONNECTED
            self._last_connect_time = time.time()
            logger.info("WebSocket connection established")
            
            # Start background tasks BEFORE authentication
            self._running = True
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            # Give receive loop time to start
            await asyncio.sleep(0.1)
            
            # Now authenticate
            await self._authenticate()
            
            # Resubscribe to previous subscriptions
            if self.subscriptions:
                await self._resubscribe_all()
            
            # Reset reconnect attempts on successful connection
            self._reconnect_attempts = 0
            
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.state = ConnectionState.ERROR
            await self._handle_connection_failure()
            return False
    
    async def disconnect(self):
        """Gracefully disconnect WebSocket."""
        logger.info("Disconnecting WebSocket")
        
        self._running = False
        self._shutdown_event.set()
        
        # Cancel tasks
        tasks = [self._heartbeat_task, self._receive_task, self._reconnect_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Close WebSocket
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
            finally:
                self.websocket = None
        
        self.state = ConnectionState.DISCONNECTED
        logger.info("WebSocket disconnected")
    
    async def subscribe(
        self,
        symbols: List[str],
        data_types: List[str] = None
    ):
        """
        Subscribe to real-time data for symbols.
        
        Args:
            symbols: List of symbols to subscribe to
            data_types: Types of data to receive (default: ["QUOTE", "TRADE"])
        """
        if not data_types:
            data_types = ["QUOTE", "TRADE"]
        
        # Store subscription for reconnection
        for data_type in data_types:
            if data_type not in self.subscriptions:
                self.subscriptions[data_type] = set()
            self.subscriptions[data_type].update(symbols)
        
        if self.state != ConnectionState.AUTHENTICATED:
            # Queue subscription for when we're connected
            self.pending_subscriptions.append({
                'symbols': symbols,
                'data_types': data_types
            })
            logger.info(f"Queued subscription for {len(symbols)} symbols")
            return
        
        # Send subscription request
        await self._send_subscription_request(symbols, data_types)
    
    async def unsubscribe(
        self,
        symbols: List[str],
        data_types: List[str] = None
    ):
        """
        Unsubscribe from real-time data for symbols.
        
        Args:
            symbols: List of symbols to unsubscribe from
            data_types: Types of data to unsubscribe (default: all)
        """
        if not data_types:
            data_types = list(self.subscriptions.keys())
        
        # Remove from stored subscriptions
        for data_type in data_types:
            if data_type in self.subscriptions:
                self.subscriptions[data_type].difference_update(symbols)
                if not self.subscriptions[data_type]:
                    del self.subscriptions[data_type]
        
        if self.state != ConnectionState.AUTHENTICATED:
            logger.warning("Cannot unsubscribe while not authenticated")
            return
        
        # Send unsubscribe request
        await self._send_unsubscription_request(symbols, data_types)
    
    # Private methods
    
    async def _get_streaming_params(self):
        """Get streaming parameters from auth service."""
        if not self.auth_service:
            self.auth_service = get_auth_service()
            await self.auth_service.initialize()
        
        # Get user principals which contains streaming info
        client = self.auth_service.get_client()
        
        # Note: This is based on schwab-py StreamClient implementation
        # The actual method may vary - check schwab-py docs
        response = await client.get_user_preferences()
        
        # Extract streaming parameters
        # This structure may need adjustment based on actual API response
        streamer_info_list = response.get('streamerInfo', [])
        if not streamer_info_list:
            raise ValueError("No streaming info found in user preferences")
        streaming_info = streamer_info_list[0]
        
        self.streaming_params = {
            'token': streaming_info.get('token'),
            'app_id': streaming_info.get('appId'),
            'streamer_url': streaming_info.get('streamerSocketUrl'),
            'user_group': streaming_info.get('userGroup'),
            'access_level': streaming_info.get('accessLevel'),
            'acl': streaming_info.get('acl'),
            'timestamp': int(time.time() * 1000)
        }
        
        # Update WebSocket URL if provided
        if self.streaming_params.get('streamer_url'):
            self.WS_URL = self.streaming_params['streamer_url']
        
        logger.info("Retrieved streaming parameters")
    
    async def _authenticate(self):
        """Authenticate with Schwab streaming server."""
        auth_request = {
            "requests": [{
                "service": "ADMIN",
                "command": "LOGIN",
                "requestid": self._get_next_request_id(),
                "account": self.account_id,
                "source": self.streaming_params.get('app_id'),
                "parameters": {
                    "credential": self._build_credential(),
                    "version": "1.0"
                }
            }]
        }
        
        # Send auth request
        response = await self._send_and_wait(auth_request)
        
        if response:
            response_list = response.get('response', [])
            if response_list and len(response_list) > 0:
                if response_list[0].get('content', {}).get('code') == 0:
                    self.state = ConnectionState.AUTHENTICATED
                    logger.info("WebSocket authenticated successfully")
                    return
        
        raise Exception(f"Authentication failed: {response}")
    
    def _build_credential(self) -> str:
        """Build credential string for authentication."""
        # Based on schwab-py implementation
        params = self.streaming_params
        
        # Handle account ID parsing for both real and test accounts
        account_parts = self.account_id.split('-') if '-' in self.account_id else [self.account_id, '000']
        
        credential_parts = [
            f"userid={self.account_id}",
            f"token={params.get('token')}",
            f"company={account_parts[0]}",  # Extract company from account
            f"segment={params.get('user_group', 'ACCT')}",
            f"cddomain=A000000{account_parts[1] if len(account_parts) > 1 else '000'}",  # Format may vary
            f"usergroup={params.get('user_group')}",
            f"accesslevel={params.get('access_level')}",
            f"authorized=Y",
            f"timestamp={params.get('timestamp')}",
            f"appid={params.get('app_id')}",
            f"acl={params.get('acl')}"
        ]
        
        return "&".join(credential_parts)
    
    async def _send_subscription_request(
        self,
        symbols: List[str],
        data_types: List[str]
    ):
        """Send subscription request for symbols."""
        # Map data types to Schwab services
        service_map = {
            "QUOTE": "QUOTE",
            "TRADE": "TIMESALE",
            "LEVEL2": "NASDAQ_BOOK",
            "OPTIONS": "OPTION"
        }
        
        requests = []
        for data_type in data_types:
            service = service_map.get(data_type, data_type)
            
            request = {
                "service": service,
                "command": "SUBS",
                "requestid": self._get_next_request_id(),
                "account": self.account_id,
                "source": self.streaming_params.get('app_id'),
                "parameters": {
                    "keys": ",".join(symbols),
                    "fields": "0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15"  # All fields
                }
            }
            requests.append(request)
        
        message = {"requests": requests}
        await self._send_message(message)
        logger.info(f"Subscribed to {len(symbols)} symbols for {data_types}")
    
    async def _send_unsubscription_request(
        self,
        symbols: List[str],
        data_types: List[str]
    ):
        """Send unsubscription request for symbols."""
        service_map = {
            "QUOTE": "QUOTE",
            "TRADE": "TIMESALE",
            "LEVEL2": "NASDAQ_BOOK",
            "OPTIONS": "OPTION"
        }
        
        requests = []
        for data_type in data_types:
            service = service_map.get(data_type, data_type)
            
            request = {
                "service": service,
                "command": "UNSUBS",
                "requestid": self._get_next_request_id(),
                "account": self.account_id,
                "source": self.streaming_params.get('app_id'),
                "parameters": {
                    "keys": ",".join(symbols)
                }
            }
            requests.append(request)
        
        message = {"requests": requests}
        await self._send_message(message)
        logger.info(f"Unsubscribed from {len(symbols)} symbols for {data_types}")
    
    async def _resubscribe_all(self):
        """Resubscribe to all stored subscriptions after reconnection."""
        logger.info("Resubscribing to all previous subscriptions")
        
        for data_type, symbols in self.subscriptions.items():
            if symbols:
                await self._send_subscription_request(list(symbols), [data_type])
        
        # Process pending subscriptions
        while self.pending_subscriptions:
            sub = self.pending_subscriptions.pop(0)
            await self._send_subscription_request(sub['symbols'], sub['data_types'])
    
    async def _send_message(self, message: Dict[str, Any]):
        """Send message to WebSocket."""
        if not self.websocket:
            raise RuntimeError("WebSocket not connected")
        
        message_str = json.dumps(message)
        await self.websocket.send(message_str)
        logger.debug(f"Sent message: {message_str[:200]}...")
    
    async def _send_and_wait(
        self,
        message: Dict[str, Any],
        timeout: float = 5.0
    ) -> Optional[Dict[str, Any]]:
        """Send message and wait for response."""
        request_id = message['requests'][0]['requestid']
        future = asyncio.Future()
        self._pending_requests[request_id] = future
        
        try:
            await self._send_message(message)
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.error(f"Request {request_id} timed out")
            return None
        finally:
            self._pending_requests.pop(request_id, None)
    
    def _get_next_request_id(self) -> int:
        """Get next message request ID."""
        self._message_id += 1
        return self._message_id
    
    # Background tasks
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats to keep connection alive."""
        logger.info("Starting heartbeat loop")
        
        while self._running:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                
                if self.state == ConnectionState.AUTHENTICATED:
                    heartbeat = {
                        "requests": [{
                            "service": "ADMIN",
                            "command": "HEARTBEAT",
                            "requestid": self._get_next_request_id(),
                            "account": self.account_id,
                            "source": self.streaming_params.get('app_id')
                        }]
                    }
                    await self._send_message(heartbeat)
                    logger.debug("Heartbeat sent")
                    
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await self._handle_connection_failure()
    
    async def _receive_loop(self):
        """Receive and process messages from WebSocket."""
        logger.info("Starting receive loop")
        
        while self._running:
            try:
                if not self.websocket:
                    logger.debug("No websocket connection, sleeping...")
                    await asyncio.sleep(1)
                    continue
                
                logger.debug("Waiting for message...")
                message = await self.websocket.recv()
                logger.info(f"Received message: {message[:100]}...")
                await self._handle_message(message)
                
            except ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                await self._handle_connection_failure()
                break
                
            except Exception as e:
                logger.error(f"Receive error: {e}")
                if self._running:
                    await asyncio.sleep(0.1)
    
    async def _handle_message(self, message: str):
        """Process incoming WebSocket message."""
        try:
            data = json.loads(message)
            
            # Handle response to our requests
            if 'response' in data:
                for response in data.get('response', []):
                    request_id = response.get('requestid')
                    if request_id in self._pending_requests:
                        self._pending_requests[request_id].set_result(data)
            
            # Handle data messages
            if 'data' in data:
                for item in data.get('data', []):
                    service = item.get('service')
                    if service in ['QUOTE', 'TIMESALE']:
                        await self._process_market_data(item)
            
            # Handle notify messages (heartbeat responses, etc.)
            if 'notify' in data:
                for notification in data.get('notify', []):
                    if notification.get('service') == 'ADMIN':
                        logger.debug(f"Admin notification: {notification.get('content')}")
                        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _process_market_data(self, data: Dict[str, Any]):
        """Process market data and convert to ticks."""
        service = data.get('service')
        timestamp = datetime.fromtimestamp(
            data.get('timestamp', 0) / 1000,
            tz=timezone.utc
        )
        
        for content in data.get('content', []):
            try:
                symbol = content.get('key')
                
                if service == 'QUOTE':
                    # Map field numbers to names
                    # Based on Schwab streaming API documentation
                    bid_price = float(content.get('1', content.get('BID_PRICE', 0)))
                    ask_price = float(content.get('2', content.get('ASK_PRICE', 0)))
                    last_price = float(content.get('3', content.get('LAST_PRICE', 0)))
                    bid_size = int(content.get('4', content.get('BID_SIZE', 0)))
                    ask_size = int(content.get('5', content.get('ASK_SIZE', 0)))
                    
                    # Create bid/ask ticks
                    if bid_price > 0:
                        bid_tick = Tick(
                            symbol=symbol,
                            price=bid_price,
                            volume=bid_size,
                            timestamp=timestamp,
                            tick_type=TickType.BID,
                            bid_price=bid_price,
                            bid_size=bid_size,
                            ask_price=ask_price,
                            ask_size=ask_size
                        )
                        await self.stream_processor.add_tick(bid_tick)
                    
                    if ask_price > 0:
                        ask_tick = Tick(
                            symbol=symbol,
                            price=ask_price,
                            volume=ask_size,
                            timestamp=timestamp,
                            tick_type=TickType.ASK,
                            bid_price=bid_price,
                            bid_size=bid_size,
                            ask_price=ask_price,
                            ask_size=ask_size
                        )
                        await self.stream_processor.add_tick(ask_tick)
                
                elif service == 'TIMESALE':
                    # Map field numbers to names for TIMESALE
                    # Field 2 is the trade price, field 3 is the trade size
                    trade_price = float(content.get('2', content.get('LAST_PRICE', 0)))
                    trade_size = int(content.get('3', content.get('LAST_SIZE', 0)))
                    trade_time = content.get('1', content.get('TRADE_TIME'))
                    sequence = content.get('4', content.get('SEQUENCE'))
                    
                    # Validate price
                    if trade_price <= 0:
                        raise ValueError(f"Invalid price: {trade_price}")
                    
                    # Create trade tick
                    trade_tick = Tick(
                        symbol=symbol,
                        price=trade_price,
                        volume=trade_size,
                        timestamp=timestamp,
                        tick_type=TickType.TRADE,
                        sequence_id=sequence
                    )
                    await self.stream_processor.add_tick(trade_tick)
                    
            except Exception as e:
                logger.error(f"Error processing market data for {symbol}: {e}")
    
    async def _handle_connection_failure(self):
        """Handle connection failure and initiate reconnection."""
        self.state = ConnectionState.DISCONNECTED
        
        if self.websocket:
            try:
                await self.websocket.close()
            except:
                pass
            self.websocket = None
        
        if self._running and not self._reconnect_task:
            self._reconnect_task = asyncio.create_task(self._reconnect())
    
    async def _reconnect(self):
        """Handle reconnection with exponential backoff."""
        self.state = ConnectionState.RECONNECTING
        
        while self._running and self._reconnect_attempts < self.RECONNECT_MAX_ATTEMPTS:
            self._reconnect_attempts += 1
            
            # Calculate backoff delay
            delay = min(
                self.RECONNECT_BASE_DELAY * (2 ** (self._reconnect_attempts - 1)),
                self.RECONNECT_MAX_DELAY
            )
            
            logger.info(
                f"Reconnection attempt {self._reconnect_attempts}/{self.RECONNECT_MAX_ATTEMPTS} "
                f"in {delay} seconds"
            )
            
            await asyncio.sleep(delay)
            
            if await self.connect():
                logger.info("Reconnection successful")
                self._reconnect_task = None
                return
        
        logger.error("Max reconnection attempts reached")
        self.state = ConnectionState.ERROR
    
    # Context manager support
    
    async def __aenter__(self):
        """Enter async context."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        await self.disconnect()


# Utility function
@asynccontextmanager
async def create_websocket_client(
    stream_processor: StreamProcessor,
    account_id: str
) -> SchwabWebSocketClient:
    """
    Create and manage a WebSocket client as a context manager.
    
    Args:
        stream_processor: Stream processor for handling ticks
        account_id: Schwab account ID
        
    Yields:
        Connected WebSocket client
    """
    client = SchwabWebSocketClient(stream_processor, account_id)
    
    try:
        await client.connect()
        yield client
    finally:
        await client.disconnect()