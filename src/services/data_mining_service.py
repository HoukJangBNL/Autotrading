"""Data mining service for historical data collection."""

import json
import asyncio
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Set, Tuple
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..data.database import get_async_db
from ..data.models import Ticker, Candle, MiningHistory, TickerTier, MiningStatus
from ..broker.schwab_client import get_schwab_broker
from ..utils.logger import get_logger

logger = get_logger(__name__)


class DataMiningService:
    """Orchestrates data collection and management."""
    
    def __init__(self):
        self.core_tickers = self._load_core_tickers()
        self.schwab_broker = None
        self.active_jobs = set()
        self.max_daily_tickers = 100
        self.candles_per_day = 390  # Regular market hours: 9:30 AM - 4:00 PM EST
        
    def _load_core_tickers(self) -> List[str]:
        """Load core ticker list from configuration."""
        config_path = Path("config/core_tickers.json")
        
        if not config_path.exists():
            logger.warning("Core tickers config not found, using defaults")
            return ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "SPY", "QQQ"]
        
        try:
            with open(config_path) as f:
                config = json.load(f)
                return config.get("core_tickers", [])
        except Exception as e:
            logger.error(f"Failed to load core tickers: {e}")
            return []
    
    async def initialize(self):
        """Initialize the service."""
        if not self.schwab_broker:
            # Create a new broker instance for each service
            # to avoid event loop conflicts in Celery
            from ..broker.schwab_client import SchwabBroker
            self.schwab_broker = SchwabBroker()
            await self.schwab_broker.initialize()
            logger.info("Data mining service initialized")
    
    async def get_daily_targets(self, session: AsyncSession) -> List[Dict[str, any]]:
        """Get today's mining targets based on priority."""
        targets = []
        
        # 1. Get core tickers
        core_tickers = await self._get_or_create_tickers(
            session, self.core_tickers, TickerTier.CORE
        )
        
        # 2. Prioritize based on last mined date
        for ticker in core_tickers:
            priority = self._calculate_priority(ticker)
            targets.append({
                "ticker": ticker,
                "priority": priority,
                "reason": "core"
            })
        
        # 3. Add expanded tickers if capacity allows
        if len(targets) < self.max_daily_tickers:
            expanded_count = self.max_daily_tickers - len(targets)
            expanded_tickers = await self._get_expanded_tickers(session, expanded_count)
            
            for ticker in expanded_tickers:
                priority = self._calculate_priority(ticker)
                targets.append({
                    "ticker": ticker,
                    "priority": priority,
                    "reason": "expanded"
                })
        
        # Sort by priority
        targets.sort(key=lambda x: x["priority"], reverse=True)
        
        return targets[:self.max_daily_tickers]
    
    async def _get_or_create_tickers(
        self,
        session: AsyncSession,
        symbols: List[str],
        tier: TickerTier
    ) -> List[Ticker]:
        """Get existing tickers or create new ones."""
        tickers = []
        
        for symbol in symbols:
            # Check if ticker exists
            result = await session.execute(
                select(Ticker).where(Ticker.symbol == symbol)
            )
            ticker = result.scalar_one_or_none()
            
            if not ticker:
                # Create new ticker
                ticker = Ticker(
                    symbol=symbol,
                    tier=tier,
                    active=True
                )
                session.add(ticker)
                await session.flush()
            else:
                # Update tier if needed
                if ticker.tier != tier and tier == TickerTier.CORE:
                    ticker.tier = tier
            
            tickers.append(ticker)
        
        await session.commit()
        return tickers
    
    def _calculate_priority(self, ticker: Ticker) -> float:
        """Calculate mining priority for a ticker."""
        priority = 0.0
        
        # Core tickers get highest priority
        if ticker.tier == TickerTier.CORE:
            priority += 100.0
        
        # Tickers never mined get high priority
        if not ticker.last_mined:
            priority += 50.0
        else:
            # Priority decreases with recency
            days_since_mined = (datetime.now() - ticker.last_mined).days
            priority += min(days_since_mined * 2, 30)
        
        # Failed tickers get lower priority
        if ticker.mining_status == MiningStatus.FAILED:
            priority -= 20.0
        
        return priority
    
    async def _get_expanded_tickers(
        self,
        session: AsyncSession,
        limit: int
    ) -> List[Ticker]:
        """Get expanded tickers for mining."""
        result = await session.execute(
            select(Ticker)
            .where(Ticker.tier == TickerTier.EXPANDED)
            .where(Ticker.active == True)
            .order_by(Ticker.last_mined.asc().nullsfirst())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def mine_ticker_data(
        self,
        ticker: Ticker,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, any]:
        """Mine historical data for a single ticker."""
        if not self.schwab_broker:
            await self.initialize()
        
        # Default to last 60 days
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=60)
        
        logger.info(f"Mining data for {ticker.symbol} from {start_date} to {end_date}")
        
        try:
            # Get price history from Schwab
            history = await self.schwab_broker.get_price_history(
                symbol=ticker.symbol,
                period_type="month",
                period=2,
                frequency_type="minute",
                frequency=1,
                start_date=start_date,
                end_date=end_date,
                need_extended_hours=False,
                need_previous_close=True
            )
            
            # Process and return results
            candles = history.get("candles", [])
            logger.info(f"Retrieved {len(candles)} candles for {ticker.symbol}")
            
            return {
                "success": True,
                "ticker_id": ticker.id,
                "symbol": ticker.symbol,
                "candles": candles,
                "count": len(candles),
                "start_date": start_date,
                "end_date": end_date
            }
            
        except Exception as e:
            logger.error(f"Failed to mine data for {ticker.symbol}: {e}")
            return {
                "success": False,
                "ticker_id": ticker.id,
                "symbol": ticker.symbol,
                "error": str(e),
                "start_date": start_date,
                "end_date": end_date
            }
    
    async def save_candles(
        self,
        session: AsyncSession,
        ticker_id: int,
        candles_data: List[Dict]
    ) -> Tuple[int, int]:
        """Save candles to database, handling duplicates."""
        saved_count = 0
        duplicate_count = 0
        
        for candle_data in candles_data:
            # Convert timestamp from milliseconds
            timestamp = datetime.fromtimestamp(candle_data["datetime"] / 1000)
            
            # Check if candle already exists
            result = await session.execute(
                select(Candle)
                .where(Candle.ticker_id == ticker_id)
                .where(Candle.timestamp == timestamp)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                duplicate_count += 1
                continue
            
            # Create new candle
            candle = Candle(
                ticker_id=ticker_id,
                timestamp=timestamp,
                open=candle_data["open"],
                high=candle_data["high"],
                low=candle_data["low"],
                close=candle_data["close"],
                volume=candle_data["volume"]
            )
            session.add(candle)
            saved_count += 1
        
        if saved_count > 0:
            await session.commit()
        
        return saved_count, duplicate_count
    
    async def create_mining_history(
        self,
        session: AsyncSession,
        ticker_id: int,
        mining_date: date,
        result: Dict[str, any]
    ) -> MiningHistory:
        """Create mining history record."""
        history = MiningHistory(
            ticker_id=ticker_id,
            date=mining_date,
            status=MiningStatus.COMPLETED if result["success"] else MiningStatus.FAILED,
            started_at=result.get("start_time", datetime.now()),
            completed_at=datetime.now(),
            candles_expected=self._calculate_expected_candles(
                result.get("start_date"),
                result.get("end_date")
            ),
            candles_received=result.get("count", 0),
            error_message=result.get("error"),
            api_calls=1,
            retry_count=result.get("retry_count", 0)
        )
        
        # Calculate duration
        if history.started_at:
            history.duration_seconds = int(
                (history.completed_at - history.started_at).total_seconds()
            )
        
        session.add(history)
        await session.commit()
        
        return history
    
    def _calculate_expected_candles(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> int:
        """Calculate expected number of candles between dates."""
        if not start_date or not end_date:
            return 0
        
        # Count trading days (roughly)
        total_days = (end_date - start_date).days
        # Approximate: 5 trading days per week
        trading_days = int(total_days * 5 / 7)
        
        return trading_days * self.candles_per_day
    
    async def check_data_gaps(
        self,
        session: AsyncSession,
        ticker_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[Tuple[datetime, datetime]]:
        """Find gaps in candle data."""
        gaps = []
        
        # Get all candles in date range
        result = await session.execute(
            select(Candle.timestamp)
            .where(Candle.ticker_id == ticker_id)
            .where(Candle.timestamp >= start_date)
            .where(Candle.timestamp <= end_date)
            .order_by(Candle.timestamp)
        )
        timestamps = [row[0] for row in result]
        
        if not timestamps:
            return [(start_date, end_date)]
        
        # Check for gaps larger than 1 minute during market hours
        for i in range(1, len(timestamps)):
            prev_ts = timestamps[i-1]
            curr_ts = timestamps[i]
            
            # Skip if different days
            if prev_ts.date() != curr_ts.date():
                continue
            
            # Check if gap is during market hours
            if self._is_market_hours(prev_ts) and self._is_market_hours(curr_ts):
                gap_minutes = (curr_ts - prev_ts).total_seconds() / 60
                
                if gap_minutes > 1.5:  # Allow small tolerance
                    gaps.append((prev_ts + timedelta(minutes=1), curr_ts))
        
        return gaps
    
    def _is_market_hours(self, dt: datetime) -> bool:
        """Check if datetime is during regular market hours."""
        # Regular market hours: 9:30 AM - 4:00 PM EST
        market_open = dt.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = dt.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= dt <= market_close
    
    async def get_mining_status(self, session: AsyncSession) -> Dict[str, any]:
        """Get current mining status and statistics."""
        # Count tickers by status
        status_counts = await session.execute(
            select(
                Ticker.mining_status,
                func.count(Ticker.id)
            ).group_by(Ticker.mining_status)
        )
        
        status_dict = {
            status.value if status else "none": count
            for status, count in status_counts
        }
        
        # Get today's mining progress
        today = date.today()
        today_history = await session.execute(
            select(MiningHistory)
            .where(MiningHistory.date == today)
            .options(selectinload(MiningHistory.ticker))
        )
        
        today_records = today_history.scalars().all()
        
        return {
            "ticker_status": status_dict,
            "today": {
                "completed": len([h for h in today_records if h.status == MiningStatus.COMPLETED]),
                "failed": len([h for h in today_records if h.status == MiningStatus.FAILED]),
                "pending": len(self.active_jobs),
                "tickers": [
                    {
                        "symbol": h.ticker.symbol,
                        "status": h.status.value,
                        "candles": h.candles_received,
                        "duration": h.duration_seconds
                    }
                    for h in today_records
                ]
            },
            "active_jobs": list(self.active_jobs)
        }
    
    async def cleanup_old_data(
        self,
        session: AsyncSession,
        days_to_keep: int = 90
    ) -> int:
        """Clean up old candle data."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        # Delete old candles
        result = await session.execute(
            select(Candle).where(Candle.timestamp < cutoff_date)
        )
        old_candles = result.scalars().all()
        
        for candle in old_candles:
            await session.delete(candle)
        
        await session.commit()
        
        logger.info(f"Cleaned up {len(old_candles)} old candles")
        return len(old_candles)