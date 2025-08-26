#!/usr/bin/env python3
"""Test script for data mining functionality."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.data.database import db_service
from src.services.data_mining_service import DataMiningService
from src.data.models import Ticker, TickerTier
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_data_mining():
    """Test the data mining service with a few tickers."""
    
    # Initialize database
    db_service.initialize()
    
    # Create service
    service = DataMiningService()
    await service.initialize()
    
    async with db_service.get_async_session() as session:
        # Create or get test tickers
        test_symbols = ["AAPL", "MSFT", "GOOGL"]
        tickers = await service._get_or_create_tickers(
            session, test_symbols, TickerTier.CORE
        )
        
        logger.info(f"Testing with {len(tickers)} tickers: {[t.symbol for t in tickers]}")
        
        # Test mining for each ticker (just 1 day for testing)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)
        
        for ticker in tickers:
            logger.info(f"\nTesting data mining for {ticker.symbol}...")
            
            # Mine data
            result = await service.mine_ticker_data(
                ticker, start_date, end_date
            )
            
            if result["success"]:
                logger.info(f"✅ Successfully mined {result['count']} candles")
                
                # Save candles
                saved, duplicates = await service.save_candles(
                    session, ticker.id, result["candles"]
                )
                logger.info(f"   Saved {saved} new candles ({duplicates} duplicates)")
                
                # Create mining history
                await service.create_mining_history(
                    session, ticker.id, datetime.today().date(), result
                )
                
                # Update ticker status
                ticker.last_mined = datetime.now()
                from src.data.models import MiningStatus
                ticker.mining_status = MiningStatus.COMPLETED
                await session.commit()
            else:
                logger.error(f"❌ Failed to mine data: {result.get('error')}")
        
        # Test gap detection
        logger.info("\nTesting gap detection...")
        for ticker in tickers[:1]:  # Just test with first ticker
            gaps = await service.check_data_gaps(
                session, ticker.id, start_date, end_date
            )
            logger.info(f"Found {len(gaps)} gaps for {ticker.symbol}")
        
        # Test mining status
        logger.info("\nGetting mining status...")
        status = await service.get_mining_status(session)
        logger.info(f"Mining status: {status}")


async def test_celery_tasks():
    """Test Celery tasks."""
    from src.tasks.data_mining import mine_ticker_data, start_daily_mining
    
    logger.info("\nTesting Celery tasks...")
    
    # Test single ticker mining
    result = mine_ticker_data.delay("AAPL", datetime.today().isoformat())
    logger.info(f"Submitted mining task: {result.id}")
    
    # Wait for result (with timeout)
    try:
        task_result = result.get(timeout=30)
        logger.info(f"Task result: {task_result}")
    except Exception as e:
        logger.error(f"Task failed: {e}")
    
    # Test daily mining
    daily_result = start_daily_mining.delay()
    logger.info(f"Submitted daily mining task: {daily_result.id}")
    
    try:
        daily_task_result = daily_result.get(timeout=10)
        logger.info(f"Daily mining result: {daily_task_result}")
    except Exception as e:
        logger.error(f"Daily mining task failed: {e}")


async def main():
    """Run all tests."""
    logger.info("Starting data mining tests...")
    
    try:
        # Test data mining service
        await test_data_mining()
        
        # Test Celery tasks (optional - requires Celery worker running)
        # await test_celery_tasks()
        
        logger.info("\n✅ All tests completed!")
        
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
    finally:
        # Cleanup
        db_service.close()


if __name__ == "__main__":
    asyncio.run(main())