"""Backtest router for running strategy backtests."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from uuid import uuid4
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from ...data.database import get_db
from ...strategy.backtesting.engine import BacktestEngine, BacktestResult
from ...strategy.base import BaseStrategy
from ..schemas.backtest import (
    BacktestRequest,
    BacktestResponse,
    BacktestStatus,
    BacktestResultResponse
)
from ..dependencies import get_current_user
from .strategies import STRATEGY_REGISTRY, strategies_store

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory backtest storage (replace with database in production)
backtest_store: Dict[str, Dict[str, Any]] = {}


async def run_backtest_task(
    backtest_id: str,
    strategy: BaseStrategy,
    start_date: datetime,
    end_date: datetime,
    initial_capital: float,
    commission_rate: float,
    slippage_rate: float
):
    """Background task to run backtest."""
    try:
        # Update status
        backtest_store[backtest_id]["status"] = "running"
        backtest_store[backtest_id]["started_at"] = datetime.now()
        
        # Create backtest engine
        engine = BacktestEngine(
            commission_rate=commission_rate,
            slippage_rate=slippage_rate,
            starting_cash=initial_capital
        )
        
        # Run backtest
        result = await engine.run_backtest(
            strategy=strategy,
            start_date=start_date,
            end_date=end_date
        )
        
        # Store results
        backtest_store[backtest_id]["status"] = "completed"
        backtest_store[backtest_id]["completed_at"] = datetime.now()
        backtest_store[backtest_id]["result"] = result.to_dict()
        
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        backtest_store[backtest_id]["status"] = "failed"
        backtest_store[backtest_id]["error"] = str(e)
        backtest_store[backtest_id]["completed_at"] = datetime.now()


@router.post("/", response_model=BacktestResponse)
async def start_backtest(
    request: BacktestRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> BacktestResponse:
    """
    Start a new backtest.
    
    Runs the backtest in the background and returns a backtest ID.
    """
    try:
        # Validate strategy exists
        if request.strategy_id not in strategies_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Strategy not found: {request.strategy_id}"
            )
        
        strategy_data = strategies_store[request.strategy_id]
        
        # Validate date range
        if request.end_date <= request.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End date must be after start date"
            )
        
        days = (request.end_date - request.start_date).days
        if days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Backtest period cannot exceed 365 days"
            )
        
        # Create strategy instance
        strategy_class = STRATEGY_REGISTRY[strategy_data["type"]]
        strategy = strategy_class(
            symbols=request.symbols or strategy_data["symbols"],
            initial_capital=request.initial_capital,
            **strategy_data["parameters"]
        )
        
        # Generate backtest ID
        backtest_id = str(uuid4())
        
        # Store backtest info
        backtest_store[backtest_id] = {
            "id": backtest_id,
            "strategy_id": request.strategy_id,
            "strategy_name": strategy_data["name"],
            "symbols": request.symbols or strategy_data["symbols"],
            "start_date": request.start_date,
            "end_date": request.end_date,
            "initial_capital": request.initial_capital,
            "commission_rate": request.commission_rate,
            "slippage_rate": request.slippage_rate,
            "status": "pending",
            "created_at": datetime.now(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None
        }
        
        # Start backtest in background
        background_tasks.add_task(
            run_backtest_task,
            backtest_id,
            strategy,
            request.start_date,
            request.end_date,
            request.initial_capital,
            request.commission_rate,
            request.slippage_rate
        )
        
        return BacktestResponse(
            backtest_id=backtest_id,
            status="pending",
            message=f"Backtest started for strategy {strategy_data['name']}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start backtest: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start backtest"
        )


@router.get("/{backtest_id}/status", response_model=BacktestStatus)
async def get_backtest_status(
    backtest_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> BacktestStatus:
    """
    Get backtest status.
    
    Returns current status and progress of a backtest.
    """
    try:
        if backtest_id not in backtest_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backtest not found: {backtest_id}"
            )
        
        backtest_data = backtest_store[backtest_id]
        
        # Calculate progress (mock for now)
        progress = 0
        if backtest_data["status"] == "running":
            if backtest_data["started_at"]:
                elapsed = (datetime.now() - backtest_data["started_at"]).seconds
                progress = min(elapsed / 30 * 100, 99)  # Assume 30 seconds
        elif backtest_data["status"] == "completed":
            progress = 100
        
        return BacktestStatus(
            backtest_id=backtest_id,
            status=backtest_data["status"],
            progress=progress,
            strategy_name=backtest_data["strategy_name"],
            symbols=backtest_data["symbols"],
            start_date=backtest_data["start_date"],
            end_date=backtest_data["end_date"],
            created_at=backtest_data["created_at"],
            started_at=backtest_data["started_at"],
            completed_at=backtest_data["completed_at"],
            error=backtest_data["error"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get backtest status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve backtest status"
        )


@router.get("/{backtest_id}/result", response_model=BacktestResultResponse)
async def get_backtest_result(
    backtest_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> BacktestResultResponse:
    """
    Get backtest results.
    
    Returns detailed performance metrics and trade history.
    """
    try:
        if backtest_id not in backtest_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backtest not found: {backtest_id}"
            )
        
        backtest_data = backtest_store[backtest_id]
        
        if backtest_data["status"] != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Backtest is {backtest_data['status']}, not completed"
            )
        
        if not backtest_data["result"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Backtest completed but results are missing"
            )
        
        result = backtest_data["result"]
        
        return BacktestResultResponse(
            backtest_id=backtest_id,
            strategy_id=backtest_data["strategy_id"],
            strategy_name=backtest_data["strategy_name"],
            **result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get backtest result: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve backtest results"
        )


@router.get("/", response_model=List[BacktestStatus])
async def list_backtests(
    strategy_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[BacktestStatus]:
    """
    List backtests.
    
    Can filter by strategy ID or status.
    """
    try:
        backtests = []
        
        for backtest_id, backtest_data in backtest_store.items():
            # Apply filters
            if strategy_id and backtest_data["strategy_id"] != strategy_id:
                continue
            if status and backtest_data["status"] != status:
                continue
            
            # Calculate progress
            progress = 0
            if backtest_data["status"] == "running":
                if backtest_data["started_at"]:
                    elapsed = (datetime.now() - backtest_data["started_at"]).seconds
                    progress = min(elapsed / 30 * 100, 99)
            elif backtest_data["status"] == "completed":
                progress = 100
            
            backtests.append(BacktestStatus(
                backtest_id=backtest_id,
                status=backtest_data["status"],
                progress=progress,
                strategy_name=backtest_data["strategy_name"],
                symbols=backtest_data["symbols"],
                start_date=backtest_data["start_date"],
                end_date=backtest_data["end_date"],
                created_at=backtest_data["created_at"],
                started_at=backtest_data["started_at"],
                completed_at=backtest_data["completed_at"],
                error=backtest_data["error"]
            ))
        
        # Sort by created_at descending
        backtests.sort(key=lambda x: x.created_at, reverse=True)
        
        return backtests[:limit]
        
    except Exception as e:
        logger.error(f"Failed to list backtests: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve backtests"
        )


@router.delete("/{backtest_id}")
async def delete_backtest(
    backtest_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Delete a backtest.
    
    Cannot delete running backtests.
    """
    try:
        if backtest_id not in backtest_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backtest not found: {backtest_id}"
            )
        
        backtest_data = backtest_store[backtest_id]
        
        if backtest_data["status"] == "running":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete a running backtest"
            )
        
        del backtest_store[backtest_id]
        
        return {"message": f"Backtest {backtest_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete backtest: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete backtest"
        )


