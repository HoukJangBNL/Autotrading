#!/usr/bin/env python3
"""Test historical data fetching from Schwab API."""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data import (
    get_historical_fetcher,
    HistoricalDataFetcher,
    TimeFrame,
    db_service
)
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def test_single_symbol():
    """Test fetching data for a single symbol."""
    print("\n" + "="*60)
    print("Test 1: Fetching Single Symbol Data")
    print("="*60)
    
    fetcher = get_historical_fetcher()
    await fetcher.initialize()
    
    # Fetch daily data for AAPL for the last month
    symbol = "AAPL"
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=30)
    
    print(f"\nFetching daily data for {symbol}")
    print(f"Period: {start_date.date()} to {end_date.date()}")
    
    try:
        data = await fetcher.fetch_historical_data(
            symbol=symbol,
            timeframe=TimeFrame.DAILY,
            start_date=start_date,
            end_date=end_date,
            save_to_db=True
        )
        
        print(f"\n✅ Successfully fetched {len(data)} data points")
        
        if data:
            # Show first and last few records
            print("\nFirst 3 records:")
            for i, record in enumerate(data[:3]):
                print(f"  {i+1}. {record['timestamp'].date()}: "
                      f"O={record['open']}, H={record['high']}, "
                      f"L={record['low']}, C={record['close']}, "
                      f"V={record['volume']:,}")
            
            if len(data) > 6:
                print("\nLast 3 records:")
                for i, record in enumerate(data[-3:], len(data)-2):
                    print(f"  {i}. {record['timestamp'].date()}: "
                          f"O={record['open']}, H={record['high']}, "
                          f"L={record['low']}, C={record['close']}, "
                          f"V={record['volume']:,}")
        
    except Exception as e:
        print(f"\n❌ Error fetching data: {e}")
        logger.error(f"Failed to fetch data for {symbol}", exc_info=True)
        return False
    
    return True


