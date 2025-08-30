from typing import List, Dict, Any
import json
import numpy as np


def load_all_symbols(limit: int = None) -> List[str]:
    with open('config/all_us_stocks_symbols.json') as f:
        data = json.load(f)
    symbols = data.get('symbols', [])
    if limit:
        symbols = symbols[:limit]
    return symbols


def select_universe_by_liquidity(
    symbols: List[str],
    get_volume_fn,
    min_avg_dollar_volume: float,
    top_n: int = 10
) -> List[str]:
    """Select universe by average dollar volume.

    get_volume_fn(symbols) should return dict symbol -> avg_dollar_volume.
    """
    vols: Dict[str, float] = get_volume_fn(symbols)
    ranked = sorted([s for s in symbols if s in vols], key=lambda s: vols[s], reverse=True)
    return ranked[:top_n]


def diversify_by_correlation(
    returns_matrix: np.ndarray,
    symbols: List[str],
    target_n: int
) -> List[str]:
    """Greedy selection minimizing average correlation."""
    corr = np.corrcoef(returns_matrix, rowvar=False)
    selected: List[int] = []
    remaining = set(range(len(symbols)))
    # start with the least average correlation
    avg_corr = np.mean(np.abs(corr), axis=1)
    first = int(np.argmin(avg_corr))
    selected.append(first)
    remaining.remove(first)

    while len(selected) < target_n and remaining:
        best_idx = None
        best_score = float('inf')
        for i in remaining:
            score = np.mean(np.abs(corr[i, selected]))
            if score < best_score:
                best_score = score
                best_idx = i
        selected.append(best_idx)
        remaining.remove(best_idx)

    return [symbols[i] for i in selected]

