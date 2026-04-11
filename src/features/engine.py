"""
Tier 3 — Behavioural Feature Extraction & Trend Engine

Consumes from stream:typed_events (Tier 2 output), computes 18+ features
using Polars rolling windows and the math from math.md, then publishes
BehaviouralFeatureVector to stream:behavioural_features.

Key design choices:
  - Polars lazy frames for memory-efficient rolling aggregation
  - EMA-weighted throughput (half-life 30d) per math.md §B
  - All features computed from in-memory event history per user_id
  - Peer cohort benchmarking via pre-computed Parquet stats
  - Pattern detection: salary-day spikes, lifestyle inflation, category shifts
"""

from __future__ import annotations

import asyncio
import glob
import json
import statistics
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import numpy as np
import polars as pl
import psutil
import redis.asyncio as aioredis
from sklearn.ensemble import IsolationForest
from sklearn.impute import KNNImputer

from config.settings import settings
from src.features.schemas import BehaviouralFeatureVector, PeerCohortStats

RAW_DATA_PATH = Path("data/raw")
FEATURES_PATH = Path("data/features")

STREAM_IN = settings.stream_typed
STREAM_OUT = settings.stream_features
GROUP = settings.cg_feature_engine
CONSUMER = "feature-engine-0"
BLOCK_MS = 2000
BATCH_SIZE = 100

# Maximum events to keep per user in memory (90d at ~15 events/day)
MAX_EVENTS_PER_USER = 4096


# ── peer cohort registry ──────────────────────────────────────────────────────

class PeerCohortRegistry:
    """
    Holds pre-computed cohort statistics loaded from Parquet.
    Falls back to neutral stats if cohort file is absent.
    """

    def __init__(self) -> None:
        self._stats: dict[str, PeerCohortStats] = {}
        self._loaded = False

    def load(self, path: str = settings.peer_cohort_path) -> None:
        p = Path(path)
        if not p.exists():
            self._loaded = True
            return
        df = pl.read_parquet(p)
        for row in df.to_dicts():
            key = row["cohort_key"]
            self._stats[key] = PeerCohortStats(**row)
        self._loaded = True

    def get(self, income_band: str, city_tier: int, age_group: str) -> Optional[PeerCohortStats]:
        key = f"{income_band}_{city_tier}_{age_group}"
        return self._stats.get(key)

    def z_score(
        self,
        value: float,
        mean: float,
        std: float,
    ) -> float:
        if std <= 0:
            return 0.0
        return (value - mean) / std


cohort_registry = PeerCohortRegistry()


# ── per-user event store ──────────────────────────────────────────────────────

class UserEventStore:
    """
    Maintains a bounded deque of enriched events per user.
    Each entry: (timestamp, amount, category, txn_type, status, merchant_name)
    """

    def __init__(self) -> None:
        self._events: deque[tuple[datetime, float, str, str, str, str]] = deque(
            maxlen=MAX_EVENTS_PER_USER
        )

    def push(
        self,
        ts: datetime,
        amount: float,
        category: str,
        txn_type: str,
        status: str,
        merchant: str,
    ) -> None:
        self._events.append((ts, amount, category, txn_type, status, merchant))

    def _filter(self, days: int, ref: datetime) -> list[tuple[datetime, float, str, str, str, str]]:
        cutoff = ref - timedelta(days=days)
        return [(ts, a, c, t, s, m) for ts, a, c, t, s, m in self._events if ts >= cutoff]

    def to_polars(self, days: int = 90, ref: datetime | None = None) -> pl.DataFrame:
        if ref is None:
            ref = datetime.utcnow()
        rows = self._filter(days, ref)
        if not rows:
            return pl.DataFrame(schema={
                "timestamp": pl.Datetime,
                "amount": pl.Float64,
                "category": pl.Utf8,
                "txn_type": pl.Utf8,
                "status": pl.Utf8,
                "merchant": pl.Utf8,
            })
        timestamps, amounts, cats, ttypes, statuses, merchants = zip(*rows)
        return pl.DataFrame({
            "timestamp": list(timestamps),
            "amount": list(amounts),
            "category": list(cats),
            "txn_type": list(ttypes),
            "status": list(statuses),
            "merchant": list(merchants),
        })


# ── EMA helper (math.md §B) ───────────────────────────────────────────────────

def _ema_weighted_sum(
    timestamps: list[datetime],
    values: list[float],
    half_life_days: float,
    ref: datetime,
) -> float:
    if not timestamps:
        return 0.0
    lam = np.log(2) / half_life_days
    result = 0.0
    for ts, v in zip(timestamps, values):
        dt_days = (ref - ts).total_seconds() / 86400.0
        result += v * np.exp(-lam * max(0.0, dt_days))
    return float(result)


def _ema_weighted_count(
    timestamps: list[datetime],
    half_life_days: float,
    ref: datetime,
) -> float:
    if not timestamps:
        return 0.0
    lam = np.log(2) / half_life_days
    result = 0.0
    for ts in timestamps:
        dt_days = (ref - ts).total_seconds() / 86400.0
        result += np.exp(-lam * max(0.0, dt_days))
    return float(result)


