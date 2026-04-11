"""
Tier 9 — Module 4: Synthetic Identity & Bot Detector

Identifies accounts that lack "Human Transactional DNA":
  1. Improbable Precision — exact-interval regularity (bot-like scheduling)
  2. Network Improbability — hub-and-spoke patterns (mule collector detection)
  3. Mule-Account DNA — high-velocity, zero-discretionary laundering template

Uses Polars temporal autocorrelation + PageRank score from fraud_ring module.
"""

from __future__ import annotations

import math
import statistics
from typing import Any

from src.vigilance.schemas import (
    BotDetectorResult,
    RiskLevel,
)

# ── Thresholds ────────────────────────────────────────────────────────────────

# Coefficient of Variation for inter-transaction intervals
# A CV < this means intervals are suspiciously regular (bot-like)
BOT_CV_THRESHOLD = 0.05

# Percentage of outflows going to a single receiver = hub-and-spoke
HUB_SPOKE_CONCENTRATION = 0.80

# Laundering template: high velocity + near-zero discretionary
LAUNDERING_VELOCITY_THRESHOLD  = 200_000.0  # INR/day total throughput
LAUNDERING_DISCRETIONARY_MAX   = 0.02       # <2% discretionary = no lifestyle spending


# ── 1. Improbable Precision Detector ─────────────────────────────────────────

def _detect_improbable_precision(
    timestamps: list[float],  # Unix timestamps in seconds
) -> tuple[bool, float]:
    """
    Compute coefficient of variation of inter-transaction intervals.
    A CV < BOT_CV_THRESHOLD signals bot-like scheduling.

    Returns: (flag, CV)
    """
    if len(timestamps) < 5:
        return False, 1.0

    sorted_ts = sorted(timestamps)
    intervals = [sorted_ts[i+1] - sorted_ts[i] for i in range(len(sorted_ts)-1)]

    if not intervals or all(iv == 0 for iv in intervals):
        return False, 1.0

    try:
        mean_iv = statistics.mean(intervals)
        std_iv  = statistics.stdev(intervals) if len(intervals) > 1 else 0.0
        cv = std_iv / (mean_iv + 1e-9)
    except statistics.StatisticsError:
        return False, 1.0

    return cv < BOT_CV_THRESHOLD, round(cv, 4)


# ── 2. Network Improbability (Hub-and-Spoke) ─────────────────────────────────

def _detect_hub_spoke(
    upi_events: list[dict[str, Any]],
    user_id: str,
    pagerank_score: float = 0.0,
) -> tuple[float, list[str]]:
    """
    Score how much this user's outflows concentrate on a single receiver.
    High concentration + high-value inflows from multiple sources = mule collector.

    Returns (network_improbability_score, evidence_list)
    """
    evidence = []

    outflows: dict[str, float] = {}
    inflow_sources: set[str]   = set()
    total_outflow = 0.0
    total_inflow  = 0.0

    for ev in upi_events:
        src = ev.get("sender_id") or ev.get("payer_id", "")
        dst = ev.get("receiver_id") or ev.get("payee_id", "")
        amt = float(ev.get("amount", 0.0))

        if src == user_id:
            outflows[dst] = outflows.get(dst, 0.0) + amt
            total_outflow += amt
        elif dst == user_id:
            inflow_sources.add(src)
            total_inflow += amt

    if total_outflow == 0:
        return 0.0, evidence

    # Top receiver concentration
    top_outflow = max(outflows.values(), default=0.0)
    concentration = top_outflow / (total_outflow + 1e-9)

    score = 0.0

    if concentration >= HUB_SPOKE_CONCENTRATION:
        score += 0.6
        evidence.append(
            f"{concentration:.0%} of outflows go to a single receiver (hub-and-spoke)"
        )

    if len(inflow_sources) > 5 and concentration > 0.6:
        score += 0.25
        evidence.append(
            f"inflows from {len(inflow_sources)} distinct sources funnelled to one collector"
        )

    if pagerank_score >= 0.10:
        score += 0.15
        evidence.append(f"elevated PageRank ({pagerank_score:.4f}) as collector hub")

    return round(min(score, 1.0), 4), evidence


# ── 3. Mule-Account DNA ───────────────────────────────────────────────────────

