"""Comprehensive tests for SchwabBroker client."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import httpx

from src.broker import (
    SchwabBroker,
    get_schwab_broker,
    RateLimiter,
    CircuitBreaker,
    BrokerError,
    BrokerConnectionError,
    RateLimitError,
    InvalidOrderError,
    OrderNotFoundError,
    PositionNotFoundError,
    MarketDataError,
)
from src.broker.exceptions import InsufficientFundsError
from src.auth.exceptions import AuthenticationError


@pytest.fixture
def mock_auth_service():
    """Create mock auth service."""
    auth_service = AsyncMock()
    auth_service.initialize = AsyncMock()
    auth_service.get_authenticated_client = AsyncMock()
    return auth_service


@pytest.fixture
def mock_client():
    """Create mock Schwab client."""
    client = AsyncMock()
    
    # Mock successful responses
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_response.headers = {}
    
    client.get = AsyncMock(return_value=mock_response)
    client.post = AsyncMock(return_value=mock_response)
    client.put = AsyncMock(return_value=mock_response)
    client.delete = AsyncMock(return_value=mock_response)
    
    return client


@pytest.fixture
async def schwab_broker(mock_auth_service, mock_client):
    """Create SchwabBroker instance with mocks."""
    mock_auth_service.get_authenticated_client.return_value = mock_client
    
    # Reset singleton
    SchwabBroker._instance = None
    SchwabBroker._initialized = False
    
    broker = SchwabBroker(auth_service=mock_auth_service)
    
    # Mock account loading
    with patch.object(broker, '_load_account_numbers', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = None
        broker._account_numbers = ['12345678', '87654321']
        broker._account_hash_map = {
            '12345678': 'hash1234',
            '87654321': 'hash8765'
        }
        await broker.initialize()
    
    return broker


class TestSchwabBrokerSingleton:
    """Test singleton pattern implementation."""
    
    def test_singleton_instance(self):
        """Test that only one instance is created."""
        broker1 = SchwabBroker()
        broker2 = SchwabBroker()
        assert broker1 is broker2
    
    @pytest.mark.asyncio
    async def test_singleton_thread_safety(self, mock_auth_service, mock_client):
        """Test thread-safe initialization."""
        mock_auth_service.get_authenticated_client.return_value = mock_client
        
        # Reset singleton
        SchwabBroker._instance = None
        SchwabBroker._initialized = False
        
        broker = SchwabBroker(auth_service=mock_auth_service)
        
        # Mock account loading
        with patch.object(broker, '_load_account_numbers', new_callable=AsyncMock):
            # Initialize concurrently
            tasks = [broker.initialize() for _ in range(5)]
            await asyncio.gather(*tasks)
        
        # Should only initialize once
        assert mock_auth_service.initialize.call_count == 1


class TestSchwabBrokerInitialization:
    """Test broker initialization."""
    
    @pytest.mark.asyncio
    async def test_successful_initialization(self, schwab_broker):
        """Test successful broker initialization."""
        assert schwab_broker._initialized
        assert schwab_broker.client is not None
        assert schwab_broker.rate_limiter is not None
        assert schwab_broker.circuit_breaker is not None
    
    @pytest.mark.asyncio
    async def test_initialization_auth_failure(self, mock_auth_service):
        """Test initialization with auth failure."""
        mock_auth_service.initialize.side_effect = AuthenticationError("Auth failed")
        
        # Reset singleton
        SchwabBroker._instance = None
        SchwabBroker._initialized = False
        
        broker = SchwabBroker(auth_service=mock_auth_service)
        
        with pytest.raises(BrokerConnectionError):
            await broker.initialize()
    
    @pytest.mark.asyncio
    async def test_load_account_numbers(self, schwab_broker, mock_client):
        """Test account number loading."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'accountNumber': '11111111', 'hashValue': 'hash1111'},
            {'accountNumber': '22222222', 'hashValue': 'hash2222'}
        ]
        mock_client.get.return_value = mock_response
        
        # Clear existing accounts
        schwab_broker._account_numbers = []
        schwab_broker._account_hash_map = {}
        
        # Load accounts
        await schwab_broker._load_account_numbers()
        
        assert schwab_broker._account_numbers == ['11111111', '22222222']
        assert schwab_broker._account_hash_map == {
            '11111111': 'hash1111',
            '22222222': 'hash2222'
        }


