"""Example trading strategies using the framework."""

from typing import Dict, List, Any
from datetime import datetime
from decimal import Decimal
import numpy as np

from .base import BaseStrategy
from .models import Signal, OrderSide, SignalStrength
from ..data.models import TimeFrame


class MovingAverageCrossStrategy(BaseStrategy):
    """
    Simple Moving Average Crossover Strategy.
    
    Generates buy signals when fast MA crosses above slow MA,
    and sell signals when fast MA crosses below slow MA.
    """
    
    def __init__(
        self,
        symbols: List[str],
        fast_period: int = 20,
        slow_period: int = 50,
        **kwargs
    ):
        """
        Initialize MA Cross strategy.
        
        Args:
            symbols: List of symbols to trade
            fast_period: Fast moving average period
            slow_period: Slow moving average period
        """
        super().__init__(
            name="MA_Cross_Strategy",
            symbols=symbols,
            timeframe=TimeFrame.FIVE_MIN,
            **kwargs
        )
        
        self.fast_period = fast_period
        self.slow_period = slow_period
        
        # MA values storage
        self.fast_ma = {}  # symbol -> ma_value
        self.slow_ma = {}  # symbol -> ma_value
        self.prev_fast_ma = {}  # Previous values for crossover detection
        self.prev_slow_ma = {}
    
    async def on_candle(self, symbol: str, candle: Dict[str, Any]) -> None:
        """Process new candle and update moving averages."""
        # Update candle history
        self.update_candle_history(symbol, candle)
        
        # Calculate moving averages if we have enough data
        if symbol in self.candle_history:
            candles = self.candle_history[symbol]
            
            if len(candles) >= self.slow_period:
                # Store previous values
                if symbol in self.fast_ma:
                    self.prev_fast_ma[symbol] = self.fast_ma[symbol]
                if symbol in self.slow_ma:
                    self.prev_slow_ma[symbol] = self.slow_ma[symbol]
                
                # Calculate fast MA
                fast_closes = [float(c['close']) for c in candles[-self.fast_period:]]
                self.fast_ma[symbol] = np.mean(fast_closes)
                
                # Calculate slow MA
                slow_closes = [float(c['close']) for c in candles[-self.slow_period:]]
                self.slow_ma[symbol] = np.mean(slow_closes)
                
                # Store in indicators
                self.indicators[symbol] = {
                    'fast_ma': self.fast_ma[symbol],
                    'slow_ma': self.slow_ma[symbol],
                    'close': float(candle['close'])
                }
    
    async def generate_signals(self) -> List[Signal]:
        """Generate signals based on MA crossovers."""
        signals = []
        
        if not self.is_running():
            return signals
        
        for symbol in self.symbols:
            # Skip if we don't have enough data
            if (symbol not in self.fast_ma or 
                symbol not in self.slow_ma or
                symbol not in self.prev_fast_ma or
                symbol not in self.prev_slow_ma):
                continue
            
            # Skip if we already have a position
            if self.has_position(symbol):
                continue
            
            fast = self.fast_ma[symbol]
            slow = self.slow_ma[symbol]
            prev_fast = self.prev_fast_ma[symbol]
            prev_slow = self.prev_slow_ma[symbol]
            
            # Get current price
            current_price = float(self.candle_history[symbol][-1]['close'])
            
            # Check for bullish crossover
            if prev_fast <= prev_slow and fast > slow:
                signal = Signal(
                    symbol=symbol,
                    direction=OrderSide.BUY,
                    strength=0.8,
                    timestamp=datetime.now(),
                    strategy_name=self.name,
                    stop_loss=current_price * (1 - self.stop_loss_pct),
                    take_profit=current_price * (1 + self.take_profit_pct),
                    reason=f"Bullish MA crossover: {self.fast_period} > {self.slow_period}",
                    confidence=0.7,
                    indicators=self.indicators.get(symbol, {}),
                    entry_price=current_price
                )
                signals.append(signal)
            
            # Check for bearish crossover
            elif prev_fast >= prev_slow and fast < slow:
                signal = Signal(
                    symbol=symbol,
                    direction=OrderSide.SELL,
                    strength=0.8,
                    timestamp=datetime.now(),
                    strategy_name=self.name,
                    stop_loss=current_price * (1 + self.stop_loss_pct),
                    take_profit=current_price * (1 - self.take_profit_pct),
                    reason=f"Bearish MA crossover: {self.fast_period} < {self.slow_period}",
                    confidence=0.7,
                    indicators=self.indicators.get(symbol, {}),
                    entry_price=current_price
                )
                signals.append(signal)
        
        return signals
    
    def calculate_position_size(self, signal: Signal) -> float:
        """Calculate position size based on signal strength."""
        # Base position size from parent class
        max_value = self.get_max_position_value()
        
        # Adjust by signal strength
        position_value = max_value * float(signal.strength) * 0.8  # Conservative sizing
        
        # Calculate shares based on entry price
        if signal.entry_price and signal.entry_price > 0:
            shares = position_value / signal.entry_price
            return int(shares)  # Round down to whole shares
        
        return 0.0


