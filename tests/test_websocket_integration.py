"""
Integration tests for WebSocket streaming pipeline.

These tests verify the complete flow from WebSocket connection through
to processed market data and bar generation.
"""

import asyncio
import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
import websockets
from contextlib import asynccontextmanager

from src.data.websocket_client import SchwabWebSocketClient, ConnectionState
from src.data.websocket_parser import SchwabMessageParser, MessageType, ServiceType
from src.data.streaming_service import StreamingService, create_streaming_service
from src.data.stream_processor import (
    StreamProcessor,
    Tick,
    TickType,
    OHLCV,
    create_stream_processor
)


class MockWebSocketServer:
    """Mock WebSocket server for testing."""
    
    def __init__(self):
        self.messages_to_send = []
        self.received_messages = []
        self.connected_clients = []
        self.should_authenticate = True
        
    async def handler(self, websocket):
        """WebSocket connection handler."""
        print(f"MockWebSocketServer: New client connected")
        self.connected_clients.append(websocket)
        
        try:
            async for message in websocket:
                print(f"MockWebSocketServer: Received message: {message[:100]}...")
                self.received_messages.append(json.loads(message))
                
                # Handle authentication
                msg_data = json.loads(message)
                if "requests" in msg_data:
                    print(f"MockWebSocketServer: Processing requests")
                    for request in msg_data["requests"]:
                        print(f"MockWebSocketServer: Request command: {request.get('command')}")
                        if request.get("command") == "LOGIN":
                            if self.should_authenticate:
                                response = {
                                    "response": [{
                                        "service": "ADMIN",
                                        "command": "LOGIN",
                                        "requestid": request["requestid"],
                                        "content": {"code": 0, "msg": "Login successful"}
                                    }]
                                }
                                response_str = json.dumps(response)
                                print(f"MockWebSocketServer: Sending LOGIN response: {response_str}")
                                await websocket.send(response_str)
                                print(f"MockWebSocketServer: LOGIN response sent")
                            else:
                                response = {
                                    "response": [{
                                        "service": "ADMIN",
                                        "command": "LOGIN",
                                        "requestid": request["requestid"],
                                        "content": {"code": 500, "msg": "Authentication failed"}
                                    }]
                                }
                                await websocket.send(json.dumps(response))
                        
                        elif request.get("command") == "SUBS":
                            # Send subscription confirmation
                            response = {
                                "response": [{
                                    "service": request["service"],
                                    "command": "SUBS",
                                    "requestid": request["requestid"],
                                    "content": {"code": 0, "msg": "Subscription successful"}
                                }]
                            }
                            await websocket.send(json.dumps(response))
                            
                            # Start sending data
                            await self.send_market_data(websocket, request["parameters"]["keys"])
                        
                        elif request.get("command") == "HEARTBEAT":
                            # Echo heartbeat
                            response = {
                                "notify": [{
                                    "service": "ADMIN",
                                    "content": {"code": 0, "msg": "Heartbeat"}
                                }]
                            }
                            await websocket.send(json.dumps(response))
                            
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.connected_clients.remove(websocket)
    
    async def send_market_data(self, websocket, symbols_str):
        """Send mock market data."""
        symbols = symbols_str.split(",")
        
        # Send initial quote data
        for symbol in symbols:
            quote_data = {
                "data": [{
                    "service": "QUOTE",
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "content": [{
                        "key": symbol,
                        "1": 150.50,  # BID_PRICE
                        "2": 150.55,  # ASK_PRICE
                        "3": 150.52,  # LAST_PRICE
                        "4": 100,     # BID_SIZE
                        "5": 200,     # ASK_SIZE
                        "9": 50,      # LAST_SIZE
                        "8": 123456,  # TOTAL_VOLUME
                        "50": int(datetime.now(timezone.utc).timestamp() * 1000),  # QUOTE_TIME
                        "51": int(datetime.now(timezone.utc).timestamp() * 1000)   # TRADE_TIME
                    }]
                }]
            }
            await websocket.send(json.dumps(quote_data))
            
            # Send trade data
            trade_data = {
                "data": [{
                    "service": "TIMESALE",
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "content": [{
                        "key": symbol,
                        "0": symbol,
                        "1": int(datetime.now(timezone.utc).timestamp() * 1000),
                        "2": 150.52,
                        "3": 100,
                        "4": 12345
                    }]
                }]
            }
            await websocket.send(json.dumps(trade_data))


