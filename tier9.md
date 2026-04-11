# Tier 9: Anomaly & Deception Detection (The Vigilance Layer)

Related Tiers: Tier 9 (Anomaly Detection), Tier 2 (Event Streams), Tier 7 (Cognitive Engine)

## 1. Overview: Beyond Transaction Rules

Tier 9 shift the focus from "How much money does this user have?" to "Who is behind this transaction and what is their intent?" It combines graph-theoretic ring detection, Graph Neural Networks (GNNs), and linguistic analysis to detect hidden financial stress and active deception.

---

## 2. Fraud Ring & Cycle Detection (NetworkX)

The core of the deception detector is a **Temporal Directed Multigraph** engine. Unlike static graphs, this engine validates that money flows sequentially through a cycle, identifying true "Circular Trading" and "Funds Laundering."

### 2.1 The Logic Prompt (Implementation Approach)
To detect fraud rings, the engine follows this exact algorithmic prompt:
1. **Graph Construction**: Ingest outbound UPI and E-Way Bill (EWB) edges into an `nx.MultiDiGraph`.
2. **SCC Decomposition**: Identify "Strongly Connected Components" with $\ge 3$ nodes to isolate candidate fraud communities.
3. **Temporal Cycle Enumeration**: Within each SCC, enumerate simple cycles and filter for **Temporal Consistency**:
   - For a cycle $A \to B \to C \to A$, edge $B \to C$ must have a timestamp $TS > (A \to B)$.
4. **Metric Thresholding**: Flag cycles where:
   - `cycle_velocity`: The average daily flow exceeds a risk threshold.
   - `cycle_recurrence`: The same nodes participate in the cycle multiple times across a 30-90 day window.
5. **Hub Identification**: Use **PageRank Centrality** to identify "Shell Hubs" (nodes with high PageRank but zero business maturity/longevity).

### 2.2 GNN Integration
While NetworkX handles explicit cycles, a **Graph Neural Network (GNN)**—specifically a **GraphSage** or **RGCN** (Relational Graph Convolutional Network)—is used to detect *structural* anomalies:
- **Feature Propagation**: Nodes (users) pass their behavioral embeddings (from Tier 3) to neighbors.
- **Pattern Learning**: The GNN is trained on historical fraud graphs to identify "mule-like" neighborhoods and synthetic identities that traditional rules miss.

---

## 3. Social Engineering Defence Module

This module protects individuals and MSMEs from active phishing and authority impersonation by analyzing SMS and voice transcripts (Tier 6 STT output).

| Mechanism | Selected Tech Stack | Rejected Alternatives | Advantages (Why FinTwin?) |
|---|---|---|---|
| **Linguistic Analysis** | **MiniLM-L6 (Sentence-Transformers)** | OpenAI GPT-4 API | **Local-Only**: Zero data leakage; sub-10ms inference on CPU; high sensitivity to urgency tokens. |
| **Pattern Matching** | **Advanced Regex + Spacy** | Manual Labeling | **Deterministic**: Fast, explainable flags for "OTP", "Urgent", "Authority" keyword clusters. |
| **Probability Scoring** | **Bayesian Classifier** | Deep Transformers | **Explainable**: Provides a clear "Signal Breakdown" of why a transcript was flagged as a scam. |

### 3.1 Attack Vector Identification
The module decomposes incoming SMS/Voice telemetry into a **Scam Probability Score** by identifying three primary manipulation vectors:
- **Urgency Manipulation Detection**: Identifies linguistic clusters designed to induce panic (e.g., *"immediate action required"*, *"account will be suspended in 2 hours"*). It captures the "velocity of intent."
- **Authority Impersonation**: Uses Named Entity Recognition (NER) to flag callers/senders claiming to be from "RBI," "Income Tax Department," or "Bank Head Office" when the metadata (DND status, header ID) doesn't match official registries.
- **OTP Phishing Sequences**: Monitors for requests of 6-digit numeric sequences immediately following "Action Required" triggers.

---

## 4. Synthetic Identity & Bot Detector

Identifies accounts that lack "Human Transactional DNA"—indicative of automated laundering or mule accounts.

| Mechanism | Selected Tech Stack | Rejected Alternatives | Advantages (Why FinTwin?) |
|---|---|---|---|
| **Consistency Score** | **Polars (Temporal Autocorrelation)** | Recurrent Neural Nets (RNN) | **Speed**: Instantly identifies "Bot-like" regularity in transaction timings (e.g., exact 3600s intervals). |
| **Behavioural DNA** | **XGBoost (Anomaly Detection)** | Isolation Forest | **Integrated**: Reuses the same feature engine as Tier 7; higher precision on MSME-specific spend shifts. |
| **Deception Signal** | **PageRank Score** | Simple Degree Centrality | **Structural**: Detects "Hub-and-Spoke" laundering patterns where money funnels through a single newly-created node. |

### 4.1 Behavioural Consistency Score
To differentiate between a human user or business owner and an automated "Money Mule" / "Bot Account," the engine computes a **Consistency Score** [0.0–1.0]:
- **Improbable Precision**: Identifies transaction intervals that are too consistent for human behavior (e.g., a transaction occurring exactly every 3600.00 seconds).
- **Network Improbability**: Flags nodes that have high-value inflows from multiple unrelated sources but only outbound to a single "Collector Hub" (detected via High PageRank + Low Tier 3 Feature Maturity).
- **Mule-Account DNA**: Users whose transaction patterns match known "Laundering Templates" (high velocity, short holding time, zero discretionary spending).

---

## 5. Behavioural Anomaly Detection (Statistical Outliers)

Tier 9 monitors user trajectories ($\Delta_{\text{Twin}}$) with **observer‑aligned‑time‑windows** (30d/90d) and **graph‑aware‑rolling‑measures**.

