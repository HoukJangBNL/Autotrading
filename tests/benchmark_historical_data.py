#!/usr/bin/env python3
"""
Benchmark script for comparing original vs enhanced historical data fetcher.

This script measures performance differences between the two implementations.
"""

import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.data.historical_data import HistoricalDataFetcher
from src.data.historical_data_enhanced import (
    EnhancedHistoricalDataFetcher,
    TimeFrame,
    LoggingProgressCallback
)
from src.broker import SchwabBroker
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def benchmark_original_fetcher(
    broker: SchwabBroker,
    symbols: List[str],
    start_date: datetime,
    end_date: datetime
) -> Dict[str, Any]:
    """Benchmark the original fetcher."""
    print("\n=== Benchmarking Original Fetcher ===")
    
    fetcher = HistoricalDataFetcher(broker=broker)
    
    start_time = time.time()
    results = {}
    failed = 0
    total_records = 0
    
    # Fetch symbols sequentially (original behavior)
    for i, symbol in enumerate(symbols):
        try:
            print(f"Fetching {symbol} ({i+1}/{len(symbols)})...")
            data = await fetcher.fetch_and_store_price_history(
                symbol=symbol,
                period_type="day",
                period=10,
                frequency_type="minute",
                frequency=5,
                start_date=start_date,
                end_date=end_date,
                save_to_db=False
            )
            
            if data and 'candles' in data:
                total_records += len(data['candles'])
                results[symbol] = {'records': len(data['candles'])}
            else:
                failed += 1
                results[symbol] = {'error': 'No data'}
                
        except Exception as e:
            failed += 1
            results[symbol] = {'error': str(e)}
            logger.error(f"Error fetching {symbol}: {e}")
    
    elapsed = time.time() - start_time
    
    return {
        'implementation': 'Original',
        'elapsed_time': elapsed,
        'total_symbols': len(symbols),
        'completed_symbols': len(symbols) - failed,
        'failed_symbols': failed,
        'total_records': total_records,
        'avg_time_per_symbol': elapsed / len(symbols),
        'records_per_second': total_records / elapsed if elapsed > 0 else 0,
        'results': results
    }


async def benchmark_enhanced_fetcher(
    broker: SchwabBroker,
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
    max_workers: int = 10
) -> Dict[str, Any]:
    """Benchmark the enhanced fetcher."""
    print(f"\n=== Benchmarking Enhanced Fetcher (workers={max_workers}) ===")
    
    fetcher = EnhancedHistoricalDataFetcher(
        broker=broker,
        max_workers=max_workers,
        batch_size=10
    )
    await fetcher.initialize()
    
    # Add minimal progress callback
    fetcher.add_progress_callback(LoggingProgressCallback(log_interval=25))
    
    start_time = time.time()
    
    result = await fetcher.fetch_symbols_batch(
        symbols=symbols,
        timeframe=TimeFrame.MINUTE_5,
        start_date=start_date,
        end_date=end_date,
        save_to_db=False,
        detect_duplicates=False,
        fill_gaps=False
    )
    
    elapsed = time.time() - start_time
    stats = result['statistics']
    
    await fetcher.shutdown()
    
    return {
        'implementation': f'Enhanced (workers={max_workers})',
        'elapsed_time': elapsed,
        'total_symbols': stats['total_symbols'],
        'completed_symbols': stats['completed_symbols'],
        'failed_symbols': stats['failed_symbols'],
        'total_records': stats['total_records'],
        'avg_time_per_symbol': elapsed / stats['total_symbols'],
        'records_per_second': stats['total_records'] / elapsed if elapsed > 0 else 0,
        'results': result['results']
    }


def print_comparison(results: List[Dict[str, Any]]):
    """Print comparison of benchmark results."""
    print("\n" + "=" * 80)
    print("Benchmark Results Comparison")
    print("=" * 80)
    
    # Print header
    print(f"{'Implementation':<25} {'Time (s)':<10} {'Symbols':<10} {'Records':<10} "
          f"{'Avg/Symbol':<12} {'Records/s':<10}")
    print("-" * 80)
    
    # Print results
    for result in results:
        print(f"{result['implementation']:<25} "
              f"{result['elapsed_time']:<10.2f} "
              f"{result['completed_symbols']:<10} "
              f"{result['total_records']:<10} "
              f"{result['avg_time_per_symbol']:<12.2f} "
              f"{result['records_per_second']:<10.1f}")
    
    # Calculate speedup
    if len(results) >= 2:
        original = results[0]
        print("\nSpeedup Analysis:")
        print("-" * 40)
        
        for i in range(1, len(results)):
            enhanced = results[i]
            speedup = original['elapsed_time'] / enhanced['elapsed_time']
            print(f"{enhanced['implementation']} vs {original['implementation']}: "
                  f"{speedup:.2f}x faster")


