from dataclasses import dataclass
from typing import Dict


@dataclass
class ObjectiveConfig:
    # Objective weights
    w1: float = 1.0  # annualized return weight
    w2: float = 1.0  # Sharpe weight
    w3: float = 1.0  # MaxDD penalty weight

    # Constraints
    max_dd_limit_pct: float = 15.0   # Maximum Drawdown limit in percent
    turnover_limit_annualized_pct: float = 200.0  # Annualized turnover limit in percent


def compute_objective(result) -> float:
    """Compute objective value based on BacktestResult.

    objective = annualized_return * w1 + sharpe * w2 - max_dd * w3
    """
    return (
        float(getattr(result, 'annualized_return', 0.0)) * 1.0
        + float(getattr(result, 'sharpe_ratio', 0.0)) * 1.0
        - float(getattr(result, 'max_drawdown', 0.0)) * 1.0
    )


def compute_objective_weighted(result, cfg: ObjectiveConfig) -> float:
    return (
        float(getattr(result, 'annualized_return', 0.0)) * cfg.w1
        + float(getattr(result, 'sharpe_ratio', 0.0)) * cfg.w2
        - float(getattr(result, 'max_drawdown', 0.0)) * cfg.w3
    )


def check_constraints(result, cfg: ObjectiveConfig) -> Dict[str, bool]:
    """Check constraints based on BacktestResult.

    Returns a dict of constraint_name -> satisfied(bool).
    """
    satisfied = {}

    max_dd = float(getattr(result, 'max_drawdown', 0.0))
    turnover_annualized_pct = float(getattr(result, 'turnover_annualized_pct', 0.0))

    satisfied['max_drawdown'] = max_dd <= cfg.max_dd_limit_pct
    satisfied['turnover'] = turnover_annualized_pct <= cfg.turnover_limit_annualized_pct

    return satisfied