async def test_intraday_data():
    """Test fetching intraday data."""
    print("\n" + "="*60)
    print("Test 2: Fetching Intraday Data")
    print("="*60)
    
    fetcher = get_historical_fetcher()
    
    # Fetch 1-minute data for the last 5 trading days
    symbol = "MSFT"
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=5)
    
    print(f"\nFetching 1-minute data for {symbol}")
    print(f"Period: {start_date.date()} to {end_date.date()}")
    
    try:
        data = await fetcher.fetch_historical_data(
            symbol=symbol,
            timeframe=TimeFrame.MINUTE_1,
            start_date=start_date,
            end_date=end_date,
            save_to_db=True
        )
        
        print(f"\n✅ Successfully fetched {len(data)} data points")
        
        if data:
            # Show sample records
            print("\nSample records (every 100th):")
            for i in range(0, len(data), max(1, len(data) // 10)):
                record = data[i]
                print(f"  {record['timestamp']}: C={record['close']}, V={record['volume']:,}")
        
    except Exception as e:
        print(f"\n❌ Error fetching intraday data: {e}")
        logger.error(f"Failed to fetch intraday data for {symbol}", exc_info=True)
        return False
    
    return True


async def test_multiple_symbols():
    """Test fetching data for multiple symbols concurrently."""
    print("\n" + "="*60)
    print("Test 3: Fetching Multiple Symbols")
    print("="*60)
    
    fetcher = get_historical_fetcher()
    
    # Tech stocks
    symbols = ["AAPL", "GOOGL", "MSFT", "META", "NVDA"]
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=7)
    
    print(f"\nFetching daily data for {len(symbols)} symbols")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Period: {start_date.date()} to {end_date.date()}")
    
    try:
        results = await fetcher.fetch_multiple_symbols(
            symbols=symbols,
            timeframe=TimeFrame.DAILY,
            start_date=start_date,
            end_date=end_date,
            max_concurrent=3  # Limit concurrent requests
        )
        
        print("\n✅ Results:")
        for symbol, data in results.items():
            print(f"  {symbol}: {len(data)} data points")
            if data:
                latest = data[-1]
                print(f"    Latest: {latest['timestamp'].date()} - Close: ${latest['close']}")
        
    except Exception as e:
        print(f"\n❌ Error fetching multiple symbols: {e}")
        logger.error("Failed to fetch multiple symbols", exc_info=True)
        return False
    
    return True


async def test_data_update():
    """Test updating existing symbol data."""
    print("\n" + "="*60)
    print("Test 4: Updating Existing Data")
    print("="*60)
    
    fetcher = get_historical_fetcher()
    symbol = "AAPL"
    
    print(f"\nChecking latest data for {symbol}...")
    
    try:
        # Get latest timestamp
        latest = await fetcher.get_latest_timestamp(symbol)
        
        if latest:
            print(f"Latest data point: {latest}")
            print("\nUpdating with new data...")
            
            # Update with new data
            new_records = await fetcher.update_symbol_data(
                symbol=symbol,
                timeframe=TimeFrame.MINUTE_1
            )
            
            print(f"✅ Added {new_records} new records")
        else:
            print("No existing data found. Fetching initial data...")
            
            # Fetch initial data
            data = await fetcher.fetch_historical_data(
                symbol=symbol,
                timeframe=TimeFrame.MINUTE_1,
                start_date=datetime.now(timezone.utc) - timedelta(days=5)
            )
            
            print(f"✅ Fetched {len(data)} initial records")
        
    except Exception as e:
        print(f"\n❌ Error updating data: {e}")
        logger.error(f"Failed to update data for {symbol}", exc_info=True)
        return False
    
    return True


async def test_gap_detection():
    """Test gap detection in historical data."""
    print("\n" + "="*60)
    print("Test 5: Gap Detection")
    print("="*60)
    
    fetcher = get_historical_fetcher()
    symbol = "MSFT"
    
    print(f"\nChecking for gaps in {symbol} data...")
    
    try:
        # First ensure we have some data
        await fetcher.fetch_historical_data(
            symbol=symbol,
            timeframe=TimeFrame.DAILY,
            start_date=datetime.now(timezone.utc) - timedelta(days=90)
        )
        
        # Check for gaps
        gaps_filled = await fetcher.fill_data_gaps(
            symbol=symbol,
            timeframe=TimeFrame.DAILY,
            max_gap_minutes=1440 * 5  # 5 days
        )
        
        if gaps_filled > 0:
            print(f"✅ Filled {gaps_filled} gap records")
        else:
            print("✅ No gaps found in the data")
        
    except Exception as e:
        print(f"\n❌ Error checking gaps: {e}")
        logger.error(f"Failed to check gaps for {symbol}", exc_info=True)
        return False
    
    return True


async def check_database_stats():
    """Check database statistics."""
    print("\n" + "="*60)
    print("Database Statistics")
    print("="*60)
    
    try:
        async with db_service.get_async_session() as session:
            from sqlalchemy import text
            
            # Total records
            result = await session.execute(
                text("SELECT COUNT(*) FROM price_data")
            )
            total_records = result.scalar()
            
            # Unique symbols
            result = await session.execute(
                text("SELECT COUNT(DISTINCT symbol) FROM price_data")
            )
            unique_symbols = result.scalar()
            
            # Date range
            result = await session.execute(
                text("SELECT MIN(timestamp), MAX(timestamp) FROM price_data")
            )
            min_date, max_date = result.one()
            
            print(f"\nTotal records: {total_records:,}")
            print(f"Unique symbols: {unique_symbols}")
            if min_date and max_date:
                print(f"Date range: {min_date.date()} to {max_date.date()}")
            
            # Records per symbol
            result = await session.execute(
                text("""
                    SELECT symbol, COUNT(*) as count 
                    FROM price_data 
                    GROUP BY symbol 
                    ORDER BY count DESC 
                    LIMIT 10
                """)
            )
            
            print("\nTop symbols by record count:")
            for symbol, count in result:
                print(f"  {symbol}: {count:,} records")
                
    except Exception as e:
        print(f"\n❌ Error checking database stats: {e}")
        logger.error("Failed to check database stats", exc_info=True)


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Schwab Historical Data Fetcher Test Suite")
    print("="*60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize database
    db_service.initialize()
    
    try:
        # Run tests
        tests_passed = 0
        total_tests = 5
        
        # Test 1: Single symbol
        if await test_single_symbol():
            tests_passed += 1
        
        # Small delay between tests
        await asyncio.sleep(1)
        
        # Test 2: Intraday data
        if await test_intraday_data():
            tests_passed += 1
        
        await asyncio.sleep(1)
        
        # Test 3: Multiple symbols
        if await test_multiple_symbols():
            tests_passed += 1
        
        await asyncio.sleep(1)
        
        # Test 4: Data update
        if await test_data_update():
            tests_passed += 1
        
        await asyncio.sleep(1)
        
        # Test 5: Gap detection
        if await test_gap_detection():
            tests_passed += 1
        
        # Show database stats
        await check_database_stats()
        
        # Summary
        print("\n" + "="*60)
        print("Test Summary")
        print("="*60)
        print(f"Tests passed: {tests_passed}/{total_tests}")
        
        if tests_passed == total_tests:
            print("✅ All tests passed! Historical data fetcher is working correctly.")
        else:
            print(f"⚠️  {total_tests - tests_passed} tests failed.")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logger.error("Test suite failed", exc_info=True)
        
    finally:
        # Cleanup
        fetcher = get_historical_fetcher()
        await fetcher.shutdown()
        db_service.close()
        
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    # Run the test suite
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Failed to run tests: {e}")
        sys.exit(1)