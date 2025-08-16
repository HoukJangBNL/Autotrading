#!/usr/bin/env python3
"""Simple test for historical data fetching."""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))


async def main():
    """Simple test to fetch historical data."""
    print("Testing Historical Data Fetcher")
    print("=" * 60)
    
    # Import after path setup
    from src.data import get_historical_fetcher, TimeFrame
    from src.utils.logger import setup_logging
    
    # Setup logging
    setup_logging()
    
    try:
        # Get fetcher
        fetcher = get_historical_fetcher()
        
        # Initialize
        print("Initializing fetcher...")
        await fetcher.initialize()
        print("✅ Fetcher initialized")
        
        # Fetch daily data for AAPL
        symbol = "AAPL"
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=7)
        
        print(f"\nFetching {symbol} daily data...")
        print(f"Period: {start_date.date()} to {end_date.date()}")
        
        data = await fetcher.fetch_historical_data(
            symbol=symbol,
            timeframe=TimeFrame.DAILY,
            start_date=start_date,
            end_date=end_date,
            save_to_db=False  # Don't save for now
        )
        
        if data:
            print(f"\n✅ Successfully fetched {len(data)} data points")
            for i, bar in enumerate(data[:3]):  # Show first 3
                print(f"\n{i+1}. {bar['timestamp'].date()}")
                print(f"   Open: ${bar['open']}")
                print(f"   High: ${bar['high']}")
                print(f"   Low: ${bar['low']}")
                print(f"   Close: ${bar['close']}")
                print(f"   Volume: {bar['volume']:,}")
        else:
            print("❌ No data returned")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\nShutting down...")
        if 'fetcher' in locals():
            await fetcher.shutdown()


if __name__ == "__main__":
    asyncio.run(main())