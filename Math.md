# Math.md — Mathematical Foundations

**Related Tiers**: Tier 2 (Event Stream Processor & Semantic Classifier), Tier 3 (Behavioural Feature Extraction & Trend Engine), Tier 6 (Predictive Risk Simulation), Tier 7 (Cognitive Credit Engine)

This document defines all mathematical equations, algorithms, and formulas used in the personal finance intelligence engine.

## 0. Real-time Typed Financial Event Classification & Sliding-Window Aggregation (Tier 2)

### A. Typed Financial Event Classification
Every raw event from any source is normalized into the canonical schema and assigned:
- `type`: INCOME, EXPENSE_ESSENTIAL, EXPENSE_DISCRETIONARY, EMI_PAYMENT, SUBSCRIPTION, TRANSFER, INVESTMENT, REFUND, OTHER
- `merchant_category`: GROCERY, TRANSPORT, DINING, HEALTHCARE, ENTERTAINMENT, BILLS_UTILITIES, EMI, SUBSCRIPTION, etc.

**Classification Method** (lightweight & real-time):
- Hybrid: Rule-based + regex for obvious cases (e.g., salary credit → INCOME, EMI keyword → EMI_PAYMENT)
- Primary: Lightweight embedded NLP using sentence-transformers embeddings + cosine similarity / KNN on `merchant_name`
- Output becomes the typed event fed into Redis Streams and the Polars feature engine

### B. Sliding-Window Aggregation
On every new event, real-time 7-day, 30-day, and 90-day summaries are updated (total income, essential expense, discretionary expense, net cashflow, category breakdown).

**Exponential Moving Average (EMA) for velocity features** (preferred to avoid cliff effects):

$$
v_{\text{ema}}(w) = \sum_{i} amount_i \cdot \exp\left(-\frac{\ln 2}{w} \cdot (t_{\text{now}} - t_i)\right)
$$

where \( w \) is the half-life window in days (7, 30, or 90).

**Simple sum and count in sliding window**:

$$
\text{sum}_w = \sum_{\text{events in last } w \text{ days}} amount_i
$$

$$
\text{count}_w = |\{ \text{events in last } w \text{ days} \}|
$$

These aggregates serve as inputs for all Tier 3 behavioural features. Late-arrival events trigger re-computation of affected windows.

## 1. Core Time-Series & Window Computations

Daily Average Throughput (30d):

$$
\text{daily\_avg\_throughput}_{30d} = \frac{1}{30} \sum_{d=1}^{30} (\text{inflow}_d + \text{outflow}_d)
$$

## 2. Cash Flow & Liquidity Features (Tier 3)

Cash Buffer Days (survival runway):

$$
\text{cash\_buffer\_days} = \min\left( \frac{\text{avg inbound}_{30d}}{\text{avg daily outflow}_{30d}}, 90 \right)
$$

Debit Failure Rate (90d):

$$
\text{debit\_failure\_rate}_{90d} = \frac{\sum \text{failed outbound transactions}_{90d}}{\sum \text{total outbound transactions}_{90d}}
$$

End-of-Month Liquidity Dip:

$$
\text{eom\_liquidity\_dip} = \frac{1}{N} \sum_{m=1}^{N} (\text{balance}_{\text{end of month } m} - \text{balance}_{25\text{th of month } m})
$$

## 3. Behavioural & Ratio Features (Tier 3)

Spending Volatility Index:

$$
\text{spending\_volatility\_index} = \frac{\sigma(\text{daily\_expenses}_{90d})}{\mu(\text{daily\_expenses}_{90d})}
$$

Income Stability Score:

$$
\text{income\_stability\_score} = \max\left(0, \min\left(1, 1 - \frac{\sigma(\text{income\_amounts}_{90d})}{\mu(\text{income\_amounts}_{90d})}\right)\right)
$$

Discretionary Ratio:

$$
\text{discretionary\_ratio} = \frac{\sum \text{discretionary expenses}_{90d}}{\sum \text{total expenses}_{90d}}
$$

EMI Burden Ratio:

