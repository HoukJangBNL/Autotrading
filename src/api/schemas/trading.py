"""Trading operation schemas."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field

from ...strategy.models import OrderSide, OrderType, OrderStatus, TimeInForce


class OrderRequest(BaseModel):
    """Request to place an order."""
    symbol: str
    side: OrderSide
    quantity: int = Field(gt=0)
    order_type: OrderType
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    strategy_name: Optional[str] = None
    signal_id: Optional[str] = None


class OrderResponse(BaseModel):
    """Order details response."""
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce
    status: OrderStatus
    created_at: datetime
    filled_quantity: int
    average_fill_price: float
    commission: float
    filled_time: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    strategy_name: Optional[str] = None
    signal_id: Optional[str] = None


class PositionResponse(BaseModel):
    """Current position details."""
    symbol: str
    quantity: int
    average_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float


class SignalResponse(BaseModel):
    """Trading signal details."""
    signal_id: str
    timestamp: datetime
    symbol: str
    direction: OrderSide
    strength: float  # 0-1
    confidence: float  # 0-1
    strategy_id: str
    strategy_name: str
    reason: str
    position_size: Optional[int] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    executed: bool = False
    order_id: Optional[str] = None


class TradingStatus(BaseModel):
    """Overall trading system status."""
    is_connected: bool
    account_id: str
    cash_balance: float
    buying_power: float
    total_value: float
    active_positions: int
    open_orders: int
    today_trades: int
    active_strategies: int
    last_update: datetime


class ExecutionReport(BaseModel):
    """Trade execution report."""
    execution_id: str
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    commission: float
    executed_at: datetime
    venue: str = "SCHWAB"