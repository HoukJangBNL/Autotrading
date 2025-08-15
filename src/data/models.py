"""Database models for the trading system."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..config.constants import (
    AssetType, OrderAction, OrderStatus, OrderType,
    PositionStatus, TimeInForce, TradingMode
)


Base = declarative_base()


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PriceData(Base, TimestampMixin):
    """Historical and real-time price data."""
    __tablename__ = "price_data"
    
    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(10), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    open = Column(Numeric(10, 2), nullable=False)
    high = Column(Numeric(10, 2), nullable=False)
    low = Column(Numeric(10, 2), nullable=False)
    close = Column(Numeric(10, 2), nullable=False)
    volume = Column(BigInteger, nullable=False)
    vwap = Column(Numeric(10, 2))  # Volume Weighted Average Price
    
    __table_args__ = (
        UniqueConstraint('symbol', 'timestamp'),
        Index('idx_price_data_symbol_timestamp', 'symbol', 'timestamp'),
    )


class Trade(Base, TimestampMixin):
    """Trade execution records."""
    __tablename__ = "trades"
    
    id = Column(BigInteger, primary_key=True)
    order_id = Column(String(50), unique=True, nullable=False)
    symbol = Column(String(10), nullable=False, index=True)
    action = Column(Enum(OrderAction), nullable=False)
    order_type = Column(Enum(OrderType), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2))
    executed_price = Column(Numeric(10, 2))
    executed_at = Column(DateTime(timezone=True), nullable=False)
    commission = Column(Numeric(10, 2), default=0)
    
    # Strategy information
    strategy_id = Column(String(50), nullable=False, index=True)
    signal_confidence = Column(Float)
    
    # Status and results
    status = Column(Enum(OrderStatus), nullable=False, index=True)
    profit_loss = Column(Numeric(10, 2))
    profit_loss_percent = Column(Numeric(5, 2))
    
    # Risk management
    stop_loss = Column(Numeric(10, 2))
    take_profit = Column(Numeric(10, 2))
    
    # Relationships
    position_id = Column(BigInteger, ForeignKey('positions.id'))
    position = relationship("Position", back_populates="trades")


class Position(Base, TimestampMixin):
    """Active and closed positions."""
    __tablename__ = "positions"
    
    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(10), nullable=False, index=True)
    status = Column(Enum(PositionStatus), nullable=False, index=True)
    
    # Entry information
    entry_price = Column(Numeric(10, 2), nullable=False)
    entry_quantity = Column(Integer, nullable=False)
    entry_date = Column(DateTime(timezone=True), nullable=False)
    
    # Current state
    current_quantity = Column(Integer, nullable=False)
    average_price = Column(Numeric(10, 2), nullable=False)
    market_value = Column(Numeric(12, 2))
    
    # Exit information
    exit_price = Column(Numeric(10, 2))
    exit_date = Column(DateTime(timezone=True))
    
    # Performance
    realized_pnl = Column(Numeric(10, 2), default=0)
    unrealized_pnl = Column(Numeric(10, 2), default=0)
    total_pnl = Column(Numeric(10, 2), default=0)
    
    # Risk management
    stop_loss = Column(Numeric(10, 2))
    take_profit = Column(Numeric(10, 2))
    max_loss = Column(Numeric(10, 2))
    
    # Relationships
    trades = relationship("Trade", back_populates="position")


class Strategy(Base, TimestampMixin):
    """Trading strategy configurations."""
    __tablename__ = "strategies"
    
    id = Column(BigInteger, primary_key=True)
    strategy_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    version = Column(String(20), nullable=False)
    active = Column(Boolean, default=True)
    
    # Configuration
    parameters = Column(JSON, nullable=False)
    symbols = Column(JSON)  # List of symbols this strategy trades
    
    # Performance tracking
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    total_pnl = Column(Numeric(12, 2), default=0)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    
    # Relationships
    backtests = relationship("Backtest", back_populates="strategy")


class Backtest(Base, TimestampMixin):
    """Backtest results."""
    __tablename__ = "backtests"
    
    id = Column(BigInteger, primary_key=True)
    strategy_id = Column(BigInteger, ForeignKey('strategies.id'), nullable=False)
    
    # Test configuration
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    initial_capital = Column(Numeric(12, 2), nullable=False)
    parameters = Column(JSON, nullable=False)
    
    # Results
    final_capital = Column(Numeric(12, 2))
    total_return = Column(Float)
    total_trades = Column(Integer)
    winning_trades = Column(Integer)
    win_rate = Column(Float)
    
    # Risk metrics
    sharpe_ratio = Column(Float)
    sortino_ratio = Column(Float)
    max_drawdown = Column(Float)
    var_95 = Column(Float)  # Value at Risk 95%
    
    # Trade statistics
    avg_win = Column(Numeric(10, 2))
    avg_loss = Column(Numeric(10, 2))
    profit_factor = Column(Float)
    
    # Detailed results
    equity_curve = Column(JSON)  # Time series of portfolio value
    trade_history = Column(JSON)  # All trades made during backtest
    
    # Relationships
    strategy = relationship("Strategy", back_populates="backtests")


class AccountSummary(Base, TimestampMixin):
    """Daily account summary."""
    __tablename__ = "account_summary"
    
    id = Column(BigInteger, primary_key=True)
    date = Column(DateTime(timezone=True), unique=True, nullable=False)
    
    # Balances
    starting_balance = Column(Numeric(12, 2), nullable=False)
    ending_balance = Column(Numeric(12, 2), nullable=False)
    cash_balance = Column(Numeric(12, 2), nullable=False)
    market_value = Column(Numeric(12, 2), nullable=False)
    
    # Trading activity
    total_trades = Column(Integer, default=0)
    profitable_trades = Column(Integer, default=0)
    total_volume = Column(Numeric(12, 2), default=0)
    
    # Performance
    daily_pnl = Column(Numeric(10, 2), nullable=False)
    daily_return = Column(Float)
    cumulative_pnl = Column(Numeric(12, 2))
    
    # Risk metrics
    positions_held = Column(Integer, default=0)
    max_position_value = Column(Numeric(12, 2))
    margin_used = Column(Numeric(12, 2))
    
    __table_args__ = (
        Index('idx_account_summary_date', 'date'),
    )


class MarketData(Base, TimestampMixin):
    """Market metadata and statistics."""
    __tablename__ = "market_data"
    
    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(10), unique=True, nullable=False)
    
    # Basic information
    company_name = Column(String(200))
    sector = Column(String(100))
    industry = Column(String(100))
    market_cap = Column(BigInteger)
    
    # Trading statistics
    avg_volume_30d = Column(BigInteger)
    volatility_30d = Column(Float)
    beta = Column(Float)
    
    # Technical indicators
    sma_20 = Column(Numeric(10, 2))
    sma_50 = Column(Numeric(10, 2))
    sma_200 = Column(Numeric(10, 2))
    rsi_14 = Column(Float)
    
    # Last update
    last_updated = Column(DateTime(timezone=True), nullable=False)


class Alert(Base, TimestampMixin):
    """System alerts and notifications."""
    __tablename__ = "alerts"
    
    id = Column(BigInteger, primary_key=True)
    alert_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False)  # INFO, WARNING, ERROR, CRITICAL
    
    # Alert details
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    context = Column(JSON)  # Additional context data
    
    # Status
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime(timezone=True))
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True))
    
    __table_args__ = (
        Index('idx_alerts_type_severity', 'alert_type', 'severity'),
        Index('idx_alerts_acknowledged', 'acknowledged'),
    )