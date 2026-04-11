# How the Data is Made — F‑2 Agentic‑AI Digital‑Twin

**Rationale**: Real row‑level financial data (bank transactions, UPI payments, SMS alerts, EMI schedules, open‑banking feeds) are highly sensitive under Indian data‑privacy regulations (DPDPA, RBI, PMLA). This protocol defines a **mathematically‑sound synthetic‑generation pipeline** to produce cryptographically‑valid, statistically‑fidelity‑preserving datasets used to train the **Agentic‑AI Financial Digital Twin and Cognitive‑Credit Engine**.

---

## 1. Schema references & compliance

The synthetic generator strictly enforces compliance with Indian government and financial‑infrastructure specifications for the 5 source domains:

| Domain | Authority / source | Application / enforcement |
| --- | --- | --- |
| Bank accounts & balances | RBI‑aligned bank‑schema patterns (e.g., IFSC, account‑number lengths, currency‑compliance). | Validates account‑type (CASA, term‑deposit, credit‑card‑linked), balance‑signs, currency‑ISO‑standard. |
| UPI logs | NPCI‑UPI standards (IMPS‑level semantics, UPI‑ID format). [web:54][web:57] | Validates UPI‑ID pattern (`<user>@<bank>`), valid P2P/P2M flags, realistic failure‑status enumerations. |
| SMS alerts | GSM‑based SMS‑gateway + bank‑transactional‑SMS format. [web:47][web:51] | Enforces standardized SMS‑templates (e.g., “Debited INR X on YYYY‑MM‑DD at VPA XXX”), balanced debit/credit‑ratio, no fabricated‑bank‑names. |
| EMI schedules | NBFC‑/bank‑lending‑API schema (e.g., principal, interest, tenure, status). [web:50][web:63] | Enforces valid EMI‑start‑date, EMI‑end‑date, `EMI‑paid` vs `EMI‑overdue`, realistic interest‑rates (e.g., 8–24% p.a.). |
| Open‑banking feeds | RBI‑aligned Account‑Aggregator / open‑banking APIs (Sahamati‑compliant). [web:46][web:56][web:62] | Generates AA‑style JSON‑schemas: `financial‑account` objects with `balance`, `transaction‑list`, `permissions`, `consent‑handle`. |

---

## 2. Profile‑variance strategy

To prevent model‑overfitting and train the agentic‑risk‑simulator effectively, the dataset uses **5 distinct MSME / consumer personas**, weighted as follows:

| Profile type | Weight | Behavioral characteristics |
| --- | --- | --- |
| **genuine_healthy** | 40% | High‑on‑time‑payment‑rate, stable UPI‑volume, moderate SMS‑alert‑frequency, EMI‑mostly‑on‑time. Balanced open‑banking‑balance‑flows. |
| **genuine_struggling** | 25% | Low transaction‑velocity, high‑EMI‑overdues, frequent SMS‑“low‑balance” alerts, volatile UPI‑cash‑flow. |
| **shell_circular** | 15% | Fraud‑target. Rotates funds in directed rings (3–4 entities) via UPI‑P2P. No P2M‑style spends; burst‑mode time‑clusters and synthetic‑identity‑like data‑patterns. |
| **paper_trader** | 10% | Fraud‑target. Extreme‑volume test‑transactions (UPI‑void‑payments, failed‑auth‑spikes) that look like “fake‑movement” but stay within protocol‑bounds. |
| **new_to_credit** | 10% | Vintage < 6 months. EMI‑schedule starts near end‑of‑history; high temporal‑sparsity in both UPI and bank‑transactions. |

---

## 3. Mathematical variable constraints

All synthetic variables are governed by **probability‑density‑functions** and hard constraints, not uniform randoms.

### 3.1 Continuous variables (amounts, balances, EMI‑values)

- **Amounts & balances**  
  - Lognormal distributions via `numpy.random.lognormal(mean, sigma)` for all monetary fields.  
  - Genuine‑healthy: `μ=10.8, σ=0.8` → realistic‑retail‑heavy‑tail skews.  
  - Shell‑circular (fraud‑rings): `μ=11.5, σ=0.5` → big‑transfers standing out organically.

- **EMI‑values**  
  - EMI‑amounts follow a lognormal‑shifted distribution with cap at 50% of monthly‑income‑proxy (to avoid extreme‑EMI‑fraud signals).  
  - Overdue‑penalty‑interests generated via fixed‑% above base‑rate, with 5–20% probability per overdue‑EMI.

### 3.2 Temporal variables (timestamps, EMI‑dates, SMS‑latency)

- **Inter‑arrival times**  
  - For UPI‑transactions and bank‑transfers: **Poisson‑like inter‑arrival** via exponential distribution, ensuring realistic‑spikiness in normal‑commerce.  
  - For shell‑circular rings: **burst‑mode clustering** using Gaussian‑burst‑clustering over 2–3 day‑windows.

- **EMI‑schedule dates**  
  - EMI‑start‑date drawn from uniform‑range (policy‑dependent): e.g., 1–28 of month, with 5‑day‑buffer from first‑drawdown‑date.  
  - Historic‑overdue‑EMIs’ timestamps generated via negative‑binomial‑style delays (1–30‑day‑overdues dominating).

- **SMS‑delay**  
  - SMS‑arrival‑timestamp delayed vs transaction‑timestamp by 0–120s, sampled from exponential‑decay with median‑30s.

### 3.3 Categorical / graph‑based definitions (UPI‑flows, AA‑feeds)

