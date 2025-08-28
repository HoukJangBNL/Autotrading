"""API schemas package."""

from .auth import AuthUrlResponse, TokenResponse, AuthStatus
from .data import (
    CandleResponse, SymbolInfo, MarketDataRequest, 
    PriceHistoryResponse, RealtimeQuote
)
from .strategy import (
    StrategyCreate, StrategyUpdate, StrategyResponse,
    StrategyListResponse, StrategyPerformance
)
from .backtest import (
    BacktestRequest, BacktestResponse, BacktestStatus,
    BacktestResultResponse
)
from .trading import (
    OrderRequest, OrderResponse, PositionResponse,
    SignalResponse, TradingStatus, ExecutionReport
)
from .portfolio import (
    PortfolioSummary, PortfolioPosition, PortfolioPerformance,
    AssetAllocation, TransactionHistory
)

__all__ = [
    # Auth schemas
    "AuthUrlResponse", "TokenResponse", "AuthStatus",
    
    # Data schemas
    "CandleResponse", "SymbolInfo", "MarketDataRequest", 
    "PriceHistoryResponse", "RealtimeQuote",
    
    # Strategy schemas
    "StrategyCreate", "StrategyUpdate", "StrategyResponse",
    "StrategyListResponse", "StrategyPerformance",
    
    # Backtest schemas
    "BacktestRequest", "BacktestResponse", "BacktestStatus",
    "BacktestResultResponse",
    
    # Trading schemas
    "OrderRequest", "OrderResponse", "PositionResponse",
    "SignalResponse", "TradingStatus", "ExecutionReport",
    
    # Portfolio schemas
    "PortfolioSummary", "PortfolioPosition", "PortfolioPerformance",
    "AssetAllocation", "TransactionHistory"
]