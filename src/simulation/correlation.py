"""
Tier 6 — t-Copula Correlated Shock Generator

Shock vector at each daily step:
  ε_t = [ε_income, ε_expense_essential, ε_expense_discretionary, ε_emi_delay]

Correlation matrix Σ is persona-calibrated (baseline: genuine_healthy).
Cholesky decomposition L = chol(Σ) is cached per persona.

Generation:
  z ~ N(0, I)  (or Sobol quasi-random)
  ε = L @ z     → correlated Gaussian shocks
  (t-Copula fat-tail: scale by chi-squared / ν before multiplying by L)

Shock indices:
  0 = income
  1 = essential expense
  2 = discretionary expense
  3 = EMI delay probability
"""

from __future__ import annotations

import numpy as np
from scipy.stats import t as t_dist

# ── Persona correlation matrices (4×4) ──────────────────────────────────────
# Columns/Rows: [income, ess_exp, disc_exp, emi_delay]
# Key insight: income is negatively correlated with expenses + EMI delay

_CORR_GENUINE_HEALTHY = np.array([
    [ 1.00, -0.55, -0.30, -0.40],
    [-0.55,  1.00,  0.62,  0.35],
    [-0.30,  0.62,  1.00,  0.18],
    [-0.40,  0.35,  0.18,  1.00],
], dtype=np.float64)

_CORR_GENUINE_STRUGGLING = np.array([
    [ 1.00, -0.65, -0.40, -0.55],
    [-0.65,  1.00,  0.70,  0.50],
    [-0.40,  0.70,  1.00,  0.30],
    [-0.55,  0.50,  0.30,  1.00],
], dtype=np.float64)

_CORR_SHELL_CIRCULAR = np.array([
    [ 1.00, -0.10,  0.15, -0.20],
    [-0.10,  1.00,  0.80,  0.55],
    [ 0.15,  0.80,  1.00,  0.45],
    [-0.20,  0.55,  0.45,  1.00],
], dtype=np.float64)

_CORR_PAPER_TRADER = np.array([
    [ 1.00, -0.45, -0.50, -0.35],
    [-0.45,  1.00,  0.58,  0.40],
    [-0.50,  0.58,  1.00,  0.25],
    [-0.35,  0.40,  0.25,  1.00],
], dtype=np.float64)

_CORR_NEW_TO_CREDIT = np.array([
    [ 1.00, -0.40, -0.25, -0.30],
    [-0.40,  1.00,  0.50,  0.28],
    [-0.25,  0.50,  1.00,  0.15],
    [-0.30,  0.28,  0.15,  1.00],
], dtype=np.float64)

PERSONA_CORR: dict[str, np.ndarray] = {
    "genuine_healthy":    _CORR_GENUINE_HEALTHY,
    "genuine_struggling": _CORR_GENUINE_STRUGGLING,
    "shell_circular":     _CORR_SHELL_CIRCULAR,
    "paper_trader":       _CORR_PAPER_TRADER,
    "new_to_credit":      _CORR_NEW_TO_CREDIT,
    "unknown":            _CORR_GENUINE_HEALTHY.copy(),
}

_T_COPULA_NU = 4  # degrees of freedom for heavy-tailed joint distribution


def _cholesky(corr: np.ndarray) -> np.ndarray:
    """Nearest positive-definite Cholesky decomposition."""
    # Add tiny jitter for numerical stability
    corr_pd = corr + np.eye(corr.shape[0]) * 1e-8
    return np.linalg.cholesky(corr_pd)


# Pre-compute Cholesky factors for all personas
_CHOLESKY_CACHE: dict[str, np.ndarray] = {
    k: _cholesky(v) for k, v in PERSONA_CORR.items()
}


def get_cholesky(persona: str) -> np.ndarray:
    """Return (cached) lower-triangular Cholesky factor L for persona."""
    if persona not in _CHOLESKY_CACHE:
        corr = PERSONA_CORR.get(persona, PERSONA_CORR["unknown"])
        _CHOLESKY_CACHE[persona] = _cholesky(corr)
    return _CHOLESKY_CACHE[persona]


def generate_correlated_shocks(
    n_paths: int,
    horizon: int,
    persona: str,
    use_t_copula: bool = True,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """
    Generate correlated shocks for all paths and all time steps.

    Returns:
        shocks: float array of shape (n_paths, horizon, 4)
                dim 0 = path, dim 1 = time step, dim 2 = [income, ess, disc, emi]
    """
    if rng is None:
        rng = np.random.default_rng()

    L = get_cholesky(persona)
    # Independent standard normal draws: (n_paths, horizon, 4)
    z = rng.standard_normal((n_paths, horizon, 4))

    if use_t_copula:
        # t-Copula: scale by sqrt(ν / chi²(ν)) to get heavy tails
        chi2 = rng.chisquare(df=_T_COPULA_NU, size=(n_paths, horizon, 1))
        z = z * np.sqrt(_T_COPULA_NU / chi2)

    # Apply Cholesky: shocks[p, t, :] = L @ z[p, t, :]
    # Vectorised: shape (n_paths, horizon, 4) @ (4, 4).T broadcast
    shocks = z @ L.T   # shape (n_paths, horizon, 4)
    return shocks


def generate_sobol_shocks(
    n_sobol_paths: int,
    horizon: int,
    persona: str,
    use_t_copula: bool = True,
    base_seed: int = 0,
) -> np.ndarray:
    """
    Generate correlated shocks using Sobol quasi-random sequences for
    low-discrepancy variance reduction.

    Returns shocks: float array of shape (n_sobol_paths, horizon, 4)
    """
    from scipy.stats.qmc import Sobol
    from scipy.stats import norm

    dim = horizon * 4
    sampler = Sobol(d=dim, scramble=True, seed=base_seed)
    # Sobol samples in [0,1)^dim, shape (n_sobol_paths, dim)
    u = sampler.random(n_sobol_paths)
    # Map uniform → standard normal via inverse CDF
    z_flat = norm.ppf(np.clip(u, 1e-10, 1 - 1e-10))
    z = z_flat.reshape(n_sobol_paths, horizon, 4)

    L = get_cholesky(persona)

    if use_t_copula:
        rng = np.random.default_rng(base_seed + 99999)
        chi2 = rng.chisquare(df=_T_COPULA_NU, size=(n_sobol_paths, horizon, 1))
        z = z * np.sqrt(_T_COPULA_NU / chi2)

    shocks = z @ L.T
    return shocks


def generate_antithetic_pair(shocks: np.ndarray) -> np.ndarray:
    """
    Given shocks of shape (n, horizon, 4), return antithetic counterpart (-shocks).
    Concatenate both to double path count with zero extra sampling cost.
    """
    return -shocks
