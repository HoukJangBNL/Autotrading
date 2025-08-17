#!/usr/bin/env python3
"""
Non-interactive integration test for Enhanced Historical Data Fetcher.
This runs automatically without user prompts.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.historical_data_enhanced import (
    EnhancedHistoricalDataFetcher,
    TimeFrame,
    FetchProgress,
)
from src.broker import SchwabBroker
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def test_basic_functionality():
    """Test basic functionality with minimal API calls."""
    print("\n=== Testing Basic Functionality ===")
    
    try:
        # Initialize broker
        print("Initializing broker...")
        broker = SchwabBroker()
        await broker.initialize()
        print("✅ Broker initialized")
        
        # Initialize fetcher
        print("\nInitializing enhanced fetcher...")
        fetcher = EnhancedHistoricalDataFetcher(
            broker=broker,
            max_workers=2,  # Use only 2 workers for testing
            batch_size=5
        )
        await fetcher.initialize()
        print("✅ Fetcher initialized")
        
        # Test 1: Single symbol fetch
        print("\n--- Test 1: Single Symbol Fetch ---")
        symbol = 'SPY'
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=1)  # Just 1 day
        
        print(f"Fetching {symbol} from {start_date.date()} to {end_date.date()}")
        
        result = await fetcher.fetch_symbols_batch(
            symbols=[symbol],
            timeframe=TimeFrame.DAILY,
            start_date=start_date,
            end_date=end_date,
            save_to_db=False,
            detect_duplicates=False,
            fill_gaps=False
        )
        
        # Check results
        if symbol in result['results']:
            data = result['results'][symbol]
            if 'error' in data:
                print(f"❌ Error: {data['error']}")
            else:
                print(f"✅ Success: {len(data['records'])} records fetched")
                if data['records']:
                    record = data['records'][0]
                    print(f"   Sample: Date={record['timestamp'].date()}, "
                          f"Close=${float(record['close']):.2f}, "
                          f"Volume={record['volume']:,}")
        
        # Test 2: Multiple symbols
        print("\n--- Test 2: Multiple Symbols ---")
        symbols = ['AAPL', 'MSFT']
        
        result = await fetcher.fetch_symbols_batch(
            symbols=symbols,
            timeframe=TimeFrame.DAILY,
            start_date=start_date,
            end_date=end_date,
            save_to_db=False,
            detect_duplicates=False,
            fill_gaps=False
        )
        
        stats = result['statistics']
        print(f"Results: {stats['completed_symbols']}/{stats['total_symbols']} completed")
        print(f"Total records: {stats['total_records']}")
        print(f"Time elapsed: {stats['elapsed_time']:.2f}s")
        
        # Test 3: Error handling
        print("\n--- Test 3: Error Handling ---")
        symbols_with_invalid = ['AAPL', 'INVALID_SYMBOL_123']
        
        result = await fetcher.fetch_symbols_batch(
            symbols=symbols_with_invalid,
            timeframe=TimeFrame.DAILY,
            start_date=start_date,
            end_date=end_date,
            save_to_db=False,
            detect_duplicates=False,
            fill_gaps=False
        )
        
        stats = result['statistics']
        print(f"Results: {stats['completed_symbols']} completed, {stats['failed_symbols']} failed")
        
        for symbol in symbols_with_invalid:
            if symbol in result['results']:
                data = result['results'][symbol]
                if 'error' in data:
                    print(f"  {symbol}: ❌ {data['error']}")
                else:
                    print(f"  {symbol}: ✅ {len(data['records'])} records")
        
        print("\n✅ All tests completed!")
        
        # Cleanup
        await fetcher.shutdown()
        await broker.close()
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logger.exception("Test error")
        return False


async def main():
    """Run non-interactive tests."""
    print("=" * 60)
    print("Enhanced Historical Data Fetcher - Automated Test")
    print("=" * 60)
    print("\nRunning minimal tests with real API...")
    
    success = await test_basic_functionality()
    
    if success:
        print("\n🎉 Tests passed!")
    else:
        print("\n❌ Tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())