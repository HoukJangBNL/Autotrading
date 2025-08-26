#!/usr/bin/env python3
"""Quick connectivity test for Phase 3 streaming."""

import requests
import asyncio
import websockets
import json
import redis

API_KEY = "test-api-key-12345"
BASE_URL = "http://localhost:8000"

def test_api():
    """Test API connectivity."""
    print("1. Testing API connectivity...")
    try:
        # Test health endpoint
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API server is healthy")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ API returned status: {response.status_code}")
        
        # Test auth endpoint
        headers = {"X-API-Key": API_KEY}
        response = requests.get(f"{BASE_URL}/api/auth/status", headers=headers, timeout=5)
        if response.status_code == 200:
            print("✅ Authentication successful")
        else:
            print(f"❌ Authentication failed: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API server")
    except requests.exceptions.Timeout:
        print("❌ API server timeout")
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_websocket():
    """Test WebSocket connectivity."""
    print("\n2. Testing WebSocket connectivity...")
    try:
        uri = f"ws://localhost:8000/ws?token={API_KEY}"
        async with websockets.connect(uri, timeout=5) as websocket:
            # Wait for connection message
            message = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(message)
            if data.get('type') == 'connected':
                print("✅ WebSocket connected")
                print(f"   Message: {data.get('message')}")
            else:
                print(f"❌ Unexpected message: {data}")
                
    except asyncio.TimeoutError:
        print("❌ WebSocket timeout")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")


def test_redis():
    """Test Redis connectivity."""
    print("\n3. Testing Redis connectivity...")
    try:
        r = redis.Redis(host='localhost', port=6379, password='redis123', decode_responses=True)
        if r.ping():
            print("✅ Redis connected")
            # Test pub/sub
            pubsub = r.pubsub()
            pubsub.subscribe('test_channel')
            print("✅ Redis pub/sub working")
            pubsub.close()
        else:
            print("❌ Redis ping failed")
    except redis.ConnectionError:
        print("❌ Cannot connect to Redis")
    except Exception as e:
        print(f"❌ Redis error: {e}")


async def main():
    """Run all tests."""
    print("=" * 50)
    print("Phase 3 Streaming Quick Test")
    print("=" * 50)
    
    # Test API
    test_api()
    
    # Test WebSocket
    await test_websocket()
    
    # Test Redis
    test_redis()
    
    print("\n" + "=" * 50)
    print("Test Complete")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())