"""Tests for enhanced historical data fetcher."""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import time

from src.data.historical_data_enhanced import (
    EnhancedHistoricalDataFetcher,
    FetchProgress,
    ValidationResult,
    OHLCValidator,
    VolumeValidator,
    TimestampValidator,
    ValidationPipeline,
    BatchProcessor,
    TimeFrame,
    LoggingProgressCallback,
    DetailedProgressCallback
)
from src.broker import SchwabBroker
from src.data.models import PriceData


# Mock data for tests
MOCK_CANDLE_DATA = {
    'candles': [
        {
            'datetime': 1701432000000,  # 2023-12-01 12:00:00 UTC
            'open': 150.00,
            'high': 151.50,
            'low': 149.50,
            'close': 151.00,
            'volume': 1000000
        },
        {
            'datetime': 1701432300000,  # 2023-12-01 12:05:00 UTC
            'open': 151.00,
            'high': 152.00,
            'low': 150.50,
            'close': 151.50,
            'volume': 800000,
            'vwap': 151.25
        },
        {
            'datetime': 1701432600000,  # 2023-12-01 12:10:00 UTC
            'open': 151.50,
            'high': 152.50,
            'low': 151.00,
            'close': 152.00,
            'volume': 1200000
        }
    ]
}

INVALID_CANDLE_DATA = {
    'candles': [
        {
            'datetime': 1701432000000,
            'open': 150.00,
            'high': 149.00,  # High < Open (invalid)
            'low': 149.50,
            'close': 151.00,
            'volume': 1000000
        },
        {
            'datetime': 1701432300000,
            'open': 151.00,
            'high': 152.00,
            'low': 153.00,  # Low > High (invalid)
            'close': 151.50,
            'volume': -1000  # Negative volume (invalid)
        }
    ]
}


class TestFetchProgress:
    """Test FetchProgress data class."""
    
    def test_progress_percentage(self):
        """Test progress percentage calculation."""
        progress = FetchProgress(total_symbols=10)
        assert progress.progress_percentage == 0.0
        
        progress.completed_symbols = 5
        assert progress.progress_percentage == 50.0
        
        progress.completed_symbols = 10
        assert progress.progress_percentage == 100.0
    
    def test_elapsed_time(self):
        """Test elapsed time calculation."""
        progress = FetchProgress(total_symbols=10)
        initial_time = progress.start_time
        
        # Sleep briefly
        time.sleep(0.1)
        
        assert progress.elapsed_time > 0.1
        assert progress.start_time == initial_time  # Start time shouldn't change
    
    def test_estimated_time_remaining(self):
        """Test ETA calculation."""
        progress = FetchProgress(total_symbols=10)
        
        # No progress yet
        assert progress.estimated_time_remaining == 0.0
        
        # Simulate some progress
        progress.completed_symbols = 2
        progress.start_time = time.time() - 10  # 10 seconds elapsed
        
        # 2 symbols in 10 seconds = 0.2 symbols/sec
        # 8 remaining symbols / 0.2 = 40 seconds
        assert abs(progress.estimated_time_remaining - 40) < 1


