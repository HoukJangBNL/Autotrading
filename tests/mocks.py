"""Standardized mock factories for consistent testing."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Any
from unittest.mock import Mock, AsyncMock, MagicMock

import httpx


def create_mock_auth_service():
    """Create standard mock auth service with all common methods."""
    auth = AsyncMock()
    auth.initialize = AsyncMock()
    auth.ensure_authenticated = AsyncMock()
    auth.shutdown = AsyncMock()
    auth.is_initialized = Mock(return_value=True)
    auth.has_valid_client = Mock(return_value=True)
    auth.test_authentication = AsyncMock(return_value=True)
    
    # Mock client getter
    mock_client = create_mock_schwab_client()
    auth.get_client = Mock(return_value=mock_client)
    auth.get_authenticated_client = AsyncMock(return_value=mock_client)
    
    return auth


def create_mock_schwab_client():
    """Create standard mock Schwab API client with all methods."""
    client = AsyncMock()
    
    # Standard successful response
    def create_response(data: Any = None, status_code: int = 200):
        response = Mock(spec=httpx.Response)
        response.status_code = status_code
        response.json.return_value = data or {}
        response.headers = {}
        response.raise_for_status = Mock()
        return response
    
    # Account methods
    client.get_account_numbers = AsyncMock(
        return_value=create_response([
            {"accountNumber": "12345678", "hashValue": "hash1234"},
            {"accountNumber": "87654321", "hashValue": "hash8765"}
        ])
    )
    
    client.get_account = AsyncMock(
        return_value=create_response({
            "accountNumber": "12345678",
            "positions": [],
            "balances": {
                "cashBalance": 10000.00,
                "equity": 15000.00
            }
        })
    )
    
    # Market data methods
    client.get_quotes = AsyncMock(
        return_value=create_response({
            "AAPL": {
                "symbol": "AAPL",
                "lastPrice": 150.00,
                "bidPrice": 149.95,
                "askPrice": 150.05,
                "volume": 50000000
            }
        })
    )
    
    client.get_price_history = AsyncMock(
        return_value=create_response({
            "candles": [
                {
                    "datetime": 1642435200000,
                    "open": 149.50,
                    "high": 151.00,
                    "low": 149.00,
                    "close": 150.50,
                    "volume": 1000000
                }
            ]
        })
    )
    
    # Order methods
    client.place_order = AsyncMock(
        return_value=create_response(status_code=201)
    )
    
    client.cancel_order = AsyncMock(
        return_value=create_response(status_code=200)
    )
    
    client.get_order = AsyncMock(
        return_value=create_response({
            "orderId": "ORD123",
            "status": "FILLED",
            "symbol": "AAPL",
            "quantity": 100,
            "price": 150.00
        })
    )
    
    # User preferences (for WebSocket)
    client.get_user_preferences = AsyncMock(
        return_value={
            'streamerInfo': [{
                'token': 'test_token',
                'appId': 'test_app',
                'streamerSocketUrl': 'ws://localhost:8765',
                'userGroup': 'ACCT',
                'accessLevel': '1',
                'acl': 'test_acl'
            }]
        }
    )
    
    # General methods
    client.get = AsyncMock(return_value=create_response())
    client.post = AsyncMock(return_value=create_response())
    client.put = AsyncMock(return_value=create_response())
    client.delete = AsyncMock(return_value=create_response())
    
    return client


def create_mock_redis():
    """Create mock Redis client with all common methods."""
    redis = AsyncMock()
    
    # Basic operations
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=0)
    redis.expire = AsyncMock(return_value=True)
    redis.ttl = AsyncMock(return_value=-1)
    
    # Pub/Sub operations
    redis.publish = AsyncMock(return_value=1)
    redis.subscribe = AsyncMock()
    redis.unsubscribe = AsyncMock()
    redis.psubscribe = AsyncMock()
    redis.punsubscribe = AsyncMock()
    
    # List operations
    redis.lpush = AsyncMock(return_value=1)
    redis.rpush = AsyncMock(return_value=1)
    redis.lpop = AsyncMock(return_value=None)
    redis.rpop = AsyncMock(return_value=None)
    redis.llen = AsyncMock(return_value=0)
    
    # Hash operations
    redis.hset = AsyncMock(return_value=1)
    redis.hget = AsyncMock(return_value=None)
    redis.hgetall = AsyncMock(return_value={})
    redis.hdel = AsyncMock(return_value=1)
    
    # Connection
    redis.close = AsyncMock()
    redis.wait_closed = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    
    return redis


def create_mock_stream_processor():
    """Create mock stream processor."""
    processor = AsyncMock()
    
    # Attributes
    processor.running = False
    processor.tick_queue = Mock()
    processor.tick_queue.qsize = Mock(return_value=0)
    processor.tick_queue.put_nowait = Mock()
    
    # Methods
    processor.start = AsyncMock()
    processor.stop = AsyncMock()
    processor.add_tick = AsyncMock()
    processor.get_ohlcv = Mock(return_value=None)
    processor.get_volume_profile = Mock(return_value=None)
    processor.on_tick = Mock()
    processor.on_bar = Mock()
    
    # Health monitoring
    processor.health_monitors = {}
    processor.get_stream_health = Mock(return_value={
        "tick_count": 0,
        "error_count": 0,
        "avg_latency_ms": 0.0,
        "is_healthy": True
    })
    
    return processor


def create_mock_websocket():
    """Create mock WebSocket connection."""
    ws = AsyncMock()
    
    # Connection state
    ws.closed = False
    ws.close_code = None
    ws.close_reason = None
    
    # Methods
    ws.send = AsyncMock()
    ws.recv = AsyncMock(return_value='{"type": "heartbeat"}')
    ws.close = AsyncMock()
    ws.ping = AsyncMock()
    ws.pong = AsyncMock()
    
    # Iterator support
    async def mock_iterator():
        yield '{"type": "heartbeat"}'
    
    ws.__aiter__ = Mock(return_value=mock_iterator())
    
    return ws


def create_sample_tick(
    symbol: str = "AAPL",
    price: float = 150.00,
    timestamp: Optional[datetime] = None
) -> Dict[str, Any]:
    """Create sample tick data."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    
    return {
        "symbol": symbol,
        "timestamp": timestamp.isoformat(),
        "bid_price": price - 0.05,
        "ask_price": price + 0.05,
        "last_price": price,
        "bid_size": 100,
        "ask_size": 100,
        "volume": 1000
    }


