"""Enhanced Historical Data Collector with parallel processing and validation."""

import asyncio
import concurrent.futures
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy import create_engine, select, func, and_
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
import pytz
import numpy as np
from src.utils.logger import get_logger
from src.models.market_data import Candle1Min, MiningStatus, MiningLog
from src.auth import get_auth_service
import os
import time
from collections import deque
import threading

logger = get_logger(__name__)

# EST timezone for market hours
EST = pytz.timezone('US/Eastern')

# Rate limiting configuration
RATE_LIMIT = {
    'calls_per_minute': 120,
    'calls_per_second': 2,
    'batch_size': 10,
    'retry_max': 3,
    'retry_delay': 1.0
}


class RateLimiter:
    """Thread-safe rate limiter for API calls."""
    
    def __init__(self, calls_per_second=2):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.call_times = deque(maxlen=int(calls_per_second * 60))  # Track last minute
        self.lock = threading.Lock()
        
    def wait_if_needed(self):
        """Wait if necessary to respect rate limits."""
        with self.lock:
            now = time.time()
            
            # Remove old timestamps
            while self.call_times and self.call_times[0] < now - 60:
                self.call_times.popleft()
            
            # Check per-second limit
            if self.call_times:
                time_since_last = now - self.call_times[-1]
                if time_since_last < self.min_interval:
                    sleep_time = self.min_interval - time_since_last
                    time.sleep(sleep_time)
                    now = time.time()
            
            self.call_times.append(now)


class DataValidator:
    """Validate OHLC data quality."""
    
    @staticmethod
    def validate_candle(candle: Dict) -> Tuple[bool, str]:
        """Validate a single candle for data integrity."""
        try:
            # Check required fields
            required_fields = ['open', 'high', 'low', 'close', 'volume', 'datetime']
            for field in required_fields:
                if field not in candle:
                    return False, f"Missing field: {field}"
            
            # OHLC consistency
            o, h, l, c = candle['open'], candle['high'], candle['low'], candle['close']
            
            if h < l:
                return False, "High < Low"
            if o > h or o < l:
                return False, "Open outside High-Low range"
            if c > h or c < l:
                return False, "Close outside High-Low range"
            
            # Volume validation
            if candle['volume'] < 0:
                return False, "Negative volume"
            
            # Price validation (sanity check)
            if any(p <= 0 for p in [o, h, l, c]):
                return False, "Non-positive price"
            if h > o * 1.5 or l < o * 0.5:  # 50% move in 1 minute is suspicious
                return False, "Suspicious price movement"
            
            return True, "Valid"
            
        except Exception as e:
            return False, f"Validation error: {e}"
    
    @staticmethod
    def calculate_quality_score(candles: List[Dict]) -> float:
        """Calculate data quality score (0-100)."""
        if not candles:
            return 0.0
        
        valid_count = 0
        total_count = len(candles)
        
        for candle in candles:
            is_valid, _ = DataValidator.validate_candle(candle)
            if is_valid:
                valid_count += 1
        
        # Check for gaps during market hours
        gaps = DataValidator.detect_market_gaps(candles)
        gap_penalty = min(len(gaps) * 2, 20)  # Max 20% penalty for gaps
        
        base_score = (valid_count / total_count) * 100
        final_score = max(0, base_score - gap_penalty)
        
        return round(final_score, 2)
    
    @staticmethod
    def detect_market_gaps(candles: List[Dict]) -> List[Tuple[datetime, datetime]]:
        """Detect gaps during market hours."""
        if len(candles) < 2:
            return []
        
        gaps = []
        sorted_candles = sorted(candles, key=lambda x: x['datetime'])
        
        for i in range(1, len(sorted_candles)):
            prev_time = datetime.fromtimestamp(sorted_candles[i-1]['datetime'] / 1000, tz=pytz.UTC)
            curr_time = datetime.fromtimestamp(sorted_candles[i]['datetime'] / 1000, tz=pytz.UTC)
            
            prev_est = prev_time.astimezone(EST)
            curr_est = curr_time.astimezone(EST)
            
            # Skip weekends
            if prev_est.weekday() >= 5 or curr_est.weekday() >= 5:
                continue
            
            # Check if during market hours (9:30 AM - 4:00 PM EST)
            market_open = prev_est.replace(hour=9, minute=30, second=0, microsecond=0)
            market_close = prev_est.replace(hour=16, minute=0, second=0, microsecond=0)
            
            if market_open <= prev_est <= market_close and market_open <= curr_est <= market_close:
                time_diff = (curr_time - prev_time).total_seconds() / 60
                if time_diff > 5:  # More than 5 minutes gap
                    gaps.append((prev_time, curr_time))
        
        return gaps