class TestValidators:
    """Test individual validators."""
    
    @pytest.mark.asyncio
    async def test_ohlc_validator_valid(self):
        """Test OHLC validator with valid data."""
        validator = OHLCValidator()
        
        data = {
            'open': 100.0,
            'high': 105.0,
            'low': 99.0,
            'close': 103.0
        }
        
        result = await validator.validate(data)
        assert result.is_valid
        assert len(result.errors) == 0
        assert result.cleaned_data == data
    
    @pytest.mark.asyncio
    async def test_ohlc_validator_invalid_relationships(self):
        """Test OHLC validator with invalid price relationships."""
        validator = OHLCValidator()
        
        # High < Low
        data = {
            'open': 100.0,
            'high': 99.0,
            'low': 101.0,
            'close': 100.0
        }
        
        result = await validator.validate(data)
        assert not result.is_valid
        assert any("Low 101" in error and "High 99" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_ohlc_validator_extreme_range_warning(self):
        """Test OHLC validator extreme price range warning."""
        validator = OHLCValidator()
        
        data = {
            'open': 100.0,
            'high': 160.0,  # 60% range
            'low': 100.0,
            'close': 150.0
        }
        
        result = await validator.validate(data)
        assert result.is_valid
        assert any("Extreme price range" in warning for warning in result.warnings)
    
    @pytest.mark.asyncio
    async def test_volume_validator(self):
        """Test volume validator."""
        validator = VolumeValidator(min_volume=0, max_volume=10_000_000)
        
        # Valid volume
        result = await validator.validate({'volume': 1000000})
        assert result.is_valid
        
        # Negative volume
        result = await validator.validate({'volume': -100})
        assert not result.is_valid
        
        # Unusually high volume
        result = await validator.validate({'volume': 100_000_000})
        assert result.is_valid  # Valid but should have warning
        assert len(result.warnings) > 0
    
    @pytest.mark.asyncio
    async def test_timestamp_validator(self):
        """Test timestamp validator."""
        min_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
        max_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        validator = TimestampValidator(min_date=min_date, max_date=max_date)
        
        # Valid timestamp
        result = await validator.validate({
            'timestamp': datetime(2023, 6, 1, tzinfo=timezone.utc)
        })
        assert result.is_valid
        
        # Too old
        result = await validator.validate({
            'timestamp': datetime(2019, 1, 1, tzinfo=timezone.utc)
        })
        assert not result.is_valid
        
        # Weekend warning
        result = await validator.validate({
            'timestamp': datetime(2023, 6, 3, tzinfo=timezone.utc)  # Saturday
        })
        assert result.is_valid
        assert any("Weekend timestamp" in warning for warning in result.warnings)


class TestValidationPipeline:
    """Test validation pipeline."""
    
    @pytest.mark.asyncio
    async def test_pipeline_all_valid(self):
        """Test pipeline with all valid data."""
        pipeline = ValidationPipeline()
        
        data = {
            'symbol': 'AAPL',
            'timestamp': datetime(2023, 12, 1, 12, 0, tzinfo=timezone.utc),
            'open': 150.0,
            'high': 152.0,
            'low': 149.0,
            'close': 151.0,
            'volume': 1000000
        }
        
        result = await pipeline.validate(data)
        assert result.is_valid
        assert result.cleaned_data == data
    
    @pytest.mark.asyncio
    async def test_pipeline_stops_on_first_error(self):
        """Test pipeline stops on first validation error."""
        # Create a pipeline with a failing validator first
        class AlwaysFailValidator:
            async def validate(self, data):
                return ValidationResult(
                    is_valid=False,
                    errors=["Always fails"]
                )
        
        class NeverCalledValidator:
            def __init__(self):
                self.called = False
            
            async def validate(self, data):
                self.called = True
                return ValidationResult(is_valid=True)
        
        never_called = NeverCalledValidator()
        pipeline = ValidationPipeline(validators=[
            AlwaysFailValidator(),
            never_called
        ])
        
        result = await pipeline.validate({})
        assert not result.is_valid
        assert not never_called.called


class TestBatchProcessor:
    """Test batch processor."""
    
    def test_create_batches(self):
        """Test batch creation."""
        processor = BatchProcessor(batch_size=3)
        
        symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'META', 'NVDA']
        batches = processor.create_batches(symbols)
        
        assert len(batches) == 3
        assert batches[0] == ['AAPL', 'GOOGL', 'MSFT']
        assert batches[1] == ['AMZN', 'TSLA', 'META']
        assert batches[2] == ['NVDA']
    
    def test_create_batches_empty(self):
        """Test batch creation with empty list."""
        processor = BatchProcessor(batch_size=5)
        batches = processor.create_batches([])
        assert batches == []


@pytest.fixture
async def mock_broker():
    """Create a mock broker."""
    broker = AsyncMock(spec=SchwabBroker)
    broker.get_price_history = AsyncMock(return_value=MOCK_CANDLE_DATA)
    return broker


@pytest.fixture
async def fetcher(mock_broker):
    """Create an enhanced fetcher with mock broker."""
    fetcher = EnhancedHistoricalDataFetcher(
        broker=mock_broker,
        max_workers=2,
        batch_size=5
    )
    await fetcher.initialize()
    return fetcher


