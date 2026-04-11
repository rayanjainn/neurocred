# schema.md — Personal Finance Multi-Source Ingestion & Feature Engineering

**Description**: Explicit JSON schema layouts and Redis stream field constraints fed directly into the Polars feature engine. Payloads must strictly adhere to these definitions.

## Table of Contents

1. bank transactions stream  
2. upi transactions stream  
3. sms transaction alerts stream  
4. recurring emi & subscription schedules stream  
5. open-banking feeds stream  
6. voice-call transcripts stream  
7. engineered ml features (polars output)

## 1. Bank Transactions Stream (stream:bank_transactions)
Derived from bank statements or Account Aggregator (AA) framework.

| Field                | Type      | Constraint & Purpose |
|----------------------|-----------|----------------------|
| event_id            | UUID     | Unique idempotent identifier |
| user_id             | string   | Anonymized user key |
| timestamp           | ISO 8601 | Transaction execution time (temporal anchor for windows) |
| amount              | float    | Signed INR amount |
| merchant_name       | string   | Parsed merchant/payee |
| merchant_category   | string   | NLP-classified category |
| channel             | enum     | [BANK_TRANSFER, CARD, ATM, OTHER] |
| balance_after       | float    | Running balance for liquidity checks |
| reference_id        | string   | Bank-provided txn reference |
| source_provenance   | string   | e.g., "open_banking_api" or "hdfc_stmt" |
| status              | enum     | [SUCCESS, PENDING, FAILED] |

## 2. UPI Transactions Stream (stream:upi_transactions)
Adheres to NPCI-style real-time payloads.

| Field                | Type      | Constraint & Purpose |
|----------------------|-----------|----------------------|
| event_id            | UUID     | Unique idempotent identifier |
| user_id             | string   | Anonymized user key |
| timestamp           | ISO 8601 | Payment execution time |
| amount              | float    | Signed INR |
| direction           | enum     | [INBOUND, OUTBOUND] |
| merchant_name       | string   | Parsed merchant |
| merchant_category   | string   | NLP-classified |
| txn_type            | enum     | [P2P, P2M, AUTOPAY] |
| status              | enum     | [SUCCESS, FAILED_TECHNICAL, FAILED_FUNDS] |
| source_provenance   | string   | e.g., "phonepe_export" or "upi_api" |
| upi_id              | string   | Transaction reference |

## 3. SMS Transaction Alerts Stream (stream:sms_alerts)
Core parsed fields only (regex + lightweight parser).

| Field                | Type      | Constraint & Purpose |
|----------------------|-----------|----------------------|
| event_id            | UUID     | Unique |
| user_id             | string   | Anonymized |
| timestamp           | ISO 8601 | Alert / txn time |
| amount              | float    | Parsed signed amount |
| merchant_name       | string   | Extracted |
| merchant_category   | string   | Classified |
| alert_type          | enum     | [DEBIT_ALERT, CREDIT_ALERT, UPI_ALERT, EMI_ALERT] |
| source_provenance   | string   | "sms_parser" |

## 4. Recurring EMI & Subscription Schedules Stream (stream:recurring_schedules)
From loan statements, autopay, or user schedules.

| Field                  | Type      | Constraint & Purpose |
|------------------------|-----------|----------------------|
| event_id              | UUID     | Unique |
| user_id               | string   | Anonymized |
| next_due_date         | ISO 8601 | Next expected payment |
| amount                | float    | EMI / subscription amount |
| type                  | enum     | [EMI_LOAN, SUBSCRIPTION, INSURANCE, RENT] |
| merchant_name         | string   | Lender or provider |
| merchant_category     | string   | "EMI", "SUBSCRIPTION" etc. |
| recurrence_pattern    | string   | e.g., "MONTHLY_5TH" |
| remaining_tenure      | integer  | Months left |
| status                | enum     | [ACTIVE, PAID, OVERDUE, CANCELLED] |
| source_provenance     | string   | "emi_statement" or "user_input" |

## 5. Open-Banking Feeds Stream (stream:open_banking)
From Account Aggregator framework.

| Field                | Type      | Constraint & Purpose |
|----------------------|-----------|----------------------|
| event_id            | UUID     | Unique |
| user_id             | string   | Anonymized |
| timestamp           | ISO 8601 | Aggregated txn time |
| amount              | float    | Signed |
| merchant_name       | string   | Standardized |
| merchant_category   | string   | Classified |
| balance             | float    | Snapshot balance |
| account_type        | enum     | [SAVINGS, CURRENT, LOAN, CREDIT_CARD] |
| source_provenance   | string   | "aa_framework_consent" |

## 6. Voice-Call Transcripts Stream (stream:voice_transcripts)
Core extracted fields only (STT + entity extraction).

| Field                  | Type      | Constraint & Purpose |
|------------------------|-----------|----------------------|
| event_id              | UUID     | Unique |
| user_id               | string   | Anonymized |
| timestamp             | ISO 8601 | Call time |
| extracted_amount      | float    | Mentioned payment/EMI |
| extracted_merchant    | string   | Mentioned party |
| extracted_type        | enum     | [EMI_PAYMENT, BILL_PAYMENT] |
| merchant_category     | string   | NLP-classified |
| source_provenance     | string   | "voice_stt_parser" |
| confidence_score      | float    | [0.0–1.0] |

## 7. Engineered ML Features (Polars Output)
Computed dynamically in `src/features/engine.py`. These form the final behavioural vector (18 core features + sliding-window summaries) used for trend detection, peer benchmarking, risk simulation, and cognitive credit decisions. Similar to MSME credit scoring, **cash flow, liquidity, burden, and stability** dominate because they directly indicate repayment capacity and financial distress risk (analogous to how GST revenue + cash realization mattered there).

