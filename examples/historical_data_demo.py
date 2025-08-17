#!/usr/bin/env python3
"""
Demo script showing how to use the enhanced historical data fetcher.

This script demonstrates:
- Batch symbol fetching with parallel processing
- Progress tracking with callbacks
- Data validation and duplicate detection
- Gap detection and filling
- Custom validation rules
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
    DataValidator,
    ValidationResult
)
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


# Custom validator example
class PriceChangeValidator(DataValidator):
    """Custom validator to check for extreme price changes."""
    
    def __init__(self, max_change_percent: float = 20.0):
        self.max_change_percent = max_change_percent
    
    async def validate(self, data: dict) -> ValidationResult:
        """Validate price change is within reasonable bounds."""
        warnings = []
        
        try:
            open_price = float(data['open'])
            close_price = float(data['close'])
            
            if open_price > 0:
                change_percent = abs((close_price - open_price) / open_price * 100)
                
                if change_percent > self.max_change_percent:
                    warnings.append(
                        f"Large price change: {change_percent:.1f}% "
                        f"(Open: {open_price}, Close: {close_price})"
                    )
        except (KeyError, ValueError, ZeroDivisionError):
            pass  # Skip if data is missing or invalid
        
        return ValidationResult(
            is_valid=True,  # Don't reject, just warn
            warnings=warnings,
            cleaned_data=data
        )


# Custom progress callback
class ConsoleProgressBar:
    """Console progress bar callback."""
    
    def __init__(self, width: int = 50):
        self.width = width
    
    async def __call__(self, progress: FetchProgress, message: str):
        """Display progress bar in console."""
        filled = int(self.width * progress.progress_percentage / 100)
        bar = '█' * filled + '░' * (self.width - filled)
        
        eta = progress.estimated_time_remaining
        eta_str = f"{eta/60:.1f}m" if eta > 60 else f"{eta:.0f}s"
        
        print(f"\r[{bar}] {progress.progress_percentage:.1f}% | "
              f"{progress.completed_symbols}/{progress.total_symbols} | "
              f"ETA: {eta_str} | {message:<30}", end='', flush=True)
        
        if progress.completed_symbols == progress.total_symbols:
            print()  # New line when complete


async def demo_basic_batch_fetch(fetcher: EnhancedHistoricalDataFetcher):
    """Demonstrate basic batch fetching."""
    print("\n=== Basic Batch Fetch Demo ===\n")
    
    symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA']
    
    # Add simple progress callback
    fetcher.add_progress_callback(LoggingProgressCallback(log_interval=20))
    
    # Fetch last 5 days of daily data
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=5)
    
    print(f"Fetching {len(symbols)} symbols from {start_date.date()} to {end_date.date()}")
    
    result = await fetcher.fetch_symbols_batch(
        symbols=symbols,
        timeframe=TimeFrame.DAILY,
        start_date=start_date,
        end_date=end_date,
        save_to_db=False,  # Don't save for demo
        detect_duplicates=False,
        fill_gaps=False
    )
    
    # Display results
    print("\n\nResults:")
    for symbol, data in result['results'].items():
        if 'error' in data:
            print(f"  {symbol}: ERROR - {data['error']}")
        else:
            print(f"  {symbol}: {len(data['records'])} records fetched")
    
    # Display statistics
    stats = result['statistics']
    print(f"\nStatistics:")
    print(f"  Total symbols: {stats['total_symbols']}")
    print(f"  Completed: {stats['completed_symbols']}")
    print(f"  Failed: {stats['failed_symbols']}")
    print(f"  Total records: {stats['total_records']}")
    print(f"  Time elapsed: {stats['elapsed_time']:.1f} seconds")


async def demo_advanced_features(fetcher: EnhancedHistoricalDataFetcher):
    """Demonstrate advanced features."""
    print("\n=== Advanced Features Demo ===\n")
    
    # Use custom validation pipeline
    custom_pipeline = ValidationPipeline(validators=[
        OHLCValidator(),
        VolumeValidator(min_volume=100, max_volume=1_000_000_000),
        PriceChangeValidator(max_change_percent=15.0)
    ])
    
    fetcher.validation_pipeline = custom_pipeline
    
    # Add detailed progress tracking
    fetcher._progress_callbacks.clear()  # Clear previous callbacks
    fetcher.add_progress_callback(ConsoleProgressBar())
    
    symbols = ['AAPL', 'NVDA', 'META']
    
    # Fetch 1-minute data for today
    end_date = datetime.now(timezone.utc)
    start_date = end_date.replace(hour=14, minute=30, second=0, microsecond=0)  # Market open
    
    print(f"Fetching intraday data with validation")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Timeframe: 1-minute bars")
    print(f"Period: {start_date.strftime('%H:%M')} to {end_date.strftime('%H:%M %Z')}")
    print()
    
    result = await fetcher.fetch_symbols_batch(
        symbols=symbols,
        timeframe=TimeFrame.MINUTE_1,
        start_date=start_date,
        end_date=end_date,
        save_to_db=False,
        detect_duplicates=True,  # Enable duplicate detection
        fill_gaps=False
    )
    
    print("\n\nValidation Summary:")
    for symbol, data in result['results'].items():
        if 'error' not in data:
            errors = data.get('validation_errors', [])
            warnings = data.get('validation_warnings', [])
            
            print(f"\n{symbol}:")
            print(f"  Records: {len(data['records'])}")
            print(f"  Validation errors: {len(errors)}")
            print(f"  Validation warnings: {len(warnings)}")
            
            if warnings:
                print(f"  Sample warnings:")
                for warning in warnings[:3]:  # Show first 3 warnings
                    print(f"    - {warning}")


async def demo_gap_detection(fetcher: EnhancedHistoricalDataFetcher):
    """Demonstrate gap detection."""
    print("\n=== Gap Detection Demo ===\n")
    
    # For demo, we'll analyze a single symbol
    symbol = 'AAPL'
    
    # Check for gaps in the last month
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=30)
    
    print(f"Checking for data gaps in {symbol}")
    print(f"Period: {start_date.date()} to {end_date.date()}")
    
    # First, fetch some data to have something in the "database"
    print("\nFetching initial data...")
    await fetcher.fetch_symbols_batch(
        symbols=[symbol],
        timeframe=TimeFrame.DAILY,
        start_date=start_date,
        end_date=end_date,
        save_to_db=False
    )
    
    # Now detect gaps (this would normally work with real database)
    # For demo, we'll show the concept
    print("\nGap detection would identify:")
    print("  - Weekend gaps (expected)")
    print("  - Holiday gaps (expected)")
    print("  - Missing data periods (unexpected)")
    print("  - After-hours gaps for intraday data")
    
    # Show statistics
    stats = await fetcher.get_data_statistics(symbol, start_date, end_date)
    print(f"\nData statistics for {symbol}:")
    print(f"  Record count: {stats['record_count']}")
    if stats['date_range']['start']:
        print(f"  Date range: {stats['date_range']['start']} to {stats['date_range']['end']}")
    if stats['price_range']['min']:
        print(f"  Price range: ${stats['price_range']['min']:.2f} - ${stats['price_range']['max']:.2f}")
    if stats['average_volume']:
        print(f"  Average volume: {stats['average_volume']:,.0f}")


async def demo_parallel_performance(fetcher: EnhancedHistoricalDataFetcher):
    """Demonstrate parallel fetching performance."""
    print("\n=== Parallel Performance Demo ===\n")
    
    # Large batch of symbols
    symbols = [
        'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX',
        'ORCL', 'CSCO', 'INTC', 'AMD', 'PYPL', 'ADBE', 'CRM', 'UBER'
    ]
    
    print(f"Fetching {len(symbols)} symbols with different worker counts\n")
    
    # Test with different worker counts
    for max_workers in [1, 5, 10]:
        # Create new fetcher with specific worker count
        test_fetcher = EnhancedHistoricalDataFetcher(
            broker=fetcher.broker,
            max_workers=max_workers,
            batch_size=10
        )
        await test_fetcher.initialize()
        
        # Add progress callback
        test_fetcher.add_progress_callback(DetailedProgressCallback())
        
        print(f"\nTesting with {max_workers} workers:")
        start_time = asyncio.get_event_loop().time()
        
        result = await test_fetcher.fetch_symbols_batch(
            symbols=symbols[:8],  # Use subset for faster demo
            timeframe=TimeFrame.DAILY,
            start_date=datetime.now(timezone.utc) - timedelta(days=5),
            save_to_db=False
        )
        
        elapsed = asyncio.get_event_loop().time() - start_time
        
        stats = result['statistics']
        print(f"  Completed in {elapsed:.1f} seconds")
        print(f"  Records fetched: {stats['total_records']}")
        print(f"  Rate: {stats['total_records']/elapsed:.1f} records/second")


async def main():
    """Main demo function."""
    print("=" * 60)
    print("Enhanced Historical Data Fetcher Demo")
    print("=" * 60)
    
    try:
        # Initialize fetcher
        print("\nInitializing enhanced fetcher...")
        fetcher = EnhancedHistoricalDataFetcher(
            max_workers=5,
            batch_size=10
        )
        await fetcher.initialize()
        print("✅ Fetcher initialized successfully!\n")
        
        # Run demos
        await demo_basic_batch_fetch(fetcher)
        
        response = input("\nContinue with advanced features demo? (y/n): ")
        if response.lower() == 'y':
            await demo_advanced_features(fetcher)
        
        response = input("\nContinue with gap detection demo? (y/n): ")
        if response.lower() == 'y':
            await demo_gap_detection(fetcher)
        
        response = input("\nContinue with parallel performance demo? (y/n): ")
        if response.lower() == 'y':
            await demo_parallel_performance(fetcher)
        
        print("\n✅ Demo completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        logger.exception("Demo error")
    
    finally:
        await fetcher.shutdown()
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())