class TestEnhancedHistoricalDataFetcher:
    """Test enhanced historical data fetcher."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, fetcher):
        """Test fetcher initialization."""
        assert fetcher.broker is not None
        assert fetcher.max_workers == 2
        assert fetcher._worker_semaphore._value == 2
    
    @pytest.mark.asyncio
    async def test_progress_callbacks(self, fetcher):
        """Test progress callback mechanism."""
        callback_calls = []
        
        async def test_callback(progress: FetchProgress, message: str):
            callback_calls.append((progress.completed_symbols, message))
        
        fetcher.add_progress_callback(test_callback)
        
        # Notify progress
        progress = FetchProgress(total_symbols=10)
        await fetcher._notify_progress(progress, "Test message")
        
        assert len(callback_calls) == 1
        assert callback_calls[0] == (0, "Test message")
    
    @pytest.mark.asyncio
    async def test_fetch_single_symbol(self, fetcher, mock_broker):
        """Test fetching data for a single symbol."""
        with patch.object(fetcher, '_save_to_database', new_callable=AsyncMock):
            result = await fetcher._fetch_symbol_data(
                'AAPL',
                TimeFrame.MINUTE_5,
                datetime(2023, 12, 1, tzinfo=timezone.utc),
                datetime(2023, 12, 2, tzinfo=timezone.utc),
                save_to_db=True,
                detect_duplicates=False,
                fill_gaps=False
            )
        
        assert result['symbol'] == 'AAPL'
        assert len(result['records']) == 3
        assert result['duplicates'] == 0
        assert result['validation_errors'] == []
    
    @pytest.mark.asyncio
    async def test_fetch_symbols_batch(self, fetcher, mock_broker):
        """Test batch fetching for multiple symbols."""
        symbols = ['AAPL', 'GOOGL', 'MSFT']
        
        # Track progress updates
        progress_updates = []
        
        async def progress_callback(progress: FetchProgress, message: str):
            progress_updates.append({
                'completed': progress.completed_symbols,
                'total': progress.total_symbols,
                'message': message
            })
        
        fetcher.add_progress_callback(progress_callback)
        
        with patch.object(fetcher, '_save_to_database', new_callable=AsyncMock):
            result = await fetcher.fetch_symbols_batch(
                symbols,
                TimeFrame.MINUTE_5,
                save_to_db=True,
                detect_duplicates=False,
                fill_gaps=False
            )
        
        # Check results
        assert 'results' in result
        assert 'statistics' in result
        
        stats = result['statistics']
        assert stats['total_symbols'] == 3
        assert stats['completed_symbols'] == 3
        assert stats['failed_symbols'] == 0
        assert stats['total_records'] == 9  # 3 records per symbol
        
        # Check progress updates
        assert len(progress_updates) > 0
        assert any("Starting batch fetch" in update['message'] for update in progress_updates)
        assert any("completed" in update['message'] for update in progress_updates)
    
    @pytest.mark.asyncio
    async def test_duplicate_detection(self, fetcher, mock_broker):
        """Test duplicate detection functionality."""
        # Mock existing timestamps
        existing_timestamps = {
            datetime.fromtimestamp(1701432000, tz=timezone.utc),  # First candle
            datetime.fromtimestamp(1701432300, tz=timezone.utc),  # Second candle
        }
        
        with patch.object(fetcher, '_get_existing_timestamps', return_value=existing_timestamps):
            with patch.object(fetcher, '_save_to_database', new_callable=AsyncMock):
                result = await fetcher._fetch_symbol_data(
                    'AAPL',
                    TimeFrame.MINUTE_5,
                    datetime(2023, 12, 1, tzinfo=timezone.utc),
                    datetime(2023, 12, 2, tzinfo=timezone.utc),
                    save_to_db=True,
                    detect_duplicates=True,
                    fill_gaps=False
                )
        
        # Should only have 1 new record (third candle)
        assert len(result['records']) == 1
        assert result['duplicates'] == 2
        assert result['existing_records'] == 2
    
    @pytest.mark.asyncio
    async def test_validation_with_invalid_data(self, fetcher, mock_broker):
        """Test validation with invalid data."""
        mock_broker.get_price_history.return_value = INVALID_CANDLE_DATA
        
        with patch.object(fetcher, '_save_to_database', new_callable=AsyncMock):
            result = await fetcher._fetch_symbol_data(
                'AAPL',
                TimeFrame.MINUTE_5,
                datetime(2023, 12, 1, tzinfo=timezone.utc),
                datetime(2023, 12, 2, tzinfo=timezone.utc),
                save_to_db=False,
                detect_duplicates=False,
                fill_gaps=False
            )
        
        # Should have validation errors
        assert len(result['validation_errors']) > 0
        assert len(result['records']) < len(INVALID_CANDLE_DATA['candles'])
    
    @pytest.mark.asyncio
    async def test_gap_detection(self, fetcher):
        """Test missing data detection."""
        # Mock database query results with gaps
        mock_timestamps = [
            datetime(2023, 12, 1, 9, 0, tzinfo=timezone.utc),
            datetime(2023, 12, 1, 9, 5, tzinfo=timezone.utc),
            # Gap from 9:05 to 10:00
            datetime(2023, 12, 1, 10, 0, tzinfo=timezone.utc),
            datetime(2023, 12, 1, 10, 5, tzinfo=timezone.utc),
        ]
        
        with patch('src.data.historical_data_enhanced.db_service.get_async_session') as mock_session:
            mock_result = Mock()
            mock_result.__iter__ = Mock(return_value=iter([(ts,) for ts in mock_timestamps]))
            
            mock_execute = AsyncMock(return_value=mock_result)
            mock_session.return_value.__aenter__.return_value.execute = mock_execute
            
            gaps = await fetcher.detect_missing_data(
                'AAPL',
                TimeFrame.MINUTE_5,
                datetime(2023, 12, 1, 9, 0, tzinfo=timezone.utc),
                datetime(2023, 12, 1, 11, 0, tzinfo=timezone.utc),
                market_hours_only=False
            )
        
        assert len(gaps) > 0
    
    @pytest.mark.asyncio
    async def test_data_statistics(self, fetcher):
        """Test data statistics calculation."""
        with patch('src.data.historical_data_enhanced.db_service.get_async_session') as mock_session:
            mock_row = Mock()
            mock_row.count = 1000
            mock_row.min_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
            mock_row.max_date = datetime(2023, 12, 31, tzinfo=timezone.utc)
            mock_row.avg_volume = Decimal('1000000')
            mock_row.min_price = Decimal('100.0')
            mock_row.max_price = Decimal('200.0')
            
            mock_result = Mock()
            mock_result.first = Mock(return_value=mock_row)
            
            mock_execute = AsyncMock(return_value=mock_result)
            mock_session.return_value.__aenter__.return_value.execute = mock_execute
            
            stats = await fetcher.get_data_statistics('AAPL')
        
        assert stats['symbol'] == 'AAPL'
        assert stats['record_count'] == 1000
        assert stats['date_range']['start'] == datetime(2023, 1, 1, tzinfo=timezone.utc)
        assert stats['date_range']['end'] == datetime(2023, 12, 31, tzinfo=timezone.utc)
        assert stats['price_range']['min'] == 100.0
        assert stats['price_range']['max'] == 200.0
        assert stats['average_volume'] == 1000000.0
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, fetcher, mock_broker):
        """Test rate limiting behavior."""
        # Simulate rate limit error
        mock_broker.get_price_history.side_effect = [
            Exception("429 Rate limit exceeded"),
            MOCK_CANDLE_DATA  # Success on retry
        ]
        
        with patch.object(fetcher, '_save_to_database', new_callable=AsyncMock):
            with patch('asyncio.sleep', new_callable=AsyncMock):  # Speed up test
                result = await fetcher._fetch_symbol_data(
                    'AAPL',
                    TimeFrame.MINUTE_5,
                    datetime(2023, 12, 1, tzinfo=timezone.utc),
                    datetime(2023, 12, 2, tzinfo=timezone.utc),
                    save_to_db=False,
                    detect_duplicates=False,
                    fill_gaps=False
                )
        
        # Should eventually succeed
        assert len(result['records']) == 3
        assert mock_broker.get_price_history.call_count == 2
    
    @pytest.mark.asyncio
    async def test_worker_error_handling(self, fetcher, mock_broker):
        """Test worker error handling."""
        # Make one symbol fail
        def side_effect(**kwargs):
            if kwargs.get('symbol') == 'GOOGL':
                raise Exception("API Error")
            return MOCK_CANDLE_DATA
        
        mock_broker.get_price_history.side_effect = side_effect
        
        with patch.object(fetcher, '_save_to_database', new_callable=AsyncMock):
            result = await fetcher.fetch_symbols_batch(
                ['AAPL', 'GOOGL', 'MSFT'],
                TimeFrame.MINUTE_5,
                save_to_db=False
            )
        
        stats = result['statistics']
        # Should have 2 successful and 1 failed
        assert stats['completed_symbols'] + stats['failed_symbols'] == 3
        assert stats['failed_symbols'] == 1
        
        # Check GOOGL has error
        assert 'error' in result['results']['GOOGL']


class TestProgressCallbacks:
    """Test progress callback implementations."""
    
    @pytest.mark.asyncio
    async def test_logging_callback(self, caplog):
        """Test logging progress callback."""
        callback = LoggingProgressCallback(log_interval=25)
        progress = FetchProgress(total_symbols=100)
        
        # Should not log at 0%
        await callback(progress, "Starting")
        assert len(caplog.records) == 0
        
        # Should log at 25%
        progress.completed_symbols = 25
        await callback(progress, "Quarter done")
        assert len(caplog.records) == 1
        assert "25%" in caplog.records[0].message
        
        # Should not log at 30% (not enough interval)
        progress.completed_symbols = 30
        await callback(progress, "Still working")
        assert len(caplog.records) == 1
        
        # Should log at 50%
        progress.completed_symbols = 50
        await callback(progress, "Half done")
        assert len(caplog.records) == 2
    
    @pytest.mark.asyncio
    async def test_detailed_callback(self, caplog):
        """Test detailed progress callback."""
        callback = DetailedProgressCallback()
        progress = FetchProgress(total_symbols=100)
        
        # Simulate some progress
        progress.completed_symbols = 10
        progress.total_records = 1000
        progress.start_time = time.time() - 10  # 10 seconds elapsed
        
        await callback(progress, "Working")
        
        # Check log contains expected elements
        assert len(caplog.records) == 1
        log_message = caplog.records[0].message
        assert "10.0%" in log_message or "10%" in log_message
        assert "10/100 symbols" in log_message
        assert "Records: 1,000" in log_message
        assert "symbols/sec" in log_message
        assert "ETA:" in log_message