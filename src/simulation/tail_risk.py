"""
Tier 6 — Tail Risk & Fan Chart Outputs

Metrics:
  - VaR₉₅:  max loss at 95th confidence
  - CVaR₉₅: expected loss in worst 5% of paths (Expected Shortfall)
  - Fan chart: p10, p25, p50, p75, p90 daily cash series
  - Net worth delta distribution: mean, p10, p50, p90 at 90d
  - Temporal snapshots at day 30, 60, 90
  - Liquidity crash days (days until cash hits minimum floor)
  - EMI stress score (cascade-weighted)
"""

from __future__ import annotations

import numpy as np


# ── VaR / CVaR ────────────────────────────────────────────────────────────────

def compute_var_cvar(
    cash_paths: np.ndarray,         # shape (N, H)
    cash0: float,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """
    Compute VaR and CVaR at given confidence level.

    Loss L^(k) = C_0 - min_t C_t^(k)  (maximum drawdown per path).

    Returns:
        (var, cvar) both in INR (positive = loss)
    """
    # Maximum drawdown per path
    min_cash = np.min(cash_paths, axis=1)   # shape (N,)
    losses = cash0 - min_cash                # positive when cash drops below initial

    sorted_losses = np.sort(losses)
    n = len(sorted_losses)
    var_idx = int(np.floor(confidence * n))
    var = float(sorted_losses[var_idx])

    # CVaR = mean of losses above VaR
    tail_losses = sorted_losses[var_idx:]
    cvar = float(np.mean(tail_losses)) if len(tail_losses) > 0 else var

    return round(var, 2), round(cvar, 2)


# ── Fan chart ─────────────────────────────────────────────────────────────────

def extract_fan_chart(cash_paths: np.ndarray) -> dict:
    """
    Extract percentile cash series from path matrix.

    Args:
        cash_paths: shape (N, H)

    Returns dict with keys p10, p25, p50, p75, p90 as Python lists of floats.
    """
    percentiles = {
        "p10": 10,
        "p25": 25,
        "p50": 50,
        "p75": 75,
        "p90": 90,
    }
    fan: dict[str, list[float]] = {}
    for key, pct in percentiles.items():
        series = np.percentile(cash_paths, pct, axis=0)
        fan[key] = [round(float(v), 2) for v in series]
    return fan


# ── Temporal snapshots (day 30, 60, 90) ──────────────────────────────────────

def temporal_projection(
    cash_paths: np.ndarray,         # shape (N, H)
    day: int,
    cash0: float,
    monthly_emi_total: float,
    default_threshold: float,       # cash below this = default
) -> dict:
    """
    Cross-sectional snapshot at a specific day.
    Returns dict with default_prob, liquidity_crash, emi_stress, net_worth_delta.
    """
    if day >= cash_paths.shape[1]:
        day = cash_paths.shape[1] - 1

    cash_at_day = cash_paths[:, day]

    # Cumulative default: any path that ever went below default_threshold by day d
    min_so_far = np.min(cash_paths[:, :day + 1], axis=1)
    default_mask = min_so_far < default_threshold
    default_prob = float(np.mean(default_mask))

    # Liquidity crash: days to reach warning threshold from today (approx)
    # For paths not yet crashed, find first day below 0.5 × monthly_emi
    theta = 0.5 * monthly_emi_total
    crash_days_list = []
    for k in range(cash_paths.shape[0]):
        path = cash_paths[k, :day + 1]
        crash = np.where(path < theta)[0]
        if len(crash) > 0:
            crash_days_list.append(int(crash[0]))

    liq_crash_mean = float(np.mean(crash_days_list)) if crash_days_list else None

    # Net worth delta at this day
    nw_deltas = cash_at_day - cash0
    nw_mean = round(float(np.mean(nw_deltas)), 2)

    return {
        "default_probability":       round(default_prob, 4),
        "liquidity_crash_days_mean": round(liq_crash_mean, 1) if liq_crash_mean else None,
        "emi_stress_score":          None,   # set by caller from cascade tracker
        "net_worth_delta_mean":      nw_mean,
    }


def compute_temporal_projections(
    cash_paths: np.ndarray,
    cash0: float,
    monthly_emi_total: float,
    default_threshold: float,
    emi_stress_by_day: dict[int, float] | None = None,
) -> dict:
    """Compute snapshots at day 30, 60, 90."""
    result = {}
    for d in [30, 60, 90]:
        proj = temporal_projection(cash_paths, d - 1, cash0, monthly_emi_total, default_threshold)
        if emi_stress_by_day:
            proj["emi_stress_score"] = emi_stress_by_day.get(d, None)
        result[f"day_{d}"] = proj
    return result


# ── Net worth delta ───────────────────────────────────────────────────────────

def net_worth_delta(cash_paths: np.ndarray, cash0: float) -> dict:
    """Distribution of 90d net position change."""
    final = cash_paths[:, -1]
    deltas = final - cash0
    return {
        "mean": round(float(np.mean(deltas)), 2),
        "p10":  round(float(np.percentile(deltas, 10)), 2),
        "p50":  round(float(np.percentile(deltas, 50)), 2),
        "p90":  round(float(np.percentile(deltas, 90)), 2),
    }


# ── Liquidity crash days ──────────────────────────────────────────────────────

def liquidity_crash_stats(
    cash_paths: np.ndarray,
    monthly_emi_total: float,
) -> dict:
    """
    When does cash hit warning floor (0.5 × monthly_emi)?
    Returns mean, p10, p50, p90 in days.
    """
    theta = 0.5 * monthly_emi_total
    crash_days: list[int] = []
    for k in range(cash_paths.shape[0]):
        hit = np.where(cash_paths[k] < theta)[0]
        if len(hit) > 0:
            crash_days.append(int(hit[0]))

    if not crash_days:
        return {"mean": None, "p10": None, "p50": None, "p90": None}

    arr = np.array(crash_days)
    return {
        "mean": round(float(np.mean(arr)), 1),
        "p10":  int(np.percentile(arr, 10)),
        "p50":  int(np.percentile(arr, 50)),
        "p90":  int(np.percentile(arr, 90)),
    }


# ── EMI stress score ─────────────────────────────────────────────────────────

def emi_stress_score(
    stage_finals: np.ndarray,  # shape (N,) — final cascade stage per path
    n_emi_due_dates: int,
) -> float:
    """
    EMI stress score = (1/N) Σ stage(k) / (4 × M_total)
    Weighted by cascade stage reached; normalised to [0,1].
    """
    if n_emi_due_dates == 0:
        return 0.0
    return float(np.mean(stage_finals) / (4.0 * max(n_emi_due_dates, 1)))


# ── Regime distribution ───────────────────────────────────────────────────────

def regime_distribution_at_day(
    regime_paths: np.ndarray,  # shape (N, H) — int 0/1/2
    day: int,
) -> dict:
    """Regime probability distribution at a specific day."""
    if day >= regime_paths.shape[1]:
        day = regime_paths.shape[1] - 1
    col = regime_paths[:, day]
    n = len(col)
    return {
        "STABLE":   round(float(np.sum(col == 0)) / n, 4),
        "STRESSED": round(float(np.sum(col == 1)) / n, 4),
        "CRISIS":   round(float(np.sum(col == 2)) / n, 4),
    }


# ── Default probability ───────────────────────────────────────────────────────

def default_probability(
    cash_paths: np.ndarray,
    default_threshold: float = 0.0,
) -> float:
    """Fraction of paths that ever went below or reached default_threshold."""
    min_per_path = np.min(cash_paths, axis=1)
    return round(float(np.mean(min_per_path <= default_threshold)), 4)
