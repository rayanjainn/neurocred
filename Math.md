# Math.md — Mathematical Foundations
Related Tiers: Tier 2 (Event Stream Processor), Tier 3 (Behavioural Feature Engine), Tier 6 (Predictive Risk Simulation), Tier 7 (Cognitive Credit Engine)

This document defines all mathematical equations, algorithms, and formulas used in the personal finance intelligence engine across the 10 layers.

## 1. Core Time-Series & Window Computations (Tier 2)

Exponential Moving Average (EMA) weighted velocity (used for all 7d/30d/90d aggregates to avoid cliff effects):

$$
v_{\text{ema}}(w) = \sum_{i} amount_i \cdot e^{-\frac{\ln 2}{w} \cdot (t_{\text{now}} - t_i)}
$$

where \( w \) is the half-life window in days (7, 30, or 90).

Daily average throughput (30d):

$$
\text{daily\_avg\_throughput}_{30d} = \frac{1}{30} \sum_{d=1}^{30} (\text{inflow}_d + \text{outflow}_d)
$$

## 2. Cash Flow & Liquidity Features (Tier 3)

Cash Buffer Days (survival runway):

$$
\text{cash\_buffer\_days} = \min\left( \frac{\text{avg inbound}_{30d}}{\text{avg daily outflow}}, 90 \right)
$$

Debit Failure Rate (90d):

$$
\text{debit\_failure\_rate}_{90d} = \frac{\sum \text{failed outbound transactions}}{\sum \text{total outbound transactions}}
$$

End-of-Month Liquidity Dip:

$$
\text{eom\_liquidity\_dip} = \frac{1}{N} \sum_{m=1}^{N} (\text{balance}_{25\text{th}-end_m} - \text{balance}_{1\text{st}_m})
$$

## 3. Behavioural & Ratio Features

Spending Volatility Index (Coefficient of Variation on daily expenses):

$$
\text{spending\_volatility\_index} = \frac{\sigma(\text{daily\_expenses}_{90d})}{\mu(\text{daily\_expenses}_{90d})}
$$

Income Stability Score:

$$
\text{income\_stability\_score} = 1 - \frac{\sigma(\text{income\_amounts}_{90d})}{\mu(\text{income\_amounts}_{90d})}
$$

(Clamped to [0, 1]; higher = more stable, salary-like income)

Discretionary Ratio:

$$
\text{discretionary\_ratio} = \frac{\sum \text{discretionary expenses}_{90d}}{\sum \text{total expenses}_{90d}}
$$

EMI Burden Ratio (analogous to Debt-to-Income for recurring obligations):

$$
\text{emi\_burden\_ratio} = \frac{\sum (\text{EMI} + \text{subscription outflows})_{30d}}{\text{avg monthly income}}
$$

Savings Rate:

$$
\text{savings\_rate} = \frac{\text{total income} - \text{essential expenses} - \text{discretionary expenses}}{\text{total income}}
$$

Cash Dependency Index:

$$
\text{cash\_dependency\_index} = \frac{\sum \text{cash/ATM withdrawals}}{\sum \text{total outflows}}
$$

Top-3 Merchant Concentration (Herfindahl-Hirschman Index style):

$$
\text{top3\_concentration} = \sum_{i=1}^{3} \left( \frac{\text{amount to merchant}_i}{\text{total spend}} \right)^2
$$

## 4. Recurrence & Pattern Detection

Lifestyle Inflation Trend (Month-over-Month % change in discretionary spending):

$$
\text{lifestyle\_inflation\_trend} = \frac{\text{discretionary}_{m} - \text{discretionary}_{m-1}}{\text{discretionary}_{m-1}}
$$

Merchant Category Shift Count:

Use Kullback-Leibler divergence between two 30d category probability distributions \( p \) and \( q \), or simple count of changes in top-5 categories.

Shannon Entropy for spending category diversity (optional complementary measure):

$$
H = -\sum_{c=1}^{C} p_c \ln(p_c)
$$

where \( p_c \) is the proportion of spend in category \( c \).

Salary-Day Spike Flag:

1. Detect major income events (clustered by timestamp).
2. Compute average discretionary spend in \([-3, +3]\) days window around income events vs. baseline.
3. Flag if deviation > threshold (e.g., +25%).

## 5. Anomaly & Concentration Features

Anomaly Flag: Output of Isolation Forest or rule-based z-score on features such as amount deviation, velocity bursts, or inter-arrival times.

Peer Cohort Benchmark Deviation (Z-score style):

$$
z = \frac{x_{\text{user}} - \mu_{\text{cohort}}}{\sigma_{\text{cohort}}}
$$

where cohort is segmented by income band, city tier, and age group.

## 6. Monte Carlo Risk Simulation (Layers 5–6: Predictive Risk Simulation)

For stress testing cash flow, savings depletion, or recovery paths, run \( N \) (typically 10,000+) simulations.

Basic Monte Carlo for future cash position at time \( t \):

$$
\text{Cash}_t^{(k)} = \text{Cash}_0 + \sum_{i=1}^{t} \left( \text{Income}_i^{(k)} - \text{Expense}_i^{(k)} + \text{InvestmentReturn}_i^{(k)} \right)
$$

where each simulation \( k \) draws random variables from distributions:
- Income ~ Normal(\( \mu_{\text{income}} \), \( \sigma_{\text{income}} \)) or lognormal for stability
- Expenses ~ Normal or with volatility
- Returns ~ Normal(\( \mu_r \), \( \sigma_r \)) with optional correlation

Probability of ruin (e.g., cash < 0):

$$
P(\text{ruin}) = \frac{1}{N} \sum_{k=1}^{N} \mathbb{I}(\min_t \text{Cash}_t^{(k)} < 0)
$$

Stress Test Scenarios:
- Base case: historical means
- Adverse: +1σ or +2σ on expenses / -1σ on income
- Recovery path modelling: optimize nudge variables (e.g., reduce discretionary by X%) to minimize ruin probability.

## 7. Dynamic Credit / Risk Scoring (Layer 7–8)

Composite Financial Health Score (example weighted sum; can feed into ML model):

$$
\text{Health Score} = w_1 \cdot (1 - \text{emi\_burden\_ratio}) + w_2 \cdot \text{savings\_rate} + w_3 \cdot \text{income\_stability\_score} - w_4 \cdot \text{spending\_volatility\_index} - w_5 \cdot \text{peer\_deviation}
$$

Typical starting weights (normalize to sum ≈ 1.0):
- EMI Burden: 0.20–0.25
- Savings Rate: 0.18–0.22
- Income Stability: 0.12–0.15
- Volatility: 0.10–0.12
- Others: remaining weight

For Monte Carlo-enhanced decisioning, expected loss or safe loan amount can be derived from simulation outputs.

## 8. Additional Supporting Formulas

Coefficient of Variation (general):

$$
CV = \frac{\sigma}{\mu}
$$

(Used in volatility and stability metrics)

## Notes
- All time-based computations use ISO 8601 timestamps and Polars rolling/EMA windows for efficiency.
- Late-arrival events are handled by re-computing affected windows.
- Peer cohorts are pre-computed as Redis hashes or Parquet summaries for fast lookup.
- Monte Carlo uses thousands of paths with realistic distributions derived from user historical data + external benchmarks.

These formulas directly support:
- Real-time typed event classification & sliding windows (Layer 2)
- Behavioural Feature Engine & Digital Twin (Layer 3–4)
- LLM Reasoning & Predictive Risk Simulation (Layer 5–6)
- Cognitive Credit Engine & Anomaly Detection (Layer 7–10)
