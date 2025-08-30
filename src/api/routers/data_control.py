"""Data control endpoints matching target spec.

Provides:
- POST /data/gapfill
- POST /data/expand
- GET  /data/bars
- GET  /data/status

These run side-by-side with existing /api/data* endpoints.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.services.mining_bridge import start_gapfill, start_expansion
from src.services.mode_manager import get_mode_manager
from src.data.database import DatabaseService
from src.data.models import Candle, Ticker

router = APIRouter(prefix="/data", tags=["data-control"])

db_service = DatabaseService()


class GapfillRequest(BaseModel):
    symbols: Optional[List[str]] = None
    days_back: int = 60


class ExpansionRequest(BaseModel):
    priority_limit: Optional[int] = None
    days_back: int = 60


@router.post("/gapfill")
async def api_gapfill(req: GapfillRequest):
    try:
        job_id = await start_gapfill(days_back=req.days_back, symbols=req.symbols)
        return {"ok": True, "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/expand")
async def api_expand(req: ExpansionRequest):
    try:
        # Enforce policy: GapFill must complete before Expansion
        state = await get_mode_manager().get_state()
        if state.data_policy == "gapfill_then_expansion" and not state.gapfill_completed:
            raise HTTPException(status_code=400, detail="GapFill must complete before Expansion")

        job_id = await start_expansion(days_back=req.days_back, priority_limit=req.priority_limit)
        return {"ok": True, "job_id": job_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/bars")
async def api_bars(
    symbol: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = Query(1000, le=10000)
):
    try:
        if end is None:
            end = datetime.now()
        if start is None:
            start = end - timedelta(days=7)

        # Basic sync DB access for now
        with db_service.get_session() as db:
            ticker = db.query(Ticker).filter(Ticker.symbol == symbol.upper()).first()
            if not ticker:
                return []

            q = (
                db.query(Candle)
                .filter(
                    Candle.ticker_id == ticker.id,
                    Candle.timestamp >= start,
                    Candle.timestamp <= end,
                )
                .order_by(Candle.timestamp.desc())
                .limit(limit)
            )
            rows = q.all()
            return [
                {
                    "timestamp": r.timestamp,
                    "open": float(r.open),
                    "high": float(r.high),
                    "low": float(r.low),
                    "close": float(r.close),
                    "volume": r.volume,
                }
                for r in rows
            ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status")
async def api_data_status():
    state = await get_mode_manager().get_state()
    return state.as_dict()

