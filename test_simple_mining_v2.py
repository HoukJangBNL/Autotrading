#!/usr/bin/env python3
"""Simple test of core mining functionality using schwab-py enums."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from schwab.client import Client
from src.auth import get_authenticated_client
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_schwab_price_history():
    """Test basic Schwab API price history call."""
    
    logger.info("Testing Schwab price history API...")
    
    # Get authenticated client
    client = await get_authenticated_client()
    
    # Test parameters
    symbol = "AAPL"
    
    try:
        # Get price history using schwab-py client methods
        logger.info(f"Fetching 1-minute data for {symbol}")
        
        # Using schwab-py client's get_price_history method
        response = await client.get_price_history(
            symbol,
            period_type=Client.PriceHistory.PeriodType.DAY,
            period=Client.PriceHistory.Period.ONE_DAY,
            frequency_type=Client.PriceHistory.FrequencyType.MINUTE,
            frequency=Client.PriceHistory.Frequency.EVERY_MINUTE,
            need_extended_hours_data=True
        )
        
        data = response.json()
        
        if data and 'candles' in data:
            candles = data['candles']
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
    
    client = await get_authenticated_client()
    symbols = ["AAPL", "MSFT", "GOOGL", "SPY"]
    
    for symbol in symbols:
        try:
            logger.info(f"\nFetching data for {symbol}...")
            
            response = await client.get_price_history(
                symbol,
                period_type=Client.PriceHistory.PeriodType.DAY,
                period=Client.PriceHistory.Period.ONE_DAY,
                frequency_type=Client.PriceHistory.FrequencyType.MINUTE,
                frequency=Client.PriceHistory.Frequency.EVERY_MINUTE
            )
            
            data = response.json()
            
            if data and 'candles' in data:
                logger.info(f"✅ {symbol}: {len(data['candles'])} candles")
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