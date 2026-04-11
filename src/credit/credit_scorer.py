"""
Tier 7 — Cognitive Credit Engine: Consumer Credit Scorer

Dual XGBoost architecture for retail consumers:
  - xgb_digital_twin.ubj         full model  (all 28 behavioural features)
  - xgb_digital_twin_income_heavy.ubj  income-heavy model (zero discretionary cols)

Model routing:
  → income_heavy when data_completeness_score < 0.7 (thin-file user)
  → full model otherwise

Scoring pipeline:
  1. Align to 28-column feature contract (zero-fill missing)
  2. CSR conversion if sparsity > 50%
  3. XGBoost predict_proba → P(default)
  4. Linear map → 300–900 CIBIL-like score  (score = 900 - prob × 600)
  5. EL-based personal loan sizing
  6. Machine-readable rule trace (per-threshold pass/fail audit)
  7. Behavioural trajectory override (improving Digital Twin → score boost)

Architecture mirrors CreditIQ's src/scoring/model.py applied to consumer signals.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import xgboost as xgb

from src.credit.schemas import BehaviouralOverride, CreditScoreResult, SHAPFeature
from src.features.schemas import BehaviouralFeatureVector
from src.scoring.trainer import FEATURE_COLUMNS  # reuse Tier 4 contract

# ── risk bands ────────────────────────────────────────────────────────────────

RISK_BANDS: dict[str, dict] = {
    "very_low_risk": {
        "min": 750, "max": 900,
        "max_loan_lakh": 20,
        "tenure_months": 60,
        "apr_range": (8.5, 11.0),
        "cgtmse_eligible": True,
    },
    "low_risk": {
        "min": 650, "max": 749,
        "max_loan_lakh": 10,
        "tenure_months": 48,
        "apr_range": (11.0, 14.0),
        "cgtmse_eligible": True,
    },
    "medium_risk": {
        "min": 550, "max": 649,
        "max_loan_lakh": 5,
        "tenure_months": 36,
        "apr_range": (14.0, 18.0),
        "cgtmse_eligible": False,
    },
    "high_risk": {
        "min": 300, "max": 549,
        "max_loan_lakh": 1,
        "tenure_months": 12,
        "apr_range": (18.0, 24.0),
        "cgtmse_eligible": False,
    },
}

_LGD = 0.45          # Loss Given Default (unsecured personal lending)
_MAX_EL = 25_000.0   # max acceptable expected loss per personal loan (INR)


# ── XGBoost safe loader (patches bracketed base_score bug in XGB 2.x) ─────────

def _load_xgb_safe(path: str | Path) -> xgb.XGBClassifier:
    booster = xgb.Booster()
    booster.load_model(str(path))
    cfg = json.loads(booster.save_config())

    def _fix(node: object) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, str) and "[" in v:
                    m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", v)
                    if m:
                        node[k] = str(float(m.group()))
                else:
                    _fix(v)
        elif isinstance(node, list):
            for item in node:
                _fix(item)

    _fix(cfg)
    booster.load_config(json.dumps(cfg))
    clf = xgb.XGBClassifier()
    clf._Booster = booster
    return clf


def _to_sparse(X: np.ndarray, threshold: float = 0.5) -> np.ndarray | sp.csr_matrix:
    sparsity = float(np.sum(X == 0)) / float(X.size)
    return sp.csr_matrix(X) if sparsity > threshold else X


# ── module-level helpers (used by tests + explainer) ─────────────────────────

def _prob_to_score_standalone(prob: float) -> int:
    raw = int(900 - prob * 600)
    return int(np.clip(raw, 300, 900))


def _score_to_band_standalone(score: int) -> str:
    for name, cfg in RISK_BANDS.items():
        if cfg["min"] <= score <= cfg["max"]:
            return name
    return "high_risk"


# ── credit scorer ─────────────────────────────────────────────────────────────

class CreditScorer:
    """
    Loads the dual digital-twin XGBoost models trained in Tier 4's scoring/trainer.py.
    Runs inference and generates EL-based personal loan sizing + rule trace.
    """

    def __init__(self, model_dir: str | Path = "data/models") -> None:
        model_dir = Path(model_dir)
        self.model_full   = _load_xgb_safe(model_dir / "xgb_digital_twin.ubj")
        self.model_income = _load_xgb_safe(model_dir / "xgb_digital_twin_income_heavy.ubj")

        fc_path = model_dir / "feature_columns.json"
        if fc_path.exists():
            with open(fc_path) as fh:
                self.feature_columns: list[str] = json.load(fh)
        else:
            self.feature_columns = FEATURE_COLUMNS

        print("[credit_scorer] dual consumer models loaded (full + income_heavy)")

    # ── internal helpers ──────────────────────────────────────────────────────

    def _prob_to_score(self, prob: float) -> int:
        raw = int(900 - prob * 600)
        return int(np.clip(raw, 300, 900))

    def _score_to_band(self, score: int) -> str:
        for name, cfg in RISK_BANDS.items():
            if cfg["min"] <= score <= cfg["max"]:
                return name
        return "high_risk"

    def _el_sizing(self, band: str, prob: float) -> dict:
        cfg = RISK_BANDS[band]
        safe_prob = max(prob, 0.0001)
        band_max = float(cfg["max_loan_lakh"] * 100_000)
        el_limit = _MAX_EL / (safe_prob * _LGD)
        optimal = min(el_limit, band_max)

        apr_lo, apr_hi = cfg["apr_range"]
        apr = apr_lo + (apr_hi - apr_lo) * min(prob, 1.0)

        return {
            "recommended_personal_loan_amount": optimal,
            "recommended_tenure_months": cfg["tenure_months"],
            "annual_percentage_rate": round(apr, 2),
            "cgtmse_eligible": cfg["cgtmse_eligible"],
        }

    def _rule_trace(
        self,
        fv: BehaviouralFeatureVector,
        score: int,
        band: str,
        prob: float,
        model_used: str,
        override: BehaviouralOverride,
    ) -> dict:
        """Machine-readable per-threshold audit trace."""
        return {
            "model_routing": {
                "model_used": model_used,
                "reason": (
                    "data_completeness_score < 0.7 → income-heavy model"
                    if model_used == "income_heavy"
                    else "data_completeness_score ≥ 0.7 → full model"
                ),
            },
            "emi_burden_check": {
                "value": round(fv.emi_burden_ratio, 3),
                "threshold": 0.5,
                "result": "PASSED" if fv.emi_burden_ratio <= 0.5 else "FAILED",
            },
            "savings_rate_check": {
                "value": round(fv.savings_rate, 3),
                "threshold": 0.0,
                "result": "PASSED" if fv.savings_rate >= 0.0 else "FAILED",
            },
            "cash_buffer_check": {
                "value": round(fv.cash_buffer_days, 1),
                "threshold": 15,
                "result": "PASSED" if fv.cash_buffer_days >= 15 else "FAILED",
            },
            "debit_failure_check": {
                "value": round(fv.debit_failure_rate_90d, 3),
                "threshold": 0.1,
                "result": "PASSED" if fv.debit_failure_rate_90d <= 0.1 else "FAILED",
            },
            "income_stability_check": {
                "value": round(fv.income_stability_score, 3),
                "threshold": 0.5,
                "result": "PASSED" if fv.income_stability_score >= 0.5 else "FAILED",
            },
            "anomaly_check": {
                "anomaly_flag": fv.anomaly_flag,
                "result": "FAILED" if fv.anomaly_flag else "PASSED",
            },
            "net_cashflow_check": {
                "net_cashflow_30d": round(fv.net_cashflow_30d, 2),
                "result": "PASSED" if fv.net_cashflow_30d >= 0 else "FAILED",
            },
            "msme_gst_check": {
                "gst_compliance": round(fv.gst_filing_compliance_rate, 3),
                "threshold": 0.8,
                "result": "PASSED" if fv.gst_filing_compliance_rate >= 0.8 else "FAILED" if fv.gstin else "N/A",
            },
            "msme_receivables_gap_check": {
                "gap": round(fv.gst_upi_receivables_gap, 3),
                "threshold": 0.4,
                "result": "PASSED" if fv.gst_upi_receivables_gap <= 0.4 else "FAILED" if fv.gstin else "N/A",
            },
            "behavioural_override": override.model_dump(),
            "final_score": score,
            "final_band": band,
            "probability_of_default": round(prob, 4),
        }

    # ── main scoring entry point ──────────────────────────────────────────────

    def score(
        self,
        fv: BehaviouralFeatureVector,
        use_income_model: bool | None = None,
        twin_trajectory_delta: float = 0.0,
    ) -> dict:
        """
        Score a consumer BehaviouralFeatureVector.

        Args:
            fv: 28-feature behavioural vector from Tier 3
            use_income_model: None = auto-route; True/False = override
            twin_trajectory_delta: positive delta from Digital Twin risk history
                                   (improving trajectory → score boost)
        Returns full scoring dict; caller assembles CreditScoreResult.
        """
        fv_dict = fv.model_dump()
        row = np.array(
            [float(fv_dict.get(col, 0)) for col in self.feature_columns],
            dtype=np.float32,
        ).reshape(1, -1)
        X = _to_sparse(row)

        if use_income_model is None:
            use_income_model = fv.data_completeness_score < 0.7

        model = self.model_income if use_income_model else self.model_full
        model_used = "income_heavy" if use_income_model else "full"

        prob = float(model.predict_proba(X)[0][1])
        score = self._prob_to_score(prob)

        # Behavioural trajectory override — improving Digital Twin offsets static bureau
        override = BehaviouralOverride()
        if twin_trajectory_delta > 0:
            boost = int(round(twin_trajectory_delta * 50))
            boost = min(boost, 75)
            score = int(np.clip(score + boost, 300, 900))
            override = BehaviouralOverride(
                applied=True,
                trajectory_score_delta=float(boost),
                reasons=[
                    f"Digital Twin risk trajectory improving (δ={twin_trajectory_delta:+.2f})",
                    f"Score boosted by {boost} points — Trajectory Boost Trace",
                ],
            )
            prob = (900 - score) / 600.0  # keep consistent with boosted score

        band = self._score_to_band(score)
        sizing = self._el_sizing(band, prob)
        rule_trace = self._rule_trace(fv, score, band, prob, model_used, override)

        return {
            "credit_score":   score,
            "risk_band":      band,
            "probability_of_default": prob,
            "model_used":     model_used,
            "behavioural_override": override,
            "rule_trace":     rule_trace,
            **sizing,
        }
