#!/usr/bin/env python3
"""Debug WebSocket subscription issues"""

import asyncio
import websockets
import json

async def test_subscribe():
    """Test WebSocket subscription functionality."""
    uri = "ws://localhost:8000/ws?token=test-api-key-12345"
    
    try:
        async with websockets.connect(uri) as ws:
            # Wait for connection message
            msg = await ws.recv()
            data = json.loads(msg)
            print(f"1. Connected: {data['type']}")
            
            # Test subscription
            print("\n2. Sending subscribe request...")
            subscribe_msg = {
                "type": "subscribe",
                "symbols": ["AAPL", "MSFT"]
            }
            await ws.send(json.dumps(subscribe_msg))
            print("   Sent: ", subscribe_msg)
            
            # Wait for response
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(msg)
                print(f"   Response: {data}")
            except asyncio.TimeoutError:
                print("   ❌ Timeout waiting for response")
            except Exception as e:
                print(f"   ❌ Error: {e}")
                
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(test_subscribe())