#!/usr/bin/env python3
"""
Comprehensive performance benchmark for real-time streaming service.

Measures:
1. Maximum throughput (ticks per second)
2. Tick-to-candle aggregation latency
3. Redis pub/sub message delivery time
4. WebSocket broadcast latency
5. Maximum concurrent symbols without degradation
"""

import asyncio
import json
import time
import statistics
import psutil
import redis
import websockets
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
import aiohttp
from dataclasses import dataclass, field
import numpy as np

# Configuration
REDIS_URL = "redis://:redis123@localhost:6379/0"
WS_URL = "ws://localhost:8000/ws"
API_KEY = "test-api-key-12345"


@dataclass
class PerformanceMetrics:
    """Container for performance measurements."""
    # Throughput
    total_ticks: int = 0
    duration: float = 0.0
    ticks_per_second: float = 0.0
    
    # Latency (in milliseconds)
    tick_to_candle_latencies: List[float] = field(default_factory=list)
    redis_pubsub_latencies: List[float] = field(default_factory=list)
    websocket_latencies: List[float] = field(default_factory=list)
    
    # Resource usage
    cpu_usage: List[float] = field(default_factory=list)
    memory_usage: List[float] = field(default_factory=list)
    
    # Concurrent symbols
    max_concurrent_symbols: int = 0
    degradation_threshold: int = 0


