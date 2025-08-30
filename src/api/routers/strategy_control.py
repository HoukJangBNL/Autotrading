"""Strategy plugin control endpoints matching target spec.

Provides:
- GET  /strategy/list
- POST /strategy/reload

Initial version stubs PluginLoader/StrategyRegistry to be filled in next milestones.
"""
from __future__ import annotations

from typing import Dict, Any
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/strategy", tags=["strategy-control"])

# Stubs for now; to be replaced with real plugin system
STRATEGY_PLUGINS: Dict[str, Dict[str, Any]] = {}


@router.get("/list")
async def strategy_list():
    # Stub: return in-memory registry
    return {"count": len(STRATEGY_PLUGINS), "strategies": list(STRATEGY_PLUGINS.keys())}


@router.post("/reload")
async def strategy_reload():
    try:
        # TODO: implement PluginLoader to rescan and hot-reload
        return {"ok": True, "reloaded": 0}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

