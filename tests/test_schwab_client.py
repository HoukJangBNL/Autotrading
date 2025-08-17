#!/usr/bin/env python3
"""
Test schwab-py client to understand its behavior.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.auth import get_auth_service
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def test_client_methods():
    """Test client methods to see if they're async."""
    print("Testing schwab-py client methods...")
    
    try:
        # Get auth service
        auth = get_auth_service()
        await auth.initialize()
        print("✓ Auth service initialized")
        
        # Get client
        client = auth.get_client()
        print(f"✓ Got client: {type(client)}")
        
        # Check available methods
        print(f"\nAvailable client methods:")
        methods = [m for m in dir(client) if not m.startswith('_')]
        for method in sorted(methods)[:10]:  # Show first 10
            print(f"  - {method}")
        
        # Look for account-related methods
        print("\nAccount-related methods:")
        account_methods = [m for m in methods if 'account' in m.lower()]
        for method in account_methods:
            print(f"  - {method}")
            
        # Look for price history methods
        print("\nPrice history methods:")
        price_methods = [m for m in methods if 'price' in m.lower() or 'history' in m.lower()]
        for method in price_methods:
            print(f"  - {method}")
        
        # Try to get account numbers
        if hasattr(client, 'get_account_numbers'):
            print("\nTrying client.get_account_numbers()...")
            response = await client.get_account_numbers()
            print(f"✓ Got response: {type(response)}")
            print(f"  Status code: {response.status_code}")
            
            # Try without .json() first
            print(f"  Response text: {response.text[:200]}...")
        else:
            print("\n✗ No get_account_numbers method found")
        
        # Cleanup
        await auth.shutdown()
        
    except Exception as e:
        print(f"✗ Error: {e}")
        logger.exception("Client test failed")


async def main():
    """Run test."""
    await test_client_methods()


if __name__ == "__main__":
    asyncio.run(main())