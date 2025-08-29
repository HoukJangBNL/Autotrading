"""Enhanced Mining Orchestrator with multi-phase support and monitoring."""

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from pathlib import Path
from sqlalchemy import create_engine, select, and_, or_
from sqlalchemy.orm import Session
import pytz
from src.utils.logger import get_logger
from src.data.historical_data_collector_v2 import EnhancedHistoricalDataCollector
from src.models.market_data import MiningStatus, MiningLog
from src.models.mining_mode import MiningMode, MiningModeConfig, MiningSession
import os

logger = get_logger(__name__)

CONFIG_PATH = Path(__file__).parent.parent.parent / "config"


class PhaseManager:
    """Manage mining phases and symbol lists."""
    
    def __init__(self):
        self.phases = {
            1: self._load_phase_1_symbols(),
            2: self._load_phase_2_symbols(),
            3: self._load_phase_3_symbols()
        }
        self.combined_symbols = self._get_combined_symbols()
        
    def _load_phase_1_symbols(self) -> Set[str]:
        """Load Phase 1 core tickers."""
        config_file = CONFIG_PATH / "core_tickers.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                data = json.load(f)
                return set(data.get("core_tickers", []))
        return set()
    
    def _load_phase_2_symbols(self) -> Set[str]:
        """Load Phase 2 S&P 100 symbols."""
        config_file = CONFIG_PATH / "sp100_symbols.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                data = json.load(f)
                return set(data.get("symbols", []))
        return set()
    
    def _load_phase_3_symbols(self) -> Set[str]:
        """Load Phase 3 NASDAQ 100 symbols."""
        config_file = CONFIG_PATH / "nasdaq100_symbols.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                data = json.load(f)
                return set(data.get("symbols", []))
        return set()
    
    def _load_all_us_stocks(self) -> Set[str]:
        """Load all US stock symbols for expansion mode."""
        config_file = CONFIG_PATH / "all_us_stocks_symbols.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                data = json.load(f)
                all_symbols = set(data.get("symbols", []))
                logger.info(f"Loaded {len(all_symbols)} total US stock symbols")
                return all_symbols
        logger.warning("all_us_stocks_symbols.json not found")
        return set()
    
    def _get_combined_symbols(self) -> Dict[int, Set[str]]:
        """Get combined unique symbols for each phase."""
        phase_1 = self.phases[1]
        phase_2 = self.phases[2] - phase_1  # Exclude Phase 1 symbols
        phase_3 = self.phases[3] - phase_1 - phase_2  # Exclude previous phases
        
        return {
            1: phase_1,
            2: phase_1 | phase_2,  # Cumulative
            3: phase_1 | phase_2 | phase_3  # Cumulative
        }
    
    def get_symbols_for_phase(self, phase: int, cumulative: bool = True) -> List[str]:
        """Get symbols for a specific phase."""
        if phase not in [1, 2, 3]:
            return []
        
        if cumulative:
            return list(self.combined_symbols[phase])
        else:
            return list(self.phases[phase])
    
    def get_phase_stats(self) -> Dict:
        """Get statistics for all phases."""
        return {
            1: {
                "name": "Core Tickers",
                "unique_symbols": len(self.phases[1]),
                "cumulative_symbols": len(self.combined_symbols[1])
            },
            2: {
                "name": "S&P 100",
                "unique_symbols": len(self.phases[2]),
                "cumulative_symbols": len(self.combined_symbols[2])
            },
            3: {
                "name": "NASDAQ 100",
                "unique_symbols": len(self.phases[3]),
                "cumulative_symbols": len(self.combined_symbols[3])
            }
        }
    
    def get_symbols_for_mode(self, mode: MiningMode, priority_limit: Optional[int] = None) -> List[str]:
        """Get symbols based on mining mode.
        
        Args:
            mode: The mining mode (GAP_FILLING or EXPANSION)
            priority_limit: Optional limit for number of symbols (for testing or batching)
        
        Returns:
            List of symbols appropriate for the mode
        """
        if mode == MiningMode.GAP_FILLING:
            # For gap filling, use existing portfolio symbols (Phase 1)
            symbols = list(self.combined_symbols[1])
            logger.info(f"Gap filling mode: Using {len(symbols)} portfolio symbols")
            return symbols
            
        elif mode == MiningMode.EXPANSION:
            # For expansion, use all US stocks minus already processed symbols
            all_stocks = self._load_all_us_stocks()
            existing_symbols = self.combined_symbols[3]  # All phase symbols
            
            # Get new symbols not in existing portfolio
            new_symbols = all_stocks - existing_symbols
            
            # Prioritize by market cap/popularity (using predefined lists)
            priority_symbols = []
            
            # First add remaining S&P 100 and NASDAQ 100 symbols
            sp100_remaining = self.phases[2] - existing_symbols
            nasdaq100_remaining = self.phases[3] - existing_symbols
            
            priority_symbols.extend(list(sp100_remaining))
            priority_symbols.extend(list(nasdaq100_remaining))
            
            # Then add other symbols
            other_symbols = new_symbols - sp100_remaining - nasdaq100_remaining
            priority_symbols.extend(sorted(list(other_symbols)))
            
            # Apply limit if specified
            if priority_limit and priority_limit < len(priority_symbols):
                priority_symbols = priority_symbols[:priority_limit]
                logger.info(f"Expansion mode: Limited to {priority_limit} symbols")
            else:
                logger.info(f"Expansion mode: Using {len(priority_symbols)} new symbols from {len(all_stocks)} total")
            
            return priority_symbols
            
        else:  # AUTO mode
            # For auto mode, return Phase 1 symbols initially
            # The orchestrator will handle mode switching
            return list(self.combined_symbols[1])


