#!/usr/bin/env python3
"""
Example script for fetching historical data using the Schwab API.

This script demonstrates common usage patterns for the HistoricalDataFetcher:
1. Fetching daily data for backtesting
2. Fetching intraday data for strategy development
3. Keeping data up to date
4. Bulk loading multiple symbols
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data import get_historical_fetcher, TimeFrame, db_service
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def fetch_daily_data_for_backtesting():
    """Fetch 2 years of daily data for backtesting."""
    print("\nExample 1: Fetching Daily Data for Backtesting")
    print("-" * 50)
    
    fetcher = get_historical_fetcher()
    await fetcher.initialize()
    
    # S&P 500 ETF and some popular stocks
    symbols = ["SPY", "AAPL", "MSFT", "GOOGL", "AMZN"]
    
    # 2 years of data
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=730)
    
    print(f"Fetching 2 years of daily data for {len(symbols)} symbols")
    print(f"Period: {start_date.date()} to {end_date.date()}")
    
    results = await fetcher.fetch_multiple_symbols(
        symbols=symbols,
        timeframe=TimeFrame.DAILY,
        start_date=start_date,
        end_date=end_date,
        max_concurrent=3
    )
    
    for symbol, data in results.items():
        if data:
            print(f"{symbol}: {len(data)} days of data fetched")
            # Calculate simple statistics
            closes = [float(d['close']) for d in data]
            avg_close = sum(closes) / len(closes)
            max_close = max(closes)
            min_close = min(closes)
            print(f"  Price range: ${min_close:.2f} - ${max_close:.2f} (avg: ${avg_close:.2f})")


async def fetch_intraday_data_for_strategy():
    """Fetch intraday data for strategy development."""
    print("\nExample 2: Fetching Intraday Data for Strategy Development")
    print("-" * 50)
    
    fetcher = get_historical_fetcher()
    
    # High-volume stocks good for day trading
    symbols = ["TSLA", "AMD", "NVDA"]
    
    # Last 30 days of 5-minute data
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=30)
    
    print(f"Fetching 30 days of 5-minute data for {len(symbols)} symbols")
    
    for symbol in symbols:
        data = await fetcher.fetch_historical_data(
            symbol=symbol,
            timeframe=TimeFrame.MINUTE_5,
            start_date=start_date,
            end_date=end_date
        )
        
        if data:
            print(f"\n{symbol}: {len(data)} 5-minute bars")
            
            # Calculate average volume per time of day
            volume_by_hour = {}
            for bar in data:
                hour = bar['timestamp'].hour
                if hour not in volume_by_hour:
                    volume_by_hour[hour] = []
                volume_by_hour[hour].append(bar['volume'])
            
            print("  Average volume by hour (EST):")
            for hour in sorted(volume_by_hour.keys()):
                if 9 <= hour <= 16:  # Market hours
                    avg_vol = sum(volume_by_hour[hour]) / len(volume_by_hour[hour])
                    print(f"    {hour:02d}:00 - {avg_vol:,.0f}")


async def keep_data_updated():
    """Keep symbol data up to date."""
    print("\nExample 3: Keeping Data Updated")
    print("-" * 50)
    
    fetcher = get_historical_fetcher()
    
    # Portfolio symbols to keep updated
    portfolio_symbols = ["AAPL", "MSFT", "GOOGL", "BRK.B", "JPM"]
    
    print(f"Updating data for {len(portfolio_symbols)} portfolio symbols")
    
    for symbol in portfolio_symbols:
        latest = await fetcher.get_latest_timestamp(symbol)
        
        if latest:
            print(f"\n{symbol}: Latest data from {latest}")
            new_records = await fetcher.update_symbol_data(
                symbol=symbol,
                timeframe=TimeFrame.MINUTE_1
            )
            print(f"  Added {new_records} new records")
        else:
            print(f"\n{symbol}: No existing data, fetching last 30 days")
            data = await fetcher.fetch_historical_data(
                symbol=symbol,
                timeframe=TimeFrame.MINUTE_1,
                start_date=datetime.now(timezone.utc) - timedelta(days=30)
            )
            print(f"  Fetched {len(data)} records")


async def bulk_load_sector_data():
    """Bulk load data for an entire sector."""
    print("\nExample 4: Bulk Loading Sector Data")
    print("-" * 50)
    
    fetcher = get_historical_fetcher()
    
    # Technology sector leaders
    tech_stocks = [
        "AAPL", "MSFT", "GOOGL", "META", "NVDA",
        "ADBE", "CRM", "INTC", "AMD", "ORCL",
        "IBM", "CSCO", "AVGO", "TXN", "QCOM"
    ]
    
    # 6 months of daily data
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=180)
    
    print(f"Bulk loading {len(tech_stocks)} tech stocks")
    print(f"Period: {start_date.date()} to {end_date.date()}")
    
    # Process in batches to avoid overwhelming the API
    batch_size = 5
    total_records = 0
    
    for i in range(0, len(tech_stocks), batch_size):
        batch = tech_stocks[i:i + batch_size]
        print(f"\nProcessing batch {i//batch_size + 1}: {', '.join(batch)}")
        
        results = await fetcher.fetch_multiple_symbols(
            symbols=batch,
            timeframe=TimeFrame.DAILY,
            start_date=start_date,
            end_date=end_date,
            max_concurrent=3
        )
        
        for symbol, data in results.items():
            if data:
                total_records += len(data)
                print(f"  {symbol}: {len(data)} records")
        
        # Small delay between batches
        if i + batch_size < len(tech_stocks):
            await asyncio.sleep(2)
    
    print(f"\nTotal records loaded: {total_records:,}")


async def analyze_data_quality():
    """Analyze the quality of fetched data."""
    print("\nExample 5: Data Quality Analysis")
    print("-" * 50)
    
    fetcher = get_historical_fetcher()
    
    # Fetch some data to analyze
    symbol = "SPY"
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=30)
    
    data = await fetcher.fetch_historical_data(
        symbol=symbol,
        timeframe=TimeFrame.DAILY,
        start_date=start_date,
        end_date=end_date,
        save_to_db=False  # Don't save, just analyze
    )
    
    if data:
        print(f"Analyzing {len(data)} days of {symbol} data")
        
        # Check for data quality issues
        issues = []
        
        for i, bar in enumerate(data):
            # Check OHLC relationships
            if bar['high'] < bar['low']:
                issues.append(f"Day {i}: High < Low")
            if bar['open'] > bar['high'] or bar['open'] < bar['low']:
                issues.append(f"Day {i}: Open outside High-Low range")
            if bar['close'] > bar['high'] or bar['close'] < bar['low']:
                issues.append(f"Day {i}: Close outside High-Low range")
            
            # Check for zero volume (except holidays)
            if bar['volume'] == 0:
                issues.append(f"Day {i} ({bar['timestamp'].date()}): Zero volume")
            
            # Check for extreme price movements (>20% in a day)
            if i > 0:
                prev_close = float(data[i-1]['close'])
                curr_close = float(bar['close'])
                pct_change = abs((curr_close - prev_close) / prev_close * 100)
                if pct_change > 20:
                    issues.append(
                        f"Day {i} ({bar['timestamp'].date()}): "
                        f"Extreme movement {pct_change:.1f}%"
                    )
        
        if issues:
            print(f"\nFound {len(issues)} potential data quality issues:")
            for issue in issues[:5]:  # Show first 5
                print(f"  - {issue}")
            if len(issues) > 5:
                print(f"  ... and {len(issues) - 5} more")
        else:
            print("\n✅ No data quality issues found")
        
        # Calculate basic statistics
        closes = [float(d['close']) for d in data]
        returns = [(closes[i] - closes[i-1]) / closes[i-1] * 100 
                   for i in range(1, len(closes))]
        
        print(f"\nBasic Statistics:")
        print(f"  Average daily return: {sum(returns) / len(returns):.3f}%")
        print(f"  Volatility (std dev): {(sum((r - sum(returns)/len(returns))**2 for r in returns) / len(returns))**0.5:.3f}%")
        print(f"  Max daily gain: {max(returns):.2f}%")
        print(f"  Max daily loss: {min(returns):.2f}%")


async def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("Schwab Historical Data Fetcher Examples")
    print("="*60)
    
    # Initialize database
    db_service.initialize()
    
    try:
        # Run examples with delays between them
        await fetch_daily_data_for_backtesting()
        await asyncio.sleep(2)
        
        await fetch_intraday_data_for_strategy()
        await asyncio.sleep(2)
        
        await keep_data_updated()
        await asyncio.sleep(2)
        
        await bulk_load_sector_data()
        await asyncio.sleep(2)
        
        await analyze_data_quality()
        
        print("\n" + "="*60)
        print("All examples completed successfully!")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n\nExamples interrupted by user")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        logger.error("Examples failed", exc_info=True)
        
    finally:
        # Cleanup
        fetcher = get_historical_fetcher()
        await fetcher.shutdown()
        db_service.close()


if __name__ == "__main__":
    print("""
This script demonstrates common usage patterns for fetching historical data.
Make sure you have:
1. Set up your Schwab API credentials in .env
2. Completed OAuth authentication (run scripts/test_auth.py first)
3. Database is running (PostgreSQL)

Press Ctrl+C to stop at any time.
""")
    
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Failed to run examples: {e}")
        sys.exit(1)