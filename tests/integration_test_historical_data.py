#!/usr/bin/env python3
"""
Integration test for Enhanced Historical Data Fetcher with real Schwab API.

This script tests the enhanced fetcher with the actual API using safe parameters.
It uses small batches and short time periods to minimize API usage.
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
    LoggingProgressCallback,
    DetailedProgressCallback,
    ValidationPipeline,
    OHLCValidator,
    VolumeValidator,
    TimestampValidator
)
from src.broker import SchwabBroker
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


class IntegrationTestCallback:
    """Custom callback for integration testing."""
    
    def __init__(self):
        self.events = []
        self.errors = []
        self.warnings = []
    
    async def __call__(self, progress: FetchProgress, message: str):
        """Record progress events."""
        event = {
            'time': datetime.now(timezone.utc),
            'progress': progress.progress_percentage,
            'completed': progress.completed_symbols,
            'failed': progress.failed_symbols,
            'records': progress.total_records,
            'message': message
        }
        self.events.append(event)
        
        # Extract errors and warnings
        if 'error' in message.lower():
            self.errors.append(message)
        if 'warning' in message.lower():
            self.warnings.append(message)
        
        # Log progress
        logger.info(
            f"[{progress.progress_percentage:.1f}%] "
            f"{progress.completed_symbols}/{progress.total_symbols} symbols | "
            f"Records: {progress.total_records} | "
            f"Failed: {progress.failed_symbols} | "
            f"{message}"
        )


async def test_single_symbol_fetch(fetcher: EnhancedHistoricalDataFetcher):
    """Test fetching data for a single symbol."""
    print("\n=== Test 1: Single Symbol Fetch ===")
    
    symbol = 'SPY'  # Use liquid ETF for testing
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=2)  # Just 2 days
    
    print(f"Fetching {symbol} daily data from {start_date.date()} to {end_date.date()}")
    
    result = await fetcher.fetch_symbols_batch(
        symbols=[symbol],
        timeframe=TimeFrame.DAILY,
        start_date=start_date,
        end_date=end_date,
        save_to_db=False,  # Don't save for testing
        detect_duplicates=False,
        fill_gaps=False
    )
    
    # Check results
    assert 'results' in result
    assert symbol in result['results']
    
    data = result['results'][symbol]
    if 'error' in data:
        print(f"❌ Error fetching {symbol}: {data['error']}")
        return False
    
    print(f"✅ Successfully fetched {len(data['records'])} records")
    
    # Validate some records
    if data['records']:
        record = data['records'][0]
        print(f"Sample record: Date={record['timestamp']}, "
              f"OHLCV={record['open']}/{record['high']}/{record['low']}/{record['close']}/{record['volume']}")
    
    return True


async def test_batch_fetch_with_validation(fetcher: EnhancedHistoricalDataFetcher):
    """Test batch fetching with validation."""
    print("\n=== Test 2: Batch Fetch with Validation ===")
    
    symbols = ['AAPL', 'MSFT', 'GOOGL']  # Major tech stocks
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=5)  # 5 days
    
    # Add test callback
    test_callback = IntegrationTestCallback()
    fetcher._progress_callbacks.clear()
    fetcher.add_progress_callback(test_callback)
    
    print(f"Fetching {len(symbols)} symbols with validation")
    print(f"Period: {start_date.date()} to {end_date.date()}")
    
    result = await fetcher.fetch_symbols_batch(
        symbols=symbols,
        timeframe=TimeFrame.DAILY,
        start_date=start_date,
        end_date=end_date,
        save_to_db=False,
        detect_duplicates=True,
        fill_gaps=False
    )
    
    # Analyze results
    stats = result['statistics']
    print(f"\nStatistics:")
    print(f"  Total symbols: {stats['total_symbols']}")
    print(f"  Completed: {stats['completed_symbols']}")
    print(f"  Failed: {stats['failed_symbols']}")
    print(f"  Total records: {stats['total_records']}")
    print(f"  Elapsed time: {stats['elapsed_time']:.2f}s")
    
    # Check for validation issues
    total_errors = 0
    total_warnings = 0
    
    for symbol, data in result['results'].items():
        if 'error' not in data:
            errors = len(data.get('validation_errors', []))
            warnings = len(data.get('validation_warnings', []))
            total_errors += errors
            total_warnings += warnings
            
            if errors > 0:
                print(f"\n⚠️  {symbol} had {errors} validation errors")
            if warnings > 0:
                print(f"⚠️  {symbol} had {warnings} validation warnings")
    
    print(f"\nTotal validation issues: {total_errors} errors, {total_warnings} warnings")
    
    # Check callback events
    print(f"\nProgress events recorded: {len(test_callback.events)}")
    if test_callback.errors:
        print(f"Errors encountered: {len(test_callback.errors)}")
    
    return stats['failed_symbols'] == 0


async def test_intraday_fetch(fetcher: EnhancedHistoricalDataFetcher):
    """Test intraday data fetching."""
    print("\n=== Test 3: Intraday Data Fetch ===")
    
    symbol = 'QQQ'  # Another liquid ETF
    end_date = datetime.now(timezone.utc)
    
    # Get data from yesterday during market hours
    if end_date.hour < 21:  # If before market close (4 PM ET = 21 UTC)
        start_date = end_date - timedelta(days=1)
    else:
        start_date = end_date
    
    # Set to market hours
    start_date = start_date.replace(hour=14, minute=30, second=0, microsecond=0)  # 9:30 AM ET
    end_date = start_date.replace(hour=16, minute=0, second=0, microsecond=0)  # 11:00 AM ET
    
    print(f"Fetching {symbol} 5-minute data")
    print(f"Period: {start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%H:%M %Z')}")
    
    result = await fetcher.fetch_symbols_batch(
        symbols=[symbol],
        timeframe=TimeFrame.MINUTE_5,
        start_date=start_date,
        end_date=end_date,
        save_to_db=False,
        detect_duplicates=False,
        fill_gaps=False
    )
    
    data = result['results'][symbol]
    if 'error' in data:
        print(f"❌ Error fetching intraday data: {data['error']}")
        return False
    
    print(f"✅ Successfully fetched {len(data['records'])} 5-minute bars")
    
    # Calculate average volume
    if data['records']:
        avg_volume = sum(r['volume'] for r in data['records']) / len(data['records'])
        print(f"Average volume per 5-min bar: {avg_volume:,.0f}")
    
    return True


async def test_rate_limiting(fetcher: EnhancedHistoricalDataFetcher):
    """Test rate limiting behavior."""
    print("\n=== Test 4: Rate Limiting Test ===")
    
    # Use more symbols to test rate limiting
    symbols = ['SPY', 'QQQ', 'IWM', 'DIA', 'VTI', 'VOO']  # ETFs
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=1)  # Just 1 day to minimize API usage
    
    print(f"Testing rate limiting with {len(symbols)} symbols")
    
    # Track timing
    start_time = asyncio.get_event_loop().time()
    
    result = await fetcher.fetch_symbols_batch(
        symbols=symbols,
        timeframe=TimeFrame.MINUTE_1,  # High frequency data
        start_date=start_date,
        end_date=end_date,
        save_to_db=False,
        detect_duplicates=False,
        fill_gaps=False
    )
    
    elapsed = asyncio.get_event_loop().time() - start_time
    
    stats = result['statistics']
    print(f"\nCompleted in {elapsed:.2f}s")
    print(f"Average time per symbol: {elapsed/len(symbols):.2f}s")
    
    # Check if rate limiter kicked in
    if elapsed > len(symbols) * 0.5:  # If it took more than 0.5s per symbol
        print("✅ Rate limiting appears to be working (requests were throttled)")
    else:
        print("⚠️  Requests completed very quickly - rate limiting may not have triggered")
    
    return True


async def test_error_handling(fetcher: EnhancedHistoricalDataFetcher):
    """Test error handling with invalid symbols."""
    print("\n=== Test 5: Error Handling Test ===")
    
    # Mix of valid and invalid symbols
    symbols = ['AAPL', 'INVALID123', 'MSFT', 'NOTREAL456']
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=1)
    
    print(f"Testing error handling with {len(symbols)} symbols (including invalid ones)")
    
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
    print(f"\nResults:")
    print(f"  Successful: {stats['completed_symbols']}")
    print(f"  Failed: {stats['failed_symbols']}")
    
    # Check individual results
    for symbol in symbols:
        data = result['results'][symbol]
        if 'error' in data:
            print(f"  {symbol}: ❌ {data['error']}")
        else:
            print(f"  {symbol}: ✅ {len(data['records'])} records")
    
    # We expect 2 failures (invalid symbols)
    expected_failures = 2
    if stats['failed_symbols'] == expected_failures:
        print(f"\n✅ Error handling working correctly - {expected_failures} symbols failed as expected")
        return True
    else:
        print(f"\n⚠️  Expected {expected_failures} failures but got {stats['failed_symbols']}")
        return False


async def main():
    """Run integration tests."""
    print("=" * 60)
    print("Enhanced Historical Data Fetcher - Integration Tests")
    print("=" * 60)
    print("\n⚠️  These tests use the real Schwab API with minimal data requests")
    print("⚠️  Make sure you have valid API credentials configured\n")
    
    # Confirm before proceeding
    response = input("Continue with integration tests? (y/n): ")
    if response.lower() != 'y':
        print("Tests cancelled.")
        return
    
    try:
        # Initialize broker and fetcher
        print("\nInitializing broker and fetcher...")
        broker = SchwabBroker()
        await broker.initialize()
        
        fetcher = EnhancedHistoricalDataFetcher(
            broker=broker,
            max_workers=3,  # Use fewer workers for testing
            batch_size=5
        )
        await fetcher.initialize()
        
        print("✅ Initialization successful\n")
        
        # Run tests
        tests = [
            ("Single Symbol Fetch", test_single_symbol_fetch),
            ("Batch Fetch with Validation", test_batch_fetch_with_validation),
            ("Intraday Data Fetch", test_intraday_fetch),
            ("Rate Limiting", test_rate_limiting),
            ("Error Handling", test_error_handling)
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                success = await test_func(fetcher)
                results.append((test_name, success))
                await asyncio.sleep(2)  # Pause between tests
            except Exception as e:
                logger.error(f"Test '{test_name}' failed with exception: {e}")
                results.append((test_name, False))
        
        # Summary
        print("\n" + "=" * 60)
        print("Test Summary:")
        print("=" * 60)
        
        passed = sum(1 for _, success in results if success)
        total = len(results)
        
        for test_name, success in results:
            status = "✅ PASSED" if success else "❌ FAILED"
            print(f"{test_name}: {status}")
        
        print(f"\nTotal: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n🎉 All integration tests passed!")
        else:
            print(f"\n⚠️  {total - passed} tests failed")
        
    except Exception as e:
        print(f"\n❌ Integration test error: {e}")
        logger.exception("Integration test failed")
    
    finally:
        # Cleanup
        if 'fetcher' in locals():
            await fetcher.shutdown()
        if 'broker' in locals():
            await broker.close()


if __name__ == "__main__":
    asyncio.run(main())