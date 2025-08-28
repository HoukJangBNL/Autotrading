"""Strategy management schemas."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class StrategyCreate(BaseModel):
    """Create strategy request."""
    name: str
    type: str
    description: Optional[str] = ""
    symbols: List[str]
    parameters: Dict[str, Any] = Field(default_factory=dict)


class StrategyUpdate(BaseModel):
    """Update strategy request."""
    name: Optional[str] = None
    description: Optional[str] = None
    symbols: Optional[List[str]] = None
    parameters: Optional[Dict[str, Any]] = None


class StrategyResponse(BaseModel):
    """Strategy details response."""
    id: str
    name: str
    type: str
    description: str
    symbols: List[str]
    parameters: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    performance: Dict[str, Any]


class StrategyListResponse(BaseModel):
    """Strategy list item."""
    id: str
    name: str
    type: str
    description: str
    is_active: bool
    is_example: bool


class StrategyPerformance(BaseModel):
    """Strategy performance metrics."""
    strategy_id: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    average_win: float
    average_loss: float
    largest_win: float
    largest_loss: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    profit_factor: float
    average_trade_duration: float  # in hours
    trades: List[Dict[str, Any]]  # Recent trades