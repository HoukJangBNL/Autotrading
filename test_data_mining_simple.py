#!/usr/bin/env python3
"""Simple test for data mining functionality."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.data.database import db_service
from src.broker.schwab_client import get_schwab_broker
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_schwab_api():
    """Test basic Schwab API functionality."""
    
    logger.info("Testing Schwab API connection...")
    
    try:
        # Get broker instance
        broker = await get_schwab_broker()
        
        # Test with just 1 day of data for AAPL
        symbol = "AAPL"
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)
        
        logger.info(f"Fetching 1-minute data for {symbol} from {start_date} to {end_date}")
        
        # Get price history
        history = await broker.get_price_history(
            symbol=symbol,
            period_type="day",
            period=1,
            frequency_type="minute",
            frequency=1,
            need_extended_hours=False,
            need_previous_close=True
        )
        
        if history and "candles" in history:
            candles = history["candles"]
            logger.info(f"✅ Successfully fetched {len(candles)} candles")
            
            # Show first few candles
            for i, candle in enumerate(candles[:5]):
                timestamp = datetime.fromtimestamp(candle["datetime"] / 1000)
                logger.info(f"   {i+1}. {timestamp}: O={candle['open']:.2f}, H={candle['high']:.2f}, L={candle['low']:.2f}, C={candle['close']:.2f}, V={candle['volume']}")
        else:
            logger.error("❌ No data returned from API")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)


async def test_api_endpoints():
    """Test API endpoints using curl."""
    
    logger.info("\nTesting API endpoints...")
    
    # Test health check
    import subprocess
    
    try:
        # Health check
        result = subprocess.run(
            ["curl", "-s", "http://localhost:8000/health"],
            capture_output=True,
            text=True
        )
        logger.info(f"Health check: {result.stdout}")
        
        # Get auth status (will fail without token)
        result = subprocess.run(
            ["curl", "-s", "http://localhost:8000/api/auth/status"],
            capture_output=True,
            text=True
        )
        logger.info(f"Auth status: {result.stdout}")
        
    except Exception as e:
        logger.error(f"API test failed: {e}")


async def main():
    """Run simple tests."""
    logger.info("Starting simple data mining tests...")
    
    try:
        # Test Schwab API
        await test_schwab_api()
        
        # Test API endpoints
        await test_api_endpoints()
        
        logger.info("\n✅ Tests completed!")
        
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())