"""Control API for global mode/state management.

Exposes endpoints to set the active mode and query current state.
Matches target spec: /control/mode, /control/state
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal

from src.services.mode_manager import get_mode_manager, Mode

router = APIRouter(prefix="/control", tags=["control"])


class SetModeRequest(BaseModel):
    mode: Literal["data_mining", "backtesting", "trading"]
    message: str | None = None


@router.post("/mode")
async def set_mode(req: SetModeRequest):
    try:
        manager = get_mode_manager()
        state = await manager.set_mode(Mode(req.mode), message=req.message)
        return {"ok": True, "state": state.as_dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/state")
async def get_state():
    manager = get_mode_manager()
    state = await manager.get_state()
    return state.as_dict()

