#!/usr/bin/env python3
"""Test Celery configuration and tasks."""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.utils.logger import setup_logging, logger
from src.tasks.celery_app import celery_app, debug_task
from src.tasks import data_mining, backtesting


def test_basic_connection():
    """Test basic Celery connection."""
    logger.info("Testing basic Celery connection...")
    
    try:
        # Test debug task
        result = debug_task.delay()
        logger.info(f"Debug task ID: {result.id}")
        
        # Wait for result
        response = result.get(timeout=5)
        logger.info(f"Debug task result: {response}")
        
        return True
    except Exception as e:
        logger.error(f"Basic connection test failed: {e}")
        return False


def test_data_mining_tasks():
    """Test data mining tasks."""
    logger.info("\nTesting data mining tasks...")
    
    try:
        # Test mine_ticker_data
        logger.info("1. Testing mine_ticker_data...")
        result = data_mining.mine_ticker_data.delay(
            symbol="AAPL",
            date_str="2024-11-14"
        )
        response = result.get(timeout=10)
        logger.info(f"   Result: {response['status']} - {response['message']}")
        
        # Test mine_date_range
        logger.info("2. Testing mine_date_range...")
        result = data_mining.mine_date_range.delay(
            symbols=["AAPL", "GOOGL", "MSFT"],
            start_date="2024-11-01",
            end_date="2024-11-14"
        )
        response = result.get(timeout=10)
        logger.info(f"   Result: {response['status']} - Job ID: {response['job_id']}")
        
        # Test check_and_fill_gaps
        logger.info("3. Testing check_and_fill_gaps...")
        result = data_mining.check_and_fill_gaps.delay()
        response = result.get(timeout=10)
        logger.info(f"   Result: {response['status']} - Gaps found: {response['gaps_found']}")
        
        return True
    except Exception as e:
        logger.error(f"Data mining test failed: {e}")
        return False


def test_backtesting_tasks():
    """Test backtesting tasks."""
    logger.info("\nTesting backtesting tasks...")
    
    try:
        # Test run_backtest_task
        logger.info("1. Testing run_backtest_task...")
        result = backtesting.run_backtest_task.delay(
            strategy_id="sma_crossover",
            symbols=["AAPL", "GOOGL"],
            start_date="2024-10-01",
            end_date="2024-11-14",
            parameters={"fast_period": 10, "slow_period": 30}
        )
        response = result.get(timeout=10)
        logger.info(f"   Result: {response['status']} - Win rate: {response['results']['win_rate']:.2%}")
        
        # Test optimize_strategy
        logger.info("2. Testing optimize_strategy...")
        result = backtesting.optimize_strategy.delay(
            strategy_id="sma_crossover",
            symbols=["AAPL"],
            start_date="2024-10-01",
            end_date="2024-11-14",
            parameter_ranges={
                "fast_period": {"min": 5, "max": 20, "step": 1},
                "slow_period": {"min": 20, "max": 50, "step": 5}
            }
        )
        
        # Check progress
        import time
        for _ in range(3):
            if result.state == 'PROGRESS':
                info = result.info
                logger.info(f"   Progress: {info.get('current', 0)}/{info.get('total', 0)}")
            time.sleep(1)
        
        response = result.get(timeout=15)
        logger.info(f"   Result: {response['status']} - Best Sharpe: {response['best_performance']['sharpe_ratio']:.2f}")
        
        return True
    except Exception as e:
        logger.error(f"Backtesting test failed: {e}")
        return False


def test_celery_beat():
    """Test Celery Beat scheduled tasks."""
    logger.info("\nTesting Celery Beat scheduled tasks...")
    
    try:
        from celery.schedules import crontab
        
        # Get beat schedule
        schedule = celery_app.conf.beat_schedule
        
        logger.info("Scheduled tasks:")
        for task_name, task_info in schedule.items():
            logger.info(f"  - {task_name}:")
            logger.info(f"    Task: {task_info['task']}")
            logger.info(f"    Schedule: {task_info['schedule']}")
            logger.info(f"    Queue: {task_info.get('options', {}).get('queue', 'default')}")
        
        return True
    except Exception as e:
        logger.error(f"Beat schedule test failed: {e}")
        return False


def main():
    """Run all Celery tests."""
    setup_logging()
    logger.info("Starting Celery tests...")
    logger.info("=" * 50)
    
    # Check Redis connection first
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
    
    # Run tests
    tests = [
        ("Basic Connection", test_basic_connection),
        ("Data Mining Tasks", test_data_mining_tasks),
        ("Backtesting Tasks", test_backtesting_tasks),
        ("Celery Beat Schedule", test_celery_beat),
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n{'=' * 50}")
        logger.info(f"Running: {test_name}")
        logger.info("=" * 50)
        
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info(f"\n{'=' * 50}")
    logger.info("Test Summary:")
    logger.info("=" * 50)
    
    for test_name, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        logger.info(f"{test_name}: {status}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    # Instructions
    if passed < total:
        logger.info("\n⚠️  Some tests failed. Make sure:")
        logger.info("1. Redis is running: redis-server")
        logger.info("2. Celery worker is running: python scripts/run_celery_worker.py")
        logger.info("3. Check the logs for error details")
    else:
        logger.info("\n✅ All tests passed! Celery is configured correctly.")
        logger.info("\nNext steps:")
        logger.info("1. Start Celery worker: python scripts/run_celery_worker.py")
        logger.info("2. Start Celery Beat: python scripts/run_celery_beat.py")
        logger.info("3. Monitor with Flower: python scripts/run_flower.py")


if __name__ == "__main__":
    main()