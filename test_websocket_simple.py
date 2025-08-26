#!/usr/bin/env python3
"""
Simple WebSocket test client for development and debugging.
"""

import asyncio
import json
import websockets
from datetime import datetime

# Configuration
WS_URL = "ws://localhost:8000/ws"
API_KEY = "test-api-key-12345"  # Should match your settings

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


async def websocket_client():
    """Simple WebSocket client for testing."""
    uri = f"{WS_URL}?token={API_KEY}"
    
    print(f"{Colors.HEADER}Connecting to WebSocket...{Colors.ENDC}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"{Colors.OKGREEN}✓ Connected to {uri}{Colors.ENDC}")
            
            # Create tasks for sending and receiving
            receive_task = asyncio.create_task(receive_messages(websocket))
            send_task = asyncio.create_task(send_commands(websocket))
            
            # Wait for both tasks
            await asyncio.gather(receive_task, send_task)
            
    except websockets.exceptions.ConnectionClosed:
        print(f"{Colors.WARNING}Connection closed by server{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}Error: {e}{Colors.ENDC}")


async def receive_messages(websocket):
    """Receive and display messages from server."""
    try:
        async for message in websocket:
            data = json.loads(message)
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            msg_type = data.get('type', 'unknown')
            
            # Color code by message type
            if msg_type == 'error':
                color = Colors.FAIL
            elif msg_type == 'connected' or msg_type == 'subscription_confirmed':
                color = Colors.OKGREEN
            elif msg_type == 'candle_update':
                color = Colors.OKCYAN
            else:
                color = Colors.OKBLUE
            
            print(f"\n{Colors.BOLD}[{timestamp}] Received:{Colors.ENDC}")
            print(f"{color}Type: {msg_type}{Colors.ENDC}")
            
            # Special handling for candle updates
            if msg_type == 'candle_update':
                symbol = data.get('symbol', 'N/A')
                candle = data.get('data', {})
                print(f"Symbol: {symbol}")
                print(f"OHLC: {candle.get('open', 0):.2f} / {candle.get('high', 0):.2f} / "
                      f"{candle.get('low', 0):.2f} / {candle.get('close', 0):.2f}")
                print(f"Volume: {candle.get('volume', 0):,}")
            else:
                # Pretty print the data
                print(json.dumps(data, indent=2))
                
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"{Colors.FAIL}Receive error: {e}{Colors.ENDC}")


async def send_commands(websocket):
    """Interactive command sender."""
    await asyncio.sleep(0.5)  # Wait a bit for connection message
    
    print(f"\n{Colors.HEADER}WebSocket Test Client{Colors.ENDC}")
    print(f"{Colors.OKBLUE}Commands:{Colors.ENDC}")
    print("  1. Subscribe to symbols")
    print("  2. Start streaming")
    print("  3. Stop streaming")
    print("  4. Get status")
    print("  5. Send ping")
    print("  6. Custom JSON message")
    print("  q. Quit")
    print("")
    
    try:
        while True:
            # Get user input
            command = await asyncio.get_event_loop().run_in_executor(
                None, input, f"{Colors.BOLD}Enter command: {Colors.ENDC}"
            )
            
            if command.lower() == 'q':
                print(f"{Colors.WARNING}Closing connection...{Colors.ENDC}")
                break
            
            message = None
            
            if command == '1':
                symbols = input("Enter symbols (comma-separated): ").upper().split(',')
                symbols = [s.strip() for s in symbols if s.strip()]
                message = {
                    "type": "subscribe",
                    "symbols": symbols
                }
                
            elif command == '2':
                symbols = input("Enter symbols to stream (comma-separated): ").upper().split(',')
                symbols = [s.strip() for s in symbols if s.strip()]
                message = {
                    "type": "start_streaming",
                    "symbols": symbols
                }
                
            elif command == '3':
                message = {"type": "stop_streaming"}
                
            elif command == '4':
                message = {"type": "get_status"}
                
            elif command == '5':
                message = {"type": "ping"}
                
            elif command == '6':
                json_str = input("Enter JSON message: ")
                try:
                    message = json.loads(json_str)
                except json.JSONDecodeError:
                    print(f"{Colors.FAIL}Invalid JSON{Colors.ENDC}")
                    continue
            
            if message:
                print(f"\n{Colors.OKBLUE}Sending: {json.dumps(message)}{Colors.ENDC}")
                await websocket.send(json.dumps(message))
            
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"{Colors.FAIL}Send error: {e}{Colors.ENDC}")


async def main():
    """Run the WebSocket client."""
    try:
        await websocket_client()
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Interrupted by user{Colors.ENDC}")


if __name__ == "__main__":
    asyncio.run(main())