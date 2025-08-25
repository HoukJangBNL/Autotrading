"""Base strategy class for all trading strategies."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from enum import Enum
import pandas as pd

from src.utils.logger import logger


class SignalType(Enum):
    """Trading signal types."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Signal:
    """Trading signal with metadata."""
    
    def __init__(
        self,
        symbol: str,
        signal_type: SignalType,
        timestamp: datetime,
        strength: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Initialize a trading signal.
        
        Args:
            symbol: Stock symbol
            signal_type: Type of signal (BUY/SELL/HOLD)
            timestamp: Signal generation time
            strength: Signal strength (0.0 to 1.0)
            metadata: Additional signal information
        """
        self.symbol = symbol
        self.signal_type = signal_type
        self.timestamp = timestamp
        self.strength = max(0.0, min(1.0, strength))  # Clamp to [0, 1]
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert signal to dictionary."""
        return {
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "timestamp": self.timestamp.isoformat(),
            "strength": self.strength,
            "metadata": self.metadata
        }


class BaseStrategy(ABC):
    """Abstract base class for trading strategies."""
    
    def __init__(self, name: str, parameters: Optional[Dict[str, Any]] = None):
        """Initialize base strategy.
        
        Args:
            name: Strategy name
            parameters: Strategy parameters
        """
        self.name = name
        self.parameters = parameters or self.get_default_parameters()
        self._validate_parameters()
        self._initialized = False
        
        # Performance tracking
        self.signals_generated = 0
        self.last_signal_time = None
        
        logger.info(f"Initialized strategy: {self.name}")
    
    @abstractmethod
    def get_default_parameters(self) -> Dict[str, Any]:
        """Get default parameters for the strategy.
        
        Returns:
            Dictionary of default parameter values
        """
        pass
    
    @abstractmethod
    def analyze(
        self,
        candles: pd.DataFrame,
        symbol: str
    ) -> Optional[Signal]:
        """Analyze candles and generate trading signal.
        
        Args:
            candles: DataFrame with OHLCV data
                     Expected columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            symbol: Stock symbol being analyzed
            
        Returns:
            Trading signal or None if no action
        """
        pass
    
    @abstractmethod
    def get_required_history(self) -> int:
        """Get number of historical candles required for analysis.
        
        Returns:
            Number of candles needed
        """
        pass
    
    def initialize(self):
        """Initialize strategy (optional override)."""
        self._initialized = True
        logger.info(f"Strategy {self.name} initialized")
    
    def cleanup(self):
        """Cleanup strategy resources (optional override)."""
        logger.info(f"Strategy {self.name} cleaned up")
    
    def update_parameters(self, parameters: Dict[str, Any]):
        """Update strategy parameters.
        
        Args:
            parameters: New parameter values
        """
        self.parameters.update(parameters)
        self._validate_parameters()
        logger.info(f"Updated parameters for {self.name}: {parameters}")
    
    def _validate_parameters(self):
        """Validate strategy parameters (optional override)."""
        # Subclasses can implement parameter validation
        pass
    
    def get_info(self) -> Dict[str, Any]:
        """Get strategy information.
        
        Returns:
            Strategy details
        """
        return {
            "name": self.name,
            "class": self.__class__.__name__,
            "parameters": self.parameters,
            "required_history": self.get_required_history(),
            "signals_generated": self.signals_generated,
            "last_signal_time": self.last_signal_time.isoformat() if self.last_signal_time else None
        }
    
    def preprocess_candles(self, candles: pd.DataFrame) -> pd.DataFrame:
        """Preprocess candles before analysis (optional override).
        
        Args:
            candles: Raw candle data
            
        Returns:
            Preprocessed candles
        """
        # Ensure timestamp is datetime
        if 'timestamp' in candles.columns and not pd.api.types.is_datetime64_any_dtype(candles['timestamp']):
            candles['timestamp'] = pd.to_datetime(candles['timestamp'])
        
        # Sort by timestamp
        candles = candles.sort_values('timestamp')
        
        return candles
    
    def should_trade(self, timestamp: datetime) -> bool:
        """Check if trading is allowed at given time (optional override).
        
        Args:
            timestamp: Current timestamp
            
        Returns:
            True if trading is allowed
        """
        # Subclasses can implement market hours check, etc.
        return True
    
    def calculate_position_size(
        self,
        signal: Signal,
        account_value: float,
        current_price: float
    ) -> int:
        """Calculate position size for a signal (optional override).
        
        Args:
            signal: Trading signal
            account_value: Total account value
            current_price: Current stock price
            
        Returns:
            Number of shares to trade
        """
        # Default: Use fixed percentage of account
        risk_percentage = self.parameters.get('risk_percentage', 0.02)  # 2% default
        position_value = account_value * risk_percentage * signal.strength
        shares = int(position_value / current_price)
        
        return shares