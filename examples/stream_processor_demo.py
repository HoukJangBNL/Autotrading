#!/usr/bin/env python3
"""
Stream Processor Demo

This script demonstrates the real-time stream processing capabilities including:
- Tick data processing
- OHLCV bar aggregation
- Volume profile tracking
- Stream health monitoring
- Redis pub/sub integration
"""

import asyncio
import random
from datetime import datetime, timezone, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.stream_processor import (
    Tick, TickType, StreamProcessor, create_stream_processor,
    calculate_vwap, detect_tick_gaps
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MarketSimulator:
    """Simulates market tick data for demo purposes."""
    
    def __init__(self, symbol: str, base_price: float = 150.0):
        self.symbol = symbol
        self.base_price = base_price
        self.current_price = base_price
        self.volatility = 0.02  # 2% volatility
        self.trend = 0.0001  # Slight upward trend
        
    def generate_tick(self) -> Tick:
        """Generate a realistic tick with random walk."""
        # Random walk with trend
        change = random.gauss(self.trend, self.volatility)
        self.current_price *= (1 + change)
        
        # Ensure price stays reasonable
        self.current_price = max(self.current_price, self.base_price * 0.8)
        self.current_price = min(self.current_price, self.base_price * 1.2)
        
        # Generate volume (higher volume around whole numbers)
        base_volume = random.randint(100, 1000)
        if abs(self.current_price - round(self.current_price)) < 0.10:
            base_volume *= 3  # More volume at psychological levels
        
        # Determine tick type (80% trades, 10% bids, 10% asks)
        rand = random.random()
        if rand < 0.8:
            tick_type = TickType.TRADE
        elif rand < 0.9:
            tick_type = TickType.BID
        else:
            tick_type = TickType.ASK
        
        return Tick(
            symbol=self.symbol,
            price=round(self.current_price, 2),
            volume=base_volume,
            timestamp=datetime.now(timezone.utc),
            tick_type=tick_type
        )


async def display_stats(processor: StreamProcessor, symbols: list):
    """Display live statistics."""
    print("\n" + "=" * 80)
    print("STREAM PROCESSOR STATISTICS")
    print("=" * 80)
    
    # Overall stats
    stats = processor.stats
    runtime = (datetime.now(timezone.utc) - stats['start_time']).total_seconds()
    ticks_per_sec = stats['ticks_processed'] / runtime if runtime > 0 else 0
    
    print(f"\nOverall Performance:")
    print(f"  Runtime: {runtime:.1f}s")
    print(f"  Ticks Processed: {stats['ticks_processed']:,}")
    print(f"  Throughput: {ticks_per_sec:.1f} ticks/sec")
    print(f"  Bars Created: {stats['bars_created']:,}")
    print(f"  Errors: {stats['errors']}")
    
    # Per-symbol stats
    for symbol in symbols:
        print(f"\n{symbol} Statistics:")
        
        # Health status
        health = processor.get_health(symbol)
        if health:
            print(f"  Status: {health.status.value}")
            print(f"  Ticks Received: {health.ticks_received:,}")
            print(f"  Avg Latency: {health.avg_latency_ms:.1f}ms")
            print(f"  Errors: {health.error_count}")
        
        # Volume profile
        profile = processor.get_volume_profile(symbol)
        if profile:
            poc = profile.poc
            val, vah = profile.val, profile.vah
            print(f"  Volume Profile:")
            print(f"    Total Volume: {profile.total_volume:,}")
            print(f"    POC: ${poc:.2f}" if poc else "    POC: N/A")
            print(f"    Value Area: ${val:.2f} - ${vah:.2f}" if val and vah else "    Value Area: N/A")
        
        # Recent bars
        bars = processor.get_recent_bars(symbol, timeframe=1, limit=3)
        if bars:
            print(f"  Recent Bars (1-min):")
            for bar in bars[-3:]:
                print(f"    {bar.timestamp.strftime('%H:%M:%S')} - "
                      f"O:{bar.open:.2f} H:{bar.high:.2f} L:{bar.low:.2f} C:{bar.close:.2f} "
                      f"V:{bar.volume:,} VWAP:{bar.vwap:.2f}")


async def simulate_market_data(processor: StreamProcessor, duration_seconds: int = 300):
    """Simulate market data for multiple symbols."""
    symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
    simulators = {symbol: MarketSimulator(symbol, base_price=150 + i*50) 
                  for i, symbol in enumerate(symbols)}
    
    print(f"Starting market simulation for {duration_seconds} seconds...")
    print(f"Symbols: {', '.join(symbols)}")
    print("\nGenerating ticks...")
    
    start_time = datetime.now()
    tick_count = 0
    
    # Set up callbacks
    bar_count = 0
    def on_bar_complete(bar):
        nonlocal bar_count
        bar_count += 1
        if bar_count % 10 == 0:
            print(f"\n✅ Bar #{bar_count} completed: {bar.symbol} "
                  f"{bar.timestamp.strftime('%H:%M:%S')} "
                  f"OHLC: {bar.open:.2f}/{bar.high:.2f}/{bar.low:.2f}/{bar.close:.2f} "
                  f"Volume: {bar.volume:,}")
    
    processor.on_bar(on_bar_complete)
    
    # Generate ticks
    while (datetime.now() - start_time).total_seconds() < duration_seconds:
        # Generate ticks for random symbols
        for _ in range(random.randint(1, 5)):  # 1-5 ticks per iteration
            symbol = random.choice(symbols)
            tick = simulators[symbol].generate_tick()
            
            success = await processor.add_tick(tick)
            if success:
                tick_count += 1
                
                # Show progress
                if tick_count % 100 == 0:
                    print(f".", end="", flush=True)
                if tick_count % 1000 == 0:
                    print(f" {tick_count:,} ticks", flush=True)
        
        # Small delay to simulate realistic tick flow
        await asyncio.sleep(random.uniform(0.05, 0.15))
        
        # Display stats periodically
        if tick_count % 500 == 0:
            await display_stats(processor, symbols)
    
    print(f"\n\nSimulation complete! Generated {tick_count:,} ticks")
    
    # Final stats
    await display_stats(processor, symbols)
    
    # Demonstrate gap detection
    print("\nGap Detection Demo:")
    for symbol in symbols:
        recent_ticks = processor.get_recent_ticks(symbol, limit=100)
        gaps = detect_tick_gaps(recent_ticks, threshold_seconds=1.0)
        if gaps:
            print(f"  {symbol}: Found {len(gaps)} gaps > 1 second")
        else:
            print(f"  {symbol}: No significant gaps detected")


async def demo_callbacks(processor: StreamProcessor):
    """Demonstrate callback functionality."""
    print("\n" + "=" * 80)
    print("CALLBACK DEMONSTRATION")
    print("=" * 80)
    
    # Volume spike detection
    volume_threshold = 2000
    def detect_volume_spike(bar):
        if bar.volume > volume_threshold:
            print(f"\n📊 VOLUME SPIKE: {bar.symbol} at {bar.timestamp.strftime('%H:%M:%S')} "
                  f"- Volume: {bar.volume:,} (threshold: {volume_threshold:,})")
    
    # Price breakout detection
    breakout_levels = {"AAPL": 152, "GOOGL": 202, "MSFT": 252}
    def detect_breakout(tick):
        if tick.symbol in breakout_levels:
            level = breakout_levels[tick.symbol]
            if tick.price > level and tick.tick_type == TickType.TRADE:
                print(f"\n🚀 BREAKOUT: {tick.symbol} broke above ${level:.2f} "
                      f"at ${tick.price:.2f}")
                # Remove to avoid repeated alerts
                del breakout_levels[tick.symbol]
    
    # Register callbacks
    processor.on_bar(detect_volume_spike)
    processor.on_tick(detect_breakout)
    
    print("\nCallbacks registered:")
    print("- Volume spike detection (threshold: 2000)")
    print("- Price breakout detection")
    print("\nWatching for events during simulation...")


async def main():
    """Run the stream processor demo."""
    print("=" * 80)
    print("SCHWAB AUTOTRADER - STREAM PROCESSOR DEMO")
    print("=" * 80)
    
    # Create stream processor
    # Note: Set redis_url if you have Redis running
    processor = await create_stream_processor(
        redis_url=None,  # Set to "redis://localhost:6379" if available
        save_to_db=False,  # Don't save to DB for demo
        timeframes=[1, 5, 15]  # 1-min, 5-min, 15-min bars
    )
    
    try:
        # Demonstrate callbacks
        await demo_callbacks(processor)
        
        # Run market simulation
        await simulate_market_data(processor, duration_seconds=30)  # 30 seconds for demo
        
        # Flush any remaining bars
        print("\nFlushing remaining bars...")
        await processor.flush_all_bars()
        
        print("\n✨ Demo completed successfully!")
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        logger.error(f"Demo error: {e}")
        raise
    finally:
        await processor.stop()
        print("\nStream processor stopped")


if __name__ == "__main__":
    # Run the demo
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")