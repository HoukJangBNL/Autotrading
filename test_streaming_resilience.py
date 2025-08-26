#!/usr/bin/env python3
"""
Streaming service resilience tests.

Tests:
1. Redis connection failure and recovery
2. WebSocket disconnection and automatic reconnection
3. High volume data processing and memory usage
4. Multiple concurrent client connections
"""

import asyncio
import json
import time
import psutil
import redis
import websockets
from datetime import datetime, timezone
from typing import List, Dict, Any
import aiohttp
from unittest.mock import patch, MagicMock
import gc

# Configuration
API_BASE_URL = "http://localhost:8000/api"
WS_URL = "ws://localhost:8000/ws"
API_KEY = "test-api-key-12345"
REDIS_URL = "redis://:redis123@localhost:6379/0"


class StreamingResilienceTests:
    """Test suite for streaming service resilience."""
    
    def __init__(self):
        self.results = {}
        self.start_memory = None
        
    async def run_all_tests(self):
        """Run all resilience tests."""
        print("=" * 60)
        print("Streaming Service Resilience Tests")
        print("=" * 60)
        print()
        
        # Test 1: Redis Connection Failure Recovery
        print("1. Testing Redis Connection Failure Recovery...")
        await self.test_redis_connection_failure_recovery()
        print()
        
        # Test 2: WebSocket Reconnection
        print("2. Testing WebSocket Automatic Reconnection...")
        await self.test_websocket_reconnection()
        print()
        
        # Test 3: High Volume Memory Usage
        print("3. Testing High Volume Data Processing...")
        await self.test_high_volume_memory_usage()
        print()
        
        # Test 4: Multiple Concurrent Clients
        print("4. Testing Multiple Concurrent Clients...")
        await self.test_multiple_concurrent_clients()
        print()
        
        # Summary
        self.print_test_summary()
        
    async def test_redis_connection_failure_recovery(self):
        """Test Redis connection failure and recovery."""
        try:
            # Start stream processor
            from src.data.stream_processor import CandleAggregator
            processor = CandleAggregator()
            await processor.initialize()
            
            print("   ✓ Stream processor initialized")
            
            # Test normal operation
            test_quote = {
                'symbol': 'TEST',
                'timestamp': datetime.now(timezone.utc),
                'last': 100.0,
                'volume': 1000
            }
            
            await processor.process_quote(test_quote)
            print("   ✓ Normal operation successful")
            
            # Simulate Redis connection failure
            original_redis = processor.redis_client
            processor.redis_client = None
            
            print("   ⚠️  Simulating Redis connection failure...")
            
            # Try to process quote with failed connection
            try:
                await processor.process_quote(test_quote)
                print("   ❌ Should have handled Redis failure")
                self.results['redis_failure_handling'] = False
            except Exception as e:
                print(f"   ✓ Handled Redis failure gracefully: {type(e).__name__}")
                self.results['redis_failure_handling'] = True
            
            # Restore connection
            processor.redis_client = original_redis
            
            # Test recovery
            await processor.process_quote(test_quote)
            print("   ✓ Recovered after Redis reconnection")
            self.results['redis_recovery'] = True
            
            # Cleanup
            await processor.shutdown()
            
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            self.results['redis_resilience'] = False
        
    async def test_websocket_reconnection(self):
        """Test WebSocket automatic reconnection."""
        reconnection_count = 0
        messages_received = []
        
        async def connect_with_retry(max_retries=3):
            nonlocal reconnection_count
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    uri = f"{WS_URL}?token={API_KEY}"
                    websocket = await websockets.connect(uri)
                    print(f"   ✓ WebSocket connected (attempt {retry_count + 1})")
                    
                    # Subscribe to test symbols
                    await websocket.send(json.dumps({
                        "type": "subscribe",
                        "symbols": ["TEST1", "TEST2"]
                    }))
                    
                    # Handle messages
                    while True:
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                            data = json.loads(message)
                            messages_received.append(data)
                            
                            if data['type'] == 'candle_update':
                                print(f"   ✓ Received update: {data['symbol']}")
                                
                        except asyncio.TimeoutError:
                            # No message received, continue
                            pass
                        except websockets.exceptions.ConnectionClosed:
                            print("   ⚠️  WebSocket connection lost")
                            break
                            
                except Exception as e:
                    print(f"   ⚠️  Connection failed: {e}")
                    retry_count += 1
                    reconnection_count += 1
                    
                    if retry_count < max_retries:
                        wait_time = min(2 ** retry_count, 10)  # Exponential backoff
                        print(f"   🔄 Retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                    else:
                        print("   ❌ Max retries reached")
                        break
                        
            return reconnection_count > 0
            
        try:
            # Test reconnection
            reconnected = await connect_with_retry()
            
            self.results['websocket_reconnection'] = reconnected
            self.results['websocket_messages'] = len(messages_received)
            
            print(f"   📊 Reconnection attempts: {reconnection_count}")
            print(f"   📊 Messages received: {len(messages_received)}")
            
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            self.results['websocket_resilience'] = False
            
    async def test_high_volume_memory_usage(self):
        """Test high volume data processing and memory usage."""
        try:
            # Get process info
            process = psutil.Process()
            self.start_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            print(f"   📊 Starting memory: {self.start_memory:.2f} MB")
            
            # Create processor
            from src.data.stream_processor import CandleAggregator
            processor = CandleAggregator()
            await processor.initialize()
            
            # Generate high volume of ticks
            symbols = [f"TEST{i}" for i in range(100)]  # 100 symbols
            tick_count = 0
            start_time = time.time()
            
            print(f"   🚀 Processing ticks for {len(symbols)} symbols...")
            
            # Process 1000 ticks per symbol
            for _ in range(10):  # 10 rounds
                for symbol in symbols:
                    for i in range(100):  # 100 ticks per round
                        quote = {
                            'symbol': symbol,
                            'timestamp': datetime.now(timezone.utc),
                            'last': 100.0 + (i % 10),
                            'volume': 100 + i
                        }
                        await processor.process_quote(quote)
                        tick_count += 1
                        
                # Check memory every round
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_increase = current_memory - self.start_memory
                print(f"   📊 Round {_+1}/10: Memory +{memory_increase:.2f} MB, Ticks: {tick_count:,}")
                
                # Force garbage collection
                gc.collect()
                
            # Final metrics
            end_time = time.time()
            duration = end_time - start_time
            final_memory = process.memory_info().rss / 1024 / 1024
            memory_increase = final_memory - self.start_memory
            ticks_per_second = tick_count / duration
            
            print(f"\n   📊 Performance Metrics:")
            print(f"      Total ticks processed: {tick_count:,}")
            print(f"      Duration: {duration:.2f} seconds")
            print(f"      Throughput: {ticks_per_second:,.0f} ticks/second")
            print(f"      Memory increase: {memory_increase:.2f} MB")
            print(f"      Memory per 1K ticks: {memory_increase / (tick_count/1000):.2f} MB")
            
            # Check if memory usage is reasonable
            memory_per_1k_ticks = memory_increase / (tick_count / 1000)
            self.results['high_volume_processed'] = tick_count
            self.results['throughput_tps'] = ticks_per_second
            self.results['memory_efficiency'] = memory_per_1k_ticks < 1.0  # Less than 1MB per 1K ticks
            
            # Cleanup
            await processor.shutdown()
            
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            self.results['high_volume_test'] = False
            
    async def test_multiple_concurrent_clients(self):
        """Test multiple concurrent WebSocket clients."""
        num_clients = 10
        clients = []
        client_messages = {i: [] for i in range(num_clients)}
        
        async def create_client(client_id: int):
            """Create and manage a WebSocket client."""
            try:
                uri = f"{WS_URL}?token={API_KEY}"
                websocket = await websockets.connect(uri)
                
                # Subscribe to symbols
                await websocket.send(json.dumps({
                    "type": "subscribe",
                    "symbols": [f"CLIENT{client_id}"]
                }))
                
                # Receive messages
                start_time = time.time()
                while time.time() - start_time < 10:  # Run for 10 seconds
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        client_messages[client_id].append(data)
                    except asyncio.TimeoutError:
                        continue
                        
                await websocket.close()
                return True
                
            except Exception as e:
                print(f"   ⚠️  Client {client_id} error: {e}")
                return False
                
        try:
            print(f"   🚀 Starting {num_clients} concurrent clients...")
            
            # Start all clients concurrently
            start_time = time.time()
            tasks = [create_client(i) for i in range(num_clients)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            duration = time.time() - start_time
            
            # Analyze results
            successful_clients = sum(1 for r in results if r is True)
            total_messages = sum(len(messages) for messages in client_messages.values())
            
            print(f"\n   📊 Concurrent Client Results:")
            print(f"      Successful clients: {successful_clients}/{num_clients}")
            print(f"      Total messages: {total_messages}")
            print(f"      Duration: {duration:.2f} seconds")
            print(f"      Messages per client: {total_messages/num_clients:.1f}")
            
            # Check server stability
            self.results['concurrent_clients'] = successful_clients
            self.results['concurrent_success_rate'] = successful_clients / num_clients
            self.results['concurrent_stable'] = successful_clients >= num_clients * 0.9  # 90% success
            
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            self.results['concurrent_test'] = False
            
    def print_test_summary(self):
        """Print test results summary."""
        print("=" * 60)
        print("Test Results Summary")
        print("=" * 60)
        
        # Redis Resilience
        print("\n📊 Redis Connection Resilience:")
        print(f"   Failure handling: {'✅ Passed' if self.results.get('redis_failure_handling', False) else '❌ Failed'}")
        print(f"   Recovery: {'✅ Passed' if self.results.get('redis_recovery', False) else '❌ Failed'}")
        
        # WebSocket Resilience
        print("\n📊 WebSocket Resilience:")
        print(f"   Auto-reconnection: {'✅ Passed' if self.results.get('websocket_reconnection', False) else '❌ Failed'}")
        print(f"   Messages received: {self.results.get('websocket_messages', 0)}")
        
        # High Volume Performance
        print("\n📊 High Volume Processing:")
        print(f"   Ticks processed: {self.results.get('high_volume_processed', 0):,}")
        print(f"   Throughput: {self.results.get('throughput_tps', 0):,.0f} ticks/sec")
        print(f"   Memory efficiency: {'✅ Passed' if self.results.get('memory_efficiency', False) else '❌ Failed'}")
        
        # Concurrent Clients
        print("\n📊 Concurrent Client Handling:")
        print(f"   Successful clients: {self.results.get('concurrent_clients', 0)}")
        print(f"   Success rate: {self.results.get('concurrent_success_rate', 0):.1%}")
        print(f"   Server stability: {'✅ Passed' if self.results.get('concurrent_stable', False) else '❌ Failed'}")
        
        # Overall Assessment
        critical_tests = [
            'redis_failure_handling',
            'redis_recovery',
            'websocket_reconnection',
            'memory_efficiency',
            'concurrent_stable'
        ]
        
        passed_tests = sum(1 for test in critical_tests if self.results.get(test, False))
        total_tests = len(critical_tests)
        
        print("\n" + "=" * 60)
        print(f"Overall: {passed_tests}/{total_tests} critical tests passed")
        
        if passed_tests == total_tests:
            print("✅ All resilience tests passed! The streaming service is production-ready.")
        else:
            print("⚠️  Some resilience tests failed. Review and fix issues before production.")
        print("=" * 60)


async def main():
    """Run resilience tests."""
    # Check prerequisites
    print("Pre-flight checks:")
    print("- Ensure API server is running (uvicorn)")
    print("- Ensure Redis is running")
    print("- Ensure sufficient system resources")
    print()
    
    # Run tests
    tester = StreamingResilienceTests()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())