"""Mode Manager for 3-mode state-machine (DataMining → Backtesting → Trading).

This service centralizes the active mode and exposes a simple API for
transitions and state inspection. Initial implementation is in-memory with
hooks for integration with orchestrators and task runners.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
import asyncio

from src.utils.logger import get_logger

logger = get_logger(__name__)


class Mode(str, Enum):
    DATA_MINING = "data_mining"
    BACKTESTING = "backtesting"
    TRADING = "trading"


@dataclass
class ModeState:
    current_mode: Mode = Mode.DATA_MINING
    status: str = "idle"  # idle|running|paused|stopped|error
    last_change: datetime = field(default_factory=datetime.utcnow)
    message: Optional[str] = None

    # DataMining policy/state
    data_policy: str = "gapfill_then_expansion"  # enforced ordering
    gapfill_completed: bool = False
    expansion_active: bool = False

    # Backtesting state
    top_symbols: List[str] = field(default_factory=list)  # selected top 10 symbols
    optimization_job_id: Optional[str] = None

    # Trading state
    paper_trading: bool = True
    active_symbols: List[str] = field(default_factory=list)

    # Misc
    last_error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "current_mode": self.current_mode.value,
            "status": self.status,
            "last_change": self.last_change.isoformat(),
            "message": self.message,
            "data_policy": self.data_policy,
            "gapfill_completed": self.gapfill_completed,
            "expansion_active": self.expansion_active,
            "top_symbols": self.top_symbols,
            "optimization_job_id": self.optimization_job_id,
            "paper_trading": self.paper_trading,
            "active_symbols": self.active_symbols,
            "last_error": self.last_error,
        }


class ModeManager:
    """Singleton manager for global mode/state.

    Thread-safe via asyncio.Lock. In a future iteration this can persist to DB
    (Jobs/Config tables) and publish via WebSocket/SSE.
    """

    _instance: Optional["ModeManager"] = None
    _lock = asyncio.Lock()

    def __init__(self) -> None:
        self._state = ModeState()
        self._transition_lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "ModeManager":
        if cls._instance is None:
            cls._instance = ModeManager()
        return cls._instance

    async def set_mode(self, mode: Mode, *, message: Optional[str] = None) -> ModeState:
        async with self._transition_lock:
            if self._state.current_mode == mode:
                logger.info(f"Mode unchanged: {mode.value}")
                if message:
                    self._state.message = message
                # If mode unchanged but not running, (re)enter to ensure hooks run
                if self._state.status != "running":
                    await self._enter_mode(mode)
                return self._state

            logger.info(f"Mode transition: {self._state.current_mode.value} → {mode.value}")
            self._state.current_mode = mode
            self._state.status = "idle"
            self._state.last_change = datetime.utcnow()
            self._state.message = message
            self._state.last_error = None
            await self._enter_mode(mode)

            return self._state

    async def _enter_mode(self, mode: Mode) -> None:
        """Internal helper to apply per-mode resets and invoke hooks."""
        # Reset per-mode fields
        if mode == Mode.DATA_MINING:
            self._state.gapfill_completed = False
            self._state.expansion_active = False
            # Hook: kick off mining orchestration enforcing GapFill→Expansion
            await self._on_enter_data_mining()
        elif mode == Mode.BACKTESTING:
            self._state.top_symbols = []
            self._state.optimization_job_id = None
            await self._on_enter_backtesting()
        elif mode == Mode.TRADING:
            self._state.active_symbols = self._state.top_symbols[:10]
            await self._on_enter_trading()

    async def get_state(self) -> ModeState:
        return self._state

    # --- Hooks (safe no-op placeholders; integrate orchestrators incrementally) ---
    async def _on_enter_data_mining(self) -> None:
        self._state.status = "running"
        logger.info("DataMining mode activated with policy GapFill→Expansion")
        # TODO: Integrate EnhancedMiningOrchestrator to:
        # 1) fill gaps first across priority symbols
        # 2) switch to expansion automatically
        # 3) update self._state.gapfill_completed/expansion_active

    async def _on_enter_backtesting(self) -> None:
        self._state.status = "running"
        logger.info("Backtesting mode activated: batch evaluation to select top 10 symbols")
        # TODO: dispatch Celery batch backtest job, persist Backtests rows
        # and populate self._state.top_symbols and optimization_job_id

    async def _on_enter_trading(self) -> None:
        self._state.status = "running"
        logger.info("Trading mode activated: start monitoring top symbols and execute signals")
        # TODO: start ExchangeAdapter (paper/live), subscribe to streams and route signals


# Convenience accessor
get_mode_manager = ModeManager.get_instance

