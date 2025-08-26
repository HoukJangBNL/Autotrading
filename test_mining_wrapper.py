#!/usr/bin/env python3
"""Test data mining using our broker wrapper."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from src.broker import get_schwab_broker
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_broker_wrapper():
    """Test the broker wrapper get_price_history method."""
    
    logger.info("Testing broker wrapper...")
    
    # Get authenticated broker
    broker = await get_schwab_broker()
    
    # Test AAPL
    symbol = "AAPL"
    
    try:
        logger.info(f"\nFetching data for {symbol}...")
        
        # Use our wrapper method which handles enum conversion
        history = await broker.get_price_history(
            symbol=symbol,
            period_type="day",
            period=1,
            frequency_type="minute",
            frequency=1
        )
        
        if history and 'candles' in history:
            candles = history['candles']
            logger.info(f"✅ Received {len(candles)} candles")
            
            # Show sample data
            if candles:
                first = candles[0]
                logger.info(f"First candle: timestamp={first.get('datetime')} open={first.get('open')} close={first.get('close')} volume={first.get('volume')}")
                
                # Count zero volume candles
                zero_vol = sum(1 for c in candles if c.get('volume', 0) == 0)
                logger.info(f"Zero volume candles: {zero_vol}/{len(candles)}")
        else:
            logger.error("❌ No candles received")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run test."""
    await test_broker_wrapper()


if __name__ == "__main__":
    asyncio.run(main())