$$
\text{emi\_burden\_ratio} = \frac{\sum (\text{EMI} + \text{subscription outflows})_{30d}}{\text{avg monthly income}}
$$

Savings Rate:

$$
\text{savings\_rate} = \frac{\text{total income} - \text{essential expenses} - \text{discretionary expenses}}{\text{total income}}
$$

Cash Dependency Index:

$$
\text{cash\_dependency\_index} = \frac{\sum \text{cash/ATM withdrawals}_{90d}}{\sum \text{total outflows}_{90d}}
$$

Top-3 Merchant Concentration (Herfindahl-Hirschman style):

$$
\text{top3\_concentration} = \sum_{i=1}^{3} \left( \frac{\text{amount to merchant}_i}{\text{total spend}} \right)^2
$$

## 4. Recurrence & Pattern Detection (Tier 3)

Lifestyle Inflation Trend (MoM % change in discretionary spending):

$$
\text{lifestyle\_inflation\_trend} = \frac{\text{discretionary}_m - \text{discretionary}_{m-1}}{\text{discretionary}_{m-1}}
$$

Merchant Category Shift Count:
- Simple count of changes in top-5 spending categories between consecutive 30-day buckets  
  (Optional: Kullback-Leibler divergence between category probability distributions \( p \) and \( q \))

Salary-Day Spike Flag:
- Detect major income events by timestamp clustering
- Compute average discretionary spend in \([-3, +3]\) days window around income events
- Flag if deviation > 25% from baseline

Shannon Entropy for category diversity (optional):

$$
H = -\sum_{c=1}^{C} p_c \ln(p_c)
$$

where \( p_c \) is the proportion of spend in category \( c \).

## 5. Anomaly & Concentration Features (Tier 3)

Anomaly Flag: Output of lightweight Isolation Forest or rule-based z-score on amount deviation, velocity bursts, or inter-arrival times.

Peer Cohort Benchmark Deviation (Z-score):

$$
z = \frac{x_{\text{user}} - \mu_{\text{cohort}}}{\sigma_{\text{cohort}}}
$$

where cohort is segmented by income band, city tier, and age group.

## 6. Monte Carlo Risk Simulation (Tier 6)

Basic Monte Carlo for future cash position:

$$
\text{Cash}_t^{(k)} = \text{Cash}_0 + \sum_{i=1}^{t} \left( \text{Income}_i^{(k)} - \text{Expense}_i^{(k)} + \text{InvestmentReturn}_i^{(k)} \right)
$$

Probability of Ruin:

$$
P(\text{ruin}) = \frac{1}{N} \sum_{k=1}^{N} \mathbb{I}\left( \min_t \text{Cash}_t^{(k)} < 0 \right)
$$

## 7. Dynamic Financial Health Score (Tier 7)

Composite example (can feed into ML model):

$$
\text{Health Score} = w_1(1 - \text{emi\_burden\_ratio}) + w_2 \cdot \text{savings\_rate} + w_3 \cdot \text{income\_stability\_score} - w_4 \cdot \text{spending\_volatility\_index} - w_5 \cdot |z_{\text{peer}}|
$$

**Typical starting weights** (normalize to sum ≈ 1.0):
- EMI Burden: 0.22
- Savings Rate: 0.20
- Income Stability: 0.15
- Spending Volatility: 0.12
- Peer Deviation & others: remaining weight

## 8. Additional Supporting Formulas

Coefficient of Variation (CV):

$$
CV = \frac{\sigma}{\mu}
$$

(Used in volatility and stability metrics)

## Notes
- All time-based computations use ISO 8601 timestamps and Polars rolling/EMA windows for efficiency.
- Late-arrival events are handled by re-computing affected windows.
- Peer cohorts are pre-computed as Redis hashes or Parquet summaries for fast lookup.
- Monte Carlo uses thousands of paths with distributions derived from user history + external benchmarks.

These formulas directly support:
- Real-time typed event classification & sliding windows (Tier 2)
- Behavioural Feature Engine & Digital Twin (Tier 3–4)
- LLM Reasoning & Predictive Risk Simulation (Tier 5–6)
- Cognitive Credit Engine & Anomaly Detection (Tier 7–10)