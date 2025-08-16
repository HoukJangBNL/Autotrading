#!/usr/bin/env python3
"""Test fetching historical data with direct client."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))


async def main():
    """Test historical data fetching."""
    print("Testing Historical Data Fetch")
    print("=" * 60)
    
    # Use direct client
    from schwab import auth
    from src.config import get_settings
    from src.data import TimeFrame, db_service
    from src.data.historical_data import HistoricalDataFetcher
    
    settings = get_settings()
    
    # Create client directly
    print("Creating Schwab client...")
    client = auth.easy_client(
        api_key=settings.schwab.api_key,
        app_secret=settings.schwab.app_secret,
        callback_url=settings.schwab.callback_url,
        token_path=str(settings.project_root / "config" / "schwab_token.json"),
        asyncio=True
    )
    
    # Create fetcher and inject client
    fetcher = HistoricalDataFetcher()
    fetcher.client = client  # Inject client directly
    
    # Initialize database
    print("\nInitializing database...")
    db_service.initialize()
    
    # Test fetching
    symbol = "AAPL"
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)
    
    print(f"\nFetching {symbol} daily data...")
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
            print("\nFirst record:")
            first = data[0]
            print(f"  Date: {first['timestamp'].date()}")
            print(f"  Open: ${first['open']}")
            print(f"  Close: ${first['close']}")
            print(f"  Volume: {first['volume']:,}")
            
            print("\nLast record:")
            last = data[-1]
            print(f"  Date: {last['timestamp'].date()}")
            print(f"  Open: ${last['open']}")
            print(f"  Close: ${last['close']}")
            print(f"  Volume: {last['volume']:,}")
            
            # Check database
            from sqlalchemy import text
            async with db_service.get_async_session() as session:
                result = await session.execute(
                    text("SELECT COUNT(*) FROM price_data WHERE symbol = :symbol"),
                    {"symbol": symbol}
                )
                count = result.scalar()
                print(f"\n✅ Records in database: {count}")
                
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        db_service.close()


if __name__ == "__main__":
    asyncio.run(main())