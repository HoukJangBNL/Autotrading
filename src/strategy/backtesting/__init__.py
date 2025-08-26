"""Backtesting module for strategy evaluation."""

from .engine import BacktestEngine, BacktestResult
from .simulator import TradeSimulator

__all__ = [
    'BacktestEngine',
    'BacktestResult',
    'TradeSimulator'
]