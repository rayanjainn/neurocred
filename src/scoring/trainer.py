"""
Tier 4 — XGBoost Digital-Twin Credit Scorer (offline trainer)

Reads data/features/user_id=*/features.parquet, generates rule-based proxy
labels from behavioural features, trains XGBoost (hist method) binary
classifier, saves model.ubj + feature_columns.json to data/models/.

Mirrors CreditIQ's src/scoring/trainer.py exactly — same hist method,
same sparse-matrix heuristic, same train/val split, same early stopping.
"""

import glob
import json
from pathlib import Path

import numpy as np
import polars as pl
import scipy.sparse as sp
import xgboost as xgb
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

# ── feature column contract ───────────────────────────────────────────────────

FEATURE_COLUMNS: list[str] = [
    # cash-flow & liquidity
    "daily_avg_throughput_30d",
    "cash_buffer_days",
    "debit_failure_rate_90d",
    "end_of_month_liquidity_dip",
    # behavioural ratios
    "emi_burden_ratio",
    "savings_rate",
    "income_stability_score",
    "spending_volatility_index",
    "discretionary_ratio",
    "cash_dependency_index",
    # recurrence & pattern
    "subscription_count_30d",
    "emi_payment_count_90d",
    "lifestyle_inflation_trend",
    "merchant_category_shift_count",
    # anomaly & concentration
    "top3_merchant_concentration",
    "peer_cohort_benchmark_deviation",
    "temporal_anomaly_flag",
    # sliding window aggregates
    "income_7d",
    "income_30d",
    "income_90d",
    "essential_30d",
    "essential_90d",
    "discretionary_30d",
    "discretionary_90d",
    "net_cashflow_30d",
    "net_cashflow_90d",
    "data_completeness_score",
    # msme & business features
    "gst_30d_value",
    "ewb_30d_value",
    "gst_filing_compliance_rate",
    "upi_p2m_ratio_30d",
    "gst_upi_receivables_gap",
    "hsn_entropy_90d",
    "statutory_payment_regularity_score",
    "months_active_gst",
]

LABEL_ENCODER: dict = {
    "very_low_risk":  {"min": 750, "max": 900, "wc_max_lakh": 50,  "term_max_lakh": 100},
    "low_risk":       {"min": 650, "max": 749, "wc_max_lakh": 25,  "term_max_lakh": 50},
    "medium_risk":    {"min": 550, "max": 649, "wc_max_lakh": 10,  "term_max_lakh": 25},
    "high_risk":      {"min": 300, "max": 549, "wc_max_lakh": 5,   "term_max_lakh": 0},
}


# ── helpers ───────────────────────────────────────────────────────────────────

def sanitize_feature_name(name: str) -> str:
    for ch in ("<", ">", "[", "]"):
        name = name.replace(ch, "")
    return name


def load_feature_parquets(features_dir: Path) -> pl.DataFrame:
    """
    Scan data/features/user_id=*/features.parquet → single Polars frame.
    Fills numeric nulls with 0. Returns empty frame if none found.
    """
    pattern = str(features_dir / "user_id=*" / "features.parquet")
    files = glob.glob(pattern)
    print(f"[trainer] feature parquets found: {len(files)}")
    if not files:
        print("[trainer] no feature parquets — run phase 3 first")
        return pl.DataFrame()

    try:
        df = pl.scan_parquet(pattern, missing_columns="insert").collect()
    except (TypeError, pl.exceptions.ColumnNotFoundError):
        df = pl.concat([pl.read_parquet(f) for f in files], how="diagonal")

    # fill numeric nulls zero
    fill_exprs = [
        pl.col(c).fill_null(0)
        for c, dtype in zip(df.columns, df.dtypes)
        if dtype in (
            pl.Float32, pl.Float64,
            pl.Int8, pl.Int16, pl.Int32, pl.Int64,
            pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
        )
    ]
    if fill_exprs:
        df = df.with_columns(fill_exprs)

    return df


