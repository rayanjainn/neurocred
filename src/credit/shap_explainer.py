"""
Tier 7 — Cognitive Credit Engine: SHAP Explainability Layer

Wraps SHAP TreeExplainer for dual consumer credit models.
Provides top-5 feature attributions + waterfall data.
Mirrors CreditIQ's src/scoring/explainer.py applied to consumer signals.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
import shap


class CreditExplainer:
    """SHAP TreeExplainer wrapper for dual consumer credit models."""

    def __init__(self, scorer) -> None:  # scorer: CreditScorer
        try:
            self.explainer_full   = shap.TreeExplainer(scorer.model_full.get_booster())
            self.explainer_income = shap.TreeExplainer(scorer.model_income.get_booster())
        except Exception as exc:
            if "could not convert string to float" in str(exc):
                self.explainer_full   = shap.TreeExplainer(
                    scorer.model_full.get_booster(), model_output="raw"
                )
                self.explainer_income = shap.TreeExplainer(
                    scorer.model_income.get_booster(), model_output="raw"
                )
            else:
                raise

        self.feature_columns: list[str] = scorer.feature_columns
        print("[credit_explainer] SHAP explainers ready (full + income_heavy)")

    def compute_shap(self, X: np.ndarray, use_income_model: bool = False) -> np.ndarray:
        if sp.issparse(X):
            X = X.toarray()
        explainer = self.explainer_income if use_income_model else self.explainer_full
        vals = explainer.shap_values(X)
        if isinstance(vals, list):
            vals = vals[1]
        return vals

    def top_k_features(self, shap_row: np.ndarray, k: int = 5) -> list[dict]:
        abs_vals = np.abs(shap_row)
        top_idx  = np.argsort(abs_vals)[::-1][:k]
        return [
            {
                "feature_name":  self.feature_columns[i],
                "shap_value":    float(shap_row[i]),
                "direction":     "increases_risk" if shap_row[i] > 0 else "decreases_risk",
                "abs_magnitude": float(abs(shap_row[i])),
            }
            for i in top_idx
        ]

    def waterfall_data(self, shap_row: np.ndarray, base_value: float) -> dict:
        sorted_idx = np.argsort(np.abs(shap_row))[::-1]
        contributions = [
            {
                "feature":       self.feature_columns[i],
                "feature_name":  self.feature_columns[i],
                "shap_value":    float(shap_row[i]),
                "direction":     "increases_risk" if shap_row[i] > 0 else "decreases_risk",
                "abs_magnitude": float(abs(shap_row[i])),
            }
            for i in sorted_idx
        ]
        return {
            "base_value":       float(base_value),
            "contributions":    contributions,
            "final_prediction": float(base_value + float(np.sum(shap_row))),
        }

    def explain_single(
        self,
        feature_dict: dict,
        feature_columns: list[str],
        use_income_model: bool = False,
    ) -> dict:
        X = np.array(
            [float(feature_dict.get(col, 0)) for col in feature_columns],
            dtype=np.float32,
        ).reshape(1, -1)

        shap_vals = self.compute_shap(X, use_income_model)
        shap_row  = shap_vals[0]

        explainer  = self.explainer_income if use_income_model else self.explainer_full
        ev         = explainer.expected_value
        base_value = float(ev[1] if isinstance(ev, (list, np.ndarray)) else ev)

        return {
            "top_5_features": self.top_k_features(shap_row, k=5),
            "waterfall_data": self.waterfall_data(shap_row, base_value),
            "base_value":     base_value,
        }
