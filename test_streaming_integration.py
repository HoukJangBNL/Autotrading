#!/usr/bin/env python3
"""
Integration test for real-time streaming functionality.

Tests:
1. WebSocket connection and authentication
2. Streaming service startup
3. Symbol subscription
4. Real-time data flow
5. Candle aggregation via Redis pub/sub
"""

import asyncio
import json
import time
from datetime import datetime
import websockets
import aiohttp
import redis
from typing import Dict, List, Any

# Configuration
API_BASE_URL = "http://localhost:8000/api"
WS_URL = "ws://localhost:8000/ws"
API_KEY = "test-api-key-12345"  # Should match settings
REDIS_URL = "redis://:redis123@localhost:6379/0"

# Test symbols
TEST_SYMBOLS = ["AAPL", "MSFT", "GOOGL"]


async def test_api_authentication():
    """Test API authentication."""
    print("\n1. Testing API authentication...")
    
    headers = {"X-API-Key": API_KEY}
    
    async with aiohttp.ClientSession() as session:
        # Test auth status
        async with session.get(f"{API_BASE_URL}/auth/status", headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✓ Authentication successful: {data}")
                return True
            else:
                print(f"✗ Authentication failed: {resp.status}")
                return False


async def test_websocket_connection():
    """Test WebSocket connection and subscription."""
    print("\n2. Testing WebSocket connection...")
    
    messages_received = []
    
    try:
        # Connect with authentication token
        uri = f"{WS_URL}?token={API_KEY}"
        
        async with websockets.connect(uri) as websocket:
            print("✓ Connected to WebSocket")
            
            # Wait for connection message
            message = await websocket.recv()
            data = json.loads(message)
            print(f"✓ Received connection message: {data['type']}")
            messages_received.append(data)
            
            # Subscribe to test symbols
            subscribe_msg = {
                "type": "subscribe",
                "symbols": TEST_SYMBOLS
            }
            await websocket.send(json.dumps(subscribe_msg))
            print(f"✓ Sent subscription request for: {TEST_SYMBOLS}")
            
            # Wait for subscription confirmation
            message = await websocket.recv()
            data = json.loads(message)
            print(f"✓ Received subscription confirmation: {data}")
            messages_received.append(data)
            
            # Test ping/pong
            ping_msg = {"type": "ping"}
            await websocket.send(json.dumps(ping_msg))
            
            message = await websocket.recv()
            data = json.loads(message)
            if data['type'] == 'pong':
                print("✓ Ping/pong successful")
                messages_received.append(data)
            
            return True, messages_received
            
    except Exception as e:
        print(f"✗ WebSocket error: {e}")
        return False, messages_received


async def test_streaming_service():
    """Test streaming service startup via REST API."""
    print("\n3. Testing streaming service startup...")
    
    headers = {"X-API-Key": API_KEY}
    
    async with aiohttp.ClientSession() as session:
        # Start streaming
        streaming_request = {
            "symbols": TEST_SYMBOLS,
            "mode": "BOTH"
        }
        
        async with session.post(
            f"{API_BASE_URL}/data/streaming/start",
            headers=headers,
            json=streaming_request
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✓ Streaming started: {data}")
                
                # Check status
                async with session.get(
                    f"{API_BASE_URL}/data/streaming/status",
                    headers=headers
                ) as status_resp:
                    if status_resp.status == 200:
                        status = await status_resp.json()
                        print(f"✓ Streaming status: Active={status.get('active')}, "
                              f"Subscriptions={status.get('subscription_count')}")
                        return True
                    else:
                        print(f"✗ Failed to get status: {status_resp.status}")
                        return False
            else:
                print(f"✗ Failed to start streaming: {resp.status}")
                error = await resp.text()
                print(f"  Error: {error}")
                return False


async def monitor_redis_pubsub(duration: int = 30):
    """Monitor Redis pub/sub for candle updates."""
    print(f"\n4. Monitoring Redis pub/sub for {duration} seconds...")
    
    # Create Redis client
    r = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    
    # Subscribe to channels
    pubsub.subscribe("candles:all")
    for symbol in TEST_SYMBOLS:
        pubsub.subscribe(f"candles:{symbol}")
    
    print(f"✓ Subscribed to Redis channels")
    
    messages = []
    end_time = time.time() + duration
    
    while time.time() < end_time:
        message = pubsub.get_message(timeout=1.0)
        if message and message['type'] == 'message':
            try:
                data = json.loads(message['data'])
                messages.append(data)
                print(f"✓ Received candle update: {data['symbol']} @ {data['timestamp']}")
                print(f"  OHLCV: {data['data']['open']:.2f}/{data['data']['high']:.2f}/"
                      f"{data['data']['low']:.2f}/{data['data']['close']:.2f} "
                      f"Vol: {data['data']['volume']}")
            except json.JSONDecodeError:
                pass
    
    print(f"\n✓ Total messages received: {len(messages)}")
    
    # Cleanup
    pubsub.close()
    r.close()
    
    return messages


async def monitor_websocket_stream(duration: int = 30):
    """Monitor WebSocket for real-time updates."""
    print(f"\n5. Monitoring WebSocket stream for {duration} seconds...")
    
    messages = []
    
    try:
        uri = f"{WS_URL}?token={API_KEY}"
        
        async with websockets.connect(uri) as websocket:
            # Skip initial connection message
            await websocket.recv()
            
            # Subscribe to symbols
            subscribe_msg = {
                "type": "subscribe",
                "symbols": TEST_SYMBOLS
            }
            await websocket.send(json.dumps(subscribe_msg))
            await websocket.recv()  # Skip confirmation
            
            # Start streaming via WebSocket
            start_msg = {
                "type": "start_streaming",
                "symbols": TEST_SYMBOLS
            }
            await websocket.send(json.dumps(start_msg))
            
            # Monitor for updates
            end_time = time.time() + duration
            
            while time.time() < end_time:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    messages.append(data)
                    
                    if data['type'] == 'candle_update':
                        print(f"✓ WebSocket candle update: {data['symbol']} @ {data['timestamp']}")
                        candle = data['data']
                        print(f"  OHLCV: {candle['open']:.2f}/{candle['high']:.2f}/"
                              f"{candle['low']:.2f}/{candle['close']:.2f} "
                              f"Vol: {candle['volume']}")
                    else:
                        print(f"  Message type: {data['type']}")
                        
                except asyncio.TimeoutError:
                    continue
            
            print(f"\n✓ Total WebSocket messages: {len(messages)}")
            
    except Exception as e:
        print(f"✗ WebSocket monitoring error: {e}")
    
    return messages


async def test_current_candles():
    """Test getting current in-progress candles."""
    print("\n6. Testing current candles endpoint...")
    
    headers = {"X-API-Key": API_KEY}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{API_BASE_URL}/data/streaming/candles",
            headers=headers
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✓ Current candles: {data['count']} candles")
                for candle in data['candles'][:5]:  # Show first 5
                    print(f"  {candle['symbol']}: {candle['close']} @ {candle['timestamp']}")
                return True
            else:
                print(f"✗ Failed to get candles: {resp.status}")
                return False


async def cleanup_streaming():
    """Stop streaming service."""
    print("\n7. Cleaning up...")
    
    headers = {"X-API-Key": API_KEY}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_BASE_URL}/data/streaming/stop",
            headers=headers
        ) as resp:
            if resp.status == 200:
                print("✓ Streaming service stopped")
            else:
                print(f"✗ Failed to stop streaming: {resp.status}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Real-time Streaming Integration Test")
    print("=" * 60)
    
    # Check if services are running
    print("\nPre-flight checks:")
    print("- Ensure API server is running (uvicorn)")
    print("- Ensure Redis is running")
    print("- Ensure you have valid Schwab auth tokens")
    print(f"- Using symbols: {TEST_SYMBOLS}")
    
    # input("\nPress Enter to start tests...")  # Skip for automated test
    
    try:
        # Test 1: API Authentication
        auth_ok = await test_api_authentication()
        if not auth_ok:
            print("\n✗ Authentication failed. Check API_KEY in settings.")
            return
        
        # Test 2: WebSocket Connection
        ws_ok, ws_messages = await test_websocket_connection()
        if not ws_ok:
            print("\n✗ WebSocket connection failed.")
            return
        
        # Test 3: Start Streaming Service
        streaming_ok = await test_streaming_service()
        if not streaming_ok:
            print("\n✗ Streaming service failed to start.")
            print("Note: This test requires valid Schwab authentication.")
            print("If you don't have valid tokens, the streaming will fail.")
            return
        
        # Test 4 & 5: Monitor data flow (run concurrently)
        print("\n🔄 Monitoring real-time data flow...")
        print("Note: During market hours, you should see real-time updates.")
        print("Outside market hours, there may be no data.\n")
        
        redis_task = asyncio.create_task(monitor_redis_pubsub(10))
        ws_task = asyncio.create_task(monitor_websocket_stream(10))
        
        redis_messages, ws_messages = await asyncio.gather(redis_task, ws_task)
        
        # Test 6: Check current candles
        await test_current_candles()
        
        # Summary
        print("\n" + "=" * 60)
        print("Test Summary:")
        print(f"✓ API Authentication: OK")
        print(f"✓ WebSocket Connection: OK")
        print(f"✓ Streaming Service: OK")
        print(f"✓ Redis Pub/Sub Messages: {len(redis_messages)}")
        print(f"✓ WebSocket Stream Messages: {len(ws_messages)}")
        
        if len(redis_messages) == 0 and len(ws_messages) == 0:
            print("\n⚠️  No real-time data received.")
            print("   This is normal outside market hours.")
            print("   Try running during market hours (9:30 AM - 4:00 PM EST)")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        await cleanup_streaming()


if __name__ == "__main__":
    asyncio.run(main())