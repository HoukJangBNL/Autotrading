#!/usr/bin/env python3
"""Test token refresh."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.auth.oauth_manager import OAuthManager
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_token_refresh():
    """Test token refresh."""
    
    logger.info("Testing token refresh...")
    
    try:
        oauth_manager = OAuthManager(settings)
        
        # Try to refresh token
        logger.info("Attempting to refresh token...")
        new_token = await oauth_manager.refresh_access_token()
        
        logger.info("✅ Token refreshed successfully!")
        logger.info(f"New token expires in: {new_token.get('expires_in')} seconds")
        
    except Exception as e:
        logger.error(f"❌ Token refresh failed: {e}")
        logger.info("\nYou may need to re-authenticate. Run: python scripts/run_auth.py")


async def main():
    """Run token refresh test."""
    await test_token_refresh()


if __name__ == "__main__":
    asyncio.run(main())