"""Full Market Mining Orchestrator with 11,609 symbols support."""

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Any
from pathlib import Path
from sqlalchemy import create_engine, select, and_, or_, func
from sqlalchemy.orm import Session
import pytz
import aiofiles
from concurrent.futures import ThreadPoolExecutor
import time
from src.utils.logger import get_logger
from src.data.historical_data_collector_v2 import EnhancedHistoricalDataCollector
from src.models.market_data import MiningStatus, MiningLog, Candle1Min
import os
import redis.asyncio as redis

logger = get_logger(__name__)

CONFIG_PATH = Path(__file__).parent.parent.parent / "config"


class FailedSymbolsTracker:
    """Track and manage failed symbols to avoid repeated failures."""
    
    def __init__(self, file_path: Path = CONFIG_PATH / "failed_symbols.json"):
        self.file_path = file_path
        self.failed_symbols = self._load_failed_symbols()
        self.temp_failures = {}  # Temporary failures that can be retried
        
    def _load_failed_symbols(self) -> Dict[str, Dict]:
        """Load failed symbols from file."""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading failed symbols: {e}")
        return {}
    
    async def save_failed_symbols(self):
        """Save failed symbols to file."""
        try:
            async with aiofiles.open(self.file_path, 'w') as f:
                await f.write(json.dumps(self.failed_symbols, indent=2))
        except Exception as e:
            logger.error(f"Error saving failed symbols: {e}")
    
    def add_failure(self, symbol: str, error: str, permanent: bool = False):
        """Add a failed symbol."""
        if permanent or symbol in self.failed_symbols:
            # Permanent failure or already failed multiple times
            self.failed_symbols[symbol] = {
                "error": error,
                "timestamp": datetime.now().isoformat(),
                "permanent": permanent,
                "retry_count": self.failed_symbols.get(symbol, {}).get("retry_count", 0) + 1
            }
        else:
            # Temporary failure
            if symbol not in self.temp_failures:
                self.temp_failures[symbol] = {
                    "errors": [],
                    "retry_count": 0
                }
            self.temp_failures[symbol]["errors"].append(error)
            self.temp_failures[symbol]["retry_count"] += 1
            
            # Move to permanent after 3 retries
            if self.temp_failures[symbol]["retry_count"] >= 3:
                self.failed_symbols[symbol] = {
                    "error": "; ".join(self.temp_failures[symbol]["errors"]),
                    "timestamp": datetime.now().isoformat(),
                    "permanent": True,
                    "retry_count": self.temp_failures[symbol]["retry_count"]
                }
                del self.temp_failures[symbol]
    
    def is_permanently_failed(self, symbol: str) -> bool:
        """Check if symbol is permanently failed."""
        return symbol in self.failed_symbols and self.failed_symbols[symbol].get("permanent", False)
    
    def get_retryable_symbols(self, symbols: List[str]) -> List[str]:
        """Filter out permanently failed symbols."""
        return [s for s in symbols if not self.is_permanently_failed(s)]