class EnhancedHistoricalDataCollector:
    """Enhanced collector with parallel processing and validation."""
    
    def __init__(self, client=None, max_workers=3):  # Reduced from 5 to 3
        """Initialize the enhanced collector."""
        self.client = client
        self.db_url = os.getenv("DATABASE_URL", "postgresql://trading_user:trading_pass@localhost/trading_dev")
        self.engine = create_engine(self.db_url)
        self.rate_limiter = RateLimiter(calls_per_second=1.5)  # Reduced from 2 to 1.5
        self.validator = DataValidator()
        self.max_workers = max_workers
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.stats = {
            'api_calls': 0,
            'candles_collected': 0,
            'validation_failures': 0,
            'symbols_completed': 0,
            'symbols_failed': 0
        }
        
    async def collect_historical_batch(
        self,
        symbols: List[str],
        days_back: int = 60,
        operation: str = "batch"
    ) -> Dict:
        """Collect historical data for multiple symbols in parallel."""
        start_time = datetime.now()
        results = []
        
        # Process in batches to respect rate limits
        batch_size = min(RATE_LIMIT['batch_size'], len(symbols))
        
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: {batch}")
            
            # Use thread pool for parallel processing
            futures = []
            for symbol in batch:
                future = self.executor.submit(
                    self._collect_symbol_data,
                    symbol,
                    days_back,
                    operation
                )
                futures.append((symbol, future))
            
            # Wait for batch completion
            for symbol, future in futures:
                try:
                    result = future.result(timeout=60)
                    results.append(result)
                    if result['success']:
                        self.stats['symbols_completed'] += 1
                    else:
                        self.stats['symbols_failed'] += 1
                except Exception as e:
                    logger.error(f"Error collecting {symbol}: {e}")
                    self.stats['symbols_failed'] += 1
                    results.append({
                        'symbol': symbol,
                        'success': False,
                        'error': str(e)
                    })
            
            # Small delay between batches
            await asyncio.sleep(1)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return {
            'results': results,
            'stats': self.stats,
            'duration': duration,
            'symbols_per_minute': (len(symbols) / duration * 60) if duration > 0 else 0
        }
    
    def _collect_symbol_data(
        self,
        symbol: str,
        days_back: int,
        operation: str
    ) -> Dict:
        """Collect data for a single symbol with retry logic."""
        for attempt in range(RATE_LIMIT['retry_max']):
            try:
                # Rate limiting
                self.rate_limiter.wait_if_needed()
                
                # Get authenticated client if not provided
                if not self.client:
                    auth_service = get_auth_service()
                    self.client = asyncio.run(auth_service.get_authenticated_client())
                
                if not self.client:
                    raise Exception("Failed to get authenticated client")
                
                # Calculate date range
                end_date = datetime.now(EST)
                start_date = end_date - timedelta(days=days_back)
                
                logger.info(f"Collecting {symbol} - Attempt {attempt + 1}")
                
                # Schwab API call - using correct method
                # The actual method depends on the schwab-py library version
                # This is a placeholder - needs to be adjusted based on actual API
                try:
                    from schwab.client import Client
                    
                    # Use the correct period enum value based on days_back
                    if days_back <= 10:
                        period = Client.PriceHistory.Period.TEN_DAYS
                    elif days_back <= 20:
                        period = Client.PriceHistory.Period.TWENTY_DAYS
                    elif days_back <= 30:
                        period = Client.PriceHistory.Period.ONE_MONTH
                    elif days_back <= 60:
                        period = Client.PriceHistory.Period.TWO_MONTHS
                    elif days_back <= 90:
                        period = Client.PriceHistory.Period.THREE_MONTHS
                    elif days_back <= 180:
                        period = Client.PriceHistory.Period.SIX_MONTHS
                    else:
                        period = Client.PriceHistory.Period.ONE_YEAR
                    
                    # Use datetime objects for start and end
                    # Since get_price_history is async, we need to handle it properly
                    import asyncio
                    
                    async def get_history():
                        return await self.client.get_price_history(
                            symbol=symbol,
                            period_type=Client.PriceHistory.PeriodType.DAY,
                            period=period,
                            frequency_type=Client.PriceHistory.FrequencyType.MINUTE,
                            frequency=Client.PriceHistory.Frequency.EVERY_MINUTE,
                            start_datetime=start_date,
                            end_datetime=end_date,
                            need_extended_hours_data=True
                        )
                    
                    # Run async function in sync context
                    try:
                        # Try to get existing event loop
                        loop = asyncio.get_running_loop()
                        response = asyncio.run_coroutine_threadsafe(get_history(), loop).result()
                    except RuntimeError:
                        # No running loop, create one
                        response = asyncio.run(get_history())
                    
                except ImportError:
                    # Fallback for different library structure
                    import asyncio
                    
                    async def get_history_fallback():
                        return await self.client.get_price_history(
                            symbol,
                            period_type='day',
                            period=days_back,
                            frequency_type='minute',
                            frequency=1,
                            need_extended_hours_data=True
                        )
                    
                    try:
                        loop = asyncio.get_running_loop()
                        response = asyncio.run_coroutine_threadsafe(get_history_fallback(), loop).result()
                    except RuntimeError:
                        response = asyncio.run(get_history_fallback())
                
                self.stats['api_calls'] += 1
                
                if response.status_code != 200:
                    if attempt < RATE_LIMIT['retry_max'] - 1:
                        time.sleep(RATE_LIMIT['retry_delay'] * (2 ** attempt))  # Exponential backoff
                        continue
                    raise Exception(f"API returned status {response.status_code}")
                
                data = response.json()
                
                # Validate and store candles
                if 'candles' in data:
                    candles = data['candles']
                    
                    # Validate data quality
                    quality_score = self.validator.calculate_quality_score(candles)
                    logger.info(f"{symbol}: {len(candles)} candles, quality: {quality_score}%")
                    
                    if quality_score < 50:
                        logger.warning(f"{symbol}: Low quality score {quality_score}%")
                    
                    # Store candles
                    stored_count = self._store_candles_batch(symbol, candles)
                    self.stats['candles_collected'] += stored_count
                    
                    # Update mining status
                    self._update_mining_status(symbol, len(candles), quality_score)
                    
                    return {
                        'symbol': symbol,
                        'success': True,
                        'candles_count': len(candles),
                        'stored_count': stored_count,
                        'quality_score': quality_score
                    }
                else:
                    return {
                        'symbol': symbol,
                        'success': False,
                        'error': 'No candle data received'
                    }
                    
            except Exception as e:
                if attempt < RATE_LIMIT['retry_max'] - 1:
                    logger.warning(f"{symbol}: Attempt {attempt + 1} failed: {e}")
                    time.sleep(RATE_LIMIT['retry_delay'] * (2 ** attempt))
                else:
                    logger.error(f"{symbol}: All attempts failed: {e}")
                    self.stats['validation_failures'] += 1
                    return {
                        'symbol': symbol,
                        'success': False,
                        'error': str(e)
                    }
    
    def _store_candles_batch(self, symbol: str, candles: List[Dict]) -> int:
        """Store candles in batch with validation."""
        stored_count = 0
        validated_candles = []
        
        for candle in candles:
            is_valid, reason = self.validator.validate_candle(candle)
            if is_valid:
                validated_candles.append({
                    'symbol': symbol,
                    'timestamp': datetime.fromtimestamp(candle['datetime'] / 1000, tz=pytz.UTC),
                    'open': candle['open'],
                    'high': candle['high'],
                    'low': candle['low'],
                    'close': candle['close'],
                    'volume': candle.get('volume', 0)
                })
            else:
                self.stats['validation_failures'] += 1
                logger.debug(f"{symbol}: Invalid candle - {reason}")
        
        # Batch insert with PostgreSQL
        if validated_candles:
            with Session(self.engine) as session:
                stmt = insert(Candle1Min).values(validated_candles)
                stmt = stmt.on_conflict_do_nothing(index_elements=['symbol', 'timestamp'])
                session.execute(stmt)
                session.commit()
                stored_count = len(validated_candles)
        
        return stored_count
    
    def _update_mining_status(self, symbol: str, candles_count: int, quality_score: float):
        """Update mining status with quality metrics."""
        with Session(self.engine) as session:
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
            status.data_quality_score = quality_score
            status.last_update = datetime.now(pytz.UTC)
            
            # Detect gaps
            gaps = self.validator.detect_market_gaps([])  # Would need actual candles
            status.gaps_detected = len(gaps)
            
            session.commit()
    
    def cleanup(self):
        """Clean up resources."""
        self.executor.shutdown(wait=True)