"""Account management schemas."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel


class AccountListResponse(BaseModel):
    """List of linked accounts."""
    accounts: List[Dict[str, str]]
    count: int


class AccountInfoResponse(BaseModel):
    """Basic account information."""
    accountNumber: str
    accountHash: str
    accountType: str
    lastUpdate: str


class AccountBalanceResponse(BaseModel):
    """Account balance details."""
    accountNumber: str
    accountHash: str
    accountType: str
    cashBalance: float
    totalValue: float
    buyingPower: float
    marginBalance: Optional[float] = None
    shortBalance: Optional[float] = None
    cashAvailableForWithdrawal: Optional[float] = None
    cashAvailableForTrading: Optional[float] = None
    maintenanceRequirement: Optional[float] = None
    dayTradingBuyingPower: Optional[float] = None
    lastUpdate: str


class PositionResponse(BaseModel):
    """Individual position details."""
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


class QuoteResponse(BaseModel):
    """Real-time quote data."""
    symbol: str
    lastPrice: float
    bidPrice: float
    askPrice: float
    bidSize: int
    askSize: int
    volume: int
    openPrice: float
    highPrice: float
    lowPrice: float
    closePrice: float
    changeValue: float
    changePercent: float
    timestamp: str