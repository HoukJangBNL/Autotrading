"""
Performance tests for WebSocket streaming with high volume data.

This module validates that the WebSocket implementation can handle
the required 10,000+ ticks per second throughput.
"""

import asyncio
import json
import time
import pytest
from datetime import datetime, timezone
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock, patch
import websockets
from dataclasses import dataclass, field
import statistics

from src.data.websocket_client import SchwabWebSocketClient
from src.data.stream_processor import StreamProcessor, create_stream_processor
from src.data.streaming_service import StreamingService, create_streaming_service


@dataclass
class PerformanceMetrics:
    """Track performance metrics during testing."""
    
    start_time: float = 0.0
    end_time: float = 0.0
    
    # Tick metrics
    ticks_sent: int = 0
    ticks_received: int = 0
    ticks_processed: int = 0
    ticks_dropped: int = 0
    
    # Latency tracking
    latencies: List[float] = field(default_factory=list)
    
    # Resource usage
    max_queue_size: int = 0
    memory_samples: List[float] = field(default_factory=list)
    
    @property
    def duration(self) -> float:
        """Test duration in seconds."""
        return self.end_time - self.start_time
    
    @property
    def ticks_per_second(self) -> float:
        """Calculate throughput."""
        if self.duration > 0:
            return self.ticks_processed / self.duration
        return 0.0
    
    @property
    def average_latency(self) -> float:
        """Average processing latency in milliseconds."""
        if self.latencies:
            return statistics.mean(self.latencies)
        return 0.0
    
    @property
    def p99_latency(self) -> float:
        """99th percentile latency."""
        if self.latencies:
            sorted_latencies = sorted(self.latencies)
            idx = int(len(sorted_latencies) * 0.99)
            return sorted_latencies[idx]
        return 0.0
    
    @property
    def drop_rate(self) -> float:
        """Percentage of ticks dropped."""
        if self.ticks_sent > 0:
            return (self.ticks_dropped / self.ticks_sent) * 100
        return 0.0
    
    def summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        return {
            'duration_seconds': round(self.duration, 2),
            'ticks_sent': self.ticks_sent,
            'ticks_processed': self.ticks_processed,
            'ticks_dropped': self.ticks_dropped,
            'drop_rate_percent': round(self.drop_rate, 2),
            'throughput_tps': round(self.ticks_per_second, 0),
            'avg_latency_ms': round(self.average_latency, 2),
            'p99_latency_ms': round(self.p99_latency, 2),
            'max_queue_size': self.max_queue_size
        }


