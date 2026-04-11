"""
Tier 6 — GARCH(1,1) Time-Varying Volatility

Equation:
  σ_t² = ω + α · ε_{t-1}² + β · σ_{t-1}²

Persona-calibrated (ω, α, β) parameters.
Constraint: α + β < 1 ensures covariance stationarity.

For `new_to_credit` profiles with short history (<6 months), income paths use
Student-t innovations (ν=4) instead of Gaussian, reflecting epistemic uncertainty.
"""

from __future__ import annotations

import numpy as np

# Persona GARCH parameter table (omega, alpha, beta)
GARCH_PARAMS: dict[str, tuple[float, float, float]] = {
    "genuine_healthy":    (0.0002, 0.05, 0.90),
    "genuine_struggling": (0.0015, 0.18, 0.75),
    "shell_circular":     (0.0030, 0.30, 0.60),
    "paper_trader":       (0.0025, 0.25, 0.68),
    "new_to_credit":      (0.0010, 0.12, 0.80),
    "unknown":            (0.0010, 0.10, 0.85),
}

# Default starting volatility (matches long-run variance = ω / (1 - α - β))
def _long_run_vol(omega: float, alpha: float, beta: float) -> float:
    denom = 1.0 - alpha - beta
    if denom <= 0:
        return 0.05  # safety fallback
    return float(np.sqrt(omega / denom))


def evolve_garch(
    sigma_prev: float,
    epsilon_prev: float,
    omega: float,
    alpha: float,
    beta: float,
) -> float:
    """Single GARCH(1,1) step. Returns σ_t (not σ_t²)."""
    var_t = omega + alpha * (epsilon_prev ** 2) + beta * (sigma_prev ** 2)
    return float(np.sqrt(max(var_t, 1e-10)))


def build_garch_vol_path(
    horizon: int,
    persona: str,
    sigma0: float | None = None,
    seed: int | None = None,
) -> np.ndarray:
    """
    Pre-compute σ_t path for a single simulation path over `horizon` days.
    Returns float array of shape (horizon,).

    The GARCH innovations are internal — the returned path is σ_t, which the
    Monte Carlo engine multiplies against its actual shock draws.
    """
    omega, alpha, beta = GARCH_PARAMS.get(persona, GARCH_PARAMS["unknown"])
    rng = np.random.default_rng(seed)

    if sigma0 is None:
        sigma0 = _long_run_vol(omega, alpha, beta)

    sigmas = np.empty(horizon, dtype=np.float64)
    sigma = sigma0
    epsilon = 0.0   # initialise last shock at 0

    for t in range(horizon):
        sigmas[t] = sigma
        # draw innovation to update sigma for next step
        epsilon = rng.standard_normal() * sigma
        sigma = evolve_garch(sigma, epsilon, omega, alpha, beta)

    return sigmas


def build_garch_vol_matrix(
    n_paths: int,
    horizon: int,
    persona: str,
    sigma0: float | None = None,
    base_seed: int = 0,
) -> np.ndarray:
    """
    Build GARCH σ matrix of shape (n_paths, horizon) for all paths.
    Each path gets a different sub-seed derived from base_seed + path_idx.
    """
    omega, alpha, beta = GARCH_PARAMS.get(persona, GARCH_PARAMS["unknown"])
    if sigma0 is None:
        sigma0 = _long_run_vol(omega, alpha, beta)

    out = np.empty((n_paths, horizon), dtype=np.float64)
    for k in range(n_paths):
        out[k] = build_garch_vol_path(horizon, persona, sigma0=sigma0, seed=base_seed + k)
    return out


def initial_sigma(persona: str) -> float:
    """Convenience: return long-run volatility for persona."""
    omega, alpha, beta = GARCH_PARAMS.get(persona, GARCH_PARAMS["unknown"])
    return _long_run_vol(omega, alpha, beta)
