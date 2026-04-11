# Agentic‑AI Financial Digital Twin & Cognitive Credit Engine
Related Tiers: Tier 7 (Cognitive Credit Engine)

This document captures the regulatory, structural, and operational knowledge underlying **MSME and consumer credit** in India, contextualised for an **Agentic‑AI Real‑Time Financial Behavioural Digital Twin and Cognitive Credit Engine** (F‑2 style). It reconciles authoritative sources: the **Ministry of MSME “Know Your Lender 2025” handbook**, the **Reserve Bank of India’s MSME credit‑policy framework**, and key **research‑papers on digital‑financial‑twins, synthetic‑data, and agentic‑AI‑risk‑simulation**. [web:46][web:55][web:58][web:61]  
All **behaviour‑based bands, limit‑recommendations, and eligibility‑rules** in your pipeline are derived from these official‑policy documents and research baselines. [web:46][web:55]

---

## 1. MSME classification & digital‑twin framing

### 1.1 MSME category (MSMED Act 2006, amended 2020)

Per the **MSMED Act 2006 (amended July 2020)**, MSMEs are classified using **both investment in plant & machinery and turnover**. [web:46]  
In your digital‑twin pipeline, each MSME profile is assigned a **`msme_category`** field based on its synthetic‑generated `turnover_proxy` and `asset_investment_proxy`.

| Category | Investment ceiling | Turnover ceiling |
| --- | --- | --- |
| Micro | ≤ ₹1 crore | ≤ ₹5 crore |
| Small | ≤ ₹10 crore | ≤ ₹50 crore |
| Medium | ≤ ₹50 crore | ≤ ₹250 crore |  
**Source:** MSME classification, Ministry of MSME/Know Your Lender 2025‑style handbook. [web:46]  

### 1.2 Udyam registration & PSL‑membership

- **Udyam Registration Portal** is the official MSME‑registration platform; the **Udyam Registration Certificate (URC)** is mandatory for PSB loans, CGTMSE eligibility, and **Priority Sector Lending (PSL) targeting**. [web:46]  
- **Udyam‑Assist‑certificates** for informal micro‑enterprises are treated at par with URC for PSL‑classification. [web:46]  
- In your twin‑layer, **`msme_registration`** (e.g., `Udyam`, `Informal‑equivalent`, `None`) is a **static‑profile** field derived from synthetic‑registration‑status in the generator.

---

## 2. Lender types, PSL, and digital‑twin‑aware roles

### 2.1 Lender‑type semantics (MSME‑credit‑policy style)

In your credit‑engine, `lender_type` determines: risk‑appetite, PSL‑alignment, and product‑pipeline eligibility. [web:46][web:63]  

| Lender type | Full name | Primary MSME‑product |
| --- | --- | --- |
| SCB | Scheduled Commercial Bank | Term‑loan, working‑capital, composite‑loan |
| NBFC | Non‑Banking Financial Company | Unsecured business‑loan, supply‑chain‑finance |
| MFI | Microfinance Institution | Group‑lending to micro‑enterprises (JLG‑model) |
| Fintech‑NBFC | Digital‑first NBFC | PSB‑“59‑minute‑loan”‑style, GST‑API‑underwriting |
| DFI | Development Finance Institution | Refinance‑lines to banks (e.g., SIDBI) |  
**Source:** MSME‑credit‑policy / RBI‑style policy‑documents. [web:46][web:63]  

### 2.2 PSL‑targets & digital‑twin‑driven incentives

Banks must allocate a mandated share of **Adjusted Net Bank Credit (ANBC)** to **Priority Sectors**, including MSME. [web:46]  

| Bank type | PSL target of ANBC | Micro sub‑target |
| --- | --- | --- |
| Domestic SCB | 40% | 7.5% |
| Foreign banks | 40% | N.A. |
| RRBs | 75% | 7.5% |
| SFBs | 60% | 7.5% |
| UCBs | 60% | 7.5% |  

Shortfall in PSL‑compliance is deposited in **NABARD / RIDF‑style funds at below‑market‑rates**, creating a direct incentive to lend to MSMEs and micro‑enterprises. [web:46]  

