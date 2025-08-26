"""Schwab streaming client for real-time market data."""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from enum import Enum

from schwab.streaming import StreamClient as SchwabStreamClient
from schwab.client import Client

from ..broker.schwab_client import get_schwab_broker
from ..utils.logger import get_logger

logger = get_logger(__name__)


class StreamingState(str, Enum):
    """Streaming connection states."""
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    AUTHENTICATED = "AUTHENTICATED"
    SUBSCRIBING = "SUBSCRIBING"
    STREAMING = "STREAMING"
    ERROR = "ERROR"
    RECONNECTING = "RECONNECTING"


class StreamingClient:
    """
    Wrapper around Schwab's StreamClient for real-time market data.
    
    Features:
    - Automatic authentication and connection management
    - Symbol subscription management
    - Reconnection logic with exponential backoff
    - Message handling and routing
    - Error recovery
    """
    
    def __init__(self, account_id: Optional[str] = None):
        """
        Initialize streaming client.
        
        Args:
            account_id: Schwab account ID (will fetch if not provided)
        """
        self.account_id = account_id
        self.schwab_broker = None
        self.stream_client = None
        self.state = StreamingState.DISCONNECTED
        
        # Subscription management
        self.subscribed_symbols: Dict[str, List[str]] = {
            'equity': [],
            'option': [],
            'futures': []
        }
        
        # Message handlers
        self.handlers: Dict[str, List[Callable]] = {}
        
        # Connection management
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        self._reconnect_delay = 1  # seconds
        self._reconnect_task = None
        self._message_handler_task = None
        self._running = False
        
    async def initialize(self):
        """Initialize the streaming client."""
        logger.info("Initializing streaming client")
        
        try:
            # Get broker instance
            self.schwab_broker = await get_schwab_broker()
            
            # Get account ID if not provided
            if not self.account_id:
                accounts = await self.schwab_broker.get_account_numbers()
                if not accounts:
                    raise ValueError("No accounts found")
                self.account_id = accounts[0]
                logger.info(f"Using account ID: {self.account_id[:4]}...")
            
            # Get the authenticated client
            client = self.schwab_broker.client
            
            # Create StreamClient using schwab-py
            self.stream_client = SchwabStreamClient(
                client=client,
                account_id=int(self.account_id)  # Convert to int
            )
            
            self.state = StreamingState.CONNECTING
            logger.info("Streaming client initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize streaming client: {e}")
            self.state = StreamingState.ERROR
            raise
    
    async def connect(self):
        """Establish WebSocket connection to Schwab streaming API."""
        if not self.stream_client:
            await self.initialize()
        
        try:
            logger.info("Connecting to Schwab streaming API")
            self.state = StreamingState.CONNECTING
            
            # Login to streaming service
            await self.stream_client.login()
            
            self.state = StreamingState.AUTHENTICATED
            self._reconnect_attempts = 0
            logger.info("Successfully connected and authenticated")
            
            # Start message handler
            self._running = True
            self._message_handler_task = asyncio.create_task(self._handle_messages())
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self.state = StreamingState.ERROR
            await self._schedule_reconnect()
            raise
    
    async def disconnect(self):
        """Disconnect from streaming API."""
        logger.info("Disconnecting from streaming API")
        self._running = False
        
        try:
            if self._message_handler_task:
                self._message_handler_task.cancel()
                try:
                    await self._message_handler_task
                except asyncio.CancelledError:
                    pass
            
            if self.stream_client and self.state in [StreamingState.AUTHENTICATED, StreamingState.STREAMING]:
                await self.stream_client.logout()
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
        finally:
            self.state = StreamingState.DISCONNECTED
            logger.info("Disconnected from streaming API")
    
    async def subscribe_equity_quotes(self, symbols: List[str]):
        """
        Subscribe to Level 1 equity quotes.
        
        Args:
            symbols: List of equity symbols to subscribe to
        """
        if self.state != StreamingState.AUTHENTICATED and self.state != StreamingState.STREAMING:
            raise RuntimeError(f"Cannot subscribe in state: {self.state}")
        
        try:
            logger.info(f"Subscribing to equity quotes: {symbols}")
            
            # Subscribe using schwab-py
            await self.stream_client.level_one_equity_subs(symbols)
            
            # Track subscriptions
            self.subscribed_symbols['equity'].extend(symbols)
            self.subscribed_symbols['equity'] = list(set(self.subscribed_symbols['equity']))
            
            self.state = StreamingState.STREAMING
            logger.info(f"Successfully subscribed to {len(symbols)} equity symbols")
            
        except Exception as e:
            logger.error(f"Failed to subscribe to equity quotes: {e}")
            raise
    
    async def unsubscribe_equity_quotes(self, symbols: List[str]):
        """
        Unsubscribe from Level 1 equity quotes.
        
        Args:
            symbols: List of equity symbols to unsubscribe from
        """
        if self.state != StreamingState.STREAMING:
            return
        
        try:
            logger.info(f"Unsubscribing from equity quotes: {symbols}")
            
            # Unsubscribe using schwab-py
            await self.stream_client.level_one_equity_unsubs(symbols)
            
            # Update tracked subscriptions
            for symbol in symbols:
                if symbol in self.subscribed_symbols['equity']:
                    self.subscribed_symbols['equity'].remove(symbol)
            
            logger.info(f"Successfully unsubscribed from {len(symbols)} equity symbols")
            
        except Exception as e:
            logger.error(f"Failed to unsubscribe from equity quotes: {e}")
            raise
    
    async def subscribe_chart_equity(self, symbols: List[str]):
        """
        Subscribe to equity chart data (OHLCV).
        
        Args:
            symbols: List of equity symbols to subscribe to
        """
        if self.state != StreamingState.AUTHENTICATED and self.state != StreamingState.STREAMING:
            raise RuntimeError(f"Cannot subscribe in state: {self.state}")
        
        try:
            logger.info(f"Subscribing to equity charts: {symbols}")
            
            # Subscribe using schwab-py
            await self.stream_client.chart_equity_subs(symbols)
            
            # Track subscriptions (reuse equity list for now)
            self.subscribed_symbols['equity'].extend(symbols)
            self.subscribed_symbols['equity'] = list(set(self.subscribed_symbols['equity']))
            
            self.state = StreamingState.STREAMING
            logger.info(f"Successfully subscribed to chart data for {len(symbols)} symbols")
            
        except Exception as e:
            logger.error(f"Failed to subscribe to chart data: {e}")
            raise
    
    def add_handler(self, service: str, handler: Callable[[Dict[str, Any]], None]):
        """
        Add a message handler for a specific service.
        
        Args:
            service: Service name (e.g., 'LEVELONE_EQUITIES', 'CHART_EQUITY')
            handler: Async function to handle messages
        """
        if service not in self.handlers:
            self.handlers[service] = []
        
        self.handlers[service].append(handler)
        logger.debug(f"Added handler for service: {service}")
        
        # Also register with schwab-py StreamClient
        if self.stream_client:
            if service == "LEVELONE_EQUITIES":
                self.stream_client.add_level_one_equity_handler(handler)
            elif service == "CHART_EQUITY":
                self.stream_client.add_chart_equity_handler(handler)
            # Add more services as needed
    
    async def _handle_messages(self):
        """Main message handling loop."""
        logger.info("Starting message handler")
        
        while self._running:
            try:
                # Handle incoming messages
                await self.stream_client.handle_message()
                
            except asyncio.CancelledError:
                logger.info("Message handler cancelled")
                break
                
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                if self._running:
                    await asyncio.sleep(0.1)  # Brief pause before retry
    
    async def _schedule_reconnect(self):
        """Schedule a reconnection attempt."""
        if self._reconnect_task and not self._reconnect_task.done():
            return
        
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error("Maximum reconnection attempts reached")
            self.state = StreamingState.ERROR
            return
        
        self._reconnect_attempts += 1
        delay = min(self._reconnect_delay * (2 ** self._reconnect_attempts), 300)  # Max 5 minutes
        
        logger.info(f"Scheduling reconnection attempt {self._reconnect_attempts} in {delay} seconds")
        self.state = StreamingState.RECONNECTING
        
        self._reconnect_task = asyncio.create_task(self._reconnect(delay))
    
    async def _reconnect(self, delay: float):
        """Attempt to reconnect after delay."""
        await asyncio.sleep(delay)
        
        try:
            logger.info(f"Attempting reconnection #{self._reconnect_attempts}")
            await self.connect()
            
            # Resubscribe to previous symbols
            if self.subscribed_symbols['equity']:
                await self.subscribe_equity_quotes(self.subscribed_symbols['equity'])
            
            logger.info("Reconnection successful")
            
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            await self._schedule_reconnect()
    
    async def get_state(self) -> Dict[str, Any]:
        """Get current streaming client state."""
        return {
            'state': self.state.value,
            'subscriptions': {
                'equity': len(self.subscribed_symbols['equity']),
                'option': len(self.subscribed_symbols['option']),
                'futures': len(self.subscribed_symbols['futures'])
            },
            'reconnect_attempts': self._reconnect_attempts,
            'handlers_registered': len(self.handlers)
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


# Example usage handler
def create_quote_handler(callback: Callable) -> Callable:
    """
    Create a quote handler that processes Level 1 equity data.
    
    Args:
        callback: Function to call with processed quote data
    
    Returns:
        Handler function for schwab-py StreamClient
    """
    async def handler(message: Dict[str, Any]):
        """Process quote message."""
        try:
            # Extract relevant data from message
            service = message.get('service', '')
            content = message.get('content', [])
            
            for item in content:
                symbol = item.get('key', '')
                
                # Create standardized quote object
                quote = {
                    'symbol': symbol,
                    'timestamp': datetime.fromtimestamp(message.get('timestamp', 0) / 1000),
                    'bid': item.get('BID_PRICE', 0),
                    'ask': item.get('ASK_PRICE', 0),
                    'last': item.get('LAST_PRICE', 0),
                    'volume': item.get('TOTAL_VOLUME', 0),
                    'bid_size': item.get('BID_SIZE', 0),
                    'ask_size': item.get('ASK_SIZE', 0),
                    'sequence': item.get('seq', 0)
                }
                
                await callback(quote)
                
        except Exception as e:
            logger.error(f"Error in quote handler: {e}")
    
    return handler


def create_chart_handler(callback: Callable) -> Callable:
    """
    Create a chart handler that processes OHLCV data.
    
    Args:
        callback: Function to call with processed chart data
    
    Returns:
        Handler function for schwab-py StreamClient
    """
    async def handler(message: Dict[str, Any]):
        """Process chart message."""
        try:
            content = message.get('content', [])
            
            for item in content:
                symbol = item.get('key', '')
                
                # Create standardized candle object
                candle = {
                    'symbol': symbol,
                    'timestamp': datetime.fromtimestamp(item.get('CHART_TIME_MILLIS', 0) / 1000),
                    'open': item.get('OPEN_PRICE', 0),
                    'high': item.get('HIGH_PRICE', 0),
                    'low': item.get('LOW_PRICE', 0),
                    'close': item.get('CLOSE_PRICE', 0),
                    'volume': item.get('VOLUME', 0),
                    'sequence': item.get('SEQUENCE', 0),
                    'chart_day': item.get('CHART_DAY', 0)
                }
                
                await callback(candle)
                
        except Exception as e:
            logger.error(f"Error in chart handler: {e}")
    
    return handler