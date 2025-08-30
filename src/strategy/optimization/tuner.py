import asyncio
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

from .objective import ObjectiveConfig, compute_objective_weighted, check_constraints
from ..backtesting.engine import BacktestEngine


@dataclass
class TrialResult:
    params: Dict[str, Any]
    objective: float
    constraints_ok: bool
    metrics: Dict[str, Any]


def _sample_param_value(spec: Dict[str, Any], rng: random.Random):
    if 'choices' in spec:
        return rng.choice(spec['choices'])
    low = spec.get('min')
    high = spec.get('max')
    step = spec.get('step')
    if low is None or high is None:
        raise ValueError("Parameter spec must include min and max or choices")
    if step:
        n_steps = int((high - low) / step)
        k = rng.randint(0, n_steps)
        return low + k * step
    # float uniform
    return rng.uniform(low, high)


def sample_params(parameter_ranges: Dict[str, Dict[str, Any]], n_samples: int, seed: int = 42) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    samples = []
    keys = list(parameter_ranges.keys())
    for _ in range(n_samples):
        params = {}
        for k in keys:
            params[k] = _sample_param_value(parameter_ranges[k], rng)
        samples.append(params)
    return samples


async def evaluate_once(
    strategy_cls,
    params: Dict[str, Any],
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
    engine: BacktestEngine,
    objective_cfg: ObjectiveConfig
) -> TrialResult:
    strategy = strategy_cls(symbols=symbols, **params)
    result = await engine.run_backtest(strategy=strategy, start_date=start_date, end_date=end_date, symbols=symbols)
    objective_value = compute_objective_weighted(result, objective_cfg)
    constraints = check_constraints(result, objective_cfg)
    constraints_ok = all(constraints.values())
    metrics = result.to_dict()
    metrics['constraints'] = constraints
    metrics['objective'] = objective_value
    return TrialResult(params=params, objective=objective_value, constraints_ok=constraints_ok, metrics=metrics)


async def optimize(
    strategy_cls,
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
    parameter_ranges: Dict[str, Dict[str, Any]],
    objective_cfg: Optional[ObjectiveConfig] = None,
    n_initial_samples: int = 20,
    seed: int = 42,
) -> Tuple[Dict[str, Any], TrialResult, List[TrialResult]]:
    """Simple random-search optimizer with constraints filtering.

    Returns best_params, best_trial, all_trials
    """
    if objective_cfg is None:
        objective_cfg = ObjectiveConfig()

    samples = sample_params(parameter_ranges, n_initial_samples, seed)
    engine = BacktestEngine()

    trials: List[TrialResult] = []
    best_trial: Optional[TrialResult] = None

    for params in samples:
        trial = await evaluate_once(strategy_cls, params, symbols, start_date, end_date, engine, objective_cfg)
        trials.append(trial)
        if trial.constraints_ok:
            if best_trial is None or trial.objective > best_trial.objective:
                best_trial = trial

    if best_trial is None:
        # If no trial met constraints, pick the least violating by objective anyway
        best_trial = max(trials, key=lambda t: t.objective)

    return best_trial.params, best_trial, trials