async def run_benchmark(broker: SchwabBroker, test_size: str = "small"):
    """Run benchmark with different test sizes."""
    
    # Define test configurations
    test_configs = {
        "small": {
            "symbols": ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"],
            "days": 2
        },
        "medium": {
            "symbols": ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", 
                       "META", "NVDA", "NFLX", "ORCL", "CSCO"],
            "days": 5
        },
        "large": {
            "symbols": ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", 
                       "META", "NVDA", "NFLX", "ORCL", "CSCO",
                       "INTC", "AMD", "PYPL", "ADBE", "CRM",
                       "UBER", "SQ", "SHOP", "ROKU", "SNAP"],
            "days": 7
        }
    }
    
    config = test_configs.get(test_size, test_configs["small"])
    symbols = config["symbols"]
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=config["days"])
    
    print(f"\nBenchmark Configuration:")
    print(f"  Test size: {test_size}")
    print(f"  Symbols: {len(symbols)}")
    print(f"  Date range: {config['days']} days")
    print(f"  Period: {start_date.date()} to {end_date.date()}")
    
    results = []
    
    # Benchmark original fetcher
    try:
        original_result = await benchmark_original_fetcher(
            broker, symbols, start_date, end_date
        )
        results.append(original_result)
    except Exception as e:
        print(f"Error benchmarking original fetcher: {e}")
    
    # Wait between tests
    await asyncio.sleep(2)
    
    # Benchmark enhanced fetcher with different worker counts
    for max_workers in [1, 5, 10]:
        try:
            enhanced_result = await benchmark_enhanced_fetcher(
                broker, symbols, start_date, end_date, max_workers
            )
            results.append(enhanced_result)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Error benchmarking enhanced fetcher (workers={max_workers}): {e}")
    
    # Print comparison
    print_comparison(results)
    
    # Additional analysis
    if results:
        print("\nDetailed Analysis:")
        print("-" * 40)
        
        # Find best configuration
        best = min(results, key=lambda x: x['elapsed_time'])
        print(f"Fastest: {best['implementation']} ({best['elapsed_time']:.2f}s)")
        
        # Check failure rates
        for result in results:
            if result['failed_symbols'] > 0:
                failure_rate = (result['failed_symbols'] / result['total_symbols']) * 100
                print(f"{result['implementation']} failure rate: {failure_rate:.1f}%")


async def main():
    """Main benchmark function."""
    print("=" * 80)
    print("Historical Data Fetcher Benchmark")
    print("=" * 80)
    print("\n⚠️  This benchmark uses the real Schwab API")
    print("⚠️  Results will vary based on network conditions and API response times\n")
    
    # Get test size
    test_size = "small"  # Default
    if len(sys.argv) > 1:
        test_size = sys.argv[1]
        if test_size not in ["small", "medium", "large"]:
            print(f"Invalid test size: {test_size}")
            print("Usage: python benchmark_historical_data.py [small|medium|large]")
            return
    
    # Confirm before proceeding
    response = input(f"Run {test_size} benchmark? (y/n): ")
    if response.lower() != 'y':
        print("Benchmark cancelled.")
        return
    
    try:
        # Initialize broker
        print("\nInitializing broker...")
        broker = SchwabBroker()
        await broker.initialize()
        print("✅ Broker initialized\n")
        
        # Run benchmark
        await run_benchmark(broker, test_size)
        
        print("\n✅ Benchmark completed!")
        
    except Exception as e:
        print(f"\n❌ Benchmark error: {e}")
        logger.exception("Benchmark failed")
    
    finally:
        # Cleanup
        if 'broker' in locals():
            await broker.close()


if __name__ == "__main__":
    asyncio.run(main())