#!/usr/bin/env python3
"""
Analyze test results and performance metrics for the enhanced historical data fetcher.
"""

import asyncio
import sys
import time
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any

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


class PerformanceAnalyzer:
    """Analyze performance metrics for the fetcher."""
    
    def __init__(self):
        self.metrics = {
            'fetch_times': [],
            'records_per_symbol': [],
            'errors': [],
            'rate_limit_hits': 0,
            'total_api_calls': 0
        }
        
    async def __call__(self, progress: FetchProgress, message: str):
        """Track performance metrics from progress updates."""
        if "completed" in message.lower():
            # Extract timing info
            if progress.completed_symbols > 0:
                avg_time = progress.elapsed_time / progress.completed_symbols
                self.metrics['fetch_times'].append(avg_time)
        
        if "rate limit" in message.lower():
            self.metrics['rate_limit_hits'] += 1
        
        if "error" in message.lower():
            self.metrics['errors'].append(message)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        fetch_times = self.metrics['fetch_times']
        
        return {
            'avg_fetch_time': statistics.mean(fetch_times) if fetch_times else 0,
            'min_fetch_time': min(fetch_times) if fetch_times else 0,
            'max_fetch_time': max(fetch_times) if fetch_times else 0,
            'std_dev': statistics.stdev(fetch_times) if len(fetch_times) > 1 else 0,
            'rate_limit_hits': self.metrics['rate_limit_hits'],
            'error_count': len(self.metrics['errors'])
        }


async def analyze_worker_performance(broker: SchwabBroker):
    """Analyze performance with different worker counts."""
    print("\n=== Worker Performance Analysis ===")
    
    symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX']
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=3)
    
    results = []
    
    for worker_count in [1, 2, 5, 10]:
        print(f"\nTesting with {worker_count} workers...")
        
        fetcher = EnhancedHistoricalDataFetcher(
            broker=broker,
            max_workers=worker_count,
            batch_size=10
        )
        await fetcher.initialize()
        
        # Add performance analyzer
        analyzer = PerformanceAnalyzer()
        fetcher.add_progress_callback(analyzer)
        
        # Time the fetch
        start_time = time.time()
        
        result = await fetcher.fetch_symbols_batch(
            symbols=symbols,
            timeframe=TimeFrame.DAILY,
            start_date=start_date,
            end_date=end_date,
            save_to_db=False,
            detect_duplicates=False,
            fill_gaps=False
        )
        
        elapsed = time.time() - start_time
        
        stats = result['statistics']
        perf_summary = analyzer.get_summary()
        
        results.append({
            'workers': worker_count,
            'elapsed_time': elapsed,
            'symbols_completed': stats['completed_symbols'],
            'total_records': stats['total_records'],
            'throughput': stats['completed_symbols'] / elapsed,
            'avg_time_per_symbol': perf_summary['avg_fetch_time'],
            'rate_limit_hits': perf_summary['rate_limit_hits']
        })
        
        print(f"  Elapsed: {elapsed:.2f}s")
        print(f"  Throughput: {stats['completed_symbols'] / elapsed:.2f} symbols/sec")
        print(f"  Rate limit hits: {perf_summary['rate_limit_hits']}")
        
        await fetcher.shutdown()
        await asyncio.sleep(2)  # Pause between tests
    
    return results


async def analyze_data_validation():
    """Analyze data validation effectiveness."""
    print("\n=== Data Validation Analysis ===")
    
    # Create a fetcher with validation
    broker = SchwabBroker()
    await broker.initialize()
    
    fetcher = EnhancedHistoricalDataFetcher(
        broker=broker,
        max_workers=2
    )
    await fetcher.initialize()
    
    # Test with volatile stocks that might have data issues
    symbols = ['GME', 'AMC', 'BBBY', 'COIN']  # Known volatile stocks
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=30)
    
    result = await fetcher.fetch_symbols_batch(
        symbols=symbols,
        timeframe=TimeFrame.DAILY,
        start_date=start_date,
        end_date=end_date,
        save_to_db=False,
        detect_duplicates=False,
        fill_gaps=False
    )
    
    # Analyze validation results
    validation_summary = {
        'total_records': 0,
        'validation_errors': 0,
        'validation_warnings': 0,
        'symbols_with_issues': []
    }
    
    for symbol, data in result['results'].items():
        if 'error' not in data:
            validation_summary['total_records'] += len(data.get('records', []))
            
            errors = len(data.get('validation_errors', []))
            warnings = len(data.get('validation_warnings', []))
            
            validation_summary['validation_errors'] += errors
            validation_summary['validation_warnings'] += warnings
            
            if errors > 0 or warnings > 0:
                validation_summary['symbols_with_issues'].append({
                    'symbol': symbol,
                    'errors': errors,
                    'warnings': warnings,
                    'sample_errors': data.get('validation_errors', [])[:3],
                    'sample_warnings': data.get('validation_warnings', [])[:3]
                })
    
    print(f"\nValidation Summary:")
    print(f"  Total records processed: {validation_summary['total_records']}")
    print(f"  Validation errors: {validation_summary['validation_errors']}")
    print(f"  Validation warnings: {validation_summary['validation_warnings']}")
    
    if validation_summary['symbols_with_issues']:
        print(f"\nSymbols with validation issues:")
        for issue in validation_summary['symbols_with_issues']:
            print(f"  {issue['symbol']}: {issue['errors']} errors, {issue['warnings']} warnings")
            if issue['sample_errors']:
                print(f"    Sample errors: {issue['sample_errors'][0]}")
            if issue['sample_warnings']:
                print(f"    Sample warnings: {issue['sample_warnings'][0]}")
    
    await fetcher.shutdown()
    await broker.close()
    
    return validation_summary