class TestRequestWrapper:
    """Test request wrapper functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_request(self, schwab_broker, mock_client):
        """Test successful API request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_response.headers = {}
        mock_client.get.return_value = mock_response
        
        response = await schwab_broker._make_request("GET", "/test")
        
        assert response.status_code == 200
        assert response.json() == {'success': True}
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, schwab_broker):
        """Test rate limiting is applied."""
        # Mock rate limiter
        schwab_broker.rate_limiter = Mock()
        schwab_broker.rate_limiter.acquire = AsyncMock()
        
        await schwab_broker._make_request("GET", "/test")
        
        schwab_broker.rate_limiter.acquire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker(self, schwab_broker):
        """Test circuit breaker integration."""
        # Open circuit breaker
        schwab_broker.circuit_breaker.can_request = Mock(return_value=False)
        
        with pytest.raises(BrokerConnectionError, match="Circuit breaker is open"):
            await schwab_broker._make_request("GET", "/test")
    
    @pytest.mark.asyncio
    async def test_401_error_handling(self, schwab_broker, mock_client):
        """Test 401 authentication error handling."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {'message': 'Unauthorized'}
        mock_client.get.return_value = mock_response
        
        with pytest.raises(AuthenticationError):
            await schwab_broker._make_request("GET", "/test")
    
    @pytest.mark.asyncio
    async def test_404_order_not_found(self, schwab_broker, mock_client):
        """Test 404 error for order endpoints."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {'message': 'Not found'}
        mock_client.get.return_value = mock_response
        
        with pytest.raises(OrderNotFoundError):
            await schwab_broker._make_request("GET", "/accounts/123/orders/456")
    
    @pytest.mark.asyncio
    async def test_429_rate_limit_retry(self, schwab_broker, mock_client):
        """Test 429 rate limit with retry."""
        # First call returns 429, second succeeds
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.json.return_value = {'message': 'Rate limited'}
        mock_response_429.headers = {'Retry-After': '1'}
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {'success': True}
        mock_response_200.headers = {}
        
        mock_client.get.side_effect = [mock_response_429, mock_response_200]
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            response = await schwab_broker._make_request("GET", "/test")
        
        assert response.status_code == 200
        assert mock_client.get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_500_error_retry(self, schwab_broker, mock_client):
        """Test 500 server error with retry."""
        # First two calls return 500, third succeeds
        mock_response_500 = Mock()
        mock_response_500.status_code = 500
        mock_response_500.json.return_value = {'message': 'Server error'}
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {'success': True}
        mock_response_200.headers = {}
        
        mock_client.get.side_effect = [
            mock_response_500,
            mock_response_500,
            mock_response_200
        ]
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            response = await schwab_broker._make_request("GET", "/test")
        
        assert response.status_code == 200
        assert mock_client.get.call_count == 3
    
    @pytest.mark.asyncio
    async def test_network_error_retry(self, schwab_broker, mock_client):
        """Test network error with retry."""
        # First call raises network error, second succeeds
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_response.headers = {}
        
        mock_client.get.side_effect = [
            httpx.NetworkError("Connection failed"),
            mock_response
        ]
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            response = await schwab_broker._make_request("GET", "/test")
        
        assert response.status_code == 200
        assert mock_client.get.call_count == 2