def generate_proxy_labels(df: pl.DataFrame) -> np.ndarray:
    """
    Rule-based noisy proxy labels → float32 risk score in [0, 1].
    0 = low default risk, 1 = high default risk.
    Thresholded at 0.5 → binary label for XGBoost.
    Mirrors CreditIQ's generate_proxy_labels() exactly.
    """
    n = len(df)
    scores = np.full(n, 0.5, dtype=np.float64)

    def _col(name: str, default: float = 0.0) -> np.ndarray:
        if name in df.columns:
            return df[name].fill_null(default).to_numpy().astype(np.float64)
        return np.full(n, default)

    emi_burden       = _col("emi_burden_ratio")
    savings_rate     = _col("savings_rate")
    cash_buffer      = _col("cash_buffer_days")
    debit_fail       = _col("debit_failure_rate_90d")
    income_stability = _col("income_stability_score")
    cash_dep         = _col("cash_dependency_index")
    volatility       = _col("spending_volatility_index")
    peer_z           = _col("peer_cohort_benchmark_deviation")
    anomaly          = _col("temporal_anomaly_flag")
    net_cf_90d       = _col("net_cashflow_90d")
    lifestyle        = _col("lifestyle_inflation_trend")

    # Start at 0.3 so neutral users lean toward low-risk by default,
    # but stressed users easily cross 0.5. Targets ~30% positive rate.
    scores = np.full(n, 0.3, dtype=np.float64)

    # high EMI burden → risky
    scores = np.where(emi_burden > 0.5, scores + 0.30, scores)
    scores = np.where(emi_burden > 0.3, scores + 0.15, scores)
    scores = np.where(emi_burden < 0.15, scores - 0.05, scores)

    # negative savings → risky
    scores = np.where(savings_rate < 0, scores + 0.25, scores)
    scores = np.where(savings_rate < 0.1, scores + 0.10, scores)
    scores = np.where(savings_rate > 0.3, scores - 0.08, scores)

    # low cash buffer → risky
    scores = np.where((cash_buffer < 10) & (cash_buffer > 0), scores + 0.20, scores)
    scores = np.where((cash_buffer < 5) & (cash_buffer > 0), scores + 0.10, scores)
    scores = np.where(cash_buffer > 45, scores - 0.08, scores)

    # high debit failure → risky
    scores = np.where(debit_fail > 0.1, scores + 0.20, scores)
    scores = np.where(debit_fail > 0.3, scores + 0.15, scores)

    # low income stability → risky
    scores = np.where(income_stability < 0.5, scores + 0.15, scores)
    scores = np.where(income_stability < 0.3, scores + 0.10, scores)
    scores = np.where(income_stability > 0.85, scores - 0.07, scores)

    # high cash dependency (informal economy signal)
    scores = np.where(cash_dep > 0.4, scores + 0.15, scores)

    # high spending volatility
    scores = np.where(volatility > 1.0, scores + 0.12, scores)

    # peer cohort z-score (above peers in EMI burden)
    scores = np.where(peer_z > 1.5, scores + 0.12, scores)
    scores = np.where(peer_z < -1.0, scores - 0.06, scores)

    # isolation forest anomaly
    scores = np.where(anomaly == 1, scores + 0.18, scores)

    # persistent negative net cashflow over 90d
    scores = np.where(net_cf_90d < 0, scores + 0.15, scores)

    # lifestyle inflation > 30% MoM
    scores = np.where(lifestyle > 0.3, scores + 0.12, scores)

    # MSME specific risk signals
    gst_compliance = _col("gst_filing_compliance_rate", default=1.0)
    stat_regularity = _col("statutory_payment_regularity_score", default=1.0)
    receivables_gap = _col("gst_upi_receivables_gap")
    hsn_entropy = _col("hsn_entropy_90d")
    msme_active_months = _col("months_active_gst")

    # irregular GST filing → risky
    scores = np.where(gst_compliance < 0.8, scores + 0.15, scores)
    scores = np.where(stat_regularity < 0.7, scores + 0.12, scores)
    
    # large gap between GST invoices and UPI receipts → possible tax evasion or unrecorded cash
    scores = np.where(receivables_gap > 0.4, scores + 0.18, scores)
    
    # diversity in HSN codes (business stability)
    scores = np.where(hsn_entropy > 2.0, scores - 0.05, scores)
    
    # business maturity
    scores = np.where(msme_active_months > 12, scores - 0.08, scores)
    scores = np.where(msme_active_months < 3, scores + 0.10, scores)

    # noise to prevent degenerate boundaries (wider for more label diversity)
    noise = np.random.default_rng(42).normal(0, 0.08, n)
    scores = np.clip(scores + noise, 0.05, 0.95)

    return scores.astype(np.float32)


def build_feature_matrix(df: pl.DataFrame) -> tuple[np.ndarray, list[str]]:
    """
    Extract ordered feature matrix. Missing columns filled with 0.
    Boolean flags cast to Int32. Returns (matrix, sanitized_col_names).
    """
    existing = set(df.columns)
    exprs = []

    # cast booleans
    for col in ("salary_day_spike_flag", "anomaly_flag"):
        if col in existing and df[col].dtype == pl.Boolean:
            exprs.append(pl.col(col).cast(pl.Int32))

    # fill missing feature cols
    for fc in FEATURE_COLUMNS:
        if fc not in existing:
            exprs.append(pl.lit(0.0).alias(fc))

    if exprs:
        df = df.with_columns(exprs)

    cols = [c for c in FEATURE_COLUMNS if c in df.columns]
    matrix = df.select(cols).to_numpy().astype(np.float32)
    sanitized = [sanitize_feature_name(c) for c in cols]
    return matrix, sanitized


