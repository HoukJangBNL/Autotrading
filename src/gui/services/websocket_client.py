"""
GUI WebSocket Client for real-time market data.
Integrates with existing WebSocket streaming infrastructure.
"""

import asyncio
import json
import logging
from typing import Dict, Set, Callable, Optional
from datetime import datetime
import websockets

from PySide6.QtCore import QObject, Signal, QThread, QTimer
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)


class WebSocketWorker(QThread):
    """Worker thread for WebSocket operations."""
    
    message_received = Signal(dict)
    connection_status_changed = Signal(bool, str)
    error_occurred = Signal(str)
    
    def __init__(self, url: str, subscriptions: Set[str]):
        super().__init__()
        self.url = url
        self.subscriptions = subscriptions
        self.websocket = None
        self.running = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        
    def run(self):
        """Main WebSocket event loop."""
        self.running = True
        asyncio.run(self._websocket_loop())
    
    async def _websocket_loop(self):
        """WebSocket connection and message handling loop."""
        while self.running:
            try:
                await self._connect_and_listen()
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.error_occurred.emit(str(e))
                
                if self.reconnect_attempts < self.max_reconnect_attempts:
                    self.reconnect_attempts += 1
                    await asyncio.sleep(5)  # Wait before reconnecting
                else:
                    self.error_occurred.emit("Max reconnection attempts reached")
                    break
    
    async def _connect_and_listen(self):
        """Connect to WebSocket and listen for messages."""
        try:
            self.connection_status_changed.emit(False, "Connecting...")
            
            async with websockets.connect(self.url) as websocket:
                self.websocket = websocket
                self.reconnect_attempts = 0
                self.connection_status_changed.emit(True, "Connected")
                
                # Send subscription requests
                await self._send_subscriptions()
                
                # Listen for messages
                async for message in websocket:
                    if not self.running:
                        break
                        
                    try:
                        data = json.loads(message)
                        self.message_received.emit(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error: {e}")
                        
        except websockets.exceptions.ConnectionClosed:
            self.connection_status_changed.emit(False, "Connection closed")
        except Exception as e:
            self.connection_status_changed.emit(False, f"Connection error: {str(e)}")
            raise
    
    async def _send_subscriptions(self):
        """Send subscription messages for symbols."""
        if not self.websocket:
            return
            
        for symbol in self.subscriptions:
            subscription_msg = {
                "service": "LEVELONE_EQUITIES",
                "command": "SUBS",
                "requestid": f"sub_{symbol}",
                "SchwabClientCustomerId": "user_id",
                "SchwabClientCorrelId": "correlation_id",
                "parameters": {
                    "keys": symbol,
                    "fields": "0,1,2,3,4,5,8,9,10,11,12,13"  # OHLCV and more
                }
            }
            
            await self.websocket.send(json.dumps(subscription_msg))
            logger.info(f"Subscribed to {symbol}")
    
    def add_subscription(self, symbol: str):
        """Add a new symbol subscription."""
        self.subscriptions.add(symbol.upper())
        
        # If connected, send subscription immediately
        if self.websocket and not self.websocket.closed:
            asyncio.create_task(self._send_single_subscription(symbol))
    
    async def _send_single_subscription(self, symbol: str):
        """Send subscription for a single symbol."""
        subscription_msg = {
            "service": "LEVELONE_EQUITIES",
            "command": "SUBS",
            "requestid": f"sub_{symbol}",
            "parameters": {
                "keys": symbol,
                "fields": "0,1,2,3,4,5,8,9,10,11,12,13"
            }
        }
        
        await self.websocket.send(json.dumps(subscription_msg))
    
    def stop(self):
        """Stop the WebSocket worker."""
        self.running = False
        if self.websocket:
            asyncio.create_task(self.websocket.close())


class GUIWebSocketClient(QObject):
    """
    GUI WebSocket client for real-time market data.
    Integrates with existing streaming infrastructure.
    """
    
    # Signals for GUI updates
    market_data_received = Signal(dict)
    connection_status_changed = Signal(bool, str)
    error_occurred = Signal(str)
    
    def __init__(self, websocket_url: Optional[str] = None):
        super().__init__()
        
        # Configuration
        self.websocket_url = websocket_url or "wss://streamer-api.schwab.com"
        self.subscribed_symbols = set()
        
        # Worker thread
        self.worker = None
        
        # Data processing
        self.last_data = {}
        self.data_cache = {}
        
        # Heartbeat timer
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self._check_connection)
        
        logger.info(f"GUIWebSocketClient initialized with URL: {self.websocket_url}")
    
    def connect_websocket(self, symbols: Set[str] = None):
        """Connect to WebSocket stream."""
        if self.worker and self.worker.isRunning():
            self.disconnect()
        
        if symbols:
            self.subscribed_symbols.update(symbols)
        
        # Create and start worker thread
        self.worker = WebSocketWorker(self.websocket_url, self.subscribed_symbols)
        
        # Connect signals
        self.worker.message_received.connect(self._handle_message)
        self.worker.connection_status_changed.connect(self._handle_connection_status)
        self.worker.error_occurred.connect(self._handle_error)
        
        # Start worker
        self.worker.start()
        
        # Start heartbeat monitoring
        self.heartbeat_timer.start(30000)  # Check every 30 seconds
        
        logger.info(f"WebSocket client connecting with {len(self.subscribed_symbols)} symbols")
    
    def disconnect(self):
        """Disconnect from WebSocket stream."""
        self.heartbeat_timer.stop()
        
        if self.worker:
            self.worker.stop()
            self.worker.wait(5000)  # Wait up to 5 seconds
            self.worker = None
        
        logger.info("WebSocket client disconnected")
    
    def subscribe_symbol(self, symbol: str):
        """Subscribe to a new symbol."""
        symbol = symbol.upper()
        self.subscribed_symbols.add(symbol)
        
        if self.worker and self.worker.isRunning():
            self.worker.add_subscription(symbol)
        
        logger.info(f"Subscribed to {symbol}")
    
    def unsubscribe_symbol(self, symbol: str):
        """Unsubscribe from a symbol."""
        symbol = symbol.upper()
        self.subscribed_symbols.discard(symbol)
        
        # TODO: Send unsubscribe message to WebSocket
        logger.info(f"Unsubscribed from {symbol}")
    
    def get_subscribed_symbols(self) -> Set[str]:
        """Get currently subscribed symbols."""
        return self.subscribed_symbols.copy()
    
    def _handle_message(self, data: Dict):
        """Handle incoming WebSocket message."""
        try:
            # Process based on message type
            if 'service' in data and data['service'] == 'LEVELONE_EQUITIES':
                self._process_market_data(data)
            elif 'heartbeat' in data:
                self._process_heartbeat(data)
            else:
                logger.debug(f"Unhandled message type: {data}")
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            self.error_occurred.emit(f"Message processing error: {str(e)}")
    
    def _process_market_data(self, data: Dict):
        """Process level-one market data."""
        try:
            content = data.get('content', [])
            
            for item in content:
                symbol = item.get('key', '')
                if not symbol:
                    continue
                
                # Extract relevant fields (Schwab field mapping)
                fields = item.get('content', {})
                
                processed_data = {
                    'symbol': symbol,
                    'price': fields.get('1', 0.0),  # Last price
                    'bid': fields.get('2', 0.0),    # Bid price
                    'ask': fields.get('3', 0.0),    # Ask price
                    'volume': fields.get('8', 0),   # Total volume
                    'high': fields.get('4', 0.0),   # Day high
                    'low': fields.get('5', 0.0),    # Day low
                    'open': fields.get('9', 0.0),   # Day open
                    'close': fields.get('10', 0.0), # Previous close
                    'change': 0.0,  # Will calculate
                    'change_percent': 0.0,  # Will calculate
                    'timestamp': datetime.now()
                }
                
                # Calculate change and percentage
                if processed_data['close'] > 0:
                    processed_data['change'] = processed_data['price'] - processed_data['close']
                    processed_data['change_percent'] = (processed_data['change'] / processed_data['close']) * 100
                
                # Cache the data
                self.data_cache[symbol] = processed_data
                
                # Emit signal for GUI update
                self.market_data_received.emit(processed_data)
                
        except Exception as e:
            logger.error(f"Error processing market data: {e}")
    
    def _process_heartbeat(self, data: Dict):
        """Process heartbeat message."""
        logger.debug("Heartbeat received")
        # Update last heartbeat timestamp
        self.last_heartbeat = datetime.now()
    
    def _handle_connection_status(self, connected: bool, message: str):
        """Handle connection status change."""
        logger.info(f"WebSocket connection status: {connected} - {message}")
        self.connection_status_changed.emit(connected, message)
    
    def _handle_error(self, error_message: str):
        """Handle WebSocket error."""
        logger.error(f"WebSocket error: {error_message}")
        self.error_occurred.emit(error_message)
    
    def _check_connection(self):
        """Check connection health (called by timer)."""
        if self.worker and not self.worker.isRunning():
            self.error_occurred.emit("WebSocket worker stopped unexpectedly")
    
    def get_cached_data(self, symbol: str) -> Optional[Dict]:
        """Get cached data for a symbol."""
        return self.data_cache.get(symbol.upper())
    
    def get_all_cached_data(self) -> Dict[str, Dict]:
        """Get all cached market data."""
        return self.data_cache.copy()
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self.worker and self.worker.isRunning()
    
    def get_connection_info(self) -> Dict:
        """Get connection information."""
        return {
            'url': self.websocket_url,
            'connected': self.is_connected(),
            'subscribed_symbols': len(self.subscribed_symbols),
            'cached_data_points': len(self.data_cache)
        }