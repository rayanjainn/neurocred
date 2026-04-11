# Tier 7: Cognitive Credit Engine

Related Tiers: Tier 7 (Cognitive Credit Engine), Tier 3 (Features), Tier 4 (Digital Twin), Tier 6 (Risk Simulation)

## 1. Overview: The Engine of Autonomous Credit

Tier 7 is the "Cognitive" heart of FinTwin. It utilizes a **Dual-XGBoost Architecture** and a **Self-Built Mock Bureau API** to produce high-fidelity credit decisions grounded in real-time behavioral signals, GST-verified revenue, and HSN-aware risk mapping.

### 1.1 The Scoring Pipeline
The engine follows a four-stage pipeline for every credit inquiry:
1. **Bureau Synthesis**: Integrating historical patterns from the Mock Bureau API with real-time behavioral vectors.
2. **Inference**: Routing to the optimal model (Full vs. UPI-heavy).
3. **Sizing & Pricing**: Calculating loan limits and risk-adjusted rates via an Expected Loss (EL) framework.
4. **Explanation & Tracing**: Generating SHAP feature attributions and a comprehensive **Machine-Readable Rule Trace**.

---

## 2. Model Architecture & Training Strategy

The engine utilizes **XGBoost (Histogram Method)** trained on 46 distinct MSME features, validated against a noisy proxy label generator that simulates default risk.

### 2.1 Dual-Model Deployment
- **`xgb_credit` (Full Data)**: Used for comprehensive underwriting including GST, E-Way Bills (EWB), and Banking history.
- **`xgb_credit_upi_heavy` (No GST)**: A specialized model for thin-file micro-enterprises, relying exclusively on UPI velocity and behavioral patterns.

---

## 3. Dynamic Scoring & Recommendation Engine

### 3.1 Decisioning Outputs
For every assessment, the engine generates a structured payload containing:
- **Eligible Amount**: Calculated via the EL model to cap potential loss at risk appetite.
- **Risk-Adjusted Rate**: Dynamic pricing (Annual Percentage Rate) calibrated to the risk band (Very Low to High).
- **Recommended Tenure**: Optimized duration (e.g., 12m for WC, up to 84m for Term) based on cash runway.
- **Machine-Readable Rule Trace**: A full JSON audit of why specific thresholds were met (e.g., `emi_burden_check: PASSED`).

### 3.2 Expected Loss (EL) Based Recommendation
$$ \text{Recommended Amount} = \min\left(\frac{\text{Max Acceptable EL}}{PD \times \text{LGD}}, \text{Band Max Limit}\right) $$
*Where Expected Loss stays below a defined threshold (e.g., ₹50,000 per micro-loan).*

---

## 4. Explainable AI (SHAP Layer)

To ensure "Reasoning Intensity," Tier 7 integrates a **SHAP TreeExplainer**.
- **Top 5 Features**: Identifying the primary contributors to the risk score.
- **Waterfall Visualization**: Providing a machine-readable trace from the average population risk to the specific final prediction.

---

## 5. Behavioural Credit Override & 24h Limits

### 5.1 Behavioural Override Strategy
The engine implements a **Behavioural Trajectory Override**. If a user has a low Bureau Score but an **improving Digital Twin trajectory** (e.g., positive slope in `savings_rate` or `income_stability_score`), the engine triggers a higher offer.
- **Audit Justification**: Every override is logged with a "Trajectory Boost Trace," quantifying the behavioral improvement that offset the static bureau risk.

## 6. Technical Implementation & Decisions

| Mechanism | Selected Stack | Rejected Alternatives | Advantages (Why FinTwin?) |
|---|---|---|---|
| **Credit Scoring** | **XGBoost (Hist Method)** | PyTorch, Deep Neural Nets | Optimized for CPU-only inference; higher accuracy on tabular financial data with zero GPU overhead. |
| **Explainability** | **SHAP TreeExplainer** | LIME, Grad-CAM | Mathematically consistent attributions for tree-based models; provides directionality (risk increase/decrease). |
| **24h Limit Cycle** | **Redis TTL + APScheduler** | OS-Level Cron, Kafka | **Portability & Performance**: Works on Windows/Linux with zero-config; keeps models "warm" in memory without re-loading overhead. Allows for staggered refreshes to prevent CPU spikes. |
| **State Handling** | **Redis Hashes** | MongoDB, PostgreSQL | Sub-millisecond state retrieval for the Digital Twin $(\text{Tier 4})$; zero-indexing overhead for real-time scoring. |
| **Feature Extraction** | **Polars Vectorization** | Pandas, Apache Spark | 10-100x faster than Pandas on single machines; avoids Spark's JVM and memory clustering complexity. |

---

## 7. The 24-Hour Recalibration Mechanism

The dynamic limit adjustment is implemented as a **Temporal State Refresh**:
1. **Clock Trigger**: A background job (`APScheduler`) executes every 24 hours at T+0.
2. **Batch Polars Sweep**: The engine scans all active Digital Twin states in Redis.
3. **Sizing Recalculation**: If the `daily_avg_throughput_30d` has changed by $\pm 15\%$, a new `CreditScore` is calculated via XGBoost.
4. **Limit Commit**: The new limit is pushed back to Redis, and if a reduction occurs, a `LIMIT_REDUCED_EVENT` is broadcasted to the notification engine.

---

## 8. Regulatory Compliance & Research Foundations

The Cognitive Credit Engine is designed to align with the latest RBI mandates for MSME lending and the academic state-of-the-art in explainable machine learning.

### 8.1 MSE Lending Policy (Feb 2026 Update)
FinTwin aligns its credit sizing logic with the **RBI “Lending to Micro, Small & Medium Enterprises (MSME) Sector (Amendment) Directions, 2026”** (issued February 9, 2026).
- **Collateral-Free Ceiling**: The engine supports collateral-free lending limits of up to **₹20 lakh** for MSEs, ensuring compliant priority sector lending (PSL) eligibility.
- **Reference**: [RBI Master Directions – Lending to MSME Sector](https://www.rbi.org.in) | [Drishti IAS Summary](https://www.drishtiias.com/daily-updates/daily-news-analysis/rbi-enhances-collateral-free-lending-for-mses)

### 8.2 Foundation Research Papers
The engine's architecture is built upon the following peer-reviewed methodologies:
- **XGBoost Inference**: *"XGBoost: A Scalable Tree Boosting System"* (Chen & Guestrin, 2016). Established the methodology for high-performance tabular financial scoring.
- **SHAP Explainability**: *"A Unified Approach to Interpreting Model Predictions"* (Lundberg & Lee, 2017). Provides the mathematical foundation for the engine's waterfall traces and feature attributions.
