"""Example trading strategy implementations."""

from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime

from .base import BaseStrategy, Signal, SignalType
from src.utils.logger import logger


class SimpleMovingAverageStrategy(BaseStrategy):
    """Simple Moving Average (SMA) crossover strategy.
    
    Generates BUY signal when fast SMA crosses above slow SMA.
    Generates SELL signal when fast SMA crosses below slow SMA.
    """
    
    def get_default_parameters(self) -> Dict[str, Any]:
        """Get default parameters."""
        return {
            "fast_period": 10,
            "slow_period": 30,
            "risk_percentage": 0.02
        }
    
    def get_required_history(self) -> int:
        """Get required history length."""
        return self.parameters["slow_period"] + 1
    
    def analyze(self, candles: pd.DataFrame, symbol: str) -> Optional[Signal]:
        """Analyze candles for SMA crossover."""
        # Preprocess candles
        candles = self.preprocess_candles(candles)
        
        # Check if we have enough data
        if len(candles) < self.get_required_history():
            return None
        
        # Calculate SMAs
        fast_sma = candles['close'].rolling(window=self.parameters["fast_period"]).mean()
        slow_sma = candles['close'].rolling(window=self.parameters["slow_period"]).mean()
        
        # Get current and previous values
        current_fast = fast_sma.iloc[-1]
        current_slow = slow_sma.iloc[-1]
        prev_fast = fast_sma.iloc[-2]
        prev_slow = slow_sma.iloc[-2]
        
        # Check for crossover
        signal = None
        timestamp = candles['timestamp'].iloc[-1]
        
        if prev_fast <= prev_slow and current_fast > current_slow:
            # Bullish crossover
            strength = min(1.0, (current_fast - current_slow) / current_slow)
            signal = Signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                timestamp=timestamp,
                strength=strength,
                metadata={
                    "fast_sma": float(current_fast),
                    "slow_sma": float(current_slow),
                    "strategy": self.name
                }
            )
            logger.info(f"SMA Strategy: BUY signal for {symbol} at {timestamp}")
            
        elif prev_fast >= prev_slow and current_fast < current_slow:
            # Bearish crossover
            strength = min(1.0, (current_slow - current_fast) / current_fast)
            signal = Signal(
                symbol=symbol,
                signal_type=SignalType.SELL,
                timestamp=timestamp,
                strength=strength,
                metadata={
                    "fast_sma": float(current_fast),
                    "slow_sma": float(current_slow),
                    "strategy": self.name
                }
            )
            logger.info(f"SMA Strategy: SELL signal for {symbol} at {timestamp}")
        
        if signal:
            self.signals_generated += 1
            self.last_signal_time = timestamp
        
        return signal


class MomentumStrategy(BaseStrategy):
    """Momentum-based trading strategy.
    
    Uses RSI and price momentum to generate signals.
    """
    
    def get_default_parameters(self) -> Dict[str, Any]:
        """Get default parameters."""
        return {
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "momentum_period": 10,
            "risk_percentage": 0.02
        }
    
    def get_required_history(self) -> int:
        """Get required history length."""
        return max(self.parameters["rsi_period"], self.parameters["momentum_period"]) + 2
    
    def calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Relative Strength Index."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def analyze(self, candles: pd.DataFrame, symbol: str) -> Optional[Signal]:
        """Analyze candles for momentum signals."""
        # Preprocess candles
        candles = self.preprocess_candles(candles)
        
        # Check if we have enough data
        if len(candles) < self.get_required_history():
            return None
        
        # Calculate indicators
        rsi = self.calculate_rsi(candles['close'], self.parameters["rsi_period"])
        momentum = candles['close'].pct_change(self.parameters["momentum_period"])
        
        # Get current values
        current_rsi = rsi.iloc[-1]
        current_momentum = momentum.iloc[-1]
        timestamp = candles['timestamp'].iloc[-1]
        
        signal = None
        
        # Generate signals based on RSI and momentum
        if current_rsi < self.parameters["rsi_oversold"] and current_momentum > 0:
            # Oversold with positive momentum
            strength = (self.parameters["rsi_oversold"] - current_rsi) / self.parameters["rsi_oversold"]
            signal = Signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                timestamp=timestamp,
                strength=strength,
                metadata={
                    "rsi": float(current_rsi),
                    "momentum": float(current_momentum),
                    "strategy": self.name
                }
            )
            logger.info(f"Momentum Strategy: BUY signal for {symbol} at {timestamp}")
            
        elif current_rsi > self.parameters["rsi_overbought"] and current_momentum < 0:
            # Overbought with negative momentum
            strength = (current_rsi - self.parameters["rsi_overbought"]) / (100 - self.parameters["rsi_overbought"])
            signal = Signal(
                symbol=symbol,
                signal_type=SignalType.SELL,
                timestamp=timestamp,
                strength=strength,
                metadata={
                    "rsi": float(current_rsi),
                    "momentum": float(current_momentum),
                    "strategy": self.name
                }
            )
            logger.info(f"Momentum Strategy: SELL signal for {symbol} at {timestamp}")
        
        if signal:
            self.signals_generated += 1
            self.last_signal_time = timestamp
        
        return signal


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion trading strategy.
    
    Trades based on price deviation from moving average.
    """
    
    def get_default_parameters(self) -> Dict[str, Any]:
        """Get default parameters."""
        return {
            "lookback_period": 20,
            "entry_std_dev": 2.0,
            "exit_std_dev": 0.5,
            "risk_percentage": 0.02
        }
    
    def get_required_history(self) -> int:
        """Get required history length."""
        return self.parameters["lookback_period"] + 1
    
    def analyze(self, candles: pd.DataFrame, symbol: str) -> Optional[Signal]:
        """Analyze candles for mean reversion signals."""
        # Preprocess candles
        candles = self.preprocess_candles(candles)
        
        # Check if we have enough data
        if len(candles) < self.get_required_history():
            return None
        
        # Calculate indicators
        ma = candles['close'].rolling(window=self.parameters["lookback_period"]).mean()
        std = candles['close'].rolling(window=self.parameters["lookback_period"]).std()
        
        # Calculate z-score
        current_price = candles['close'].iloc[-1]
        current_ma = ma.iloc[-1]
        current_std = std.iloc[-1]
        z_score = (current_price - current_ma) / current_std if current_std > 0 else 0
        
        timestamp = candles['timestamp'].iloc[-1]
        signal = None
        
        # Generate signals based on z-score
        if z_score < -self.parameters["entry_std_dev"]:
            # Price significantly below mean - potential buy
            strength = min(1.0, abs(z_score) / 3.0)
            signal = Signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                timestamp=timestamp,
                strength=strength,
                metadata={
                    "z_score": float(z_score),
                    "ma": float(current_ma),
                    "std": float(current_std),
                    "strategy": self.name
                }
            )
            logger.info(f"Mean Reversion Strategy: BUY signal for {symbol} at {timestamp}")
            
        elif z_score > self.parameters["entry_std_dev"]:
            # Price significantly above mean - potential sell
            strength = min(1.0, abs(z_score) / 3.0)
            signal = Signal(
                symbol=symbol,
                signal_type=SignalType.SELL,
                timestamp=timestamp,
                strength=strength,
                metadata={
                    "z_score": float(z_score),
                    "ma": float(current_ma),
                    "std": float(current_std),
                    "strategy": self.name
                }
            )
            logger.info(f"Mean Reversion Strategy: SELL signal for {symbol} at {timestamp}")
        
        if signal:
            self.signals_generated += 1
            self.last_signal_time = timestamp
        
        return signal