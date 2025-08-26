#!/usr/bin/env python3
"""Simple test of core mining functionality."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from src.auth import get_authenticated_client
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_schwab_price_history():
    """Test basic Schwab API price history call."""
    
    logger.info("Testing Schwab price history API...")
    
    # Get authenticated broker
    broker = await get_authenticated_client()
    
    # Test parameters
    symbol = "AAPL"
    yesterday = datetime.now().date() - timedelta(days=1)
    
    try:
        # Get price history
        logger.info(f"Fetching 1-minute data for {symbol} on {yesterday}")
        
        history = await broker.get_price_history(
            symbol=symbol,
            period_type="day",
            period=1,
            frequency_type="minute", 
            frequency=1,
            need_extended_hours=True
        )
        
        if history and 'candles' in history:
            candles = history['candles']
            logger.info(f"✅ Received {len(candles)} candles")
            
            # Show first and last candle
            if candles:
                first = candles[0]
                last = candles[-1]
                
                logger.info(f"First candle: {datetime.fromtimestamp(first['datetime']/1000)} - O:{first['open']} H:{first['high']} L:{first['low']} C:{first['close']} V:{first['volume']}")
                logger.info(f"Last candle: {datetime.fromtimestamp(last['datetime']/1000)} - O:{last['open']} H:{last['high']} L:{last['low']} C:{last['close']} V:{last['volume']}")
                
                # Check data quality
                zero_volume = sum(1 for c in candles if c['volume'] == 0)
                logger.info(f"Zero volume candles: {zero_volume}/{len(candles)}")
                
        else:
            logger.error("❌ No candles received")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        

async def test_multiple_symbols():
    """Test fetching data for multiple symbols."""
    
    logger.info("\n\nTesting multiple symbols...")
    
    broker = await get_authenticated_client()
    symbols = ["AAPL", "MSFT", "GOOGL", "SPY"]
    
    for symbol in symbols:
        try:
            logger.info(f"\nFetching data for {symbol}...")
            
            history = await broker.get_price_history(
                symbol=symbol,
                period_type="day",
                period=1,
                frequency_type="minute",
                frequency=1
            )
            
            if history and 'candles' in history:
                logger.info(f"✅ {symbol}: {len(history['candles'])} candles")
            else:
                logger.error(f"❌ {symbol}: No data")
                
        except Exception as e:
            logger.error(f"❌ {symbol}: Error - {e}")
            

async def main():
    """Run tests."""
    await test_schwab_price_history()
    await test_multiple_symbols()


if __name__ == "__main__":
    asyncio.run(main())