"""Backtesting schemas."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from decimal import Decimal


class BacktestRequest(BaseModel):
    """Request to start a backtest."""
    strategy_id: str
    start_date: datetime
    end_date: datetime
    symbols: Optional[List[str]] = None  # Override strategy symbols
    initial_capital: float = 100000.0
    commission_rate: float = 0.001  # 0.1%
    slippage_rate: float = 0.0005  # 0.05%


class BacktestResponse(BaseModel):
    """Response when backtest is started."""
    backtest_id: str
    status: str
    message: str


class BacktestStatus(BaseModel):
    """Backtest status and progress."""
    backtest_id: str
    status: str  # pending, running, completed, failed
    progress: float  # 0-100
    strategy_name: str
    symbols: List[str]
    start_date: datetime
    end_date: datetime
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class BacktestResultResponse(BaseModel):
    """Detailed backtest results."""
    backtest_id: str
    strategy_id: str
    strategy_name: str
    
    # Performance metrics
    total_return: float
    total_return_pct: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration: int  # days
    
    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    average_win: float
    average_loss: float
    largest_win: float
    largest_loss: float
    profit_factor: float
    
    # Risk metrics
    var_95: float  # Value at Risk 95%
    cvar_95: float  # Conditional Value at Risk 95%
    
    # Time metrics
    average_holding_period: float  # hours
    longest_winning_streak: int
    longest_losing_streak: int
    
    # Capital metrics
    starting_capital: float
    ending_capital: float
    peak_capital: float
    lowest_capital: float
    
    # Monthly returns
    monthly_returns: List[Dict[str, Any]]
    
    # Equity curve data
    equity_curve: List[Dict[str, Any]]
    
    # Trade log
    trades: List[Dict[str, Any]]