class HighVolumeWebSocketServer:
    """Mock WebSocket server that generates high-volume data."""
    
    def __init__(self, target_tps: int = 10000):
        """
        Initialize high-volume server.
        
        Args:
            target_tps: Target ticks per second to generate
        """
        self.target_tps = target_tps
        self.symbols = []
        self.running = False
        self.metrics = PerformanceMetrics()
        
    async def handler(self, websocket, path):
        """WebSocket connection handler."""
        try:
            # Handle authentication
            auth_msg = await websocket.recv()
            auth_data = json.loads(auth_msg)
            
            # Send auth response
            response = {
                "response": [{
                    "service": "ADMIN",
                    "command": "LOGIN",
                    "requestid": auth_data["requests"][0]["requestid"],
                    "content": {"code": 0, "msg": "Login successful"}
                }]
            }
            await websocket.send(json.dumps(response))
            
            # Handle subscription
            sub_msg = await websocket.recv()
            sub_data = json.loads(sub_msg)
            
            for request in sub_data.get("requests", []):
                if request.get("command") == "SUBS":
                    self.symbols = request["parameters"]["keys"].split(",")
                    
                    # Send subscription response
                    response = {
                        "response": [{
                            "service": request["service"],
                            "command": "SUBS",
                            "requestid": request["requestid"],
                            "content": {"code": 0, "msg": "Subscription successful"}
                        }]
                    }
                    await websocket.send(json.dumps(response))
                    
                    # Start high-volume data generation
                    await self.generate_high_volume_data(websocket)
                    
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            print(f"Server error: {e}")
    
    async def generate_high_volume_data(self, websocket):
        """Generate high-volume market data."""
        self.running = True
        self.metrics.start_time = time.time()
        
        # Calculate batch size and interval for target TPS
        batch_size = min(100, self.target_tps // 10)  # Send in batches
        batch_interval = batch_size / self.target_tps
        
        price_base = 150.0
        tick_count = 0
        
        try:
            while self.running:
                batch_start = time.time()
                
                # Generate batch of ticks
                messages = []
                
                for _ in range(batch_size):
                    # Rotate through symbols
                    symbol = self.symbols[tick_count % len(self.symbols)]
                    
                    # Generate tick with timestamp
                    timestamp = int(time.time() * 1000)
                    price = price_base + (tick_count % 100) * 0.01
                    
                    # Create quote update
                    quote_data = {
                        "data": [{
                            "service": "QUOTE",
                            "timestamp": timestamp,
                            "content": [{
                                "key": symbol,
                                "1": price - 0.01,  # BID_PRICE
                                "2": price + 0.01,  # ASK_PRICE
                                "3": price,         # LAST_PRICE
                                "4": 100,           # BID_SIZE
                                "5": 100,           # ASK_SIZE
                                "9": 100,           # LAST_SIZE
                                "8": tick_count * 100,  # TOTAL_VOLUME
                                "50": timestamp,    # QUOTE_TIME
                                "51": timestamp     # TRADE_TIME
                            }]
                        }]
                    }
                    messages.append(json.dumps(quote_data))
                    
                    tick_count += 1
                    self.metrics.ticks_sent += 3  # bid, ask, trade
                
                # Send batch
                for msg in messages:
                    await websocket.send(msg)
                
                # Maintain target rate
                elapsed = time.time() - batch_start
                if elapsed < batch_interval:
                    await asyncio.sleep(batch_interval - elapsed)
                    
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.running = False
            self.metrics.end_time = time.time()


class TestWebSocketPerformance:
    """Performance test suite for WebSocket streaming."""
    
    @pytest.fixture
    async def high_volume_server(self):
        """Create high-volume test server."""
        server = HighVolumeWebSocketServer(target_tps=10000)
        
        async with websockets.serve(
            server.handler,
            "localhost",
            8767,
            max_size=50 * 1024 * 1024  # 50MB max message
        ):
            yield server
    
    @pytest.fixture
    def mock_auth_service(self):
        """Create mock auth service."""
        auth_service = Mock()
        mock_client = Mock()
        mock_client.get_user_preferences = AsyncMock(return_value={
            'streamerInfo': [{
                'token': 'test_token',
                'appId': 'test_app',
                'streamerSocketUrl': 'ws://localhost:8767',
                'userGroup': 'ACCT',
                'accessLevel': '1',
                'acl': 'test_acl'
            }]
        })
        auth_service.get_client = Mock(return_value=mock_client)
        auth_service.initialize = AsyncMock()
        return auth_service
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_10k_ticks_per_second(self, high_volume_server, mock_auth_service):
        """Test handling 10,000 ticks per second."""
        metrics = PerformanceMetrics()
        processed_count = 0
        
        # Create stream processor
        stream_processor = await create_stream_processor(
            redis_url=None,
            save_to_db=False,
            timeframes=[1]  # Only 1-minute bars for performance
        )
        
        # Track processed ticks
        @stream_processor.on_tick
        async def on_tick(tick):
            nonlocal processed_count
            processed_count += 1
            
            # Sample latency (every 100th tick)
            if processed_count % 100 == 0:
                latency = (time.time() * 1000) - (tick.timestamp.timestamp() * 1000)
                metrics.latencies.append(latency)
        
        # Create WebSocket client
        with patch('src.data.websocket_client.get_auth_service', return_value=mock_auth_service):
            client = SchwabWebSocketClient(
                stream_processor=stream_processor,
                account_id="TEST123456",
                auth_service=mock_auth_service
            )
            
            # Start performance test
            metrics.start_time = time.time()
            
            # Connect and subscribe
            success = await client.connect()
            assert success is True
            
            await client.subscribe(["AAPL", "GOOGL", "MSFT"], ["QUOTE"])
            
            # Run for 10 seconds
            test_duration = 10
            await asyncio.sleep(test_duration)
            
            metrics.end_time = time.time()
            metrics.ticks_processed = processed_count
            metrics.ticks_sent = high_volume_server.metrics.ticks_sent
            
            # Check queue usage
            metrics.max_queue_size = client.tick_queue.qsize()
            
            # Calculate drop rate from stream processor
            total_dropped = sum(
                monitor.ticks_dropped 
                for monitor in stream_processor.health_monitors.values()
            )
            metrics.ticks_dropped = total_dropped
            
            # Cleanup
            await client.disconnect()
            await stream_processor.stop()
        
        # Performance assertions
        summary = metrics.summary()
        print(f"\nPerformance Test Results:")
        print(f"Duration: {summary['duration_seconds']}s")
        print(f"Ticks sent: {summary['ticks_sent']:,}")
        print(f"Ticks processed: {summary['ticks_processed']:,}")
        print(f"Throughput: {summary['throughput_tps']:,.0f} ticks/second")
        print(f"Drop rate: {summary['drop_rate_percent']:.2f}%")
        print(f"Average latency: {summary['avg_latency_ms']:.2f}ms")
        print(f"P99 latency: {summary['p99_latency_ms']:.2f}ms")
        
        # Performance requirements
        assert summary['throughput_tps'] >= 9000  # Allow 10% margin
        assert summary['drop_rate_percent'] < 1.0  # Less than 1% drops
        assert summary['avg_latency_ms'] < 50  # Average under 50ms
        assert summary['p99_latency_ms'] < 100  # P99 under 100ms
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_streaming_service_performance(self, high_volume_server, mock_auth_service):
        """Test StreamingService with high volume."""
        # Create streaming service
        with patch('src.auth.auth_service.get_auth_service', return_value=mock_auth_service):
            with patch('src.data.websocket_client.get_auth_service', return_value=mock_auth_service):
                service = StreamingService(
                    account_id="TEST123456",
                    redis_url=None,
                    save_to_db=False,
                    timeframes=[1, 5]  # Test with multiple timeframes
                )
                
                # Track performance
                tick_count = 0
                bar_count = 0
                
                @service.stream_processor.on_tick
                async def on_tick(tick):
                    nonlocal tick_count
                    tick_count += 1
                
                @service.stream_processor.on_bar
                async def on_bar(bar):
                    nonlocal bar_count
                    bar_count += 1
                
                # Start streaming
                await service.start_streaming(["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"])
                
                # Run for 5 seconds
                start_time = time.time()
                await asyncio.sleep(5)
                duration = time.time() - start_time
                
                # Get statistics
                stats = service.get_statistics()
                health = service.get_health_status()
                
                # Calculate rates
                tick_rate = tick_count / duration
                message_rate = stats['messages_received'] / duration
                
                print(f"\nStreaming Service Performance:")
                print(f"Messages received: {stats['messages_received']:,}")
                print(f"Message rate: {message_rate:,.0f}/second")
                print(f"Ticks processed: {tick_count:,}")
                print(f"Tick rate: {tick_rate:,.0f}/second")
                print(f"Bars created: {bar_count:,}")
                print(f"Active symbols: {len(stats['active_symbols'])}")
                
                # Check health
                assert health['streaming_service'] == 'running'
                assert all(
                    symbol_health['is_healthy'] 
                    for symbol_health in health['symbols'].values()
                )
                
                # Performance requirements
                assert tick_rate >= 9000  # Can handle 9k+ ticks/second
                assert stats['errors'] == 0  # No errors during test
                
                # Cleanup
                await service.stop_streaming()
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_queue_overflow_handling(self, mock_auth_service):
        """Test behavior when tick queue overflows."""
        # Create stream processor with small queue
        stream_processor = StreamProcessor(
            redis_client=None,
            save_to_db=False,
            timeframes=[1]
        )
        stream_processor.tick_queue = asyncio.Queue(maxsize=100)  # Small queue
        
        await stream_processor.start()
        
        # Track drops
        drops = 0
        
        # Simulate high-volume tick generation
        start_time = time.time()
        for i in range(1000):
            tick = Mock(
                symbol="AAPL",
                price=150.0 + i * 0.01,
                volume=100,
                timestamp=datetime.now(timezone.utc),
                tick_type="TRADE"
            )
            
            success = await stream_processor.add_tick(tick)
            if not success:
                drops += 1
        
        duration = time.time() - start_time
        
        # Check drop handling
        drop_rate = (drops / 1000) * 100
        print(f"\nQueue Overflow Test:")
        print(f"Ticks sent: 1,000")
        print(f"Ticks dropped: {drops}")
        print(f"Drop rate: {drop_rate:.1f}%")
        print(f"Duration: {duration:.2f}s")
        
        # Should handle overflow gracefully
        assert drops > 0  # Some drops expected with small queue
        assert stream_processor.health_monitors["AAPL"].ticks_dropped == drops
        
        await stream_processor.stop()
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_multi_symbol_performance(self, high_volume_server, mock_auth_service):
        """Test performance with many symbols."""
        # Generate 50 symbols
        symbols = [f"SYM{i:03d}" for i in range(50)]
        
        # Adjust server for more symbols
        high_volume_server.target_tps = 20000  # Higher rate with more symbols
        
        # Create streaming service
        with patch('src.auth.auth_service.get_auth_service', return_value=mock_auth_service):
            with patch('src.data.websocket_client.get_auth_service', return_value=mock_auth_service):
                service = await create_streaming_service(
                    account_id="TEST123456",
                    symbols=symbols,
                    redis_url=None,
                    save_to_db=False,
                    timeframes=[1]  # Single timeframe for performance
                )
                
                # Run for 5 seconds
                await asyncio.sleep(5)
                
                # Check performance
                stats = service.get_statistics()
                health = service.get_health_status()
                
                print(f"\nMulti-Symbol Performance (50 symbols):")
                print(f"Ticks per second: {stats['ticks_per_second']:,.0f}")
                print(f"Active symbols: {len(stats['active_symbols'])}")
                print(f"Errors: {stats['errors']}")
                
                # All symbols should be active
                assert len(stats['active_symbols']) == 50
                assert stats['ticks_per_second'] >= 15000  # Higher rate
                
                # Cleanup
                await service.stop_streaming()
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_sustained_performance(self, high_volume_server, mock_auth_service):
        """Test sustained performance over longer duration."""
        # Create stream processor
        stream_processor = await create_stream_processor(
            redis_url=None,
            save_to_db=False,
            timeframes=[1, 5]
        )
        
        # Track metrics over time
        samples = []
        
        async def sample_performance():
            """Sample performance metrics periodically."""
            while True:
                await asyncio.sleep(1)
                stats = stream_processor.stats.copy()
                stats['timestamp'] = time.time()
                stats['queue_size'] = stream_processor.tick_queue.qsize()
                samples.append(stats)
        
        # Start sampling
        sample_task = asyncio.create_task(sample_performance())
        
        # Create WebSocket client
        with patch('src.data.websocket_client.get_auth_service', return_value=mock_auth_service):
            client = SchwabWebSocketClient(
                stream_processor=stream_processor,
                account_id="TEST123456",
                auth_service=mock_auth_service
            )
            
            # Run for 30 seconds
            await client.connect()
            await client.subscribe(["AAPL", "GOOGL"], ["QUOTE"])
            
            await asyncio.sleep(30)
            
            # Stop sampling
            sample_task.cancel()
            
            # Analyze performance over time
            if len(samples) >= 2:
                # Calculate throughput for each second
                throughputs = []
                for i in range(1, len(samples)):
                    ticks_delta = samples[i]['ticks_processed'] - samples[i-1]['ticks_processed']
                    time_delta = samples[i]['timestamp'] - samples[i-1]['timestamp']
                    tps = ticks_delta / time_delta if time_delta > 0 else 0
                    throughputs.append(tps)
                
                avg_throughput = statistics.mean(throughputs)
                min_throughput = min(throughputs)
                max_throughput = max(throughputs)
                std_dev = statistics.stdev(throughputs) if len(throughputs) > 1 else 0
                
                print(f"\nSustained Performance (30s):")
                print(f"Average throughput: {avg_throughput:,.0f} tps")
                print(f"Min throughput: {min_throughput:,.0f} tps")
                print(f"Max throughput: {max_throughput:,.0f} tps")
                print(f"Std deviation: {std_dev:,.0f}")
                print(f"Total ticks: {samples[-1]['ticks_processed']:,}")
                
                # Performance should be consistent
                assert avg_throughput >= 9000
                assert min_throughput >= 8000  # Allow some variation
                assert std_dev < 2000  # Relatively stable
            
            # Cleanup
            await client.disconnect()
            await stream_processor.stop()