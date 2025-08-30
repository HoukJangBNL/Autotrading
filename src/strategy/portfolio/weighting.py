from typing import List, Dict
import numpy as np


def _simplex_projection(v: np.ndarray) -> np.ndarray:
    # Euclidean projection onto simplex {w >=0, sum w = 1}
    n = v.shape[0]
    u = np.sort(v)[::-1]
    cssv = np.cumsum(u)
    rho = np.nonzero(u * np.arange(1, n+1) > (cssv - 1))[0][-1]
    theta = (cssv[rho] - 1) / (rho + 1)
    w = np.maximum(v - theta, 0)
    return w


def volatility_targeting(sigmas: np.ndarray, target_vol: float = None) -> np.ndarray:
    inv_vol = 1.0 / np.maximum(sigmas, 1e-8)
    w = inv_vol / inv_vol.sum()
    # optional scaling to target vol at portfolio level can be applied downstream
    return w


def risk_parity(cov: np.ndarray, tol: float = 1e-6, max_iter: int = 1000) -> np.ndarray:
    n = cov.shape[0]
    w = np.ones(n) / n
    for _ in range(max_iter):
        port_var = w @ cov @ w
        mrc = cov @ w  # marginal risk contributions
        rc = w * mrc    # risk contributions
        target = port_var / n
        grad = mrc * 2 * w - target  # heuristic gradient
        w_new = w - 0.01 * grad
        w_new = _simplex_projection(w_new)
        if np.linalg.norm(w_new - w, 1) < tol:
            return w_new
        w = w_new
    return w


def mean_variance_with_dd_penalty(mu: np.ndarray, cov: np.ndarray, dd_penalty: float = 0.0, lr: float = 0.01, iters: int = 200) -> np.ndarray:
    # maximize mu^T w - lambda w^T C w - gamma * DD_penalty(w)
    # here approximate DD penalty by k * sqrt(w^T C w) for simplicity
    n = mu.shape[0]
    lam = 1.0
    gamma = dd_penalty
    w = np.ones(n) / n
    for _ in range(iters):
        grad = mu - 2 * lam * (cov @ w) - 0.5 * gamma * (cov @ w) / max(np.sqrt(w @ cov @ w), 1e-8)
        w = w + lr * grad
        w = _simplex_projection(w)
    return w

