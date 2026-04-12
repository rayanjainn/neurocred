"""
Tier 8 — Micro-loan Offer + EMI Restructuring Negotiation Engine

Implements:
  - Pre-qualified micro-loan generation when liquidity stress is detected
  - Structured multi-turn negotiation loop for EMI restructuring
  - Lightweight impact simulation for each proposal
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from src.twin.twin_model import DigitalTwin


def _monthly_rate(apr: float) -> float:
    return max(0.0, apr / 12.0 / 100.0)


def _emi(principal: float, apr: float, tenure_months: int) -> float:
    n = max(1, int(tenure_months))
    r = _monthly_rate(apr)
    if r <= 0:
        return principal / n
    x = (1.0 + r) ** n
    return principal * r * x / max(x - 1.0, 1e-9)


def _risk_band_from_score(score: float) -> str:
    if score <= 0.30:
        return "low_risk"
    if score <= 0.60:
        return "medium_risk"
    return "high_risk"


def make_prequalified_offer(
    twin: DigitalTwin,
    *,
    liquidity_floor_days: float = 5.0,
) -> dict[str, Any]:
    stress_factor = max(0.0, min(1.0, (liquidity_floor_days - twin.cash_buffer_days) / 5.0))
    cibil = twin.cibil_like_score()

    # Offer sizing is bounded and tied to score + stress severity.
    base = max(15_000.0, min(150_000.0, 20_000.0 + (cibil - 300) * 120.0))
    amount = int(round(base * (0.85 + stress_factor * 0.2), -2))

    if cibil >= 760:
        apr = 13.0
    elif cibil >= 680:
        apr = 16.0
    elif cibil >= 600:
        apr = 19.5
    else:
        apr = 24.0

    tenures = [3, 6, 9, 12]
    tenure_options = [
        {
            "tenure_months": t,
            "monthly_emi": round(_emi(amount, apr, t), 2),
            "apr": apr,
        }
        for t in tenures
    ]

    return {
        "offer_id": f"offer_{twin.user_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "generated_at": datetime.utcnow().isoformat(),
        "user_id": twin.user_id,
        "persona": twin.persona,
        "risk_band": _risk_band_from_score(twin.risk_score),
        "cibil_like_score": cibil,
        "approved_amount": amount,
        "currency": "INR",
        "apr": apr,
        "tenure_options": tenure_options,
        "valid_until": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        "purpose": "liquidity_stabilization",
    }


def simulate_restructure_impact(
    twin: DigitalTwin,
    *,
    proposed_monthly_emi: float,
    tenure_months: int,
    moratorium_days: int = 0,
) -> dict[str, Any]:
    income_proxy = max(20_000.0, twin.cibil_like_score() * 120.0)
    baseline_burden = twin.emi_burden_ratio
    new_burden = max(0.0, min(2.0, proposed_monthly_emi / income_proxy))

    buffer_boost = max(0.0, (baseline_burden - new_burden) * 14.0)
    if moratorium_days > 0:
        buffer_boost += min(10.0, moratorium_days / 6.0)

    projected_buffer_days = round(min(90.0, twin.cash_buffer_days + buffer_boost), 2)
    risk_delta = round((new_burden - baseline_burden) * 0.28 - (buffer_boost / 100.0), 4)
    projected_risk = round(max(0.0, min(1.0, twin.risk_score + risk_delta)), 4)

    return {
        "baseline": {
            "emi_burden_ratio": round(baseline_burden, 4),
            "cash_buffer_days": round(twin.cash_buffer_days, 2),
            "risk_score": round(twin.risk_score, 4),
        },
        "proposal": {
            "proposed_monthly_emi": round(proposed_monthly_emi, 2),
            "tenure_months": int(tenure_months),
            "moratorium_days": int(moratorium_days),
        },
        "projection": {
            "emi_burden_ratio": round(new_burden, 4),
            "cash_buffer_days": projected_buffer_days,
            "risk_score": projected_risk,
            "risk_band": _risk_band_from_score(projected_risk),
        },
    }


def _parse_negotiation_intent(message: str) -> str:
    txt = (message or "").strip().lower()
    if any(k in txt for k in ["accept", "ok", "confirm", "yes", "done"]):
        return "confirm"
    if any(k in txt for k in ["reject", "no", "decline", "cancel"]):
        return "reject"
    if any(k in txt for k in ["lower emi", "reduce emi", "smaller emi"]):
        return "lower_emi"
    if any(k in txt for k in ["longer", "extend", "12 month", "tenure"]):
        return "extend_tenure"
    if any(k in txt for k in ["moratorium", "next month", "defer"]):
        return "defer"
    return "clarify"


def start_negotiation_session(twin: DigitalTwin, offer: dict[str, Any]) -> dict[str, Any]:
    options = offer.get("tenure_options", [])
    selected = options[1] if len(options) > 1 else (options[0] if options else None)
    return {
        "session_id": f"neg_{twin.user_id}_{datetime.utcnow().strftime('%H%M%S')}",
        "user_id": twin.user_id,
        "status": "active",
        "turn": 0,
        "offer": offer,
        "selected": selected,
        "conversation": [
            {
                "role": "agent",
                "message": (
                    "Liquidity stress is detected. I have generated a pre-qualified micro-loan offer "
                    "and can simulate EMI restructuring options before you confirm."
                ),
                "ts": datetime.utcnow().isoformat(),
            }
        ],
        "last_impact": None,
    }


def advance_negotiation_session(
    session: dict[str, Any],
    twin: DigitalTwin,
    user_message: str,
) -> dict[str, Any]:
    if session.get("status") != "active":
        return session

    intent = _parse_negotiation_intent(user_message)
    session["turn"] = int(session.get("turn", 0)) + 1
    session.setdefault("conversation", []).append(
        {"role": "user", "message": user_message, "ts": datetime.utcnow().isoformat()}
    )

    selected = session.get("selected") or {}
    tenure = int(selected.get("tenure_months", 6) or 6)
    emi_val = float(selected.get("monthly_emi", 0.0) or 0.0)

    if intent == "lower_emi":
        tenure = min(24, tenure + 3)
        emi_val = max(500.0, emi_val * 0.88)
    elif intent == "extend_tenure":
        tenure = min(24, tenure + 6)
        emi_val = max(500.0, emi_val * 0.80)

    moratorium_days = 30 if intent == "defer" else 0

    impact = simulate_restructure_impact(
        twin,
        proposed_monthly_emi=emi_val,
        tenure_months=tenure,
        moratorium_days=moratorium_days,
    )
    session["last_impact"] = impact
    session["selected"] = {
        "tenure_months": tenure,
        "monthly_emi": round(emi_val, 2),
        "moratorium_days": moratorium_days,
    }

    if intent == "confirm":
        session["status"] = "confirmed"
        msg = (
            "Confirmed. I will apply this restructuring plan to your twin and mark negotiation complete."
        )
    elif intent == "reject":
        session["status"] = "rejected"
        msg = "Rejected. No restructuring changes have been applied."
    else:
        msg = (
            f"If we set EMI to INR {impact['proposal']['proposed_monthly_emi']:.0f} over "
            f"{impact['proposal']['tenure_months']} months, projected risk moves to "
            f"{impact['projection']['risk_band']} and cash buffer to "
            f"{impact['projection']['cash_buffer_days']} days. Reply 'confirm' to accept or ask for another option."
        )

    session["conversation"].append(
        {"role": "agent", "message": msg, "ts": datetime.utcnow().isoformat(), "intent": intent}
    )
    return session