def create_sample_ohlcv(
    symbol: str = "AAPL",
    timestamp: Optional[datetime] = None
) -> Dict[str, Any]:
    """Create sample OHLCV candle data."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    
    return {
        "symbol": symbol,
        "timestamp": timestamp.isoformat(),
        "open": 149.50,
        "high": 151.00,
        "low": 149.00,
        "close": 150.50,
        "volume": 1000000,
        "vwap": 150.00
    }


def create_sample_order(
    symbol: str = "AAPL",
    action: str = "BUY",
    quantity: int = 100,
    order_type: str = "LIMIT",
    price: Optional[float] = 150.00
) -> Dict[str, Any]:
    """Create sample order data."""
    order = {
        "symbol": symbol,
        "action": action,
        "quantity": quantity,
        "orderType": order_type,
        "timeInForce": "DAY",
        "accountNumber": "12345678"
    }
    
    if order_type == "LIMIT" and price:
        order["price"] = price
    
    return order


def create_sample_position(
    symbol: str = "AAPL",
    quantity: int = 100,
    entry_price: float = 150.00
) -> Dict[str, Any]:
    """Create sample position data."""
    current_price = entry_price * 1.02  # 2% profit
    
    return {
        "symbol": symbol,
        "quantity": quantity,
        "averagePrice": entry_price,
        "currentPrice": current_price,
        "marketValue": quantity * current_price,
        "unrealizedPL": quantity * (current_price - entry_price),
        "realizedPL": 0.0
    }


def create_error_response(
    status_code: int = 400,
    error_message: str = "Bad Request"
) -> Mock:
    """Create mock error response."""
    response = Mock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = {
        "error": error_message,
        "message": error_message
    }
    response.headers = {}
    response.raise_for_status = Mock(
        side_effect=httpx.HTTPStatusError(
            message=error_message,
            request=Mock(),
            response=response
        )
    )
    return response