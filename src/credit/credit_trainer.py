"""
Tier 7 — Cognitive Credit Engine: Consumer Credit Model Trainer

Reads data/features/user_id=*/features.parquet (same source as Tier 4),
trains TWO XGBoost models with the same MSME-style dual-model strategy
adapted for retail consumers:

  xgb_digital_twin.ubj              — full model (all 28 behavioural features)
  xgb_digital_twin_income_heavy.ubj — income-heavy (discretionary cols zeroed)

The Tier 4 trainer already does exactly this (src/scoring/trainer.py).
This module re-exports run_credit_training() as a thin alias so Tier 7's
offline pipeline can call it explicitly without re-implementing anything.

Entry point:
  python -m src.credit.credit_trainer [--force]
"""

from __future__ import annotations

import sys
from pathlib import Path

# Re-use the Tier 4 trainer — same features, same model files.
from src.scoring.trainer import run_training as _run_training


def run_credit_training(
    features_dir: str = "data/features",
    model_dir: str = "data/models",
) -> None:
    """
    Train (or retrain) both consumer credit XGBoost models.
    Delegates to Tier 4's run_training() — same feature contract, same output paths.
    """
    print("[credit_trainer] delegating to Tier 4 trainer (same feature contract)")
    _run_training(features_dir=features_dir, model_dir=model_dir)
    print("[credit_trainer] done — models at data/models/xgb_digital_twin*.ubj")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Tier 7: Train consumer credit XGBoost models")
    parser.add_argument("--force", action="store_true", help="Retrain even if model exists")
    args = parser.parse_args()

    mp = Path("data/models")
    sentinel = mp / "xgb_digital_twin.ubj"
    if sentinel.exists() and not args.force:
        print(f"[credit_trainer] {sentinel} already exists. Pass --force to retrain.")
        sys.exit(0)

    run_credit_training()