class TestWebSocketIntegration:
    """Integration tests for complete WebSocket pipeline."""
    
    @pytest.fixture
    async def mock_server(self):
        """Create and start mock WebSocket server."""
        server = MockWebSocketServer()
        
        # Start server on a test port
        async with websockets.serve(
            server.handler,
            "localhost",
            8765
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
                'streamerSocketUrl': 'ws://localhost:8765',
                'userGroup': 'ACCT',
                'accessLevel': '1',
                'acl': 'test_acl'
            }]
        })
        auth_service.get_client = Mock(return_value=mock_client)
        auth_service.initialize = AsyncMock()
        return auth_service
    
    @pytest.mark.asyncio
    async def test_full_streaming_pipeline(self, mock_server, mock_auth_service):
        """Test complete streaming pipeline from connection to bar generation."""
        # Track processed data
        processed_ticks = []
        completed_bars = []
        
        # Create stream processor
        stream_processor = await create_stream_processor(
            redis_url=None,
            save_to_db=False,
            timeframes=[1]
        )
        
        # Register callbacks
        @stream_processor.on_tick
        async def on_tick(tick: Tick):
            processed_ticks.append(tick)
        
        @stream_processor.on_bar
        async def on_bar(bar: OHLCV):
            completed_bars.append(bar)
        
        # Create and connect WebSocket client
        with patch('src.data.websocket_client.get_auth_service', return_value=mock_auth_service):
            client = SchwabWebSocketClient(
                stream_processor=stream_processor,
                account_id="TEST123456",
                auth_service=mock_auth_service
            )
            
            # Override URL to use test server
            client.WS_URL = "ws://localhost:8765"
            
            # Connect and subscribe
            success = await client.connect()
            assert success is True
            assert client.state == ConnectionState.AUTHENTICATED
            
            await client.subscribe(["AAPL", "GOOGL"], ["QUOTE", "TRADE"])
            
            # Wait for data to be processed
            await asyncio.sleep(0.5)
            
            # Verify data was received and processed
            assert len(processed_ticks) > 0
            
            # Check tick details
            aapl_ticks = [t for t in processed_ticks if t.symbol == "AAPL"]
            assert len(aapl_ticks) > 0
            
            # Should have bid, ask, and trade ticks
            tick_types = {t.tick_type for t in aapl_ticks}
            assert TickType.BID in tick_types
            assert TickType.ASK in tick_types
            assert TickType.TRADE in tick_types
            
            # Verify tick data
            bid_tick = next(t for t in aapl_ticks if t.tick_type == TickType.BID)
            assert bid_tick.price == 150.50
            assert bid_tick.volume == 100
            
            # Cleanup
            await client.disconnect()
            await stream_processor.stop()
    
    @pytest.mark.asyncio
    async def test_streaming_service_integration(self, mock_server, mock_auth_service):
        """Test StreamingService high-level integration."""
        # Track callbacks
        connection_states = []
        health_updates = []
        
        # Create streaming service
        with patch('src.auth.auth_service.get_auth_service', return_value=mock_auth_service):
            with patch('src.data.websocket_client.get_auth_service', return_value=mock_auth_service):
                service = StreamingService(
                    account_id="TEST123456",
                    redis_url=None,
                    save_to_db=False,
                    timeframes=[1]
                )
                
                # Register callbacks
                @service.on_connection_change
                async def on_connection(connected: bool):
                    connection_states.append(connected)
                
                # Override WebSocket URL in initialization
                original_init = service.initialize
                async def patched_init():
                    await original_init()
                    if service.websocket_client:
                        service.websocket_client.WS_URL = "ws://localhost:8765"
                
                service.initialize = patched_init
                
                # Start streaming
                await service.start_streaming(["AAPL"])
                
                # Wait for connection and data
                await asyncio.sleep(0.5)
                
                # Verify connection callback
                assert True in connection_states
                
                # Check statistics
                stats = service.get_statistics()
                assert stats['messages_received'] > 0
                assert stats['ticks_processed'] > 0
                assert "AAPL" in stats['subscribed_symbols']
                assert stats['connection_attempts'] == 1
                assert stats['successful_connections'] == 1
                
                # Check health
                health = service.get_health_status()
                assert health['streaming_service'] == 'running'
                assert health['websocket']['connected'] is True
                
                # Get recent data
                ticks = service.get_recent_ticks("AAPL")
                assert len(ticks) > 0
                
                # Add another symbol
                await service.add_symbols(["GOOGL"])
                await asyncio.sleep(0.2)
                
                assert "GOOGL" in service.stats.subscribed_symbols
                
                # Stop streaming
                await service.stop_streaming()
                
                # Verify disconnection callback
                assert False in connection_states
    
    @pytest.mark.asyncio
    async def test_reconnection_handling(self, mock_auth_service):
        """Test automatic reconnection on connection loss."""
        reconnect_count = 0
        
        class ReconnectTestServer:
            def __init__(self):
                self.connection_count = 0
                
            async def handler(self, websocket):
                self.connection_count += 1
                
                # First connection: authenticate then close
                if self.connection_count == 1:
                    message = await websocket.recv()
                    msg_data = json.loads(message)
                    
                    # Send auth response
                    response = {
                        "response": [{
                            "service": "ADMIN",
                            "command": "LOGIN",
                            "requestid": msg_data["requests"][0]["requestid"],
                            "content": {"code": 0, "msg": "Login successful"}
                        }]
                    }
                    await websocket.send(json.dumps(response))
                    
                    # Close connection after 0.2 seconds
                    await asyncio.sleep(0.2)
                    await websocket.close()
                    
                # Second connection: stay connected
                else:
                    await mock_server.handler(websocket)
        
        server = ReconnectTestServer()
        mock_server = MockWebSocketServer()
        
        async with websockets.serve(server.handler, "localhost", 8766):
            # Create stream processor
            stream_processor = await create_stream_processor(
                redis_url=None,
                save_to_db=False
            )
            
            # Create WebSocket client with fast reconnect for testing
            with patch('src.data.websocket_client.get_auth_service', return_value=mock_auth_service):
                client = SchwabWebSocketClient(
                    stream_processor=stream_processor,
                    account_id="TEST123456",
                    auth_service=mock_auth_service
                )
                
                # Override settings for faster testing BEFORE connecting
                # Need to override the URL before any connection attempt
                await client._get_streaming_params()  # Load params first
                client.WS_URL = "ws://localhost:8766"  # Then override URL
                client.RECONNECT_BASE_DELAY = 0.1
                client.HEARTBEAT_INTERVAL = 0.5
                
                # Connect
                success = await client.connect()
                assert success is True
                
                # Wait for disconnection and reconnection
                await asyncio.sleep(1.0)
                
                # Should have reconnected
                assert server.connection_count >= 2
                
                # Cleanup
                await client.disconnect()
                await stream_processor.stop()
    
    @pytest.mark.asyncio
    async def test_parser_integration(self):
        """Test message parser with various message formats."""
        parser = SchwabMessageParser()
        
        # Test complete message flow
        messages = [
            # Login response
            {
                "response": [{
                    "service": "ADMIN",
                    "command": "LOGIN",
                    "requestid": 1,
                    "content": {"code": 0, "msg": "Login successful"}
                }]
            },
            # Quote data with all fields
            {
                "data": [{
                    "service": "QUOTE",
                    "timestamp": 1640995200000,
                    "content": [{
                        "key": "AAPL",
                        "1": 150.50,
                        "2": 150.55,
                        "3": 150.52,
                        "4": 100,
                        "5": 200,
                        "9": 50,
                        "8": 123456,
                        "12": 151.00,
                        "13": 150.00,
                        "28": 150.25,
                        "39": "NASDAQ"
                    }]
                }]
            },
            # Time & Sales data
            {
                "data": [{
                    "service": "TIMESALE",
                    "timestamp": 1640995200000,
                    "content": [{
                        "key": "AAPL",
                        "1": 1640995200000,
                        "2": 150.52,
                        "3": 100,
                        "4": 12345
                    }]
                }]
            },
            # Heartbeat notification
            {
                "notify": [{
                    "service": "ADMIN",
                    "content": {"code": 0, "msg": "Heartbeat"}
                }]
            }
        ]
        
        parsed_messages = []
        all_ticks = []
        
        for msg in messages:
            parsed = parser.parse(msg)
            parsed_messages.append(parsed)
            
            if parsed.is_data_message:
                ticks = parser.to_ticks(parsed)
                all_ticks.extend(ticks)
        
        # Verify parsing
        assert len(parsed_messages) == 4
        
        # Check message types
        assert parsed_messages[0].message_type == MessageType.RESPONSE
        assert parsed_messages[1].message_type == MessageType.DATA
        assert parsed_messages[2].message_type == MessageType.DATA
        assert parsed_messages[3].message_type == MessageType.NOTIFY
        
        # Check service types
        assert parsed_messages[0].service == ServiceType.ADMIN
        assert parsed_messages[1].service == ServiceType.QUOTE
        assert parsed_messages[2].service == ServiceType.TIMESALE
        
        # Verify tick extraction
        assert len(all_ticks) > 0
        
        # Check quote ticks
        quote_ticks = [t for t in all_ticks if t.timestamp.timestamp() * 1000 == 1640995200000]
        assert any(t.tick_type == TickType.BID for t in quote_ticks)
        assert any(t.tick_type == TickType.ASK for t in quote_ticks)
        
        # Check extracted data
        quote_data = parser.extract_quotes(parsed_messages[1].content[0])
        assert quote_data["symbol"] == "AAPL"
        assert quote_data["bid_price"] == 150.50
        assert quote_data["high"] == 151.00
        assert quote_data["low"] == 150.00
        assert quote_data["exchange"] == "NASDAQ"
    
    @pytest.mark.asyncio
    async def test_volume_profile_generation(self, mock_server, mock_auth_service):
        """Test volume profile generation from streaming data."""
        # Create stream processor
        stream_processor = await create_stream_processor(
            redis_url=None,
            save_to_db=False
        )
        
        # Create streaming service
        with patch('src.auth.auth_service.get_auth_service', return_value=mock_auth_service):
            with patch('src.data.websocket_client.get_auth_service', return_value=mock_auth_service):
                service = await create_streaming_service(
                    account_id="TEST123456",
                    symbols=["AAPL"],
                    redis_url=None,
                    save_to_db=False
                )
                
                # Override WebSocket URL
                service.websocket_client.WS_URL = "ws://localhost:8765"
                
                # Reconnect with new URL
                await service.websocket_client.disconnect()
                await service.websocket_client.connect()
                await service.websocket_client.subscribe(["AAPL"], ["QUOTE", "TRADE"])
                
                # Wait for data
                await asyncio.sleep(0.5)
                
                # Get volume profile
                profile = service.get_volume_profile("AAPL")
                
                assert profile is not None
                assert profile['symbol'] == "AAPL"
                assert profile['poc'] is not None  # Point of Control
                assert profile['total_volume'] > 0
                assert len(profile['price_levels']) > 0
                
                # Cleanup
                await service.stop_streaming()
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, mock_auth_service):
        """Test error handling throughout the pipeline."""
        errors_captured = []
        
        # Create streaming service
        service = StreamingService(
            account_id="TEST123456",
            redis_url=None,
            save_to_db=False
        )
        
        # Register error callback
        @service.on_error
        async def on_error(error: Exception):
            errors_captured.append(error)
        
        # Try to connect to non-existent server
        with patch('src.data.websocket_client.get_auth_service', return_value=mock_auth_service):
            # Override with bad URL
            original_init = service.initialize
            async def patched_init():
                await original_init()
                if service.websocket_client:
                    service.websocket_client.WS_URL = "ws://localhost:9999"  # Non-existent
            
            service.initialize = patched_init
            
            # Should fail to connect
            with pytest.raises(RuntimeError, match="Failed to establish WebSocket connection"):
                await service.start_streaming(["AAPL"])
        
        # Should have captured error
        assert len(errors_captured) > 0
        assert service.stats.errors > 0