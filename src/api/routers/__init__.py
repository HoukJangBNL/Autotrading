"""API routers initialization."""

from .auth import router as auth_router
from .data import router as data_router
from .strategies import router as strategies_router
from .backtest import router as backtest_router
from .trading import router as trading_router
from .portfolio import router as portfolio_router
from .account import router as account_router
from .data_mining import router as data_mining_router
from .mining import router as mining_router

# New control/data-control routers (optional if modules present)
try:
    from .control import router as control_router  # type: ignore
except Exception:  # pragma: no cover
    control_router = None  # type: ignore

try:
    from .data_control import router as data_control_router  # type: ignore
except Exception:  # pragma: no cover
    data_control_router = None  # type: ignore

__all__ = [
    "auth_router",
    "data_router",
    "strategies_router",
    "backtest_router",
    "trading_router",
    "portfolio_router",
    "account_router",
    "data_mining_router",
    "mining_router",
    "control_router",
    "data_control_router",
]