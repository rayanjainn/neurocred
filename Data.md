# howisthedatamade_f2.md — Agentic‑AI Financial Digital Twin & Cognitive Credit Engine

**Table of contents**

1. [Schema references & compliance](#1-schema-references--compliance)  
2. [Profile variance strategy](#2-profile-variance-strategy)  
3. [Mathematical variable constraints](#3-mathematical-variable-constraints)  
4. [Architectural decisions](#4-architectural-decisions)  
5. [Target variables & real‑world transition strategy](#5-target-variables--real-world-transition-strategy)  
6. [Where to get the real‑data (licensed sources)](#6-where-to-get-the-real-data-licensed-sources)  
7. [Mock API‑JSON schemas per data‑type](#7-mock-api-json-schemas-per-data-type)  

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

## 2. Profile variance strategy

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

## 6. Where to get the real‑data (licensed sources)

If you obtain the required licenses and consent‑frameworks (AA‑registration, NBFC‑RBI‑compliance, DPDP‑compliance), the **real‑data‑sources** would be:

| Domain / data type | What it provides | Official / licensed source |
| --- | --- | --- |
| Account‑Aggregator / open‑banking (India) | Consent‑based access to bank‑account balances and transaction‑lists. | Sahamati AA‑network: https://sahamati.org.in |
| | Developer‑gateway and example‑APIs for AA‑data‑pulls. | Setu AA‑gateway: https://setu.co/data/financial-data-apis/account-aggregator/ |
| | Open‑banking‑style API‑guides (India‑context). | Cashfree‑open‑banking‑API‑guide: https://www.cashfree.com/blog/open-banking-api/ |
| UPI‑logs | Real‑UPI‑transaction‑level data via PSPs or banks. | NPCI‑UPI‑ecosystem overview: https://en.wikipedia.org/wiki/Unified_Payments_Interface |
| | UPI‑API‑guide and example‑payloads (PSP‑style). | Razorpay‑UPI‑API‑guide: https://razorpay.com/blog/upi-payment-api-guide |
| SMS‑alert‑data | Transactional‑SMS‑logs via SMS‑gateways integrated with banks. | SMS‑alert‑enterprise‑gateway: https://www.smsalert.co.in |
| | Paper‑on‑SMS‑based‑financial‑SMS‑design (schema‑inspiration). | IRaj‑SMS‑paper: http://www.iraj.in/journal/journal_file/journal_pdf/12-514-154865223114-19.pdf |
| EMI‑schedules | EMI‑schedules and payment‑records via NBFC / bank‑lending‑APIs. | India‑fintech‑licensing‑&‑data‑sharing‑rails: https://www.enkash.com/resources/blog/essential-business-licenses-for-fintech-in-india |
| Synthetic‑financial‑data‑research | Papers on realistic‑synthetic‑transactions and datasets. | Realistic‑synthetic‑financial‑transactions‑paper: https://arxiv.org/pdf/2306.16424.pdf |
| | Synthetic‑transaction‑monitoring‑dataset‑paper. | IEEE‑synthetic‑dataset‑paper: https://eprints.bournemouth.ac.uk/40982/1/Full_IEEE_Dataset_Conference_Paper%20(4).pdf |
| | Generative‑AI‑based‑synthetic‑banking‑transactions. | Generative‑AI‑banking‑paper: https://wjarr.com/sites/default/files/fulltext_pdf/WJARR-2025-0828.pdf |

## 7. Mock API‑JSON schemas per data‑type

Assuming you integrate with each source‑via‑API, the **raw‑ingestion‑layer** in your PS would consume schemas like the following.

### 7.1 Bank‑transactions (AA‑style `financial-account` feed)

Example: `/api/aa/v1/financial-accounts/{id}` (Sahamati‑AA‑style). [web:56][web:62]

```json
{
  "account": {
    "id": "ac12345678",
    "accountNumber": "XXXXXXXXXXXX1234",
    "ifsc": "SBIN0002499",
    "type": "SAVINGS",
    "currency": "INR",
    "balance": 123456.78,
    "lastUpdated": "2026-04-11T11:00:00Z"
  },
  "transactions": [
    {
      "id": "txn12345678",
      "amount": 5000.00,
      "currency": "INR",
      "type": "CREDIT",
      "timestamp": "2026-04-10T10:30:15Z",
      "description": "Salary from EMPLOYER-NAME",
      "merchant": "EMPLOYER-NAME",
      "category": "INCOME",
      "status": "SETTLED"
    },
    {
      "id": "txn12345679",
      "amount": 299.00,
      "currency": "INR",
      "type": "DEBIT",
      "timestamp": "2026-04-10T12:15:30Z",
      "description": "UPI Payment to Favourite-Store",
      "merchant": "Favourite-Store",
      "category": "ESSENTIAL",
      "status": "SETTLED"
    }
  ],
  "from": "2026-04-01T00:00:00Z",
  "to": "2026-04-10T23:59:59Z"
}
```

### 7.2 UPI‑logs (PSP‑style transaction‑API response)

Example: `/api/v1/transactions` (UPI‑PSP‑style). [web:54][web:57]

```json
{
  "transactions": [
    {
      "id": "upi12345678",
      "transactionId": "NT20260410123456789",
      "amount": 1999.00,
      "currency": "INR",
      "date": "2026-04-10",
      "vpa": "user@bank",
      "counterpartyVpa": "merchant@bank",
      "mode": "P2P",
      "reason": "Payment for goods",
      "status": "SUCCESS",
      "failureReason": null,
      "timestamp": "2026-04-10T16:45:23Z",
      "merchant": "Online-Shop",
      "category": "DISCRETIONARY"
    },
    {
      "id": "upi12345679",
      "transactionId": "NT20260410123456790",
      "amount": 20000.00,
      "currency": "INR",
      "date": "2026-04-10",
      "vpa": "user@bank",
      "counterpartyVpa": "friend@bank",
      "mode": "P2P",
      "reason": "Lending to friend",
      "status": "FAILED",
      "failureReason": "FUNDS_UNAVAILABLE",
      "timestamp": "2026-04-10T18:12:45Z",
      "merchant": null,
      "category": "CASH_TRANSFER"
    }
  ],
  "from": "2026-04-01",
  "to": "2026-04-10",
  "page": 1,
  "limit": 100
}
```

### 7.3 SMS‑alerts (SMS‑gateway‑style `inbound`‑logs)

Example: `/api/sms/v1/inbound` (SMS‑gateway‑style API). [web:51]

```json
{
  "messageList": [
    {
      "id": "sms12345678",
      "from": "GMBANK",
      "to": "+919876543210",
      "text": "INR 2,999 debited on 10‑Apr‑2026 at VPA user@bank for Favourite‑Store.",
      "type": "Transactional",
      "category": "DEBIT_ALERT",
      "timestamp": "2026-04-10T12:16:00Z",
      "metadata": {
        "transactionId": "NT20260410123456789",
        "amount": 2999.00,
        "currency": "INR",
        "vpa": "user@bank",
        "merchant": "Favourite-Store"
      }
    },
    {
      "id": "sms12345679",
      "from": "GMBANK",
      "to": "+919876543210",
      "text": "INR 5,000 credited to your account on 10‑Apr‑2026 from EMPLOYER‑NAME.",
      "type": "Transactional",
      "category": "CREDIT_ALERT",
      "timestamp": "2026-04-10T10:31:00Z",
      "metadata": {
        "transactionId": "txn12345678",
        "amount": 5000.00,
        "currency": "INR",
        "fromAccount": "EMPLOYER-NAME",
        "toAccount": "user@bank"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 100,
    "total": 2
  }
}
```

### 7.4 EMI‑schedules (lending‑platform‑style loan‑detail API)

Example: `/api/lending/v1/loans/{loanId}` (NBFC‑/bank‑lending‑API‑style). [web:50][web:63]

```json
{
  "loan": {
    "id": "loan12345678",
    "borrowerId": "usr12345678",
    "productName": "Personal Loan",
    "principal": 500000.00,
    "interestRate": 12.0,
    "tenureMonths": 24,
    "loanType": "TERM_LOAN",
    "startAt": "2026-04-01T00:00:00Z",
    "status": "ACTIVE"
  },
  "emis": [
    {
      "id": "emi12345678",
      "loanId": "loan12345678",
      "number": 1,
      "dueDate": "2026-05-01",
      "principal": 19200.00,
      "interest": 5000.00,
      "installmentAmount": 24200.00,
      "paid": false,
      "overdueDays": 0,
      "status": "SCHEDULED"
    },
    {
      "id": "emi12345679",
      "loanId": "loan12345678",
      "number": 2,
      "dueDate": "2026-06-01",
      "principal": 19300.00,
      "interest": 4900.00,
      "installmentAmount": 24200.00,
      "paid": false,
      "overdueDays": 0,
      "status": "SCHEDULED"
    }
  ],
  "from": "2026-04-01T00:00:00Z",
  "to": "2026-05-31T23:59:59Z"
}
```

### 7.5 EMI‑payment‑events (payment‑gateway‑style webhook)

Example: `/api/webhook/v1/emi-payments` (payment‑gateway‑style EMI‑collection). [web:50][web:63]

```json
{
  "payments": [
    {
      "id": "pmt12345678",
      "loanId": "loan12345678",
      "installmentId": "emi12345679",
      "amount": 24200.00,
      "currency": "INR",
      "paymentMethod": "UPI",
      "vpa": "user@bank",
      "timestamp": "2026-06-01T14:22:10Z",
      "status": "SUCCESS",
      "failureReason": null,
      "reference": "UPI‑NT2026060123456790",
      "metadata": {
        "mode": "P2M",
        "merchant": "Lending‑Platform‑Name"
      }
    },
    {
      "id": "pmt12345679",
      "loanId": "loan12345678",
      "installmentId": "emi12345680",
      "amount": 24200.00,
      "currency": "INR",
      "paymentMethod": "BANK_TRANSFER",
      "timestamp": "2026-07-01T11:15:00Z",
      "status": "FAILED",
      "failureReason": "INSUFFICIENT_BALANCE",
      "reference": "BANK‑REF1234567890",
      "metadata": {}
    }
  ],
  "from": "2026-06-01T00:00:00Z",
  "to": "2026-07-01T23:59:59Z"
}
```

### 7.6 Open‑banking / AA‑style `financial‑account` feed (consent‑based)

Example: `/api/aa/v1/financial-accounts/{id}` (Sahamati‑AA‑style consent‑response payload). [web:56][web:62]

```json
{
  "consent": {
    "id": "cons12345678",
    "status": "ACTIVE",
    "from": "2026-04-01T00:00:00Z",
    "to": "2026-10-01T23:59:59Z",
    "fiTypes": ["BANK_ACCOUNT", "CREDIT_CARD"]
  },
  "fa": [
    {
      "id": "fa12345678",
      "maskedAccNum": "XXXX1234",
      "alias": "Savings",
      "type": "BANK_ACCOUNT",
      "fi": "SBI BLR",
      "balance": 123456.78,
      "currency": "INR",
      "balanceTime": "2026-04-11T11:00:00Z",
      "transactions": [
        {
          "id": "txn12345678",
          "amount": 5000.00,
          "type": "CREDIT",
          "isoCode": "INR",
          "valueDate": "2026-04-10",
          "narrative": "Salary from EMPLOYER-NAME",
          "merchant": "EMPLOYER-NAME",
          "category": "INCOME"
        },
        {
          "id": "txn12345679",
          "amount": 299.00,
          "type": "DEBIT",
          "isoCode": "INR",
          "valueDate": "2026-04-10",
          "narrative": "UPI Payment to Favourite-Store",
          "merchant": "Favourite-Store",
          "category": "ESSENTIAL"
        }
      ]
    }
  ],
  "from": "2026-04-01T00:00:00Z",
  "to": "2026-04-10T23:59:59Z"
}
```

---


### Source of mock JSON structures (for your doc)

- **Bank‑transactions & AA‑feed schemas**  
  Inspired by **Sahamati AA‑specification** and **account‑aggregator‑style bank‑data payloads** (e.g., Setu‑style open‑banking APIs):  
  - Sahamati AA‑network: https://sahamati.org.in  
  - Setu AA‑gateway: https://setu.co/data/financial-data-apis/account-aggregator/  
  - Cashfree‑open‑banking‑API‑guide: https://www.cashfree.com/blog/open-banking-api/  

- **UPI‑logs schema**  
  Based on **NPCI‑UPI‑ecosystem** and **Razorpay‑/PSP‑UPI‑API‑guides**, with simplified fields for consistency with your PS‑ingestion‑layer:  
  - NPCI‑UPI‑ecosystem overview: https://en.wikipedia.org/wiki/Unified_Payments_Interface  
  - Razorpay‑UPI‑API‑guide: https://razorpay.com/blog/upi-payment-api-guide  

- **SMS‑alerts schema**  
  Inspired by **SMS‑gateway‑style enterprise‑SMS‑APIs** (e.g., SMSAlert‑type providers) and GSM‑SMS‑standard‑patterns:  
  - SMS‑alert‑enterprise‑gateway: https://www.smsalert.co.in  
  - SMS‑based‑financial‑SMS‑design‑paper: http://www.iraj.in/journal/journal_file/journal_pdf/12-514-154865223114-19.pdf  

- **EMI‑schedules & EMI‑payments schemas**  
  Adapted from **NBFC‑lending‑platform‑APIs** (e.g., Cashfree‑style lending‑products and open‑banking‑API‑guides) and generic‑loan‑management‑API conventions:  
  - India‑fintech‑licensing‑&‑data‑sharing‑rails: https://www.enkash.com/resources/blog/essential-business-licenses-for-fintech-in-india  

These are **mock structures**, not raw‑copy‑paste‑from‑proprietary‑APIs; they preserve **semantics** (e.g., UPI‑ID format, AA‑consent‑fields, EMI‑installment‑breakdown) while staying generic so you can plug them into your **Kafka‑/Redis‑based‑ingestion** pipeline.  
