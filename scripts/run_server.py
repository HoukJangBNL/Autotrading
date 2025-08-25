#!/usr/bin/env python3
"""Run the FastAPI trading system server."""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

import uvicorn
from src.api.main import app
from src.config import settings
from src.utils.logger import setup_logging, logger


def main():
    """Run the FastAPI server."""
    # Setup logging
    setup_logging()
    
    logger.info("Starting Trading System API Server")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    
    # Server configuration
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = settings.environment == "development"
    
    # SSL configuration for production
    ssl_keyfile = None
    ssl_certfile = None
    
    if settings.environment == "production":
        ssl_keyfile = os.getenv("SSL_KEYFILE")
        ssl_certfile = os.getenv("SSL_CERTFILE")
        
        if ssl_keyfile and ssl_certfile:
            logger.info("SSL enabled for production")
        else:
            logger.warning("Running production without SSL - not recommended!")
    
    # Log server URLs
    protocol = "https" if ssl_keyfile else "http"
    logger.info(f"API Documentation: {protocol}://localhost:{port}/api/docs")
    logger.info(f"Alternative docs: {protocol}://localhost:{port}/api/redoc")
    logger.info(f"Health check: {protocol}://localhost:{port}/health")
    
    # Run server
    try:
        uvicorn.run(
            "src.api.main:app" if reload else app,
            host=host,
            port=port,
            reload=reload,
            log_level="info" if settings.debug else "warning",
            access_log=settings.debug,
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
            # Workers only in production without reload
            workers=1 if reload else os.cpu_count()
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()