class RSIMeanReversionStrategy(BaseStrategy):
    """
    RSI Mean Reversion Strategy.
    
    Buys when RSI is oversold (<30) and sells when overbought (>70).
    """
    
    def __init__(
        self,
        symbols: List[str],
        rsi_period: int = 14,
        oversold_level: float = 30.0,
        overbought_level: float = 70.0,
        **kwargs
    ):
        """
        Initialize RSI strategy.
        
        Args:
            symbols: List of symbols to trade
            rsi_period: RSI calculation period
            oversold_level: RSI level to consider oversold
            overbought_level: RSI level to consider overbought
        """
        super().__init__(
            name="RSI_MeanReversion_Strategy",
            symbols=symbols,
            timeframe=TimeFrame.FIVE_MIN,
            **kwargs
        )
        
        self.rsi_period = rsi_period
        self.oversold_level = oversold_level
        self.overbought_level = overbought_level
        
        # RSI storage
        self.rsi_values = {}  # symbol -> rsi_value
        self.price_changes = {}  # symbol -> list of price changes
    
    async def on_candle(self, symbol: str, candle: Dict[str, Any]) -> None:
        """Process new candle and update RSI."""
        # Update candle history
        self.update_candle_history(symbol, candle)
        
        # Calculate RSI if we have enough data
        if symbol in self.candle_history:
            candles = self.candle_history[symbol]
            
            if len(candles) >= self.rsi_period + 1:
                # Calculate price changes
                closes = [float(c['close']) for c in candles[-(self.rsi_period+1):]]
                changes = [closes[i+1] - closes[i] for i in range(len(closes)-1)]
                
                # Calculate RSI
                gains = [c for c in changes if c > 0]
                losses = [-c for c in changes if c < 0]
                
                avg_gain = np.mean(gains) if gains else 0
                avg_loss = np.mean(losses) if losses else 0
                
                if avg_loss == 0:
                    rsi = 100.0
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                
                self.rsi_values[symbol] = rsi
                
                # Store in indicators
                self.indicators[symbol] = {
                    'rsi': rsi,
                    'close': float(candle['close'])
                }
    
    async def generate_signals(self) -> List[Signal]:
        """Generate signals based on RSI levels."""
        signals = []
        
        if not self.is_running():
            return signals
        
        for symbol in self.symbols:
            # Skip if we don't have RSI value
            if symbol not in self.rsi_values:
                continue
            
            # Skip if we already have a position
            if self.has_position(symbol):
                continue
            
            rsi = self.rsi_values[symbol]
            current_price = float(self.candle_history[symbol][-1]['close'])
            
            # Check for oversold condition (buy signal)
            if rsi < self.oversold_level:
                signal = Signal(
                    symbol=symbol,
                    direction=OrderSide.BUY,
                    strength=min(1.0, (self.oversold_level - rsi) / self.oversold_level),
                    timestamp=datetime.now(),
                    strategy_name=self.name,
                    stop_loss=current_price * (1 - self.stop_loss_pct),
                    take_profit=current_price * (1 + self.take_profit_pct),
                    reason=f"RSI oversold: {rsi:.1f} < {self.oversold_level}",
                    confidence=0.8,
                    indicators=self.indicators.get(symbol, {}),
                    entry_price=current_price
                )
                signals.append(signal)
            
            # Check for overbought condition (sell signal)
            elif rsi > self.overbought_level:
                signal = Signal(
                    symbol=symbol,
                    direction=OrderSide.SELL,
                    strength=min(1.0, (rsi - self.overbought_level) / (100 - self.overbought_level)),
                    timestamp=datetime.now(),
                    strategy_name=self.name,
                    stop_loss=current_price * (1 + self.stop_loss_pct),
                    take_profit=current_price * (1 - self.take_profit_pct),
                    reason=f"RSI overbought: {rsi:.1f} > {self.overbought_level}",
                    confidence=0.8,
                    indicators=self.indicators.get(symbol, {}),
                    entry_price=current_price
                )
                signals.append(signal)
        
        return signals
    
    def calculate_position_size(self, signal: Signal) -> float:
        """Calculate position size based on signal strength."""
        # Base position size
        max_value = self.get_max_position_value()
        
        # Use stronger position sizing for stronger signals
        position_value = max_value * float(signal.strength) * 0.6
        
        # Calculate shares
        if signal.entry_price and signal.entry_price > 0:
            shares = position_value / signal.entry_price
            return int(shares)
        
        return 0.0


