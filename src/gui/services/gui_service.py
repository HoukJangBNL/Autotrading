"""
GUI Service Layer for backend integration.
Provides unified interface between Qt GUI and trading system backend.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime
import json

from PySide6.QtCore import QObject, Signal, QThread, QTimer
from PySide6.QtWidgets import QApplication

# Set up logger first
logger = logging.getLogger(__name__)

# Import backend services
try:
    # Import actual backend services
    from ...auth.auth_service import AuthService
    from ...data.streaming_service import StreamingService, StreamingStats
    from ...config.settings import get_settings
    from ...data.stream_processor import Tick, OHLCV
    BACKEND_AVAILABLE = True
except ImportError as e:
    # Fallback for development when backend not available
    logger.warning(f"Backend services not available: {e}")
    AuthService = None
    StreamingService = None
    StreamingStats = None
    get_settings = None
    Tick = None
    OHLCV = None
    BACKEND_AVAILABLE = False


@dataclass
class MarketDataPoint:
    """Market data point for GUI display."""
    symbol: str
    price: float
    volume: int
    change: float
    change_percent: float
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'price': self.price,
            'volume': self.volume,
            'change': self.change,
            'change_percent': self.change_percent,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class DiscoveryAlert:
    """Discovery alert for ticker discovery mode."""
    symbol: str
    alert_type: str  # 'volume_spike', 'price_breakout', 'momentum'
    trigger_value: float
    current_value: float
    message: str
    timestamp: datetime
    severity: str  # 'low', 'medium', 'high'


class AsyncWorker(QThread):
    """Worker thread for async operations in Qt."""
    
    data_received = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, async_func: Callable, *args, **kwargs):
        super().__init__()
        self.async_func = async_func
        self.args = args
        self.kwargs = kwargs
        self.loop = None
        
    def run(self):
        """Run async function in thread."""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            result = self.loop.run_until_complete(
                self.async_func(*self.args, **self.kwargs)
            )
            
            if result:
                self.data_received.emit(result)
                
        except Exception as e:
            logger.error(f"Async worker error: {e}")
            self.error_occurred.emit(str(e))
        finally:
            if self.loop:
                self.loop.close()


class GUIService(QObject):
    """
    Main GUI service for backend integration.
    Handles communication between Qt GUI and trading system backend.
    """
    
    # Signals for GUI updates
    market_data_updated = Signal(dict)
    discovery_alert = Signal(dict)
    connection_status_changed = Signal(bool, str)
    system_error = Signal(str)
    
    def __init__(self, mock_mode: bool = True):
        super().__init__()
        
        # Configuration
        self.mock_mode = mock_mode or not BACKEND_AVAILABLE  # Force mock if backend unavailable
        
        # Backend service instances
        self.auth_service = None
        self.streaming_service = None
        self.settings = None
        
        # Legacy placeholders (for compatibility)
        self.broker_client = None
        self.quote_service = None
        self.stream_processor = None
        
        # State
        self.is_connected = False
        self.discovery_active = False
        self.watched_symbols = set()
        
        # Discovery criteria
        self.discovery_criteria = {
            'volume_spike_threshold': 2.0,  # 2x average volume
            'price_change_threshold': 5.0,  # 5% price change
            'min_volume': 100000,  # Minimum volume filter
            'market_cap_filter': None  # None, 'small', 'mid', 'large'
        }
        
        # Data storage
        self.market_data_cache = {}
        self.discovery_alerts = []
        
        # Timers
        self.discovery_timer = QTimer()
        self.discovery_timer.timeout.connect(self.run_discovery_scan)
        
        # Mock data timer for realistic simulation
        if self.mock_mode:
            self.mock_data_timer = QTimer()
            self.mock_data_timer.timeout.connect(self._generate_mock_market_data)
        
        mode_status = "Mock Mode" if self.mock_mode else "Live Mode"
        logger.info(f"GUIService initialized in {mode_status}")
    
    # Mock Data Generation
    def _generate_mock_market_data(self):
        """Generate realistic mock market data for testing."""
        import random
        
        # Popular stocks for simulation
        symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA', 'AMD', 'META', 'AMZN', 'NFLX', 'CRM']
        
        for symbol in symbols:
            # Generate realistic market data
            base_price = {
                'AAPL': 180, 'GOOGL': 140, 'MSFT': 350, 'TSLA': 250, 'NVDA': 450,
                'AMD': 120, 'META': 320, 'AMZN': 140, 'NFLX': 420, 'CRM': 200
            }.get(symbol, 100)
            
            # Small price movements
            price_change = random.uniform(-5, 5)
            current_price = base_price + price_change
            change_percent = (price_change / base_price) * 100
            
            # Volume with occasional spikes
            base_volume = random.randint(1000000, 5000000)
            if random.random() < 0.1:  # 10% chance of volume spike
                volume = base_volume * random.uniform(3, 8)
            else:
                volume = base_volume
            
            market_data = {
                'symbol': symbol,
                'price': current_price,
                'change': price_change,
                'change_percent': change_percent,
                'volume': int(volume),
                'high': current_price + random.uniform(0, 3),
                'low': current_price - random.uniform(0, 3),
                'timestamp': datetime.now()
            }
            
            # Update cache and emit signal
            self.market_data_cache[symbol] = market_data
            self.market_data_updated.emit(market_data)
    
    # Connection Management
    async def connect_to_backend(self) -> bool:
        """Connect to trading system backend services."""
        if self.mock_mode:
            return await self._connect_mock_backend()
        else:
            return await self._connect_real_backend()
    
    async def _connect_mock_backend(self) -> bool:
        """Connect to mock backend for testing."""
        try:
            # Mock mode - simulate successful connection
            await asyncio.sleep(0.1)  # Simulate connection delay
            self.is_connected = True
            self.connection_status_changed.emit(True, "Connected to Mock Backend (Testing Mode)")
            
            # Start mock data generation
            self.mock_data_timer.start(2000)  # Generate data every 2 seconds
            
            logger.info("Successfully connected to Mock backend services")
            return True
            
        except Exception as e:
            error_msg = f"Failed to connect to mock backend: {str(e)}"
            logger.error(error_msg)
            self.system_error.emit(error_msg)
            return False
    
    async def _connect_real_backend(self) -> bool:
        """Connect to real Schwab backend services."""
        try:
            logger.info("Connecting to real Schwab backend services...")
            
            # 1. Load settings
            if not get_settings:
                raise RuntimeError("Backend settings not available")
            
            self.settings = get_settings()
            logger.info("Settings loaded successfully")
            
            # 2. Initialize authentication
            logger.info("Initializing authentication service...")
            self.auth_service = AuthService()
            await self.auth_service.initialize()
            logger.info("Authentication successful")
            
            # 3. Create streaming service
            logger.info("Creating streaming service...")
            account_id = self.settings.schwab.account_number
            if not account_id:
                raise RuntimeError("Account number not configured")
            
            self.streaming_service = StreamingService(
                account_id=account_id,
                redis_url=self.settings.database.redis_url,
                save_to_db=False,  # Don't save to DB for GUI
                timeframes=[1]  # Only 1-minute bars for GUI
            )
            
            # 4. Initialize streaming service
            await self.streaming_service.initialize()
            logger.info("Streaming service initialized")
            
            # 5. Set up callbacks
            self.streaming_service.on_connection_change(self._on_streaming_connection_change)
            self.streaming_service.on_error(self._on_streaming_error)
            
            self.is_connected = True
            self.connection_status_changed.emit(True, "Connected to Schwab Real Backend")
            logger.info("Successfully connected to real backend services")
            return True
            
        except Exception as e:
            error_msg = f"Failed to connect to real backend: {str(e)}"
            logger.error(error_msg)
            self.system_error.emit(error_msg)
            
            # Fallback to mock mode on error
            logger.warning("Falling back to mock mode due to real backend connection failure")
            self.mock_mode = True
            return await self._connect_mock_backend()
    
    async def disconnect_from_backend(self):
        """Disconnect from backend services."""
        try:
            self.stop_discovery()
            
            if self.mock_mode:
                await self._disconnect_mock_backend()
            else:
                await self._disconnect_real_backend()
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    async def _disconnect_mock_backend(self):
        """Disconnect from mock backend."""
        # Stop mock data generation
        if hasattr(self, 'mock_data_timer'):
            self.mock_data_timer.stop()
        
        self.is_connected = False
        self.connection_status_changed.emit(False, "Disconnected from Mock backend")
        logger.info("Disconnected from Mock backend services")
    
    async def _disconnect_real_backend(self):
        """Disconnect from real backend services."""
        # Stop streaming service
        if self.streaming_service:
            await self.streaming_service.stop_streaming()
            self.streaming_service = None
        
        # Close auth service
        if self.auth_service:
            # AuthService cleanup if needed
            self.auth_service = None
        
        self.is_connected = False
        self.connection_status_changed.emit(False, "Disconnected from Schwab backend")
        logger.info("Disconnected from real backend services")
    
    # Streaming Service Callbacks
    async def _on_streaming_connection_change(self, connected: bool):
        """Handle streaming connection state changes."""
        status = "Connected" if connected else "Disconnected"
        message = f"Streaming service {status.lower()}"
        self.connection_status_changed.emit(connected, message)
        logger.info(f"Streaming connection changed: {message}")
    
    async def _on_streaming_error(self, error: Exception):
        """Handle streaming service errors."""
        error_msg = f"Streaming service error: {str(error)}"
        logger.error(error_msg)
        self.system_error.emit(error_msg)
    
    def connect_to_backend_sync(self):
        """Synchronous wrapper for backend connection."""
        worker = AsyncWorker(self.connect_to_backend)
        worker.data_received.connect(lambda result: None)
        worker.error_occurred.connect(lambda error: self.system_error.emit(error))
        worker.start()
        worker.wait()  # Wait for completion
    
    def disconnect_from_backend_sync(self):
        """Synchronous wrapper for backend disconnection."""
        worker = AsyncWorker(self.disconnect_from_backend)
        worker.start()
        worker.wait()
    
    # Discovery Mode Functions
    def start_discovery(self, criteria: Optional[Dict] = None):
        """Start discovery scanning with given criteria."""
        if not self.is_connected:
            self.system_error.emit("Must be connected to start discovery")
            return
            
        if criteria:
            self.discovery_criteria.update(criteria)
            
        self.discovery_active = True
        
        if self.mock_mode:
            self._start_mock_discovery()
        else:
            # Use async worker for real discovery
            worker = AsyncWorker(self._start_real_discovery)
            worker.error_occurred.connect(lambda error: self.system_error.emit(error))
            worker.start()
        
        logger.info(f"Discovery started with criteria: {self.discovery_criteria}")
    
    def _start_mock_discovery(self):
        """Start mock discovery scanning."""
        # Start discovery timer (scan every 5 seconds)
        self.discovery_timer.start(5000)
    
    async def _start_real_discovery(self):
        """Start real discovery scanning with streaming data."""
        try:
            if not self.streaming_service:
                raise RuntimeError("Streaming service not available")
            
            # Define symbols to monitor (popular stocks for discovery)
            discovery_symbols = [
                'AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA', 'AMD', 'META', 'AMZN',
                'NFLX', 'CRM', 'ADBE', 'PYPL', 'INTC', 'CSCO', 'ORCL'
            ]
            
            # Start streaming for discovery symbols
            await self.streaming_service.start_streaming(
                symbols=discovery_symbols,
                data_types=["QUOTE", "TRADE"]
            )
            
            # Start real-time analysis timer
            self.discovery_timer.timeout.disconnect()  # Disconnect mock handler
            self.discovery_timer.timeout.connect(self._analyze_real_market_data)
            self.discovery_timer.start(5000)  # Analyze every 5 seconds
            
            logger.info(f"Real discovery started for {len(discovery_symbols)} symbols")
            
        except Exception as e:
            logger.error(f"Failed to start real discovery: {e}")
            # Fallback to mock discovery
            self._start_mock_discovery()
    
    def stop_discovery(self):
        """Stop discovery scanning."""
        self.discovery_active = False
        self.discovery_timer.stop()
        logger.info("Discovery stopped")
    
    def run_discovery_scan(self):
        """Run discovery scan (called by timer)."""
        if not self.discovery_active or not self.is_connected:
            return
            
        if self.mock_mode:
            # Simulate discovery alerts for mock mode
            self._simulate_discovery_scan()
        else:
            # This should not be called in real mode (uses _analyze_real_market_data instead)
            logger.warning("run_discovery_scan called in real mode - using mock simulation")
            self._simulate_discovery_scan()
    
    def _analyze_real_market_data(self):
        """Analyze real market data for discovery opportunities."""
        if not self.streaming_service or not self.discovery_active:
            return
            
        try:
            # Get recent ticks for all monitored symbols
            recent_ticks = self.streaming_service.get_recent_ticks(limit=100)
            
            if not recent_ticks:
                logger.debug("No recent ticks available for analysis")
                return
            
            # Group ticks by symbol
            symbol_ticks = {}
            for tick in recent_ticks:
                if tick.symbol not in symbol_ticks:
                    symbol_ticks[tick.symbol] = []
                symbol_ticks[tick.symbol].append(tick)
            
            # Analyze each symbol
            for symbol, ticks in symbol_ticks.items():
                self._analyze_symbol_for_discovery(symbol, ticks)
                
            # Update market data display with real data
            self._update_market_data_from_streaming()
            
        except Exception as e:
            logger.error(f"Error analyzing real market data: {e}")
    
    def _analyze_symbol_for_discovery(self, symbol: str, ticks: List):
        """Analyze a symbol's ticks for discovery opportunities."""
        if not ticks or len(ticks) < 2:
            return
            
        try:
            # Get latest tick
            latest_tick = ticks[-1]
            
            # Calculate volume metrics
            recent_volume = sum(tick.volume for tick in ticks[-10:])  # Last 10 ticks
            avg_volume = recent_volume / len(ticks[-10:]) if len(ticks) >= 10 else recent_volume
            
            # Calculate price movement
            price_start = ticks[0].price
            price_current = latest_tick.price
            price_change = ((price_current - price_start) / price_start) * 100
            
            # Check discovery criteria
            volume_threshold = self.discovery_criteria.get('volume_spike_threshold', 2.0)
            price_threshold = self.discovery_criteria.get('price_change_threshold', 5.0)
            min_volume = self.discovery_criteria.get('min_volume', 100000)
            
            alerts_generated = []
            
            # Volume spike detection
            if recent_volume > min_volume and avg_volume > (volume_threshold * 1000):
                alerts_generated.append({
                    'type': 'volume_spike',
                    'trigger_value': volume_threshold,
                    'current_value': avg_volume,
                    'severity': 'high' if avg_volume > (volume_threshold * 3000) else 'medium'
                })
            
            # Price breakout detection
            if abs(price_change) >= price_threshold:
                alerts_generated.append({
                    'type': 'price_breakout',
                    'trigger_value': price_threshold,
                    'current_value': abs(price_change),
                    'severity': 'high' if abs(price_change) > (price_threshold * 2) else 'medium'
                })
            
            # Generate discovery alerts
            for alert_data in alerts_generated:
                alert = DiscoveryAlert(
                    symbol=symbol,
                    alert_type=alert_data['type'],
                    trigger_value=alert_data['trigger_value'],
                    current_value=alert_data['current_value'],
                    message=f"{symbol}: {alert_data['type'].replace('_', ' ').title()} detected - {alert_data['current_value']:.2f}",
                    timestamp=datetime.now(),
                    severity=alert_data['severity']
                )
                
                self.discovery_alerts.append(alert)
                
                # Emit signal for GUI update
                alert_gui_data = {
                    'symbol': alert.symbol,
                    'type': alert.alert_type,
                    'message': alert.message,
                    'severity': alert.severity,
                    'timestamp': alert.timestamp.strftime('%H:%M:%S')
                }
                
                self.discovery_alert.emit(alert_gui_data)
                logger.info(f"Real discovery alert: {alert.message}")
                
        except Exception as e:
            logger.error(f"Error analyzing symbol {symbol}: {e}")
    
    def _update_market_data_from_streaming(self):
        """Update market data display with real streaming data."""
        if not self.streaming_service:
            return
            
        try:
            # Get recent ticks for display
            recent_ticks = self.streaming_service.get_recent_ticks(limit=50)
            
            # Group by symbol and get latest data
            symbol_data = {}
            for tick in recent_ticks:
                if tick.symbol not in symbol_data or tick.timestamp > symbol_data[tick.symbol].timestamp:
                    symbol_data[tick.symbol] = tick
            
            # Convert to GUI format and emit
            for symbol, tick in symbol_data.items():
                # Get recent bars for additional data
                recent_bars = self.streaming_service.get_recent_bars(symbol, timeframe=1, limit=2)
                
                # Calculate change if we have previous data
                change = 0.0
                change_percent = 0.0
                if len(recent_bars) >= 2:
                    prev_close = recent_bars[-2].close
                    current_price = tick.price
                    change = current_price - prev_close
                    change_percent = (change / prev_close) * 100 if prev_close > 0 else 0.0
                
                market_data = {
                    'symbol': symbol,
                    'price': tick.price,
                    'change': change,
                    'change_percent': change_percent,
                    'volume': tick.volume,
                    'high': recent_bars[-1].high if recent_bars else tick.price,
                    'low': recent_bars[-1].low if recent_bars else tick.price,
                    'timestamp': tick.timestamp
                }
                
                # Update cache and emit signal
                self.market_data_cache[symbol] = market_data
                self.market_data_updated.emit(market_data)
                
        except Exception as e:
            logger.error(f"Error updating market data from streaming: {e}")
    
    def _simulate_discovery_scan(self):
        """Simulate discovery scan for development/testing."""
        import random
        
        # Simulate some discovery alerts
        symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA', 'AMD', 'META']
        
        if random.random() < 0.3:  # 30% chance of alert
            symbol = random.choice(symbols)
            alert_type = random.choice(['volume_spike', 'price_breakout', 'momentum'])
            
            alert = DiscoveryAlert(
                symbol=symbol,
                alert_type=alert_type,
                trigger_value=random.uniform(1.5, 10.0),
                current_value=random.uniform(10.0, 50.0),
                message=f"{symbol}: {alert_type.replace('_', ' ').title()} detected",
                timestamp=datetime.now(),
                severity=random.choice(['low', 'medium', 'high'])
            )
            
            self.discovery_alerts.append(alert)
            
            # Emit signal for GUI update
            alert_data = {
                'symbol': alert.symbol,
                'type': alert.alert_type,
                'message': alert.message,
                'severity': alert.severity,
                'timestamp': alert.timestamp.strftime('%H:%M:%S')
            }
            
            self.discovery_alert.emit(alert_data)
            logger.info(f"Discovery alert: {alert.message}")
    
    # Market Data Functions
    async def get_symbol_data(self, symbol: str) -> Optional[MarketDataPoint]:
        """Get current market data for a symbol."""
        try:
            if self.quote_service:
                # Use real quote service
                quote_data = await self.quote_service.get_quote(symbol)
                
                if quote_data:
                    return MarketDataPoint(
                        symbol=symbol,
                        price=quote_data.get('price', 0.0),
                        volume=quote_data.get('volume', 0),
                        change=quote_data.get('change', 0.0),
                        change_percent=quote_data.get('change_percent', 0.0),
                        timestamp=datetime.now()
                    )
            else:
                # Simulate market data for development
                return self._simulate_market_data(symbol)
                
        except Exception as e:
            logger.error(f"Error getting symbol data for {symbol}: {e}")
            return None
    
    def _simulate_market_data(self, symbol: str) -> MarketDataPoint:
        """Simulate market data for development."""
        import random
        
        base_price = random.uniform(50, 500)
        change = random.uniform(-10, 10)
        change_percent = (change / base_price) * 100
        
        return MarketDataPoint(
            symbol=symbol,
            price=base_price + change,
            volume=random.randint(100000, 10000000),
            change=change,
            change_percent=change_percent,
            timestamp=datetime.now()
        )
    
    def get_market_data_sync(self, symbol: str):
        """Synchronous wrapper for market data retrieval."""
        worker = AsyncWorker(self.get_symbol_data, symbol)
        worker.data_received.connect(
            lambda data: self.market_data_updated.emit(data) if data else None
        )
        worker.error_occurred.connect(lambda error: self.system_error.emit(error))
        worker.start()
    
    # Watch List Management
    def add_to_watchlist(self, symbol: str):
        """Add symbol to watch list."""
        symbol = symbol.upper()
        self.watched_symbols.add(symbol)
        logger.info(f"Added {symbol} to watchlist")
    
    def remove_from_watchlist(self, symbol: str):
        """Remove symbol from watch list."""
        symbol = symbol.upper()
        self.watched_symbols.discard(symbol)
        logger.info(f"Removed {symbol} from watchlist")
    
    def get_watchlist(self) -> List[str]:
        """Get current watch list."""
        return sorted(list(self.watched_symbols))
    
    # Criteria Management
    def update_discovery_criteria(self, criteria: Dict):
        """Update discovery criteria."""
        self.discovery_criteria.update(criteria)
        logger.info(f"Updated discovery criteria: {criteria}")
    
    def get_discovery_criteria(self) -> Dict:
        """Get current discovery criteria."""
        return self.discovery_criteria.copy()
    
    # Utility Functions
    def get_connection_status(self) -> tuple[bool, str]:
        """Get current connection status."""
        if self.is_connected:
            return True, "Connected to Schwab backend"
        else:
            return False, "Disconnected"
    
    def get_discovery_status(self) -> tuple[bool, int]:
        """Get discovery status and alert count."""
        return self.discovery_active, len(self.discovery_alerts)
    
    def clear_discovery_alerts(self):
        """Clear all discovery alerts."""
        self.discovery_alerts.clear()
        logger.info("Discovery alerts cleared")
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information for status display."""
        return {
            'connected': self.is_connected,
            'discovery_active': self.discovery_active,
            'watchlist_count': len(self.watched_symbols),
            'alert_count': len(self.discovery_alerts),
            'backend_services': {
                'broker': self.broker_client is not None,
                'quotes': self.quote_service is not None,
                'streaming': self.stream_processor is not None
            }
        }