"""
Tier 5 — Context Assembly Engine (Module 1)

Assembles a token-budgeted, priority-ranked context object before
every LLM call. Prevents context window overflow and focuses the LLM
on the most information-dense signals.

Priority order (per tier5.md):
  1. Delta Packet       — what changed since last twin version
  2. Simulation Verdict — EWS, default probability (Tier 6 placeholder)
  3. Top 5 anomalous features by peer cohort z-score deviation
  4. Last N typed events from Tier 2
  5. Declared income + Contradiction Detector result

Token budget: 70% of model context window reserved for context;
30% for output schema + reasoning trace.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from src.features.schemas import BehaviouralFeatureVector
from src.reasoning.schemas import (
    ContradictionDetectorResult,
    DeltaPacket,
    FeatureDelta,
)


# Approximate tokens per character ratio for a tokenizer (conservative estimate)
_CHARS_PER_TOKEN = 4.0
_MAX_CONTEXT_TOKENS = 6_000   # budget for context assembly (70% of 8192-token window)
_RESERVE_TOKENS = 2_400       # reserved for output schema + CoT trace


def _token_estimate(text: str) -> int:
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


@dataclass
class AssembledContext:
    """The fully assembled, token-budgeted context ready for LLM injection."""
    delta_packet: Optional[DeltaPacket] = None
    top5_anomalous_features: list[dict] = field(default_factory=list)
    recent_events_summary: str = ""
    contradiction_result: Optional[ContradictionDetectorResult] = None
    declared_income: float = 0.0
    simulation_verdict: dict = field(default_factory=dict)
    total_tokens_used: int = 0

    def to_prompt_section(self) -> str:
        """Render the assembled context into a structured prompt string."""
        parts: list[str] = []

        # Priority 1: Delta Packet
        if self.delta_packet and self.delta_packet.changed_features:
            changes = []
            for fd in self.delta_packet.changed_features[:8]:
                arrow = "↑" if fd.direction == "improved" else ("↓" if fd.direction == "degraded" else "→")
                changes.append(
                    f"  {arrow} {fd.feature}: {fd.previous:.3f} → {fd.current:.3f} "
                    f"(Δ={fd.z_change:+.2f}σ)"
                )
            parts.append(
                "=== [DELTA PACKET — Priority 1] ===\n"
                + "\n".join(changes)
                + (f"\n  Regime changed: YES" if self.delta_packet.regime_changed else "")
                + (f"\n  New event types: {', '.join(self.delta_packet.new_event_types)}"
                   if self.delta_packet.new_event_types else "")
            )

        # Priority 2: Simulation Verdict
        if self.simulation_verdict:
            sv = self.simulation_verdict
            parts.append(
                "=== [SIMULATION VERDICT — Priority 2] ===\n"
                f"  EWS_14d: {sv.get('ews_14d', 'N/A')} | "
                f"EWS_30d: {sv.get('ews_30d', 'N/A')} | "
                f"EWS_90d: {sv.get('ews_90d', 'N/A')}\n"
                f"  Default probability (90d): {sv.get('default_probability', 'N/A')}\n"
                f"  CVaR: {sv.get('cvar', 'N/A')} | "
                f"Regime: {sv.get('dominant_regime', 'N/A')}"
            )
        else:
            parts.append(
                "=== [SIMULATION VERDICT — Priority 2] ===\n"
                "  Tier 6 simulation data unavailable — reasoning from Tier 3 features only."
            )

        # Priority 3: Top 5 anomalous features
        if self.top5_anomalous_features:
            feat_lines = []
            for f in self.top5_anomalous_features[:5]:
                feat_lines.append(
                    f"  • {f['feature']}: {f['value']:.4f} "
                    f"(cohort z-score: {f['z_score']:+.2f}, "
                    f"rank: {f['anomaly_rank']})"
                )
            parts.append(
                "=== [TOP-5 ANOMALOUS FEATURES — Priority 3] ===\n"
                + "\n".join(feat_lines)
            )

        # Priority 4: Recent events
        if self.recent_events_summary:
            parts.append(
                "=== [RECENT TYPED EVENTS — Priority 4] ===\n"
                + self.recent_events_summary
            )

        # Priority 5: Income + Contradiction
        income_section = f"  Declared monthly income: ₹{self.declared_income:,.0f}"
        if self.contradiction_result:
            cd = self.contradiction_result
            income_section += (
                f"\n  Observed mean income: ₹{cd.observed_mean_income:,.0f}"
                f"\n  Z-score: {cd.z_score:.2f} | Direction: {cd.direction}"
                f"\n  Layers triggered: {cd.layers_triggered}/3 | Severity: {cd.severity}"
                f"\n  LCI (Lifestyle Consistency Index): {cd.layer3_lci:.3f}"
            )
            if cd.contradiction_detected:
                income_section += f"\n  ⚠️  CONTRADICTION DETECTED: {cd.details}"
        parts.append("=== [INCOME & CONTRADICTION — Priority 5] ===\n" + income_section)

        return "\n\n".join(parts)


def rank_anomalous_features(
    features: BehaviouralFeatureVector,
) -> list[dict]:
    """
    Rank all numeric features by their deviation from expected normal ranges.
    Uses hard-coded peer cohort z-score proxies where real cohort data
    is unavailable; real deviation comes from peer_cohort_benchmark_deviation.
    Returns top 5 as structured dicts.
    """
    # Feature → (value, expected_mean, expected_std) for z-score computation
    # These are approximate cohort norms for mid-income Indian retail users
    COHORT_NORMS: dict[str, tuple[float, float]] = {
        "emi_burden_ratio":           (0.25, 0.10),
        "savings_rate":               (0.15, 0.08),
        "income_stability_score":     (0.75, 0.15),
        "spending_volatility_index":  (0.35, 0.12),
        "cash_buffer_days":           (25.0, 10.0),
        "discretionary_ratio":        (0.25, 0.08),
        "debit_failure_rate_90d":     (0.05, 0.04),
        "lifestyle_inflation_trend":  (0.05, 0.10),
        "top3_merchant_concentration":(0.35, 0.12),
        "cash_dependency_index":      (0.10, 0.08),
        "end_of_month_liquidity_dip": (5000, 3000),
    }

    feature_dict = features.model_dump()
    ranked: list[dict] = []

    for feat, (mean, std) in COHORT_NORMS.items():
        val = feature_dict.get(feat)
        if val is None or not isinstance(val, (int, float)):
            continue
        z = (float(val) - mean) / max(std, 1e-9)
        ranked.append({
            "feature": feat,
            "value": float(val),
            "z_score": round(z, 3),
            "anomaly_rank": 0,  # filled below
        })

    # Sort by absolute z-score descending
    ranked.sort(key=lambda x: abs(x["z_score"]), reverse=True)
    for i, item in enumerate(ranked):
        item["anomaly_rank"] = i + 1

    return ranked[:5]


def build_delta_packet(
    current_features: dict[str, float],
    previous_features: dict[str, float],
    feature_stds: dict[str, float],
) -> DeltaPacket:
    """
    Compute feature-level diffs between current and previous twin snapshots.
    Only includes features that moved by more than 0.5 std devs.
    """
    changed: list[FeatureDelta] = []
    for key, curr_val in current_features.items():
        prev_val = previous_features.get(key, curr_val)
        std = feature_stds.get(key, 1.0)
        z_change = (curr_val - prev_val) / max(std, 1e-9)
        if abs(z_change) >= 0.5:
            direction = "improved" if _is_improvement(key, z_change) else (
                "degraded" if abs(z_change) > 0 else "stable"
            )
            changed.append(FeatureDelta(
                feature=key,
                previous=round(prev_val, 4),
                current=round(curr_val, 4),
                z_change=round(z_change, 3),
                direction=direction,
            ))
    changed.sort(key=lambda x: abs(x.z_change), reverse=True)
    return DeltaPacket(changed_features=changed[:10])


def _is_improvement(feature_name: str, z_change: float) -> bool:
    """For features where higher is better, improvement = positive z_change."""
    HIGHER_IS_BETTER = {
        "savings_rate", "income_stability_score", "cash_buffer_days",
        "income_7d", "income_30d", "income_90d", "net_cashflow_30d", "net_cashflow_90d",
    }
    LOWER_IS_BETTER = {
        "emi_burden_ratio", "spending_volatility_index", "debit_failure_rate_90d",
        "cash_dependency_index", "lifestyle_inflation_trend", "top3_merchant_concentration",
        "end_of_month_liquidity_dip",
    }
    if feature_name in HIGHER_IS_BETTER:
        return z_change > 0
    if feature_name in LOWER_IS_BETTER:
        return z_change < 0
    return False  # neutral


def assemble_context(
    features: BehaviouralFeatureVector,
    declared_income: float,
    contradiction_result: Optional[ContradictionDetectorResult],
    delta_packet: Optional[DeltaPacket],
    recent_events: list[dict],
    simulation_verdict: Optional[dict] = None,
) -> AssembledContext:
    """
    Build the full token-budgeted context object.
    Respects the 70/30 budget split.
    """
    ctx = AssembledContext(
        delta_packet=delta_packet,
        contradiction_result=contradiction_result,
        declared_income=declared_income,
        simulation_verdict=simulation_verdict or {},
    )

    # Priority 3: Top 5 anomalous features
    ctx.top5_anomalous_features = rank_anomalous_features(features)

    # Priority 4: Summarize last 15 events
    if recent_events:
        lines = []
        for ev in recent_events[-15:]:
            ts = str(ev.get("timestamp", ""))[:16]
            amt = ev.get("amount", 0)
            merchant = ev.get("merchant_name", "unknown")[:20]
            cat = ev.get("merchant_category", ev.get("source_provenance", "?"))[:15]
            status = ev.get("status", "?")
            lines.append(f"  {ts}  ₹{float(amt):>10,.0f}  {merchant:<22}  {cat:<15}  {status}")
        ctx.recent_events_summary = "\n".join(lines)

    # Estimate tokens used
    prompt_text = ctx.to_prompt_section()
    ctx.total_tokens_used = _token_estimate(prompt_text)

    return ctx
