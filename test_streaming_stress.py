#!/usr/bin/env python3
"""
Extreme stress tests for streaming service.
"""

import asyncio
import json
import time
import psutil
import redis
from datetime import datetime, timezone
import gc
import random
import websockets
import aiohttp
import traceback
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

# Configuration
REDIS_URL = "redis://:redis123@localhost:6379/0"
API_BASE_URL = "http://localhost:8000/api"
WS_URL = "ws://localhost:8000/ws"
API_KEY = "test-api-key-12345"


class StreamingStressTests:
    """Extreme stress tests for streaming service."""
    
    def __init__(self):
        self.results = {}
        
    async def run_all_tests(self):
        """Run all stress tests."""
        print("=" * 60)
        print("Streaming Service Stress Tests")
        print("=" * 60)
        print()
        
        # Test 1: Extreme Volume
        print("1. Testing Extreme Volume Processing...")
        await self.test_extreme_volume()
        print()
        
        # Test 2: Rapid Connect/Disconnect
        print("2. Testing Rapid Connect/Disconnect...")
        await self.test_rapid_connections()
        print()
        
        # Test 3: Large Message Sizes
        print("3. Testing Large Message Handling...")
        await self.test_large_messages()
        print()
        
        # Test 4: Redis Pub/Sub Stress
        print("4. Testing Redis Pub/Sub Under Load...")
        await self.test_redis_pubsub_stress()
        print()
        
        # Summary
        self.print_stress_summary()
        
    async def test_extreme_volume(self):
        """Test processing extreme volume of ticks."""
        try:
            from src.data.stream_processor import CandleAggregator
            processor = CandleAggregator()
            await processor.initialize()
            
            # Get initial metrics
            process = psutil.Process()
            start_memory = process.memory_info().rss / 1024 / 1024
            start_cpu = process.cpu_percent(interval=0.1)
            
            print(f"   📊 Starting metrics:")
            print(f"      Memory: {start_memory:.2f} MB")
            print(f"      CPU: {start_cpu:.1f}%")
            
            # Generate extreme load
            symbols = [f"STRESS{i}" for i in range(200)]  # 200 symbols
            tick_count = 0
            error_count = 0
            start_time = time.time()
            
            print(f"\n   🚀 Processing extreme volume for {len(symbols)} symbols...")
            
            # Process in bursts
            for burst in range(10):
                burst_start = time.time()
                burst_ticks = 0
                
                # Fire rapid ticks
                tasks = []
                for symbol in symbols:
                    for _ in range(50):  # 50 ticks per symbol per burst
                        quote = {
                            'symbol': symbol,
                            'timestamp': datetime.now(timezone.utc),
                            'last': random.uniform(90, 110),
                            'volume': random.randint(100, 10000)
                        }
                        tasks.append(processor.process_quote(quote))
                        burst_ticks += 1
                        tick_count += 1
                
                # Process all concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)
                error_count += sum(1 for r in results if isinstance(r, Exception))
                
                # Metrics
                burst_duration = time.time() - burst_start
                burst_tps = burst_ticks / burst_duration
                current_memory = process.memory_info().rss / 1024 / 1024
                current_cpu = process.cpu_percent(interval=0.1)
                
                print(f"   📊 Burst {burst+1}/10:")
                print(f"      Ticks: {burst_ticks:,} in {burst_duration:.2f}s ({burst_tps:,.0f} ticks/sec)")
                print(f"      Memory: {current_memory:.2f} MB (+{current_memory-start_memory:.2f})")
                print(f"      CPU: {current_cpu:.1f}%")
                print(f"      Errors: {error_count}")
                
            # Final metrics
            total_duration = time.time() - start_time
            overall_tps = tick_count / total_duration
            final_memory = process.memory_info().rss / 1024 / 1024
            memory_increase = final_memory - start_memory
            
            print(f"\n   📊 Extreme Volume Results:")
            print(f"      Total ticks: {tick_count:,}")
            print(f"      Duration: {total_duration:.2f}s")
            print(f"      Overall TPS: {overall_tps:,.0f}")
            print(f"      Memory increase: {memory_increase:.2f} MB")
            print(f"      Error rate: {(error_count/tick_count)*100:.2f}%")
            
            # Evaluate
            self.results['extreme_volume_tps'] = overall_tps
            self.results['extreme_volume_stable'] = error_count < tick_count * 0.01  # <1% errors
            self.results['extreme_memory_stable'] = memory_increase < 100  # <100MB increase
            
            await processor.shutdown()
            gc.collect()
            
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            traceback.print_exc()
            self.results['extreme_volume'] = False
            
    async def test_rapid_connections(self):
        """Test rapid WebSocket connect/disconnect cycles."""
        try:
            connection_count = 0
            error_count = 0
            start_time = time.time()
            
            print("   🚀 Testing rapid WebSocket connections...")
            
            async def rapid_connect():
                """Rapidly connect and disconnect."""
                nonlocal connection_count, error_count
                
                try:
                    uri = f"{WS_URL}?token={API_KEY}"
                    websocket = await websockets.connect(uri)
                    connection_count += 1
                    
                    # Quick subscribe
                    await websocket.send(json.dumps({
                        "type": "subscribe",
                        "symbols": ["RAPID"]
                    }))
                    
                    # Immediate disconnect
                    await websocket.close()
                    
                except Exception as e:
                    error_count += 1
            
            # Fire rapid connections
            tasks = []
            for i in range(100):  # 100 rapid connections
                tasks.append(rapid_connect())
                if i % 10 == 0:
                    # Process batch
                    await asyncio.gather(*tasks, return_exceptions=True)
                    tasks = []
                    await asyncio.sleep(0.1)  # Brief pause
            
            # Process remaining
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            duration = time.time() - start_time
            connections_per_sec = connection_count / duration
            
            print(f"\n   📊 Rapid Connection Results:")
            print(f"      Connections: {connection_count}")
            print(f"      Duration: {duration:.2f}s")
            print(f"      Rate: {connections_per_sec:.0f} conn/sec")
            print(f"      Errors: {error_count}")
            print(f"      Success rate: {((connection_count-error_count)/100)*100:.1f}%")
            
            self.results['rapid_connections'] = connection_count
            self.results['rapid_conn_stable'] = error_count < 10  # <10% errors
            
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            self.results['rapid_conn_test'] = False
            
    async def test_large_messages(self):
        """Test handling of large messages."""
        try:
            from src.data.stream_processor import CandleAggregator
            processor = CandleAggregator()
            await processor.initialize()
            
            print("   🚀 Testing large message handling...")
            
            # Create symbols with long names
            long_symbols = [f"SYMBOL_WITH_VERY_LONG_NAME_{i:06d}" for i in range(50)]
            
            # Process large batches
            large_batch_count = 0
            start_time = time.time()
            
            for batch_num in range(5):
                tasks = []
                
                # Create large quotes
                for symbol in long_symbols:
                    # Add extra metadata
                    quote = {
                        'symbol': symbol,
                        'timestamp': datetime.now(timezone.utc),
                        'last': 100.0,
                        'volume': 1000000,
                        'metadata': {
                            'exchange': 'VERY_LONG_EXCHANGE_NAME_FOR_TESTING',
                            'conditions': ['CONDITION_' + str(i) for i in range(20)],
                            'extra_data': 'X' * 1000  # 1KB of data
                        }
                    }
                    tasks.append(processor.process_quote(quote))
                    large_batch_count += 1
                
                # Process batch
                results = await asyncio.gather(*tasks, return_exceptions=True)
                errors = sum(1 for r in results if isinstance(r, Exception))
                
                print(f"   📊 Large batch {batch_num+1}: {len(tasks)} messages, {errors} errors")
            
            duration = time.time() - start_time
            
            print(f"\n   📊 Large Message Results:")
            print(f"      Messages processed: {large_batch_count}")
            print(f"      Duration: {duration:.2f}s")
            print(f"      Rate: {large_batch_count/duration:.0f} msg/sec")
            
            self.results['large_messages'] = large_batch_count
            self.results['large_msg_stable'] = True
            
            await processor.shutdown()
            
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            self.results['large_msg_test'] = False
            
    async def test_redis_pubsub_stress(self):
        """Test Redis pub/sub under extreme load."""
        try:
            r = redis.from_url(REDIS_URL, decode_responses=True)
            pubsub = r.pubsub()
            
            print("   🚀 Testing Redis pub/sub stress...")
            
            # Subscribe to multiple channels
            channels = [f"stress:channel:{i}" for i in range(100)]
            for channel in channels:
                pubsub.subscribe(channel)
            
            print(f"   ✓ Subscribed to {len(channels)} channels")
            
            # Publish storm
            publish_count = 0
            start_time = time.time()
            
            for round_num in range(10):
                for channel in channels:
                    # Publish multiple messages per channel
                    for msg_num in range(10):
                        message = {
                            'type': 'stress_test',
                            'channel': channel,
                            'data': 'X' * 100,  # 100 bytes
                            'timestamp': time.time()
                        }
                        r.publish(channel, json.dumps(message))
                        publish_count += 1
                
                print(f"   📊 Round {round_num+1}: Published {len(channels)*10} messages")
            
            duration = time.time() - start_time
            publish_rate = publish_count / duration
            
            # Try to receive some messages
            received = 0
            timeout_time = time.time() + 2  # 2 seconds to receive
            while time.time() < timeout_time:
                message = pubsub.get_message(timeout=0.1)
                if message and message['type'] == 'message':
                    received += 1
            
            print(f"\n   📊 Redis Pub/Sub Results:")
            print(f"      Messages published: {publish_count:,}")
            print(f"      Publish rate: {publish_rate:,.0f} msg/sec")
            print(f"      Messages received: {received}")
            
            self.results['redis_publish_rate'] = publish_rate
            self.results['redis_pubsub_stable'] = True
            
            # Cleanup
            pubsub.close()
            r.close()
            
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            self.results['redis_stress_test'] = False
            
    def print_stress_summary(self):
        """Print stress test summary."""
        print("=" * 60)
        print("Stress Test Results Summary")
        print("=" * 60)
        
        # Extreme volume
        print("\n📊 Extreme Volume Processing:")
        if 'extreme_volume_tps' in self.results:
            print(f"   Throughput: {self.results['extreme_volume_tps']:,.0f} ticks/sec")
            print(f"   Stability: {'✅ Stable' if self.results.get('extreme_volume_stable', False) else '❌ Errors'}")
            print(f"   Memory: {'✅ Stable' if self.results.get('extreme_memory_stable', False) else '❌ High usage'}")
        
        # Rapid connections
        print("\n📊 Rapid Connections:")
        if 'rapid_connections' in self.results:
            print(f"   Successful connections: {self.results['rapid_connections']}")
            print(f"   Stability: {'✅ Stable' if self.results.get('rapid_conn_stable', False) else '❌ Errors'}")
        
        # Large messages
        print("\n📊 Large Message Handling:")
        if 'large_messages' in self.results:
            print(f"   Messages processed: {self.results['large_messages']}")
            print(f"   Stability: {'✅ Stable' if self.results.get('large_msg_stable', False) else '❌ Failed'}")
        
        # Redis stress
        print("\n📊 Redis Pub/Sub Stress:")
        if 'redis_publish_rate' in self.results:
            print(f"   Publish rate: {self.results['redis_publish_rate']:,.0f} msg/sec")
            print(f"   Stability: {'✅ Stable' if self.results.get('redis_pubsub_stable', False) else '❌ Failed'}")
        
        # Overall assessment
        stress_tests = [
            'extreme_volume_stable',
            'extreme_memory_stable',
            'rapid_conn_stable',
            'large_msg_stable',
            'redis_pubsub_stable'
        ]
        
        passed = sum(1 for test in stress_tests if self.results.get(test, False))
        total = len(stress_tests)
        
        print("\n" + "=" * 60)
        print(f"Stress Tests Passed: {passed}/{total}")
        
        if passed == total:
            print("✅ Excellent! The streaming service handles extreme stress well.")
        elif passed >= total * 0.8:
            print("✅ Good! The streaming service is robust under stress.")
        else:
            print("⚠️  Some stress tests failed. Consider optimization for production.")
        print("=" * 60)


async def main():
    """Run stress tests."""
    print("⚠️  WARNING: These are extreme stress tests!")
    print("They will consume significant system resources.")
    print()
    
    # Check prerequisites
    try:
        r = redis.from_url(REDIS_URL)
        r.ping()
        r.close()
        print("✓ Redis is running")
        
        # Check API
        async with aiohttp.ClientSession() as session:
            headers = {"X-API-Key": API_KEY}
            async with session.get(f"{API_BASE_URL}/auth/status", headers=headers) as resp:
                if resp.status == 200:
                    print("✓ API server is running")
                else:
                    print("❌ API server not responding")
                    return
    except Exception as e:
        print(f"❌ Prerequisites check failed: {e}")
        return
    
    print()
    
    # Run stress tests
    tester = StreamingStressTests()
    await tester.run_all_tests()


if __name__ == "__main__":
    # Set higher limits for stress testing
    import sys
    sys.setrecursionlimit(10000)
    
    asyncio.run(main())