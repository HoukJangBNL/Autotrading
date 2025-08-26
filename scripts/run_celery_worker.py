#!/usr/bin/env python3
"""Run Celery worker for background tasks."""

import sys
import os
from pathlib import Path
import subprocess
import argparse

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.utils.logger import setup_logging, logger


def run_worker(queue: str = None, concurrency: int = 4, loglevel: str = "info"):
    """Run Celery worker process.
    
    Args:
        queue: Specific queue to consume from (default: all queues)
        concurrency: Number of concurrent worker processes
        loglevel: Logging level (debug, info, warning, error)
    """
    setup_logging()
    
    # Base command
    cmd = [
        "celery",
        "-A", "src.tasks.celery_app",
        "worker",
        f"--loglevel={loglevel}",
        f"--concurrency={concurrency}",
        "--time-limit=3600",  # Hard time limit: 1 hour
        "--soft-time-limit=3300",  # Soft time limit: 55 minutes
    ]
    
    # Add queue if specified
    if queue:
        cmd.extend(["-Q", queue])
        logger.info(f"Starting Celery worker for queue: {queue}")
    else:
        logger.info("Starting Celery worker for all queues")
    
    # Set worker name based on queue
    worker_name = f"worker-{queue}" if queue else "worker-main"
    cmd.extend(["-n", f"{worker_name}@%h"])
    
    # Log the command
    logger.info(f"Command: {' '.join(cmd)}")
    
    try:
        # Run the worker
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Worker failed with error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run Celery worker")
    parser.add_argument(
        "-Q", "--queue",
        choices=["default", "data_mining", "backtesting"],
        help="Specific queue to consume from"
    )
    parser.add_argument(
        "-c", "--concurrency",
        type=int,
        default=4,
        help="Number of concurrent worker processes (default: 4)"
    )
    parser.add_argument(
        "-l", "--loglevel",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Logging level (default: info)"
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
    
    # Run the worker
    run_worker(
        queue=args.queue,
        concurrency=args.concurrency,
        loglevel=args.loglevel
    )


if __name__ == "__main__":
    main()