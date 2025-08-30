"""Bridging helpers connecting ModeManager with EnhancedMiningOrchestrator.

Provides simple coroutine starters for GapFill and Expansion that update the
ModeManager state accordingly. This is an incremental integration; in future
iterations these will dispatch Celery tasks and persist Jobs rows.
"""
from __future__ import annotations

import asyncio
from typing import Optional, List

from src.utils.logger import get_logger
from src.services.mode_manager import get_mode_manager
from src.services.mode_manager import Mode
from src.services.mining_orchestrator_v2 import EnhancedMiningOrchestrator, PhaseManager
from src.models.mining_mode import MiningMode

logger = get_logger(__name__)

# Keep a single background task reference to avoid overlapping runs
_gapfill_task: Optional[asyncio.Task] = None
_expansion_task: Optional[asyncio.Task] = None


async def start_gapfill(days_back: int = 60, symbols: Optional[List[str]] = None) -> str:
    """Start GapFill phase (priority: Phase 1/core symbols).

    Returns a pseudo job id (string) for now.
    """
    global _gapfill_task

    manager = get_mode_manager()
    await manager.set_mode(Mode.DATA_MINING, message="GapFill starting")

    orch = EnhancedMiningOrchestrator()
    if symbols is None:
        pm = PhaseManager()
        symbols = pm.get_symbols_for_mode(MiningMode.GAP_FILLING)

    async def _run():
        try:
            logger.info("GapFill run started")
            await orch.execute_gap_filling_mode(symbols, days_back=days_back)
            state = await manager.get_state()
            state.gapfill_completed = True
            state.expansion_active = False
            state.status = "idle"
            logger.info("GapFill run completed")
        except Exception as e:
            (await manager.get_state()).last_error = str(e)
            logger.exception("GapFill run failed")

    _gapfill_task = asyncio.create_task(_run())
    return "gapfill-queued"


async def start_expansion(days_back: int = 60, priority_limit: Optional[int] = None) -> str:
    """Start Expansion phase using symbol discovery priority ordering.

    Returns a pseudo job id (string) for now.
    """
    global _expansion_task

    manager = get_mode_manager()
    await manager.set_mode(Mode.DATA_MINING, message="Expansion starting")

    orch = EnhancedMiningOrchestrator()
    pm = PhaseManager()
    symbols = pm.get_symbols_for_mode(MiningMode.EXPANSION, priority_limit=priority_limit)

    async def _run():
        try:
            logger.info("Expansion run started")
            (await manager.get_state()).expansion_active = True
            await orch.execute_expansion_mode(symbols, days_back=days_back)
            state = await manager.get_state()
            state.expansion_active = False
            state.status = "idle"
            logger.info("Expansion run completed")
        except Exception as e:
            (await manager.get_state()).last_error = str(e)
            logger.exception("Expansion run failed")

    _expansion_task = asyncio.create_task(_run())
    return "expansion-queued"