class TestAccountMethods:
    """Test account-related methods."""
    
    @pytest.mark.asyncio
    async def test_get_account_numbers(self, schwab_broker):
        """Test getting account numbers."""
        accounts = await schwab_broker.get_account_numbers()
        assert accounts == ['12345678', '87654321']
    
    @pytest.mark.asyncio
    async def test_get_account_info(self, schwab_broker, mock_client):
        """Test getting account information."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'securitiesAccount': {
                'accountNumber': '12345678',
                'currentBalances': {'cashBalance': 10000}
            }
        }
        mock_response.headers = {}
        mock_client.get.return_value = mock_response
        
        account_info = await schwab_broker.get_account_info('12345678')
        
        assert account_info['securitiesAccount']['accountNumber'] == '12345678'
        mock_client.get.assert_called_with(
            'https://api.schwabapi.com/trader/v1/accounts/hash1234',
            params={}
        )
    
    @pytest.mark.asyncio
    async def test_get_account_info_with_fields(self, schwab_broker, mock_client):
        """Test getting account info with specific fields."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'securitiesAccount': {}}
        mock_response.headers = {}
        mock_client.get.return_value = mock_response
        
        await schwab_broker.get_account_info('12345678', fields=['positions', 'orders'])
        
        mock_client.get.assert_called_with(
            'https://api.schwabapi.com/trader/v1/accounts/hash1234',
            params={'fields': 'positions,orders'}
        )
    
    @pytest.mark.asyncio
    async def test_get_positions(self, schwab_broker, mock_client):
        """Test getting positions."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'securitiesAccount': {
                'positions': [
                    {'symbol': 'AAPL', 'quantity': 100},
                    {'symbol': 'GOOGL', 'quantity': 50}
                ]
            }
        }
        mock_response.headers = {}
        mock_client.get.return_value = mock_response
        
        positions = await schwab_broker.get_positions('12345678')
        
        assert len(positions) == 2
        assert positions[0]['symbol'] == 'AAPL'
        assert positions[1]['symbol'] == 'GOOGL'
    
    @pytest.mark.asyncio
    async def test_get_orders(self, schwab_broker, mock_client):
        """Test getting orders."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'orderId': '123', 'status': 'FILLED'},
            {'orderId': '456', 'status': 'WORKING'}
        ]
        mock_response.headers = {}
        mock_client.get.return_value = mock_response
        
        orders = await schwab_broker.get_orders('12345678')
        
        assert len(orders) == 2
        assert orders[0]['orderId'] == '123'
        assert orders[1]['orderId'] == '456'


class TestTradingMethods:
    """Test trading-related methods."""
    
    @pytest.mark.asyncio
    async def test_place_order_success(self, schwab_broker, mock_client):
        """Test successful order placement."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.headers = {'Location': '/accounts/hash1234/orders/789'}
        mock_response.json.return_value = {}
        mock_client.post.return_value = mock_response
        
        order = {
            'orderType': 'LIMIT',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'orderLegCollection': [{
                'instruction': 'BUY',
                'quantity': 100,
                'instrument': {'symbol': 'AAPL'}
            }]
        }
        
        result = await schwab_broker.place_order('12345678', order)
        
        assert result['order_id'] == '789'
        assert result['status'] == 'SUBMITTED'
    
    @pytest.mark.asyncio
    async def test_place_order_invalid(self, schwab_broker):
        """Test order validation."""
        # Missing required fields
        order = {'orderType': 'LIMIT'}
        
        with pytest.raises(InvalidOrderError):
            await schwab_broker.place_order('12345678', order)
    
    @pytest.mark.asyncio
    async def test_cancel_order(self, schwab_broker, mock_client):
        """Test order cancellation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.headers = {}
        mock_client.delete.return_value = mock_response
        
        result = await schwab_broker.cancel_order('12345678', '789')
        
        assert result['order_id'] == '789'
        assert result['status'] == 'CANCELLED'
        
        mock_client.delete.assert_called_with(
            'https://api.schwabapi.com/trader/v1/accounts/hash1234/orders/789'
        )


