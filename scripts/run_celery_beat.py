#!/usr/bin/env python3
"""Run Celery Beat scheduler for periodic tasks."""

import sys
import os
from pathlib import Path
import subprocess
import argparse

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.utils.logger import setup_logging, logger


def run_beat(loglevel: str = "info", pidfile: str = None):
    """Run Celery Beat scheduler.
    
    Args:
        loglevel: Logging level (debug, info, warning, error)
        pidfile: Path to PID file for the scheduler
    """
    setup_logging()
    
    # Base command
    cmd = [
        "celery",
        "-A", "src.tasks.celery_app",
        "beat",
        f"--loglevel={loglevel}",
    ]
    
    # Add pidfile if specified
    if pidfile:
        cmd.extend(["--pidfile", pidfile])
    
    logger.info("Starting Celery Beat scheduler")
    logger.info(f"Command: {' '.join(cmd)}")
    
    # Show scheduled tasks
    logger.info("Scheduled tasks:")
    logger.info("  - check-data-gaps: Daily at 5:00 AM ET")
    logger.info("  - weekly-backtesting: Weekly on Sunday at 6:00 AM ET")
    
    try:
        # Run the scheduler
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Beat scheduler failed with error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Beat scheduler stopped by user")
        sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run Celery Beat scheduler")
    parser.add_argument(
        "-l", "--loglevel",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Logging level (default: info)"
    )
    parser.add_argument(
        "--pidfile",
        help="Path to PID file for the scheduler"
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
    
    # Check if worker is running
    logger.info("Note: Celery Beat requires at least one worker to be running")
    logger.info("Start a worker with: python scripts/run_celery_worker.py")
    
    # Run the scheduler
    run_beat(
        loglevel=args.loglevel,
        pidfile=args.pidfile
    )


if __name__ == "__main__":
    main()