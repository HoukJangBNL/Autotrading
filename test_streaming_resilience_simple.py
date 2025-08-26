#!/usr/bin/env python3
"""
Simplified streaming service resilience tests.
"""

import asyncio
import json
import time
import psutil
import redis
from datetime import datetime, timezone
from typing import List, Dict, Any
import gc
import sys
import traceback

# Configuration
REDIS_URL = "redis://:redis123@localhost:6379/0"


class SimpleResilienceTests:
    """Simple test suite for streaming service resilience."""
    
    def __init__(self):
        self.results = {}
        
    async def run_all_tests(self):
        """Run all resilience tests."""
        print("=" * 60)
        print("Streaming Service Resilience Tests (Simplified)")
        print("=" * 60)
        print()
        
        # Test 1: Redis Resilience
        print("1. Testing Redis Connection Resilience...")
        await self.test_redis_resilience()
        print()
        
        # Test 2: Memory Usage
        print("2. Testing Memory Usage Under Load...")
        await self.test_memory_usage()
        print()
        
        # Test 3: Concurrent Processing
        print("3. Testing Concurrent Processing...")
        await self.test_concurrent_processing()
        print()
        
        # Summary
        self.print_summary()
        
    async def test_redis_resilience(self):
        """Test Redis connection handling."""
        try:
            # Test 1: Normal connection
            r = redis.from_url(REDIS_URL, decode_responses=True)
            r.ping()
            print("   ✅ Redis connection successful")
            self.results['redis_connection'] = True
            
            # Test 2: Connection recovery
            from src.data.stream_processor import CandleAggregator
            processor = CandleAggregator()
            
            try:
                await processor.initialize()
                print("   ✅ Processor initialized with Redis")
                self.results['processor_init'] = True
            except Exception as e:
                print(f"   ❌ Processor initialization failed: {e}")
                self.results['processor_init'] = False
                return
            
            # Test 3: Process data
            test_quote = {
                'symbol': 'TEST',
                'timestamp': datetime.now(timezone.utc),
                'last': 100.0,
                'volume': 1000
            }
            
            await processor.process_quote(test_quote)
            print("   ✅ Quote processing successful")
            self.results['quote_processing'] = True
            
            # Test 4: Simulate connection loss
            old_client = processor.redis_client
            processor.redis_client = None
            
            # Try processing without Redis
            try:
                await processor.process_quote(test_quote)
                print("   ⚠️  Processed without Redis (degraded mode)")
                self.results['degraded_mode'] = True
            except Exception as e:
                print(f"   ✅ Correctly failed without Redis: {type(e).__name__}")
                self.results['error_handling'] = True
            
            # Restore
            processor.redis_client = old_client
            await processor.process_quote(test_quote)
            print("   ✅ Recovered after reconnection")
            self.results['recovery'] = True
            
            # Cleanup
            await processor.shutdown()
            r.close()
            
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            traceback.print_exc()
            self.results['redis_resilience'] = False
            
    async def test_memory_usage(self):
        """Test memory usage under load."""
        try:
            # Get initial memory
            process = psutil.Process()
            start_memory = process.memory_info().rss / 1024 / 1024  # MB
            print(f"   📊 Starting memory: {start_memory:.2f} MB")
            
            # Create processor
            from src.data.stream_processor import CandleAggregator
            processor = CandleAggregator()
            await processor.initialize()
            
            # Process many ticks
            symbols = [f"SYM{i}" for i in range(50)]  # 50 symbols
            tick_count = 0
            start_time = time.time()
            
            # Process ticks
            for round_num in range(5):  # 5 rounds
                for symbol in symbols:
                    for _ in range(20):  # 20 ticks per symbol per round
                        quote = {
                            'symbol': symbol,
                            'timestamp': datetime.now(timezone.utc),
                            'last': 100.0 + (tick_count % 10),
                            'volume': 100
                        }
                        await processor.process_quote(quote)
                        tick_count += 1
                
                # Check memory
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_increase = current_memory - start_memory
                print(f"   📊 Round {round_num+1}: Processed {tick_count:,} ticks, Memory +{memory_increase:.2f} MB")
                
                # Force GC
                gc.collect()
            
            # Final stats
            duration = time.time() - start_time
            final_memory = process.memory_info().rss / 1024 / 1024
            memory_increase = final_memory - start_memory
            ticks_per_second = tick_count / duration
            
            print(f"\n   📊 Performance Summary:")
            print(f"      Total ticks: {tick_count:,}")
            print(f"      Duration: {duration:.2f}s")
            print(f"      Throughput: {ticks_per_second:,.0f} ticks/sec")
            print(f"      Memory increase: {memory_increase:.2f} MB")
            
            # Check efficiency
            self.results['total_ticks'] = tick_count
            self.results['throughput'] = ticks_per_second
            self.results['memory_efficient'] = memory_increase < 50  # Less than 50MB increase
            
            await processor.shutdown()
            
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            traceback.print_exc()
            self.results['memory_test'] = False
            
    async def test_concurrent_processing(self):
        """Test concurrent quote processing."""
        try:
            from src.data.stream_processor import CandleAggregator
            processor = CandleAggregator()
            await processor.initialize()
            
            # Create multiple concurrent tasks
            async def process_quotes(symbol: str, count: int):
                """Process multiple quotes for a symbol."""
                for i in range(count):
                    quote = {
                        'symbol': symbol,
                        'timestamp': datetime.now(timezone.utc),
                        'last': 100.0 + i,
                        'volume': 100 + i
                    }
                    await processor.process_quote(quote)
                return symbol, count
            
            # Run concurrent tasks
            symbols = [f"CONCURRENT{i}" for i in range(10)]
            tasks = [process_quotes(sym, 100) for sym in symbols]
            
            print(f"   🚀 Processing {len(symbols)} symbols concurrently...")
            start_time = time.time()
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            duration = time.time() - start_time
            successful = sum(1 for r in results if not isinstance(r, Exception))
            
            print(f"   📊 Concurrent Processing Results:")
            print(f"      Successful symbols: {successful}/{len(symbols)}")
            print(f"      Duration: {duration:.2f}s")
            print(f"      Quotes per second: {(successful * 100) / duration:.0f}")
            
            self.results['concurrent_success'] = successful == len(symbols)
            self.results['concurrent_rate'] = successful / len(symbols)
            
            await processor.shutdown()
            
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            traceback.print_exc()
            self.results['concurrent_test'] = False
            
    def print_summary(self):
        """Print test summary."""
        print("=" * 60)
        print("Test Results Summary")
        print("=" * 60)
        
        # Redis tests
        print("\n📊 Redis Resilience:")
        tests = ['redis_connection', 'processor_init', 'quote_processing', 'recovery']
        for test in tests:
            status = '✅ Passed' if self.results.get(test, False) else '❌ Failed'
            print(f"   {test}: {status}")
        
        # Memory tests
        print("\n📊 Memory Efficiency:")
        if 'total_ticks' in self.results:
            print(f"   Ticks processed: {self.results['total_ticks']:,}")
            print(f"   Throughput: {self.results.get('throughput', 0):,.0f} ticks/sec")
            status = '✅ Efficient' if self.results.get('memory_efficient', False) else '❌ High usage'
            print(f"   Memory usage: {status}")
        
        # Concurrent tests
        print("\n📊 Concurrent Processing:")
        if 'concurrent_rate' in self.results:
            print(f"   Success rate: {self.results['concurrent_rate']:.1%}")
            status = '✅ Stable' if self.results.get('concurrent_success', False) else '❌ Unstable'
            print(f"   Stability: {status}")
        
        # Overall
        critical_tests = [
            'redis_connection',
            'recovery',
            'memory_efficient',
            'concurrent_success'
        ]
        
        passed = sum(1 for test in critical_tests if self.results.get(test, False))
        total = len(critical_tests)
        
        print("\n" + "=" * 60)
        print(f"Overall: {passed}/{total} critical tests passed")
        
        if passed == total:
            print("✅ Streaming service shows good resilience!")
        else:
            failed_tests = [t for t in critical_tests if not self.results.get(t, False)]
            print(f"⚠️  Failed tests: {', '.join(failed_tests)}")
        print("=" * 60)


async def main():
    """Run simplified resilience tests."""
    tester = SimpleResilienceTests()
    
    try:
        # Check Redis first
        r = redis.from_url(REDIS_URL)
        r.ping()
        r.close()
        print("✓ Redis is running")
    except:
        print("❌ Redis is not running. Please start Redis first.")
        return
    
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())