#!/usr/bin/env python3
"""Debug WebSocket connection issues"""

import asyncio
import websockets
import json
from urllib.parse import urlencode

async def test_websocket_auth():
    """Test WebSocket with different authentication methods."""
    
    # Test 1: URL parameter
    print("Test 1: WebSocket with URL token parameter")
    try:
        params = {"token": "test-api-key-12345"}
        uri = f"ws://localhost:8000/ws?{urlencode(params)}"
        print(f"Connecting to: {uri}")
        
        async with websockets.connect(uri) as ws:
            msg = await ws.recv()
            print(f"Received: {msg}")
            
            # Send ping
            await ws.send(json.dumps({"type": "ping"}))
            msg = await ws.recv()
            print(f"Ping response: {msg}")
            
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 2: No token
    print("\nTest 2: WebSocket without token")
    try:
        uri = "ws://localhost:8000/ws"
        print(f"Connecting to: {uri}")
        
        async with websockets.connect(uri) as ws:
            msg = await ws.recv()
            print(f"Received: {msg}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_auth())