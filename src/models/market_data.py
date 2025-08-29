"""Market data models for TimescaleDB."""

from sqlalchemy import Column, String, Float, BigInteger, DateTime, Integer, Boolean, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class Candle1Min(Base):
    """1-minute candlestick data."""
    __tablename__ = 'candles_1min'
    
    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(10), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint('symbol', 'timestamp', name='uq_symbol_timestamp'),
        Index('idx_symbol_timestamp', 'symbol', 'timestamp'),
        Index('idx_timestamp', 'timestamp'),
        {'schema': 'public'}
    )


class MiningStatus(Base):
    """Track mining status for each symbol."""
    __tablename__ = 'mining_status'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), unique=True, nullable=False)
    first_date = Column(DateTime(timezone=True))
    last_date = Column(DateTime(timezone=True))
    total_candles = Column(Integer, default=0)
    gaps_detected = Column(Integer, default=0)
    last_update = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    data_quality_score = Column(Float, default=0.0)  # 0-100
    phase = Column(Integer, default=1)  # 1: Core, 2: S&P100, 3: NASDAQ100, 4: Dynamic
    
    __table_args__ = (
        Index('idx_symbol_active', 'symbol', 'is_active'),
        {'schema': 'public'}
    )


class MiningLog(Base):
    """Log mining operations for monitoring."""
    __tablename__ = 'mining_logs'
    
    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(10), nullable=False)
    operation = Column(String(50), nullable=False)  # 'gap_fill', 'update', 'initial'
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True))
    candles_added = Column(Integer, default=0)
    success = Column(Boolean, default=False)
    error_message = Column(String(500))
    api_calls = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_symbol_operation', 'symbol', 'operation'),
        Index('idx_created_at', 'created_at'),
        {'schema': 'public'}
    )