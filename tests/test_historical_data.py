"""Tests for historical data fetcher."""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import text

from src.data import (
    HistoricalDataFetcher,
    TimeFrame,
    get_historical_fetcher,
    db_service
)
from src.data.models import PriceData


@pytest.fixture
async def fetcher():
    """Create a historical data fetcher instance."""
    fetcher = HistoricalDataFetcher()
    # Mock the auth service to avoid real authentication
    with patch('src.data.historical_data.get_auth_service') as mock_auth:
        mock_auth_service = MagicMock()
        mock_client = AsyncMock()
        mock_auth_service.get_client.return_value = mock_client
        mock_auth.return_value = mock_auth_service
        
        fetcher.auth_service = mock_auth_service
        fetcher.client = mock_client
        
        yield fetcher


@pytest.fixture
def sample_candle_data():
    """Sample candle data from API."""
    return {
        'candles': [
            {
                'datetime': 1704067200000,  # 2024-01-01 00:00:00 UTC
                'open': 150.00,
                'high': 152.00,
                'low': 149.50,
                'close': 151.50,
                'volume': 1000000
            },
            {
                'datetime': 1704070800000,  # 2024-01-01 01:00:00 UTC
                'open': 151.50,
                'high': 153.00,
                'low': 151.00,
                'close': 152.50,
                'volume': 1200000,
                'vwap': 152.25
            }
        ]
    }


@pytest.fixture
def invalid_candle_data():
    """Invalid candle data for testing error handling."""
    return {
        'candles': [
            {
                # Missing required fields
                'datetime': 1704067200000,
                'open': 150.00,
                'close': 151.50,
                'volume': 1000000
            },
            {
                # Invalid OHLC relationship (high < low)
                'datetime': 1704070800000,
                'open': 151.50,
                'high': 150.00,
                'low': 153.00,
                'close': 152.50,
                'volume': 1200000
            }
        ]
    }


