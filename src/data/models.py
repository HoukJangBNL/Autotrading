"""Database models for the trading system."""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column, DateTime, Integer, Text, String, Boolean, 
    BigInteger, Numeric, ForeignKey, Index, UniqueConstraint,
    Enum as SQLEnum, JSON, Date
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


Base = declarative_base()


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AuthToken(Base, TimestampMixin):
    """OAuth token storage."""
    __tablename__ = "auth_tokens"
    
    id = Column(Integer, primary_key=True)
    encrypted_token = Column(Text, nullable=False)
    # created_at and updated_at are provided by TimestampMixin


class TickerTier(str, Enum):
    """Ticker priority tiers."""
    CORE = "core"
    EXPANDED = "expanded"
    DYNAMIC = "dynamic"


class MiningStatus(str, Enum):
    """Mining job status."""
    PENDING = "pending"
    MINING = "mining"
    COMPLETED = "completed"
    FAILED = "failed"


class Ticker(Base, TimestampMixin):
    """Stock ticker information."""
    __tablename__ = "tickers"
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255))
    sector = Column(String(100))
    industry = Column(String(100))
    market_cap = Column(BigInteger)
    tier = Column(SQLEnum(TickerTier), default=TickerTier.EXPANDED)
    active = Column(Boolean, default=True)
    last_mined = Column(DateTime(timezone=True))
    mining_status = Column(SQLEnum(MiningStatus))
    
    # Relationships
    candles = relationship("Candle", back_populates="ticker", cascade="all, delete-orphan")
    mining_history = relationship("MiningHistory", back_populates="ticker", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Ticker(symbol='{self.symbol}', tier='{self.tier}')>"


class Candle(Base):
    """1-minute OHLCV data for time-series storage."""
    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint('ticker_id', 'timestamp', name='_ticker_timestamp_uc'),
        Index('idx_candles_ticker_timestamp', 'ticker_id', 'timestamp'),
        Index('idx_candles_timestamp', 'timestamp'),
    )
    
    # Composite primary key for time-series optimization
    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=False, primary_key=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, primary_key=True)
    
    # OHLCV data
    open = Column(Numeric(10, 4), nullable=False)
    high = Column(Numeric(10, 4), nullable=False)
    low = Column(Numeric(10, 4), nullable=False)
    close = Column(Numeric(10, 4), nullable=False)
    volume = Column(BigInteger, nullable=False)
    
    # Extended hours flag
    extended_hours = Column(Boolean, default=False)
    
    # Relationships
    ticker = relationship("Ticker", back_populates="candles")
    
    def __repr__(self):
        return f"<Candle(ticker_id={self.ticker_id}, timestamp='{self.timestamp}', close={self.close})>"


class MiningHistory(Base, TimestampMixin):
    """Track mining job history and statistics."""
    __tablename__ = "mining_history"
    __table_args__ = (
        UniqueConstraint('ticker_id', 'date', name='_ticker_date_uc'),
        Index('idx_mining_history_date', 'date'),
        Index('idx_mining_history_status', 'status'),
    )
    
    id = Column(Integer, primary_key=True)
    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=False)
    date = Column(Date, nullable=False)
    
    # Mining statistics
    candles_expected = Column(Integer)
    candles_received = Column(Integer)
    gaps_detected = Column(Integer, default=0)
    
    # Status tracking
    status = Column(SQLEnum(MiningStatus), nullable=False, default=MiningStatus.PENDING)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    
    # Performance metrics
    duration_seconds = Column(Integer)
    api_calls = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)
    
    # Relationships
    ticker = relationship("Ticker", back_populates="mining_history")
    
    def __repr__(self):
        return f"<MiningHistory(ticker_id={self.ticker_id}, date='{self.date}', status='{self.status}')>"