class TestMarketDataMethods:
    """Test market data methods."""
    
    @pytest.mark.asyncio
    async def test_get_quotes_single_symbol(self, schwab_broker, mock_client):
        """Test getting quote for single symbol."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'AAPL': {
                'symbol': 'AAPL',
                'lastPrice': 150.00,
                'bidPrice': 149.95,
                'askPrice': 150.05
            }
        }
        mock_response.headers = {}
        mock_client.get.return_value = mock_response
        
        quotes = await schwab_broker.get_quotes('AAPL')
        
        assert quotes['AAPL']['lastPrice'] == 150.00
        mock_client.get.assert_called_with(
            'https://api.schwabapi.com/trader/v1/marketdata/v1/quotes',
            params={'symbols': 'AAPL', 'indicative': 'false'}
        )
    
    @pytest.mark.asyncio
    async def test_get_quotes_multiple_symbols(self, schwab_broker, mock_client):
        """Test getting quotes for multiple symbols."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'AAPL': {'symbol': 'AAPL', 'lastPrice': 150.00},
            'GOOGL': {'symbol': 'GOOGL', 'lastPrice': 2800.00}
        }
        mock_response.headers = {}
        mock_client.get.return_value = mock_response
        
        quotes = await schwab_broker.get_quotes(['AAPL', 'GOOGL'])
        
        assert len(quotes) == 2
        assert quotes['AAPL']['lastPrice'] == 150.00
        assert quotes['GOOGL']['lastPrice'] == 2800.00
    
    @pytest.mark.asyncio
    async def test_get_quotes_too_many_symbols(self, schwab_broker):
        """Test quote request with too many symbols."""
        symbols = [f'SYM{i}' for i in range(501)]
        
        with pytest.raises(MarketDataError, match="Maximum 500 symbols"):
            await schwab_broker.get_quotes(symbols)
    
    @pytest.mark.asyncio
    async def test_get_price_history(self, schwab_broker, mock_client):
        """Test getting price history."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'candles': [
                {'datetime': 1234567890, 'open': 149.0, 'high': 151.0, 'low': 148.5, 'close': 150.0, 'volume': 1000000},
                {'datetime': 1234567950, 'open': 150.0, 'high': 152.0, 'low': 149.5, 'close': 151.5, 'volume': 1200000}
            ]
        }
        mock_response.headers = {}
        mock_client.get.return_value = mock_response
        
        history = await schwab_broker.get_price_history('AAPL')
        
        assert len(history['candles']) == 2
        assert history['candles'][0]['close'] == 150.0
    
    @pytest.mark.asyncio
    async def test_get_market_hours(self, schwab_broker, mock_client):
        """Test getting market hours."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'EQUITY': {
                'EQ': {
                    'date': '2023-12-01',
                    'marketType': 'EQUITY',
                    'isOpen': True,
                    'sessionHours': {
                        'regularMarket': [
                            {'start': '2023-12-01T09:30:00-05:00', 'end': '2023-12-01T16:00:00-05:00'}
                        ]
                    }
                }
            }
        }
        mock_response.headers = {}
        mock_client.get.return_value = mock_response
        
        hours = await schwab_broker.get_market_hours('EQUITY')
        
        assert hours['EQUITY']['EQ']['isOpen'] is True
    
    @pytest.mark.asyncio
    async def test_search_instruments(self, schwab_broker, mock_client):
        """Test instrument search."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'AAPL': {
                'symbol': 'AAPL',
                'description': 'Apple Inc.',
                'exchange': 'NASDAQ'
            }
        }
        mock_response.headers = {}
        mock_client.get.return_value = mock_response
        
        results = await schwab_broker.search_instruments('AAPL')
        
        assert results['AAPL']['description'] == 'Apple Inc.'


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_sensitive_data_masking(self, schwab_broker):
        """Test that sensitive data is masked in logs."""
        data = {
            'accountNumber': '12345678',
            'password': 'secret123',
            'positions': [
                {'symbol': 'AAPL', 'quantity': 100, 'cost': 15000}
            ]
        }
        
        masked = schwab_broker._mask_sensitive_data(data)
        
        assert masked['accountNumber'] == '12...78'
        assert masked['password'] == '***'
        assert masked['positions'][0]['quantity'] == '***'
        assert masked['positions'][0]['cost'] == '***'
    
    @pytest.mark.asyncio
    async def test_context_manager(self, mock_auth_service, mock_client):
        """Test context manager support."""
        mock_auth_service.get_authenticated_client.return_value = mock_client
        
        # Reset singleton
        SchwabBroker._instance = None
        SchwabBroker._initialized = False
        
        async with SchwabBroker(auth_service=mock_auth_service) as broker:
            assert broker._initialized
        
        # Should call close
        mock_auth_service.shutdown.assert_called_once()


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    @pytest.mark.asyncio
    async def test_get_schwab_broker(self, mock_auth_service, mock_client):
        """Test get_schwab_broker convenience function."""
        with patch('src.broker.schwab_client.get_auth_service') as mock_get_auth:
            mock_get_auth.return_value = mock_auth_service
            mock_auth_service.get_authenticated_client.return_value = mock_client
            
            # Reset singleton
            SchwabBroker._instance = None
            SchwabBroker._initialized = False
            
            with patch.object(SchwabBroker, '_load_account_numbers', new_callable=AsyncMock):
                broker = await get_schwab_broker()
            
            assert isinstance(broker, SchwabBroker)
            assert broker._initialized