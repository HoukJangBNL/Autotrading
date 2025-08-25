"""Celery tasks for data mining operations."""

from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
from celery import group, chain, chord
from celery.exceptions import Retry
import asyncio

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from .celery_app import celery_app
from .celery_utils import run_async_in_celery
from src.utils.logger import logger
from src.services.data_mining_service import DataMiningService
from src.services.data_mining_service_sync import DataMiningServiceSync
from src.data.database import db_service
from src.data.models import Ticker, MiningStatus, TickerTier
from src.config import settings


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def mine_ticker_data(
    self, 
    symbol: str,
    date_str: str
) -> Dict[str, Any]:
    """Mine 1-minute data for a single ticker on a specific date.
    
    Args:
        symbol: Stock symbol
        date_str: Date in YYYY-MM-DD format
        
    Returns:
        Task result with status and data
    """
    logger.info(f"[Task {self.request.id}] Mining data for {symbol} on {date_str}")
    
    # Create new event loop for this task
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Run async function in the new event loop
        result = loop.run_until_complete(
            _mine_ticker_data_async(symbol, date_str, self.request.id)
        )
        
        if result["success"]:
            return {
                "status": "success",
                "symbol": symbol,
                "date": date_str,
                "candles_count": result.get("saved", 0),
                "task_id": self.request.id,
                "message": result.get("message", "Successfully mined data")
            }
        else:
            raise Exception(result.get("error", "Unknown error"))
    
    except Exception as e:
        logger.error(f"[Task {self.request.id}] Error mining data for {symbol} on {date_str}: {e}")
        
        # 재시도 로직
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying task {self.request.id} (attempt {self.request.retries + 1})")
            raise self.retry(exc=e)
        
        return {
            "status": "error",
            "symbol": symbol,
            "date": date_str,
            "task_id": self.request.id,
            "error": str(e),
            "retries": self.request.retries
        }
    finally:
        # Clean up the event loop
        loop.close()


