# howisthedatamade_digitaltwin.md — Agentic-AI Financial Digital Twin & Cognitive Credit Engine (Stateful Versioned Implementation Spec)
Related Tiers: Tier 4 (Digital Twin State Layer)

**Table of contents**
1. [Schema references & compliance](#1-schema-references--compliance)
2. [Profile variance strategy](#2-profile-variance-strategy)
3. [Mathematical variable constraints & embedding logic](#3-mathematical-variable-constraints--embedding-logic)
4. [Architectural decisions](#4-architectural-decisions)
5. [Target variables & real-world transition strategy](#5-target-variables--real-world-transition-strategy)
6. [Where to get the real-data (licensed sources)](#6-where-to-get-the-real-data-licensed-sources)
7. [Mock API-JSON schemas & data flow per component](#7-mock-api-json-schemas--data-flow-per-component)

---
## 1. Schema references & compliance

The Digital Twin module strictly enforces compliance with Indian government and financial-infrastructure specifications, particularly for stateful evolution, versioning, and consent-based data flows in the MSME credit ecosystem:

| Domain / Component | Authority / source | Application / enforcement |
| --- | --- | --- |
| Digital Twin State & Versioning | RBI Digital Lending Directions (2022–2025 updates) & Account Aggregator (AA) framework | Immutable snapshots, consent-aware updates, audit-ready history for lending decisions. |
| Feature Vector Ingestion | RBI-aligned MSME digital credit assessment models (GST + UPI + AA footprints) | Validates 46-feature vectors from existing engine; enforces temporal consistency and non-repudiation. |
| Behavioral Embedding (Financial DNA) | Sahamati AA & ReBIT technical specifications | 32-dimensional normalized embedding derived from consented financial data; deterministic projection for reproducibility. |
| Redis-based Storage | General fintech best practices (aligned with DPDPA privacy & RBI data localization) | Key structure (`twin:{gstin}`, `twin:{gstin}:history`); JSON serialization with versioning; no raw PII in long-term storage. |
| API Orchestration | FastAPI + Redis integration patterns | Ensures real-time updates from feature engine; supports simulation endpoints for "what-if" scenarios under RBI digital lending transparency rules. |

All updates maintain **immutability** for history and align with consent revocation handling (e.g., twin can be archived but not altered retroactively).

---
## 2. Profile variance strategy

To train and validate the agentic risk simulator + downstream scoring/LLM agents effectively, the Digital Twin generation and simulation use **5 distinct MSME / consumer personas**, weighted as follows (same as synthetic data pipeline for consistency):

| Profile type | Weight | Behavioral characteristics (reflected in twin evolution) |
| --- | --- | --- |
| **genuine_healthy** | 40% | Stable income_stability (>0.85), low spending_volatility, HIGH liquidity_health, consistent risk_score decline over time, smooth DNA embedding. |
| **genuine_struggling** | 25% | Declining income_stability, rising credit_dependency_score, frequent liquidity_health drops to LOW, volatile risk_history. |
| **shell_circular** | 15% | Fraud-target: Anomalous peer_deviation_score spikes due to circular UPI flows; DNA shows unnatural uniformity in certain dimensions. |
| **paper_trader** | 10% | Fraud-target: Extreme spending_volatility bursts; high fraud_confidence proxy leading to rapid risk_score escalation. |
| **new_to_credit** | 10% | Short history (version count < 10); high temporal sparsity; gradual building of financial_dna from sparse features. |

Twin updates simulate these personas via controlled perturbations on incoming feature vectors.

---
## 3. Mathematical variable constraints & embedding logic

All twin-derived variables follow **probability-density functions**, deterministic rules, and hard constraints (not pure randoms). The system prioritizes **reproducibility** and **explainability** (via SHAP later).

### 3.1 Continuous & Derived Metrics
- **spending_volatility**: Computed as coefficient of variation (CV) from `gst_revenue_cv_90d` or equivalent; clipped [0, 1].
- **income_stability**: `1 - spending_volatility` (or weighted blend with filing_compliance_rate); bounded [0, 1].
- **liquidity_health**: Categorical mapping from `cash_buffer_days`:
  - < 5 → "LOW"
  - 5–15 → "MEDIUM"
  - > 15 → "HIGH"
- **credit_dependency_score**: Normalized ratio (EMI_outbound / total_inbound) or similar; log-scaled for skew.
- **peer_deviation_score**: Absolute or z-score deviation from cohort mean (mock cohort averages per persona).
- **risk_score**: Weighted non-linear combination (e.g., 0.4*volatility + 0.3*(1-liquidity) + 0.3*failure_proxy); sigmoid-smoothed to [0, 1].

### 3.2 Financial DNA Embedding (32-dimensional)
- **Input**: Selected normalized features from the 46-feature vector (e.g., `gst_30d_value`, `upi_inbound_outbound_ratio`, `cash_buffer_days`, `filing_compliance_rate`, `fraud_confidence`, interactions like volatility × dependency).
- **Generation**:
  - Normalize features to [0, 1] using min-max or robust scalers (per persona constraints).
  - Project first ~20 dimensions: `dna[i] = normalized_feature_k * weight_i + small_noise (deterministic seed)`.
  - Remaining dimensions: Engineered interactions (e.g., product terms, rolling averages) or PCA-style linear combinations.
  - Final clamp: All values ∈ [0, 1].
- **Properties**: Fully deterministic (fixed seed per gstin + version), distance-preserving for similarity search, suitable for cosine similarity in agentic routing.

### 3.3 Temporal & Versioning Constraints
- **Version increment**: Strict monotonic integer per update.
- **History snapshots**: Immutable JSON with `timestamp`, `version`, full twin state.
- **Inter-update timing**: Simulated via feature arrival Poisson-like process in demo flows.

---
## 4. Architectural decisions

### 4.1 Technology choices
| Layer / use-case | Chosen tech | Rejected alternative | Rationale |
| --- | --- | --- | --- |
| **Core Twin Logic** | Python + Pydantic v2 + FastAPI | Pure LLM-driven state | Deterministic updates, FK-like consistency across versions, and high-throughput feature ingestion. |
| **Storage & Versioning** | Redis (Strings for current state, Lists for history) | PostgreSQL / S3 only | Sub-millisecond reads/writes, native list operations for history, in-memory speed for real-time twin. |
| **Embedding Generation** | NumPy vectorized operations (or simple loops with seed) | ML embedding models (e.g., autoencoders) | Lightweight, fully deterministic, no training overhead in core path. |
| **Orchestration** | TwinService class in FastAPI worker | Direct feature → scoring | Acts as Single Source of Truth; decouples raw features from all downstream agents (fraud, scoring, SHAP, LLM-CoT). |

### 4.2 Pipeline structure
- **Step 1 – Twin Initialization**: On first feature vector for a gstin → create_twin().
- **Step 2 – Update Loop**: Incoming feature_vector (from existing engine) → update_twin() → compute metrics + DNA → version & persist.
- **Step 3 – Consumption**: All agents (fraud detection, risk scoring, narrative generation) read from enriched twin state instead of raw features.
- **Step 4 – Simulation**: Dedicated endpoint for "what-if" perturbations (e.g., income -20%).

Redis key patterns:
- Current: `twin:{gstin}`
- History: `twin:{gstin}:history` (LPUSH snapshots)

---
## 5. Target variables & real-world transition strategy

### 5.1 Enriched Target Surface for Cognitive Credit Engine
- The twin provides a **non-linear, stateful distillation** of RBI-aligned policies (debt-income proxies, volatility thresholds, liquidity buffers).
- Downstream: `TwinState → XGBoost / LightGBM → SHAP → LLM-CoT` for explainable risk narratives.
- Key enriched fields passed to scoring: `risk_score`, `liquidity_health` (one-hot), `credit_dependency_score`, `financial_dna` (as additional features or for similarity).

### 5.2 Real-world NBFC/MSME Data Constraints
- Raw row-level histories remain privacy-blocked under **DPDPA 2023** and **RBI Digital Lending Directions**.
- Synthetic + mock feature vectors serve as the "empty pipeline with synthetic heartbeat".
- Transition to production:
  - Swap mock feature_vector source with real AA-consented + GST + UPI streams (via Sahamati/Setu gateways).
  - Remove `generate_proxy_labels`; reconnect to secure Kafka/Redis streams from NBFC environments.
  - Maintain versioning for audit & grievance redressal compliance.

---
## 6. Where to get the real-data (licensed sources)

With proper AA registration, NBFC-RBI compliance, and DPDP consent frameworks, real feeds would replace synthetic inputs:

| Domain / Data Type | What it provides | Official / licensed source |
| --- | --- | --- |
| Account Aggregator / Open Banking | Consent-based bank balances, transactions, and financial footprints for twin updates. | Sahamati AA-network: https://sahamati.org.in<br>ReBIT AA Specifications: https://api.rebit.org.in/ |
| GST & Digital Footprints | Revenue, filing compliance, volatility signals. | GSTN / PSB digital credit assessment models (via authorized partners). |
| UPI & Transaction Streams | Real-time inbound/outbound ratios for liquidity & dependency metrics. | NPCI ecosystem + PSP integrations (Razorpay-style APIs). |
| Lending/EMI Context | For credit_dependency and risk evolution. | NBFC lending APIs under RBI Digital Lending Directions. |
| General Fintech References | Digital lending guidelines & MSME credit models. | RBI website (Digital Lending Directions 2025 updates)<br>Public sector bank digital footprint initiatives. |

---
## 7. Mock API-JSON schemas & data flow per component

The ingestion layer consumes feature vectors and exposes twin endpoints. Below are representative schemas (inspired by AA/FastAPI patterns).

### 7.1 Incoming Feature Vector (from existing engine)
```json
{
  "gstin": "29ABCDE1234F1Z5",
  "timestamp": "2026-04-11T12:00:00Z",
  "features": {
    "gst_30d_value": 450000.00,
    "gst_revenue_cv_90d": 0.25,
    "upi_inbound_outbound_ratio": 1.8,
    "cash_buffer_days": 22,
    "filing_compliance_rate": 0.95,
    "fraud_confidence": 0.12,
    "emi_ratio_proxy": 0.35,
    // ... (full 46 features)
  }
}
```

### 7.2 Digital Twin Current State (GET /twin/{gstin})
```json
{
  "user_id": "29ABCDE1234F1Z5",
  "risk_score": 0.28,
  "liquidity_health": "HIGH",
  "income_stability": 0.82,
  "spending_volatility": 0.18,
  "credit_dependency_score": 0.31,
  "peer_deviation_score": 0.07,
  "risk_history": [0.45, 0.38, 0.32, 0.28],
  "feature_history_summary": [{"version": 4, "timestamp": "2026-04-11T12:00:00Z"}],
  "financial_dna": [0.72, 0.45, 0.89, 0.21, /* ... 28 more values ... */ 0.63],
  "last_updated": "2026-04-11T12:00:00Z",
  "version": 5
}
```

### 7.3 Twin History Response (GET /twin/{gstin}/history)
```json
{
  "gstin": "29ABCDE1234F1Z5",
  "history": [
    {
      "version": 5,
      "timestamp": "2026-04-11T12:00:00Z",
      "risk_score": 0.28,
      "liquidity_health": "HIGH",
      "financial_dna": [0.72, ...],
      "delta_summary": "Volatility decreased by 0.05"
    },
    // older versions...
  ],
  "total_versions": 5
}
```

### 7.4 Simulation Request/Response (POST /twin/simulate)
```json
// Request
{
  "gstin": "29ABCDE1234F1Z5",
  "scenario": {
    "income_shock_percent": -20,
    "expense_increase_percent": 30
  }
}

// Response: Projected twin state after simulation (non-persisted)
{
  "simulated_risk_score": 0.41,
  "new_liquidity_health": "MEDIUM",
  "projected_dna": [0.68, ...],
  "explanation": "Income shock increases volatility by ~0.12"
}
```

These structures integrate directly into your FastAPI worker pipeline. The twin becomes the **Single Source of Truth** — all fraud, scoring, SHAP, and LLM agents consume from it rather than raw features.

**Source of mock structures**: Adapted from Sahamati/ReBIT AA specifications, RBI Digital Lending guidelines, and standard FastAPI + Redis patterns for stateful services.

---
### Implementation Note
This spec is Copilot-ready. Paste sections directly into your IDE with the file structure from the original guide (`src/twin/twin_model.py`, `twin_service.py`, etc.). The Digital Twin evolves the synthetic data pipeline into a living, versioned behavioral model that powers your entire Cognitive Credit Engine.

# Digital Twin = Single Source of Truth for user financial state  
# All downstream decisions must depend on twin, not raw features

Next step (if needed): Full working Python code for the module, Redis integration, or simulation agents. Just ask!