class TestHistoricalDataFetcher:
    """Test cases for HistoricalDataFetcher."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, fetcher):
        """Test fetcher initialization."""
        assert fetcher._rate_limit_delay == 0.5
        assert fetcher._max_rate_limit_delay == 60
        assert fetcher._max_retries == 3
        
        # Test initialize method
        await fetcher.initialize()
        fetcher.auth_service.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetch_historical_data_success(self, fetcher, sample_candle_data):
        """Test successful historical data fetch."""
        # Mock API response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = sample_candle_data
        
        fetcher.client.get_price_history_every_day.return_value = mock_response
        
        # Fetch data
        symbol = "AAPL"
        end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        
        data = await fetcher.fetch_historical_data(
            symbol=symbol,
            timeframe=TimeFrame.DAILY,
            start_date=start_date,
            end_date=end_date,
            save_to_db=False
        )
        
        # Verify results
        assert len(data) == 2
        assert data[0]['symbol'] == symbol
        assert data[0]['open'] == Decimal('150.00')
        assert data[0]['high'] == Decimal('152.00')
        assert data[0]['low'] == Decimal('149.50')
        assert data[0]['close'] == Decimal('151.50')
        assert data[0]['volume'] == 1000000
        
        # Check second candle has vwap
        assert data[1]['vwap'] == Decimal('152.25')
    
    @pytest.mark.asyncio
    async def test_fetch_with_rate_limit_retry(self, fetcher, sample_candle_data):
        """Test retry logic on rate limit error."""
        # First call fails with rate limit
        rate_limit_response = AsyncMock()
        rate_limit_response.status_code = 429
        rate_limit_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limit exceeded",
            request=MagicMock(),
            response=MagicMock(status_code=429)
        )
        
        # Second call succeeds
        success_response = AsyncMock()
        success_response.status_code = 200
        success_response.raise_for_status = MagicMock()
        success_response.json.return_value = sample_candle_data
        
        fetcher.client.get_price_history_every_minute.side_effect = [
            rate_limit_response,
            success_response
        ]
        
        # Fetch data with fast retry for testing
        fetcher._rate_limit_delay = 0.01
        
        data = await fetcher.fetch_historical_data(
            symbol="AAPL",
            timeframe=TimeFrame.MINUTE_1,
            save_to_db=False
        )
        
        # Should succeed after retry
        assert len(data) == 2
        assert fetcher.client.get_price_history_every_minute.call_count == 2
    
    @pytest.mark.asyncio
    async def test_parse_invalid_data(self, fetcher, invalid_candle_data):
        """Test parsing of invalid candle data."""
        parsed = fetcher._parse_price_data("AAPL", invalid_candle_data, TimeFrame.DAILY)
        
        # Should skip invalid candles
        assert len(parsed) == 0
    
    @pytest.mark.asyncio
    async def test_different_timeframes(self, fetcher, sample_candle_data):
        """Test fetching data with different timeframes."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = sample_candle_data
        
        # Set all timeframe methods to return mock response
        fetcher.client.get_price_history_every_minute.return_value = mock_response
        fetcher.client.get_price_history_every_five_minutes.return_value = mock_response
        fetcher.client.get_price_history_every_ten_minutes.return_value = mock_response
        fetcher.client.get_price_history_every_fifteen_minutes.return_value = mock_response
        fetcher.client.get_price_history_every_thirty_minutes.return_value = mock_response
        fetcher.client.get_price_history_every_day.return_value = mock_response
        fetcher.client.get_price_history_every_week.return_value = mock_response
        
        # Test each timeframe
        timeframes = [
            (TimeFrame.MINUTE_1, fetcher.client.get_price_history_every_minute),
            (TimeFrame.MINUTE_5, fetcher.client.get_price_history_every_five_minutes),
            (TimeFrame.MINUTE_10, fetcher.client.get_price_history_every_ten_minutes),
            (TimeFrame.MINUTE_15, fetcher.client.get_price_history_every_fifteen_minutes),
            (TimeFrame.MINUTE_30, fetcher.client.get_price_history_every_thirty_minutes),
            (TimeFrame.DAILY, fetcher.client.get_price_history_every_day),
            (TimeFrame.WEEKLY, fetcher.client.get_price_history_every_week),
        ]
        
        for timeframe, expected_method in timeframes:
            await fetcher.fetch_historical_data(
                symbol="AAPL",
                timeframe=timeframe,
                save_to_db=False
            )
            expected_method.assert_called_once()
            expected_method.reset_mock()
    
    @pytest.mark.asyncio
    async def test_fetch_multiple_symbols(self, fetcher, sample_candle_data):
        """Test fetching data for multiple symbols concurrently."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = sample_candle_data
        
        fetcher.client.get_price_history_every_day.return_value = mock_response
        
        symbols = ["AAPL", "GOOGL", "MSFT"]
        results = await fetcher.fetch_multiple_symbols(
            symbols=symbols,
            timeframe=TimeFrame.DAILY,
            max_concurrent=2
        )
        
        # Should have results for all symbols
        assert len(results) == 3
        for symbol in symbols:
            assert symbol in results
            assert len(results[symbol]) == 2
    
    @pytest.mark.asyncio
    async def test_error_handling_in_multiple_symbols(self, fetcher, sample_candle_data):
        """Test error handling when fetching multiple symbols."""
        # First symbol succeeds, second fails, third succeeds
        success_response = AsyncMock()
        success_response.status_code = 200
        success_response.raise_for_status = MagicMock()
        success_response.json.return_value = sample_candle_data
        
        error_response = AsyncMock()
        error_response.status_code = 404
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Symbol not found",
            request=MagicMock(),
            response=MagicMock(status_code=404)
        )
        
        fetcher.client.get_price_history_every_day.side_effect = [
            success_response,  # AAPL
            error_response,    # INVALID
            success_response   # MSFT
        ]
        
        symbols = ["AAPL", "INVALID", "MSFT"]
        results = await fetcher.fetch_multiple_symbols(
            symbols=symbols,
            timeframe=TimeFrame.DAILY,
            max_concurrent=1  # Sequential for predictable order
        )
        
        # Should have results for valid symbols
        assert len(results["AAPL"]) == 2
        assert len(results["INVALID"]) == 0
        assert len(results["MSFT"]) == 2


class TestDatabaseIntegration:
    """Test database integration features."""
    
    @pytest.mark.asyncio
    async def test_get_latest_timestamp(self, fetcher):
        """Test getting latest timestamp for a symbol."""
        # Initialize test database
        db_service.initialize()
        
        # Insert test data
        async with db_service.get_async_session() as session:
            test_data = [
                PriceData(
                    symbol="TEST",
                    timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
                    open=Decimal('100'),
                    high=Decimal('101'),
                    low=Decimal('99'),
                    close=Decimal('100.5'),
                    volume=1000
                ),
                PriceData(
                    symbol="TEST",
                    timestamp=datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
                    open=Decimal('100.5'),
                    high=Decimal('102'),
                    low=Decimal('100'),
                    close=Decimal('101.5'),
                    volume=1100
                )
            ]
            
            session.add_all(test_data)
            await session.commit()
        
        # Test getting latest timestamp
        latest = await fetcher.get_latest_timestamp("TEST")
        assert latest == datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc)
        
        # Test non-existent symbol
        latest = await fetcher.get_latest_timestamp("NONEXISTENT")
        assert latest is None
        
        # Cleanup
        async with db_service.get_async_session() as session:
            await session.execute(text("DELETE FROM price_data WHERE symbol = 'TEST'"))
            await session.commit()
    
    @pytest.mark.asyncio
    async def test_update_symbol_data(self, fetcher, sample_candle_data):
        """Test updating symbol data from latest timestamp."""
        # Mock the client
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = sample_candle_data
        
        fetcher.client.get_price_history_every_minute.return_value = mock_response
        
        # Mock get_latest_timestamp to return a date
        with patch.object(fetcher, 'get_latest_timestamp') as mock_get_latest:
            mock_get_latest.return_value = datetime(2024, 1, 1, tzinfo=timezone.utc)
            
            # Update data
            new_records = await fetcher.update_symbol_data("AAPL", TimeFrame.MINUTE_1)
            
            assert new_records == 2
            mock_get_latest.assert_called_once_with("AAPL")
            
            # Verify start date was adjusted
            call_args = fetcher.client.get_price_history_every_minute.call_args
            assert call_args[1]['start_date'] == "2024-01-01"


class TestDataValidation:
    """Test data validation and quality checks."""
    
    def test_ohlc_validation(self, fetcher):
        """Test OHLC relationship validation."""
        # Valid OHLC data
        valid_data = {
            'candles': [{
                'datetime': 1704067200000,
                'open': 100,
                'high': 105,
                'low': 98,
                'close': 103,
                'volume': 1000
            }]
        }
        
        parsed = fetcher._parse_price_data("AAPL", valid_data, TimeFrame.DAILY)
        assert len(parsed) == 1
        
        # Invalid OHLC - open > high
        invalid_data = {
            'candles': [{
                'datetime': 1704067200000,
                'open': 110,
                'high': 105,
                'low': 98,
                'close': 103,
                'volume': 1000
            }]
        }
        
        parsed = fetcher._parse_price_data("AAPL", invalid_data, TimeFrame.DAILY)
        assert len(parsed) == 0
        
        # Invalid OHLC - close < low
        invalid_data = {
            'candles': [{
                'datetime': 1704067200000,
                'open': 100,
                'high': 105,
                'low': 98,
                'close': 95,
                'volume': 1000
            }]
        }
        
        parsed = fetcher._parse_price_data("AAPL", invalid_data, TimeFrame.DAILY)
        assert len(parsed) == 0


@pytest.mark.asyncio
async def test_singleton_fetcher():
    """Test that get_historical_fetcher returns singleton instance."""
    fetcher1 = get_historical_fetcher()
    fetcher2 = get_historical_fetcher()
    
    assert fetcher1 is fetcher2


@pytest.mark.asyncio
async def test_shutdown(fetcher):
    """Test clean shutdown of fetcher."""
    await fetcher.shutdown()
    # Should complete without errors