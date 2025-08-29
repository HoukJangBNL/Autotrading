"""Mining mode definitions and configurations."""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MiningMode(Enum):
    """Mining operation modes."""
    GAP_FILLING = "gap_filling"
    EXPANSION = "expansion"
    AUTO = "auto"  # Automatically switch between gap filling and expansion


@dataclass
class MiningModeConfig:
    """Configuration for mining modes."""
    mode: MiningMode
    priority_symbols: Optional[List[str]] = None
    lookback_days: int = 60  # Default 2 months
    min_data_points_per_day: int = 390  # Trading minutes per day
    batch_size: int = 10
    max_workers: int = 10
    
    # Gap filling specific
    gap_threshold_minutes: int = 30  # Consider gap if missing > 30 minutes
    gap_check_interval_hours: int = 1  # Check for gaps every hour
    
    # Expansion specific
    expansion_start_date: Optional[datetime] = None
    expansion_end_date: Optional[datetime] = None
    new_symbols_only: bool = False  # Only mine symbols without any data
    
    # Auto mode specific
    gap_filling_first: bool = True  # Start with gap filling in auto mode
    switch_on_completion: bool = True  # Switch modes when current mode completes


class MiningSession:
    """Track mining session state and progress."""
    
    def __init__(self, mode_config: MiningModeConfig):
        self.config = mode_config
        self.current_mode = mode_config.mode
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        
        # Progress tracking
        self.total_symbols = 0
        self.processed_symbols = 0
        self.successful_symbols = 0
        self.failed_symbols = 0
        self.gaps_filled = 0
        self.data_points_collected = 0
        
        # Mode specific tracking
        self.gap_filling_completed = False
        self.expansion_completed = False
        
        # Current operation
        self.current_symbol: Optional[str] = None
        self.current_operation: Optional[str] = None
        
    def update_progress(self, symbol: str, success: bool, data_points: int = 0, gaps_filled: int = 0):
        """Update session progress."""
        self.processed_symbols += 1
        if success:
            self.successful_symbols += 1
        else:
            self.failed_symbols += 1
        
        self.data_points_collected += data_points
        self.gaps_filled += gaps_filled
        
    def get_progress_percentage(self) -> float:
        """Get overall progress percentage."""
        if self.total_symbols == 0:
            return 0.0
        return (self.processed_symbols / self.total_symbols) * 100
    
    def get_session_stats(self) -> Dict:
        """Get current session statistics."""
        duration = (self.end_time or datetime.now()) - self.start_time
        
        return {
            "session_id": self.session_id,
            "mode": self.current_mode.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": duration.total_seconds(),
            "total_symbols": self.total_symbols,
            "processed_symbols": self.processed_symbols,
            "successful_symbols": self.successful_symbols,
            "failed_symbols": self.failed_symbols,
            "progress_percentage": self.get_progress_percentage(),
            "gaps_filled": self.gaps_filled,
            "data_points_collected": self.data_points_collected,
            "current_symbol": self.current_symbol,
            "current_operation": self.current_operation,
            "gap_filling_completed": self.gap_filling_completed,
            "expansion_completed": self.expansion_completed
        }
    
    def should_switch_mode(self) -> bool:
        """Check if mode should be switched in auto mode."""
        if self.config.mode != MiningMode.AUTO:
            return False
        
        if not self.config.switch_on_completion:
            return False
        
        if self.current_mode == MiningMode.GAP_FILLING and self.gap_filling_completed:
            return True
        
        if self.current_mode == MiningMode.EXPANSION and self.expansion_completed:
            return True
        
        return False
    
    def switch_mode(self):
        """Switch to the next mode in auto mode."""
        if self.current_mode == MiningMode.GAP_FILLING:
            self.current_mode = MiningMode.EXPANSION
            logger.info("Switching from GAP_FILLING to EXPANSION mode")
        elif self.current_mode == MiningMode.EXPANSION:
            self.current_mode = MiningMode.GAP_FILLING
            logger.info("Switching from EXPANSION to GAP_FILLING mode")