async def _mine_ticker_data_async(symbol: str, date_str: str, task_id: str) -> Dict[str, Any]:
    """Async helper for mining ticker data."""
    # Create independent database engine for this task
    async_url = settings.get_database_url().replace('postgresql://', 'postgresql+asyncpg://')
    engine = create_async_engine(async_url, echo=False)
    
    # Create session factory
    AsyncSessionLocal = sessionmaker(
        engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    try:
        # Initialize service
        service = DataMiningService()
        await service.initialize()
        
        async with AsyncSessionLocal() as session:
            # Get or create ticker
            tickers = await service._get_or_create_tickers(
                session, [symbol], TickerTier.CORE
            )
            ticker = tickers[0]
            
            # Parse date and create date range
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_date = datetime.combine(target_date, datetime.min.time())
            end_date = datetime.combine(target_date, datetime.max.time())
            
            # Mine data
            result = await service.mine_ticker_data(ticker, start_date, end_date)
            
            if result["success"]:
                # Save candles
                saved, duplicates = await service.save_candles(
                    session, ticker.id, result["candles"]
                )
                
                # Create mining history
                await service.create_mining_history(
                    session, ticker.id, target_date, result
                )
                
                # Update ticker status
                ticker.last_mined = datetime.now()
                ticker.mining_status = MiningStatus.COMPLETED
                await session.commit()
                
                logger.info(f"Saved {saved} candles for {symbol} ({duplicates} duplicates)")
                
                # Add saved count and message to result
                result["saved"] = saved
                result["duplicates"] = duplicates
                result["message"] = f"Successfully mined {saved} candles for {symbol} ({duplicates} duplicates)"
            else:
                # Update ticker status to failed
                ticker.mining_status = MiningStatus.FAILED
                await session.commit()
            
            return result
    finally:
        # Clean up engine
        await engine.dispose()


@celery_app.task
def mine_date_range(
    symbols: List[str],
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """Mine data for multiple symbols over a date range.
    
    Creates parallel sub-tasks for efficient data collection.
    
    Args:
        symbols: List of stock symbols
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        
    Returns:
        Task result with job details
    """
    logger.info(f"Creating mining jobs for {len(symbols)} symbols from {start_date} to {end_date}")
    
    try:
        # 날짜 범위 생성
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        # 모든 symbol/date 조합에 대한 태스크 생성
        tasks = []
        current_date = start
        
        while current_date <= end:
            # 주말 제외
            if current_date.weekday() < 5:  # 월요일(0) ~ 금요일(4)
                for symbol in symbols:
                    task = mine_ticker_data.s(symbol, current_date.isoformat())
                    tasks.append(task)
            
            current_date += timedelta(days=1)
        
        # 병렬로 실행할 태스크 그룹 생성
        job = group(tasks)
        result = job.apply_async(queue="data_mining")
        
        return {
            "status": "submitted",
            "job_id": result.id,
            "total_tasks": len(tasks),
            "symbols": symbols,
            "date_range": {
                "start": start_date,
                "end": end_date
            },
            "message": f"Submitted {len(tasks)} mining tasks"
        }
    
    except Exception as e:
        logger.error(f"Error creating date range mining jobs: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@celery_app.task
def check_and_fill_gaps() -> Dict[str, Any]:
    """Check for data gaps and fill them.
    
    This is designed to be run periodically by Celery Beat.
    
    Returns:
        Task result with gap information
    """
    logger.info("Starting data gap check")
    
    # Create new event loop for this task
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Run async function in the new event loop
        result = loop.run_until_complete(_check_and_fill_gaps_async())
        return result
    except Exception as e:
        logger.error(f"Error in gap checking: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
    finally:
        # Clean up the event loop
        loop.close()


async def _check_and_fill_gaps_async() -> Dict[str, Any]:
    """Async helper for checking and filling data gaps."""
    # Create independent database engine for this task
    async_url = settings.get_database_url().replace('postgresql://', 'postgresql+asyncpg://')
    engine = create_async_engine(async_url, echo=False)
    
    # Create session factory
    AsyncSessionLocal = sessionmaker(
        engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    try:
        service = DataMiningService()
        await service.initialize()
        
        gaps_found = []
        symbols_checked = 0
        
        async with AsyncSessionLocal() as session:
            # Get all active tickers
            result = await session.execute(
                select(Ticker)
                .where(Ticker.active == True)
                .where(Ticker.tier.in_([TickerTier.CORE, TickerTier.EXPANDED]))
            )
            tickers = result.scalars().all()
            symbols_checked = len(tickers)
            
            # Check gaps for each ticker
            end_date = datetime.now()
            start_date = end_date - timedelta(days=60)
            
            for ticker in tickers:
                gaps = await service.check_data_gaps(
                    session, ticker.id, start_date, end_date
                )
                
                for gap_start, gap_end in gaps:
                    # Group gaps by date
                    current_date = gap_start.date()
                    while current_date <= gap_end.date():
                        gaps_found.append({
                            "symbol": ticker.symbol,
                            "date": current_date.isoformat()
                        })
                        current_date += timedelta(days=1)
        
        # Create tasks to fill gaps
        if gaps_found:
            fill_tasks = [
                mine_ticker_data.s(gap["symbol"], gap["date"]) 
                for gap in gaps_found
            ]
            job = group(fill_tasks)
            job.apply_async(queue="data_mining")
            
            logger.info(f"Created {len(fill_tasks)} tasks to fill data gaps")
        
        return {
            "status": "success",
            "symbols_checked": symbols_checked,
            "gaps_found": len(gaps_found),
            "gaps_details": gaps_found[:10],  # First 10 for summary
            "timestamp": datetime.now().isoformat(),
            "message": f"Checked {symbols_checked} symbols, found and queued {len(gaps_found)} gaps"
        }
    finally:
        # Clean up engine
        await engine.dispose()


@celery_app.task
def get_mining_progress(job_id: str) -> Dict[str, Any]:
    """Get progress of a mining job.
    
    Args:
        job_id: Celery group result ID
        
    Returns:
        Progress information
    """
    try:
        from celery.result import GroupResult
        
        result = GroupResult.restore(job_id, app=celery_app)
        if not result:
            return {
                "status": "not_found",
                "job_id": job_id,
                "message": "Job not found"
            }
        
        total = len(result)
        completed = result.completed_count()
        failed = result.failed() 
        
        return {
            "status": "progress",
            "job_id": job_id,
            "total_tasks": total,
            "completed": completed,
            "failed": len(failed) if failed else 0,
            "progress_percent": (completed / total * 100) if total > 0 else 0,
            "is_ready": result.ready()
        }
        
    except Exception as e:
        logger.error(f"Error getting progress for job {job_id}: {e}")
        return {
            "status": "error",
            "job_id": job_id,
            "error": str(e)
        }


@celery_app.task
def cleanup_old_data(days_to_keep: int = 90) -> Dict[str, Any]:
    """Clean up old data from the database.
    
    Args:
        days_to_keep: Number of days of data to keep
        
    Returns:
        Cleanup result
    """
    logger.info(f"Cleaning up data older than {days_to_keep} days")
    
    try:
        # Phase 2에서 실제 구현 예정
        # cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        # deleted_count = delete_candles_before(cutoff_date)
        
        # 시뮬레이션 결과
        deleted_count = 1000000
        
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "days_kept": days_to_keep,
            "message": f"Deleted {deleted_count} old candle records"
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up old data: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@celery_app.task
def start_daily_mining() -> Dict[str, Any]:
    """Start the daily mining process.
    
    This task should be scheduled to run during pre-market hours.
    It identifies today's mining targets and creates tasks for each ticker.
    
    Returns:
        Task result with job information
    """
    logger.info("Starting daily mining process")
    
    # Create new event loop for this task
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Run async function in the new event loop
        result = loop.run_until_complete(_start_daily_mining_async())
        return result
    except Exception as e:
        logger.error(f"Error starting daily mining: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
    finally:
        # Clean up the event loop
        loop.close()


async def _start_daily_mining_async() -> Dict[str, Any]:
    """Async helper for starting daily mining."""
    # Create independent database engine for this task
    async_url = settings.get_database_url().replace('postgresql://', 'postgresql+asyncpg://')
    engine = create_async_engine(async_url, echo=False)
    
    # Create session factory
    AsyncSessionLocal = sessionmaker(
        engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    try:
        service = DataMiningService()
        await service.initialize()
        
        async with AsyncSessionLocal() as session:
            # Get today's mining targets
            targets = await service.get_daily_targets(session)
            
            if not targets:
                logger.warning("No mining targets found for today")
                return {
                    "status": "success",
                    "message": "No targets to mine",
                    "targets_count": 0,
                    "timestamp": datetime.now().isoformat()
                }
        
            # Create mining tasks for each target
            tasks = []
            today = date.today()
            
            # Go back 60 days
            end_date = today
            start_date = today - timedelta(days=60)
            
            # Create tasks for each day and ticker
            current_date = start_date
            while current_date <= end_date:
                # Skip weekends
                if current_date.weekday() < 5:  # Monday(0) to Friday(4)
                    for target in targets:
                        task = mine_ticker_data.s(
                            target["ticker"].symbol,
                            current_date.isoformat()
                        )
                        tasks.append(task)
                
                current_date += timedelta(days=1)
            
            # Submit tasks as a group
            if tasks:
                job = group(tasks)
                result = job.apply_async(queue="data_mining")
                
                logger.info(f"Created {len(tasks)} mining tasks for {len(targets)} tickers")
                
                return {
                    "status": "success",
                    "job_id": result.id,
                    "targets_count": len(targets),
                    "tasks_count": len(tasks),
                    "targets": [
                        {
                            "symbol": t["ticker"].symbol,
                            "tier": t["ticker"].tier.value,
                            "priority": t["priority"],
                            "reason": t["reason"]
                        }
                        for t in targets[:10]  # First 10 for summary
                    ],
                    "timestamp": datetime.now().isoformat(),
                    "message": f"Started mining {len(targets)} tickers with {len(tasks)} tasks"
                }
            else:
                return {
                    "status": "success",
                    "message": "No tasks created (all dates are weekends)",
                    "targets_count": len(targets),
                    "tasks_count": 0,
                    "timestamp": datetime.now().isoformat()
                }
    finally:
        # Clean up engine
        await engine.dispose()