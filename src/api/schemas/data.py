"""Market data schemas."""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from ...data.models import TimeFrame


class CandleResponse(BaseModel):
    """Candle data response."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    
    class Config:
        from_attributes = True


class SymbolInfo(BaseModel):
    """Symbol information."""
    symbol: str
    name: str
    data_start: datetime
    data_end: datetime
    candle_count: int


class MarketDataRequest(BaseModel):
    """Request for fetching market data."""
    symbols: List[str]
    start_date: datetime
    end_date: datetime
    timeframe: TimeFrame = TimeFrame.ONE_MIN


class PriceHistoryResponse(BaseModel):
    """Price history response."""
    symbol: str
    candles: List[CandleResponse]
    period_start: datetime
    period_end: datetime


class RealtimeQuote(BaseModel):
    """Real-time quote data."""
    symbol: str
    last_price: float
    bid_price: float
    ask_price: float
    bid_size: int
    ask_size: int
    volume: int
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    change: float
    change_percent: float
    timestamp: datetime