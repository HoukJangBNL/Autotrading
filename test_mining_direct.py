#!/usr/bin/env python3
"""Direct test of data mining without status checking."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from src.services.data_mining_service import DataMiningService
from src.data.database import db_service
from src.data.models import Ticker, TickerTier, MiningStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_direct_mining():
    """Test mining directly without Celery."""
    
    logger.info("Starting direct data mining test...")
    
    # Initialize services
    db_service.initialize()
    service = DataMiningService()
    await service.initialize()
    
    async with db_service.get_async_session() as session:
        # Get tickers
        tickers = await service._get_or_create_tickers(
            session, ["AAPL", "MSFT"], TickerTier.CORE
        )
        
        # Mine yesterday's data
        yesterday = datetime.now().date() - timedelta(days=1)
        start_date = datetime.combine(yesterday, datetime.min.time())
        end_date = datetime.combine(yesterday, datetime.max.time())
        
        logger.info(f"Mining data from {start_date} to {end_date}")
        
        for ticker in tickers:
            logger.info(f"\nMining {ticker.symbol}...")
            
            try:
                # Mine data
                result = await service.mine_ticker_data(ticker, start_date, end_date)
                
                if result["success"]:
                    logger.info(f"✅ Fetched {len(result['candles'])} candles")
                    
                    # Save candles
                    saved, duplicates = await service.save_candles(
                        session, ticker.id, result["candles"]
                    )
                    
                    logger.info(f"✅ Saved {saved} candles ({duplicates} duplicates)")
                    
                    # Update ticker status
                    ticker.last_mined = datetime.now()
                    ticker.mining_status = MiningStatus.COMPLETED
                    
                    await session.commit()
                    
                else:
                    logger.error(f"❌ Mining failed: {result.get('error')}")
                    
            except Exception as e:
                logger.error(f"❌ Error mining {ticker.symbol}: {e}")
                await session.rollback()
        
        # Check results
        logger.info("\n📊 Checking saved data...")
        
        from sqlalchemy import select, func
        from src.data.models import Candle
        
        for ticker in tickers:
            result = await session.execute(
                select(func.count(Candle.timestamp))
                .where(Candle.ticker_id == ticker.id)
                .where(Candle.timestamp >= start_date)
                .where(Candle.timestamp <= end_date)
            )
            count = result.scalar()
            
            logger.info(f"{ticker.symbol}: {count} candles for {yesterday}")
    
    logger.info("\n✅ Direct mining test completed!")


async def main():
    """Run the test."""
    try:
        await test_direct_mining()
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
    finally:
        db_service.close()
        

if __name__ == "__main__":
    asyncio.run(main())