In your **Cognitive‑Credit Engine (Tier‑7)**:  
- A **PSL‑score** component is inferred from: `msme_category`, `investment_proxy`, `turnover_proxy`, and `digital‑presence` (UPI‑ratio, GST‑filing regularity).  
- The engine modulates **limit‑eligibility** and **risk‑adjustment** based on the simulated‑lender‑type’s PSL‑incentives. [web:46][web:55]

---

## 3. Loan‑type semantics for digital‑twin behaviour‑modelling

Each MSME‑loan‑type maps to **distinct behaviour‑patterns** observable in bank‑transactions, UPI, EMI, and open‑banking‑feeds. [web:46][web:55]  

### 3.1 Term‑loan (capital‑expenditure‑behaviour)

- Used for **capital‑expenditure**: machinery, infrastructure, etc.; repaid in fixed‑schedule. [web:46]  
- RBI‑policy‑style tenures: **7–10 years** generally, **up to 15 years** for specific‑projects with initial moratorium. [web:46]  
- In your twin‑layer:  
  - **Large‑inflows** at loan‑disbursement, then **fixed‑EMI‑outflows** (corresponding to `EMI‑schedule`‑feed)  
  - **`twin.form.factor`** = `term‑loan‑driven‑capital‑expenditure` (Tier‑4‑state). [web:55]

### 3.2 Working‑capital‑loan (operational‑cash‑flow)

- Covers **operational‑expenses**: raw‑material, wages, receivables‑gap; assessed annually. [web:46]  
- Sub‑types:  
  - **CC (Cash‑Credit)**: revolving‑facility against stock & receivables.  
  - **OD (Overdraft)**: against current‑account balance.  
- In your twin‑layer:  
  - **Revolving‑payouts / drawdowns** and **stock‑cycle‑peaks** (via UPI‑/bank‑flows) calibrate **working‑capital‑stress‑signatures**. [web:55]

### 3.3 Composite‑loan (single‑window‑behaviour)

- Single‑window product combining **working‑capital** and **term‑loan** up to **₹1 crore**. [web:46]  
- **CGTMSE** covers composite‑loans; this is captured as:  
  - `cgtmse_eligible = true` if `msme_category ∈ (Micro, Small)` and loan‑type = `composite`. [web:46]  
  - Twin‑state: `credit_dependency_score` reacts to **composite‑loan‑structure** vs pure‑WC or pure‑term‑profiles. [web:55]

---

## 4. Working‑capital‑assessment logic for twin‑state‑signals

Your twin‑state‑engine (Tier‑4) implicitly mirrors **real‑world WC‑assessment methodologies** via behaviour‑signals. [web:55][web:61]  

### 4.1 Turnover‑method (Nayak‑style)

- For WC‑limits up to **₹5 crore**, RBI‑mandated **Nayak‑committee‑formula** applies:  
  - At least **20% of projected‑turnover** as bank‑finance. [web:46]  
- For **digital‑turnover ≥25%** of total‑turnover:  
  - **25%** for non‑digital‑portion, **30%** for digital‑portion. [web:46]  

In your pipeline:  
- `upi_p2m_ratio_30d` and `digital_payment_ratio` act as **proxy‑for‑digital‑turnover**; when above **25%**, the engine simulates **higher‑WC‑ceiling‑eligibility**. [web:55]

### 4.2 MPBF & Cash‑budget‑method (higher‑limits)

- For WC‑above **₹5 crore** or units with long‑cycle, **MPBF = 75% × (current‑assets − current‑liabilities excluding bank‑borrowings)**; borrower‑contributes min‑**25% NWC**. [web:46]  
- **Cash‑budget‑method** for contractors / seasonal‑businesses uses **peak‑cash‑deficit** as WC‑finance. [web:46]  

In your **Predictive‑Risk‑Simulation‑Engine (Tier‑6)**:  
- Synthetic‑`current_ratio`‑ and `cash_buffer_days`‑features are used to simulate **MPBF‑style** and **cash‑budget‑style** stress‑tests. [web:58][web:61]

---

## 5. Credit‑guarantee‑schemes as twin‑state‑signals

These schemes map directly to **eligibility‑flags** and **collateral‑behaviour** in your twin‑engine.

### 5.1 CGTMSE