# ── feature computation ───────────────────────────────────────────────────────

def _safe_cv(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mu = statistics.mean(values)
    if mu == 0:
        return 0.0
    return statistics.stdev(values) / abs(mu)


def compute_features(
    store: UserEventStore,
    ref: datetime,
    income_band: str = "mid",
    city_tier: int = 2,
    age_group: str = "26-35",
) -> BehaviouralFeatureVector:
    """
    Compute all Tier 3 features from the user's event store.
    Math references: math.md §1–§5.
    """

    df90 = store.to_polars(90, ref)
    df30 = store.to_polars(30, ref)
    df7  = store.to_polars(7,  ref)

    # helper: sum amounts by condition
    def _sum_type(df: pl.DataFrame, txn_type: str) -> float:
        if df.is_empty():
            return 0.0
        sub = df.filter(pl.col("txn_type") == txn_type)
        return float(sub["amount"].sum()) if not sub.is_empty() else 0.0

    def _sum_abs_type(df: pl.DataFrame, txn_type: str) -> float:
        return abs(_sum_type(df, txn_type))

    def _sum_abs_types(df: pl.DataFrame, types: list[str]) -> float:
        return sum(_sum_abs_type(df, t) for t in types)

    # ── 7d / 30d / 90d aggregates ────────────────────────────────────────────
    income_7d   = _sum_abs_type(df7,  "INCOME")
    income_30d  = _sum_abs_type(df30, "INCOME")
    income_90d  = _sum_abs_type(df90, "INCOME")

    essential_7d   = _sum_abs_type(df7,  "EXPENSE_ESSENTIAL")
    essential_30d  = _sum_abs_type(df30, "EXPENSE_ESSENTIAL")
    essential_90d  = _sum_abs_type(df90, "EXPENSE_ESSENTIAL")

    disc_7d   = _sum_abs_type(df7,  "EXPENSE_DISCRETIONARY")
    disc_30d  = _sum_abs_type(df30, "EXPENSE_DISCRETIONARY")
    disc_90d  = _sum_abs_type(df90, "EXPENSE_DISCRETIONARY")

    emi_30d  = _sum_abs_type(df30, "EMI_PAYMENT")
    emi_90d  = _sum_abs_type(df90, "EMI_PAYMENT")
    subs_30d = _sum_abs_type(df30, "SUBSCRIPTION")

    total_expense_90d = essential_90d + disc_90d + emi_90d

    net_7d  = income_7d  - essential_7d  - disc_7d
    net_30d = income_30d - essential_30d - disc_30d - emi_30d - subs_30d
    net_90d = income_90d - essential_90d - disc_90d - emi_90d

    # ── daily avg throughput (30d EMA, math.md §1) ────────────────────────────
    if not df30.is_empty():
        ts_list = df30["timestamp"].to_list()
        amt_list = [abs(v) for v in df30["amount"].to_list()]
        daily_avg_throughput = _ema_weighted_sum(ts_list, amt_list, 30.0, ref) / 30.0
    else:
        daily_avg_throughput = 0.0

    # ── cash buffer days (math.md §2) ─────────────────────────────────────────
    avg_inbound_30d = income_30d
    daily_outflow_30d = (essential_30d + disc_30d + emi_30d + subs_30d) / 30.0
    if daily_outflow_30d > 0:
        cash_buffer = min(avg_inbound_30d / daily_outflow_30d, 90.0)
    else:
        cash_buffer = 90.0

    # ── debit failure rate 90d ────────────────────────────────────────────────
    if not df90.is_empty():
        outbound = df90.filter(pl.col("amount") < 0)
        if not outbound.is_empty():
            failed = outbound.filter(pl.col("status") == "FAILED")
            debit_failure_rate = len(failed) / len(outbound)
        else:
            debit_failure_rate = 0.0
    else:
        debit_failure_rate = 0.0

    # ── end-of-month liquidity dip (math.md §2) ───────────────────────────────
    eom_dip = _compute_eom_dip(store, ref)

    # ── EMI burden ratio (math.md §3) ────────────────────────────────────────
    avg_monthly_income = income_30d if income_30d > 0 else max(income_90d / 3, 1.0)
    emi_burden = (emi_30d + subs_30d) / avg_monthly_income if avg_monthly_income > 0 else 0.0

    # ── savings rate ──────────────────────────────────────────────────────────
    if income_30d > 0:
        savings_rate = (income_30d - essential_30d - disc_30d) / income_30d
    else:
        savings_rate = 0.0
    savings_rate = float(np.clip(savings_rate, -1.0, 1.0))

    # ── income stability score (math.md §3) ──────────────────────────────────
    income_stability = _income_stability(df90)

    # ── spending volatility index (math.md §3) ───────────────────────────────
    spending_volatility = _spending_volatility(df90, ref)

    # ── discretionary ratio ───────────────────────────────────────────────────
    disc_ratio = disc_90d / total_expense_90d if total_expense_90d > 0 else 0.0

    # ── cash dependency index ─────────────────────────────────────────────────
    if not df90.is_empty():
        cash_atm = float(
            df90.filter(pl.col("category") == "CASH_ATM")["amount"].abs().sum()
        )
        total_outflows = float(
            df90.filter(pl.col("amount") < 0)["amount"].abs().sum()
        )
        cash_dep = cash_atm / total_outflows if total_outflows > 0 else 0.0
    else:
        cash_dep = 0.0

    # ── subscription & EMI counts ─────────────────────────────────────────────
    sub_count_30d = int(
        df30.filter(pl.col("txn_type") == "SUBSCRIPTION").shape[0]
    ) if not df30.is_empty() else 0

    emi_count_90d = int(
        df90.filter(pl.col("txn_type") == "EMI_PAYMENT").shape[0]
    ) if not df90.is_empty() else 0

    # ── salary-day spike flag (math.md §4) ───────────────────────────────────
    salary_spike = _detect_salary_spike(df90, ref)

    # ── lifestyle inflation trend (math.md §4) ────────────────────────────────
    lifestyle_trend = _lifestyle_inflation(store, ref)

    # ── merchant category shift count (math.md §4) ────────────────────────────
    cat_shift = _category_shift_count(store, ref)

    # ── anomaly flag ──────────────────────────────────────────────────────────
    anomaly = bool(
        (not df90.is_empty()) and
        df90.filter(pl.col("status") == "FAILED").shape[0] > 2
    )

    # ── top-3 merchant concentration (math.md §3 HHI) ────────────────────────
    top3_conc = _top3_concentration(df90)

    # ── peer cohort deviation ─────────────────────────────────────────────────
    peer_z = _peer_deviation(emi_burden, income_band, city_tier, age_group)

    return BehaviouralFeatureVector(
        user_id="",  # caller fills this in
        computed_at=ref,
        daily_avg_throughput_30d=round(daily_avg_throughput, 4),
        cash_buffer_days=round(cash_buffer, 4),
        debit_failure_rate_90d=round(debit_failure_rate, 4),
        end_of_month_liquidity_dip=round(eom_dip, 4),
        emi_burden_ratio=round(float(np.clip(emi_burden, 0.0, 5.0)), 4),
        savings_rate=round(savings_rate, 4),
        income_stability_score=round(income_stability, 4),
        spending_volatility_index=round(spending_volatility, 4),
        discretionary_ratio=round(float(np.clip(disc_ratio, 0.0, 1.0)), 4),
        cash_dependency_index=round(float(np.clip(cash_dep, 0.0, 1.0)), 4),
        subscription_count_30d=sub_count_30d,
        emi_payment_count_90d=emi_count_90d,
        salary_day_spike_flag=salary_spike,
        lifestyle_inflation_trend=round(float(np.clip(lifestyle_trend, -1.0, 5.0)), 4),
        merchant_category_shift_count=cat_shift,
        anomaly_flag=anomaly,
        top3_merchant_concentration=round(float(np.clip(top3_conc, 0.0, 1.0)), 4),
        peer_cohort_benchmark_deviation=round(peer_z, 4),
        income_7d=round(income_7d, 2),
        income_30d=round(income_30d, 2),
        income_90d=round(income_90d, 2),
        essential_7d=round(essential_7d, 2),
        essential_30d=round(essential_30d, 2),
        essential_90d=round(essential_90d, 2),
        discretionary_7d=round(disc_7d, 2),
        discretionary_30d=round(disc_30d, 2),
        discretionary_90d=round(disc_90d, 2),
        net_cashflow_7d=round(net_7d, 2),
        net_cashflow_30d=round(net_30d, 2),
        net_cashflow_90d=round(net_90d, 2),
        income_band=income_band,
        city_tier=city_tier,
        age_group=age_group,
    )


def compute_features_msme(
    store: UserEventStore,
    ref: datetime,
    gst_g: pl.DataFrame,
    ewb_g: pl.DataFrame,
    income_band: str = "mid",
    city_tier: int = 2,
    age_group: str = "26-35",
) -> BehaviouralFeatureVector:
    """
    Extensions for MSME Feature Engineering.
    Combines retail behavioral features with GST/EWB signals.
    """
    # 1. Base retail features
    fv = compute_features(store, ref, income_band, city_tier, age_group)

    # 2. MSME specific features
    gstin = None
    if not gst_g.is_empty():
        gstin = gst_g["gstin"][0]
        gst_now = gst_g["timestamp"].max()
        if isinstance(gst_now, str): gst_now = datetime.fromisoformat(gst_now)
        
        # EMA GST value 30d
        gst_ts = [datetime.fromisoformat(t) if isinstance(t, str) else t for t in gst_g["timestamp"].to_list()]
        gst_vals = gst_g["taxable_value"].to_list()
        fv.gst_30d_value = round(_ema_weighted_sum(gst_ts, gst_vals, 30.0, gst_now), 2)
        
        # Filing compliance
        fv.gst_filing_compliance_rate = round(gst_g.filter(pl.col("filing_status") == "ontime").height / max(len(gst_g), 1), 4)
        fv.months_active_gst = gst_g.select(pl.col("timestamp").str.slice(0, 7) if gst_g["timestamp"].dtype == pl.Utf8 else pl.col("timestamp").dt.truncate("1mo")).unique().height

        # Regularity score
        avg_delay = float(gst_g["filing_delay_days"].mean() or 0.0)
        fv.statutory_payment_regularity_score = round(max(0.0, 1.0 - min(avg_delay / 30.0, 1.0)), 4)
    
    fv.gstin = gstin

    if not ewb_g.is_empty():
        ewb_now = ewb_g["timestamp"].max()
        if isinstance(ewb_now, str): ewb_now = datetime.fromisoformat(ewb_now)
        ewb_ts = [datetime.fromisoformat(t) if isinstance(t, str) else t for t in ewb_g["timestamp"].to_list()]
        ewb_vals = ewb_g["tot_inv_value"].to_list()
        fv.ewb_30d_value = round(_ema_weighted_sum(ewb_ts, ewb_vals, 30.0, ewb_now), 2)
        
        # HSN Entropy
        hsn_counts = ewb_g.group_by("main_hsn_code").agg(pl.len().alias("cnt"))
        shares = (hsn_counts["cnt"] / len(ewb_g)).to_numpy()
        fv.hsn_entropy_90d = round(float(-np.sum(shares * np.log(shares + 1e-9))), 4)

    # UPI P2M Ratio (Business logic)
    df30 = store.to_polars(30, ref)
    if not df30.is_empty():
        # We don't have P2M flag in UserEventStore yet, but we can approximate by merchant presence
        # Actually in generator we set txn_type P2M for some.
        # Let's assume for now.
        inbound = df30.filter(pl.col("amount") > 0)
        if not inbound.is_empty():
             # Approximating P2M from merchant name if it looks like a business
             # In our case, we'll just check if txn_type was passed (from classifier or direct)
             p2m = inbound.filter(pl.col("txn_type") == "P2M")
             fv.upi_p2m_ratio_30d = round(len(p2m) / len(inbound), 4)
             
             # Receivables gap
             inbound_ema = _ema_weighted_sum(inbound["timestamp"].to_list(), inbound["amount"].to_list(), 30.0, ref)
             if fv.gst_30d_value > 0:
                 fv.gst_upi_receivables_gap = round((fv.gst_30d_value - inbound_ema) / fv.gst_30d_value, 4)

    return fv


# ── sub-computations ──────────────────────────────────────────────────────────

def _compute_eom_dip(store: UserEventStore, ref: datetime) -> float:
    """
    math.md §2: avg(balance_EOM - balance_25th) over available months.
    Approximated from daily net-cashflow pattern.
    """
    df = store.to_polars(90, ref)
    if df.is_empty():
        return 0.0
    # add date columns
    df = df.with_columns([
        pl.col("timestamp").dt.day().alias("day"),
        pl.col("timestamp").dt.month().alias("month"),
    ])
    dips = []
    for month in df["month"].unique().to_list():
        month_df = df.filter(pl.col("month") == month)
        late = month_df.filter(pl.col("day") >= 25)
        early = month_df.filter(pl.col("day") < 25)
        if not late.is_empty() and not early.is_empty():
            late_net = float(late["amount"].sum())
            early_net = float(early["amount"].sum())
            dips.append(late_net - early_net)
    return statistics.mean(dips) if dips else 0.0


def _income_stability(df: pl.DataFrame) -> float:
    """math.md §3: max(0, 1 - CV(income_90d))"""
    if df.is_empty():
        return 0.5
    income_rows = df.filter(pl.col("txn_type") == "INCOME")
    if income_rows.is_empty():
        return 0.3
    amounts = income_rows["amount"].to_list()
    if len(amounts) < 2:
        return 0.8
    cv = _safe_cv(amounts)
    return float(np.clip(1.0 - cv, 0.0, 1.0))


def _spending_volatility(df: pl.DataFrame, ref: datetime) -> float:
    """math.md §3: σ(daily_expense) / μ(daily_expense) over 90d"""
    if df.is_empty():
        return 0.0
    expense = df.filter(
        (pl.col("txn_type").is_in(["EXPENSE_ESSENTIAL", "EXPENSE_DISCRETIONARY", "EMI_PAYMENT"])) &
        (pl.col("amount") < 0)
    )
    if expense.is_empty():
        return 0.0
    expense = expense.with_columns([
        pl.col("timestamp").dt.date().alias("date")
    ])
    daily = expense.group_by("date").agg(pl.col("amount").abs().sum().alias("daily_spend"))
    vals = daily["daily_spend"].to_list()
    return _safe_cv(vals)


def _detect_salary_spike(df: pl.DataFrame, ref: datetime) -> bool:
    """
    math.md §4: flag if avg discretionary spend ±3d of salary day
    is >25% above baseline.
    """
    if df.is_empty():
        return False
    salary_rows = df.filter(pl.col("txn_type") == "INCOME")
    if salary_rows.is_empty():
        return False

    salary_dates = [ts.date() for ts in salary_rows["timestamp"].to_list()]
    disc_rows = df.filter(pl.col("txn_type") == "EXPENSE_DISCRETIONARY")
    if disc_rows.is_empty():
        return False

    disc_amounts = {
        ts.date(): abs(amt)
        for ts, amt in zip(disc_rows["timestamp"].to_list(), disc_rows["amount"].to_list())
    }

    window_spends = []
    baseline_spends = []
    for d, amt in disc_amounts.items():
        near_salary = any(abs((d - sd).days) <= 3 for sd in salary_dates)
        if near_salary:
            window_spends.append(amt)
        else:
            baseline_spends.append(amt)

    if not window_spends or not baseline_spends:
        return False
    window_avg = statistics.mean(window_spends)
    baseline_avg = statistics.mean(baseline_spends)
    return bool(baseline_avg > 0 and (window_avg - baseline_avg) / baseline_avg > 0.25)


def _lifestyle_inflation(store: UserEventStore, ref: datetime) -> float:
    """
    math.md §4: MoM % change in discretionary spending.
    Compares most recent full month vs previous month.
    """
    cur_month_disc = 0.0
    prev_month_disc = 0.0

    cur_start = (ref.replace(day=1) - timedelta(days=1)).replace(day=1)  # first of prev month
    prev_start = (cur_start - timedelta(days=1)).replace(day=1)

    for ts, amt, cat, ttype, _, _ in store._events:
        if ttype != "EXPENSE_DISCRETIONARY":
            continue
        if cur_start <= ts < ref:
            cur_month_disc += abs(amt)
        elif prev_start <= ts < cur_start:
            prev_month_disc += abs(amt)

    if prev_month_disc == 0:
        return 0.0
    return (cur_month_disc - prev_month_disc) / prev_month_disc


def _category_shift_count(store: UserEventStore, ref: datetime) -> int:
    """
    math.md §4: count changes in top-5 spending categories
    between consecutive 30d buckets.
    """
    def top5(rows: list) -> set[str]:
        totals: dict[str, float] = defaultdict(float)
        for _, amt, cat, ttype, _, _ in rows:
            if ttype not in ("INCOME", "TRANSFER"):
                totals[cat] += abs(amt)
        sorted_cats = sorted(totals, key=lambda c: totals[c], reverse=True)
        return set(sorted_cats[:5])

    current_end = ref
    current_start = ref - timedelta(days=30)
    prev_end = current_start
    prev_start = prev_end - timedelta(days=30)

    cur_events = [(ts, a, c, t, s, m) for ts, a, c, t, s, m in store._events
                  if current_start <= ts < current_end]
    prev_events = [(ts, a, c, t, s, m) for ts, a, c, t, s, m in store._events
                   if prev_start <= ts < prev_end]

    if not cur_events or not prev_events:
        return 0

    cur_top5 = top5(cur_events)
    prev_top5 = top5(prev_events)
    return len(cur_top5.symmetric_difference(prev_top5))


def _top3_concentration(df: pl.DataFrame) -> float:
    """math.md §3 HHI: Σ(spend_i / total)² for top-3 merchants."""
    if df.is_empty():
        return 0.0
    expense = df.filter(pl.col("amount") < 0)
    if expense.is_empty():
        return 0.0
    merchant_totals = (
        expense
        .with_columns(pl.col("amount").abs().alias("abs_amount"))
        .group_by("merchant")
        .agg(pl.col("abs_amount").sum().alias("total"))
        .sort("total", descending=True)
    )
    total_spend = float(merchant_totals["total"].sum())
    if total_spend == 0:
        return 0.0
    top3 = merchant_totals.head(3)["total"].to_list()
    return sum((v / total_spend) ** 2 for v in top3)


def _peer_deviation(
    emi_burden: float,
    income_band: str,
    city_tier: int,
    age_group: str,
) -> float:
    """math.md §5: z-score of emi_burden vs cohort."""
    stats = cohort_registry.get(income_band, city_tier, age_group)
    if stats is None:
        return 0.0
    return cohort_registry.z_score(emi_burden, stats.mean_emi_burden, stats.std_emi_burden)


# ── stream worker ─────────────────────────────────────────────────────────────

class FeatureEngine:
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client
        self._stores: dict[str, UserEventStore] = defaultdict(UserEventStore)
        self._meta: dict[str, dict[str, Any]] = {}  # income_band, city_tier, age_group

    def _ingest(self, fields: dict[str, str]) -> None:
        """Parse a typed event from Redis and push into user store."""
        try:
            ts_raw = fields.get("timestamp", "")
            ts = datetime.fromisoformat(ts_raw) if ts_raw else datetime.utcnow()
            amount = float(fields.get("amount", "0") or "0")
            category = fields.get("merchant_category") or "OTHER"
            txn_type = fields.get("transaction_type") or "OTHER"
            status = fields.get("status", "SUCCESS") or "SUCCESS"
            merchant = fields.get("merchant_name", "") or ""
            user_id = fields.get("user_id", "") or ""

            if not user_id:
                return

            self._stores[user_id].push(ts, amount, category, txn_type, status, merchant)

            # update meta from first occurrence
            if user_id not in self._meta:
                self._meta[user_id] = {
                    "income_band": "mid",
                    "city_tier": 2,
                    "age_group": "26-35",
                }
        except Exception:
            pass

    async def _publish_features(self, user_id: str, fv: BehaviouralFeatureVector) -> None:
        fv.user_id = user_id
        payload: dict[str, str] = {}
        for k, v in fv.model_dump().items():
            if isinstance(v, datetime):
                payload[k] = v.isoformat()
            elif isinstance(v, bool):
                payload[k] = "1" if v else "0"
            elif v is None:
                payload[k] = ""
            else:
                payload[k] = str(v)

        await self.redis.xadd(
            STREAM_OUT, payload,
            maxlen=settings.stream_maxlen, approximate=True
        )
        # also cache under twin:features:<user_id>
        await self.redis.set(
            f"twin:features:{user_id}",
            json.dumps(payload),
        )

    async def process_batch(
        self,
        messages: list[tuple[str, dict[str, str]]],
    ) -> int:
        """Ingest typed events, recompute features for affected users, publish."""
        affected: set[str] = set()
        for _mid, fields in messages:
            uid = fields.get("user_id", "")
            if uid:
                self._ingest(fields)
                affected.add(uid)

        ref = datetime.utcnow()
        for uid in affected:
            meta = self._meta.get(uid, {})
            fv = compute_features(
                self._stores[uid],
                ref,
                income_band=meta.get("income_band", "mid"),
                city_tier=int(meta.get("city_tier", 2)),
                age_group=meta.get("age_group", "26-35"),
            )
            await self._publish_features(uid, fv)

        return len(messages)


async def run_feature_engine() -> None:
    """Long-running worker consuming stream:typed_events."""
    client = aioredis.from_url(settings.redis_url, decode_responses=True)

    try:
        await client.xgroup_create(STREAM_IN, GROUP, id="0", mkstream=True)
    except aioredis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise

    # load peer cohort stats
    cohort_registry.load()

    engine = FeatureEngine(client)
    total = 0
    print(f"[feature-engine] listening on {STREAM_IN} group={GROUP}")

    while True:
        result = await client.xreadgroup(
            GROUP, CONSUMER,
            {STREAM_IN: ">"},
            count=BATCH_SIZE,
            block=BLOCK_MS,
        )
        if not result:
            continue

        for _stream, messages in result:
            n = await engine.process_batch(messages)
            total += n
            if total % 2000 == 0:
                print(f"[feature-engine] processed {total:,} typed events")

            ids = [msg[0] for msg in messages]
            if ids:
                await client.xack(STREAM_IN, GROUP, *ids)


# ── offline batch engine (Phase 3) ───────────────────────────────────────────

def _load_raw_parquets(prefix: str) -> pl.DataFrame:
    """Scan all chunk parquets for a given source prefix from data/raw/."""
    pattern = str(RAW_DATA_PATH / f"{prefix}_chunk_*.parquet")
    files = glob.glob(pattern)
    if not files:
        return pl.DataFrame()
    frames = [pl.read_parquet(f) for f in sorted(files)]
    return pl.concat(frames, how="diagonal")


def _check_memory_pressure(spill_threshold_gb: float = 3.0) -> bool:
    """True if process RSS exceeds 90% of spill_threshold_gb."""
    proc = psutil.Process()
    rss_gb = proc.memory_info().rss / (1024 ** 3)
    return rss_gb >= spill_threshold_gb * 0.9


def _build_user_store_from_df(rows: pl.DataFrame) -> UserEventStore:
    """Populate a UserEventStore from a slice of the merged raw events frame."""
    store = UserEventStore()
    for row in rows.sort("timestamp").iter_rows(named=True):
        ts_raw = row.get("timestamp") or row.get("event_time")
        if ts_raw is None:
            continue
        if isinstance(ts_raw, str):
            ts = datetime.fromisoformat(ts_raw)
        else:
            ts = ts_raw
        amount = float(row.get("amount", 0) or 0)
        merchant = str(row.get("merchant_name", "") or "")
        status = str(row.get("status", "SUCCESS") or "SUCCESS")
        # categorize using lightweight rule map (avoid loading MiniLM in batch)
        txn_type = str(row.get("txn_type", "") or "")
        category = str(row.get("category", "") or "OTHER")
        if not txn_type:
            if amount > 0:
                txn_type = "INCOME"
            elif "EMI" in merchant.upper() or "LOAN" in merchant.upper():
                txn_type = "EMI_PAYMENT"
            else:
                txn_type = "EXPENSE_ESSENTIAL"
        store.push(ts, amount, category, txn_type, status, merchant)
    return store


def _apply_knn_imputer(df: pl.DataFrame, ref_cols: list[str], target_cols: list[str]) -> pl.DataFrame:
    """
    KNNImputer on target_cols using ref_cols as reference (n_neighbors = min(5, n)).
    Mirrors CreditIQ's fill-missing-GST-fields-using-UPI pattern.
    """
    all_cols = list(dict.fromkeys(ref_cols + target_cols))
    existing = [c for c in all_cols if c in df.columns]
    if not existing:
        return df

    sub = df.select(existing).to_numpy().astype(np.float32)
    n = sub.shape[0]
    if n < 2:
        return df

    imputer = KNNImputer(n_neighbors=min(5, n))
    imputed = imputer.fit_transform(sub)

    fill_exprs = [
        pl.Series(col, imputed[:, i]).alias(col)
        for i, col in enumerate(existing)
        if col in target_cols
    ]
    if fill_exprs:
        df = df.with_columns(fill_exprs)
    return df


def _apply_isolation_forest(df: pl.DataFrame, cadence_cols: list[str]) -> pl.DataFrame:
    """
    IsolationForest on cadence features → temporal_anomaly_flag.
    contamination=0.05, random_state=42. Mirrors CreditIQ exactly.
    """
    existing = [c for c in cadence_cols if c in df.columns]
    if not existing or len(df) < 10:
        return df.with_columns(pl.lit(0).alias("temporal_anomaly_flag"))

    X = df.select(existing).fill_null(0.0).to_numpy().astype(np.float32)
    iso = IsolationForest(contamination=0.05, random_state=42)
    labels = iso.fit_predict(X)  # -1 = anomaly, 1 = normal
    flags = (labels == -1).astype(np.int32)
    return df.with_columns(pl.Series("temporal_anomaly_flag", flags))


def run_batch(
    raw_dir: str = "data/raw",
    features_dir: str = "data/features",
    reference_date: datetime | None = None,
) -> None:
    """
    Phase 3 offline batch entry point.
    Reads all data/raw/*.parquet chunks, computes 18 behavioural features
    per user using EMA weights, applies KNNImputer + IsolationForest,
    writes data/features/user_id=<uid>/features.parquet.
    Mirrors CreditIQ's FeatureEngine.compute_batch() exactly.
    """
    global RAW_DATA_PATH, FEATURES_PATH
    RAW_DATA_PATH = Path(raw_dir)
    FEATURES_PATH = Path(features_dir)
    ref = reference_date or datetime(2026, 4, 11)

    print("[batch-engine] loading raw parquets ...")
    bank_df = _load_raw_parquets("bank")
    upi_df  = _load_raw_parquets("upi")
    sms_df  = _load_raw_parquets("sms")   # used to augment failure signals below
    emi_df  = _load_raw_parquets("emi")
    ob_df   = _load_raw_parquets("open_banking")
    gst_df  = _load_raw_parquets("gst_invoices")
    ewb_df  = _load_raw_parquets("eway_bills")

    # unify bank + UPI into a single events frame
    frames = []
    if not bank_df.is_empty():
        bank_slim = bank_df.select([
            pl.col("user_id"),
            pl.col("timestamp"),
            pl.col("amount"),
            pl.col("merchant_name"),
            pl.col("status"),
            pl.lit("").alias("txn_type"),
            pl.lit("OTHER").alias("category"),
        ])
        frames.append(bank_slim)
    if not upi_df.is_empty():
        upi_slim = upi_df.select([
            pl.col("user_id"),
            pl.col("timestamp"),
            pl.col("amount"),
            pl.col("merchant_name").alias("merchant_name"),
            pl.col("status"),
            pl.lit("").alias("txn_type"),
            pl.lit("OTHER").alias("category"),
        ])
        frames.append(upi_slim)

    if not emi_df.is_empty():
        # EMI schedules — map each payment as a negative EMI_PAYMENT event
        emi_cols = {"user_id", "timestamp", "amount", "merchant_name", "status"}
        if emi_cols.issubset(set(emi_df.columns)):
            emi_slim = emi_df.select([
                pl.col("user_id"),
                pl.col("timestamp"),
                pl.col("amount"),
                pl.col("merchant_name"),
                pl.col("status"),
                pl.lit("EMI_PAYMENT").alias("txn_type"),
                pl.lit("EMI").alias("category"),
            ])
            frames.append(emi_slim)

    if not ob_df.is_empty():
        # Open banking daily balance snapshots — treat as zero-amount balance events
        ob_required = {"user_id", "timestamp"}
        if ob_required.issubset(set(ob_df.columns)):
            ob_slim = ob_df.select([
                pl.col("user_id"),
                pl.col("timestamp"),
                pl.lit(0.0).alias("amount"),
                pl.lit("AA_BALANCE_SNAPSHOT").alias("merchant_name"),
                pl.lit("SUCCESS").alias("status"),
                pl.lit("OTHER").alias("txn_type"),
                pl.lit("OTHER").alias("category"),
            ])
            frames.append(ob_slim)

    # SMS alerts: extract FAILED payment events to augment debit failure signal
    if not sms_df.is_empty():
        sms_required = {"user_id", "timestamp", "body"}
        if sms_required.issubset(set(sms_df.columns)):
            sms_fail = sms_df.filter(
                pl.col("body").str.to_lowercase().str.contains("failed|declined|insufficient")
            )
            if not sms_fail.is_empty():
                sms_slim = sms_fail.select([
                    pl.col("user_id"),
                    pl.col("timestamp"),
                    pl.lit(-1.0).alias("amount"),
                    pl.lit("SMS_FAILURE_ALERT").alias("merchant_name"),
                    pl.lit("FAILED").alias("status"),
                    pl.lit("EXPENSE_ESSENTIAL").alias("txn_type"),
                    pl.lit("OTHER").alias("category"),
                ])
                frames.append(sms_slim)

    if not frames:
        print("[batch-engine] no raw data found — run phase 1 first")
        return

    events_df = pl.concat(frames, how="diagonal")
    user_ids = events_df["user_id"].unique().to_list()
    print(f"[batch-engine] {len(events_df):,} events across {len(user_ids):,} users")

    # per-user feature computation
    records: list[dict] = []
    for i, uid in enumerate(user_ids):
        if i % 50 == 0:
            print(f"[batch-engine] {i}/{len(user_ids)} users processed ...")
            if _check_memory_pressure():
                print("[batch-engine] memory pressure — flushing partial results")
                _flush_features(records, FEATURES_PATH)
                records = []

        user_rows = events_df.filter(pl.col("user_id") == uid)
        store = _build_user_store_from_df(user_rows)
        
        # Filter MSME data for this user
        user_gst = gst_df.filter(pl.col("user_id") == uid) if not gst_df.is_empty() else pl.DataFrame()
        user_ewb = ewb_df.filter(pl.col("user_id") == uid) if not ewb_df.is_empty() else pl.DataFrame()
        
        fv = compute_features_msme(store, ref, user_gst, user_ewb)
        fv.user_id = uid

        # infer income_band from 90d income
        if fv.income_90d > 100_000:
            income_band = "high"
        elif fv.income_90d > 30_000:
            income_band = "mid"
        else:
            income_band = "low"
        fv.income_band = income_band

        row = fv.model_dump()
        row["computed_at"] = ref.isoformat()
        records.append(row)

    if records:
        _flush_features(records, FEATURES_PATH)

    # post-processing: KNNImputer + IsolationForest across all users
    print("[batch-engine] post-processing: KNNImputer + IsolationForest ...")
    _postprocess_features(FEATURES_PATH)

    print("[batch-engine] done.")


def _flush_features(records: list[dict], features_dir: Path) -> None:
    """Write per-user feature rows to partitioned Parquet cache."""
    df = pl.DataFrame(records)
    for uid in df["user_id"].unique().to_list():
        slice_ = df.filter(pl.col("user_id") == uid)
        out_path = features_dir / f"user_id={uid}" / "features.parquet"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists():
            existing = pl.read_parquet(out_path)
            slice_ = pl.concat([existing, slice_], how="diagonal")
        slice_.write_parquet(out_path)


def _postprocess_features(features_dir: Path) -> None:
    """
    Load all user feature parquets, apply KNNImputer on sparse columns,
    run IsolationForest on cadence features, write back.
    """
    pattern = str(features_dir / "user_id=*" / "features.parquet")
    files = glob.glob(pattern)
    if not files:
        return

    frames = [pl.read_parquet(f) for f in files]
    df = pl.concat(frames, how="diagonal")
    print(f"[batch-engine] post-processing {len(df):,} rows")

    # KNNImputer: fill missing window cols using income cols as reference
    ref_cols = ["income_30d", "income_90d", "essential_30d", "essential_90d", "daily_avg_throughput_30d"]
    target_cols = [
        "cash_buffer_days", "emi_burden_ratio", "savings_rate", "debit_failure_rate_90d",
        "gst_30d_value", "ewb_30d_value", "gst_filing_compliance_rate", "statutory_payment_regularity_score"
    ]
    df = _apply_knn_imputer(df, ref_cols, target_cols)

    # IsolationForest on cadence/behavioural features
    cadence_cols = [
        "daily_avg_throughput_30d", "spending_volatility_index",
        "income_stability_score", "debit_failure_rate_90d",
        "top3_merchant_concentration", "discretionary_ratio",
        "gst_filing_compliance_rate", "statutory_payment_regularity_score"
    ]
    df = _apply_isolation_forest(df, cadence_cols)

    # write back per-user
    user_ids = df["user_id"].unique().to_list()
    for uid in user_ids:
        slice_ = df.filter(pl.col("user_id") == uid)
        out_path = features_dir / f"user_id={uid}" / "features.parquet"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        slice_.write_parquet(out_path)

    print(f"[batch-engine] post-processing complete — {len(user_ids)} user partitions written")


if __name__ == "__main__":
    import argparse, sys
    if len(sys.argv) > 1 and sys.argv[1] == "batch":
        parser = argparse.ArgumentParser()
        parser.add_argument("mode")
        parser.add_argument("--force", action="store_true",
                            help="Recompute features even if partitions already exist")
        args = parser.parse_args()

        sentinel_pattern = str(FEATURES_PATH / "user_id=*" / "features.parquet")
        existing = glob.glob(sentinel_pattern)
        if existing and not args.force:
            print(f"⚡ {len(existing)} feature partitions already exist. "
                  f"Skipping Phase 3. Pass --force to recompute.")
            raise SystemExit(0)

        run_batch()
    else:
        asyncio.run(run_feature_engine())
