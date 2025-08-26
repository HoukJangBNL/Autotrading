"""Synchronous data mining service for use in Celery tasks."""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func
from schwab import auth
from schwab.client import Client

from ..data.models import Ticker, Candle, MiningHistory, TickerTier, MiningStatus
from ..data.database import db_service
from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class DataMiningServiceSync:
    """Synchronous data mining service that works with Celery."""
    
    def __init__(self):
        """Initialize the sync data mining service."""
        self.client = None
        self.settings = settings
        
    def initialize(self):
        """Initialize the synchronous Schwab client."""
        if self.client:
            return
            
        try:
            # Use synchronous client
            self.client = auth.client_from_token_file(
                token_path=str(self.settings.schwab.token_file),
                api_key=self.settings.schwab.api_key,
                app_secret=self.settings.schwab.app_secret,
                asyncio=False,  # Use sync client
                enforce_enums=False  # Don't enforce enums
            )
            logger.info("Sync data mining service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize sync client: {e}")
            raise
    
    def mine_ticker_data(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Mine data for a single ticker synchronously."""
        
        logger.info(f"Mining data for {symbol} from {start_date} to {end_date}")
        
        try:
            # Get price history using synchronous client
            response = self.client.get_price_history_every_minute(
                symbol,
                start_datetime=start_date,
                end_datetime=end_date,
                need_extended_hours_data=False,
                need_previous_close=True
            )
            
            data = response.json()
            
            if not data or 'candles' not in data:
                logger.warning(f"No data returned for {symbol}")
                return {
                    "success": False,
                    "error": "No data returned",
                    "candles": []
                }
            
            candles = data['candles']
            logger.info(f"Retrieved {len(candles)} candles for {symbol}")
            
            return {
                "success": True,
                "candles": candles,
                "count": len(candles)
            }
            
        except Exception as e:
            logger.error(f"Failed to mine data for {symbol}: {e}")
            return {
                "success": False,
                "error": str(e),
                "candles": []
            }
    
    def save_candles(
        self,
        session: Session,
        ticker_id: int,
        candles: List[Dict[str, Any]]
    ) -> Tuple[int, int]:
        """Save candles to database synchronously."""
        
        saved = 0
        duplicates = 0
        
        for candle_data in candles:
            try:
                timestamp = datetime.fromtimestamp(candle_data['datetime'] / 1000)
                
                # Check if exists
                existing = session.execute(
                    select(Candle)
                    .where(Candle.ticker_id == ticker_id)
                    .where(Candle.timestamp == timestamp)
                ).scalar_one_or_none()
                
                if existing:
                    duplicates += 1
                    continue
                
                # Create new candle
                candle = Candle(
                    ticker_id=ticker_id,
                    timestamp=timestamp,
                    open=Decimal(str(candle_data['open'])),
                    high=Decimal(str(candle_data['high'])),
                    low=Decimal(str(candle_data['low'])),
                    close=Decimal(str(candle_data['close'])),
                    volume=candle_data['volume']
                )
                
                session.add(candle)
                saved += 1
                
            except Exception as e:
                logger.error(f"Error saving candle: {e}")
                continue
        
        if saved > 0:
            session.commit()
            
        logger.info(f"Saved {saved} candles ({duplicates} duplicates)")
        return saved, duplicates
    
    def get_or_create_ticker(
        self,
        session: Session,
        symbol: str,
        tier: TickerTier = TickerTier.CORE
    ) -> Ticker:
        """Get or create a ticker synchronously."""
        
        ticker = session.execute(
            select(Ticker).where(Ticker.symbol == symbol)
        ).scalar_one_or_none()
        
        if not ticker:
            ticker = Ticker(
                symbol=symbol,
                name=f"{symbol} Inc.",
                tier=tier,
                active=True
            )
            session.add(ticker)
            session.commit()
            logger.info(f"Created ticker {symbol}")
        
        return ticker
    
    def create_mining_history(
        self,
        session: Session,
        ticker_id: int,
        mining_date: date,
        result: Dict[str, Any]
    ) -> MiningHistory:
        """Create mining history record."""
        
        history = MiningHistory(
            ticker_id=ticker_id,
            mining_date=mining_date,
            candles_mined=result.get("count", 0),
            success=result.get("success", False),
            error_message=result.get("error"),
            mining_duration=0  # We could track this if needed
        )
        
        session.add(history)
        session.commit()
        
        return history