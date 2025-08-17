"""Enhanced Historical data fetcher with batch processing and advanced features."""

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Protocol
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
from sqlalchemy import text, and_, select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..auth import get_auth_service
from ..broker import SchwabBroker
from ..config import get_settings
from ..utils.logger import get_logger
from .database import db_service
from .models import PriceData

logger = get_logger(__name__)
settings = get_settings()


class TimeFrame(str, Enum):
    """Available timeframes for historical data."""
    
    MINUTE_1 = "minute"
    MINUTE_5 = "5min"
    MINUTE_10 = "10min"
    MINUTE_15 = "15min"
    MINUTE_30 = "30min"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class FetchProgress:
    """Progress tracking for batch operations."""
    total_symbols: int
    completed_symbols: int = 0
    failed_symbols: int = 0
    total_records: int = 0
    duplicates_found: int = 0
    gaps_filled: int = 0
    start_time: float = field(default_factory=time.time)
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_symbols == 0:
            return 0.0
        return (self.completed_symbols / self.total_symbols) * 100
    
    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time
    
    @property
    def estimated_time_remaining(self) -> float:
        """Estimate remaining time based on current pace."""
        if self.completed_symbols == 0:
            return 0.0
        
        rate = self.completed_symbols / self.elapsed_time
        remaining = self.total_symbols - self.completed_symbols
        return remaining / rate if rate > 0 else 0.0


@dataclass
class ValidationResult:
    """Result of data validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    cleaned_data: Optional[Dict[str, Any]] = None


class DataValidator(Protocol):
    """Protocol for data validators."""
    
    async def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate a single data record."""
        ...


class OHLCValidator:
    """Validates OHLC price relationships."""
    
    async def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Ensure OHLC values follow logical relationships."""
        errors = []
        warnings = []
        
        try:
            open_price = Decimal(str(data['open']))
            high_price = Decimal(str(data['high']))
            low_price = Decimal(str(data['low']))
            close_price = Decimal(str(data['close']))
            
            # Check basic OHLC relationships
            if not (low_price <= open_price <= high_price):
                errors.append(f"Invalid OHLC: Open {open_price} not between Low {low_price} and High {high_price}")
            
            if not (low_price <= close_price <= high_price):
                errors.append(f"Invalid OHLC: Close {close_price} not between Low {low_price} and High {high_price}")
            
            if low_price > high_price:
                errors.append(f"Invalid OHLC: Low {low_price} > High {high_price}")
            
            # Check for zero or negative prices
            if any(price <= 0 for price in [open_price, high_price, low_price, close_price]):
                errors.append("Invalid OHLC: Zero or negative prices detected")
            
            # Warn about extreme price movements
            if high_price > low_price * Decimal('1.5'):  # 50% range
                warnings.append(f"Extreme price range: {((high_price - low_price) / low_price * 100):.1f}%")
            
        except (KeyError, ValueError, TypeError) as e:
            errors.append(f"Error parsing OHLC data: {e}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            cleaned_data=data if len(errors) == 0 else None
        )


class VolumeValidator:
    """Validates volume data."""
    
    def __init__(self, min_volume: int = 0, max_volume: int = 1_000_000_000):
        self.min_volume = min_volume
        self.max_volume = max_volume
    
    async def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate volume is within reasonable bounds."""
        errors = []
        warnings = []
        
        try:
            volume = int(data['volume'])
            
            if volume < self.min_volume:
                errors.append(f"Volume {volume} below minimum {self.min_volume}")
            
            if volume > self.max_volume:
                warnings.append(f"Unusually high volume: {volume:,}")
            
            # Check for suspiciously round numbers
            if volume > 1000 and volume % 1000 == 0:
                warnings.append(f"Suspiciously round volume: {volume:,}")
                
        except (KeyError, ValueError, TypeError) as e:
            errors.append(f"Error parsing volume data: {e}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            cleaned_data=data if len(errors) == 0 else None
        )


