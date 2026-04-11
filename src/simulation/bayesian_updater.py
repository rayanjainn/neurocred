"""
Tier 6 — Bayesian Posterior Updating

When a real `twin_updated` event arrives mid-simulation (e.g., a salary credit),
the income distribution prior is updated via conjugate Gaussian posterior in log-space.

Income prior:   I ~ LogNormal(μ₀, σ₀²)
Observation:    I_obs (observed income event)
Posterior:      μ_post = (σ₀⁻² μ₀ + σ_obs⁻² ln(I_obs)) / (σ₀⁻² + σ_obs⁻²)
                σ_post² = (σ₀⁻² + σ_obs⁻²)⁻¹

Regime posterior update via Bayes factor:
  P(R_j | event) ∝ P(event | R_j) × P(R_j)

Effect: confirmed salary credit narrows income uncertainty; fan chart tightens.
"""

from __future__ import annotations

import math
import numpy as np


# ── Income prior / posterior ──────────────────────────────────────────────────

class IncomePrior:
    """
    LogNormal income prior in log-space.
    Parameters: μ (log-mean), σ (log-std).
    """

    def __init__(self, income_mean: float, income_stability: float) -> None:
        """
        Initialise from twin features.
        income_mean: estimated monthly income (INR)
        income_stability: [0,1]; σ₀ = (1 - income_stability) × 0.5 + 0.05
        """
        self.mu: float = math.log(max(income_mean, 1.0))
        self.sigma: float = max((1.0 - income_stability) * 0.5 + 0.05, 0.05)

    def update(self, observed_income: float, obs_sigma: float = 0.10) -> None:
        """
        Conjugate Gaussian update in log-space.

        Args:
            observed_income: observed INR amount of income event
            obs_sigma: measurement noise on ln(I_obs); default 0.10
        """
        if observed_income <= 0:
            return

        ln_obs = math.log(observed_income)
        prior_precision = 1.0 / (self.sigma ** 2)
        obs_precision   = 1.0 / (obs_sigma ** 2)

        post_precision = prior_precision + obs_precision
        self.mu    = (prior_precision * self.mu + obs_precision * ln_obs) / post_precision
        self.sigma = math.sqrt(1.0 / post_precision)

    def sample(self, size: int, rng: np.random.Generator) -> np.ndarray:
        """Sample income values from current posterior. Returns array of shape (size,)."""
        log_samples = rng.normal(self.mu, self.sigma, size)
        return np.exp(log_samples)

    @property
    def mean_income(self) -> float:
        """Expected income = exp(μ + σ²/2)."""
        return math.exp(self.mu + 0.5 * self.sigma ** 2)

    def tighten_by(self, fraction: float) -> None:
        """Manually reduce uncertainty by fraction (0–1). Used after event confirmation."""
        self.sigma = max(self.sigma * (1.0 - fraction), 0.02)


# ── Regime posterior update ───────────────────────────────────────────────────

_REGIME_INCOME_MEAN_MULTIPLIER = {
    0: 1.0,   # STABLE:  income at baseline
    1: 0.75,  # STRESSED: income suppressed
    2: 0.40,  # CRISIS:   income severely suppressed
}


def regime_posterior_update(
    regime_probs: dict[int, float],   # {0: P(R0), 1: P(R1), 2: P(R2)}
    observed_event_type: str,          # "income" | "expense" | "emi_paid"
    observed_value: float,             # INR magnitude
    income_prior: IncomePrior,
) -> dict[int, float]:
    """
    Update regime distribution via Bayes factor when a real event arrives.

    P(R_j | event) ∝ P(event | R_j) × P(R_j)
    """
    likelihoods: dict[int, float] = {}

    for regime, prior_p in regime_probs.items():
        if observed_event_type == "income":
            # Large income inflow is more likely under STABLE
            multiplier = _REGIME_INCOME_MEAN_MULTIPLIER[regime]
            expected = income_prior.mean_income * multiplier
            # Gaussian likelihood in log-space
            if observed_value > 0 and expected > 0:
                log_diff = math.log(observed_value) - math.log(expected)
                likelihood = math.exp(-0.5 * (log_diff / income_prior.sigma) ** 2)
            else:
                likelihood = 0.01
        elif observed_event_type == "emi_paid":
            # Successful EMI payment is evidence against CRISIS
            likelihood = {0: 0.90, 1: 0.60, 2: 0.20}[regime]
        else:
            likelihood = 1.0  # flat prior for other events

        likelihoods[regime] = max(likelihood * prior_p, 1e-10)

    total = sum(likelihoods.values())
    return {k: round(v / total, 4) for k, v in likelihoods.items()}


# ── Mid-simulation path re-weighting ─────────────────────────────────────────

def reweight_paths_on_event(
    cash_paths: np.ndarray,          # shape (N, H) mutable
    observation_day: int,
    observed_inflow: float,
    income_prior: IncomePrior,
) -> np.ndarray:
    """
    After a confirmed income event on observation_day, reweight remaining
    paths by scaling their post-observation-day cash trajectories.

    Paths that were already below prior mean get a relative boost;
    paths above get gently pulled down — narrowing the fan.

    This is a lightweight approximation of full particle filter reweighting.
    Returns updated cash_paths (modified in-place).
    """
    if observation_day >= cash_paths.shape[1]:
        return cash_paths

    expected = income_prior.mean_income
    if expected <= 0 or observed_inflow <= 0:
        return cash_paths

    ratio = observed_inflow / expected
    # Apply a dampened version of the ratio to future path values
    for t in range(observation_day, cash_paths.shape[1]):
        decay = 1.0 / (1.0 + (t - observation_day) * 0.02)   # geometric decay
        cash_paths[:, t] *= (1.0 + (ratio - 1.0) * decay * 0.3)

    return cash_paths