class BollingerBandStrategy(BaseStrategy):
    """
    Bollinger Band Trading Strategy.
    
    Trades based on price movements relative to Bollinger Bands.
    """
    
    def __init__(
        self,
        symbols: List[str],
        bb_period: int = 20,
        bb_std: float = 2.0,
        **kwargs
    ):
        """
        Initialize Bollinger Band strategy.
        
        Args:
            symbols: List of symbols to trade
            bb_period: Period for moving average
            bb_std: Number of standard deviations for bands
        """
        super().__init__(
            name="BollingerBand_Strategy",
            symbols=symbols,
            timeframe=TimeFrame.FIVE_MIN,
            **kwargs
        )
        
        self.bb_period = bb_period
        self.bb_std = bb_std
        
        # BB values storage
        self.bb_upper = {}
        self.bb_middle = {}
        self.bb_lower = {}
        self.bb_width = {}
    
    async def on_candle(self, symbol: str, candle: Dict[str, Any]) -> None:
        """Process new candle and update Bollinger Bands."""
        # Update candle history
        self.update_candle_history(symbol, candle)
        
        # Calculate BB if we have enough data
        if symbol in self.candle_history:
            candles = self.candle_history[symbol]
            
            if len(candles) >= self.bb_period:
                # Get closing prices
                closes = np.array([float(c['close']) for c in candles[-self.bb_period:]])
                
                # Calculate middle band (SMA)
                middle = np.mean(closes)
                
                # Calculate standard deviation
                std_dev = np.std(closes)
                
                # Calculate bands
                upper = middle + (self.bb_std * std_dev)
                lower = middle - (self.bb_std * std_dev)
                
                self.bb_upper[symbol] = upper
                self.bb_middle[symbol] = middle
                self.bb_lower[symbol] = lower
                self.bb_width[symbol] = upper - lower
                
                # Store in indicators
                self.indicators[symbol] = {
                    'bb_upper': upper,
                    'bb_middle': middle,
                    'bb_lower': lower,
                    'bb_width': self.bb_width[symbol],
                    'close': float(candle['close'])
                }
    
    async def generate_signals(self) -> List[Signal]:
        """Generate signals based on Bollinger Band touches and breakouts."""
        signals = []
        
        if not self.is_running():
            return signals
        
        for symbol in self.symbols:
            # Skip if we don't have BB values
            if symbol not in self.bb_upper:
                continue
            
            # Skip if we have a position
            if self.has_position(symbol):
                continue
            
            current_price = float(self.candle_history[symbol][-1]['close'])
            upper = self.bb_upper[symbol]
            middle = self.bb_middle[symbol]
            lower = self.bb_lower[symbol]
            
            # Buy signal: Price touches lower band
            if current_price <= lower * 1.01:  # Within 1% of lower band
                signal = Signal(
                    symbol=symbol,
                    direction=OrderSide.BUY,
                    strength=0.7,
                    timestamp=datetime.now(),
                    strategy_name=self.name,
                    stop_loss=lower * 0.98,  # 2% below lower band
                    take_profit=middle,  # Target middle band
                    reason=f"Price at lower BB: {current_price:.2f} <= {lower:.2f}",
                    confidence=0.75,
                    indicators=self.indicators.get(symbol, {}),
                    entry_price=current_price
                )
                signals.append(signal)
            
            # Sell signal: Price touches upper band
            elif current_price >= upper * 0.99:  # Within 1% of upper band
                signal = Signal(
                    symbol=symbol,
                    direction=OrderSide.SELL,
                    strength=0.7,
                    timestamp=datetime.now(),
                    strategy_name=self.name,
                    stop_loss=upper * 1.02,  # 2% above upper band
                    take_profit=middle,  # Target middle band
                    reason=f"Price at upper BB: {current_price:.2f} >= {upper:.2f}",
                    confidence=0.75,
                    indicators=self.indicators.get(symbol, {}),
                    entry_price=current_price
                )
                signals.append(signal)
        
        return signals
    
    def calculate_position_size(self, signal: Signal) -> float:
        """Calculate position size based on band width."""
        # Base position size
        max_value = self.get_max_position_value()
        
        # Adjust based on volatility (band width)
        if signal.symbol in self.bb_width and signal.symbol in self.bb_middle:
            width_ratio = self.bb_width[signal.symbol] / self.bb_middle[signal.symbol]
            
            # Reduce position size in high volatility
            volatility_adjustment = max(0.5, 1 - width_ratio)
            position_value = max_value * float(signal.strength) * volatility_adjustment * 0.7
        else:
            position_value = max_value * float(signal.strength) * 0.5
        
        # Calculate shares
        if signal.entry_price and signal.entry_price > 0:
            shares = position_value / signal.entry_price
            return int(shares)
        
        return 0.0