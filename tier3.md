# Tier 3: Behavioural Feature Engine

Related Tiers: Tier 3 (Behavioural Feature Engine)

## 1. Overview: The Engine of Behavioural Intelligence

Tier 3 is where raw processed events from Tier 2 are transformed into specialized **behavioural vectors**. This engine uses high-performance Polars processing to extract 46+ distinct features that capture the "DNA" of a user's financial behaviour.

### 1.1 Core Methodology: Polars & Vectorization
The feature engine is built for extreme efficiency on single-machine hardware.
- **Batched Windowing**: Uses rolling aggregates over 7d, 30d, and 90d windows.
- **Parallel Feature Extraction**: Extracts cash-flow, liquidity, and stability metrics in parallel across the event stream.
- **Normalization**: All features are projected into a normalized space ([0-1] or Z-scores) to enable downstream ML scoring and Digital Twin updates.

---

## 2. Feature Domains & Key Metrics

We categorize features into four critical domains, as defined in `Math.md`:

### 2.1 Cash Flow & Liquidity
- **Daily Avg Throughput**: Measures total inbound/outbound volume (EMA-weighted).
- **Cash Buffer Days**: The estimated "runway" a user has based on income vs. daily outflow.
- **Debit Failure Rate**: A high-sensitivity signal of acute liquidity stress.

### 2.2 Behavioural Ratios (The "DTI" Analogue)
- **EMI Burden Ratio**: Total debt/subscription outflows vs. avg monthly income. This is the strongest predictor of repayment capacity.
- **Savings Rate**: The residual income percentage after essential and discretionary expenses.
- **Discretionary Ratio**: Measures "lifestyle overhead" by comparing discretionary spend to total outflows.

### 2.3 Stability & Trend Engine
- **Income Stability Score**: 1 - Coefficient of Variation (CV) of income. Measures the "salary-likeness" of inbound flows.
- **Spending Volatility Index**: Measures the erratic nature of day-to-day spending.
- **Lifestyle Inflation Trend**: Captures month-over-month increases in discretionary spending (the "creep" factor).

---

## 3. High-Importance Features (Top 5)

| Rank | Feature | Why it Matters |
|---|---|---|
| **1** | **EMI Burden Ratio** | Quantifies the immediate risk of default on fixed obligations. |
| **2** | **Savings Rate** | Indicates the net "burn" or "wealth accumulation" capability. |
| **3** | **Income Stability** | Critical for MSME and Gig-worker lending where income is non-fixed. |
| **4** | **Cash Buffer Days** | Best metric for short-term survival and emergency preparedness. |
| **5** | **Spending Volatility** | High volatility often precedes financial distress or anomaly events. |

---

## 4. Output: The Feature Vector
The output of Tier 3 is a version-controlled **Behavioural Vector** pushed to the Digital Twin State Layer (Tier 4). This vector serves as the "source of truth" for:
- XGBoost Risk Scoring (Tier 7)
- Monte Carlo Risk Simulation (Tier 6)
- LLM-based Narrative Generation (Tier 5)
