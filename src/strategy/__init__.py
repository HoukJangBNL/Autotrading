"""Trading strategy module with pluggable strategy framework."""

from .base import BaseStrategy, Signal
from .momentum_breakout import MomentumBreakoutStrategy
from .mean_reversion import MeanReversionStrategy
from .optimizer import StrategyOptimizer

__all__ = [
    'BaseStrategy', 
    'Signal',
    'MomentumBreakoutStrategy',
    'MeanReversionStrategy',
    'StrategyOptimizer'
]