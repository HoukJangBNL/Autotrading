"""
Tests for WebSocket client with connection management and authentication.
"""

import asyncio
import json
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import websockets
from websockets.exceptions import ConnectionClosed

from src.data.websocket_client import (
    SchwabWebSocketClient,
    ConnectionState,
    MessageType
)
from src.data.stream_processor import StreamProcessor, Tick, TickType


class TestSchwabWebSocketClient:
    """Test suite for Schwab WebSocket client."""
    
    @pytest.fixture
    def mock_stream_processor(self):
        """Create mock stream processor."""
        processor = Mock(spec=StreamProcessor)
        processor.add_tick = AsyncMock()
        return processor
    
    @pytest.fixture
    def mock_auth_service(self):
        """Create mock auth service."""
        auth_service = Mock()
        auth_service.get_client = Mock()
        auth_service.initialize = AsyncMock()
        return auth_service
    
    @pytest.fixture
    async def client(self, mock_stream_processor, mock_auth_service):
        """Create WebSocket client instance."""
        client = SchwabWebSocketClient(
            stream_processor=mock_stream_processor,
            account_id="TEST123456",
            auth_service=mock_auth_service
        )
        yield client
        # Cleanup
        if client.state != ConnectionState.DISCONNECTED:
            await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_initial_state(self, client):
        """Test initial client state."""
        assert client.state == ConnectionState.DISCONNECTED
        assert client.websocket is None
        assert client.streaming_params is None
        assert len(client.subscriptions) == 0
        assert client._running is False
    
    @pytest.mark.asyncio
    async def test_get_streaming_params(self, client, mock_auth_service):
        """Test getting streaming parameters from auth service."""
        # Mock auth service response
        mock_client = Mock()
        mock_client.get_user_preferences = AsyncMock(return_value={
            'streamerInfo': [{
                'token': 'test_token',
                'appId': 'test_app',
                'streamerSocketUrl': 'wss://test.schwab.com/ws',
                'userGroup': 'ACCT',
                'accessLevel': '1',
                'acl': 'test_acl'
            }]
        })
        mock_auth_service.get_client.return_value = mock_client
        
        await client._get_streaming_params()
        
        assert client.streaming_params is not None
        assert client.streaming_params['token'] == 'test_token'
        assert client.streaming_params['app_id'] == 'test_app'
        assert client.streaming_params['streamer_url'] == 'wss://test.schwab.com/ws'
        assert client.WS_URL == 'wss://test.schwab.com/ws'
    
    @pytest.mark.asyncio
    async def test_build_credential(self, client):
        """Test credential string building."""
        client.streaming_params = {
            'token': 'test_token',
            'app_id': 'test_app',
            'user_group': 'ACCT',
            'access_level': '1',
            'acl': 'test_acl',
            'timestamp': 1640995200000
        }
        client.account_id = "SCHWAB-123456"
        
        credential = client._build_credential()
        
        assert 'userid=SCHWAB-123456' in credential
        assert 'token=test_token' in credential
        assert 'company=SCHWAB' in credential
        assert 'segment=ACCT' in credential
        assert 'appid=test_app' in credential
        assert 'authorized=Y' in credential
    
    @pytest.mark.asyncio
    @patch('websockets.connect')
    async def test_connect_success(self, mock_ws_connect, client, mock_auth_service):
        """Test successful WebSocket connection."""
        # Mock WebSocket connection
        mock_ws = AsyncMock()
        mock_ws_connect.return_value = mock_ws
        
        # Mock auth service
        mock_client = Mock()
        mock_client.get_user_preferences = AsyncMock(return_value={
            'streamerInfo': [{
                'token': 'test_token',
                'appId': 'test_app',
                'streamerSocketUrl': 'wss://test.schwab.com/ws',
                'userGroup': 'ACCT',
                'accessLevel': '1',
                'acl': 'test_acl'
            }]
        })
        mock_auth_service.get_client.return_value = mock_client
        
        # Mock authentication
        with patch.object(client, '_authenticate', new=AsyncMock()):
            with patch.object(client, '_heartbeat_loop', new=AsyncMock()):
                with patch.object(client, '_receive_loop', new=AsyncMock()):
                    success = await client.connect()
        
        assert success is True
        assert client.state == ConnectionState.AUTHENTICATED
        assert client.websocket is not None
        assert client._running is True
        mock_ws_connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_failure(self, client):
        """Test connection failure handling."""
        with patch('websockets.connect', side_effect=Exception("Connection failed")):
            with patch.object(client, '_get_streaming_params', new=AsyncMock()):
                success = await client.connect()
        
        assert success is False
        assert client.state == ConnectionState.ERROR
    
    @pytest.mark.asyncio
    async def test_authenticate(self, client):
        """Test authentication process."""
        # Setup client state
        client.streaming_params = {
            'token': 'test_token',
            'app_id': 'test_app',
            'user_group': 'ACCT',
            'access_level': '1',
            'acl': 'test_acl',
            'timestamp': 1640995200000
        }
        
        # Mock send_and_wait to return successful response
        mock_response = {
            'response': [{
                'content': {'code': 0, 'msg': 'Login successful'}
            }]
        }
        with patch.object(client, '_send_and_wait', return_value=mock_response):
            await client._authenticate()
        
        assert client.state == ConnectionState.AUTHENTICATED
    
    @pytest.mark.asyncio
    async def test_authenticate_failure(self, client):
        """Test authentication failure."""
        client.streaming_params = {'app_id': 'test_app'}
        
        # Mock send_and_wait to return error response
        mock_response = {
            'response': [{
                'content': {'code': 500, 'msg': 'Authentication failed'}
            }]
        }
        
        with patch.object(client, '_send_and_wait', return_value=mock_response):
            with pytest.raises(Exception, match="Authentication failed"):
                await client._authenticate()
    
    @pytest.mark.asyncio
    async def test_subscribe(self, client):
        """Test subscribing to symbols."""
        symbols = ["AAPL", "GOOGL"]
        data_types = ["QUOTE", "TRADE"]
        
        # When not authenticated, should queue subscription
        client.state = ConnectionState.CONNECTED
        await client.subscribe(symbols, data_types)
        
        assert len(client.pending_subscriptions) == 1
        assert client.pending_subscriptions[0]['symbols'] == symbols
        assert "QUOTE" in client.subscriptions
        assert "TRADE" in client.subscriptions
        assert "AAPL" in client.subscriptions["QUOTE"]
        assert "GOOGL" in client.subscriptions["QUOTE"]
    
    @pytest.mark.asyncio
    async def test_subscribe_when_authenticated(self, client):
        """Test subscribing when already authenticated."""
        client.state = ConnectionState.AUTHENTICATED
        client.streaming_params = {'app_id': 'test_app'}
        
        with patch.object(client, '_send_subscription_request', new=AsyncMock()) as mock_send:
            await client.subscribe(["AAPL"], ["QUOTE"])
        
        mock_send.assert_called_once_with(["AAPL"], ["QUOTE"])
        assert "AAPL" in client.subscriptions["QUOTE"]
    
    @pytest.mark.asyncio
    async def test_unsubscribe(self, client):
        """Test unsubscribing from symbols."""
        # Setup subscriptions
        client.subscriptions = {
            "QUOTE": {"AAPL", "GOOGL", "MSFT"},
            "TRADE": {"AAPL", "GOOGL"}
        }
        client.state = ConnectionState.AUTHENTICATED
        
        with patch.object(client, '_send_unsubscription_request', new=AsyncMock()):
            await client.unsubscribe(["AAPL", "GOOGL"], ["QUOTE"])
        
        assert "AAPL" not in client.subscriptions["QUOTE"]
        assert "GOOGL" not in client.subscriptions["QUOTE"]
        assert "MSFT" in client.subscriptions["QUOTE"]
        assert "AAPL" in client.subscriptions["TRADE"]  # Other data types unchanged
    
    @pytest.mark.asyncio
    async def test_send_subscription_request(self, client):
        """Test sending subscription request."""
        client.streaming_params = {'app_id': 'test_app'}
        client.websocket = AsyncMock()
        
        await client._send_subscription_request(["AAPL", "GOOGL"], ["QUOTE", "TRADE"])
        
        # Should send 2 requests (one for QUOTE, one for TIMESALE)
        call_args = client.websocket.send.call_args[0][0]
        message = json.loads(call_args)
        
        assert "requests" in message
        assert len(message["requests"]) == 2
        
        # Check QUOTE request
        quote_req = next(r for r in message["requests"] if r["service"] == "QUOTE")
        assert quote_req["command"] == "SUBS"
        assert quote_req["parameters"]["keys"] == "AAPL,GOOGL"
        
        # Check TIMESALE request (TRADE maps to TIMESALE)
        trade_req = next(r for r in message["requests"] if r["service"] == "TIMESALE")
        assert trade_req["command"] == "SUBS"
    
    @pytest.mark.asyncio
    async def test_heartbeat_loop(self, client):
        """Test heartbeat sending."""
        client._running = True
        client.state = ConnectionState.AUTHENTICATED
        client.streaming_params = {'app_id': 'test_app'}
        client.websocket = AsyncMock()
        
        # Run heartbeat loop for a short time
        heartbeat_task = asyncio.create_task(client._heartbeat_loop())
        await asyncio.sleep(0.1)
        client._running = False
        await heartbeat_task
        
        # Should have sent at least one heartbeat
        assert client.websocket.send.called
    
    @pytest.mark.asyncio
    async def test_receive_loop_data_message(self, client, mock_stream_processor):
        """Test receiving and processing data messages."""
        client._running = True
        client.websocket = AsyncMock()
        
        # Mock incoming message
        data_message = json.dumps({
            "data": [{
                "service": "QUOTE",
                "timestamp": 1640995200000,
                "content": [{
                    "key": "AAPL",
                    "BID_PRICE": 150.50,
                    "BID_SIZE": 100,
                    "ASK_PRICE": 150.55,
                    "ASK_SIZE": 200
                }]
            }]
        })
        
        client.websocket.recv = AsyncMock(side_effect=[data_message, ConnectionClosed(None, None)])
        
        # Run receive loop
        with patch.object(client, '_handle_connection_failure', new=AsyncMock()):
            await client._receive_loop()
        
        # Should have processed the tick
        assert mock_stream_processor.add_tick.called
        
        # Check tick details
        tick_calls = mock_stream_processor.add_tick.call_args_list
        assert len(tick_calls) >= 2  # At least bid and ask ticks
        
        # Verify bid tick
        bid_tick = tick_calls[0][0][0]
        assert bid_tick.symbol == "AAPL"
        assert bid_tick.price == 150.50
        assert bid_tick.tick_type == TickType.BID
    
    @pytest.mark.asyncio
    async def test_receive_loop_response_message(self, client):
        """Test receiving response messages."""
        client._running = True
        client.websocket = AsyncMock()
        
        # Setup pending request
        request_id = 123
        future = asyncio.Future()
        client._pending_requests[request_id] = future
        
        # Mock response message
        response_message = json.dumps({
            "response": [{
                "requestid": request_id,
                "service": "ADMIN",
                "command": "LOGIN",
                "content": {"code": 0, "msg": "Success"}
            }]
        })
        
        client.websocket.recv = AsyncMock(side_effect=[response_message, ConnectionClosed(None, None)])
        
        # Run receive loop
        with patch.object(client, '_handle_connection_failure', new=AsyncMock()):
            await client._receive_loop()
        
        # Future should be resolved
        assert future.done()
        result = future.result()
        assert result["response"][0]["requestid"] == request_id
    
    @pytest.mark.asyncio
    async def test_reconnect_with_backoff(self, client):
        """Test reconnection with exponential backoff."""
        client._running = True
        client._reconnect_attempts = 0
        
        # Mock connect to fail first 2 times, then succeed
        connect_results = [False, False, True]
        with patch.object(client, 'connect', side_effect=connect_results):
            with patch('asyncio.sleep', new=AsyncMock()) as mock_sleep:
                await client._reconnect()
        
        # Should have attempted 3 times
        assert client._reconnect_attempts == 3
        
        # Check backoff delays
        sleep_calls = mock_sleep.call_args_list
        assert len(sleep_calls) == 3
        assert sleep_calls[0][0][0] == 1  # First delay: 1 second
        assert sleep_calls[1][0][0] == 2  # Second delay: 2 seconds
        assert sleep_calls[2][0][0] == 4  # Third delay: 4 seconds
    
    @pytest.mark.asyncio
    async def test_reconnect_max_attempts(self, client):
        """Test reconnection stops after max attempts."""
        client._running = True
        client._reconnect_attempts = 0
        client.RECONNECT_MAX_ATTEMPTS = 3
        
        # Mock connect to always fail
        with patch.object(client, 'connect', return_value=False):
            with patch('asyncio.sleep', new=AsyncMock()):
                await client._reconnect()
        
        assert client._reconnect_attempts == 3
        assert client.state == ConnectionState.ERROR
    
    @pytest.mark.asyncio
    async def test_resubscribe_all(self, client):
        """Test resubscribing after reconnection."""
        # Setup previous subscriptions
        client.subscriptions = {
            "QUOTE": {"AAPL", "GOOGL"},
            "TRADE": {"MSFT"}
        }
        client.pending_subscriptions = [
            {'symbols': ['TSLA'], 'data_types': ['QUOTE']}
        ]
        
        with patch.object(client, '_send_subscription_request', new=AsyncMock()) as mock_send:
            await client._resubscribe_all()
        
        # Should send 3 subscription requests
        assert mock_send.call_count == 3
        
        # Check each call
        calls = mock_send.call_args_list
        # Order may vary due to dict iteration
        symbols_sent = []
        for call in calls:
            symbols_sent.extend(call[0][0])
        
        assert "AAPL" in symbols_sent
        assert "GOOGL" in symbols_sent
        assert "MSFT" in symbols_sent
        assert "TSLA" in symbols_sent
        
        # Pending subscriptions should be cleared
        assert len(client.pending_subscriptions) == 0
    
    @pytest.mark.asyncio
    async def test_disconnect(self, client):
        """Test graceful disconnection."""
        # Setup connected client
        client._running = True
        client.websocket = AsyncMock()
        client.state = ConnectionState.AUTHENTICATED
        
        # Create mock tasks
        client._heartbeat_task = AsyncMock()
        client._receive_task = AsyncMock()
        
        await client.disconnect()
        
        assert client._running is False
        assert client.state == ConnectionState.DISCONNECTED
        assert client.websocket.close.called
        assert client._heartbeat_task.cancel.called
        assert client._receive_task.cancel.called
    
    @pytest.mark.asyncio
    async def test_context_manager(self, mock_stream_processor, mock_auth_service):
        """Test using client as async context manager."""
        with patch('websockets.connect', new=AsyncMock()):
            with patch.object(SchwabWebSocketClient, '_authenticate', new=AsyncMock()):
                with patch.object(SchwabWebSocketClient, '_heartbeat_loop', new=AsyncMock()):
                    with patch.object(SchwabWebSocketClient, '_receive_loop', new=AsyncMock()):
                        async with SchwabWebSocketClient(
                            stream_processor=mock_stream_processor,
                            account_id="TEST123456",
                            auth_service=mock_auth_service
                        ) as client:
                            assert client.state == ConnectionState.AUTHENTICATED
                            assert client._running is True
        
        # After context exit, should be disconnected
        assert client.state == ConnectionState.DISCONNECTED
        assert client._running is False
    
    @pytest.mark.asyncio
    async def test_process_market_data_quote(self, client, mock_stream_processor):
        """Test processing QUOTE market data."""
        data = {
            'service': 'QUOTE',
            'timestamp': 1640995200000,
            'content': [{
                'key': 'AAPL',
                'BID_PRICE': 150.50,
                'BID_SIZE': 100,
                'ASK_PRICE': 150.55,
                'ASK_SIZE': 200
            }]
        }
        
        await client._process_market_data(data)
        
        # Should create bid and ask ticks
        assert mock_stream_processor.add_tick.call_count == 2
        
        # Check bid tick
        bid_tick = mock_stream_processor.add_tick.call_args_list[0][0][0]
        assert bid_tick.symbol == 'AAPL'
        assert bid_tick.price == 150.50
        assert bid_tick.volume == 100
        assert bid_tick.tick_type == TickType.BID
        
        # Check ask tick
        ask_tick = mock_stream_processor.add_tick.call_args_list[1][0][0]
        assert ask_tick.price == 150.55
        assert ask_tick.volume == 200
        assert ask_tick.tick_type == TickType.ASK
    
    @pytest.mark.asyncio
    async def test_process_market_data_timesale(self, client, mock_stream_processor):
        """Test processing TIMESALE market data."""
        data = {
            'service': 'TIMESALE',
            'timestamp': 1640995200000,
            'content': [{
                'key': 'AAPL',
                'LAST_PRICE': 150.52,
                'LAST_SIZE': 100,
                'SEQUENCE': 12345
            }]
        }
        
        await client._process_market_data(data)
        
        # Should create trade tick
        assert mock_stream_processor.add_tick.call_count == 1
        
        trade_tick = mock_stream_processor.add_tick.call_args[0][0]
        assert trade_tick.symbol == 'AAPL'
        assert trade_tick.price == 150.52
        assert trade_tick.volume == 100
        assert trade_tick.tick_type == TickType.TRADE
        assert trade_tick.sequence_id == 12345
    
    @pytest.mark.asyncio
    async def test_send_and_wait_timeout(self, client):
        """Test send_and_wait with timeout."""
        client.websocket = AsyncMock()
        
        # Don't resolve the future to trigger timeout
        message = {"requests": [{"requestid": 1}]}
        
        result = await client._send_and_wait(message, timeout=0.1)
        
        assert result is None
        assert len(client._pending_requests) == 0