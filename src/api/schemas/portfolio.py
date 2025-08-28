"""Portfolio management schemas."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel


class PortfolioSummary(BaseModel):
    """Overall portfolio summary."""
    total_value: float
    cash_balance: float
    securities_value: float
    buying_power: float
    day_change: float
    day_change_pct: float
    total_change: float
    total_change_pct: float
    position_count: int
    last_update: datetime


class PortfolioPosition(BaseModel):
    """Individual portfolio position."""
    symbol: str
    quantity: float
    averageCost: float
    currentPrice: float
    marketValue: float
    unrealizedPnl: float
    unrealizedPnlPercent: float
    realizedPnl: float
    assetType: str
    positionType: str
    percentOfPortfolio: float


class PortfolioPerformance(BaseModel):
    """Portfolio performance metrics."""
    period: str  # 1D, 1W, 1M, 3M, 6M, 1Y, YTD, ALL
    start_date: datetime
    end_date: datetime
    starting_value: float
    ending_value: float
    total_return: float
    total_return_pct: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    daily_values: List[Dict[str, Any]]  # Time series data


class AssetAllocation(BaseModel):
    """Portfolio asset allocation breakdown."""
    total_value: float
    by_asset_type: List[Dict[str, Any]]  # type, value, percentage
    by_sector: List[Dict[str, Any]]  # sector, value, percentage
    by_holding: List[Dict[str, Any]]  # symbol, value, percentage
    cash_percentage: float


class TransactionHistory(BaseModel):
    """Portfolio transaction record."""
    transaction_id: str
    date: datetime
    type: str  # BUY, SELL, DIVIDEND, etc.
    symbol: str
    description: str
    quantity: float
    price: float
    amount: float
    fees: float
    net_amount: float
    balance_after: float


class PortfolioMetrics(BaseModel):
    """Portfolio performance metrics."""
    totalValue: float
    totalCost: float
    totalPnl: float
    totalPnlPercent: float
    dailyPnl: float
    dailyPnlPercent: float
    positionsCount: int
    winningPositions: int
    losingPositions: int
    winRate: float
    bestPerformer: Optional[str] = None
    worstPerformer: Optional[str] = None
    largestPosition: Optional[str] = None


class AssetAllocationItem(BaseModel):
    """Asset allocation breakdown item."""
    assetType: str
    value: float
    percentage: float
    count: int


class AccountInfo(BaseModel):
    """Account information for portfolio."""
    accountNumber: str
    accountHash: str
    accountType: str
    cashBalance: float
    totalValue: float
    buyingPower: float
    dayTradingBuyingPower: Optional[float] = None


class PortfolioSummaryResponse(BaseModel):
    """Complete portfolio summary response."""
    accountInfo: AccountInfo
    metrics: PortfolioMetrics
    positions: List[PortfolioPosition]
    assetAllocation: List[AssetAllocationItem]
    lastUpdate: str


class PortfolioHistoryResponse(BaseModel):
    """Portfolio history response."""
    dates: List[str]
    values: List[float]
    returns: List[float]
    cumulative_returns: List[float]