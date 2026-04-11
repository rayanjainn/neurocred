"""
Tier 6 — Regime-Switching Model

Three financial regimes:
  R0 — STABLE:  income_stability > 0.75, cash_buffer > 15d, emi_burden < 0.35
  R1 — STRESSED: cash_buffer 5–15d OR emi_burden 0.35–0.55 OR debit_failure_rate > 0.08
  R2 — CRISIS:  cash_buffer < 5d OR emi_burden > 0.55 OR two consecutive missed EMIs

Transition matrix is persona-calibrated.  At each simulation step, regime_t is sampled
from the matrix.  Active regime gates the volatility multiplier applied to GARCH shocks.
"""

from __future__ import annotations

import numpy as np
from enum import IntEnum
from typing import Literal

PersonaType = Literal[
    "genuine_healthy",
    "genuine_struggling",
    "shell_circular",
    "paper_trader",
    "new_to_credit",
    "unknown",
]


class Regime(IntEnum):
    STABLE   = 0
    STRESSED = 1
    CRISIS   = 2


# Volatility multiplier per regime (applied to GARCH σ_t)
REGIME_SIGMA_MULTIPLIER = {
    Regime.STABLE:   1.0,
    Regime.STRESSED: 1.6,
    Regime.CRISIS:   2.8,
}

# Baseline transition matrix (rows=from, cols=to)
_BASE_TRANSITION = np.array([
    [0.92, 0.07, 0.01],   # STABLE  → STABLE / STRESSED / CRISIS
    [0.25, 0.60, 0.15],   # STRESSED → ...
    [0.05, 0.30, 0.65],   # CRISIS  → ...
], dtype=np.float64)

# Persona-specific overrides (full 3×3 matrices)
_PERSONA_TRANSITION: dict[str, np.ndarray] = {
    "genuine_healthy": np.array([
        [0.95, 0.04, 0.01],
        [0.30, 0.58, 0.12],
        [0.08, 0.32, 0.60],
    ], dtype=np.float64),
    "genuine_struggling": np.array([
        [0.82, 0.14, 0.04],
        [0.18, 0.58, 0.24],
        [0.04, 0.28, 0.68],
    ], dtype=np.float64),
    "shell_circular": np.array([
        [0.70, 0.20, 0.10],
        [0.15, 0.50, 0.35],
        [0.03, 0.22, 0.75],
    ], dtype=np.float64),
    "paper_trader": np.array([
        [0.75, 0.18, 0.07],
        [0.20, 0.52, 0.28],
        [0.04, 0.26, 0.70],
    ], dtype=np.float64),
    "new_to_credit": np.array([
        [0.85, 0.11, 0.04],
        [0.22, 0.58, 0.20],
        [0.05, 0.30, 0.65],
    ], dtype=np.float64),
    "unknown": _BASE_TRANSITION.copy(),
}


def classify_regime(
    cash_buffer_days: float,
    emi_burden_ratio: float,
    debit_failure_rate: float,
    emi_overdue_count: int = 0,
) -> Regime:
    """Deterministic regime classification from current twin features."""
    # CRISIS conditions
    if (
        cash_buffer_days < 5
        or emi_burden_ratio > 0.55
        or emi_overdue_count >= 2
    ):
        return Regime.CRISIS
    # STRESSED conditions
    if (
        cash_buffer_days < 15
        or (0.35 <= emi_burden_ratio <= 0.55)
        or debit_failure_rate > 0.08
    ):
        return Regime.STRESSED
    return Regime.STABLE


def get_transition_matrix(persona: PersonaType) -> np.ndarray:
    """Return persona-calibrated 3×3 transition probability matrix."""
    return _PERSONA_TRANSITION.get(persona, _BASE_TRANSITION).copy()


def sample_next_regime(
    current: Regime,
    transition_matrix: np.ndarray,
    rng: np.random.Generator,
) -> Regime:
    """Sample next regime from the transition matrix row for current regime."""
    probs = transition_matrix[int(current)]
    return Regime(rng.choice(3, p=probs))


def sample_regime_path(
    initial_regime: Regime,
    transition_matrix: np.ndarray,
    horizon: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Generate a full regime path of length `horizon`.
    Returns int array of shape (horizon,), values in {0, 1, 2}.
    """
    path = np.empty(horizon, dtype=np.int8)
    regime = initial_regime
    for t in range(horizon):
        path[t] = int(regime)
        regime = sample_next_regime(regime, transition_matrix, rng)
    return path


def regime_sigma_multipliers(regime_path: np.ndarray) -> np.ndarray:
    """Map regime int path → float σ multiplier array, shape (horizon,)."""
    mults = np.array([REGIME_SIGMA_MULTIPLIER[Regime.STABLE],
                      REGIME_SIGMA_MULTIPLIER[Regime.STRESSED],
                      REGIME_SIGMA_MULTIPLIER[Regime.CRISIS]])
    return mults[regime_path.astype(np.int8)]