@router.post("/compare")
async def compare_backtests(
    backtest_ids: List[str],
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Compare multiple backtest results.
    
    Returns side-by-side comparison of key metrics.
    """
    try:
        if len(backtest_ids) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Need at least 2 backtests to compare"
            )
        
        if len(backtest_ids) > 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot compare more than 5 backtests at once"
            )
        
        comparisons = []
        
        for backtest_id in backtest_ids:
            if backtest_id not in backtest_store:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Backtest not found: {backtest_id}"
                )
            
            backtest_data = backtest_store[backtest_id]
            
            if backtest_data["status"] != "completed":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Backtest {backtest_id} is not completed"
                )
            
            result = backtest_data["result"]
            
            comparisons.append({
                "backtest_id": backtest_id,
                "strategy_name": backtest_data["strategy_name"],
                "total_return_pct": result["total_return_pct"],
                "sharpe_ratio": result["sharpe_ratio"],
                "max_drawdown": result["max_drawdown"],
                "win_rate": result["win_rate"],
                "total_trades": result["total_trades"],
                "profit_factor": result["profit_factor"]
            })
        
        # Sort by total return
        comparisons.sort(key=lambda x: x["total_return_pct"], reverse=True)
        
        return {
            "comparison_count": len(comparisons),
            "best_performer": comparisons[0]["strategy_name"],
            "comparisons": comparisons
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compare backtests: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare backtests"
        )