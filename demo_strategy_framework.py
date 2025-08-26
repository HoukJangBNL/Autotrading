#!/usr/bin/env python3
"""
Demo script showing how to use the Trading Strategy Framework.

This demonstrates:
1. Creating a custom strategy
2. Running backtests
3. Analyzing performance
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any

from src.strategy import BaseStrategy, Signal, OrderSide
from src.strategy.example_strategies import (
    MovingAverageCrossStrategy,
    RSIMeanReversionStrategy,
    BollingerBandStrategy
)
from src.data.models import TimeFrame


# Simple demo strategy
class DemoStrategy(BaseStrategy):
    """Demo strategy that generates signals based on simple price movements."""
    
    def __init__(self):
        super().__init__(
            name="DemoStrategy",
            symbols=["AAPL", "MSFT", "GOOGL"],
            timeframe=TimeFrame.FIVE_MIN,
            initial_capital=100000,
            max_position_size=0.1,  # 10% per position
            stop_loss_pct=0.02,     # 2% stop loss
            take_profit_pct=0.05    # 5% take profit
        )
        self.price_history = {}  # symbol -> list of prices
        
    async def on_candle(self, symbol: str, candle: Dict[str, Any]) -> None:
        """Process new candle data."""
        # Update candle history
        self.update_candle_history(symbol, candle)
        
        # Track price history
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append(float(candle['close']))
        
        # Keep only recent prices
        if len(self.price_history[symbol]) > 20:
            self.price_history[symbol] = self.price_history[symbol][-20:]
    
    async def generate_signals(self) -> List[Signal]:
        """Generate trading signals."""
        signals = []
        
        if not self.is_running():
            return signals
        
        for symbol in self.symbols:
            # Need at least 10 candles
            if symbol not in self.price_history or len(self.price_history[symbol]) < 10:
                continue
            
            # Skip if we have a position
            if self.has_position(symbol):
                continue
            
            prices = self.price_history[symbol]
            current_price = prices[-1]
            avg_price = sum(prices[-10:]) / 10
            
            # Buy if price is 2% below 10-period average
            if current_price < avg_price * 0.98:
                signal = Signal(
                    symbol=symbol,
                    direction=OrderSide.BUY,
                    strength=0.7,
                    timestamp=datetime.now(),
                    strategy_name=self.name,
                    stop_loss=current_price * 0.98,
                    take_profit=current_price * 1.05,
                    reason=f"Price below average: {current_price:.2f} < {avg_price:.2f}",
                    confidence=0.6,
                    entry_price=current_price
                )
                signals.append(signal)
        
        return signals
    
    def calculate_position_size(self, signal: Signal) -> float:
        """Calculate position size for a signal."""
        max_value = self.get_max_position_value()
        position_value = max_value * 0.5  # Use 50% of max
        
        if signal.entry_price and signal.entry_price > 0:
            return int(position_value / signal.entry_price)
        return 0.0


async def demo_strategy_usage():
    """Demonstrate basic strategy usage."""
    print("=" * 60)
    print("Trading Strategy Framework Demo")
    print("=" * 60)
    print()
    
    # Create strategy instance
    strategy = DemoStrategy()
    print(f"Created strategy: {strategy.name}")
    print(f"Symbols: {strategy.symbols}")
    print(f"Initial capital: ${strategy.initial_capital:,.2f}")
    print()
    
    # Start strategy
    await strategy.start()
    print("Strategy started")
    print()
    
    # Simulate some candle data
    print("Simulating market data...")
    for i in range(20):
        timestamp = datetime.now() - timedelta(minutes=20-i)
        
        # AAPL candles
        await strategy.on_candle("AAPL", {
            'timestamp': timestamp,
            'open': Decimal('150') + Decimal(i % 5) - Decimal('2'),
            'high': Decimal('152') + Decimal(i % 5),
            'low': Decimal('149') + Decimal(i % 5) - Decimal('3'),
            'close': Decimal('151') + Decimal(i % 5) - Decimal('1'),
            'volume': 1000000 + (i * 50000)
        })
        
        # MSFT candles  
        await strategy.on_candle("MSFT", {
            'timestamp': timestamp,
            'open': Decimal('380') + Decimal(i % 3),
            'high': Decimal('382') + Decimal(i % 3),
            'low': Decimal('378') + Decimal(i % 3),
            'close': Decimal('380') + Decimal(i % 3),
            'volume': 500000 + (i * 25000)
        })
    
    # Generate signals
    signals = await strategy.generate_signals()
    print(f"\nGenerated {len(signals)} signals:")
    for signal in signals:
        print(f"  - {signal.direction.value} {signal.symbol} "
              f"@ ${signal.entry_price:.2f} "
              f"(strength: {signal.strength:.1f})")
        print(f"    Reason: {signal.reason}")
        print(f"    SL: ${signal.stop_loss:.2f}, TP: ${signal.take_profit:.2f}")
    
    # Show performance metrics
    print("\nPerformance Metrics:")
    metrics = strategy.get_performance_metrics()
    for key, value in metrics.items():
        if isinstance(value, float):
            if 'pct' in key or 'rate' in key:
                print(f"  {key}: {value:.2%}")
            else:
                print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")
    
    # Stop strategy
    await strategy.stop()
    print("\nStrategy stopped")


async def demo_example_strategies():
    """Demo the example strategies."""
    print("\n" + "=" * 60)
    print("Example Strategies Demo")
    print("=" * 60)
    print()
    
    # Create different strategies
    strategies = [
        MovingAverageCrossStrategy(
            symbols=["AAPL", "MSFT"],
            fast_period=10,
            slow_period=20,
            initial_capital=50000
        ),
        RSIMeanReversionStrategy(
            symbols=["GOOGL", "AMZN"],
            rsi_period=14,
            oversold_level=30,
            overbought_level=70,
            initial_capital=50000
        ),
        BollingerBandStrategy(
            symbols=["TSLA", "NVDA"],
            bb_period=20,
            bb_std=2.0,
            initial_capital=50000
        )
    ]
    
    for strategy in strategies:
        print(f"\nStrategy: {strategy.name}")
        print(f"  Type: {strategy.__class__.__name__}")
        print(f"  Symbols: {strategy.symbols}")
        print(f"  Capital: ${strategy.initial_capital:,.2f}")
        
        # Start strategy
        await strategy.start()
        
        # Would normally process real/historical data here
        # For demo, just show it's running
        print(f"  Status: {'Running' if strategy.is_running() else 'Stopped'}")
        
        # Stop strategy
        await strategy.stop()


def print_strategy_features():
    """Print framework features."""
    print("\n" + "=" * 60)
    print("Trading Strategy Framework Features")
    print("=" * 60)
    print()
    
    print("✅ BaseStrategy Abstract Class")
    print("   - Standardized interface for all strategies")
    print("   - Built-in position and capital management")
    print("   - Performance tracking and metrics")
    print()
    
    print("✅ Data Models")
    print("   - Signal: Trading signals with risk parameters")
    print("   - Position: Open position tracking with P&L")
    print("   - Trade: Completed trades with full metrics")
    print("   - Order: Order management and execution")
    print()
    
    print("✅ Backtesting Engine")
    print("   - Historical data testing")
    print("   - Realistic trade simulation")
    print("   - Slippage and commission modeling")
    print("   - Performance analysis")
    print()
    
    print("✅ Example Strategies")
    print("   - Moving Average Crossover")
    print("   - RSI Mean Reversion")
    print("   - Bollinger Band")
    print()
    
    print("✅ Performance Metrics")
    print("   - Sharpe Ratio")
    print("   - Maximum Drawdown")
    print("   - Win Rate")
    print("   - Profit Factor")
    print()


async def main():
    """Run all demos."""
    # Show features
    print_strategy_features()
    
    # Demo basic usage
    await demo_strategy_usage()
    
    # Demo example strategies
    await demo_example_strategies()
    
    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print("\nNext Steps:")
    print("1. Connect to Phase 3 streaming data")
    print("2. Implement backtesting with historical data")
    print("3. Create custom strategies")
    print("4. Run live trading (with proper risk management!)")


if __name__ == "__main__":
    asyncio.run(main())