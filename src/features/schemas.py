"""
Tier 3 — Behavioural Feature Vector schema

18 core features + sliding-window summaries as defined in schema.md §7
and math.md.  All features are float unless noted.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BehaviouralFeatureVector(BaseModel):
    """
    The output of Tier 3 feature engine for a single user at a point in time.
    Pushed to stream:behavioural_features and stored in Redis as
    twin:features:<user_id> for Tier 4 to pick up.
    """

    user_id: str
    computed_at: datetime

    # ── Cash Flow & Liquidity (math.md §1, §2) ───────────────────────────────
    daily_avg_throughput_30d: float          # EMA-weighted avg daily in+out
    cash_buffer_days: float                  # min(30d_inbound / daily_outflow, 90)
    debit_failure_rate_90d: float            # failed_outbound / total_outbound (90d)
    end_of_month_liquidity_dip: float        # avg balance drop last 5 days of month

    # ── Behavioural Ratios (math.md §3) ─────────────────────────────────────
    emi_burden_ratio: float                  # (EMI+subs) / avg_monthly_income
    savings_rate: float                      # (income - essential - discretionary) / income
    income_stability_score: float            # max(0, 1 - CV(income_90d))
    spending_volatility_index: float         # σ(daily_expense) / μ(daily_expense) 90d
    discretionary_ratio: float              # discretionary / total_expense (90d)
    cash_dependency_index: float             # cash_atm_withdrawals / total_outflows (90d)

    # ── Recurrence & Pattern (math.md §4) ───────────────────────────────────
    subscription_count_30d: int              # detected recurring non-EMI outflows
    emi_payment_count_90d: int               # active EMI events
    salary_day_spike_flag: bool              # >25% discretionary spike ±3d of salary
    lifestyle_inflation_trend: float         # MoM % change in discretionary spend
    merchant_category_shift_count: int       # top-5 category changes between 30d buckets

    # ── Anomaly & Concentration (math.md §5) ─────────────────────────────────
    anomaly_flag: bool                       # Isolation Forest / z-score rule
    top3_merchant_concentration: float      # HHI-style: Σ(spend_i / total)² for top 3
    peer_cohort_benchmark_deviation: float  # z-score vs cohort (income band, city, age)

    # ── Sliding-window summaries (7d / 30d / 90d) ───────────────────────────
    # Stored inline for downstream Tier 4 / Tier 6 use
    income_7d: float = 0.0
    income_30d: float = 0.0
    income_90d: float = 0.0
    essential_7d: float = 0.0
    essential_30d: float = 0.0
    essential_90d: float = 0.0
    discretionary_7d: float = 0.0
    discretionary_30d: float = 0.0
    discretionary_90d: float = 0.0
    net_cashflow_7d: float = 0.0
    net_cashflow_30d: float = 0.0
    net_cashflow_90d: float = 0.0

    # ── MSME & Business Features (from CreditIQ integration) ─────────────────
    gstin: Optional[str] = None
    gst_30d_value: float = 0.0
    ewb_30d_value: float = 0.0
    gst_filing_compliance_rate: float = 0.0
    upi_p2m_ratio_30d: float = 0.0
    gst_upi_receivables_gap: float = 0.0
    hsn_entropy_90d: float = 0.0
    statutory_payment_regularity_score: float = 0.0
    temporal_anomaly_flag: float = 0.0
    months_active_gst: int = 0

    # ── Metadata ─────────────────────────────────────────────────────────────
    income_band: Optional[str] = None       # low / mid / high (for peer cohort)
    city_tier: Optional[int] = None
    age_group: Optional[str] = None
    data_completeness_score: float = 1.0    # fraction of expected windows with data


class PeerCohortStats(BaseModel):
    """
    Pre-computed cohort statistics for peer benchmarking.
    Segmented by income_band × city_tier × age_group.
    """

    cohort_key: str          # e.g. "mid_1_26-35"
    n_users: int
    mean_emi_burden: float
    std_emi_burden: float
    mean_savings_rate: float
    std_savings_rate: float
    mean_spending_volatility: float
    std_spending_volatility: float
    mean_cash_buffer: float
    std_cash_buffer: float
    mean_income_stability: float
    std_income_stability: float