class TimestampValidator:
    """Validates timestamp data."""
    
    def __init__(self, min_date: Optional[datetime] = None, max_date: Optional[datetime] = None):
        self.min_date = min_date or datetime(2000, 1, 1, tzinfo=timezone.utc)
        self.max_date = max_date or datetime.now(timezone.utc) + timedelta(days=1)
    
    async def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate timestamp is within reasonable bounds."""
        errors = []
        warnings = []
        
        try:
            timestamp = data['timestamp']
            
            if not isinstance(timestamp, datetime):
                errors.append(f"Timestamp is not a datetime object: {type(timestamp)}")
                return ValidationResult(is_valid=False, errors=errors)
            
            if timestamp < self.min_date:
                errors.append(f"Timestamp {timestamp} is before minimum date {self.min_date}")
            
            if timestamp > self.max_date:
                errors.append(f"Timestamp {timestamp} is after maximum date {self.max_date}")
            
            # Warn about weekend data for stocks
            if timestamp.weekday() in [5, 6]:  # Saturday, Sunday
                warnings.append(f"Weekend timestamp: {timestamp}")
                
        except KeyError as e:
            errors.append(f"Missing timestamp field: {e}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            cleaned_data=data if len(errors) == 0 else None
        )


class ValidationPipeline:
    """Manages a pipeline of validators."""
    
    def __init__(self, validators: Optional[List[DataValidator]] = None):
        self.validators = validators or [
            OHLCValidator(),
            VolumeValidator(),
            TimestampValidator()
        ]
    
    async def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Run all validators on the data."""
        all_errors = []
        all_warnings = []
        current_data = data
        
        for validator in self.validators:
            result = await validator.validate(current_data)
            
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
            
            if not result.is_valid:
                # Stop on first validation failure
                return ValidationResult(
                    is_valid=False,
                    errors=all_errors,
                    warnings=all_warnings
                )
            
            # Use cleaned data for next validator
            if result.cleaned_data:
                current_data = result.cleaned_data
        
        return ValidationResult(
            is_valid=True,
            errors=all_errors,
            warnings=all_warnings,
            cleaned_data=current_data
        )


class BatchProcessor:
    """Handles batch processing of symbols."""
    
    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size
    
    def create_batches(self, symbols: List[str]) -> List[List[str]]:
        """Create batches of symbols for processing."""
        batches = []
        for i in range(0, len(symbols), self.batch_size):
            batch = symbols[i:i + self.batch_size]
            batches.append(batch)
        return batches


class ProgressCallback(Protocol):
    """Protocol for progress callbacks."""
    
    async def __call__(self, progress: FetchProgress, message: str) -> None:
        """Handle progress update."""
        ...


