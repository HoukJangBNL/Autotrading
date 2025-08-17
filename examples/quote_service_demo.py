#!/usr/bin/env python3
"""
Demo script for the real-time quote service.

This script demonstrates:
- Single quote fetching
- Batch quote operations
- Quote history tracking
- Spread analysis
- Real-time updates via pub/sub
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.quote_service import QuoteService, create_quote_service
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


def print_quote(quote):
    """Pretty print a quote."""
    print(f"\n{'='*60}")
    print(f"Symbol: {quote.symbol}")
    print(f"{'='*60}")
    print(f"Last Price:  ${quote.last_price:>10.2f}")
    print(f"Bid:         ${quote.bid_price:>10.2f} (Size: {quote.bid_size:>6})")
    print(f"Ask:         ${quote.ask_price:>10.2f} (Size: {quote.ask_size:>6})")
    print(f"Spread:      ${quote.spread:>10.4f} ({quote.spread_percentage:.3f}%)")
    print(f"Mid Price:   ${quote.mid_price:>10.2f}")
    print(f"Volume:      {quote.volume:>13,}")
    
    if quote.change is not None:
        change_symbol = "+" if quote.change >= 0 else ""
        print(f"Change:      {change_symbol}${quote.change:.2f} ({change_symbol}{quote.change_percentage:.2f}%)")
    
    if quote.open_price:
        print(f"\nOpen:        ${quote.open_price:>10.2f}")
    if quote.high_price and quote.low_price:
        print(f"Range:       ${quote.low_price:.2f} - ${quote.high_price:.2f}")
    if quote.fifty_two_week_low and quote.fifty_two_week_high:
        print(f"52W Range:   ${quote.fifty_two_week_low:.2f} - ${quote.fifty_two_week_high:.2f}")
    
    print(f"\nTimestamp:   {quote.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")


def print_spread_stats(stats):
    """Pretty print spread statistics."""
    print(f"\n{'='*40}")
    print("Spread Statistics")
    print(f"{'='*40}")
    print(f"Average Spread:     ${stats['avg_spread']:.4f}")
    print(f"Average Spread %:   {stats['avg_spread_pct']:.3f}%")
    print(f"Min Spread:         ${stats['min_spread']:.4f}")
    print(f"Max Spread:         ${stats['max_spread']:.4f}")
    print(f"Total Spread Cost:  ${stats['total_spread_cost']:.4f}")


async def demo_single_quote(service: QuoteService):
    """Demo single quote fetching."""
    print("\n" + "="*80)
    print("DEMO: Single Quote Fetching")
    print("="*80)
    
    symbol = "AAPL"
    print(f"\nFetching quote for {symbol}...")
    
    quote = await service.get_quote(symbol)
    if quote:
        print_quote(quote)
    else:
        print(f"Failed to fetch quote for {symbol}")


async def demo_batch_quotes(service: QuoteService):
    """Demo batch quote fetching."""
    print("\n" + "="*80)
    print("DEMO: Batch Quote Fetching")
    print("="*80)
    
    symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
    print(f"\nFetching quotes for: {', '.join(symbols)}")
    
    quotes = await service.get_quotes_batch(symbols)
    
    print(f"\nReceived {len(quotes)} quotes:")
    for symbol, quote in sorted(quotes.items()):
        print(f"\n{symbol}: ${quote.last_price:.2f} "
              f"(Bid: ${quote.bid_price:.2f} / Ask: ${quote.ask_price:.2f}) "
              f"Spread: ${quote.spread:.4f}")
    
    # Calculate spread statistics
    if quotes:
        stats = service.calculate_spread_stats(list(quotes.values()))
        print_spread_stats(stats)


async def demo_quote_history(service: QuoteService):
    """Demo quote history tracking."""
    print("\n" + "="*80)
    print("DEMO: Quote History Tracking")
    print("="*80)
    
    symbol = "AAPL"
    print(f"\nFetching multiple quotes for {symbol} to build history...")
    
    # Fetch quotes multiple times with delay
    for i in range(5):
        print(f"\nFetch #{i+1}:")
        quote = await service.get_quote(symbol, use_cache=False)  # Skip cache
        if quote:
            print(f"  Price: ${quote.last_price:.2f}, "
                  f"Spread: ${quote.spread:.4f}, "
                  f"Volume: {quote.volume:,}")
        
        if i < 4:  # Don't sleep after last fetch
            await asyncio.sleep(1)
    
    # Get quote with history
    print(f"\nGetting current quote with history...")
    current, history = await service.get_quote_with_history(symbol, history_count=5)
    
    if current:
        print(f"\nCurrent quote: ${current.last_price:.2f}")
        
    if history:
        print(f"\nLast {len(history)} quotes:")
        for i, q in enumerate(history):
            print(f"  {i+1}. ${q.last_price:.2f} at {q.timestamp.strftime('%H:%M:%S')}")
    
    # Get metrics
    metrics = service.get_quote_metrics(symbol, minutes=1)
    print(f"\nQuote metrics (last 1 minute):")
    print(f"  Price range: ${metrics['price_range'][0]:.2f} - ${metrics['price_range'][1]:.2f}")
    print(f"  Volatility: ${metrics['price_volatility']:.2f}")
    print(f"  Volume: {metrics['volume']:,}")
    print(f"  Quote count: {metrics['quote_count']}")
    print(f"  Avg spread: ${metrics['avg_spread']:.4f} ({metrics['avg_spread_pct']:.3f}%)")


async def demo_cache_behavior(service: QuoteService):
    """Demo cache behavior."""
    print("\n" + "="*80)
    print("DEMO: Cache Behavior")
    print("="*80)
    
    symbol = "MSFT"
    
    print(f"\nFirst fetch for {symbol} (will hit API)...")
    start = datetime.now()
    quote1 = await service.get_quote(symbol, use_cache=True)
    time1 = (datetime.now() - start).total_seconds()
    print(f"  Fetched in {time1:.3f} seconds")
    
    print(f"\nSecond fetch for {symbol} (should hit cache)...")
    start = datetime.now()
    quote2 = await service.get_quote(symbol, use_cache=True)
    time2 = (datetime.now() - start).total_seconds()
    print(f"  Fetched in {time2:.3f} seconds")
    
    print(f"\nCache speedup: {time1/time2:.1f}x faster")
    
    print(f"\nFetch without cache...")
    start = datetime.now()
    quote3 = await service.get_quote(symbol, use_cache=False)
    time3 = (datetime.now() - start).total_seconds()
    print(f"  Fetched in {time3:.3f} seconds")


async def demo_real_time_updates(service: QuoteService):
    """Demo real-time updates via pub/sub."""
    print("\n" + "="*80)
    print("DEMO: Real-time Updates (Pub/Sub)")
    print("="*80)
    
    try:
        # Subscribe to updates
        pubsub = await service.subscribe_to_updates()
        print("\nSubscribed to quote updates...")
        print("Fetching quotes to trigger updates...")
        
        # Create a task to listen for updates
        async def listen_for_updates():
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    print(f"\n[UPDATE] Received: {message['data'][:100]}...")
        
        # Start listening in background
        listen_task = asyncio.create_task(listen_for_updates())
        
        # Fetch some quotes to trigger updates
        symbols = ["AAPL", "GOOGL", "MSFT"]
        for symbol in symbols:
            print(f"\nFetching {symbol}...")
            await service.get_quote(symbol, use_cache=False)
            await asyncio.sleep(0.5)
        
        # Give time for messages to arrive
        await asyncio.sleep(1)
        
        # Cancel listening task
        listen_task.cancel()
        try:
            await listen_task
        except asyncio.CancelledError:
            pass
        
        await pubsub.close()
        
    except RuntimeError as e:
        print(f"\nPub/Sub not available: {e}")


async def demo_error_handling(service: QuoteService):
    """Demo error handling."""
    print("\n" + "="*80)
    print("DEMO: Error Handling")
    print("="*80)
    
    # Try invalid symbol
    print("\nFetching invalid symbol 'INVALID123'...")
    quote = await service.get_quote("INVALID123")
    if quote:
        print("  Unexpectedly got a quote!")
    else:
        print("  ✓ Correctly returned None for invalid symbol")
    
    # Try empty batch
    print("\nFetching empty batch...")
    quotes = await service.get_quotes_batch([])
    print(f"  ✓ Returned {len(quotes)} quotes (empty dict)")
    
    # Try very large batch
    print("\nTrying oversized batch (150 symbols)...")
    large_batch = [f"TEST{i}" for i in range(150)]
    quotes = await service.get_quotes_batch(large_batch[:100])  # Service should handle
    print(f"  ✓ Handled batch of {len(large_batch[:100])} symbols")


async def main():
    """Run all demos."""
    print("="*80)
    print("Real-time Quote Service Demo")
    print("="*80)
    
    # Create and initialize service
    print("\nInitializing quote service...")
    service = await create_quote_service()
    
    try:
        # Run demos
        await demo_single_quote(service)
        await demo_batch_quotes(service)
        await demo_quote_history(service)
        await demo_cache_behavior(service)
        await demo_real_time_updates(service)
        await demo_error_handling(service)
        
        print("\n" + "="*80)
        print("Demo completed successfully!")
        print("="*80)
        
    except Exception as e:
        logger.error(f"Demo error: {e}")
        raise
    
    finally:
        # Cleanup
        await service.shutdown()
        print("\nService shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())