#!/usr/bin/env python3
"""
Retry failed symbols from mining operation
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.api.routers.auth import get_schwab_auth
from src.data.historical_data_collector_v2 import EnhancedHistoricalDataCollector
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Failed symbols to retry
FAILED_SYMBOLS = ['BRK.B', 'PYPL', 'GOOGL', 'META', 'AAPL']

async def retry_failed_symbols():
    """Retry collecting data for failed symbols."""
    
    # Get authenticated client
    schwab_auth = get_schwab_auth()
    client = schwab_auth.get_client()
    
    if not client:
        logger.error("Failed to get authenticated client")
        return
    
    # Create collector with reduced workers
    collector = EnhancedHistoricalDataCollector(client, max_workers=1)  # Single worker to avoid connection issues
    
    logger.info(f"Retrying {len(FAILED_SYMBOLS)} failed symbols...")
    
    results = []
    for symbol in FAILED_SYMBOLS:
        logger.info(f"Retrying {symbol}...")
        try:
            result = collector._collect_symbol_data(symbol, days_back=60, operation="retry")
            results.append(result)
            
            if result['success']:
                logger.info(f"✅ {symbol}: Successfully collected {result.get('candles_count', 0)} candles")
            else:
                logger.error(f"❌ {symbol}: Failed - {result.get('error', 'Unknown error')}")
                
            # Add delay between symbols to avoid rate limiting
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"❌ {symbol}: Exception - {e}")
            results.append({
                'symbol': symbol,
                'success': False,
                'error': str(e)
            })
    
    # Print summary
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    
    logger.info("=" * 50)
    logger.info(f"Retry Summary:")
    logger.info(f"  Total: {len(results)}")
    logger.info(f"  Success: {successful}")
    logger.info(f"  Failed: {failed}")
    
    # Cleanup
    collector.cleanup()
    
    return results

if __name__ == "__main__":
    asyncio.run(retry_failed_symbols())