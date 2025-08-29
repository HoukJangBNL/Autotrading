"""Historical data collector for 1-minute candle data."""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy import create_engine, select, func, and_
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
import pytz
from src.utils.logger import get_logger
from src.models.market_data import Candle1Min, MiningStatus, MiningLog
from src.auth import get_auth_service
import os

logger = get_logger(__name__)

# EST timezone for market hours
EST = pytz.timezone('US/Eastern')


class HistoricalDataCollector:
    """Collects historical 1-minute candle data from Schwab API."""
    
    def __init__(self, client=None):
        """Initialize the collector."""
        self.client = client
        self.db_url = os.getenv("DATABASE_URL", "postgresql://trading_user:trading_pass@localhost/trading_dev")
        self.engine = create_engine(self.db_url)
        self.api_calls = 0
        self.rate_limit_delay = 0.5  # 2 calls per second max
        
    async def collect_historical_data(
        self, 
        symbol: str, 
        days_back: int = 60,  # 2 months default
        operation: str = "initial"
    ) -> Dict:
        """
        Collect historical 1-minute candle data for a symbol.
        
        Args:
            symbol: Stock symbol
            days_back: Number of days to collect (default 60 = 2 months)
            operation: Type of operation (initial, update, gap_fill)
            
        Returns:
            Collection statistics
        """
        start_time = datetime.now()
        candles_added = 0
        success = False
        error_message = None
        
        try:
            # Get authenticated client if not provided
            if not self.client:
                auth_service = get_auth_service()
                self.client = await auth_service.get_authenticated_client()
                
            if not self.client:
                raise Exception("Failed to get authenticated client")
            
            # Calculate date range
            end_date = datetime.now(EST)
            start_date = end_date - timedelta(days=days_back)
            
            logger.info(f"Collecting {days_back} days of data for {symbol}")
            
            # Schwab API call for price history
            # Note: Schwab API has specific requirements for date format and frequency
            try:
                response = self.client.get_price_history_every_minute(
                    symbol=symbol,
                    start_datetime=start_date,
                    end_datetime=end_date,
                    need_extended_hours_data=True,
                    need_previous_close=False
                )
                self.api_calls += 1
                
                # Add rate limiting delay
                await asyncio.sleep(self.rate_limit_delay)
                
            except Exception as api_error:
                logger.error(f"API error for {symbol}: {api_error}")
                raise api_error
                
            if response.status_code != 200:
                raise Exception(f"API returned status {response.status_code}: {response.text}")
            
            data = response.json()
            
            # Parse and store candles
            if 'candles' in data:
                candles = data['candles']
                logger.info(f"Received {len(candles)} candles for {symbol}")
                
                # Batch insert candles
                candles_added = await self._store_candles(symbol, candles)
                success = True
                
                # Update mining status
                await self._update_mining_status(symbol, len(candles))
                
            else:
                logger.warning(f"No candle data received for {symbol}")
                
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error collecting data for {symbol}: {e}")
            
        finally:
            # Log the operation
            await self._log_operation(
                symbol=symbol,
                operation=operation,
                start_time=start_time,
                end_time=datetime.now(),
                candles_added=candles_added,
                success=success,
                error_message=error_message,
                api_calls=self.api_calls
            )
            
        return {
            "symbol": symbol,
            "candles_added": candles_added,
            "success": success,
            "error": error_message,
            "api_calls": self.api_calls,
            "duration": (datetime.now() - start_time).total_seconds()
        }
    
    async def _store_candles(self, symbol: str, candles: List[Dict]) -> int:
        """Store candles in database with duplicate handling."""
        stored_count = 0
        
        with Session(self.engine) as session:
            for candle in candles:
                try:
                    # Convert timestamp (milliseconds) to datetime
                    timestamp = datetime.fromtimestamp(
                        candle['datetime'] / 1000, 
                        tz=pytz.UTC
                    )
                    
                    # Prepare candle data
                    candle_data = {
                        'symbol': symbol,
                        'timestamp': timestamp,
                        'open': candle['open'],
                        'high': candle['high'],
                        'low': candle['low'],
                        'close': candle['close'],
                        'volume': candle.get('volume', 0)
                    }
                    
                    # Use PostgreSQL upsert to handle duplicates
                    stmt = insert(Candle1Min).values(**candle_data)
                    stmt = stmt.on_conflict_do_nothing(
                        index_elements=['symbol', 'timestamp']
                    )
                    
                    session.execute(stmt)
                    stored_count += 1
                    
                except Exception as e:
                    logger.debug(f"Error storing candle: {e}")
                    continue
                    
            session.commit()
            
        logger.info(f"Stored {stored_count} candles for {symbol}")
        return stored_count
    
    async def detect_gaps(self, symbol: str) -> List[Tuple[datetime, datetime]]:
        """
        Detect gaps in historical data for a symbol.
        
        Returns:
            List of gap periods (start, end)
        """
        gaps = []
        
        with Session(self.engine) as session:
            # Get all timestamps for symbol ordered
            result = session.execute(
                select(Candle1Min.timestamp)
                .where(Candle1Min.symbol == symbol)
                .order_by(Candle1Min.timestamp)
            )
            timestamps = [row[0] for row in result]
            
            if len(timestamps) < 2:
                return gaps
                
            # Check for gaps larger than 1 minute during market hours
            for i in range(1, len(timestamps)):
                prev_time = timestamps[i-1]
                curr_time = timestamps[i]
                time_diff = (curr_time - prev_time).total_seconds() / 60
                
                # During market hours, expect 1-minute intervals
                # Allow up to 5 minutes for minor gaps
                if time_diff > 5:
                    # Check if it's during market hours (9:30 AM - 4:00 PM EST)
                    prev_est = prev_time.astimezone(EST)
                    curr_est = curr_time.astimezone(EST)
                    
                    # Skip weekends
                    if prev_est.weekday() >= 5 or curr_est.weekday() >= 5:
                        continue
                        
                    # Check market hours
                    market_open = prev_est.replace(hour=9, minute=30, second=0, microsecond=0)
                    market_close = prev_est.replace(hour=16, minute=0, second=0, microsecond=0)
                    
                    if market_open <= prev_est <= market_close:
                        gaps.append((prev_time, curr_time))
                        
        logger.info(f"Found {len(gaps)} gaps for {symbol}")
        return gaps
    
    async def fill_gaps(self, symbol: str) -> int:
        """Fill detected gaps in data."""
        gaps = await self.detect_gaps(symbol)
        total_filled = 0
        
        for gap_start, gap_end in gaps:
            try:
                # Calculate days to fetch
                days = (gap_end - gap_start).days + 1
                
                # Collect data for gap period
                result = await self.collect_historical_data(
                    symbol=symbol,
                    days_back=days,
                    operation="gap_fill"
                )
                
                if result['success']:
                    total_filled += result['candles_added']
                    
            except Exception as e:
                logger.error(f"Error filling gap for {symbol}: {e}")
                continue
                
        return total_filled
    
    async def _update_mining_status(self, symbol: str, candles_count: int):
        """Update mining status for a symbol."""
        with Session(self.engine) as session:
            # Get or create status record
            status = session.execute(
                select(MiningStatus).where(MiningStatus.symbol == symbol)
            ).scalar_one_or_none()
            
            if not status:
                status = MiningStatus(symbol=symbol, phase=1)
                session.add(status)
            
            # Update statistics
            result = session.execute(
                select(
                    func.min(Candle1Min.timestamp),
                    func.max(Candle1Min.timestamp),
                    func.count(Candle1Min.id)
                ).where(Candle1Min.symbol == symbol)
            ).one()
            
            status.first_date = result[0]
            status.last_date = result[1]
            status.total_candles = result[2] or 0
            status.last_update = datetime.now(pytz.UTC)
            
            # Calculate data quality score (simple version)
            if status.total_candles > 0:
                expected_candles = candles_count  # Simplified
                status.data_quality_score = min(100, (status.total_candles / expected_candles) * 100)
            
            session.commit()
    
    async def _log_operation(self, **kwargs):
        """Log mining operation to database."""
        with Session(self.engine) as session:
            log = MiningLog(**kwargs)
            session.add(log)
            session.commit()
    
    async def get_collection_status(self) -> Dict:
        """Get overall collection status."""
        with Session(self.engine) as session:
            # Get mining status for all symbols
            statuses = session.execute(
                select(MiningStatus).where(MiningStatus.is_active == True)
            ).scalars().all()
            
            total_symbols = len(statuses)
            total_candles = sum(s.total_candles for s in statuses)
            avg_quality = sum(s.data_quality_score for s in statuses) / total_symbols if total_symbols > 0 else 0
            
            return {
                "total_symbols": total_symbols,
                "total_candles": total_candles,
                "average_quality": avg_quality,
                "symbols": [
                    {
                        "symbol": s.symbol,
                        "candles": s.total_candles,
                        "quality": s.data_quality_score,
                        "last_update": s.last_update.isoformat() if s.last_update else None
                    }
                    for s in statuses
                ]
            }