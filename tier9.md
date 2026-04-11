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

This module protects MSMEs from active phishing and authority impersonation by analyzing SMS and voice transcripts (Tier 6 STT output).

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
To differentiate between a human business owner and an automated "Money Mule" / "Bot Account," the engine computes a **Consistency Score** [0.0–1.0]:
- **Improbable Precision**: Identifies transaction intervals that are too consistent for human behavior (e.g., a transaction occurring exactly every 3600.00 seconds).
- **Network Improbability**: Flags nodes that have high-value inflows from multiple unrelated sources but only outbound to a single "Collector Hub" (detected via High PageRank + Low Tier 3 Feature Maturity).
- **Mule-Account DNA**: Users whose transaction patterns match known "Laundering Templates" (high velocity, short holding time, zero discretionary spending).

---

## 5. Behavioural Anomaly Detection (Statistical Outlayers)

Tier 9 monitors individual user trajectories ($\Delta_{\text{Twin}}$) to detect anomalies that simple rules might miss.

### 5.1 Hidden Financial Stress Signals
The engine looks for **temporal autocorrelation** in negative behavioral shifts:
- **Liquidity Decay**: A progressive narrowing of `cash_buffer_days` over a 90-day window, even if the absolute balance remains positive.
- **Velocity Stress**: Sudden spikes in `debit_failure_rate_90d` across multiple payment channels simultaneously.

### 5.2 Progressive Income Underreporting
By cross-referencing **Internal Cash Velocity** (UPI/Bank) against the **External Twin Archetype**, the engine identifies discrepancies:
- If a user's transaction throughput is $3 \times$ higher than their reported income or peer cohort average, it flags **Underreporting Risk**, affecting the "Trust Score" in Tier 7.

### 5.3 Identity & Behaviour Shifts
Detects sudden, statistically improbable shifts in the user's "Digital DNA":
- **Category Drift**: A jump in the `merchant_category_shift_count` (e.g., sudden high-value spend in categories outside their Peer Cohort's norm).
- **Inflation of Discretionary Ratio**: Identifying "Lifestyle Creep" that signals a baseline shift in business sustainability.

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