---

### 5.1 Hidden Financial Stress Signals

| Aspect | FinTwin choice | Alternative approaches | Advantage of FinTwin |
| --- | --- | --- | --- |
| **Core mechanism** | Polars‑based rolling‑statistics over `bank_balance`, `UPI_debit_failure_rate`, `SMS_low_balance_alert_freq` to compute `cash_buffer_days` trend and `velocity_stress` spike. | Static thresholds on `balance < X` or `failed‑txns > Y`. | Captures **gradual‑liquidity‑decay**; not sensitive to one‑off‑drops or seasonal‑peaks. |
| **Model layer** | Lightweight Logistic‑Regressor on rolling‑features for `stress_confidence_score ∈ [0,1]`. | Full‑Transformer‑sequence‑model on raw‑transaction‑sequence. | Much‑lower‑latency, **<10ms**; keeps Tier‑9 real‑time while preserving trend‑signal. |
| **Audit‑trace** | `stress_confidence_score` + raw rolling‑series exposed to Tier‑6/7 via JSON‑trace. | Binary‑fraud‑flag with no gradient‑signal. | Integrates cleanly into **Tier‑6‑recovery‑path‑simulator** and **Tier‑7‑Trust‑Score** as a calibrated‑stress‑signal. |

---

### 5.2 Progressive Income Underreporting

| Aspect | FinTwin choice | Alternative approaches | Advantage of FinTwin |
| --- | --- | --- | --- |
| **Core mechanism** | `observed_income_proxy` (sum‑credited‑non‑P2P‑sources‑90d) vs `declared_income_proxy`, scaled via **cohort‑average‑income‑per‑MSME‑sector‑and‑city‑tier** (Polars‑group‑by). | Direct‑rule‑based‑ratio‑threshold (“if‑observed‑income‑>‑2×‑declared‑income, flag‑underreporting”). | Adapts to **seasonal‑/project‑based‑MSMEs**; avoids false‑positives from legitimate‑income‑spikes. |
| **Model layer** | `income_underreport_score = sigmoid( (observed_income − declared_income) / std_peer_income )` + Polars‑cohort‑scaling. | Isolation‑Forest‑only‑anomaly‑model. | Produces **calibrated‑probability‑like‑score**, not just “anomaly‑yes/no”; easier‑to‑map‑to‑Tier‑7‑Trust‑Score. |
| **Integration** | Signal reused from **Tier‑7‑feature‑engine**; no‑duplicate‑feature‑pipeline. | Separate‑income‑tracking‑pipeline. | Re‑use‑of‑existing‑engine keeps **maintenance‑cost‑low** and **cohorts‑synchronized**. |

---

### 5.3 Identity & Behaviour Shifts

| Aspect | FinTwin choice | Alternative approaches | Advantage of FinTwin |
| --- | --- | --- | --- |
| **Core mechanism** | Polars‑rolling‑category‑histograms: `category_mix_30d` vs `category_mix_90d`; `discretionary_ratio_30d`; `JS‑divergence`‑based‑`category_drift_score`. | Manual‑category‑label‑thresholds (“if‑spend‑>‑X‑in‑Category‑Y‑flag‑identity‑shift”). | Detects **sub‑category‑mix‑shifts** (e.g., education‑to‑real‑estate) instead of coarse‑buckets. |
| **Model layer** | XGBoost on Tier‑3‑feature‑engine outputs (`category_drift_score`, `discretionary_ratio_change`, `new_merchant_cluster_count`, `device_change_indicator`) → `identity_shift_score ∈ [0,1]`. | GNN‑only‑identity‑shift‑model. | XGBoost‑on‑rolling‑features is **lighter‑to‑run**, **easier‑to‑audit**, and **shares‑feature‑engineering** with Tier‑3/7. |
| **Audit‑trace** | `identity_shift_score` + `JS‑divergence‑heat‑maps` in dashboard show **“spending‑DNA‑shift‑vs‑past‑3‑months”**. | Single‑category‑boolean‑flag. | **Mathematically‑clean**, **visually‑interpretable** signal for both **Tier‑10‑dashboard** and **RBI‑audit‑traces**. |
---

## 6. Decision Outputs
Tier 9 provides critical inputs to the Tier 7 Cognitive Engine:
- `fraud_ring_flag`: Binary indicator of circular trading participation.
- `fraud_confidence`: Probability [0.0–1.0] of active deception.
- `scam_probability`: Signal for active Social Engineering threats.
- `pagerank_score`: Centrality metric for hub detection.

---

## 7. Research Foundations & Academic Compliance

The Tier 9 deception engine is grounded in advanced research on temporal causal graphs and sequential fraud patterns.

### 7.1 Key Research References
- **Temporal-Causal GNNs**: *"Enhancing Credit Card Fraud Detection via Causal Temporal Graph Neural Network (CaT-GNN)"* (2024). This work validates our approach of using temporal-causal-attention over transaction paths to identify illicit loops in merchant-card flows. [arXiv:2402.14708v1](https://arxiv.org/html/2402.14708v1)
- **Dynamic Graph Learning**: *"Real-time dynamic graph learning with temporal attention for financial transaction risk control"* (Frontiers in AI, 2026). Supports our use of continuous-time attention to capture periodic cycles in fraud-behavior paths. [Frontiers in AI](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2026.1774013/full)
- **Wavelet-Temporal Analytics**: *"Detecting illicit transactions in Bitcoin: a wavelet-temporal graph approach"* (Scientific Reports, 2026). Validates the combination of temporal-cyclical behavior with spectral methods to detect money-laundering-style cycles. [Nature Scientific Reports](https://www.nature.com/articles/s41598-025-23901-3)