- **Graph‑edge‑routing weights**  
  - Genuine‑healthy: 70% random‑pool edges, 30% edges to “unregistered‑person”‑like nodes (URP‑pattern).  
  - Shell‑circular: 70% hard‑routed edges within a fixed‑ring‑ID cyclic‑multigraph (3–4 nodes always re‑appearing).  
  - New‑to‑credit: 90% edges to “known‑merchant‑clusters”, 10% to URP‑nodes.

---

## 4. Architectural decisions

### 4.1 Technology choices

| Layer / use‑case | Chosen tech | Rejected alternative | Rationale |
| --- | --- | --- | --- |
| **Core synthetic‑generator** | Python + `numpy` + `polars` / `pandas`‑style batching | LLM‑based synthetic generation (e.g., GPT‑4) | Deterministic‑cycle‑creation, relational‑FK‑enforcement, and 100k+‑row‑scale consistency are not feasible with LLM‑generation. [web:55][web:58] |
| **Statistical‑fidelity‑preservation** | `SDV.GaussianCopulaSynthesizer` for cross‑field‑correlations | Random‑field‑fills | Copula‑modeled correlations (e.g., high‑`income_proxy` ↔ lower‑EMI‑overdue‑rate, higher‑UPI‑activity) produce realistic‑business‑behaviour. [web:55][web:61] |
| **Data‑storage / export** | **Parquet** for all source‑domain files | CSV or raw‑SQL‑inserts | Parquet preserves exact numeric‑types (e.g., 15‑digit UPI‑references, high‑precision‑floats) and enables fast‑column‑wise‑ingestion in `polars`. [web:61] |

### 4.2 Pipeline structure

- **Step 1 – Profile‑generator**  
  Generate 250 base‑profiles via `SDV.GaussianCopulaSynthesizer` for fields: `bank_account_age_months`, `monthly_income_proxy`, `UPI_volume_per_month`, `average_EMI_overdue_days`, `SMS_alert_frequency`.  
- **Step 2 – Time‑series‑generator**  
  For each profile, generate 6–24 months of:  
  - bank‑transaction‑streams,  
  - UPI‑PAY‑/REFUND‑/VOID‑events,  
  - SMS‑alert‑events with timestamps,  
  - EMI‑payments / overdues,  
  - open‑banking‑AA‑style JSON‑blobs per day.  
- **Step 3 – Agentic‑data‑sink**  
  Dump all streams into **Redis‑Streams** or **Kafka‑lite**‑style topics to simulate your real‑time‑ingestion‑layer, keeping the “empty‑pipeline‑with‑synthetic‑heartbeat” pattern from your old credit‑scoring‑PS. [web:55][web:61]

---

## 5. Target variables & real‑world transition strategy

### 5.1 Non‑Linear Policy‑Distillation Model (Tier‑7‑aligned)

- Encoded **standard RBI‑aligned lending‑policies** (e.g., debt‑income‑ratios, EMI‑overdue‑count‑caps, UPI‑volatility‑thresholds) as a noisy‑synthetic‑target.  
- Used **XGBoost** as a **non‑linear‑policy‑distillation‑engine** to map the 46‑feature‑style‑inputs to a smooth risk‑probability surface, then chained:  
  `XGBoost → SHAP → LLM‑CoT‑narrative` for the Cognitive‑Credit‑Engine. [web:55][web:58]

### 5.2 Real‑world NBFC‑data‑constraints

- True row‑level financial‑histories (UPI‑handles, GSTINs, EMI‑defaults, SMS‑content) are **legally blocked** in development under:  
  - **DPDPA‑style privacy laws**,  
  - **NBFC‑/bank‑NDAs**. [web:46][web:50]  
- Synthetic‑pipeline thus functions as a **scalable “empty‑pipeline‑with‑synthetic‑heartbeat”** that can be upgraded to production by:  
  - Removing the `generate_proxy_labels` function.  
  - Reconnecting secure NBFC‑environments (AWS‑S3 / Kafka‑Streams) to the `polars`‑ingestion‑engine. [web:58][web:63]

---

## 6. Links to official data‑specifications

- **Account‑Aggregator / open‑banking (India)**  
  - Sahamati (AA‑network): https://sahamati.org.in  
  - AA‑gateway‑API guide (Setu): https://setu.co/data/financial-data-apis/account-aggregator/  
  - Open‑banking‑API guide (India‑context): https://www.cashfree.com/blog/open-banking-api/ [web:56][web:62][web:63]  

- **UPI‑compliance / standards**  
  - UPI‑ecosystem (NPCI‑RBI‑aligned): https://en.wikipedia.org/wiki/Unified_Payments_Interface  
  - UPI‑API‑guide (Razorpay): https://razorpay.com/blog/upi-payment-api-guide [web:54][web:57]  

- **India‑data‑regulations & compliance**  
  - Data‑regulations in financial‑sector (DPDPA, RBI‑directions, etc.): https://securiti.ai/data-regulations-in-india-financial-sector/ [web:46]  

- **Synthetic‑financial‑data‑best‑practices**  
  - Realistic‑synthetic‑financial‑transactions‑paper: https://arxiv.org/pdf/2306.16424.pdf [web:55]  
  - Synthetic‑transaction‑monitoring‑dataset‑paper: https://eprints.bournemouth.ac.uk/40982/1/Full_IEEE_Dataset_Conference_Paper%20(4).pdf [web:61]  
  - Generative‑AI‑based‑synthetic‑banking‑transactions: https://wjarr.com/sites/default/files/fulltext_pdf/WJARR-2025-0828.pdf [web:58]