- **Administered by:** SIDBI + Ministry of MSME. [web:46]  
- **Eligible borrowers:** Micro and small enterprises only. [web:46]  
- **Coverage per borrower:** up to **₹10 crore** (revised from earlier ₹500 lakh). [web:46]  
- **Coverage ratio:** 75%‑of‑principal (85% for micro, women, NE, SC/ST). [web:46]  
- **No‑collateral** for CGTMSE‑guaranteed‑loans; **RBI‑directive** for loans up to ₹10L. [web:46]  

In your **Cognitive‑Credit‑Engine (Tier‑7)**:  
- `cgtmse_eligible` is a **boolean** derived from `msme_category`, `loan_type`, and absence‑of‑fraud‑flags. [web:55]  
- Digital‑twin‑state: `credit_dependency_score` lowers when `cgtmse_eligible = true`, reflecting guaranteed‑risk‑transfer. [web:58]

### 5.2 Other‑guarantee‑schemes (CGFMU, CGSS‑startups, MCgSMSE)

- **CGFMU** (for MUDRA loans under PMMY). [web:46]  
- **CGSS‑startups** (DPIIT‑recognized, 85%‑coverage‑up‑to‑₹10Cr). [web:46]  
- **MCgSMSE** (for machinery‑purchase‑term‑loans, 60%‑coverage‑up‑to‑₹100Cr). [web:46]  

In your pipeline:  
- Each scheme is mapped to a **scheme‑eligibility** flag in `twin.eligibility` based on `msme_category`, `loan_type`, and `digital‑presence`. [web:55]

---

## 6. Government‑schemes as behavioural‑pattern‑templates

### 6.1 PMMY / MUDRA (micro‑enterprise‑behaviour)

- Loans up to **₹20L** to income‑generating micro‑enterprises; tiers: Shishu (≤₹50k), Kishor (₹50k–₹5L), Tarun (₹5L–₹10L), Tarun‑plus (₹10L–₹20L). [web:46]  
- **CGFMU‑guarantee**, **no‑collateral‑for‑≤₹10L**, **no‑margin‑for‑Shishu**, **15%‑margin‑for‑Kishor+**. [web:46]  

In your twin‑state‑engine:  
- High‑risk‑micro‑profiles (`high_risk`, `micro`) with strong‑EMI‑on‑time‑history are flagged as **“MUDRA‑Shishu/Kishor‑eligible”** via `twin.scheme_flags`. [web:55]

### 6.2 PMEGP, Stand‑Up‑India, PM‑Vishwakarma, MSE‑GIFT, MSE‑SPICTE

- **PMEGP:** Manufacturing‑up‑to‑₹50L, services‑up‑to‑₹20L, with **15–35%‑subsidy**; no‑collateral‑for‑≤₹10L. [web:46]  
- **Stand‑Up‑India:** SC/ST‑and‑women‑entrepreneurs; **composite‑loan‑₹10L–₹1Cr**; 84‑month‑tenure. [web:46]  
- **PM‑Vishwakarma:** Traditional‑artisans; **collateral‑free‑up‑to‑₹3L**, two‑tranches, **re‑₹1‑per‑digital‑transaction** incentive. [web:46]  
- **MSE‑GIFT:** 2%‑interest‑subvention‑for‑green‑tech‑term‑loans‑up‑to‑₹2Cr, under‑CGTMSE‑guarantee. [web:46]  
- **MSE‑SPICTE:** 25%‑capital‑subsidy‑for‑circular‑economy‑projects; focus‑on‑plastic/rubber/e‑waste. [web:46]  

In your **LLM‑Reasoning‑Layer (Tier‑5)**:  
- When `twin.msme_category == micro` and `sector == craft/artisan`, the agent can generate a **“PM‑Vishwakarma‑eligible”** nugget; similarly for **MSE‑GIFT/MSE‑SPICTE** when `sector = green‑tech`. [web:55]

---

## 7. Credit‑information‑bureaus, score‑bands, and digital‑twin‑calibration

### 7.1 CIC‑framework (India‑licensed‑bureaus)

- Major CICs: **CIBIL (TransUnion)**, **Experian**, **Equifax**, **CRIF‑Highmark**. [web:46]  
- Score‑ranges vary, but commonly **300–900**‑style bands. [web:46]  

### 7.2 CIBIL‑style‑bands & mapping to your engine