def _compute_mule_dna_score(
    daily_avg_throughput: float,
    discretionary_ratio: float,
    cash_buffer_days: float,
    debit_failure_rate: float,
) -> tuple[float, list[str]]:
    """
    Match to known money-mule laundering template:
      - High velocity (large daily throughput)
      - Near-zero discretionary spending (no lifestyle = mule)
      - Very low cash buffer (money held for < 1 day)
      - Low debit failure (mules never run out — they pass money on quickly)

    Returns (score, evidence_list)
    """
    evidence = []
    score_components = []

    # Velocity signal
    if daily_avg_throughput > LAUNDERING_VELOCITY_THRESHOLD:
        v_score = min((daily_avg_throughput - LAUNDERING_VELOCITY_THRESHOLD) / LAUNDERING_VELOCITY_THRESHOLD, 1.0)
        score_components.append(v_score * 0.4)
        evidence.append(f"daily throughput ₹{daily_avg_throughput:,.0f} exceeds laundering threshold")

    # Near-zero discretionary
    if discretionary_ratio <= LAUNDERING_DISCRETIONARY_MAX:
        score_components.append(0.35)
        evidence.append(f"discretionary ratio {discretionary_ratio:.1%} — no lifestyle spending signature")

    # Minimal cash buffer (money passes through quickly)
    if cash_buffer_days < 2.0:
        score_components.append(0.15)
        evidence.append(f"cash buffer {cash_buffer_days:.1f} days — very short holding time")

    # Low failure rate (clean pass-through)
    if debit_failure_rate < 0.01:
        score_components.append(0.10)
        evidence.append("near-zero debit failure rate — automated pass-through pattern")

    mule_score = sum(score_components)
    return round(min(mule_score, 1.0), 4), evidence


# ── Main Entry ────────────────────────────────────────────────────────────────

def run_bot_detector(
    user_id: str,
    upi_events: list[dict[str, Any]],
    daily_avg_throughput: float,
    discretionary_ratio: float,
    cash_buffer_days: float,
    debit_failure_rate: float,
    pagerank_score: float = 0.0,
) -> BotDetectorResult:
    """
    Full bot / synthetic identity / mule account detection.

    Args:
        user_id:               Target user
        upi_events:            List of UPI transaction dicts (with timestamps)
        daily_avg_throughput:  From BehaviouralFeatureVector.daily_avg_throughput_30d
        discretionary_ratio:   From BehaviouralFeatureVector.discretionary_ratio
        cash_buffer_days:      From BehaviouralFeatureVector.cash_buffer_days
        debit_failure_rate:    From BehaviouralFeatureVector.debit_failure_rate_90d
        pagerank_score:        From FraudRingResult.pagerank_score

    Returns:
        BotDetectorResult
    """
    evidence_all: list[str] = []

    # 1. Improbable Precision
    import time
    timestamps_raw = []
    for ev in upi_events:
        raw = ev.get("timestamp") or ev.get("ts", "")
        if raw:
            try:
                from datetime import datetime
                ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                timestamps_raw.append(ts.timestamp())
            except (ValueError, TypeError):
                pass

    precision_flag, cv = _detect_improbable_precision(timestamps_raw)
    if precision_flag:
        evidence_all.append(f"improbably regular transaction intervals (CV={cv:.4f})")

    # 2. Network Improbability
    hub_score, hub_evidence = _detect_hub_spoke(upi_events, user_id, pagerank_score)
    evidence_all.extend(hub_evidence)

    # 3. Mule DNA
    mule_score, mule_evidence = _compute_mule_dna_score(
        daily_avg_throughput, discretionary_ratio,
        cash_buffer_days, debit_failure_rate,
    )
    evidence_all.extend(mule_evidence)

    # Composite consistency score: weighted combination
    precision_component = 0.8 if precision_flag else 0.0
    consistency_score = (
        precision_component * 0.35
        + hub_score * 0.40
        + mule_score * 0.25
    )
    consistency_score = round(min(consistency_score, 1.0), 4)

    is_bot  = precision_flag and consistency_score > 0.5
    is_mule = mule_score > 0.6 or (hub_score > 0.5 and mule_score > 0.35)

    if consistency_score >= 0.7:
        risk = RiskLevel.CRITICAL
    elif consistency_score >= 0.45:
        risk = RiskLevel.HIGH
    elif consistency_score >= 0.2:
        risk = RiskLevel.MEDIUM
    else:
        risk = RiskLevel.LOW

    return BotDetectorResult(
        user_id=user_id,
        consistency_score=consistency_score,
        is_bot_flag=is_bot,
        is_mule_flag=is_mule,
        improbable_precision_detected=precision_flag,
        network_improbability_score=hub_score,
        mule_dna_score=mule_score,
        risk_level=risk,
        evidence=evidence_all[:10],
    )
