#!/usr/bin/env python3
"""Direct API test without Celery."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.broker.schwab_client import get_schwab_broker
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_direct_api():
    """Test Schwab API directly."""
    
    logger.info("Testing Schwab API directly...")
    
    try:
        # Get broker instance
        broker = await get_schwab_broker()
        
        # Test with AAPL
        symbol = "AAPL"
        
        # Get 1 hour of data
        logger.info(f"\nFetching 1-minute data for {symbol}...")
        
        history = await broker.get_price_history(
            symbol=symbol,
            period_type="day",
            period=1,
            frequency_type="minute",
            frequency=1,
            need_extended_hours=False
        )
        
        if history and "candles" in history:
            candles = history["candles"]
            logger.info(f"✅ Successfully fetched {len(candles)} candles")
            
            # Show summary
            if candles:
                first_candle = candles[0]
                last_candle = candles[-1]
                
                first_time = datetime.fromtimestamp(first_candle["datetime"] / 1000)
                last_time = datetime.fromtimestamp(last_candle["datetime"] / 1000)
                
                logger.info(f"\nData range: {first_time} to {last_time}")
                logger.info(f"First candle: O={first_candle['open']:.2f}, H={first_candle['high']:.2f}, L={first_candle['low']:.2f}, C={first_candle['close']:.2f}")
                logger.info(f"Last candle: O={last_candle['open']:.2f}, H={last_candle['high']:.2f}, L={last_candle['low']:.2f}, C={last_candle['close']:.2f}")
                
                # Calculate some stats
                volumes = [c["volume"] for c in candles]
                prices = [c["close"] for c in candles]
                
                logger.info(f"\nStats:")
                logger.info(f"Total volume: {sum(volumes):,}")
                logger.info(f"Avg volume per minute: {sum(volumes) / len(volumes):,.0f}")
                logger.info(f"Price range: ${min(prices):.2f} - ${max(prices):.2f}")
                
        else:
            logger.error("❌ No data returned")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)


async def main():
    """Run direct API test."""
    await test_direct_api()


if __name__ == "__main__":
    asyncio.run(main())