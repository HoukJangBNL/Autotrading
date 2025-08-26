#!/usr/bin/env python3
"""Run Flower web-based monitoring tool for Celery."""

import sys
import os
from pathlib import Path
import subprocess
import argparse

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.utils.logger import setup_logging, logger


def run_flower(port: int = 5555, address: str = "127.0.0.1"):
    """Run Flower monitoring tool.
    
    Args:
        port: Port to run Flower on (default: 5555)
        address: Address to bind to (default: 127.0.0.1)
    """
    setup_logging()
    
    # Base command
    cmd = [
        "celery",
        "-A", "src.tasks.celery_app",
        "flower",
        f"--port={port}",
        f"--address={address}",
        "--url_prefix=",  # No URL prefix
        "--basic_auth=admin:admin",  # Basic auth (change in production!)
    ]
    
    logger.info("Starting Flower monitoring tool")
    logger.info(f"Command: {' '.join(cmd)}")
    logger.info(f"Access Flower at: http://{address}:{port}")
    logger.info("Default credentials: admin/admin (CHANGE IN PRODUCTION!)")
    
    try:
        # Run Flower
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Flower failed with error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Flower stopped by user")
        sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run Flower monitoring tool")
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=5555,
        help="Port to run Flower on (default: 5555)"
    )
    parser.add_argument(
        "-a", "--address",
        default="127.0.0.1",
        help="Address to bind to (default: 127.0.0.1)"
    )
    
    args = parser.parse_args()
    
    # Ensure Redis is available
    logger.info("Checking Redis connection...")
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        logger.info("✓ Redis is available")
    except Exception as e:
        logger.error(f"✗ Redis is not available: {e}")
        logger.error("Please start Redis first: redis-server")
        sys.exit(1)
    
    # Run Flower
    run_flower(
        port=args.port,
        address=args.address
    )


if __name__ == "__main__":
    main()