| Band name | Score range | Lending implication |
| --- | --- | --- |
| Excellent | 750–900 | Prime‑borrower, lowest‑rates, full‑products |
| Good | 650–750 | Near‑prime, standard‑terms |
| Average | 550–650 | Sub‑prime, restricted‑products |
| Poor | 300–550 | High‑risk, Mudra‑micro‑only |  
**Source:** CIBIL‑band‑semantics, KYL‑handbook‑style documents. [web:46]  

In your **XGBoost‑→‑LLM‑pipeline**:  
- Your synthetic‑engine emits a **`credit_score`** in **300–900**, calibrated to **CIBIL‑band‑semantics** as per earlier‑format. [web:55]  

```markdown
our risk band         score range    CIBIL equivalent    lending pathway
very_low_risk          750–900      excellent           full‑MSME‑credit, CGTMSE‑Tier‑1
low_risk               650–749      good                standard‑MSME‑lending
medium_risk            550–649      average             CGTMSE‑collateral‑free‑products
high_risk              300–549      poor                Mudra‑Shishu/Kishor‑only
```

---

## 8. Bank‑credit‑rating‑models & digital‑twin‑segmentation

RBI‑style‑models segment by **turnover** and map directly to **digital‑twin‑risk‑segments**. [web:46]  

| Model | Turnover‑range | Limit‑ceiling |
| --- | --- | --- |
| SARAL | ≤ ₹10L | ₹10L |
| SCBL | ₹10L–₹1Cr | ₹1Cr |
| SBS | ₹1Cr–₹5Cr | varies |
| SME | ₹5Cr–₹50Cr | varies |
| MS | ₹50Cr–₹250Cr | varies |
| HLC | ≥ ₹250Cr | varies |  

In your pipeline:  
- `model_segment` is inferred from synthetic‑`turnover_proxy`; this informs **simulation‑boundaries** in the **Predictive‑Risk‑Simulation‑Engine (Tier‑6)**. [web:58]

Financial‑ratios checked by banks (e.g., **debt‑equity‑ratio**, **current‑ratio**, **DSCR**) mirror your **digital‑twin‑financial‑health‑indicators** (`de_ratio`, `current_ratio`, `dscr_proxy`). [web:46]

---

## 9. Digital‑lending‑framework & our agentic‑twin‑compliance

### 9.1 RBI‑Digital‑Lending‑Guidelines‑2025‑style

- Regulated‑entities must collect **economic‑profile** (age, occupation, income) before‑loan. [web:46]  
- **Key‑Fact‑Statement (KFS)** mandatory for all digital‑loans; digitally‑signed‑docs sent to borrower‑via‑SMS/email. [web:46]  
- **Cooling‑off‑period** ≥ 1 day

---

## 10. Temporal-cycle-detection in financial-transaction-graphs

The FinTwin engine utilizes temporal causality to distinguish between legitimate business flows and fraudulent circular trading.

- **RBI-collateral-free-loan-update (Feb 2026 – ₹20 lakh for MSEs):**  
  As per RBI's *Lending to MSME Sector (Amendment) Directions, 2026*:  
  - Official Reference: [RBI Master Directions – Lending to MSME Sector (latest amendments)](https://www.rbi.org.in)  
  - Summary: [RBI enhances collateral-free lending for MSEs (Drishti IAS)](https://www.drishtiias.com/daily-updates/daily-news-analysis/rbi-enhances-collateral-free-lending-for-mses)  

- **Peer-reviewed-papers on temporal-cycle-detection using temporal-causality:**  
  - **Real-time dynamic graph learning with temporal attention for financial transaction risk control:**  
    Models streaming transaction graphs with temporal-encoding and continuous-time-attention transformers (C2GAT) to capture causal-temporal patterns and periodic cycles.  
    [Frontiers in AI (2026)](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2026.1774013/full)  
  - **Enhancing Credit Card Fraud Detection via Causal Temporal Graph Neural Network (CaT-GNN):**  
    Introduces CaT-GNN that uses temporal-causal-attention over transaction graphs to identify causal-transaction-paths and temporal-cycles.  
    [arXiv:2402.14708v1](https://arxiv.org/html/2402.14708v1)  
  - **Detecting illicit transactions in Bitcoin: a wavelet-temporal graph approach:**  
    Combines temporal-cyclical-behavior with wavelet-based spectral-methods to detect money-laundering-style financial-cycles.  
    [Scientific Reports (Nature, 2026)](https://www.nature.com/articles/s41598-025-23901-3)