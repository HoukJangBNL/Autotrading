"""Test script for the data mining system."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))

from src.services.mining_orchestrator_full import FullMarketMiningOrchestrator
from src.broker.schwab_client import SchwabBroker
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_mining_system():
    """Test the mining system with a small subset of symbols."""
    
    # Initialize broker
    logger.info("Initializing Schwab broker...")
    broker = SchwabBroker()
    await broker.initialize()
    
    # Create orchestrator
    logger.info("Creating mining orchestrator...")
    orchestrator = FullMarketMiningOrchestrator(broker.client)
    
    # Test 1: Check symbol loading
    logger.info(f"Total symbols loaded: {len(orchestrator.all_symbols)}")
    logger.info(f"Popular symbols loaded: {len(orchestrator.popular_symbols)}")
    
    # Test 2: Test gap detection with a single symbol
    test_symbol = "AAPL"
    logger.info(f"\nTesting gap detection for {test_symbol}...")
    gaps = await orchestrator.gap_filler.detect_gaps(test_symbol, days_back=30)
    logger.info(f"Gaps found: {len(gaps)}")
    for gap in gaps[:3]:  # Show first 3 gaps
        logger.info(f"  Gap: {gap['type']} from {gap['start']} to {gap['end']}")
    
    # Test 3: Test failed symbol tracking
    logger.info("\nTesting failed symbol tracking...")
    orchestrator.failed_tracker.add_failure("TEST1", "Test error 1")
    orchestrator.failed_tracker.add_failure("TEST1", "Test error 2")
    orchestrator.failed_tracker.add_failure("TEST1", "Test error 3")  # Should be permanent now
    logger.info(f"TEST1 is permanently failed: {orchestrator.failed_tracker.is_permanently_failed('TEST1')}")
    
    # Test 4: Test small mining batch
    logger.info("\nTesting small mining batch...")
    test_symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
    
    # Start mining in background
    mining_task = asyncio.create_task(
        orchestrator.start_mining(
            mode="new_only",
            days_back=5,  # Just 5 days for testing
            batch_size=2,
            concurrent_limit=2
        )
    )
    
    # Monitor progress for 30 seconds
    for _ in range(6):
        await asyncio.sleep(5)
        status = orchestrator.get_status()
        logger.info(f"Progress: {status['progress']['processed']}/{status['progress']['total_symbols']} symbols")
        logger.info(f"  Successful: {status['progress']['successful']}")
        logger.info(f"  Failed: {status['progress']['failed']}")
        logger.info(f"  Candles collected: {status['progress']['candles_collected']}")
        
        # Stop after processing a few symbols
        if status['progress']['processed'] >= 5:
            break
    
    # Stop mining
    logger.info("\nStopping mining...")
    await orchestrator.stop_mining()
    mining_task.cancel()
    
    # Get final report
    final_status = orchestrator.get_status()
    logger.info("\nFinal Status:")
    logger.info(f"  Total processed: {final_status['progress']['processed']}")
    logger.info(f"  Successful: {final_status['progress']['successful']}")
    logger.info(f"  Failed: {final_status['progress']['failed']}")
    logger.info(f"  Candles collected: {final_status['progress']['candles_collected']}")
    logger.info(f"  Performance: {final_status['performance']['symbols_per_minute']:.2f} symbols/min")
    
    # Cleanup
    await broker.close()
    logger.info("\nTest completed successfully!")


async def test_api_endpoints():
    """Test the API endpoints."""
    import aiohttp
    
    base_url = "http://localhost:8000/api/mining"
    
    async with aiohttp.ClientSession() as session:
        # Test status endpoint
        async with session.get(f"{base_url}/status") as resp:
            if resp.status == 200:
                data = await resp.json()
                logger.info(f"Status endpoint OK: {data}")
            else:
                logger.error(f"Status endpoint failed: {resp.status}")
        
        # Test statistics endpoint
        async with session.get(f"{base_url}/statistics") as resp:
            if resp.status == 200:
                data = await resp.json()
                logger.info(f"Statistics endpoint OK: {data.get('database_stats')}")
            else:
                logger.error(f"Statistics endpoint failed: {resp.status}")
        
        # Test failed symbols endpoint
        async with session.get(f"{base_url}/failed-symbols") as resp:
            if resp.status == 200:
                data = await resp.json()
                logger.info(f"Failed symbols endpoint OK: {data.get('total_failed')} failed")
            else:
                logger.error(f"Failed symbols endpoint failed: {resp.status}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test mining system")
    parser.add_argument("--test", choices=["system", "api", "both"], default="system",
                        help="Which test to run")
    args = parser.parse_args()
    
    if args.test in ["system", "both"]:
        logger.info("=" * 50)
        logger.info("Testing Mining System")
        logger.info("=" * 50)
        asyncio.run(test_mining_system())
    
    if args.test in ["api", "both"]:
        logger.info("=" * 50)
        logger.info("Testing API Endpoints")
        logger.info("=" * 50)
        asyncio.run(test_api_endpoints())