#!/usr/bin/env python3
"""Simple database test."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.data.database import db_service
from src.data.models import Ticker, Candle, TickerTier, MiningStatus
from sqlalchemy import select, func
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_database():
    """Test database operations."""
    
    logger.info("Testing database operations...")
    
    # Initialize database
    db_service.initialize()
    
    async with db_service.get_async_session() as session:
        # 1. Test ticker operations
        logger.info("\n1. Testing ticker operations...")
        
        # Check existing tickers
        result = await session.execute(
            select(Ticker).order_by(Ticker.symbol)
        )
        existing_tickers = result.scalars().all()
        
        logger.info(f"Found {len(existing_tickers)} existing tickers:")
        for ticker in existing_tickers:
            logger.info(f"   - {ticker.symbol} (tier: {ticker.tier.value}, last_mined: {ticker.last_mined})")
        
        # Add a new ticker if not exists
        test_symbol = "SPY"
        result = await session.execute(
            select(Ticker).where(Ticker.symbol == test_symbol)
        )
        spy_ticker = result.scalar_one_or_none()
        
        if not spy_ticker:
            logger.info(f"\nAdding {test_symbol} to database...")
            spy_ticker = Ticker(
                symbol=test_symbol,
                name="SPDR S&P 500 ETF",
                tier=TickerTier.CORE,
                active=True
            )
            session.add(spy_ticker)
            await session.commit()
            logger.info(f"✅ Added {test_symbol}")
        else:
            logger.info(f"\n{test_symbol} already exists")
        
        # 2. Test candle operations
        logger.info("\n2. Testing candle operations...")
        
        # Check if we have any candles
        result = await session.execute(
            select(func.count(Candle.timestamp)).select_from(Candle)
        )
        candle_count = result.scalar()
        
        logger.info(f"Total candles in database: {candle_count}")
        
        # Get candle count by ticker
        result = await session.execute(
            select(
                Ticker.symbol,
                func.count(Candle.timestamp).label('candle_count')
            )
            .select_from(Ticker)
            .outerjoin(Candle)
            .group_by(Ticker.symbol)
            .order_by(Ticker.symbol)
        )
        
        logger.info("\nCandles per ticker:")
        for symbol, count in result:
            logger.info(f"   - {symbol}: {count} candles")
        
        logger.info("\n✅ Database test completed!")


async def main():
    """Run database test."""
    try:
        await test_database()
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
    finally:
        db_service.close()


if __name__ == "__main__":
    asyncio.run(main())