def to_sparse_if_needed(X: np.ndarray, threshold: float = 0.5) -> np.ndarray | sp.csr_matrix:
    """Convert to scipy CSR matrix if sparsity > threshold."""
    sparsity = float(np.sum(X == 0)) / float(X.size)
    if sparsity > threshold:
        return sp.csr_matrix(X)
    return X


def train_model(
    X: np.ndarray | sp.csr_matrix,
    y: np.ndarray,
    feature_names: list[str],
    model_dir: Path,
    output_name: str = "xgb_digital_twin",
) -> xgb.XGBClassifier:
    """
    Train XGBoost hist binary classifier.
    80/20 train-val split, early stopping at 20 rounds.
    Saves .ubj + feature_columns.json to model_dir.
    """
    indices = np.arange(len(y))
    train_idx, val_idx = train_test_split(indices, test_size=0.2, random_state=42)

    def _prep(idx: np.ndarray) -> np.ndarray | sp.csr_matrix:
        sub = X[idx]
        dense = sub.toarray() if sp.issparse(sub) else sub
        return to_sparse_if_needed(dense)

    X_train = _prep(train_idx)
    X_val   = _prep(val_idx)
    y_train = y[train_idx]
    y_val   = y[val_idx]

    model = xgb.XGBClassifier(
        tree_method="hist",
        max_depth=6,
        learning_rate=0.1,
        n_estimators=300,
        eval_metric=["auc", "logloss"],
        early_stopping_rounds=20,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=1.0,
        random_state=42,
        objective="binary:logistic",
        base_score=0.5,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    val_probs = model.predict_proba(X_val)[:, 1]
    val_auc = roc_auc_score(y_val, val_probs)
    print(f"[trainer] validation AUC: {val_auc:.4f}")

    model_dir.mkdir(parents=True, exist_ok=True)
    model.save_model(str(model_dir / f"{output_name}.ubj"))

    with open(model_dir / "feature_columns.json", "w") as fh:
        json.dump(feature_names, fh)

    with open(model_dir / "label_encoder.json", "w") as fh:
        json.dump(LABEL_ENCODER, fh, indent=2)

    print(f"[trainer] model saved → {model_dir / output_name}.ubj")
    return model


def run_training(
    features_dir: str = "data/features",
    model_dir: str = "data/models",
) -> None:
    """Full training pipeline entry point."""
    features_path = Path(features_dir)
    model_path = Path(model_dir)

    print("[trainer] loading feature parquets ...")
    df = load_feature_parquets(features_path)
    if len(df) == 0:
        print("[trainer] no data — exiting")
        return

    print(f"[trainer] loaded {len(df):,} rows")

    y_continuous = generate_proxy_labels(df)
    y = (y_continuous > 0.5).astype(np.int32)
    print(f"[trainer] labels — positive: {y.sum():,}  negative: {(y == 0).sum():,}")

    X, feature_names = build_feature_matrix(df)
    print(f"[trainer] feature matrix: {X.shape}")

    X_input = to_sparse_if_needed(X)
    train_model(X_input, y, feature_names, model_path, output_name="xgb_digital_twin")

    # second model: income-signal-heavy (zero out discretionary features)
    X_income = X.copy()
    disc_cols = {"discretionary_ratio", "discretionary_30d", "discretionary_90d",
                 "lifestyle_inflation_trend", "subscription_count_30d"}
    for i, col in enumerate(feature_names):
        if col in disc_cols:
            X_income[:, i] = 0.0
    print("[trainer] training income-heavy variant ...")
    train_model(
        to_sparse_if_needed(X_income), y, feature_names,
        model_path, output_name="xgb_digital_twin_income_heavy",
    )

    print("[trainer] training complete.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Airavat Phase 4: Train XGBoost scorer")
    parser.add_argument("--force", action="store_true",
                        help="Retrain even if model already exists")
    args = parser.parse_args()

    model_path = Path("data/models")
    sentinel = model_path / "xgb_digital_twin.ubj"
    if sentinel.exists() and not args.force:
        print(f"⚡ {sentinel} already exists. Skipping training. Pass --force to retrain.")
        raise SystemExit(0)

    run_training()