class GapFiller:
    """Smart gap detection and filling for existing data."""
    
    def __init__(self, engine, collector):
        self.engine = engine
        self.collector = collector
        
    async def detect_gaps(self, symbol: str, days_back: int = 60) -> List[Dict]:
        """Detect gaps in existing data."""
        gaps = []
        end_date = datetime.now(pytz.timezone('US/Eastern'))
        start_date = end_date - timedelta(days=days_back)
        
        with Session(self.engine) as session:
            # Get existing data points
            result = session.execute(
                select(Candle1Min.timestamp)
                .where(
                    and_(
                        Candle1Min.symbol == symbol,
                        Candle1Min.timestamp >= start_date,
                        Candle1Min.timestamp <= end_date
                    )
                )
                .order_by(Candle1Min.timestamp)
            ).scalars().all()
            
            if not result:
                # No data at all
                gaps.append({
                    "start": start_date,
                    "end": end_date,
                    "type": "no_data",
                    "size_minutes": days_back * 390  # Trading minutes per day
                })
                return gaps
            
            # Check for gaps between data points
            timestamps = sorted(result)
            for i in range(1, len(timestamps)):
                prev_ts = timestamps[i-1]
                curr_ts = timestamps[i]
                
                # Calculate expected gap (considering market hours)
                expected_gap = self._calculate_expected_gap(prev_ts, curr_ts)
                actual_gap = (curr_ts - prev_ts).total_seconds() / 60
                
                if actual_gap > expected_gap + 1:  # Allow 1 minute tolerance
                    gaps.append({
                        "start": prev_ts,
                        "end": curr_ts,
                        "type": "missing_data",
                        "size_minutes": int(actual_gap - expected_gap)
                    })
            
            # Check for missing recent data
            last_ts = timestamps[-1]
            if (end_date - last_ts).days > 1:
                gaps.append({
                    "start": last_ts,
                    "end": end_date,
                    "type": "stale_data",
                    "size_minutes": (end_date - last_ts).days * 390
                })
        
        return gaps
    
    def _calculate_expected_gap(self, prev_ts: datetime, curr_ts: datetime) -> int:
        """Calculate expected gap between timestamps considering market hours."""
        # Simplified: assume 1 minute during market hours
        # Real implementation would check weekends, holidays, and market hours
        if prev_ts.date() == curr_ts.date():
            return 1  # Same day, expect 1 minute gap
        else:
            # Different days, account for overnight gap
            return 960  # 16 hours * 60 minutes
    
    async def fill_gaps(self, symbol: str, gaps: List[Dict]) -> Dict[str, Any]:
        """Fill detected gaps."""
        filled = 0
        errors = []
        
        for gap in gaps:
            try:
                # Fetch data for gap period
                result = await self.collector.collect_historical_data(
                    symbol,
                    start_date=gap["start"],
                    end_date=gap["end"],
                    interval="1min"
                )
                
                if result and result.get("success"):
                    filled += result.get("stored_count", 0)
                else:
                    errors.append(f"Failed to fill gap {gap['start']} - {gap['end']}")
                    
            except Exception as e:
                errors.append(f"Error filling gap: {e}")
        
        return {
            "symbol": symbol,
            "gaps_found": len(gaps),
            "candles_filled": filled,
            "errors": errors,
            "success": len(errors) == 0
        }


