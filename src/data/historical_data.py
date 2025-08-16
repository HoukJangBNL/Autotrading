"""Historical data fetcher for Schwab API integration."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..auth import get_auth_service
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


class HistoricalDataFetcher:
    """Fetches and stores historical price data from Schwab API."""
    
    def __init__(self):
        self.auth_service = get_auth_service()
        self.client = None
        self._rate_limit_delay = 0.5  # Initial delay between requests
        self._max_rate_limit_delay = 60  # Maximum delay
        self._batch_size = settings.system.batch_insert_size
        self._max_retries = 3
        
    async def initialize(self):
        """Initialize the fetcher with authenticated client."""
        await self.auth_service.initialize()
        self.client = self.auth_service.get_client()
        logger.info("Historical data fetcher initialized")
        
    async def fetch_historical_data(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        save_to_db: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical data for a symbol.
        
        Args:
            symbol: Stock symbol to fetch
            timeframe: Timeframe for the data
            start_date: Start date for historical data
            end_date: End date for historical data
            save_to_db: Whether to save data to database
            
        Returns:
            List of price data dictionaries
        """
        if not self.client:
            raise RuntimeError("Fetcher not initialized. Call initialize() first.")
            
        # Default date range if not specified
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            # Default to 1 year of data for daily, 1 month for intraday
            if timeframe in [TimeFrame.DAILY, TimeFrame.WEEKLY, TimeFrame.MONTHLY]:
                start_date = end_date - timedelta(days=365)
            else:
                start_date = end_date - timedelta(days=30)
                
        logger.info(
            f"Fetching {timeframe.value} data for {symbol} "
            f"from {start_date.date()} to {end_date.date()}"
        )
        
        # Make the API call with retries
        price_data = await self._fetch_with_retry(
            symbol, timeframe, start_date, end_date
        )
        
        if not price_data:
            logger.warning(f"No data returned for {symbol}")
            return []
            
        # Parse and validate the data
        parsed_data = self._parse_price_data(symbol, price_data, timeframe)
        
        if save_to_db and parsed_data:
            await self._save_to_database(parsed_data)
            
        return parsed_data
        
    async def _fetch_with_retry(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[Dict[str, Any]]:
        """Fetch data with retry logic for rate limiting and errors."""
        retry_count = 0
        current_delay = self._rate_limit_delay
        
        while retry_count < self._max_retries:
            try:
                # Apply rate limit delay
                await asyncio.sleep(current_delay)
                
                # Make the appropriate API call based on timeframe
                response = await self._make_api_call(
                    symbol, timeframe, start_date, end_date
                )
                
                response.raise_for_status()
                
                # Reset delay on success
                self._rate_limit_delay = max(0.5, self._rate_limit_delay * 0.9)
                
                return response.json()
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limit
                    retry_count += 1
                    self._rate_limit_delay = min(
                        self._rate_limit_delay * 2,
                        self._max_rate_limit_delay
                    )
                    logger.warning(
                        f"Rate limit hit. Retry {retry_count}/{self._max_retries} "
                        f"with delay {self._rate_limit_delay}s"
                    )
                    current_delay = self._rate_limit_delay
                    continue
                else:
                    logger.error(f"HTTP error fetching data: {e}")
                    raise
                    
            except Exception as e:
                retry_count += 1
                logger.error(
                    f"Error fetching data: {e}. "
                    f"Retry {retry_count}/{self._max_retries}"
                )
                if retry_count >= self._max_retries:
                    raise
                await asyncio.sleep(current_delay)
                
        return None
        
    async def _make_api_call(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_date: datetime,
        end_date: datetime
    ) -> httpx.Response:
        """Make the appropriate API call based on timeframe."""
        # schwab-py expects datetime objects, not strings
        # Pass the datetime objects directly
        
        if timeframe == TimeFrame.MINUTE_1:
            return await self.client.get_price_history_every_minute(
                symbol, start_datetime=start_date, end_datetime=end_date
            )
        elif timeframe == TimeFrame.MINUTE_5:
            return await self.client.get_price_history_every_five_minutes(
                symbol, start_datetime=start_date, end_datetime=end_date
            )
        elif timeframe == TimeFrame.MINUTE_10:
            return await self.client.get_price_history_every_ten_minutes(
                symbol, start_datetime=start_date, end_datetime=end_date
            )
        elif timeframe == TimeFrame.MINUTE_15:
            return await self.client.get_price_history_every_fifteen_minutes(
                symbol, start_datetime=start_date, end_datetime=end_date
            )
        elif timeframe == TimeFrame.MINUTE_30:
            return await self.client.get_price_history_every_thirty_minutes(
                symbol, start_datetime=start_date, end_datetime=end_date
            )
        elif timeframe == TimeFrame.DAILY:
            return await self.client.get_price_history_every_day(
                symbol, start_datetime=start_date, end_datetime=end_date
            )
        elif timeframe == TimeFrame.WEEKLY:
            return await self.client.get_price_history_every_week(
                symbol, start_datetime=start_date, end_datetime=end_date
            )
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
            
    def _parse_price_data(
        self,
        symbol: str,
        raw_data: Dict[str, Any],
        timeframe: TimeFrame
    ) -> List[Dict[str, Any]]:
        """Parse and validate price data from API response."""
        parsed_data = []
        
        # The API returns data in a 'candles' array
        candles = raw_data.get('candles', [])
        
        if not candles:
            logger.warning(f"No candles data found in response for {symbol}")
            return []
            
        for candle in candles:
            try:
                # Validate required fields
                if not all(key in candle for key in ['datetime', 'open', 'high', 'low', 'close', 'volume']):
                    logger.warning(f"Missing required fields in candle data: {candle}")
                    continue
                    
                # Convert timestamp to datetime
                timestamp = datetime.fromtimestamp(
                    candle['datetime'] / 1000,  # API returns milliseconds
                    tz=timezone.utc
                )
                
                # Validate OHLC relationships
                open_price = Decimal(str(candle['open']))
                high_price = Decimal(str(candle['high']))
                low_price = Decimal(str(candle['low']))
                close_price = Decimal(str(candle['close']))
                
                if not (low_price <= open_price <= high_price and
                        low_price <= close_price <= high_price):
                    logger.warning(
                        f"Invalid OHLC data for {symbol} at {timestamp}: "
                        f"O={open_price}, H={high_price}, L={low_price}, C={close_price}"
                    )
                    continue
                    
                parsed_data.append({
                    'symbol': symbol,
                    'timestamp': timestamp,
                    'open': open_price,
                    'high': high_price,
                    'low': low_price,
                    'close': close_price,
                    'volume': int(candle['volume']),
                    'vwap': Decimal(str(candle.get('vwap', 0))) if 'vwap' in candle else None
                })
                
            except (KeyError, ValueError, TypeError) as e:
                logger.error(f"Error parsing candle data: {e}. Data: {candle}")
                continue
                
        logger.info(f"Parsed {len(parsed_data)} candles for {symbol}")
        return parsed_data
        
    async def _save_to_database(self, price_data: List[Dict[str, Any]]):
        """Save price data to database with bulk insert optimization."""
        if not price_data:
            return
            
        async with db_service.get_async_session() as session:
            try:
                # Use PostgreSQL's ON CONFLICT DO UPDATE for upsert
                await self._bulk_upsert_postgresql(session, price_data)
                    
                await session.commit()
                logger.info(f"Saved {len(price_data)} price records to database")
                
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Database error saving price data: {e}")
                raise
                
    async def _bulk_upsert_postgresql(self, session, price_data: List[Dict[str, Any]]):
        """Bulk upsert for PostgreSQL with ON CONFLICT DO UPDATE."""
        # Process in batches
        for i in range(0, len(price_data), self._batch_size):
            batch = price_data[i:i + self._batch_size]
            
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
            
            
            if existing.scalar():
                # Update existing record
                await session.execute(
                    text("""
                        UPDATE price_data 
                        SET open = :open, high = :high, low = :low, 
                            close = :close, volume = :volume, vwap = :vwap,
                            updated_at = :updated_at
                        WHERE symbol = :symbol AND timestamp = :timestamp
                    """),
                    {**record, 'updated_at': datetime.now(timezone.utc)}
                )
            else:
                # Insert new record
                await session.execute(
                    text("""
                        INSERT INTO price_data 
                        (symbol, timestamp, open, high, low, close, volume, vwap, created_at)
                        VALUES 
                        (:symbol, :timestamp, :open, :high, :low, :close, :volume, :vwap, :created_at)
                    """),
                    {**record, 'created_at': datetime.now(timezone.utc)}
                )
                
    async def fetch_multiple_symbols(
        self,
        symbols: List[str],
        timeframe: TimeFrame,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_concurrent: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch historical data for multiple symbols concurrently.
        
        Args:
            symbols: List of stock symbols
            timeframe: Timeframe for the data
            start_date: Start date for historical data
            end_date: End date for historical data
            max_concurrent: Maximum concurrent requests
            
        Returns:
            Dictionary mapping symbols to their price data
        """
        results = {}
        
        # Create semaphore for rate limiting
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_with_semaphore(symbol: str):
            async with semaphore:
                try:
                    data = await self.fetch_historical_data(
                        symbol, timeframe, start_date, end_date
                    )
                    results[symbol] = data
                except Exception as e:
                    logger.error(f"Error fetching data for {symbol}: {e}")
                    results[symbol] = []
                    
        # Fetch all symbols concurrently
        tasks = [fetch_with_semaphore(symbol) for symbol in symbols]
        await asyncio.gather(*tasks)
        
        return results
        
    async def get_latest_timestamp(self, symbol: str) -> Optional[datetime]:
        """Get the latest timestamp for a symbol in the database."""
        async with db_service.get_async_session() as session:
            result = await session.execute(
                text(
                    "SELECT MAX(timestamp) FROM price_data WHERE symbol = :symbol"
                ),
                {"symbol": symbol}
            )
            
            latest = result.scalar()
            return latest if latest else None
            
    async def update_symbol_data(
        self,
        symbol: str,
        timeframe: TimeFrame = TimeFrame.MINUTE_1
    ) -> int:
        """
        Update symbol data from the latest timestamp to current time.
        
        Args:
            symbol: Stock symbol to update
            timeframe: Timeframe for the update
            
        Returns:
            Number of new records added
        """
        latest_timestamp = await self.get_latest_timestamp(symbol)
        
        if latest_timestamp:
            # Add a small buffer to avoid duplicates
            start_date = latest_timestamp + timedelta(seconds=1)
            logger.info(f"Updating {symbol} from {start_date}")
        else:
            # No existing data, fetch last month
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
            logger.info(f"No existing data for {symbol}, fetching from {start_date}")
            
        data = await self.fetch_historical_data(
            symbol, timeframe, start_date=start_date
        )
        
        return len(data)
        
    async def fill_data_gaps(
        self,
        symbol: str,
        timeframe: TimeFrame = TimeFrame.MINUTE_1,
        max_gap_minutes: int = 60
    ) -> int:
        """
        Find and fill gaps in historical data.
        
        Args:
            symbol: Stock symbol to check
            timeframe: Expected timeframe
            max_gap_minutes: Maximum expected gap in minutes
            
        Returns:
            Number of gaps filled
        """
        async with db_service.get_async_session() as session:
            # Find gaps in the data
            result = await session.execute(
                text("""
                    WITH time_diffs AS (
                        SELECT 
                            symbol,
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
                """),
                {"symbol": symbol, "max_gap": max_gap_minutes}
            )
            
            gaps = result.fetchall()
            
            if not gaps:
                logger.info(f"No gaps found for {symbol}")
                return 0
                
            total_filled = 0
            
            for gap_start, gap_end, gap_minutes in gaps:
                logger.info(
                    f"Found gap for {symbol}: {gap_start} to {gap_end} "
                    f"({gap_minutes:.1f} minutes)"
                )
                
                # Fetch data for the gap period
                data = await self.fetch_historical_data(
                    symbol,
                    timeframe,
                    start_date=gap_start + timedelta(seconds=1),
                    end_date=gap_end - timedelta(seconds=1)
                )
                
                total_filled += len(data)
                
            return total_filled
            
    async def shutdown(self):
        """Clean up resources."""
        # The client cleanup is handled by auth service
        logger.info("Historical data fetcher shutdown complete")


# Convenience function for getting fetcher instance
_fetcher_instance = None


def get_historical_fetcher() -> HistoricalDataFetcher:
    """Get or create historical data fetcher instance."""
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = HistoricalDataFetcher()
    return _fetcher_instance