"""Backtest/Optimize control endpoints matching target spec.

Provides:
- POST /backtest/run
- POST /optimize/run
- GET  /backtest/status

These coexist with existing /api/backtest endpoints and Celery tasks.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator

from src.tasks.backtesting import run_backtest_task, batch_backtest, optimize_strategy
from src.tasks.celery_app import celery_app

router = APIRouter(prefix="/backtest", tags=["backtest-control"])


class BacktestRunRequest(BaseModel):
    strategy_ids: Optional[List[str]] = None
    strategy_id: Optional[str] = None
    symbols: List[str]
    start_date: datetime
    end_date: datetime
    parameters: Optional[Dict[str, Any]] = None

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, v: datetime, info):  # type: ignore[override]
        start = info.data.get("start_date")
        if start and v <= start:
            raise ValueError("end_date must be after start_date")
        return v


class OptimizeRunRequest(BaseModel):
    strategy_id: str
    symbols: List[str]
    start_date: datetime
    end_date: datetime
    parameter_ranges: Dict[str, Dict[str, Any]]


@router.post("/run")
async def backtest_run(req: BacktestRunRequest):
    try:
        if req.strategy_ids and req.strategy_id:
            raise HTTPException(status_code=400, detail="Use either strategy_ids or strategy_id, not both")
        if not req.strategy_ids and not req.strategy_id:
            raise HTTPException(status_code=400, detail="Provide strategy_id or strategy_ids")

        if req.strategy_ids:
            # Submit a batch backtest job (Celery group)
            result = batch_backtest.apply_async(
                kwargs=dict(
                    strategy_ids=req.strategy_ids,
                    symbols=req.symbols,
                    start_date=req.start_date.date().isoformat(),
                    end_date=req.end_date.date().isoformat(),
                ),
                queue="backtesting",
            )
            return {"status": "submitted", "job_id": result.id, "mode": "batch"}
        else:
            # Single strategy run
            async_result = run_backtest_task.apply_async(
                kwargs=dict(
                    strategy_id=req.strategy_id,
                    symbols=req.symbols,
                    start_date=req.start_date.date().isoformat(),
                    end_date=req.end_date.date().isoformat(),
                    parameters=req.parameters or {},
                ),
                queue="backtesting",
            )
            return {"status": "submitted", "task_id": async_result.id, "mode": "single"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status")
async def backtest_status(job_id: str = Query(...)):
    try:
        # Inspect Celery GroupResult without blocking
        from celery.result import GroupResult
        result = GroupResult.restore(job_id, app=celery_app)
        if not result:
            return {"status": "not_found", "job_id": job_id}
        total = len(result)
        completed = sum(1 for r in result if r.ready())
        return {
            "status": "ready" if result.ready() else "progress",
            "job_id": job_id,
            "total": total,
            "completed": completed,
            "progress_percent": (completed / total * 100) if total > 0 else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/../optimize/run")
async def optimize_run(req: OptimizeRunRequest):
    try:
        async_result = optimize_strategy.apply_async(
            kwargs=dict(
                strategy_id=req.strategy_id,
                symbols=req.symbols,
                start_date=req.start_date.date().isoformat(),
                end_date=req.end_date.date().isoformat(),
                parameter_ranges=req.parameter_ranges,
            ),
            queue="backtesting",
        )
        return {"status": "submitted", "task_id": async_result.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

