"""API routes for data mining operations."""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
from pydantic import BaseModel
from src.services.mining_orchestrator_full import FullMarketMiningOrchestrator
from src.services.mining_orchestrator_v2 import EnhancedMiningOrchestrator
from src.broker.schwab_client import SchwabBroker
from src.utils.logger import get_logger
from src.api.dependencies import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/api/mining", tags=["mining"])

# Global orchestrator instances
full_orchestrator: Optional[FullMarketMiningOrchestrator] = None
phase_orchestrator: Optional[EnhancedMiningOrchestrator] = None
mining_task: Optional[asyncio.Task] = None


class MiningStartRequest(BaseModel):
    """Request model for starting mining operations."""
    mode: str = "full"  # full, gaps_only, new_only, phases
    days_back: int = 60
    batch_size: int = 50
    concurrent_limit: int = 10
    start_phase: Optional[int] = 1
    end_phase: Optional[int] = 3
    symbols: Optional[List[str]] = None  # Custom symbol list


class MiningControlRequest(BaseModel):
    """Request model for mining control operations."""
    action: str  # pause, resume, stop


async def get_orchestrator():
    """Get or create orchestrator instance."""
    global full_orchestrator, phase_orchestrator
    
    if not full_orchestrator:
        # Initialize Schwab client
        broker = SchwabBroker()
        await broker.initialize()
        
        # Create orchestrators
        full_orchestrator = FullMarketMiningOrchestrator(broker.client)
        phase_orchestrator = EnhancedMiningOrchestrator(broker.client)
    
    return full_orchestrator, phase_orchestrator


@router.post("/start")
async def start_mining(
    request: MiningStartRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user)
):
    """Start mining operations."""
    global mining_task
    
    try:
        # Check if mining is already running
        if mining_task and not mining_task.done():
            raise HTTPException(status_code=400, detail="Mining already in progress")
        
        # Get orchestrators
        full_orch, phase_orch = await get_orchestrator()
        
        # Start mining based on mode
        if request.mode == "phases":
            # Use phase-based orchestrator
            mining_task = asyncio.create_task(
                phase_orch.execute_multi_phase_mining(
                    start_phase=request.start_phase,
                    end_phase=request.end_phase,
                    days_back=request.days_back
                )
            )
            logger.info(f"Started phase mining: phases {request.start_phase}-{request.end_phase}")
            
            return {
                "status": "started",
                "mode": "phases",
                "phases": f"{request.start_phase}-{request.end_phase}",
                "days_back": request.days_back
            }
        else:
            # Use full market orchestrator
            mining_task = asyncio.create_task(
                full_orch.start_mining(
                    mode=request.mode,
                    days_back=request.days_back,
                    batch_size=request.batch_size,
                    concurrent_limit=request.concurrent_limit
                )
            )
            logger.info(f"Started {request.mode} mining for full market")
            
            return {
                "status": "started",
                "mode": request.mode,
                "total_symbols": full_orch.progress['total_symbols'],
                "days_back": request.days_back,
                "batch_size": request.batch_size
            }
            
    except Exception as e:
        logger.error(f"Failed to start mining: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/control")
