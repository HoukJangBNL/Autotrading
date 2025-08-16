"""Integration tests for SchwabBroker with realistic mock responses."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import json

from src.broker import SchwabBroker, get_schwab_broker
from src.broker.exceptions import (
    BrokerError,
    RateLimitError,
    InvalidOrderError,
    OrderNotFoundError,
    InsufficientFundsError
)


# Realistic mock responses
MOCK_ACCOUNT_NUMBERS_RESPONSE = [
    {
        "accountNumber": "12345678",
        "hashValue": "A1B2C3D4E5F6",
        "type": "BROKERAGE",
        "nickname": "Individual Trading"
    },
    {
        "accountNumber": "87654321",
        "hashValue": "F6E5D4C3B2A1",
        "type": "BROKERAGE",
        "nickname": "IRA Account"
    }
]

MOCK_ACCOUNT_INFO_RESPONSE = {
    "securitiesAccount": {
        "type": "CASH",
        "accountNumber": "12345678",
        "roundTrips": 0,
        "isDayTrader": False,
        "isClosingOnlyRestricted": False,
        "pfcbFlag": False,
        "positions": [
            {
                "shortQuantity": 0,
                "averagePrice": 145.50,
                "currentDayProfitLoss": 250.00,
                "currentDayProfitLossPercentage": 0.5,
                "longQuantity": 100,
                "settledLongQuantity": 100,
                "settledShortQuantity": 0,
                "instrument": {
                    "assetType": "EQUITY",
                    "cusip": "037833100",
                    "symbol": "AAPL",
                    "description": "Apple Inc"
                },
                "marketValue": 15000.00,
                "maintenanceRequirement": 4500.00,
                "averageLongPrice": 145.50,
                "taxLotAverageLongPrice": 145.50,
                "longOpenProfitLoss": 450.00,
                "previousSessionLongQuantity": 100,
                "currentDayCost": 0
            },
            {
                "shortQuantity": 0,
                "averagePrice": 2750.00,
                "currentDayProfitLoss": -100.00,
                "currentDayProfitLossPercentage": -0.2,
                "longQuantity": 10,
                "settledLongQuantity": 10,
                "settledShortQuantity": 0,
                "instrument": {
                    "assetType": "EQUITY",
                    "cusip": "02079K305",
                    "symbol": "GOOGL",
                    "description": "Alphabet Inc Class A"
                },
                "marketValue": 27400.00,
                "maintenanceRequirement": 8220.00,
                "averageLongPrice": 2750.00,
                "taxLotAverageLongPrice": 2750.00,
                "longOpenProfitLoss": -100.00,
                "previousSessionLongQuantity": 10,
                "currentDayCost": 0
            }
        ],
        "initialBalances": {
            "accruedInterest": 0,
            "cashAvailableForTrading": 50000.00,
            "cashAvailableForWithdrawal": 50000.00,
            "cashBalance": 50000.00,
            "bondValue": 0,
            "cashReceipts": 0,
            "liquidationValue": 92400.00,
            "longOptionMarketValue": 0,
            "longStockValue": 42400.00,
            "moneyMarketFund": 0,
            "mutualFundValue": 0,
            "shortOptionMarketValue": 0,
            "shortStockValue": 0,
            "isInCall": False,
            "unsettledCash": 0,
            "cashDebitCallValue": 0,
            "pendingDeposits": 0,
            "accountValue": 92400.00
        },
        "currentBalances": {
            "accruedInterest": 0,
            "cashBalance": 50000.00,
            "cashReceipts": 0,
            "longOptionMarketValue": 0,
            "liquidationValue": 92400.00,
            "longMarketValue": 42400.00,
            "moneyMarketFund": 0,
            "savings": 0,
            "shortMarketValue": 0,
            "pendingDeposits": 0,
            "mutualFundValue": 0,
            "bondValue": 0,
            "shortOptionMarketValue": 0,
            "availableFunds": 50000.00,
            "availableFundsNonMarginableTrade": 50000.00,
            "buyingPower": 50000.00,
            "buyingPowerNonMarginableTrade": 50000.00,
            "dayTradingBuyingPower": 0,
            "dayTradingBuyingPowerCall": 0,
            "dayTradingEquityCall": 0,
            "equity": 92400.00,
            "equityPercentage": 100.0,
            "longMarginValue": 42400.00,
            "maintenanceCall": 0,
            "maintenanceRequirement": 12720.00,
            "marginBalance": 0,
            "regTCall": 0,
            "shortBalance": 0,
            "shortMarginValue": 0,
            "sma": 50000.00,
            "isInCall": False,
            "stockBuyingPower": 50000.00,
            "optionBuyingPower": 50000.00
        }
    }
}

MOCK_ORDERS_RESPONSE = [
    {
        "session": "NORMAL",
        "duration": "DAY",
        "orderType": "LIMIT",
        "complexOrderStrategyType": "NONE",
        "quantity": 10,
        "filledQuantity": 10,
        "remainingQuantity": 0,
        "requestedDestination": "AUTO",
        "destinationLinkName": "CDRG",
        "price": 148.50,
        "orderLegCollection": [
            {
                "orderLegType": "EQUITY",
                "legId": 1,
                "instrument": {
                    "assetType": "EQUITY",
                    "cusip": "037833100",
                    "symbol": "AAPL",
                    "description": "Apple Inc"
                },
                "instruction": "BUY",
                "positionEffect": "OPENING",
                "quantity": 10
            }
        ],
        "orderStrategyType": "SINGLE",
        "orderId": 1234567890,
        "cancelable": False,
        "editable": False,
        "status": "FILLED",
        "enteredTime": "2023-12-01T10:30:00+0000",
        "closeTime": "2023-12-01T10:30:15+0000",
        "tag": "API_ORDER",
        "accountNumber": "12345678",
        "orderActivityCollection": [
            {
                "activityType": "EXECUTION",
                "executionType": "FILL",
                "quantity": 10,
                "orderRemainingQuantity": 0,
                "executionLegs": [
                    {
                        "legId": 1,
                        "price": 148.50,
                        "quantity": 10,
                        "mismarkedQuantity": 0,
                        "instrumentId": 9394353,
                        "time": "2023-12-01T10:30:15+0000"
                    }
                ]
            }
        ],
        "statusDescription": "Filled"
    },
    {
        "session": "NORMAL",
        "duration": "DAY",
        "orderType": "LIMIT",
        "complexOrderStrategyType": "NONE",
        "quantity": 5,
        "filledQuantity": 0,
        "remainingQuantity": 5,
        "requestedDestination": "AUTO",
        "destinationLinkName": "CDRG",
        "price": 2700.00,
        "orderLegCollection": [
            {
                "orderLegType": "EQUITY",
                "legId": 1,
                "instrument": {
                    "assetType": "EQUITY",
                    "cusip": "02079K305",
                    "symbol": "GOOGL",
                    "description": "Alphabet Inc Class A"
                },
                "instruction": "BUY",
                "positionEffect": "OPENING",
                "quantity": 5
            }
        ],
        "orderStrategyType": "SINGLE",
        "orderId": 1234567891,
        "cancelable": True,
        "editable": True,
        "status": "WORKING",
        "enteredTime": "2023-12-01T11:00:00+0000",
        "tag": "API_ORDER",
        "accountNumber": "12345678",
        "statusDescription": "Working"
    }
]

MOCK_QUOTES_RESPONSE = {
    "AAPL": {
        "assetMainType": "EQUITY",
        "assetSubType": "COE",
        "quoteType": "NBBO",
        "realtime": True,
        "ssid": 1973757747,
        "symbol": "AAPL",
        "bid": 149.95,
        "ask": 150.05,
        "last": 150.00,
        "open": 148.50,
        "high": 151.25,
        "low": 148.25,
        "volume": 45678901,
        "change": 1.50,
        "changePercent": 1.01,
        "close": 148.50,
        "prevClose": 148.50,
        "mark": 150.00,
        "markChange": 1.50,
        "markChangePercent": 1.01,
        "fiftyTwoWeekHigh": 199.62,
        "fiftyTwoWeekLow": 124.17,
        "peRatio": 32.12,
        "divAmount": 0.96,
        "divYield": 0.64,
        "divDate": "2023-11-10 00:00:00.000",
        "securityStatus": "Normal",
        "bidSize": 100,
        "askSize": 200,
        "lastSize": 100,
        "bidTime": 1701432000000,
        "askTime": 1701432000000,
        "lastTime": 1701432000000,
        "tradeTime": 1701432000000,
        "regularMarketLastPrice": 150.00,
        "regularMarketLastSize": 100,
        "regularMarketChange": 1.50,
        "regularMarketPercentChange": 1.01,
        "delayed": False,
        "realtimeEntitled": True,
        "exchangeName": "NASD",
        "exchangeDataDelayedBy": 0,
        "marketState": "OPEN",
        "marginable": True,
        "shortable": True,
        "volatility": 0.0123
    }
}

MOCK_PRICE_HISTORY_RESPONSE = {
    "candles": [
        {
            "open": 148.50,
            "high": 149.00,
            "low": 148.25,
            "close": 148.75,
            "volume": 1234567,
            "datetime": 1701428400000
        },
        {
            "open": 148.75,
            "high": 149.50,
            "low": 148.50,
            "close": 149.25,
            "volume": 2345678,
            "datetime": 1701428460000
        },
        {
            "open": 149.25,
            "high": 150.00,
            "low": 149.00,
            "close": 149.75,
            "volume": 3456789,
            "datetime": 1701428520000
        },
        {
            "open": 149.75,
            "high": 150.25,
            "low": 149.50,
            "close": 150.00,
            "volume": 4567890,
            "datetime": 1701428580000
        }
    ],
    "symbol": "AAPL",
    "empty": False,
    "previousClose": 148.50,
    "previousCloseDate": 1701360000000
}


@pytest.fixture
async def mock_broker():
    """Create a fully mocked broker for integration testing."""
    with patch('src.broker.schwab_client.get_auth_service') as mock_get_auth:
        mock_auth_service = AsyncMock()
        mock_client = AsyncMock()
        
        mock_get_auth.return_value = mock_auth_service
        mock_auth_service.initialize = AsyncMock()
        mock_auth_service.get_authenticated_client = AsyncMock(return_value=mock_client)
        
        # Reset singleton
        SchwabBroker._instance = None
        SchwabBroker._initialized = False
        
        broker = SchwabBroker()
        
        # Setup default mock responses
        def setup_mock_response(status_code, json_data, headers=None):
            response = Mock()
            response.status_code = status_code
            response.json.return_value = json_data
            response.headers = headers or {}
            return response
        
        # Mock account numbers
        mock_client.get.side_effect = lambda url, **kwargs: {
            'https://api.schwabapi.com/trader/v1/accounts/accountNumbers': 
                setup_mock_response(200, MOCK_ACCOUNT_NUMBERS_RESPONSE),
            'https://api.schwabapi.com/trader/v1/accounts/A1B2C3D4E5F6': 
                setup_mock_response(200, MOCK_ACCOUNT_INFO_RESPONSE),
            'https://api.schwabapi.com/trader/v1/accounts/A1B2C3D4E5F6/orders': 
                setup_mock_response(200, MOCK_ORDERS_RESPONSE),
            'https://api.schwabapi.com/trader/v1/marketdata/v1/quotes': 
                setup_mock_response(200, MOCK_QUOTES_RESPONSE),
            'https://api.schwabapi.com/trader/v1/marketdata/v1/pricehistory': 
                setup_mock_response(200, MOCK_PRICE_HISTORY_RESPONSE),
        }.get(url, setup_mock_response(404, {'error': 'Not found'}))
        
        await broker.initialize()
        
        # Override side_effect for more control
        broker.client = mock_client
        
        return broker


class TestSchwabBrokerIntegration:
    """Integration tests with realistic workflows."""
    
    @pytest.mark.asyncio
    async def test_full_account_workflow(self, mock_broker):
        """Test complete account information workflow."""
        # Get account numbers
        accounts = await mock_broker.get_account_numbers()
        assert len(accounts) == 2
        assert "12345678" in accounts
        
        # Get account info
        account_info = await mock_broker.get_account_info("12345678")
        assert account_info['securitiesAccount']['accountNumber'] == "12345678"
        
        # Check balances
        balances = account_info['securitiesAccount']['currentBalances']
        assert balances['cashBalance'] == 50000.00
        assert balances['buyingPower'] == 50000.00
        
        # Get positions
        positions = await mock_broker.get_positions("12345678")
        assert len(positions) == 2
        
        # Verify position details
        aapl_position = next(p for p in positions if p['instrument']['symbol'] == 'AAPL')
        assert aapl_position['longQuantity'] == 100
        assert aapl_position['averagePrice'] == 145.50
        assert aapl_position['marketValue'] == 15000.00
    
    @pytest.mark.asyncio
    async def test_order_lifecycle(self, mock_broker):
        """Test complete order lifecycle."""
        # Place order
        order = {
            'orderType': 'LIMIT',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'price': 149.00,
            'orderLegCollection': [{
                'instruction': 'BUY',
                'quantity': 10,
                'instrument': {'symbol': 'AAPL', 'assetType': 'EQUITY'}
            }]
        }
        
        # Mock successful order placement
        mock_broker.client.post = AsyncMock(
            return_value=Mock(
                status_code=201,
                headers={'Location': '/accounts/A1B2C3D4E5F6/orders/1234567892'},
                json=Mock(return_value={})
            )
        )
        
        result = await mock_broker.place_order("12345678", order)
        assert result['order_id'] == '1234567892'
        assert result['status'] == 'SUBMITTED'
        
        # Get orders
        orders = await mock_broker.get_orders("12345678")
        assert len(orders) == 2
        
        # Find working order
        working_order = next(o for o in orders if o['status'] == 'WORKING')
        assert working_order['orderId'] == 1234567891
        assert working_order['cancelable'] is True
        
        # Cancel order
        mock_broker.client.delete = AsyncMock(
            return_value=Mock(status_code=200, json=Mock(return_value={}))
        )
        
        cancel_result = await mock_broker.cancel_order("12345678", "1234567891")
        assert cancel_result['status'] == 'CANCELLED'
    
    @pytest.mark.asyncio
    async def test_market_data_workflow(self, mock_broker):
        """Test market data fetching workflow."""
        # Get single quote
        quotes = await mock_broker.get_quotes("AAPL")
        assert "AAPL" in quotes
        
        aapl_quote = quotes["AAPL"]
        assert aapl_quote['last'] == 150.00
        assert aapl_quote['bid'] == 149.95
        assert aapl_quote['ask'] == 150.05
        assert aapl_quote['volume'] == 45678901
        
        # Get price history
        history = await mock_broker.get_price_history(
            "AAPL",
            period_type="day",
            period=1,
            frequency_type="minute",
            frequency=1
        )
        
        assert len(history['candles']) == 4
        assert history['symbol'] == "AAPL"
        assert history['previousClose'] == 148.50
        
        # Verify candle data
        first_candle = history['candles'][0]
        assert first_candle['open'] == 148.50
        assert first_candle['close'] == 148.75
        assert first_candle['volume'] == 1234567
    
    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, mock_broker):
        """Test error handling in realistic scenarios."""
        # Test insufficient funds
        large_order = {
            'orderType': 'MARKET',
            'session': 'NORMAL',
            'duration': 'DAY',
            'orderStrategyType': 'SINGLE',
            'orderLegCollection': [{
                'instruction': 'BUY',
                'quantity': 1000,  # Would cost ~$150,000
                'instrument': {'symbol': 'AAPL', 'assetType': 'EQUITY'}
            }]
        }
        
        # Mock insufficient funds error
        mock_broker.client.post = AsyncMock(
            return_value=Mock(
                status_code=400,
                json=Mock(return_value={
                    'message': 'Insufficient funds',
                    'code': 'INSUFFICIENT_BUYING_POWER'
                })
            )
        )
        
        with pytest.raises(BrokerError):
            await mock_broker.place_order("12345678", large_order)
        
        # Test order not found
        mock_broker.client.delete = AsyncMock(
            return_value=Mock(
                status_code=404,
                json=Mock(return_value={'message': 'Order not found'})
            )
        )
        
        with pytest.raises(OrderNotFoundError):
            await mock_broker.cancel_order("12345678", "9999999999")
    
    @pytest.mark.asyncio
    async def test_rate_limiting_scenario(self, mock_broker):
        """Test rate limiting behavior."""
        # Simulate rate limit response
        rate_limit_response = Mock(
            status_code=429,
            json=Mock(return_value={'message': 'Rate limit exceeded'}),
            headers={'Retry-After': '2'}
        )
        
        success_response = Mock(
            status_code=200,
            json=Mock(return_value=MOCK_QUOTES_RESPONSE)
        )
        
        # First call hits rate limit, second succeeds
        mock_broker.client.get = AsyncMock(
            side_effect=[rate_limit_response, success_response]
        )
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            quotes = await mock_broker.get_quotes("AAPL")
        
        assert "AAPL" in quotes
        assert mock_broker.client.get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, mock_broker):
        """Test concurrent request handling."""
        # Setup mock responses for concurrent calls
        quote_tasks = []
        symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
        
        mock_broker.client.get = AsyncMock(
            return_value=Mock(
                status_code=200,
                json=Mock(return_value=MOCK_QUOTES_RESPONSE)
            )
        )
        
        # Make concurrent requests
        for symbol in symbols:
            task = mock_broker.get_quotes(symbol)
            quote_tasks.append(task)
        
        results = await asyncio.gather(*quote_tasks)
        
        # All should succeed
        assert len(results) == 5
        for result in results:
            assert "AAPL" in result  # Mock always returns AAPL data
    
    @pytest.mark.asyncio
    async def test_session_lifecycle(self, mock_broker):
        """Test complete session lifecycle."""
        # Use context manager
        async with mock_broker as broker:
            # Perform operations
            accounts = await broker.get_account_numbers()
            assert len(accounts) > 0
            
            quotes = await broker.get_quotes("AAPL")
            assert "AAPL" in quotes
        
        # Verify cleanup was called
        mock_broker.auth_service.shutdown.assert_called_once()