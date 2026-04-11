"""
Tier 9 — Top-level Vigilance Agent entry point

Wires all 5 modules:
  2. Fraud Ring & Cycle Detection (NetworkX)
  3. Social Engineering Defence (Bayesian scam detector)
  4. Synthetic Identity & Bot Detector
  5.1 Hidden Financial Stress
  5.2 Progressive Income Underreporting
  5.3 Identity & Behaviour Shifts

Emits:
  - Redis: stream:vigilance_events  (event: vigilance_completed, fraud_ring_flagged, scam_alert)
  - Redis: tier9:result:{user_id}   (latest result, TTL 24h)
  - Decision outputs consumed directly by Tier 7 Cognitive Engine
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

import redis.asyncio as aioredis

from src.features.schemas import BehaviouralFeatureVector
from src.vigilance.anomaly_detector import (
    run_identity_shift_detector,
    run_income_underreport_detector,
    run_stress_detector,
)
from src.vigilance.bot_detector import run_bot_detector
from src.vigilance.fraud_ring import run_fraud_ring_detector
from src.vigilance.scam_detector import run_scam_detector
from src.vigilance.schemas import RiskLevel, Tier9Result


# ── Risk Level Aggregator ─────────────────────────────────────────────────────

_RISK_ORDER = {
    RiskLevel.LOW:      0,
    RiskLevel.MEDIUM:   1,
    RiskLevel.HIGH:     2,
    RiskLevel.CRITICAL: 3,
}


def _aggregate_risk(*levels: RiskLevel) -> RiskLevel:
    """Return the highest risk level from a set of module outputs."""
    return max(levels, key=lambda r: _RISK_ORDER.get(r, 0))


# ── Deception Score ───────────────────────────────────────────────────────────

def _compute_deception_score(result: "Tier9Result") -> float:
    """
    Composite deception score [0, 1] from all module outputs.
    Weights per §6 (Decision Outputs) of tier9.md.
    """
    score = (
        result.fraud_ring.fraud_confidence      * 0.30
        + result.scam_defence.scam_probability  * 0.20
        + result.bot_detector.consistency_score * 0.20
        + result.stress_signal.stress_confidence_score * 0.10
        + result.income_underreport.income_underreport_score * 0.10
        + result.identity_shift.identity_shift_score * 0.10
    )
    return round(min(score, 1.0), 4)


# ── Main Entry Point ──────────────────────────────────────────────────────────

async def run_tier9(
    features: BehaviouralFeatureVector,
    redis_client: aioredis.Redis,
    upi_events: Optional[list[dict[str, Any]]] = None,
    ewb_events: Optional[list[dict[str, Any]]] = None,
    sms_texts: Optional[list[dict[str, str]]] = None,
    declared_income: float = 0.0,
    cohort_mean_income: float = 0.0,
    cohort_std_income:  float = 0.0,
    category_mix_30d: Optional[list[float]] = None,
    category_mix_90d: Optional[list[float]] = None,
) -> Tier9Result:
    """
    Full Tier 9 vigilance pipeline for one user.

    Args:
        features:           Latest BehaviouralFeatureVector from Tier 3
        redis_client:       Async Redis client
        upi_events:         Raw UPI transaction dicts (from stream:typed_events)
        ewb_events:         E-Way Bill dicts (from GST integration)
        sms_texts:          List of {"text": ..., "sender_id": ...} dicts
        declared_income:    Monthly INR from onboarding
        cohort_mean_income: Peer cohort mean monthly income
        cohort_std_income:  Peer cohort std-dev monthly income
        category_mix_30d:   Spend fractions per category (30d)
        category_mix_90d:   Spend fractions per category (90d baseline)
    """
    run_id   = str(uuid.uuid4())
    user_id  = features.user_id
    evts     = upi_events or []
    ewbs     = ewb_events or []
    smss     = sms_texts or []

    if declared_income <= 0:
        declared_income = features.income_90d / 3.0

    # ── Module 2: Fraud Ring Detection ───────────────────────────────────────
    fraud_ring = run_fraud_ring_detector(
        user_id=user_id,
        upi_events=evts,
        ewb_events=ewbs,
        months_active=features.months_active_gst or 24,
    )

    # ── Module 3: Scam Detector (aggregate across SMS batch) ─────────────────
    if smss:
        # Score each message, keep the worst-case
        best_scam = None
        for msg in smss[:20]:  # cap at 20 messages
            r = run_scam_detector(
                user_id=user_id,
                text=msg.get("text", ""),
                sender_id=msg.get("sender_id"),
            )
            if best_scam is None or r.scam_probability > best_scam.scam_probability:
                best_scam = r
        scam_defence = best_scam
    else:
        scam_defence = run_scam_detector(user_id=user_id, text="")

    # ── Module 4: Bot Detector ────────────────────────────────────────────────
    bot_detector = run_bot_detector(
        user_id=user_id,
        upi_events=evts,
        daily_avg_throughput=features.daily_avg_throughput_30d,
        discretionary_ratio=features.discretionary_ratio,
        cash_buffer_days=features.cash_buffer_days,
        debit_failure_rate=features.debit_failure_rate_90d,
        pagerank_score=fraud_ring.pagerank_score,
    )

    # ── Module 5.1: Stress Detector ───────────────────────────────────────────
    stress_signal = run_stress_detector(features)

    # ── Module 5.2: Income Underreporting ────────────────────────────────────
    income_underreport = run_income_underreport_detector(
        fv=features,
        declared_income=declared_income,
        cohort_mean_income=cohort_mean_income or declared_income,
        cohort_std_income=cohort_std_income or declared_income * 0.3,
    )

    # ── Module 5.3: Identity Shift ────────────────────────────────────────────
    identity_shift = run_identity_shift_detector(
        fv=features,
        category_mix_30d=category_mix_30d,
        category_mix_90d=category_mix_90d,
    )

    # ── Aggregate ─────────────────────────────────────────────────────────────
    result = Tier9Result(
        user_id=user_id,
        run_id=run_id,
        fraud_ring=fraud_ring,
        scam_defence=scam_defence,
        bot_detector=bot_detector,
        stress_signal=stress_signal,
        income_underreport=income_underreport,
        identity_shift=identity_shift,
        fraud_ring_flag=fraud_ring.fraud_ring_flag,
        fraud_confidence=fraud_ring.fraud_confidence,
        scam_probability=scam_defence.scam_probability,
        pagerank_score=fraud_ring.pagerank_score,
        overall_risk_level=_aggregate_risk(
            fraud_ring.risk_level,
            scam_defence.risk_level,
            bot_detector.risk_level,
            stress_signal.risk_level,
            income_underreport.risk_level,
            identity_shift.risk_level,
        ),
    )
    result.deception_score = _compute_deception_score(result)

    # ── Persist to Redis ──────────────────────────────────────────────────────
    result_json = result.model_dump_json()
    await redis_client.setex(f"tier9:result:{user_id}", 86400, result_json)

    # ── Emit events to vigilance stream ───────────────────────────────────────
    await redis_client.xadd(
        "stream:vigilance_events",
        {
            "event": "vigilance_completed",
            "user_id": user_id,
            "run_id": run_id,
            "deception_score": str(result.deception_score),
            "overall_risk": result.overall_risk_level.value,
            "fraud_ring_flag": "1" if fraud_ring.fraud_ring_flag else "0",
            "scam_alert": "1" if scam_defence.is_scam_alert else "0",
            "bot_flag": "1" if bot_detector.is_bot_flag else "0",
            "mule_flag": "1" if bot_detector.is_mule_flag else "0",
        },
        maxlen=10_000,
        approximate=True,
    )

    if fraud_ring.fraud_ring_flag:
        await redis_client.xadd(
            "stream:vigilance_events",
            {
                "event": "fraud_ring_flagged",
                "user_id": user_id,
                "fraud_confidence": str(fraud_ring.fraud_confidence),
                "pagerank": str(fraud_ring.pagerank_score),
                "cycles_detected": str(len(fraud_ring.detected_cycles)),
            },
        )

    if scam_defence.is_scam_alert:
        await redis_client.xadd(
            "stream:vigilance_events",
            {
                "event": "scam_alert",
                "user_id": user_id,
                "scam_probability": str(scam_defence.scam_probability),
                "urgency": str(scam_defence.urgency_score),
                "authority": str(scam_defence.authority_score),
                "otp_phishing": str(scam_defence.otp_phishing_score),
            },
        )

    return result


async def get_tier9_result(
    user_id: str,
    redis_client: aioredis.Redis,
) -> Optional[Tier9Result]:
    """Retrieve the latest cached Tier 9 result for a user."""
    raw = await redis_client.get(f"tier9:result:{user_id}")
    if not raw:
        return None
    return Tier9Result.model_validate_json(raw)
