"""Mining Orchestrator for coordinating data collection."""

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import Session
import pytz
from src.utils.logger import get_logger
from src.data.historical_data_collector import HistoricalDataCollector
from src.models.market_data import MiningStatus
import os

logger = get_logger(__name__)

# Config path
CONFIG_PATH = Path(__file__).parent.parent.parent / "config"


class MiningOrchestrator:
    """Orchestrates data mining operations with prioritization and monitoring."""
    
    def __init__(self, client=None):
        """Initialize the orchestrator."""
        self.collector = HistoricalDataCollector(client)
        self.db_url = os.getenv("DATABASE_URL", "postgresql://trading_user:trading_pass@localhost/trading_dev")
        self.engine = create_engine(self.db_url)
        self.is_running = False
        self.current_phase = 1
        self.symbols_queue = []
        self.completed_symbols = set()
        self.failed_symbols = set()
        self.stats = {
            "total_symbols": 0,
            "completed": 0,
            "failed": 0,
            "total_candles": 0,
            "start_time": None,
            "api_calls": 0
        }
        
    def load_symbols(self, phase: int = 1) -> List[str]:
        """Load symbols for a specific phase."""
        symbols = []
        
        if phase == 1:
            # Phase 1: Core tickers
            config_file = CONFIG_PATH / "core_tickers.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    symbols = data.get("core_tickers", [])
            else:
                # Default core tickers if file doesn't exist
                symbols = [
                    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", 
                    "TSLA", "META", "BRK.B", "JPM", "JNJ",
                    "SPY", "QQQ", "IWM", "DIA", "VTI"
                ]
                # Save for future use
                config_file.parent.mkdir(exist_ok=True)
                with open(config_file, 'w') as f:
                    json.dump({"core_tickers": symbols}, f, indent=2)
                    
        elif phase == 2:
            # Phase 2: S&P 100 (placeholder - need actual list)
            config_file = CONFIG_PATH / "sp100_symbols.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    symbols = data.get("symbols", [])
            else:
                # For now, return empty - need to populate with actual S&P 100
                symbols = []
                
        elif phase == 3:
            # Phase 3: NASDAQ 100 (placeholder - need actual list)
            config_file = CONFIG_PATH / "nasdaq100_symbols.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    symbols = data.get("symbols", [])
            else:
                symbols = []
                
        logger.info(f"Loaded {len(symbols)} symbols for Phase {phase}")
        return symbols
    
    async def prioritize_symbols(self) -> List[str]:
        """
        Prioritize symbols for collection.
        Priority order:
        1. Symbols with gaps
        2. Symbols needing updates
        3. New symbols
        """
        prioritized = []
        
        with Session(self.engine) as session:
            # 1. Get symbols with poor data quality (gaps)
            gaps_symbols = session.execute(
                select(MiningStatus.symbol)
                .where(
                    and_(
                        MiningStatus.is_active == True,
                        MiningStatus.data_quality_score < 95
                    )
                )
                .order_by(MiningStatus.data_quality_score)
            ).scalars().all()
            
            # 2. Get symbols needing updates (older than 1 day)
            update_threshold = datetime.now(pytz.UTC) - timedelta(days=1)
            update_symbols = session.execute(
                select(MiningStatus.symbol)
                .where(
                    and_(
                        MiningStatus.is_active == True,
                        MiningStatus.last_update < update_threshold
                    )
                )
                .order_by(MiningStatus.last_update)
            ).scalars().all()
            
            # 3. Get symbols not in database (new)
            existing_symbols = session.execute(
                select(MiningStatus.symbol)
            ).scalars().all()
            existing_set = set(existing_symbols)
            
        # Load symbols for current phase
        phase_symbols = self.load_symbols(self.current_phase)
        new_symbols = [s for s in phase_symbols if s not in existing_set]
        
        # Combine in priority order (avoiding duplicates)
        seen = set()
        
        # Add gap symbols first
        for symbol in gaps_symbols:
            if symbol not in seen:
                prioritized.append(symbol)
                seen.add(symbol)
                
        # Add update symbols
        for symbol in update_symbols:
            if symbol not in seen:
                prioritized.append(symbol)
                seen.add(symbol)
                
        # Add new symbols
        for symbol in new_symbols:
            if symbol not in seen:
                prioritized.append(symbol)
                seen.add(symbol)
                
        logger.info(f"Prioritized {len(prioritized)} symbols: "
                   f"{len(gaps_symbols)} with gaps, "
                   f"{len(update_symbols)} need updates, "
                   f"{len(new_symbols)} new")
        
        return prioritized
    
    async def execute_mining(self):
        """Execute mining for prioritized symbols."""
        self.is_running = True
        self.stats["start_time"] = datetime.now()
        
        try:
            # Get prioritized symbols
            self.symbols_queue = await self.prioritize_symbols()
            self.stats["total_symbols"] = len(self.symbols_queue)
            
            logger.info(f"Starting mining for {len(self.symbols_queue)} symbols")
            
            for symbol in self.symbols_queue:
                if not self.is_running:
                    logger.info("Mining stopped by user")
                    break
                    
                try:
                    logger.info(f"Mining {symbol} ({self.stats['completed'] + 1}/{self.stats['total_symbols']})")
                    
                    # Check if symbol has existing data
                    has_data = await self._check_existing_data(symbol)
                    
                    if has_data:
                        # Fill gaps first
                        gaps_filled = await self.collector.fill_gaps(symbol)
                        logger.info(f"Filled {gaps_filled} gaps for {symbol}")
                        
                        # Then update recent data (last 5 days)
                        result = await self.collector.collect_historical_data(
                            symbol=symbol,
                            days_back=5,
                            operation="update"
                        )
                    else:
                        # Initial collection (60 days)
                        result = await self.collector.collect_historical_data(
                            symbol=symbol,
                            days_back=60,
                            operation="initial"
                        )
                    
                    if result['success']:
                        self.completed_symbols.add(symbol)
                        self.stats["completed"] += 1
                        self.stats["total_candles"] += result['candles_added']
                        self.stats["api_calls"] += result['api_calls']
                        logger.info(f"Successfully collected {result['candles_added']} candles for {symbol}")
                    else:
                        self.failed_symbols.add(symbol)
                        self.stats["failed"] += 1
                        logger.error(f"Failed to collect data for {symbol}: {result['error']}")
                        
                    # Progress update
                    progress = (self.stats['completed'] + self.stats['failed']) / self.stats['total_symbols'] * 100
                    logger.info(f"Progress: {progress:.1f}% ({self.stats['completed']} completed, {self.stats['failed']} failed)")
                    
                except Exception as e:
                    logger.error(f"Unexpected error mining {symbol}: {e}")
                    self.failed_symbols.add(symbol)
                    self.stats["failed"] += 1
                    
                # Small delay between symbols to avoid overwhelming API
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Mining orchestration error: {e}")
            
        finally:
            self.is_running = False
            duration = (datetime.now() - self.stats["start_time"]).total_seconds()
            logger.info(f"Mining completed in {duration:.1f} seconds. "
                       f"Collected {self.stats['total_candles']} candles for "
                       f"{self.stats['completed']} symbols")
    
    async def _check_existing_data(self, symbol: str) -> bool:
        """Check if symbol has existing data."""
        with Session(self.engine) as session:
            status = session.execute(
                select(MiningStatus)
                .where(MiningStatus.symbol == symbol)
            ).scalar_one_or_none()
            
            return status is not None and status.total_candles > 0
    
    async def stop_mining(self):
        """Stop mining operations."""
        self.is_running = False
        logger.info("Mining stop requested")
    
    def get_status(self) -> Dict:
        """Get current mining status."""
        elapsed = 0
        if self.stats["start_time"]:
            elapsed = (datetime.now() - self.stats["start_time"]).total_seconds()
            
        return {
            "is_running": self.is_running,
            "current_phase": self.current_phase,
            "queue_size": len(self.symbols_queue),
            "completed": list(self.completed_symbols),
            "failed": list(self.failed_symbols),
            "stats": {
                **self.stats,
                "start_time": self.stats["start_time"].isoformat() if self.stats["start_time"] else None,
                "elapsed_seconds": elapsed,
                "symbols_per_minute": (self.stats["completed"] / (elapsed / 60)) if elapsed > 0 else 0
            }
        }
    
    async def retry_failed(self):
        """Retry failed symbols."""
        if self.failed_symbols:
            logger.info(f"Retrying {len(self.failed_symbols)} failed symbols")
            self.symbols_queue = list(self.failed_symbols)
            self.failed_symbols = set()
            await self.execute_mining()