class EnhancedMiningOrchestrator:
    """Enhanced orchestrator with multi-phase support and monitoring."""
    
    def __init__(self, client=None, mode_config: Optional[MiningModeConfig] = None):
        """Initialize the enhanced orchestrator."""
        self.collector = EnhancedHistoricalDataCollector(client, max_workers=5)
        self.phase_manager = PhaseManager()
        self.db_url = os.getenv("DATABASE_URL", "postgresql://trading_user:trading_pass@localhost/trading_dev")
        self.engine = create_engine(self.db_url)
        
        # Mining mode configuration
        if mode_config is None:
            mode_config = MiningModeConfig(
                mode=MiningMode.AUTO,
                gap_filling_first=True,
                switch_on_completion=True
            )
        self.mode_config = mode_config
        self.mining_session = MiningSession(mode_config)
        
        self.is_running = False
        self.current_phase = 1
        self.max_phase = 3
        self.auto_advance = False  # Auto-advance to next phase
        self.expansion_limit = None  # Optional limit for expansion mode symbols
        
        self.progress = {
            'phase': 1,
            'symbols_total': 0,
            'symbols_completed': 0,
            'symbols_failed': 0,
            'candles_collected': 0,
            'start_time': None,
            'phase_start_times': {},
            'phase_completions': {},
            'current_symbol': None,
            'estimated_completion': None
        }
        
        self.quality_metrics = {
            'average_quality': 0.0,
            'low_quality_symbols': [],
            'gap_symbols': [],
            'validation_failures': 0
        }
        
    async def execute_gap_filling_mode(self, symbols: List[str], days_back: int = 60):
        """Execute gap filling mode - fill missing data in existing records.
        
        Args:
            symbols: List of symbols to check for gaps
            days_back: Number of days to look back (0 means dynamic from last data to current)
        """
        logger.info(f"Starting gap filling mode for {len(symbols)} symbols")
        
        self.mining_session.current_operation = "Gap Filling"
        self.mining_session.total_symbols = len(symbols)
        
        # If days_back is 0, use dynamic gap detection (from last data to current)
        if days_back == 0:
            # Dynamic gap detection will be handled per symbol in _identify_symbols_with_gaps
            logger.info("Using dynamic gap detection (from last data to current)")
        
        # Prioritize symbols with known gaps
        symbols_with_gaps = await self._identify_symbols_with_gaps(symbols, days_back)
        
        if not symbols_with_gaps:
            logger.info("No gaps found in any symbols")
            self.mining_session.gap_filling_completed = True
            return
        
        logger.info(f"Found {len(symbols_with_gaps)} symbols with gaps")
        
        # Process symbols with gaps
        batch_size = 5  # Smaller batch for gap filling
        for i in range(0, len(symbols_with_gaps), batch_size):
            if not self.is_running:
                break
                
            batch = symbols_with_gaps[i:i+batch_size]
            
            for symbol in batch:
                self.mining_session.current_symbol = symbol
                
                # Identify specific gaps for this symbol
                gaps = await self._identify_gaps_for_symbol(symbol, days_back)
                
                if gaps:
                    logger.info(f"Filling {len(gaps)} gaps for {symbol}")
                    
                    # Fill each gap
                    for gap_start, gap_end in gaps:
                        result = await self.collector.collect_historical_data(
                            symbol,
                            start_date=gap_start,
                            end_date=gap_end,
                            interval="1min"
                        )
                        
                        if result.get('success'):
                            self.mining_session.gaps_filled += 1
                            self.mining_session.data_points_collected += result.get('candles_count', 0)
                
                self.mining_session.update_progress(
                    symbol, 
                    success=True,
                    gaps_filled=self.mining_session.gaps_filled
                )
        
        self.mining_session.gap_filling_completed = True
        logger.info(f"Gap filling completed. Filled {self.mining_session.gaps_filled} gaps")
    
    async def execute_expansion_mode(self, symbols: List[str], days_back: int = 60):
        """Execute expansion mode - collect new historical data."""
        logger.info(f"Starting expansion mode for {len(symbols)} symbols")
        
        self.mining_session.current_operation = "Data Expansion"
        self.mining_session.total_symbols = len(symbols)
        
        # Identify symbols needing expansion
        symbols_to_expand = await self._identify_symbols_for_expansion(symbols, days_back)
        
        if not symbols_to_expand:
            logger.info("No symbols need expansion")
            self.mining_session.expansion_completed = True
            return
        
        logger.info(f"Expanding data for {len(symbols_to_expand)} symbols")
        
        # Collect historical data
        batch_size = 10
        for i in range(0, len(symbols_to_expand), batch_size):
            if not self.is_running:
                break
                
            batch = symbols_to_expand[i:i+batch_size]
            
            result = await self.collector.collect_historical_batch(
                batch,
                days_back=days_back,
                operation="expansion"
            )
            
            for r in result.get('results', []):
                self.mining_session.update_progress(
                    r['symbol'],
                    success=r['success'],
                    data_points=r.get('candles_count', 0)
                )
        
        self.mining_session.expansion_completed = True
        logger.info(f"Expansion completed. Collected {self.mining_session.data_points_collected} data points")
    
    async def execute_mining_with_modes(self, symbols: Optional[List[str]] = None, days_back: int = 60):
        """Execute mining with mode management.
        
        Args:
            symbols: Optional list of symbols. If not provided, will be determined based on mode.
            days_back: Number of days to look back for data collection.
        """
        self.is_running = True
        self.mining_session.start_time = datetime.now()
        
        # Get PhaseManager to determine symbols based on mode
        phase_manager = PhaseManager()
        
        try:
            if self.mining_session.config.mode == MiningMode.GAP_FILLING:
                # Gap filling mode only - use portfolio symbols
                gap_symbols = symbols or phase_manager.get_symbols_for_mode(MiningMode.GAP_FILLING)
                await self.execute_gap_filling_mode(gap_symbols, days_back)
                
            elif self.mining_session.config.mode == MiningMode.EXPANSION:
                # Expansion mode only - use all US stocks (with optional limit)
                expansion_symbols = symbols or phase_manager.get_symbols_for_mode(
                    MiningMode.EXPANSION, 
                    priority_limit=self.expansion_limit  # Use configured limit or None for all
                )
                await self.execute_expansion_mode(expansion_symbols, days_back)
                
            elif self.mining_session.config.mode == MiningMode.AUTO:
                # Auto mode - switch between gap filling and expansion with appropriate symbols
                if self.mining_session.config.gap_filling_first:
                    # Start with gap filling using portfolio symbols
                    self.mining_session.current_mode = MiningMode.GAP_FILLING
                    gap_symbols = phase_manager.get_symbols_for_mode(MiningMode.GAP_FILLING)
                    await self.execute_gap_filling_mode(gap_symbols, days_back)
                    
                    # Check if should switch to expansion
                    if self.mining_session.should_switch_mode():
                        self.mining_session.switch_mode()
                        # Use all US stocks for expansion
                        expansion_symbols = phase_manager.get_symbols_for_mode(
                            MiningMode.EXPANSION,
                            priority_limit=self.expansion_limit  # Use configured limit
                        )
                        await self.execute_expansion_mode(expansion_symbols, days_back)
                else:
                    # Start with expansion using all US stocks
                    self.mining_session.current_mode = MiningMode.EXPANSION
                    expansion_symbols = phase_manager.get_symbols_for_mode(
                        MiningMode.EXPANSION,
                        priority_limit=self.expansion_limit  # Use configured limit
                    )
                    await self.execute_expansion_mode(expansion_symbols, days_back)
                    
                    # Check if should switch to gap filling
                    if self.mining_session.should_switch_mode():
                        self.mining_session.switch_mode()
                        gap_symbols = phase_manager.get_symbols_for_mode(MiningMode.GAP_FILLING)
                        await self.execute_gap_filling_mode(gap_symbols, days_back)
        
        except Exception as e:
            logger.error(f"Mining execution error: {e}")
        finally:
            self.is_running = False
            self.mining_session.end_time = datetime.now()
            stats = self.mining_session.get_session_stats()
            logger.info(f"Mining session completed: {json.dumps(stats, indent=2)}")
    
    async def execute_multi_phase_mining(
        self,
        start_phase: int = 1,
        end_phase: int = 3,
        days_back: int = 60
    ):
        """Execute mining across multiple phases."""
        self.is_running = True
        self.progress['start_time'] = datetime.now()
        
        try:
            for phase in range(start_phase, min(end_phase + 1, 4)):
                if not self.is_running:
                    logger.info("Mining stopped by user")
                    break
                
                self.current_phase = phase
                self.progress['phase'] = phase
                self.progress['phase_start_times'][phase] = datetime.now()
                
                logger.info(f"Starting Phase {phase} mining")
                
                # Get symbols for this phase
                symbols = self.phase_manager.get_symbols_for_phase(phase, cumulative=False)
                symbols_to_mine = await self._prioritize_symbols(symbols)
                
                if not symbols_to_mine:
                    logger.info(f"Phase {phase}: No symbols to mine")
                    self.progress['phase_completions'][phase] = datetime.now()
                    continue
                
                self.progress['symbols_total'] = len(symbols_to_mine)
                self.progress['symbols_completed'] = 0
                self.progress['symbols_failed'] = 0
                
                logger.info(f"Phase {phase}: Mining {len(symbols_to_mine)} symbols")
                
                # Collect data in batches
                batch_size = 10  # Process 10 symbols at a time
                for i in range(0, len(symbols_to_mine), batch_size):
                    if not self.is_running:
                        break
                    
                    batch = symbols_to_mine[i:i+batch_size]
                    
                    # Update progress
                    self.progress['current_symbol'] = f"Batch {i//batch_size + 1}"
                    self._update_estimated_completion()
                    
                    # Collect batch
                    result = await self.collector.collect_historical_batch(
                        batch,
                        days_back=days_back,
                        operation=f"phase_{phase}"
                    )
                    
                    # Update metrics
                    self._update_quality_metrics(result)
                    
                    # Log batch results
                    await self._log_batch_results(phase, batch, result)
                    
                    # Update progress
                    for r in result['results']:
                        if r['success']:
                            self.progress['symbols_completed'] += 1
                            self.progress['candles_collected'] += r.get('candles_count', 0)
                        else:
                            self.progress['symbols_failed'] += 1
                    
                    # Progress report
                    progress_pct = (self.progress['symbols_completed'] + self.progress['symbols_failed']) / self.progress['symbols_total'] * 100
                    logger.info(f"Phase {phase} progress: {progress_pct:.1f}%")
                
                self.progress['phase_completions'][phase] = datetime.now()
                logger.info(f"Phase {phase} completed: {self.progress['symbols_completed']} success, {self.progress['symbols_failed']} failed")
                
        except Exception as e:
            logger.error(f"Mining orchestration error: {e}")
        finally:
            self.is_running = False
            self.collector.cleanup()
            await self._generate_final_report()
    
    async def _identify_symbols_with_gaps(self, symbols: List[str], days_back: int) -> List[str]:
        """Identify symbols that have gaps in their data."""
        symbols_with_gaps = []
        
        with Session(self.engine) as session:
            for symbol in symbols:
                # Check for gaps in the last N days
                gaps_query = session.execute(
                    select(MiningStatus.gaps_detected)
                    .where(MiningStatus.symbol == symbol)
                ).scalar()
                
                if gaps_query and gaps_query > 0:
                    symbols_with_gaps.append(symbol)
        
        return symbols_with_gaps
    
    async def _identify_gaps_for_symbol(self, symbol: str, days_back: int) -> List[tuple]:
        """Identify specific time gaps for a symbol."""
        gaps = []
        
        # This is a simplified implementation
        # In production, you would query the actual data and find time gaps
        # For now, we'll return empty list as placeholder
        return gaps
    
    async def _identify_symbols_for_expansion(self, symbols: List[str], days_back: int) -> List[str]:
        """Identify symbols that need data expansion."""
        symbols_to_expand = []
        cutoff_date = datetime.now(pytz.UTC) - timedelta(days=days_back)
        
        with Session(self.engine) as session:
            for symbol in symbols:
                # Check if symbol has old data or no data
                status = session.execute(
                    select(MiningStatus)
                    .where(MiningStatus.symbol == symbol)
                ).scalar()
                
                if not status or status.first_date is None or status.first_date > cutoff_date:
                    symbols_to_expand.append(symbol)
        
        return symbols_to_expand
    
    async def _prioritize_symbols(self, symbols: List[str]) -> List[str]:
        """Prioritize symbols based on data quality and completeness."""
        prioritized = []
        
        with Session(self.engine) as session:
            # Get existing symbols with poor quality
            poor_quality = session.execute(
                select(MiningStatus.symbol)
                .where(
                    and_(
                        MiningStatus.symbol.in_(symbols),
                        MiningStatus.data_quality_score < 90
                    )
                )
                .order_by(MiningStatus.data_quality_score)
            ).scalars().all()
            
            # Get symbols with gaps
            gap_symbols = session.execute(
                select(MiningStatus.symbol)
                .where(
                    and_(
                        MiningStatus.symbol.in_(symbols),
                        MiningStatus.gaps_detected > 0
                    )
                )
                .order_by(MiningStatus.gaps_detected.desc())
            ).scalars().all()
            
            # Get symbols needing updates
            update_threshold = datetime.now(pytz.UTC) - timedelta(days=1)
            update_symbols = session.execute(
                select(MiningStatus.symbol)
                .where(
                    and_(
                        MiningStatus.symbol.in_(symbols),
                        or_(
                            MiningStatus.last_update < update_threshold,
                            MiningStatus.last_update.is_(None)
                        )
                    )
                )
            ).scalars().all()
            
            # Get existing symbols
            existing = session.execute(
                select(MiningStatus.symbol)
                .where(MiningStatus.symbol.in_(symbols))
            ).scalars().all()
            existing_set = set(existing)
        
        # Combine in priority order
        seen = set()
        
        # 1. Poor quality symbols (need fixing)
        for symbol in poor_quality:
            if symbol not in seen:
                prioritized.append(symbol)
                seen.add(symbol)
        
        # 2. Symbols with gaps
        for symbol in gap_symbols:
            if symbol not in seen:
                prioritized.append(symbol)
                seen.add(symbol)
        
        # 3. Symbols needing updates
        for symbol in update_symbols:
            if symbol not in seen:
                prioritized.append(symbol)
                seen.add(symbol)
        
        # 4. New symbols
        for symbol in symbols:
            if symbol not in existing_set and symbol not in seen:
                prioritized.append(symbol)
                seen.add(symbol)
        
        return prioritized
    
    def _update_quality_metrics(self, result: Dict):
        """Update quality metrics from batch results."""
        if 'results' not in result:
            return
        
        quality_scores = []
        for r in result['results']:
            if r['success'] and 'quality_score' in r:
                quality_scores.append(r['quality_score'])
                if r['quality_score'] < 80:
                    self.quality_metrics['low_quality_symbols'].append({
                        'symbol': r['symbol'],
                        'score': r['quality_score']
                    })
        
        if quality_scores:
            self.quality_metrics['average_quality'] = sum(quality_scores) / len(quality_scores)
        
        self.quality_metrics['validation_failures'] = result.get('stats', {}).get('validation_failures', 0)
    
    def _update_estimated_completion(self):
        """Update estimated completion time."""
        if not self.progress['start_time'] or self.progress['symbols_completed'] == 0:
            return
        
        elapsed = (datetime.now() - self.progress['start_time']).total_seconds()
        rate = self.progress['symbols_completed'] / elapsed if elapsed > 0 else 0
        
        if rate > 0:
            remaining = self.progress['symbols_total'] - self.progress['symbols_completed'] - self.progress['symbols_failed']
            seconds_remaining = remaining / rate
            self.progress['estimated_completion'] = (
                datetime.now() + timedelta(seconds=seconds_remaining)
            ).isoformat()
    
    async def _log_batch_results(self, phase: int, symbols: List[str], result: Dict):
        """Log batch mining results."""
        with Session(self.engine) as session:
            for symbol_result in result.get('results', []):
                log = MiningLog(
                    symbol=symbol_result['symbol'],
                    operation=f"phase_{phase}_batch",
                    start_time=datetime.now(pytz.UTC) - timedelta(seconds=result.get('duration', 0)),
                    end_time=datetime.now(pytz.UTC),
                    candles_added=symbol_result.get('stored_count', 0),
                    success=symbol_result['success'],
                    error_message=symbol_result.get('error'),
                    api_calls=1
                )
                session.add(log)
            session.commit()
    
    async def _generate_final_report(self):
        """Generate comprehensive final report."""
        if not self.progress['start_time']:
            return
        
        total_duration = (datetime.now() - self.progress['start_time']).total_seconds()
        
        report = {
            "summary": {
                "phases_completed": list(self.progress['phase_completions'].keys()),
                "total_symbols": self.progress['symbols_total'],
                "successful": self.progress['symbols_completed'],
                "failed": self.progress['symbols_failed'],
                "total_candles": self.progress['candles_collected'],
                "duration_minutes": round(total_duration / 60, 2)
            },
            "quality": self.quality_metrics,
            "performance": {
                "symbols_per_minute": (self.progress['symbols_completed'] / total_duration * 60) if total_duration > 0 else 0,
                "candles_per_second": (self.progress['candles_collected'] / total_duration) if total_duration > 0 else 0
            },
            "phase_details": {}
        }
        
        # Add phase-specific details
        for phase, start_time in self.progress['phase_start_times'].items():
            if phase in self.progress['phase_completions']:
                phase_duration = (self.progress['phase_completions'][phase] - start_time).total_seconds()
                report["phase_details"][phase] = {
                    "duration_minutes": round(phase_duration / 60, 2),
                    "symbols_count": len(self.phase_manager.get_symbols_for_phase(phase, cumulative=False))
                }
        
        logger.info(f"Mining completed: {json.dumps(report, indent=2)}")
        return report
    
    def get_detailed_status(self) -> Dict:
        """Get detailed mining status with all metrics."""
        elapsed = 0
        if self.progress['start_time']:
            elapsed = (datetime.now() - self.progress['start_time']).total_seconds()
        
        return {
            "is_running": self.is_running,
            "current_phase": self.current_phase,
            "mining_mode": {
                "current_mode": self.mining_session.current_mode.value,
                "config": {
                    "mode": self.mode_config.mode.value,
                    "gap_filling_first": self.mode_config.gap_filling_first,
                    "switch_on_completion": self.mode_config.switch_on_completion,
                    "lookback_days": self.mode_config.lookback_days
                },
                "session": self.mining_session.get_session_stats()
            },
            "progress": {
                **self.progress,
                "start_time": self.progress['start_time'].isoformat() if self.progress['start_time'] else None,
                "elapsed_minutes": round(elapsed / 60, 2) if elapsed > 0 else 0,
                "completion_percentage": (
                    (self.progress['symbols_completed'] + self.progress['symbols_failed']) / 
                    self.progress['symbols_total'] * 100
                ) if self.progress['symbols_total'] > 0 else 0
            },
            "quality": self.quality_metrics,
            "phase_info": self.phase_manager.get_phase_stats(),
            "collector_stats": self.collector.stats if hasattr(self.collector, 'stats') else {}
        }
    
    async def stop_mining(self):
        """Stop mining operations gracefully."""
        self.is_running = False
        logger.info("Mining stop requested - will complete current batch")
        
        # Wait for current batch to complete (max 30 seconds)
        for _ in range(30):
            if not self.collector.executor._threads:
                break
            await asyncio.sleep(1)
        
        self.collector.cleanup()