async def control_mining(
    request: MiningControlRequest,
    user=Depends(get_current_user)
):
    """Control mining operations (pause/resume/stop)."""
    try:
        full_orch, phase_orch = await get_orchestrator()
        
        if request.action == "pause":
            await full_orch.pause_mining()
            return {"status": "paused", "message": "Mining paused"}
            
        elif request.action == "resume":
            await full_orch.resume_mining()
            return {"status": "resumed", "message": "Mining resumed"}
            
        elif request.action == "stop":
            await full_orch.stop_mining()
            await phase_orch.stop_mining()
            
            # Cancel the task
            global mining_task
            if mining_task:
                mining_task.cancel()
                mining_task = None
            
            return {"status": "stopped", "message": "Mining stopped"}
            
        else:
            raise HTTPException(status_code=400, detail=f"Invalid action: {request.action}")
            
    except Exception as e:
        logger.error(f"Mining control error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_mining_status(user=Depends(get_current_user)):
    """Get current mining status."""
    try:
        full_orch, phase_orch = await get_orchestrator()
        
        # Check which orchestrator is active
        if full_orch.is_running:
            status = full_orch.get_status()
            status['orchestrator'] = 'full_market'
        elif phase_orch.is_running:
            status = phase_orch.get_detailed_status()
            status['orchestrator'] = 'phases'
        else:
            status = {
                "is_running": False,
                "orchestrator": None,
                "message": "No mining operation in progress"
            }
        
        # Add task status
        global mining_task
        if mining_task:
            status['task_status'] = 'running' if not mining_task.done() else 'completed'
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting mining status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/progress")
async def get_mining_progress(user=Depends(get_current_user)):
    """Get detailed mining progress."""
    try:
        full_orch, phase_orch = await get_orchestrator()
        
        if full_orch.is_running:
            return {
                "orchestrator": "full_market",
                "progress": full_orch.progress,
                "performance": full_orch.performance
            }
        elif phase_orch.is_running:
            return {
                "orchestrator": "phases",
                "progress": phase_orch.progress,
                "quality": phase_orch.quality_metrics
            }
        else:
            return {
                "orchestrator": None,
                "message": "No mining in progress"
            }
            
    except Exception as e:
        logger.error(f"Error getting progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/failed-symbols")
async def get_failed_symbols(user=Depends(get_current_user)):
    """Get list of failed symbols."""
    try:
        full_orch, _ = await get_orchestrator()
        
        return {
            "permanent_failures": full_orch.failed_tracker.failed_symbols,
            "temporary_failures": full_orch.failed_tracker.temp_failures,
            "total_failed": len(full_orch.failed_tracker.failed_symbols)
        }
        
    except Exception as e:
        logger.error(f"Error getting failed symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retry-failed")
async def retry_failed_symbols(
    symbols: Optional[List[str]] = None,
    user=Depends(get_current_user)
):
    """Retry failed symbols."""
    try:
        full_orch, _ = await get_orchestrator()
        
        # Clear specified symbols from failed list
        if symbols:
            for symbol in symbols:
                if symbol in full_orch.failed_tracker.failed_symbols:
                    del full_orch.failed_tracker.failed_symbols[symbol]
                if symbol in full_orch.failed_tracker.temp_failures:
                    del full_orch.failed_tracker.temp_failures[symbol]
        else:
            # Clear all temporary failures
            full_orch.failed_tracker.temp_failures.clear()
        
        await full_orch.failed_tracker.save_failed_symbols()
        
        return {
            "status": "cleared",
            "symbols_cleared": symbols or list(full_orch.failed_tracker.temp_failures.keys()),
            "remaining_failures": len(full_orch.failed_tracker.failed_symbols)
        }
        
    except Exception as e:
        logger.error(f"Error retrying failed symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_mining_statistics(user=Depends(get_current_user)):
    """Get comprehensive mining statistics."""
    try:
        from sqlalchemy import create_engine, select, func
        from sqlalchemy.orm import Session
        from src.models.market_data import MiningStatus, MiningLog, Candle1Min
        import os
        
        db_url = os.getenv("DATABASE_URL", "postgresql://houkjang@localhost/autotrading")
        engine = create_engine(db_url)
        
        with Session(engine) as session:
            # Get overall statistics
            total_symbols = session.execute(
                select(func.count(MiningStatus.id))
            ).scalar() or 0
            
            active_symbols = session.execute(
                select(func.count(MiningStatus.id))
                .where(MiningStatus.is_active == True)
            ).scalar() or 0
            
            total_candles = session.execute(
                select(func.count(Candle1Min.id))
            ).scalar() or 0
            
            # Get quality statistics
            avg_quality = session.execute(
                select(func.avg(MiningStatus.data_quality_score))
            ).scalar() or 0
            
            low_quality = session.execute(
                select(func.count(MiningStatus.id))
                .where(MiningStatus.data_quality_score < 80)
            ).scalar() or 0
            
            # Get recent operations
            recent_ops = session.execute(
                select(
                    MiningLog.operation,
                    func.count(MiningLog.id).label('count'),
                    func.sum(MiningLog.candles_added).label('candles'),
                    func.avg(
                        func.extract('epoch', MiningLog.end_time - MiningLog.start_time)
                    ).label('avg_duration')
                )
                .group_by(MiningLog.operation)
                .order_by(func.count(MiningLog.id).desc())
                .limit(10)
            ).all()
            
            return {
                "database_stats": {
                    "total_symbols": total_symbols,
                    "active_symbols": active_symbols,
                    "total_candles": total_candles,
                    "average_quality": round(avg_quality, 2),
                    "low_quality_symbols": low_quality
                },
                "recent_operations": [
                    {
                        "operation": op.operation,
                        "count": op.count,
                        "candles_added": op.candles or 0,
                        "avg_duration_seconds": round(op.avg_duration or 0, 2)
                    }
                    for op in recent_ops
                ]
            }
            
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gaps/{symbol}")
async def get_symbol_gaps(
    symbol: str,
    days_back: int = 60,
    user=Depends(get_current_user)
):
    """Get data gaps for a specific symbol."""
    try:
        full_orch, _ = await get_orchestrator()
        
        gaps = await full_orch.gap_filler.detect_gaps(symbol, days_back)
        
        return {
            "symbol": symbol,
            "gaps_found": len(gaps),
            "gaps": gaps,
            "days_analyzed": days_back
        }
        
    except Exception as e:
        logger.error(f"Error detecting gaps for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gaps/{symbol}/fill")
async def fill_symbol_gaps(
    symbol: str,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user)
):
    """Fill data gaps for a specific symbol."""
    try:
        full_orch, _ = await get_orchestrator()
        
        # Detect gaps
        gaps = await full_orch.gap_filler.detect_gaps(symbol, days_back=60)
        
        if not gaps:
            return {
                "symbol": symbol,
                "message": "No gaps found",
                "gaps_filled": 0
            }
        
        # Fill gaps in background
        async def fill_gaps_task():
            result = await full_orch.gap_filler.fill_gaps(symbol, gaps)
            logger.info(f"Gap filling completed for {symbol}: {result}")
        
        background_tasks.add_task(fill_gaps_task)
        
        return {
            "symbol": symbol,
            "status": "filling",
            "gaps_to_fill": len(gaps),
            "message": "Gap filling started in background"
        }
        
    except Exception as e:
        logger.error(f"Error filling gaps for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))