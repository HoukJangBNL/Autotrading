#!/usr/bin/env python3
"""
Simple test to debug broker initialization issue.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.broker import SchwabBroker
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def test_broker_init():
    """Test broker initialization."""
    print("Testing broker initialization...")
    
    try:
        broker = SchwabBroker()
        print("✓ Broker instance created")
        
        # Try to initialize
        print("Initializing broker...")
        await broker.initialize()
        print("✓ Broker initialized")
        
        # Try to get account numbers
        print("Getting account numbers...")
        accounts = await broker.get_account_numbers()
        print(f"✓ Found {len(accounts)} accounts")
        
        # Cleanup
        await broker.close()
        print("✓ Broker closed")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        logger.exception("Broker init test failed")
        return False


async def main():
    """Run test."""
    success = await test_broker_init()
    if success:
        print("\n✅ Test passed!")
    else:
        print("\n❌ Test failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())