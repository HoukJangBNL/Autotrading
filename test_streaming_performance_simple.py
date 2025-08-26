#!/usr/bin/env python3
"""
Simplified performance benchmark for streaming service.
"""

import asyncio
import time
import statistics
import psutil
import redis
from datetime import datetime, timezone
from typing import List
import numpy as np
import gc

# Configuration
REDIS_URL = "redis://:redis123@localhost:6379/0"


class SimplePerformanceBenchmark:
    """Simple performance benchmark for streaming."""
    
    def __init__(self):
        self.results = {}
        self.process = psutil.Process()
        
    async def run_benchmarks(self):
        """Run performance benchmarks."""
        print("=" * 60)
        print("Streaming Service Performance Benchmark (Simplified)")
        print("=" * 60)
        print()
        
        # Test 1: Throughput
        print("1. Testing Throughput...")
        await self.test_throughput()
        print()
        
        # Test 2: Latency
        print("2. Testing Processing Latency...")
        await self.test_latency()
        print()
        
        # Test 3: Concurrent Symbols
        print("3. Testing Concurrent Symbol Capacity...")
        await self.test_concurrent_symbols()
        print()
        
        # Summary
        self.print_summary()
        
    async def test_throughput(self):
        """Test maximum tick processing throughput."""
        from src.data.stream_processor import CandleAggregator
        
        # Create new processor
        processor = CandleAggregator()
        await processor.initialize()
        
        try:
            print("   🚀 Running throughput test...")
            
            # Test different batch sizes
            batch_sizes = [100, 1000, 5000]
            best_tps = 0
            
            for batch_size in batch_sizes:
                # Clear memory
                gc.collect()
                
                # Prepare quotes
                quotes = []
                for i in range(batch_size):
                    quotes.append({
                        'symbol': f'TEST{i % 10}',
                        'timestamp': datetime.now(timezone.utc),
                        'last': 100.0 + (i % 100),
                        'volume': 1000
                    })
                
                # Measure processing time
                start_time = time.perf_counter()
                start_memory = self.process.memory_info().rss / 1024 / 1024
                
                # Process all quotes
                for quote in quotes:
                    await processor.process_quote(quote)
                
                # Calculate metrics
                duration = time.perf_counter() - start_time
                tps = batch_size / duration
                end_memory = self.process.memory_info().rss / 1024 / 1024
                memory_increase = end_memory - start_memory
                
                print(f"   📊 Batch {batch_size:,} ticks:")
                print(f"      Duration: {duration:.3f}s")
                print(f"      Throughput: {tps:,.0f} ticks/sec")
                print(f"      Memory increase: {memory_increase:.1f} MB")
                
                if tps > best_tps:
                    best_tps = tps
                    self.results['best_tps'] = tps
                    self.results['best_batch_size'] = batch_size
                    
        finally:
            # Clean shutdown
            await processor.shutdown()
            
    async def test_latency(self):
        """Test processing latency."""
        from src.data.stream_processor import CandleAggregator
        
        processor = CandleAggregator()
        await processor.initialize()
        
        try:
            print("   🚀 Measuring processing latency...")
            
            latencies = []
            
            # Process 100 ticks and measure time
            for i in range(100):
                quote = {
                    'symbol': 'LATENCY_TEST',
                    'timestamp': datetime.now(timezone.utc),
                    'last': 100.0 + i,
                    'volume': 1000
                }
                
                start = time.perf_counter()
                await processor.process_quote(quote)
                end = time.perf_counter()
                
                latency_ms = (end - start) * 1000
                latencies.append(latency_ms)
            
            # Calculate statistics
            self.results['latencies'] = latencies
            self.results['avg_latency'] = statistics.mean(latencies)
            self.results['median_latency'] = statistics.median(latencies)
            self.results['p95_latency'] = np.percentile(latencies, 95)
            self.results['max_latency'] = max(latencies)
            
            print(f"   📊 Processing Latency (ms):")
            print(f"      Average: {self.results['avg_latency']:.2f}")
            print(f"      Median: {self.results['median_latency']:.2f}")
            print(f"      95th percentile: {self.results['p95_latency']:.2f}")
            print(f"      Maximum: {self.results['max_latency']:.2f}")
            
        finally:
            await processor.shutdown()
            
    async def test_concurrent_symbols(self):
        """Test maximum concurrent symbols."""
        from src.data.stream_processor import CandleAggregator
        
        processor = CandleAggregator()
        await processor.initialize()
        
        try:
            print("   🚀 Testing concurrent symbol capacity...")
            
            symbol_counts = [10, 50, 100, 200]
            baseline_tps = None
            max_symbols = 0
            
            for symbol_count in symbol_counts:
                gc.collect()
                
                # Create symbols
                symbols = [f'SYM_{i:04d}' for i in range(symbol_count)]
                
                # Process 1000 ticks distributed across symbols
                tick_count = 1000
                start_time = time.perf_counter()
                
                for i in range(tick_count):
                    symbol = symbols[i % symbol_count]
                    quote = {
                        'symbol': symbol,
                        'timestamp': datetime.now(timezone.utc),
                        'last': 100.0 + (i % 100),
                        'volume': 1000
                    }
                    await processor.process_quote(quote)
                
                # Calculate TPS
                duration = time.perf_counter() - start_time
                tps = tick_count / duration
                
                # Set baseline
                if baseline_tps is None:
                    baseline_tps = tps
                
                # Check degradation
                degradation = ((baseline_tps - tps) / baseline_tps) * 100 if baseline_tps > 0 else 0
                
                print(f"   📊 {symbol_count} symbols:")
                print(f"      TPS: {tps:,.0f}")
                print(f"      Degradation: {degradation:.1f}%")
                
                # Update max symbols if degradation is acceptable (<20%)
                if degradation < 20:
                    max_symbols = symbol_count
                else:
                    break
            
            self.results['max_concurrent_symbols'] = max_symbols
            
        finally:
            await processor.shutdown()
            
    def print_summary(self):
        """Print performance summary."""
        print("=" * 60)
        print("Performance Summary")
        print("=" * 60)
        
        # Throughput
        print("\n📊 Throughput:")
        if 'best_tps' in self.results:
            print(f"   Best TPS: {self.results['best_tps']:,.0f} ticks/second")
            print(f"   Optimal batch size: {self.results['best_batch_size']:,}")
            
            if self.results['best_tps'] > 5000:
                print("   Rating: ✅ Excellent (>5K TPS)")
            elif self.results['best_tps'] > 1000:
                print("   Rating: ✅ Good (>1K TPS)")
            elif self.results['best_tps'] > 500:
                print("   Rating: ⚠️  Moderate (>500 TPS)")
            else:
                print("   Rating: ❌ Low (<500 TPS)")
        
        # Latency
        print("\n📊 Processing Latency:")
        if 'avg_latency' in self.results:
            print(f"   Average: {self.results['avg_latency']:.2f} ms")
            print(f"   Median: {self.results['median_latency']:.2f} ms")
            print(f"   95th percentile: {self.results['p95_latency']:.2f} ms")
            
            if self.results['avg_latency'] < 5:
                print("   Rating: ✅ Excellent (<5ms)")
            elif self.results['avg_latency'] < 20:
                print("   Rating: ✅ Good (<20ms)")
            elif self.results['avg_latency'] < 50:
                print("   Rating: ⚠️  Moderate (<50ms)")
            else:
                print("   Rating: ❌ High (>50ms)")
        
        # Concurrent symbols
        print("\n📊 Concurrent Symbol Capacity:")
        if 'max_concurrent_symbols' in self.results:
            print(f"   Maximum: {self.results['max_concurrent_symbols']} symbols")
            
            if self.results['max_concurrent_symbols'] >= 100:
                print("   Rating: ✅ High capacity (100+ symbols)")
            elif self.results['max_concurrent_symbols'] >= 50:
                print("   Rating: ✅ Good capacity (50+ symbols)")
            else:
                print("   Rating: ⚠️  Limited capacity (<50 symbols)")
        
        # Overall assessment
        print("\n" + "=" * 60)
        print("Overall Performance Assessment:")
        
        excellent_count = 0
        if self.results.get('best_tps', 0) > 1000:
            excellent_count += 1
        if self.results.get('avg_latency', 100) < 20:
            excellent_count += 1
        if self.results.get('max_concurrent_symbols', 0) >= 50:
            excellent_count += 1
        
        if excellent_count == 3:
            print("✅ EXCELLENT - Production ready with high performance")
        elif excellent_count >= 2:
            print("✅ GOOD - Production ready with good performance")
        elif excellent_count >= 1:
            print("⚠️  MODERATE - May need optimization for production")
        else:
            print("❌ NEEDS IMPROVEMENT - Significant optimization required")
        
        print("=" * 60)


async def main():
    """Run simplified performance benchmark."""
    print("Starting simplified performance benchmark...")
    print("This will take about 2-3 minutes.")
    print()
    
    # Check Redis
    try:
        r = redis.from_url(REDIS_URL)
        r.ping()
        
        # Clear any lingering connections
        info = r.info()
        connected_clients = info.get('connected_clients', 0)
        print(f"✓ Redis is running (connected clients: {connected_clients})")
        
        r.close()
    except Exception as e:
        print(f"❌ Redis error: {e}")
        return
    
    # Run benchmark
    benchmark = SimplePerformanceBenchmark()
    await benchmark.run_benchmarks()


if __name__ == "__main__":
    asyncio.run(main())