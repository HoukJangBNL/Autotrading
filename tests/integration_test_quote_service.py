#!/usr/bin/env python3
"""
Integration test for quote service with real Schwab API.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.quote_service import create_quote_service
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def test_quote_service():
    """Test quote service with real API."""
    print("\n" + "="*60)
    print("Quote Service Integration Test")
    print("="*60)
    
    try:
        # Create service
        print("\nInitializing quote service...")
        service = await create_quote_service()
        print("✓ Service initialized")
        
        # Test single quote
        print("\n1. Testing single quote fetch...")
        quote = await service.get_quote("AAPL")
        if quote:
            print(f"✓ AAPL Quote:")
            print(f"  Last: ${quote.last_price:.2f}")
            print(f"  Bid:  ${quote.bid_price:.2f} (Size: {quote.bid_size})")
            print(f"  Ask:  ${quote.ask_price:.2f} (Size: {quote.ask_size})")
            print(f"  Spread: ${quote.spread:.4f} ({quote.spread_percentage:.3f}%)")
            print(f"  Volume: {quote.volume:,}")
        else:
            print("✗ Failed to fetch quote")
            return False
        
        # Test batch quotes
        print("\n2. Testing batch quote fetch...")
        symbols = ["MSFT", "GOOGL", "AMZN"]
        quotes = await service.get_quotes_batch(symbols)
        print(f"✓ Fetched {len(quotes)} quotes:")
        for symbol, q in sorted(quotes.items()):
            print(f"  {symbol}: ${q.last_price:.2f} (Spread: ${q.spread:.4f})")
        
        # Test cache behavior
        print("\n3. Testing cache behavior...")
        import time
        
        # First fetch (API)
        start = time.time()
        q1 = await service.get_quote("TSLA")
        time1 = time.time() - start
        print(f"✓ First fetch: {time1:.3f}s (API call)")
        
        # Second fetch (cache)
        start = time.time()
        q2 = await service.get_quote("TSLA")
        time2 = time.time() - start
        print(f"✓ Second fetch: {time2:.3f}s (cache hit)")
        print(f"  Cache speedup: {time1/time2:.1f}x")
        
        # Test history tracking
        print("\n4. Testing history tracking...")
        for i in range(3):
            await service.get_quote("NVDA", use_cache=False)
            await asyncio.sleep(1)
        
        current, history = await service.get_quote_with_history("NVDA", 3)
        print(f"✓ Tracked {len(history)} quotes")
        
        # Test metrics
        print("\n5. Testing quote metrics...")
        metrics = service.get_quote_metrics("NVDA", minutes=1)
        print(f"✓ Metrics calculated:")
        print(f"  Price range: ${metrics['price_range'][0]:.2f} - ${metrics['price_range'][1]:.2f}")
        print(f"  Quote count: {metrics['quote_count']}")
        print(f"  Avg spread: ${metrics['avg_spread']:.4f}")
        
        # Test spread statistics
        print("\n6. Testing spread analysis...")
        test_symbols = ["SPY", "QQQ", "IWM", "DIA"]
        batch_quotes = await service.get_quotes_batch(test_symbols)
        if batch_quotes:
            stats = service.calculate_spread_stats(list(batch_quotes.values()))
            print(f"✓ Spread statistics for {len(batch_quotes)} ETFs:")
            print(f"  Average: ${stats['avg_spread']:.4f} ({stats['avg_spread_pct']:.3f}%)")
            print(f"  Min: ${stats['min_spread']:.4f}")
            print(f"  Max: ${stats['max_spread']:.4f}")
        
        print("\n✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logger.exception("Integration test error")
        return False
    
    finally:
        # Cleanup
        await service.shutdown()
        print("\n✓ Service shutdown complete")


async def main():
    """Run integration test."""
    success = await test_quote_service()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())