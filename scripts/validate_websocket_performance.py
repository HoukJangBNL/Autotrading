#!/usr/bin/env python3
"""
Standalone script to validate WebSocket performance.

Run this script to verify the WebSocket implementation meets performance requirements:
- Handle 10,000+ ticks per second
- Maintain low latency (<50ms average, <100ms P99)
- Drop rate less than 1%
- Support multiple symbols efficiently
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_websocket_performance import (
    HighVolumeWebSocketServer,
    PerformanceMetrics,
    TestWebSocketPerformance
)
from unittest.mock import Mock, AsyncMock
import websockets
import time


async def run_performance_test():
    """Run standalone performance validation."""
    print("=" * 60)
    print("WebSocket Performance Validation")
    print("=" * 60)
    
    # Create mock auth service
    auth_service = Mock()
    mock_client = Mock()
    mock_client.get_user_preferences = AsyncMock(return_value={
        'streamerInfo': [{
            'token': 'test_token',
            'appId': 'test_app',
            'streamerSocketUrl': 'ws://localhost:8768',
            'userGroup': 'ACCT',
            'accessLevel': '1',
            'acl': 'test_acl'
        }]
    })
    auth_service.get_client = Mock(return_value=mock_client)
    auth_service.initialize = AsyncMock()
    
    # Create high-volume server
    server = HighVolumeWebSocketServer(target_tps=10000)
    
    # Start server
    async with websockets.serve(
        server.handler,
        "localhost",
        8768,
        max_size=50 * 1024 * 1024
    ):
        print("\n✓ High-volume WebSocket server started on localhost:8768")
        print(f"  Target throughput: {server.target_tps:,} ticks/second")
        
        # Create test instance
        test = TestWebSocketPerformance()
        
        # Run tests
        print("\n1. Testing 10,000 ticks per second throughput...")
        print("-" * 40)
        
        try:
            await test.test_10k_ticks_per_second(server, auth_service)
            print("✓ Throughput test PASSED")
        except AssertionError as e:
            print(f"✗ Throughput test FAILED: {e}")
        except Exception as e:
            print(f"✗ Throughput test ERROR: {e}")
        
        # Reset server
        server.running = False
        await asyncio.sleep(0.5)
        
        print("\n2. Testing StreamingService performance...")
        print("-" * 40)
        
        try:
            await test.test_streaming_service_performance(server, auth_service)
            print("✓ StreamingService test PASSED")
        except AssertionError as e:
            print(f"✗ StreamingService test FAILED: {e}")
        except Exception as e:
            print(f"✗ StreamingService test ERROR: {e}")
        
        # Test with many symbols
        print("\n3. Testing multi-symbol performance (50 symbols)...")
        print("-" * 40)
        
        server.running = False
        await asyncio.sleep(0.5)
        
        try:
            await test.test_multi_symbol_performance(server, auth_service)
            print("✓ Multi-symbol test PASSED")
        except AssertionError as e:
            print(f"✗ Multi-symbol test FAILED: {e}")
        except Exception as e:
            print(f"✗ Multi-symbol test ERROR: {e}")
    
    print("\n" + "=" * 60)
    print("Performance Validation Complete")
    print("=" * 60)


async def run_stress_test():
    """Run extended stress test."""
    print("\n" + "=" * 60)
    print("Running Extended Stress Test (60 seconds)")
    print("=" * 60)
    
    # Create mock auth service
    auth_service = Mock()
    mock_client = Mock()
    mock_client.get_user_preferences = AsyncMock(return_value={
        'streamerInfo': [{
            'token': 'test_token',
            'appId': 'test_app',
            'streamerSocketUrl': 'ws://localhost:8769',
            'userGroup': 'ACCT',
            'accessLevel': '1',
            'acl': 'test_acl'
        }]
    })
    auth_service.get_client = Mock(return_value=mock_client)
    auth_service.initialize = AsyncMock()
    
    # Create server with very high volume
    server = HighVolumeWebSocketServer(target_tps=20000)
    
    async with websockets.serve(
        server.handler,
        "localhost",
        8769,
        max_size=50 * 1024 * 1024
    ):
        from src.data.stream_processor import create_stream_processor
        from src.data.websocket_client import SchwabWebSocketClient
        from unittest.mock import patch
        
        # Create stream processor
        stream_processor = await create_stream_processor(
            redis_url=None,
            save_to_db=False,
            timeframes=[1]
        )
        
        # Track metrics
        metrics = PerformanceMetrics()
        tick_count = 0
        
        @stream_processor.on_tick
        async def on_tick(tick):
            nonlocal tick_count
            tick_count += 1
            
            # Sample latency
            if tick_count % 1000 == 0:
                latency = (time.time() * 1000) - (tick.timestamp.timestamp() * 1000)
                metrics.latencies.append(latency)
        
        # Create client
        with patch('src.data.websocket_client.get_auth_service', return_value=auth_service):
            client = SchwabWebSocketClient(
                stream_processor=stream_processor,
                account_id="TEST123456",
                auth_service=auth_service
            )
            
            print("\nStarting stress test...")
            print(f"Target: {server.target_tps:,} ticks/second")
            print("Duration: 60 seconds")
            print("\nProgress:")
            
            # Connect
            await client.connect()
            
            # Subscribe to many symbols
            symbols = [f"SYM{i:03d}" for i in range(100)]
            await client.subscribe(symbols[:50], ["QUOTE"])
            
            # Track progress
            start_time = time.time()
            last_print = start_time
            
            for i in range(60):
                await asyncio.sleep(1)
                
                # Print progress
                elapsed = time.time() - start_time
                current_tps = tick_count / elapsed if elapsed > 0 else 0
                queue_size = stream_processor.tick_queue.qsize()
                
                if time.time() - last_print >= 5:
                    print(f"  {int(elapsed)}s: {current_tps:,.0f} tps, "
                          f"queue: {queue_size}, total: {tick_count:,}")
                    last_print = time.time()
            
            # Final metrics
            metrics.end_time = time.time()
            metrics.start_time = start_time
            metrics.ticks_processed = tick_count
            
            summary = metrics.summary()
            
            print("\n" + "-" * 40)
            print("Stress Test Results:")
            print(f"Total ticks processed: {tick_count:,}")
            print(f"Average throughput: {summary['throughput_tps']:,.0f} tps")
            print(f"Average latency: {summary['avg_latency_ms']:.2f} ms")
            print(f"P99 latency: {summary['p99_latency_ms']:.2f} ms")
            
            # Check for any errors
            total_errors = sum(
                monitor.error_count 
                for monitor in stream_processor.health_monitors.values()
            )
            print(f"Total errors: {total_errors}")
            
            # Cleanup
            await client.disconnect()
            await stream_processor.stop()


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Validate WebSocket streaming performance"
    )
    parser.add_argument(
        "--stress",
        action="store_true",
        help="Run extended stress test (60 seconds)"
    )
    
    args = parser.parse_args()
    
    try:
        if args.stress:
            await run_stress_test()
        else:
            await run_performance_test()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())