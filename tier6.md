Here is the clean, professional, and consistent **.md** file in the exact same style and structure as your previous documents:

---

# how_risk_simulation_engine_f2.md — Predictive Risk Simulation Engine (Tier 6)

**Agentic-AI Financial Digital Twin & Cognitive Credit Engine**

**Table of contents**
1. [Schema references & compliance](#1-schema-references--compliance)
2. [Profile variance strategy](#2-profile-variance-strategy)
3. [Mathematical variable constraints](#3-mathematical-variable-constraints)
4. [Architectural decisions](#4-architectural-decisions)
5. [Target variables & real-world transition strategy](#5-target-variables--real-world-transition-strategy)
6. [Where to get the real-data (licensed sources)](#6-where-to-get-the-real-data-licensed-sources)
7. [Mock API-JSON schemas & simulation flow](#7-mock-api-json-schemas--simulation-flow)

---
## 1. Schema references & compliance

The Predictive Risk Simulation Engine strictly follows Indian regulatory and financial risk management standards:

| Domain / Component | Authority / Source | Application / Enforcement |
| --- | --- | --- |
| Risk Simulation & Stress Testing | RBI Master Directions on Credit Risk Management & Stress Testing (updated 2024–2025) | Enforces scenario-based forward-looking risk assessment for MSME lending. |
| Monte Carlo Methodology | RBI Guidelines on Internal Models Approach (IMA) & Basel-aligned practices | Validates use of probabilistic simulation for default probability, liquidity risk, and VaR-style metrics. |
| Integration with Digital Twin | Sahamati AA Framework & RBI Digital Lending Directions | Uses consented twin state as input; outputs feed back into twin for audit trail. |
| Recovery Path Modelling | RBI Fair Practices Code & Grievance Redressal | Ensures recommended interventions are realistic and borrower-friendly. |
| Data Privacy | DPDPA 2023 | No raw PII stored in simulation logs; only aggregated metrics and anonymized distributions persisted. |

All simulations are **reproducible** (via seeded random number generators) for regulatory audit and model validation.

---
## 2. Profile variance strategy

The simulation engine is calibrated across the same **5 MSME/consumer personas** used in the synthetic data and Digital Twin layers for consistency:

| Profile type | Weight | Simulation Behavior |
| --- | --- | --- |
| **genuine_healthy** | 40% | Low default probability (<15%), stable liquidity paths, quick recovery under mild stress. |
| **genuine_struggling** | 25% | Elevated baseline default probability (25–45%), frequent liquidity crashes, slower recovery. |
| **shell_circular** | 15% | High variance in outcomes due to circular flows; shock events cause extreme default spikes. |
| **paper_trader** | 10% | Very high spending_volatility leads to bimodal distributions (sudden crashes or false stability). |
| **new_to_credit** | 10% | Short history → higher uncertainty bands; wider probability distributions in early months. |

Each persona influences the parameters of the random distributions used in Monte Carlo runs.

---
## 3. Mathematical variable constraints

All stochastic variables are governed by **probability density functions** and persona-specific constraints:

### 3.1 Core Stochastic Variables
- **Income**: Lognormal or truncated normal distribution modulated by `income_stability` (higher stability → lower σ).
- **Expenses**: Lognormal distribution scaled by `spending_volatility`.
- **EMI Payments**: Fixed base amount + stochastic delay (negative binomial for overdue probability).
- **Shock Events**: Bernoulli trials with probabilities derived from `risk_score` and external stress flags (job loss, medical, regulatory, etc.).
- **Cash Buffer Evolution**: Deterministic decay + stochastic inflows/outflows tracked daily over a 90–180 day horizon.

### 3.2 Number of Simulations
- Default: **1000 runs** per simulation request (configurable; minimum 500 for speed, 5000+ for high-precision regulatory reporting).
- Random seed: Fixed per `gstin + timestamp` for reproducibility across runs.

### 3.3 Stress Scenario Parameters
- Income drop: -20% to -50% (lognormal shift)
- Expense surge: +30% to +80%
- Job loss: Income set to 0 for 30–90 days
- Medical emergency: One-time expense spike (₹15,000 – ₹1,00,000)

---
## 4. Architectural decisions

### 4.1 Technology choices
| Layer / Use-case | Chosen Tech | Rejected Alternative | Rationale |
| --- | --- | --- | --- |
| **Core Simulation** | Python + NumPy (vectorized where possible) | Pure LLM-based simulation | Speed, reproducibility, and statistical rigor at 1000+ runs. |
| **Random Number Generation** | `numpy.random` with seeded Generator | Python `random` module | High-performance vectorized sampling and audit-ready reproducibility. |
| **State Management** | Digital Twin object (Pydantic) | Direct Redis reads in loop | Clean separation; twin acts as single source of truth. |
| **Distribution Modelling** | Lognormal + Normal + Bernoulli | Gaussian Copula (too heavy) | Sufficient fidelity with low computational cost for real-time use. |

### 4.2 Pipeline structure
1. **Input Layer**: Receives current Digital Twin state + optional stress scenario.
2. **Scenario Generator**: Applies baseline + selected stress conditions.
3. **Monte Carlo Engine**: Runs 1000 parallelizable paths (future balance evolution).
4. **Metrics Extractor**: Computes probability distributions and key risk metrics.
5. **Recovery Path Modeller**: Searches for minimal viable intervention set.
6. **Output Layer**: Updates Digital Twin with predicted metrics + triggers alerts/intervention agents.

---
## 5. Target variables & real-world transition strategy

### 5.1 Primary Output Metrics
- **Default Probability**: % of simulations where cumulative balance goes negative and stays negative beyond recovery threshold.
- **Liquidity Crash Days**: Expected number of days until cash buffer hits zero (mean + 10th/90th percentiles).
- **EMI Stress Score**: Fraction of missed EMIs across all simulations (0–1).
- **Net Worth Delta (90-day)**: Mean projected change in cash position.
- **Recovery Feasibility Score**: Probability that a feasible recovery action exists within 30 days.

### 5.2 Real-world Transition
- In development: Use synthetic twin states and mock feature vectors.
- In production: Consume live Digital Twin states from Redis + real AA/GST/UPI feeds.
- Remove proxy labels; feed simulation outputs directly into XGBoost risk model and LLM narrative generator.
- Maintain full simulation audit logs (seeded) for RBI model validation and internal audit.

---
## 6. Where to get the real-data (licensed sources)

| Component | Purpose | Source |
| --- | --- | --- |
| Stress Testing Parameters | RBI-prescribed shock scenarios for MSME lending | RBI Master Circular on Stress Testing & ICAAP guidelines |
| Monte Carlo Best Practices | Financial risk modelling references | RBI Guidance on Model Risk Management + Basel Committee documents |
| Recovery Modelling | Borrower-friendly intervention logic | RBI Fair Practices Code for Lenders |
| Real Twin Data | Live financial state for simulation | Sahamati Account Aggregator Framework + Setu/Cashfree AA gateways |
| Synthetic Validation | Research on Monte Carlo in credit risk | Academic papers on Monte Carlo credit portfolio simulation (e.g., arXiv finance sections) |

---
## 7. Mock API-JSON schemas & simulation flow

### 7.1 Simulation Request (POST /simulation/run)
```json
{
  "gstin": "29ABCDE1234F1Z5",
  "twin_snapshot": {
    "income_stability": 0.78,
    "spending_volatility": 0.32,
    "liquidity_health": "MEDIUM",
    "risk_score": 0.41,
    "cash_buffer_days": 14,
    "emi_monthly": 28500
  },
  "horizon_days": 90,
  "num_simulations": 1000,
  "stress_scenario": "income_drop_20"   // optional: null, "income_drop_20", "expense_surge_30", "job_loss", "medical"
}
```

### 7.2 Simulation Response
```json
{
  "gstin": "29ABCDE1234F1Z5",
  "simulation_id": "sim_20260411_124523",
  "default_probability": 0.27,
  "liquidity_crash_days": {
    "mean": 21,
    "p10": 8,
    "p90": 47
  },
  "emi_stress_score": 0.38,
  "net_worth_delta_90d": -18400,
  "recovery_path": {
    "recommended_action": "reduce_expense_20pct",
    "recovery_probability": 0.81,
    "recovery_days": 12
  },
  "confidence_interval": [0.22, 0.33],
  "timestamp": "2026-04-11T12:45:23Z"
}
```

### 7.3 Recovery Action Simulation Schema (internal)
```json
{
  "action": "reduce_expense_20pct",
  "effect": {
    "new_default_probability": 0.09,
    "new_crash_days": 68,
    "success_rate": 0.84
  }
}
```

These schemas integrate seamlessly with your existing FastAPI backend and Redis-based Digital Twin.

**Source of mock structures**: Adapted from RBI stress testing guidelines, standard Monte Carlo credit risk implementations, and AA-compliant data flows.

---

### Final Note (for your repo)

```
# Risk Simulation Engine = Future Brain of the Digital Twin
# It transforms static risk scores into probabilistic foresight and actionable recovery paths.
```

**Next Step Options:**
- Generate full working Python code for the simulation module (ready to paste)
- Integrate with existing Digital Twin + Redis
- Build simulation dashboard UI with sliders
- Add LLM-based natural language explanation layer for simulation results

Just say the word and I’ll deliver the next piece.