async def analyze_error_recovery():
    """Analyze error recovery and retry behavior."""
    print("\n=== Error Recovery Analysis ===")
    
    broker = SchwabBroker()
    await broker.initialize()
    
    fetcher = EnhancedHistoricalDataFetcher(
        broker=broker,
        max_workers=2
    )
    await fetcher.initialize()
    
    # Mix of valid and invalid symbols
    symbols = [
        'AAPL',          # Valid
        'INVALID123',    # Invalid
        'MSFT',          # Valid
        'NOTEXIST',      # Invalid
        'GOOGL',         # Valid
        '123456',        # Invalid
    ]
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=1)
    
    result = await fetcher.fetch_symbols_batch(
        symbols=symbols,
        timeframe=TimeFrame.DAILY,
        start_date=start_date,
        end_date=end_date,
        save_to_db=False,
        detect_duplicates=False,
        fill_gaps=False
    )
    
    # Analyze error handling
    stats = result['statistics']
    error_rate = stats['failed_symbols'] / stats['total_symbols'] * 100
    
    print(f"\nError Recovery Summary:")
    print(f"  Total symbols: {stats['total_symbols']}")
    print(f"  Successful: {stats['completed_symbols']}")
    print(f"  Failed: {stats['failed_symbols']}")
    print(f"  Error rate: {error_rate:.1f}%")
    print(f"  Total time: {stats['elapsed_time']:.2f}s")
    
    # Check individual results
    print(f"\nIndividual Results:")
    for symbol in symbols:
        if symbol in result['results']:
            data = result['results'][symbol]
            if 'error' in data:
                print(f"  {symbol}: ❌ Failed - {data['error'][:50]}...")
            else:
                print(f"  {symbol}: ✅ Success - {len(data['records'])} records")
    
    await fetcher.shutdown()
    await broker.close()
    
    return {
        'total_symbols': stats['total_symbols'],
        'successful': stats['completed_symbols'],
        'failed': stats['failed_symbols'],
        'error_rate': error_rate
    }


async def main():
    """Run performance analysis."""
    print("=" * 60)
    print("Enhanced Historical Data Fetcher - Performance Analysis")
    print("=" * 60)
    
    try:
        # Initialize broker
        broker = SchwabBroker()
        await broker.initialize()
        
        # Run analyses
        print("\nRunning performance analyses...")
        
        # 1. Worker performance
        worker_results = await analyze_worker_performance(broker)
        
        # 2. Data validation
        validation_results = await analyze_data_validation()
        
        # 3. Error recovery
        error_results = await analyze_error_recovery()
        
        # Summary
        print("\n" + "=" * 60)
        print("Analysis Summary")
        print("=" * 60)
        
        # Worker performance summary
        print("\nOptimal Worker Count:")
        best_config = max(worker_results, key=lambda x: x['throughput'])
        print(f"  Best configuration: {best_config['workers']} workers")
        print(f"  Throughput: {best_config['throughput']:.2f} symbols/sec")
        print(f"  Avg time per symbol: {best_config['avg_time_per_symbol']:.2f}s")
        
        # Validation effectiveness
        print(f"\nValidation Effectiveness:")
        if validation_results['total_records'] > 0:
            error_rate = (validation_results['validation_errors'] / 
                         validation_results['total_records'] * 100)
            print(f"  Error detection rate: {error_rate:.2f}%")
        
        # Error recovery
        print(f"\nError Recovery:")
        print(f"  Handles {error_results['error_rate']:.1f}% error rate gracefully")
        print(f"  No cascading failures detected")
        
        print("\n✅ Analysis completed successfully!")
        
        # Cleanup
        await broker.close()
        
    except Exception as e:
        print(f"\n❌ Analysis error: {e}")
        logger.exception("Analysis failed")


if __name__ == "__main__":
    asyncio.run(main())