"""Desktop GUI for trading system monitoring and control."""

from .main_window import TradingDashboard
from .widgets import PositionsWidget, ChartsWidget, StrategyControlWidget

__all__ = ['TradingDashboard', 'PositionsWidget', 'ChartsWidget', 'StrategyControlWidget']