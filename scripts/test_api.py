#!/usr/bin/env python3
"""Test the FastAPI endpoints."""

import sys
from pathlib import Path
import asyncio
import httpx

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.utils.logger import setup_logging, logger


async def test_endpoints():
    """Test various API endpoints."""
    base_url = "http://localhost:8000"
    
    # Test client
    async with httpx.AsyncClient() as client:
        # Test health check (no auth required)
        logger.info("Testing health check...")
        try:
            response = await client.get(f"{base_url}/health")
            logger.info(f"Health check: {response.status_code} - {response.json()}")
        except Exception as e:
            logger.error(f"Health check failed: {e}")
        
        # Test detailed health check
        logger.info("\nTesting detailed health check...")
        try:
            response = await client.get(f"{base_url}/health/detailed")
            logger.info(f"Detailed health: {response.status_code}")
            health_data = response.json()
            for service, status in health_data.get("services", {}).items():
                logger.info(f"  {service}: {status}")
        except Exception as e:
            logger.error(f"Detailed health check failed: {e}")
        
        # Test auth status (requires auth - should fail)
        logger.info("\nTesting auth status without token...")
        try:
            response = await client.get(f"{base_url}/api/auth/status")
            logger.info(f"Auth status (no token): {response.status_code} - {response.json()}")
        except Exception as e:
            logger.error(f"Auth status failed: {e}")
        
        # Test with fake token
        logger.info("\nTesting auth status with fake token...")
        headers = {"Authorization": "Bearer fake-token"}
        try:
            response = await client.get(f"{base_url}/api/auth/status", headers=headers)
            logger.info(f"Auth status (fake token): {response.status_code} - {response.json()}")
        except Exception as e:
            logger.error(f"Auth status with token failed: {e}")
        
        # Test API docs
        logger.info("\nTesting API documentation endpoints...")
        try:
            response = await client.get(f"{base_url}/api/docs")
            logger.info(f"API docs available: {response.status_code == 200}")
            
            response = await client.get(f"{base_url}/api/openapi.json")
            logger.info(f"OpenAPI spec available: {response.status_code == 200}")
        except Exception as e:
            logger.error(f"API docs test failed: {e}")


def main():
    """Run API tests."""
    setup_logging()
    logger.info("Starting API endpoint tests...")
    
    try:
        asyncio.run(test_endpoints())
        logger.info("\nAPI tests completed!")
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
    except Exception as e:
        logger.error(f"Test error: {e}")


if __name__ == "__main__":
    main()