class FullMarketMiningOrchestrator:
    """Orchestrator for mining all 11,609 US market symbols."""
    
    def __init__(self, client=None):
        """Initialize the full market orchestrator."""
        self.collector = EnhancedHistoricalDataCollector(client, max_workers=10)
        self.db_url = os.getenv("DATABASE_URL", "postgresql://houkjang@localhost/autotrading")
        self.engine = create_engine(self.db_url)
        
        # Components
        self.failed_tracker = FailedSymbolsTracker()
        self.gap_filler = GapFiller(self.engine, self.collector)
        
        # Load symbol lists
        self.all_symbols = self._load_all_symbols()
        self.popular_symbols = self._load_popular_symbols()
        
        # Redis for progress tracking
        self.redis_client = None
        self._init_redis()
        
        # Control flags
        self.is_running = False
        self.pause_requested = False
        self.mode = "full"  # full, gaps_only, new_only
        
        # Progress tracking
        self.progress = {
            'total_symbols': len(self.all_symbols),
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'candles_collected': 0,
            'gaps_filled': 0,
            'start_time': None,
            'current_batch': 0,
            'total_batches': 0,
            'estimated_completion': None,
            'current_symbol': None,
            'rate_limit_delays': 0,
            'api_calls': 0
        }
        
        # Performance metrics
        self.performance = {
            'symbols_per_minute': 0,
            'candles_per_second': 0,
            'api_calls_per_minute': 0,
            'average_symbol_time': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    def _init_redis(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.Redis(
                host='localhost',
                port=6379,
                db=1,
                decode_responses=True
            )
            logger.info("Redis connected for mining progress tracking")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
    
    def _load_all_symbols(self) -> List[str]:
        """Load all US stock symbols."""
        file_path = CONFIG_PATH / "all_us_stocks_symbols.json"
        if file_path.exists():
            with open(file_path, 'r') as f:
                data = json.load(f)
                return data.get("symbols", [])
        return []
    
    def _load_popular_symbols(self) -> Set[str]:
        """Load popular symbols for prioritization."""
        file_path = CONFIG_PATH / "popular_stocks_symbols.json"
        if file_path.exists():
            with open(file_path, 'r') as f:
                data = json.load(f)
                return set(data.get("symbols", []))
        return set()
    
    async def start_mining(
        self,
        mode: str = "full",
        days_back: int = 60,
        batch_size: int = 50,
        concurrent_limit: int = 10
    ):
        """Start the mining process."""
        self.is_running = True
        self.mode = mode
        self.progress['start_time'] = datetime.now()
        
        try:
            # Filter symbols based on mode and failures
            symbols_to_process = self._prepare_symbol_list(mode)
            self.progress['total_symbols'] = len(symbols_to_process)
            self.progress['total_batches'] = (len(symbols_to_process) + batch_size - 1) // batch_size
            
            logger.info(f"Starting {mode} mining for {len(symbols_to_process)} symbols")
            
            # Process in batches
            for batch_num, i in enumerate(range(0, len(symbols_to_process), batch_size)):
                if not self.is_running:
                    break
                
                while self.pause_requested:
                    await asyncio.sleep(1)
                
                batch = symbols_to_process[i:i+batch_size]
                self.progress['current_batch'] = batch_num + 1
                
                # Check rate limits
                await self._check_rate_limits()
                
                # Process batch based on mode
                if mode == "gaps_only":
                    await self._process_gaps_batch(batch)
                else:
                    await self._process_full_batch(batch, days_back, concurrent_limit)
                
                # Update progress
                await self._update_progress()
                
                # Save failed symbols periodically
                if batch_num % 10 == 0:
                    await self.failed_tracker.save_failed_symbols()
            
            # Final save
            await self.failed_tracker.save_failed_symbols()
            
        except Exception as e:
            logger.error(f"Mining error: {e}")
        finally:
            self.is_running = False
            await self._generate_final_report()
    
    def _prepare_symbol_list(self, mode: str) -> List[str]:
        """Prepare symbol list based on mode and priorities."""
        # Start with all symbols
        symbols = self.all_symbols.copy()
        
        # Filter out permanently failed symbols
        symbols = self.failed_tracker.get_retryable_symbols(symbols)
        
        # Prioritize popular symbols
        popular = [s for s in symbols if s in self.popular_symbols]
        others = [s for s in symbols if s not in self.popular_symbols]
        
        # Combine with popular first
        prioritized = popular + others
        
        if mode == "gaps_only":
            # Only process symbols with existing data
            with Session(self.engine) as session:
                existing = session.execute(
                    select(MiningStatus.symbol)
                    .where(MiningStatus.symbol.in_(prioritized))
                ).scalars().all()
                prioritized = list(existing)
        elif mode == "new_only":
            # Only process symbols without data
            with Session(self.engine) as session:
                existing = session.execute(
                    select(MiningStatus.symbol)
                    .where(MiningStatus.symbol.in_(prioritized))
                ).scalars().all()
                existing_set = set(existing)
                prioritized = [s for s in prioritized if s not in existing_set]
        
        return prioritized
    
    async def _process_full_batch(
        self,
        batch: List[str],
        days_back: int,
        concurrent_limit: int
    ):
        """Process a batch of symbols for full data collection."""
        tasks = []
        semaphore = asyncio.Semaphore(concurrent_limit)
        
        async def process_with_limit(symbol):
            async with semaphore:
                return await self._process_symbol(symbol, days_back)
        
        # Create tasks for concurrent processing
        for symbol in batch:
            task = asyncio.create_task(process_with_limit(symbol))
            tasks.append(task)
        
        # Wait for all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for symbol, result in zip(batch, results):
            if isinstance(result, Exception):
                logger.error(f"Error processing {symbol}: {result}")
                self.failed_tracker.add_failure(symbol, str(result))
                self.progress['failed'] += 1
            elif result['success']:
                self.progress['successful'] += 1
                self.progress['candles_collected'] += result.get('candles_collected', 0)
            else:
                self.failed_tracker.add_failure(symbol, result.get('error', 'Unknown error'))
                self.progress['failed'] += 1
            
            self.progress['processed'] += 1
    
    async def _process_symbol(self, symbol: str, days_back: int) -> Dict[str, Any]:
        """Process a single symbol."""
        self.progress['current_symbol'] = symbol
        start_time = time.time()
        
        try:
            # Check for gaps first
            gaps = await self.gap_filler.detect_gaps(symbol, days_back)
            
            if gaps:
                # Fill gaps
                gap_result = await self.gap_filler.fill_gaps(symbol, gaps)
                self.progress['gaps_filled'] += gap_result.get('candles_filled', 0)
                
                if not gap_result['success']:
                    return {
                        'success': False,
                        'symbol': symbol,
                        'error': f"Gap filling failed: {gap_result['errors']}"
                    }
            
            # Collect full historical data
            end_date = datetime.now(pytz.timezone('US/Eastern'))
            start_date = end_date - timedelta(days=days_back)
            
            result = await self.collector.collect_historical_data(
                symbol,
                start_date=start_date,
                end_date=end_date,
                interval="1min"
            )
            
            # Update statistics
            self.progress['api_calls'] += 1
            elapsed = time.time() - start_time
            
            # Update mining status in database
            await self._update_mining_status(symbol, result, elapsed)
            
            return {
                'success': result.get('success', False),
                'symbol': symbol,
                'candles_collected': result.get('stored_count', 0),
                'duration': elapsed,
                'error': result.get('error')
            }
            
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            return {
                'success': False,
                'symbol': symbol,
                'error': str(e)
            }
    
    async def _process_gaps_batch(self, batch: List[str]):
        """Process a batch of symbols for gap filling only."""
        for symbol in batch:
            if not self.is_running:
                break
            
            self.progress['current_symbol'] = symbol
            
            try:
                # Detect and fill gaps
                gaps = await self.gap_filler.detect_gaps(symbol, days_back=60)
                
                if gaps:
                    gap_result = await self.gap_filler.fill_gaps(symbol, gaps)
                    
                    if gap_result['success']:
                        self.progress['successful'] += 1
                        self.progress['gaps_filled'] += gap_result['candles_filled']
                    else:
                        self.progress['failed'] += 1
                        self.failed_tracker.add_failure(symbol, str(gap_result['errors']))
                else:
                    self.progress['skipped'] += 1
                    
            except Exception as e:
                logger.error(f"Error processing gaps for {symbol}: {e}")
                self.progress['failed'] += 1
                self.failed_tracker.add_failure(symbol, str(e))
            
            self.progress['processed'] += 1
    
    async def _check_rate_limits(self):
        """Check and handle rate limits."""
        # Schwab API: 120 requests per second
        if self.progress['api_calls'] > 0:
            elapsed = (datetime.now() - self.progress['start_time']).total_seconds()
            current_rate = self.progress['api_calls'] / elapsed if elapsed > 0 else 0
            
            if current_rate > 100:  # Stay under 120 limit
                delay = 1.0  # Delay 1 second
                self.progress['rate_limit_delays'] += 1
                logger.info(f"Rate limit approaching, delaying {delay}s")
                await asyncio.sleep(delay)
    
    async def _update_mining_status(self, symbol: str, result: Dict, duration: float):
        """Update mining status in database."""
        with Session(self.engine) as session:
            # Get or create status
            status = session.execute(
                select(MiningStatus).where(MiningStatus.symbol == symbol)
            ).scalar_one_or_none()
            
            if not status:
                status = MiningStatus(symbol=symbol)
                session.add(status)
            
            # Update fields
            if result.get('success'):
                status.last_update = datetime.now(pytz.UTC)
                status.total_candles = result.get('stored_count', 0)
                status.data_quality_score = result.get('quality_score', 0)
                
                # Update date range
                if result.get('date_range'):
                    status.first_date = result['date_range'].get('start')
                    status.last_date = result['date_range'].get('end')
            
            # Log the operation
            log_entry = MiningLog(
                symbol=symbol,
                operation=self.mode,
                start_time=datetime.now(pytz.UTC) - timedelta(seconds=duration),
                end_time=datetime.now(pytz.UTC),
                candles_added=result.get('stored_count', 0),
                success=result.get('success', False),
                error_message=result.get('error'),
                api_calls=1
            )
            session.add(log_entry)
            
            session.commit()
    
    async def _update_progress(self):
        """Update progress metrics and Redis."""
        if not self.progress['start_time']:
            return
        
        elapsed = (datetime.now() - self.progress['start_time']).total_seconds()
        
        # Calculate rates
        if elapsed > 0:
            self.performance['symbols_per_minute'] = (self.progress['processed'] / elapsed) * 60
            self.performance['candles_per_second'] = self.progress['candles_collected'] / elapsed
            self.performance['api_calls_per_minute'] = (self.progress['api_calls'] / elapsed) * 60
            
            # Estimate completion
            if self.progress['processed'] > 0:
                avg_time = elapsed / self.progress['processed']
                remaining = self.progress['total_symbols'] - self.progress['processed']
                eta_seconds = remaining * avg_time
                self.progress['estimated_completion'] = (
                    datetime.now() + timedelta(seconds=eta_seconds)
                ).isoformat()
        
        # Update Redis
        if self.redis_client:
            try:
                await self.redis_client.hset(
                    "mining:progress",
                    mapping={
                        "processed": self.progress['processed'],
                        "total": self.progress['total_symbols'],
                        "successful": self.progress['successful'],
                        "failed": self.progress['failed'],
                        "candles": self.progress['candles_collected'],
                        "current_symbol": self.progress['current_symbol'] or "",
                        "estimated_completion": self.progress['estimated_completion'] or ""
                    }
                )
            except Exception as e:
                logger.error(f"Redis update error: {e}")
    
    async def _generate_final_report(self):
        """Generate comprehensive final report."""
        if not self.progress['start_time']:
            return
        
        duration = (datetime.now() - self.progress['start_time']).total_seconds()
        
        report = {
            "summary": {
                "mode": self.mode,
                "total_symbols": self.progress['total_symbols'],
                "processed": self.progress['processed'],
                "successful": self.progress['successful'],
                "failed": self.progress['failed'],
                "skipped": self.progress['skipped'],
                "candles_collected": self.progress['candles_collected'],
                "gaps_filled": self.progress['gaps_filled'],
                "duration_hours": round(duration / 3600, 2)
            },
            "performance": self.performance,
            "failures": {
                "permanent": len(self.failed_tracker.failed_symbols),
                "temporary": len(self.failed_tracker.temp_failures)
            },
            "rate_limits": {
                "delays": self.progress['rate_limit_delays'],
                "total_api_calls": self.progress['api_calls']
            }
        }
        
        # Save report
        report_path = CONFIG_PATH / f"mining_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Mining completed. Report saved to {report_path}")
        logger.info(json.dumps(report['summary'], indent=2))
        
        return report
    
    async def pause_mining(self):
        """Pause mining operations."""
        self.pause_requested = True
        logger.info("Mining pause requested")
    
    async def resume_mining(self):
        """Resume mining operations."""
        self.pause_requested = False
        logger.info("Mining resumed")
    
    async def stop_mining(self):
        """Stop mining operations."""
        self.is_running = False
        logger.info("Mining stop requested")
        
        # Wait for current operations to complete
        for _ in range(30):
            if self.progress['current_symbol'] is None:
                break
            await asyncio.sleep(1)
        
        # Cleanup
        self.collector.cleanup()
        await self.failed_tracker.save_failed_symbols()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current mining status."""
        return {
            "is_running": self.is_running,
            "is_paused": self.pause_requested,
            "mode": self.mode,
            "progress": self.progress,
            "performance": self.performance,
            "failed_symbols": len(self.failed_tracker.failed_symbols)
        }