class EnhancedHistoricalDataFetcher:
    """Enhanced fetcher with batch processing, parallel fetching, and advanced features."""
    
    def __init__(
        self,
        broker: Optional[SchwabBroker] = None,
        max_workers: int = 10,
        batch_size: int = 10,
        validation_pipeline: Optional[ValidationPipeline] = None
    ):
        self.broker = broker
        self.max_workers = max_workers
        self.batch_processor = BatchProcessor(batch_size)
        self.validation_pipeline = validation_pipeline or ValidationPipeline()
        self._rate_limit_delay = 0.5
        self._max_rate_limit_delay = 60
        self._db_batch_size = settings.system.batch_insert_size
        self._progress_callbacks: List[ProgressCallback] = []
        self._worker_semaphore = asyncio.Semaphore(max_workers)
        
    async def initialize(self):
        """Initialize the fetcher."""
        if not self.broker:
            self.broker = await SchwabBroker().initialize()
        logger.info(f"Enhanced fetcher initialized with {self.max_workers} workers")
    
    def add_progress_callback(self, callback: ProgressCallback):
        """Add a progress callback."""
        self._progress_callbacks.append(callback)
    
    async def _notify_progress(self, progress: FetchProgress, message: str):
        """Notify all progress callbacks."""
        for callback in self._progress_callbacks:
            try:
                await callback(progress, message)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
    
    async def fetch_symbols_batch(
        self,
        symbols: List[str],
        timeframe: TimeFrame,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        save_to_db: bool = True,
        detect_duplicates: bool = True,
        fill_gaps: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch historical data for multiple symbols with batch processing.
        
        Returns:
            Dictionary with results and statistics
        """
        if not self.broker:
            raise RuntimeError("Fetcher not initialized. Call initialize() first.")
        
        # Initialize progress tracking
        progress = FetchProgress(total_symbols=len(symbols))
        await self._notify_progress(progress, "Starting batch fetch")
        
        # Create work queue
        work_queue = asyncio.Queue()
        results_queue = asyncio.Queue()
        
        # Add all symbols to work queue
        for symbol in symbols:
            await work_queue.put((symbol, timeframe, start_date, end_date))
        
        # Create worker tasks
        workers = []
        for i in range(min(self.max_workers, len(symbols))):
            worker = asyncio.create_task(
                self._worker(
                    worker_id=i,
                    work_queue=work_queue,
                    results_queue=results_queue,
                    progress=progress,
                    save_to_db=save_to_db,
                    detect_duplicates=detect_duplicates,
                    fill_gaps=fill_gaps
                )
            )
            workers.append(worker)
        
        # Wait for all work to complete
        await work_queue.join()
        
        # Cancel workers
        for worker in workers:
            worker.cancel()
        
        # Wait for cancellation
        await asyncio.gather(*workers, return_exceptions=True)
        
        # Collect results
        results = {}
        while not results_queue.empty():
            symbol, data = await results_queue.get()
            results[symbol] = data
        
        # Final progress notification
        await self._notify_progress(
            progress,
            f"Batch fetch completed: {progress.completed_symbols}/{progress.total_symbols} symbols, "
            f"{progress.total_records} records, {progress.elapsed_time:.1f}s"
        )
        
        return {
            'results': results,
            'statistics': {
                'total_symbols': progress.total_symbols,
                'completed_symbols': progress.completed_symbols,
                'failed_symbols': progress.failed_symbols,
                'total_records': progress.total_records,
                'duplicates_found': progress.duplicates_found,
                'gaps_filled': progress.gaps_filled,
                'elapsed_time': progress.elapsed_time
            }
        }
    
    async def _worker(
        self,
        worker_id: int,
        work_queue: asyncio.Queue,
        results_queue: asyncio.Queue,
        progress: FetchProgress,
        save_to_db: bool,
        detect_duplicates: bool,
        fill_gaps: bool
    ):
        """Worker coroutine for processing symbols."""
        logger.info(f"Worker {worker_id} started")
        
        while True:
            try:
                # Get work item with timeout
                symbol, timeframe, start_date, end_date = await asyncio.wait_for(
                    work_queue.get(),
                    timeout=1.0
                )
                
                async with self._worker_semaphore:
                    try:
                        # Notify progress
                        await self._notify_progress(
                            progress,
                            f"Worker {worker_id} processing {symbol}"
                        )
                        
                        # Fetch data
                        data = await self._fetch_symbol_data(
                            symbol, timeframe, start_date, end_date,
                            save_to_db, detect_duplicates, fill_gaps
                        )
                        
                        # Check if fetch resulted in error
                        if 'error' in data:
                            # Handle as failure
                            progress.failed_symbols += 1
                            await results_queue.put((symbol, data))
                            await self._notify_progress(
                                progress,
                                f"Failed {symbol}: {data['error']}"
                            )
                        else:
                            # Update progress for successful fetch
                            progress.completed_symbols += 1
                            progress.total_records += len(data.get('records', []))
                            progress.duplicates_found += data.get('duplicates', 0)
                            progress.gaps_filled += data.get('gaps_filled', 0)
                            
                            # Add to results
                            await results_queue.put((symbol, data))
                            
                            # Notify completion
                            await self._notify_progress(
                                progress,
                                f"Completed {symbol}: {len(data.get('records', []))} records "
                                f"({progress.progress_percentage:.1f}% complete)"
                            )
                        
                    except Exception as e:
                        logger.error(f"Worker {worker_id} error processing {symbol}: {e}")
                        progress.failed_symbols += 1
                        await results_queue.put((symbol, {'error': str(e)}))
                    
                    finally:
                        work_queue.task_done()
                        
            except asyncio.TimeoutError:
                # No more work, exit
                break
            except asyncio.CancelledError:
                # Shutdown requested
                break
        
        logger.info(f"Worker {worker_id} stopped")
    
    async def _fetch_symbol_data(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        save_to_db: bool,
        detect_duplicates: bool,
        fill_gaps: bool
    ) -> Dict[str, Any]:
        """Fetch data for a single symbol with all enhancements."""
        result = {
            'symbol': symbol,
            'records': [],
            'duplicates': 0,
            'gaps_filled': 0,
            'validation_errors': [],
            'validation_warnings': []
        }
        
        try:
            # Default date range
            if not end_date:
                end_date = datetime.now(timezone.utc)
            if not start_date:
                if timeframe in [TimeFrame.DAILY, TimeFrame.WEEKLY, TimeFrame.MONTHLY]:
                    start_date = end_date - timedelta(days=365)
                else:
                    start_date = end_date - timedelta(days=30)
            
            # Check for existing data if duplicate detection enabled
            existing_timestamps = set()
            if detect_duplicates and save_to_db:
                existing_timestamps = await self._get_existing_timestamps(
                    symbol, start_date, end_date
                )
                result['existing_records'] = len(existing_timestamps)
            
            # Fetch data from API
            raw_data = await self._fetch_with_retry(symbol, timeframe, start_date, end_date)
            
            if not raw_data:
                result['error'] = "No data returned from API"
                return result
            
            # Parse and validate data
            parsed_data = await self._parse_and_validate(symbol, raw_data, timeframe)
            
            # Filter duplicates
            if detect_duplicates:
                new_data = []
                for record in parsed_data['records']:
                    if record['timestamp'] not in existing_timestamps:
                        new_data.append(record)
                    else:
                        result['duplicates'] += 1
                parsed_data['records'] = new_data
            
            result['records'] = parsed_data['records']
            result['validation_errors'] = parsed_data['validation_errors']
            result['validation_warnings'] = parsed_data['validation_warnings']
            
            # Save to database
            if save_to_db and result['records']:
                await self._save_to_database(result['records'])
            
            # Fill gaps if requested
            if fill_gaps and save_to_db:
                gaps_filled = await self._fill_data_gaps(symbol, timeframe)
                result['gaps_filled'] = gaps_filled
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            result['error'] = str(e)
        
        return result
    
    async def _get_existing_timestamps(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> Set[datetime]:
        """Get existing timestamps from database for duplicate detection."""
        async with db_service.get_async_session() as session:
            result = await session.execute(
                select(PriceData.timestamp).where(
                    and_(
                        PriceData.symbol == symbol,
                        PriceData.timestamp >= start_date,
                        PriceData.timestamp <= end_date
                    )
                )
            )
            
            return {row[0] for row in result}
    
    async def _fetch_with_retry(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[Dict[str, Any]]:
        """Fetch data with retry logic."""
        retry_count = 0
        max_retries = 3
        current_delay = self._rate_limit_delay
        
        while retry_count < max_retries:
            try:
                # Apply rate limit
                await asyncio.sleep(current_delay)
                
                # Use broker to fetch data
                history = await self.broker.get_price_history(
                    symbol=symbol,
                    period_type=self._get_period_type(timeframe),
                    period=self._calculate_period(start_date, end_date, timeframe),
                    frequency_type=self._get_frequency_type(timeframe),
                    frequency=self._get_frequency(timeframe),
                    start_date=start_date,
                    end_date=end_date
                )
                
                # Adjust rate limit on success
                self._rate_limit_delay = max(0.5, self._rate_limit_delay * 0.9)
                
                return history
                
            except Exception as e:
                retry_count += 1
                if "429" in str(e) or "rate" in str(e).lower():
                    # Rate limit hit
                    self._rate_limit_delay = min(
                        self._rate_limit_delay * 2,
                        self._max_rate_limit_delay
                    )
                    current_delay = self._rate_limit_delay
                    logger.warning(
                        f"Rate limit hit for {symbol}. Retry {retry_count}/{max_retries} "
                        f"with delay {current_delay}s"
                    )
                else:
                    logger.error(f"Error fetching {symbol}: {e}")
                    if retry_count >= max_retries:
                        raise
                
                await asyncio.sleep(current_delay)
        
        return None
    
    def _get_period_type(self, timeframe: TimeFrame) -> str:
        """Get period type for API call."""
        if timeframe in [TimeFrame.MINUTE_1, TimeFrame.MINUTE_5, TimeFrame.MINUTE_10,
                        TimeFrame.MINUTE_15, TimeFrame.MINUTE_30]:
            return "day"
        elif timeframe == TimeFrame.DAILY:
            return "month"
        elif timeframe == TimeFrame.WEEKLY:
            return "month"
        elif timeframe == TimeFrame.MONTHLY:
            return "year"
        return "day"
    
    def _calculate_period(self, start_date: datetime, end_date: datetime, timeframe: TimeFrame) -> int:
        """Calculate period for API call."""
        delta = end_date - start_date
        
        if timeframe in [TimeFrame.MINUTE_1, TimeFrame.MINUTE_5, TimeFrame.MINUTE_10,
                        TimeFrame.MINUTE_15, TimeFrame.MINUTE_30]:
            return max(1, delta.days)
        elif timeframe == TimeFrame.DAILY:
            return max(1, delta.days // 30)
        elif timeframe == TimeFrame.WEEKLY:
            return max(1, delta.days // 30)
        elif timeframe == TimeFrame.MONTHLY:
            return max(1, delta.days // 365)
        return 1
    
    def _get_frequency_type(self, timeframe: TimeFrame) -> str:
        """Get frequency type for API call."""
        if timeframe in [TimeFrame.MINUTE_1, TimeFrame.MINUTE_5, TimeFrame.MINUTE_10,
                        TimeFrame.MINUTE_15, TimeFrame.MINUTE_30]:
            return "minute"
        elif timeframe == TimeFrame.DAILY:
            return "daily"
        elif timeframe == TimeFrame.WEEKLY:
            return "weekly"
        elif timeframe == TimeFrame.MONTHLY:
            return "monthly"
        return "daily"
    
    def _get_frequency(self, timeframe: TimeFrame) -> int:
        """Get frequency value for API call."""
        frequency_map = {
            TimeFrame.MINUTE_1: 1,
            TimeFrame.MINUTE_5: 5,
            TimeFrame.MINUTE_10: 10,
            TimeFrame.MINUTE_15: 15,
            TimeFrame.MINUTE_30: 30,
            TimeFrame.DAILY: 1,
            TimeFrame.WEEKLY: 1,
            TimeFrame.MONTHLY: 1
        }
        return frequency_map.get(timeframe, 1)
    
    async def _parse_and_validate(
        self,
        symbol: str,
        raw_data: Dict[str, Any],
        timeframe: TimeFrame
    ) -> Dict[str, Any]:
        """Parse and validate price data."""
        result = {
            'records': [],
            'validation_errors': [],
            'validation_warnings': []
        }
        
        candles = raw_data.get('candles', [])
        
        for candle in candles:
            try:
                # Convert timestamp
                timestamp = datetime.fromtimestamp(
                    candle['datetime'] / 1000,
                    tz=timezone.utc
                )
                
                # Create record
                record = {
                    'symbol': symbol,
                    'timestamp': timestamp,
                    'open': Decimal(str(candle['open'])),
                    'high': Decimal(str(candle['high'])),
                    'low': Decimal(str(candle['low'])),
                    'close': Decimal(str(candle['close'])),
                    'volume': int(candle['volume']),
                    'vwap': Decimal(str(candle.get('vwap', 0))) if 'vwap' in candle else None
                }
                
                # Validate record
                validation_result = await self.validation_pipeline.validate(record)
                
                if validation_result.is_valid:
                    result['records'].append(validation_result.cleaned_data or record)
                else:
                    result['validation_errors'].extend(validation_result.errors)
                
                result['validation_warnings'].extend(validation_result.warnings)
                
            except Exception as e:
                error_msg = f"Error parsing candle for {symbol}: {e}"
                logger.error(error_msg)
                result['validation_errors'].append(error_msg)
        
        return result
    
    async def _save_to_database(self, records: List[Dict[str, Any]]):
        """Save records to database with batch optimization."""
        if not records:
            return
        
        async with db_service.get_async_session() as session:
            try:
                # Process in batches
                for i in range(0, len(records), self._db_batch_size):
                    batch = records[i:i + self._db_batch_size]
                    
                    stmt = pg_insert(PriceData).values(batch)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['symbol', 'timestamp'],
                        set_={
                            'open': stmt.excluded.open,
                            'high': stmt.excluded.high,
                            'low': stmt.excluded.low,
                            'close': stmt.excluded.close,
                            'volume': stmt.excluded.volume,
                            'vwap': stmt.excluded.vwap,
                            'updated_at': datetime.now(timezone.utc)
                        }
                    )
                    
                    await session.execute(stmt)
                
                await session.commit()
                
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Database error saving records: {e}")
                raise
    
    async def _fill_data_gaps(
        self,
        symbol: str,
        timeframe: TimeFrame,
        max_gap_minutes: int = 60
    ) -> int:
        """Fill gaps in data."""
        gaps_filled = 0
        
        async with db_service.get_async_session() as session:
            # Find gaps using window function
            gap_query = text("""
                WITH time_diffs AS (
                    SELECT 
                        timestamp,
                        LAG(timestamp) OVER (ORDER BY timestamp) as prev_timestamp,
                        EXTRACT(EPOCH FROM (timestamp - LAG(timestamp) OVER (ORDER BY timestamp))) / 60 as gap_minutes
                    FROM price_data
                    WHERE symbol = :symbol
                    ORDER BY timestamp
                )
                SELECT 
                    prev_timestamp as gap_start,
                    timestamp as gap_end,
                    gap_minutes
                FROM time_diffs
                WHERE gap_minutes > :max_gap
                LIMIT 100
            """)
            
            result = await session.execute(
                gap_query,
                {"symbol": symbol, "max_gap": max_gap_minutes}
            )
            
            gaps = result.fetchall()
            
            for gap_start, gap_end, gap_minutes in gaps:
                if gap_start and gap_end:
                    # Fetch data for gap
                    gap_data = await self._fetch_with_retry(
                        symbol,
                        timeframe,
                        gap_start + timedelta(seconds=1),
                        gap_end - timedelta(seconds=1)
                    )
                    
                    if gap_data:
                        parsed = await self._parse_and_validate(symbol, gap_data, timeframe)
                        if parsed['records']:
                            await self._save_to_database(parsed['records'])
                            gaps_filled += len(parsed['records'])
        
        return gaps_filled
    
    async def detect_missing_data(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_date: datetime,
        end_date: datetime,
        market_hours_only: bool = True
    ) -> List[Tuple[datetime, datetime]]:
        """Detect missing data periods."""
        missing_periods = []
        
        async with db_service.get_async_session() as session:
            # Get all timestamps
            result = await session.execute(
                select(PriceData.timestamp).where(
                    and_(
                        PriceData.symbol == symbol,
                        PriceData.timestamp >= start_date,
                        PriceData.timestamp <= end_date
                    )
                ).order_by(PriceData.timestamp)
            )
            
            timestamps = [row[0] for row in result]
            
            if not timestamps:
                # No data at all
                return [(start_date, end_date)]
            
            # Expected interval based on timeframe
            expected_interval = self._get_expected_interval(timeframe)
            
            # Check for gaps
            for i in range(1, len(timestamps)):
                gap = timestamps[i] - timestamps[i-1]
                
                if gap > expected_interval:
                    # Consider market hours if requested
                    if market_hours_only:
                        if self._is_market_gap(timestamps[i-1], timestamps[i]):
                            continue
                    
                    missing_periods.append((timestamps[i-1], timestamps[i]))
        
        return missing_periods
    
    def _get_expected_interval(self, timeframe: TimeFrame) -> timedelta:
        """Get expected interval between data points."""
        intervals = {
            TimeFrame.MINUTE_1: timedelta(minutes=1),
            TimeFrame.MINUTE_5: timedelta(minutes=5),
            TimeFrame.MINUTE_10: timedelta(minutes=10),
            TimeFrame.MINUTE_15: timedelta(minutes=15),
            TimeFrame.MINUTE_30: timedelta(minutes=30),
            TimeFrame.DAILY: timedelta(days=1),
            TimeFrame.WEEKLY: timedelta(days=7),
            TimeFrame.MONTHLY: timedelta(days=30)  # Approximate
        }
        return intervals.get(timeframe, timedelta(days=1))
    
    def _is_market_gap(self, start: datetime, end: datetime) -> bool:
        """Check if gap is due to market closure."""
        # Simple check for weekends
        current = start
        while current < end:
            if current.weekday() in [5, 6]:  # Saturday, Sunday
                return True
            current += timedelta(days=1)
        
        # TODO: Add holiday checking
        return False
    
    async def get_data_statistics(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get statistics about stored data."""
        async with db_service.get_async_session() as session:
            # Build base query
            query = select(
                func.count(PriceData.id).label('count'),
                func.min(PriceData.timestamp).label('min_date'),
                func.max(PriceData.timestamp).label('max_date'),
                func.avg(PriceData.volume).label('avg_volume'),
                func.min(PriceData.low).label('min_price'),
                func.max(PriceData.high).label('max_price')
            ).where(PriceData.symbol == symbol)
            
            # Add date filters if provided
            if start_date:
                query = query.where(PriceData.timestamp >= start_date)
            if end_date:
                query = query.where(PriceData.timestamp <= end_date)
            
            result = await session.execute(query)
            row = result.first()
            
            if row:
                return {
                    'symbol': symbol,
                    'record_count': row.count or 0,
                    'date_range': {
                        'start': row.min_date,
                        'end': row.max_date
                    },
                    'price_range': {
                        'min': float(row.min_price) if row.min_price else None,
                        'max': float(row.max_price) if row.max_price else None
                    },
                    'average_volume': float(row.avg_volume) if row.avg_volume else None
                }
            
            return {
                'symbol': symbol,
                'record_count': 0,
                'date_range': {'start': None, 'end': None},
                'price_range': {'min': None, 'max': None},
                'average_volume': None
            }
    
    async def shutdown(self):
        """Clean up resources."""
        logger.info("Enhanced historical data fetcher shutdown complete")


# Progress callback implementations
class LoggingProgressCallback:
    """Simple logging progress callback."""
    
    def __init__(self, log_interval: int = 10):
        self.log_interval = log_interval
        self.last_logged_percentage = 0
    
    async def __call__(self, progress: FetchProgress, message: str):
        """Log progress at intervals."""
        current_percentage = int(progress.progress_percentage)
        
        if current_percentage >= self.last_logged_percentage + self.log_interval:
            logger.info(
                f"Progress: {current_percentage}% "
                f"({progress.completed_symbols}/{progress.total_symbols} symbols) - "
                f"{message}"
            )
            self.last_logged_percentage = current_percentage


class DetailedProgressCallback:
    """Detailed progress callback with ETA."""
    
    async def __call__(self, progress: FetchProgress, message: str):
        """Log detailed progress with ETA."""
        if progress.completed_symbols > 0:
            eta = progress.estimated_time_remaining
            eta_str = f"{eta/60:.1f} minutes" if eta > 60 else f"{eta:.0f} seconds"
            
            logger.info(
                f"[{progress.progress_percentage:.1f}%] "
                f"{progress.completed_symbols}/{progress.total_symbols} symbols | "
                f"Records: {progress.total_records:,} | "
                f"Rate: {progress.completed_symbols/progress.elapsed_time:.1f} symbols/sec | "
                f"ETA: {eta_str} | "
                f"{message}"
            )