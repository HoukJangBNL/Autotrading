#!/usr/bin/env python3
"""Test data mining with synchronous approach."""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import time

sys.path.insert(0, str(Path(__file__).parent))

from src.broker import get_schwab_broker_sync
from src.data.database import db_service
from src.data.models import Ticker, Candle, TickerTier, MiningStatus
from sqlalchemy import select, func
from src.utils.logger import get_logger

logger = get_logger(__name__)


def test_sync_mining():
    """Test synchronous data mining."""
    
    logger.info("Testing synchronous data mining...")
    
    # Initialize database
    db_service.initialize()
    
    # Get sync broker
    broker = get_schwab_broker_sync()
    
    # Test parameters
    symbol = "AAPL"
    yesterday = datetime.now().date() - timedelta(days=1)
    start_date = datetime.combine(yesterday, datetime.min.time())
    end_date = datetime.combine(yesterday, datetime.max.time())
    
    logger.info(f"Fetching data for {symbol} from {start_date} to {end_date}")
    
    try:
        # Get price history - pass datetime objects
        history = broker.get_price_history_sync(
            symbol=symbol,
            period_type="day",
            period=1,
            frequency_type="minute",
            frequency=1,
            start_date=start_date,
            end_date=end_date
        )
        
        if history and 'candles' in history:
            candles = history['candles']
            logger.info(f"✅ Received {len(candles)} candles")
            
            # Save to database
            with db_service.get_sync_session() as session:
                # Get or create ticker
                ticker = session.execute(
                    select(Ticker).where(Ticker.symbol == symbol)
                ).scalar_one_or_none()
                
                if not ticker:
                    ticker = Ticker(
                        symbol=symbol,
                        name=f"{symbol} Inc.",
                        tier=TickerTier.CORE,
                        active=True
                    )
                    session.add(ticker)
                    session.commit()
                    logger.info(f"Created ticker {symbol}")
                
                # Save candles
                saved = 0
                for candle_data in candles:
                    timestamp = datetime.fromtimestamp(candle_data['datetime'] / 1000)
                    
                    # Check if exists
                    existing = session.execute(
                        select(Candle)
                        .where(Candle.ticker_id == ticker.id)
                        .where(Candle.timestamp == timestamp)
                    ).scalar_one_or_none()
                    
                    if not existing:
                        candle = Candle(
                            ticker_id=ticker.id,
                            timestamp=timestamp,
                            open=candle_data['open'],
                            high=candle_data['high'],
                            low=candle_data['low'],
                            close=candle_data['close'],
                            volume=candle_data['volume']
                        )
                        session.add(candle)
                        saved += 1
                
                # Update ticker status
                ticker.last_mined = datetime.now()
                ticker.mining_status = MiningStatus.COMPLETED
                
                session.commit()
                logger.info(f"✅ Saved {saved} candles to database")
                
                # Verify
                count = session.execute(
                    select(func.count(Candle.timestamp))
                    .where(Candle.ticker_id == ticker.id)
                ).scalar()
                
                logger.info(f"Total candles for {symbol}: {count}")
                
        else:
            logger.error("❌ No candles received")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_sync_mining()