### Cash Flow & Liquidity
| Field                        | Type   | Constraint & Purpose |
|------------------------------|--------|----------------------|
| daily_avg_throughput_30d    | float  | Average daily inflow+outflow velocity (EMA-weighted) |
| cash_buffer_days            | float  | Bounded [0.0, 90.0]; survival runway via 30d inbound vs daily outflow |
| debit_failure_rate_90d      | float  | Signals acute cash stress via failed outbound ratio |
| end_of_month_liquidity_dip  | float  | Avg balance drop in last 5 days of month (recurring pattern) |

### Behavioural & Ratio
| Field                        | Type   | Constraint & Purpose |
|------------------------------|--------|----------------------|
| emi_burden_ratio            | float  | EMI + subscription outflows / avg monthly income (30d rolling) — strongest analogue to DTI |
| savings_rate                | float  | (Income - essential - discretionary) / income |
| income_stability_score      | float  | 1 - (std(income)/mean(income)) over 90d; higher = stable |
| spending_volatility_index   | float  | Coeff. of variation of daily expenses over 90d |
| discretionary_ratio         | float  | Discretionary expenses / total expenses (90d) |
| cash_dependency_index       | float  | Cash/ATM withdrawals / total outflows |

### Recurrence & Pattern
| Field                          | Type    | Constraint & Purpose |
|--------------------------------|---------|----------------------|
| subscription_count_30d        | integer | Detected recurring non-EMI outflows |
| emi_payment_count_90d         | integer | Active EMIs |
| salary_day_spike_flag         | boolean | Discretionary spending spike within ±3 days of income events |
| lifestyle_inflation_trend     | float   | MoM % increase in discretionary spending |
| merchant_category_shift_count | integer | Abrupt changes in top categories across 30d buckets |

### Anomaly & Concentration
| Field                            | Type    | Constraint & Purpose |
|----------------------------------|---------|----------------------|
| anomaly_flag                    | boolean | Rule-based or Isolation Forest on velocity/amount |
| top3_merchant_concentration     | float   | % of spend on top 3 merchants (HHI-style) |
| peer_cohort_benchmark_deviation | float   | Z-score deviation from cohort avg (income band, city tier, age group) |

**Sliding-Window Aggregators** (real-time, updated on every event):  
7d / 30d / 90d summaries for total_income, total_expense_essential, total_discretionary, net_cashflow, and category_breakdown.

**Peer Cohort Benchmarking Layer**:  
Compares features against anonymized averages segmented by income band (<50k / 50-100k / >100k monthly), city tier (1/2/3/4), and age group.

## 8. Engineered ML Features Ranked by Importance

| Rank | Feature                          | Source Streams                          | How Obtained                  | Why Ranked High |
|------|----------------------------------|-----------------------------------------|-------------------------------|-----------------|
| 1    | emi_burden_ratio                | EMI_SCHEDULE, BANK, UPI, OPEN_BANKING  | Engineered (ratio)           | Strongest personal analogue to Debt-to-Income (DTI); best predictor of repayment capacity and default risk |
| 2    | savings_rate                    | All streams                            | Engineered (ratio)           | Most reliable indicator of long-term financial health and resilience |
| 3    | income_stability_score          | BANK, UPI, SMS, OPEN_BANKING           | Engineered (1 - CV of income) | High income volatility strongly linked to financial stress and distress |
| 4    | spending_volatility_index       | All expense streams                    | Engineered (CV of daily expenses) | Captures erratic spending behaviour; key early warning for over-spending |
| 5    | cash_buffer_days                | BANK, OPEN_BANKING                     | Engineered (runway ratio)    | Measures liquidity survival; critical for handling income shocks |
| 6    | discretionary_ratio             | All (classified expenses)              | Engineered (ratio)           | High discretionary spend signals lifestyle creep and reduced savings potential |
| 7    | debit_failure_rate_90d          | UPI, BANK, SMS                         | Engineered (failed ratio)    | Direct signal of acute cash flow stress |
| 8    | lifestyle_inflation_trend       | All (MoM discretionary)                | Engineered (MoM % change)    | Detects progressive spending increase that erodes financial buffer |
| 9    | daily_avg_throughput_30d        | All                                    | Engineered (EMA avg)         | Overall cash flow activity and velocity |
| 10   | end_of_month_liquidity_dip      | BANK, OPEN_BANKING                     | Engineered (pattern)         | Identifies recurring pre-salary liquidity crunches |
| 11   | subscription_count_30d          | EMI_SCHEDULE, BANK, UPI                | Engineered (recurrence)      | Tracks hidden recurring commitments inflating burden |
| 12   | emi_payment_count_90d           | EMI_SCHEDULE, BANK                     | Engineered (count)           | Measures active long-term debt load |
| 13   | salary_day_spike_flag           | All (around income events)             | Engineered (pattern)         | Detects poor impulse control after salary credits |
| 14   | merchant_category_shift_count   | All                                    | Engineered (category delta)  | Sudden shifts often signal life changes or emerging risks |
| 15   | top3_merchant_concentration     | All                                    | Engineered (HHI-style)       | High concentration indicates dependency risk |
| 16   | anomaly_flag                    | All                                    | Engineered (Isolation Forest/rules) | Flags unusual patterns for scam or fraud defence |
| 17   | peer_cohort_benchmark_deviation | All                                    | Engineered (z-score)         | Contextualizes user behaviour against similar peers |
| 18   | cash_dependency_index           | BANK, UPI (cash/ATM)                   | Engineered (ratio)           | High cash usage signals lower formal financial integration |