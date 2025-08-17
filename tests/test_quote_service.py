"""
Comprehensive tests for the real-time quote service.
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from collections import deque

import pytest
import redis.asyncio as redis
from redis.exceptions import RedisError

from src.data.quote_service import (
    Quote, QuoteHistory, QuoteService, create_quote_service
)
from src.broker.exceptions import MarketDataError, BrokerError


class TestQuote:
    """Test the Quote data model."""
    
    def test_quote_creation(self):
        """Test basic quote creation."""
        quote = Quote(
            symbol="AAPL",
            bid_price=150.00,
            ask_price=150.05,
            last_price=150.02,
            bid_size=100,
            ask_size=200,
            last_size=50,
            volume=1000000,
            timestamp=datetime.now(timezone.utc)
        )
        
        assert quote.symbol == "AAPL"
        assert quote.bid_price == 150.00
        assert quote.ask_price == 150.05
        assert quote.spread == pytest.approx(0.05, rel=1e-9)
        assert quote.spread_percentage == pytest.approx(0.0333, rel=1e-3)
        assert quote.mid_price == 150.025
    
    def test_quote_with_change_calculation(self):
        """Test quote with change calculation."""
        quote = Quote(
            symbol="AAPL",
            bid_price=150.00,
            ask_price=150.05,
            last_price=152.00,
            bid_size=100,
            ask_size=200,
            last_size=50,
            volume=1000000,
            timestamp=datetime.now(timezone.utc),
            previous_close=150.00
        )
        
        assert quote.change == 2.00
        assert quote.change_percentage == pytest.approx(1.333, rel=1e-3)
    
    def test_quote_to_dict(self):
        """Test quote serialization to dictionary."""
        timestamp = datetime.now(timezone.utc)
        quote = Quote(
            symbol="AAPL",
            bid_price=150.00,
            ask_price=150.05,
            last_price=150.02,
            bid_size=100,
            ask_size=200,
            last_size=50,
            volume=1000000,
            timestamp=timestamp
        )
        
        data = quote.to_dict()
        assert data['symbol'] == "AAPL"
        assert data['bid_price'] == 150.00
        assert data['spread'] == pytest.approx(0.05, rel=1e-9)
        assert data['timestamp'] == timestamp.isoformat()
    
    def test_quote_from_dict(self):
        """Test quote deserialization from dictionary."""
        timestamp = datetime.now(timezone.utc)
        data = {
            'symbol': 'AAPL',
            'bid_price': 150.00,
            'ask_price': 150.05,
            'last_price': 150.02,
            'bid_size': 100,
            'ask_size': 200,
            'last_size': 50,
            'volume': 1000000,
            'timestamp': timestamp.isoformat()
        }
        
        quote = Quote.from_dict(data)
        assert quote.symbol == "AAPL"
        assert quote.bid_price == 150.00
        assert quote.spread == pytest.approx(0.05, rel=1e-9)
        assert quote.timestamp == timestamp
    
    def test_quote_from_schwab_response(self):
        """Test quote creation from Schwab API response."""
        schwab_data = {
            'quote': {
                'bidPrice': 150.00,
                'askPrice': 150.05,
                'lastPrice': 150.02,
                'bidSize': 100,
                'askSize': 200,
                'lastSize': 50,
                'totalVolume': 1000000,
                'openPrice': 149.50,
                'highPrice': 151.00,
                'lowPrice': 149.00,
                'closePrice': 150.00,
                '52WeekHigh': 180.00,
                '52WeekLow': 120.00,
                'exchangeName': 'NASDAQ',
                'quoteTime': 1234567890000,
                'tradeTime': 1234567890000
            }
        }
        
        quote = Quote.from_schwab_quote("AAPL", schwab_data)
        assert quote.symbol == "AAPL"
        assert quote.bid_price == 150.00
        assert quote.open_price == 149.50
        assert quote.fifty_two_week_high == 180.00
        assert quote.exchange == "NASDAQ"


class TestQuoteHistory:
    """Test the QuoteHistory tracking."""
    
    def test_quote_history_tracking(self):
        """Test adding quotes to history."""
        history = QuoteHistory("AAPL", max_history=5)
        
        # Add quotes
        for i in range(7):
            quote = Quote(
                symbol="AAPL",
                bid_price=150.00 + i,
                ask_price=150.05 + i,
                last_price=150.02 + i,
                bid_size=100,
                ask_size=200,
                last_size=50,
                volume=1000000,
                timestamp=datetime.now(timezone.utc)
            )
            history.add_quote(quote)
        
        # Should only keep last 5
        assert len(history.quotes) == 5
        assert history.quotes[0].bid_price == 152.00  # First 2 removed
    
    def test_get_latest_quotes(self):
        """Test getting latest quotes from history."""
        history = QuoteHistory("AAPL")
        
        # Add quotes
        quotes = []
        for i in range(5):
            quote = Quote(
                symbol="AAPL",
                bid_price=150.00 + i,
                ask_price=150.05 + i,
                last_price=150.02 + i,
                bid_size=100,
                ask_size=200,
                last_size=50,
                volume=1000000,
                timestamp=datetime.now(timezone.utc)
            )
            quotes.append(quote)
            history.add_quote(quote)
        
        latest = history.get_latest(3)
        assert len(latest) == 3
        assert latest[0].bid_price == 152.00
        assert latest[2].bid_price == 154.00
    
    def test_price_range_calculation(self):
        """Test price range calculation over time window."""
        history = QuoteHistory("AAPL")
        base_time = datetime.now(timezone.utc)
        
        # Add quotes with timestamps in the past
        for i in range(10):
            quote = Quote(
                symbol="AAPL",
                bid_price=150.00,
                ask_price=150.05,
                last_price=150.00 + i,  # Price increases
                bid_size=100,
                ask_size=200,
                last_size=50,
                volume=1000000,
                timestamp=base_time - timedelta(minutes=9-i)  # 9 minutes ago to now
            )
            history.add_quote(quote)
        
        # Get range for last 5 minutes
        min_price, max_price = history.get_price_range(5)
        # Should include quotes from last 5 minutes (prices 155-159)
        assert min_price == 155.00
        assert max_price == 159.00
    
    def test_volume_calculation(self):
        """Test volume calculation over time window."""
        history = QuoteHistory("AAPL")
        base_time = datetime.now(timezone.utc)
        
        # Add quotes with increasing volume
        for i in range(5):
            quote = Quote(
                symbol="AAPL",
                bid_price=150.00,
                ask_price=150.05,
                last_price=150.02,
                bid_size=100,
                ask_size=200,
                last_size=50,
                volume=1000000 + (i * 100000),  # Volume increases
                timestamp=base_time - timedelta(minutes=4-i)  # 4 minutes ago to now
            )
            history.add_quote(quote)
        
        # Get volume for last 5 minutes
        volume = history.get_volume_total(5)
        # Should be difference between last and first
        assert volume == 400000  # 1400000 - 1000000


@pytest.fixture
async def mock_broker():
    """Create a mock broker instance."""
    broker = AsyncMock()
    return broker


@pytest.fixture
async def mock_redis():
    """Create a mock Redis client."""
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.get = AsyncMock(return_value=None)
    redis_client.setex = AsyncMock(return_value=True)
    redis_client.publish = AsyncMock(return_value=1)
    redis_client.close = AsyncMock()
    return redis_client


@pytest.fixture
async def quote_service(mock_broker, mock_redis):
    """Create a quote service instance with mocks."""
    service = QuoteService(
        broker=mock_broker,
        redis_client=mock_redis,
        cache_ttl=5,
        history_enabled=True
    )
    service._initialized = True
    return service


class TestQuoteService:
    """Test the QuoteService functionality."""
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, mock_broker):
        """Test service initialization."""
        with patch('src.data.quote_service.redis.from_url') as mock_redis_from_url:
            mock_redis_client = AsyncMock()
            mock_redis_client.ping = AsyncMock(return_value=True)
            # Make from_url return a coroutine that resolves to the client
            async def mock_from_url(*args, **kwargs):
                return mock_redis_client
            mock_redis_from_url.side_effect = mock_from_url
            
            service = QuoteService(broker=mock_broker)
            await service.initialize()
            
            assert service._initialized
            assert service.broker == mock_broker
            assert service.redis_client == mock_redis_client
            mock_redis_client.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_single_quote(self, quote_service, mock_broker):
        """Test fetching a single quote."""
        # Mock broker response
        mock_response = {
            'AAPL': {
                'quote': {
                    'bidPrice': 150.00,
                    'askPrice': 150.05,
                    'lastPrice': 150.02,
                    'bidSize': 100,
                    'askSize': 200,
                    'lastSize': 50,
                    'totalVolume': 1000000
                }
            }
        }
        mock_broker.get_quotes.return_value = mock_response
        
        quote = await quote_service.get_quote("AAPL")
        
        assert quote is not None
        assert quote.symbol == "AAPL"
        assert quote.bid_price == 150.00
        assert quote.spread == pytest.approx(0.05, rel=1e-9)
        
        # Verify broker was called
        mock_broker.get_quotes.assert_called_once_with(["AAPL"])
    
    @pytest.mark.asyncio
    async def test_get_quote_with_cache_hit(self, quote_service, mock_redis):
        """Test getting quote from cache."""
        # Mock cached quote
        cached_data = {
            'symbol': 'AAPL',
            'bid_price': 150.00,
            'ask_price': 150.05,
            'last_price': 150.02,
            'bid_size': 100,
            'ask_size': 200,
            'last_size': 50,
            'volume': 1000000,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        mock_redis.get.return_value = json.dumps(cached_data)
        
        quote = await quote_service.get_quote("AAPL", use_cache=True)
        
        assert quote is not None
        assert quote.symbol == "AAPL"
        assert quote.bid_price == 150.00
        
        # Verify cache was checked
        mock_redis.get.assert_called_once_with("quote:AAPL")
        # Broker should not be called
        quote_service.broker.get_quotes.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_batch_quote_fetching(self, quote_service, mock_broker):
        """Test batch quote fetching."""
        symbols = ["AAPL", "GOOGL", "MSFT"]
        
        # Mock broker response
        mock_response = {
            'AAPL': {
                'quote': {
                    'bidPrice': 150.00,
                    'askPrice': 150.05,
                    'lastPrice': 150.02,
                    'bidSize': 100,
                    'askSize': 200,
                    'lastSize': 50,
                    'totalVolume': 1000000
                }
            },
            'GOOGL': {
                'quote': {
                    'bidPrice': 2800.00,
                    'askPrice': 2800.50,
                    'lastPrice': 2800.25,
                    'bidSize': 10,
                    'askSize': 20,
                    'lastSize': 5,
                    'totalVolume': 500000
                }
            },
            'MSFT': {
                'quote': {
                    'bidPrice': 300.00,
                    'askPrice': 300.10,
                    'lastPrice': 300.05,
                    'bidSize': 50,
                    'askSize': 100,
                    'lastSize': 25,
                    'totalVolume': 750000
                }
            }
        }
        mock_broker.get_quotes.return_value = mock_response
        
        quotes = await quote_service.get_quotes_batch(symbols)
        
        assert len(quotes) == 3
        assert "AAPL" in quotes
        assert "GOOGL" in quotes
        assert "MSFT" in quotes
        assert quotes["AAPL"].bid_price == 150.00
        assert quotes["GOOGL"].bid_price == 2800.00
    
    @pytest.mark.asyncio
    async def test_batch_with_partial_cache(self, quote_service, mock_broker, mock_redis):
        """Test batch fetching with some quotes in cache."""
        symbols = ["AAPL", "GOOGL", "MSFT"]
        
        # Mock cache - only AAPL is cached
        async def mock_get(key):
            if key == "quote:AAPL":
                return json.dumps({
                    'symbol': 'AAPL',
                    'bid_price': 149.00,  # Different price (cached)
                    'ask_price': 149.05,
                    'last_price': 149.02,
                    'bid_size': 100,
                    'ask_size': 200,
                    'last_size': 50,
                    'volume': 900000,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
            return None
        
        mock_redis.get.side_effect = mock_get
        
        # Mock broker response for non-cached symbols
        mock_response = {
            'GOOGL': {
                'quote': {
                    'bidPrice': 2800.00,
                    'askPrice': 2800.50,
                    'lastPrice': 2800.25,
                    'bidSize': 10,
                    'askSize': 20,
                    'lastSize': 5,
                    'totalVolume': 500000
                }
            },
            'MSFT': {
                'quote': {
                    'bidPrice': 300.00,
                    'askPrice': 300.10,
                    'lastPrice': 300.05,
                    'bidSize': 50,
                    'askSize': 100,
                    'lastSize': 25,
                    'totalVolume': 750000
                }
            }
        }
        mock_broker.get_quotes.return_value = mock_response
        
        quotes = await quote_service.get_quotes_batch(symbols, use_cache=True)
        
        assert len(quotes) == 3
        assert quotes["AAPL"].bid_price == 149.00  # From cache
        assert quotes["GOOGL"].bid_price == 2800.00  # From API
        assert quotes["MSFT"].bid_price == 300.00  # From API
        
        # Broker should only be called for non-cached symbols
        mock_broker.get_quotes.assert_called_once_with(["GOOGL", "MSFT"])
    
    @pytest.mark.asyncio
    async def test_quote_history_tracking(self, quote_service, mock_broker):
        """Test quote history tracking."""
        # Mock broker response
        mock_response = {
            'AAPL': {
                'quote': {
                    'bidPrice': 150.00,
                    'askPrice': 150.05,
                    'lastPrice': 150.02,
                    'bidSize': 100,
                    'askSize': 200,
                    'lastSize': 50,
                    'totalVolume': 1000000
                }
            }
        }
        mock_broker.get_quotes.return_value = mock_response
        
        # Fetch quote multiple times
        for i in range(3):
            await quote_service.get_quote("AAPL", use_cache=False)
        
        # Check history
        assert "AAPL" in quote_service._quote_history
        history = quote_service._quote_history["AAPL"]
        assert len(history.quotes) == 3
    
    @pytest.mark.asyncio
    async def test_spread_statistics(self, quote_service):
        """Test spread statistics calculation."""
        quotes = [
            Quote(
                symbol="AAPL",
                bid_price=150.00,
                ask_price=150.05,
                last_price=150.02,
                bid_size=100,
                ask_size=200,
                last_size=50,
                volume=1000000,
                timestamp=datetime.now(timezone.utc)
            ),
            Quote(
                symbol="AAPL",
                bid_price=150.10,
                ask_price=150.20,
                last_price=150.15,
                bid_size=100,
                ask_size=200,
                last_size=50,
                volume=1000000,
                timestamp=datetime.now(timezone.utc)
            )
        ]
        
        stats = quote_service.calculate_spread_stats(quotes)
        
        assert stats['avg_spread'] == pytest.approx(0.075, rel=1e-9)  # (0.05 + 0.10) / 2
        assert stats['min_spread'] == pytest.approx(0.05, rel=1e-9)
        assert stats['max_spread'] == pytest.approx(0.10, rel=1e-9)
        assert stats['total_spread_cost'] == pytest.approx(0.15, rel=1e-9)
    
    @pytest.mark.asyncio
    async def test_error_handling(self, quote_service, mock_broker):
        """Test error handling for API failures."""
        # Mock broker error
        mock_broker.get_quotes.side_effect = MarketDataError("API error")
        
        quote = await quote_service.get_quote("AAPL")
        assert quote is None
    
    @pytest.mark.asyncio
    async def test_redis_error_handling(self, quote_service, mock_redis):
        """Test handling of Redis errors."""
        # Mock Redis error
        mock_redis.get.side_effect = RedisError("Connection error")
        
        # Should fall back to API call
        mock_response = {
            'AAPL': {
                'quote': {
                    'bidPrice': 150.00,
                    'askPrice': 150.05,
                    'lastPrice': 150.02,
                    'bidSize': 100,
                    'askSize': 200,
                    'lastSize': 50,
                    'totalVolume': 1000000
                }
            }
        }
        quote_service.broker.get_quotes.return_value = mock_response
        
        quote = await quote_service.get_quote("AAPL", use_cache=True)
        
        assert quote is not None
        assert quote.symbol == "AAPL"
        # Broker should be called despite cache error
        quote_service.broker.get_quotes.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_quote_metrics(self, quote_service):
        """Test quote metrics calculation."""
        # Add some quote history
        history = QuoteHistory("AAPL")
        base_time = datetime.now(timezone.utc)
        
        for i in range(10):
            quote = Quote(
                symbol="AAPL",
                bid_price=150.00 + (i * 0.1),
                ask_price=150.05 + (i * 0.1),
                last_price=150.02 + (i * 0.1),
                bid_size=100,
                ask_size=200,
                last_size=50,
                volume=1000000 + (i * 10000),
                timestamp=base_time - timedelta(minutes=9-i)  # 9 minutes ago to now
            )
            history.add_quote(quote)
        
        quote_service._quote_history["AAPL"] = history
        
        metrics = quote_service.get_quote_metrics("AAPL", minutes=5)
        
        # Last 5 minutes should include quotes with indices 5-9 (prices 150.52-150.92)
        assert metrics['price_range'][0] == pytest.approx(150.52, rel=1e-9)  # Min price in last 5 minutes
        assert metrics['price_range'][1] == pytest.approx(150.92, rel=1e-9)  # Max price in last 5 minutes
        assert metrics['price_volatility'] == pytest.approx(0.4, rel=1e-9)
        assert metrics['volume'] == 40000  # Volume difference (1050000 - 1050000 + 40000)
        assert metrics['avg_spread'] == pytest.approx(0.05, rel=1e-9)  # Constant spread in test data
    
    @pytest.mark.asyncio
    async def test_pubsub_functionality(self, quote_service, mock_redis):
        """Test pub/sub functionality."""
        # Create a mock pubsub
        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        
        pubsub = await quote_service.subscribe_to_updates()
        
        assert pubsub == mock_pubsub
        mock_pubsub.subscribe.assert_called_once_with("quote_updates")
    
    @pytest.mark.asyncio
    async def test_shutdown(self, quote_service, mock_redis):
        """Test service shutdown."""
        await quote_service.shutdown()
        
        mock_redis.close.assert_called_once()


class TestQuoteServiceIntegration:
    """Integration tests with actual Redis (if available)."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_with_real_redis(self):
        """Test with real Redis connection if available."""
        try:
            # Try to connect to Redis
            redis_client = await redis.from_url(
                "redis://localhost:6379/1",  # Use DB 1 for tests
                encoding="utf-8",
                decode_responses=True
            )
            await redis_client.ping()
            
            # Create service with real Redis
            mock_broker = AsyncMock()
            service = QuoteService(
                broker=mock_broker,
                redis_client=redis_client,
                cache_ttl=2  # Short TTL for testing
            )
            service._initialized = True
            
            # Mock broker response
            mock_response = {
                'AAPL': {
                    'quote': {
                        'bidPrice': 150.00,
                        'askPrice': 150.05,
                        'lastPrice': 150.02,
                        'bidSize': 100,
                        'askSize': 200,
                        'lastSize': 50,
                        'totalVolume': 1000000
                    }
                }
            }
            mock_broker.get_quotes.return_value = mock_response
            
            # First call - should hit API
            quote1 = await service.get_quote("AAPL")
            assert quote1.bid_price == 150.00
            assert mock_broker.get_quotes.call_count == 1
            
            # Second call - should hit cache
            quote2 = await service.get_quote("AAPL")
            assert quote2.bid_price == 150.00
            assert mock_broker.get_quotes.call_count == 1  # Not called again
            
            # Wait for cache to expire
            await asyncio.sleep(2.5)
            
            # Third call - cache expired, should hit API
            quote3 = await service.get_quote("AAPL")
            assert quote3.bid_price == 150.00
            assert mock_broker.get_quotes.call_count == 2
            
            # Cleanup
            await redis_client.flushdb()
            await redis_client.close()
            
        except (ConnectionError, RedisError):
            pytest.skip("Redis not available")