class StreamingPerformanceBenchmark:
    """Performance benchmark suite for streaming service."""
    
    def __init__(self):
        self.metrics = PerformanceMetrics()
        self.redis_client = None
        self.process = psutil.Process()
        
    async def initialize(self):
        """Initialize benchmark components."""
        self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        print("✓ Benchmark initialized")
        
    async def run_all_benchmarks(self):
        """Run all performance benchmarks."""
        print("=" * 60)
        print("Streaming Service Performance Benchmark")
        print("=" * 60)
        print()
        
        await self.initialize()
        
        # Benchmark 1: Maximum Throughput
        print("1. Testing Maximum Throughput...")
        await self.benchmark_throughput()
        print()
        
        # Benchmark 2: Tick-to-Candle Latency
        print("2. Testing Tick-to-Candle Latency...")
        await self.benchmark_tick_to_candle_latency()
        print()
        
        # Benchmark 3: Redis Pub/Sub Latency
        print("3. Testing Redis Pub/Sub Latency...")
        await self.benchmark_redis_latency()
        print()
        
        # Benchmark 4: WebSocket Broadcast Latency
        print("4. Testing WebSocket Broadcast Latency...")
        await self.benchmark_websocket_latency()
        print()
        
        # Benchmark 5: Maximum Concurrent Symbols
        print("5. Testing Maximum Concurrent Symbols...")
        await self.benchmark_concurrent_symbols()
        print()
        
        # Generate report
        self.generate_performance_report()
        
    async def benchmark_throughput(self):
        """Benchmark maximum tick processing throughput."""
        from src.data.stream_processor import CandleAggregator
        processor = CandleAggregator()
        await processor.initialize()
        
        print("   🚀 Running throughput benchmark...")
        
        # Warm up
        for _ in range(100):
            await processor.process_quote({
                'symbol': 'WARMUP',
                'timestamp': datetime.now(timezone.utc),
                'last': 100.0,
                'volume': 100
            })
        
        # Actual benchmark
        tick_count = 0
        batch_sizes = [100, 500, 1000, 5000, 10000]
        
        for batch_size in batch_sizes:
            start_time = time.perf_counter()
            start_cpu = self.process.cpu_percent(interval=0.1)
            start_memory = self.process.memory_info().rss / 1024 / 1024
            
            # Process batch
            tasks = []
            for i in range(batch_size):
                quote = {
                    'symbol': f'PERF{i % 10}',  # 10 different symbols
                    'timestamp': datetime.now(timezone.utc),
                    'last': 100.0 + (i % 100),
                    'volume': 1000 + i
                }
                tasks.append(processor.process_quote(quote))
            
            # Execute all tasks
            await asyncio.gather(*tasks)
            tick_count += batch_size
            
            # Measure
            duration = time.perf_counter() - start_time
            tps = batch_size / duration
            cpu = self.process.cpu_percent(interval=0.1)
            memory = self.process.memory_info().rss / 1024 / 1024
            
            print(f"   📊 Batch {batch_size:,} ticks:")
            print(f"      Throughput: {tps:,.0f} ticks/sec")
            print(f"      Duration: {duration:.3f}s")
            print(f"      CPU: {cpu:.1f}%")
            print(f"      Memory: {memory:.1f} MB (+{memory-start_memory:.1f})")
            
            self.metrics.cpu_usage.append(cpu)
            self.metrics.memory_usage.append(memory)
            
            # Update best throughput
            if tps > self.metrics.ticks_per_second:
                self.metrics.ticks_per_second = tps
                self.metrics.total_ticks = batch_size
                self.metrics.duration = duration
        
        await processor.shutdown()
        
    async def benchmark_tick_to_candle_latency(self):
        """Benchmark latency from tick arrival to candle aggregation."""
        from src.data.stream_processor import CandleAggregator
        processor = CandleAggregator()
        await processor.initialize()
        
        print("   🚀 Measuring tick-to-candle latency...")
        
        # Set up Redis listener for candle updates
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe("candles:all")
        
        latencies = []
        
        # Process ticks and measure latency
        for i in range(100):
            tick_time = time.perf_counter()
            
            quote = {
                'symbol': 'LATENCY_TEST',
                'timestamp': datetime.now(timezone.utc),
                'last': 100.0 + i,
                'volume': 1000
            }
            
            # Process tick
            await processor.process_quote(quote)
            
            # Wait for candle update
            start_wait = time.perf_counter()
            while time.perf_counter() - start_wait < 0.1:  # 100ms timeout
                message = pubsub.get_message(timeout=0.001)
                if message and message['type'] == 'message':
                    candle_time = time.perf_counter()
                    latency = (candle_time - tick_time) * 1000  # Convert to ms
                    latencies.append(latency)
                    break
        
        if latencies:
            self.metrics.tick_to_candle_latencies = latencies
            
            print(f"   📊 Tick-to-Candle Latency (ms):")
            print(f"      Average: {statistics.mean(latencies):.2f}")
            print(f"      Median: {statistics.median(latencies):.2f}")
            print(f"      Min: {min(latencies):.2f}")
            print(f"      Max: {max(latencies):.2f}")
            print(f"      95th percentile: {np.percentile(latencies, 95):.2f}")
        
        pubsub.close()
        await processor.shutdown()
        
    async def benchmark_redis_latency(self):
        """Benchmark Redis pub/sub message delivery latency."""
        print("   🚀 Measuring Redis pub/sub latency...")
        
        pubsub = self.redis_client.pubsub()
        test_channel = "benchmark:test"
        pubsub.subscribe(test_channel)
        
        latencies = []
        
        # Send messages and measure round-trip time
        for i in range(100):
            message_data = {
                'id': i,
                'timestamp': time.perf_counter()
            }
            
            # Publish
            self.redis_client.publish(test_channel, json.dumps(message_data))
            
            # Receive
            start_wait = time.perf_counter()
            while time.perf_counter() - start_wait < 0.1:  # 100ms timeout
                message = pubsub.get_message(timeout=0.001)
                if message and message['type'] == 'message':
                    received_data = json.loads(message['data'])
                    if received_data['id'] == i:
                        latency = (time.perf_counter() - received_data['timestamp']) * 1000
                        latencies.append(latency)
                        break
        
        if latencies:
            self.metrics.redis_pubsub_latencies = latencies
            
            print(f"   📊 Redis Pub/Sub Latency (ms):")
            print(f"      Average: {statistics.mean(latencies):.2f}")
            print(f"      Median: {statistics.median(latencies):.2f}")
            print(f"      Min: {min(latencies):.2f}")
            print(f"      Max: {max(latencies):.2f}")
            print(f"      95th percentile: {np.percentile(latencies, 95):.2f}")
        
        pubsub.close()
        
    async def benchmark_websocket_latency(self):
        """Benchmark WebSocket broadcast latency."""
        print("   🚀 Measuring WebSocket broadcast latency...")
        
        latencies = []
        
        try:
            # Connect to WebSocket
            uri = f"{WS_URL}?token={API_KEY}"
            async with websockets.connect(uri) as websocket:
                # Skip initial connection message
                await websocket.recv()
                
                # Subscribe to test symbol
                await websocket.send(json.dumps({
                    "type": "subscribe",
                    "symbols": ["WS_LATENCY_TEST"]
                }))
                
                # Skip subscription confirmation
                await websocket.recv()
                
                # Measure latency by sending ping messages
                for i in range(50):
                    ping_time = time.perf_counter()
                    
                    await websocket.send(json.dumps({
                        "type": "ping",
                        "timestamp": ping_time
                    }))
                    
                    # Wait for pong
                    start_wait = time.perf_counter()
                    while time.perf_counter() - start_wait < 0.1:
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                            data = json.loads(message)
                            if data.get('type') == 'pong':
                                pong_time = time.perf_counter()
                                latency = (pong_time - ping_time) * 1000
                                latencies.append(latency)
                                break
                        except asyncio.TimeoutError:
                            break
                    
                    await asyncio.sleep(0.01)  # Small delay between pings
                
                if latencies:
                    self.metrics.websocket_latencies = latencies
                    
                    print(f"   📊 WebSocket Latency (ms):")
                    print(f"      Average: {statistics.mean(latencies):.2f}")
                    print(f"      Median: {statistics.median(latencies):.2f}")
                    print(f"      Min: {min(latencies):.2f}")
                    print(f"      Max: {max(latencies):.2f}")
                    print(f"      95th percentile: {np.percentile(latencies, 95):.2f}")
                    
        except Exception as e:
            print(f"   ⚠️  WebSocket benchmark failed: {e}")
            
    async def benchmark_concurrent_symbols(self):
        """Find maximum concurrent symbols without performance degradation."""
        from src.data.stream_processor import CandleAggregator
        processor = CandleAggregator()
        await processor.initialize()
        
        print("   🚀 Testing maximum concurrent symbols...")
        
        baseline_tps = 0
        symbol_counts = [10, 50, 100, 200, 500, 1000]
        
        for symbol_count in symbol_counts:
            symbols = [f"SYMBOL_{i:04d}" for i in range(symbol_count)]
            
            # Generate test load
            tick_count = 1000
            start_time = time.perf_counter()
            
            tasks = []
            for i in range(tick_count):
                symbol = symbols[i % len(symbols)]
                quote = {
                    'symbol': symbol,
                    'timestamp': datetime.now(timezone.utc),
                    'last': 100.0 + (i % 100),
                    'volume': 1000
                }
                tasks.append(processor.process_quote(quote))
            
            # Process
            await asyncio.gather(*tasks)
            
            duration = time.perf_counter() - start_time
            tps = tick_count / duration
            
            # Set baseline
            if symbol_count == 10:
                baseline_tps = tps
            
            # Check for degradation (>20% drop)
            degradation = ((baseline_tps - tps) / baseline_tps) * 100 if baseline_tps > 0 else 0
            
            print(f"   📊 {symbol_count} symbols:")
            print(f"      TPS: {tps:,.0f}")
            print(f"      Degradation: {degradation:.1f}%")
            
            if degradation < 20:  # Less than 20% degradation
                self.metrics.max_concurrent_symbols = symbol_count
            else:
                self.metrics.degradation_threshold = symbol_count
                break
        
        await processor.shutdown()
        
    def generate_performance_report(self):
        """Generate comprehensive performance report."""
        print("=" * 60)
        print("Performance Benchmark Report")
        print("=" * 60)
        
        # Throughput
        print("\n📊 Maximum Throughput:")
        print(f"   Peak TPS: {self.metrics.ticks_per_second:,.0f} ticks/second")
        print(f"   Batch size: {self.metrics.total_ticks:,} ticks")
        print(f"   Duration: {self.metrics.duration:.3f} seconds")
        
        # Latencies
        print("\n📊 Latency Analysis (milliseconds):")
        
        if self.metrics.tick_to_candle_latencies:
            print("   Tick-to-Candle:")
            self._print_latency_stats(self.metrics.tick_to_candle_latencies)
        
        if self.metrics.redis_pubsub_latencies:
            print("   Redis Pub/Sub:")
            self._print_latency_stats(self.metrics.redis_pubsub_latencies)
        
        if self.metrics.websocket_latencies:
            print("   WebSocket:")
            self._print_latency_stats(self.metrics.websocket_latencies)
        
        # Resource usage
        if self.metrics.cpu_usage:
            print(f"\n📊 Resource Usage:")
            print(f"   CPU: {statistics.mean(self.metrics.cpu_usage):.1f}% average")
            print(f"   Memory: {statistics.mean(self.metrics.memory_usage):.1f} MB average")
        
        # Concurrent symbols
        print(f"\n📊 Concurrent Symbol Capacity:")
        print(f"   Maximum without degradation: {self.metrics.max_concurrent_symbols} symbols")
        if self.metrics.degradation_threshold:
            print(f"   Performance degradation at: {self.metrics.degradation_threshold} symbols")
        
        # Overall assessment
        print("\n" + "=" * 60)
        print("Performance Assessment:")
        
        if self.metrics.ticks_per_second > 10000:
            print("✅ Excellent throughput (>10K TPS)")
        elif self.metrics.ticks_per_second > 5000:
            print("✅ Good throughput (>5K TPS)")
        elif self.metrics.ticks_per_second > 1000:
            print("⚠️  Moderate throughput (>1K TPS)")
        else:
            print("❌ Low throughput (<1K TPS)")
        
        avg_latency = statistics.mean(self.metrics.tick_to_candle_latencies) if self.metrics.tick_to_candle_latencies else 0
        if avg_latency < 5:
            print("✅ Excellent latency (<5ms)")
        elif avg_latency < 20:
            print("✅ Good latency (<20ms)")
        elif avg_latency < 50:
            print("⚠️  Moderate latency (<50ms)")
        else:
            print("❌ High latency (>50ms)")
        
        if self.metrics.max_concurrent_symbols >= 100:
            print("✅ High concurrency capacity (100+ symbols)")
        elif self.metrics.max_concurrent_symbols >= 50:
            print("✅ Good concurrency capacity (50+ symbols)")
        else:
            print("⚠️  Limited concurrency capacity")
        
        print("=" * 60)
        
    def _print_latency_stats(self, latencies: List[float]):
        """Print latency statistics."""
        print(f"      Average: {statistics.mean(latencies):.2f} ms")
        print(f"      Median: {statistics.median(latencies):.2f} ms")
        print(f"      95th percentile: {np.percentile(latencies, 95):.2f} ms")
        print(f"      99th percentile: {np.percentile(latencies, 99):.2f} ms")
        print(f"      Max: {max(latencies):.2f} ms")


async def main():
    """Run performance benchmarks."""
    print("Starting performance benchmark...")
    print("This will take several minutes to complete.")
    print()
    
    # Check prerequisites
    try:
        r = redis.from_url(REDIS_URL)
        r.ping()
        r.close()
        print("✓ Redis is running")
    except:
        print("❌ Redis is not running. Please start Redis first.")
        return
    
    # Run benchmarks
    benchmark = StreamingPerformanceBenchmark()
    await benchmark.run_all_benchmarks()


if __name__ == "__main__":
    asyncio.run(main())