#!/usr/bin/env python3
"""Phase 3 Quick WebSocket Test"""

import asyncio
import json
import websockets
from datetime import datetime

async def test_websocket():
    """Test WebSocket connection and basic functionality."""
    print("🔌 Testing WebSocket Connection...")
    
    uri = "ws://localhost:8000/ws?token=test-api-key-12345"
    
    try:
        async with websockets.connect(uri) as websocket:
            # 1. Connection test
            msg = await websocket.recv()
            data = json.loads(msg)
            print(f"✅ Connected: {data['type']} - {data['message']}")
            
            # 2. Subscribe test
            subscribe_msg = {"type": "subscribe", "symbols": ["AAPL", "MSFT"]}
            await websocket.send(json.dumps(subscribe_msg))
            
            msg = await websocket.recv()
            data = json.loads(msg)
            print(f"✅ Subscription confirmed: {data['symbols']}")
            
            # 3. Ping test
            ping_msg = {"type": "ping"}
            await websocket.send(json.dumps(ping_msg))
            
            msg = await websocket.recv()
            data = json.loads(msg)
            if data['type'] == 'pong':
                print("✅ Ping/Pong successful")
            
            return True
            
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        return False

async def main():
    success = await test_websocket()
    print(f"\n{'✅ WebSocket Test PASSED' if success else '❌ WebSocket Test FAILED'}")

if __name__ == "__main__":
    asyncio.run(main())