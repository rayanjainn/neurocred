# how_risk_simulation_engine_f2.md — Predictive Risk Simulation Engine (Tier 6)
Related Tiers: Tier 6 (Predictive Risk Simulation), Tier 4 (Digital Twin State), Tier 5 (LLM Reasoning), Tier 8 (Proactive Intervention Agent), Tier 10 (Audit Repository)

**Agentic-AI Financial Digital Twin & Cognitive Credit Engine**

**Table of contents**
1. [Schema references & compliance](#1-schema-references--compliance)
2. [Profile variance strategy](#2-profile-variance-strategy)
3. [Mathematical foundations — advanced stochastic engine](#3-mathematical-foundations--advanced-stochastic-engine)
4. [Regime-switching & early warning system](#4-regime-switching--early-warning-system)
5. [Correlated Monte Carlo engine](#5-correlated-monte-carlo-engine)
6. [EMI cascade & contagion model](#6-emi-cascade--contagion-model)
7. [Stress scenario library — compound & atomic](#7-stress-scenario-library--compound--atomic)
8. [Dynamic recovery path modeller](#8-dynamic-recovery-path-modeller)
9. [Bayesian posterior updating](#9-bayesian-posterior-updating)
10. [Tail risk & fan chart outputs](#10-tail-risk--fan-chart-outputs)
11. [Counterfactual reasoning engine](#11-counterfactual-reasoning-engine)
12. [Architectural decisions](#12-architectural-decisions)
13. [Target variables & real-world transition strategy](#13-target-variables--real-world-transition-strategy)
14. [Where to get the real-data (licensed sources)](#14-where-to-get-the-real-data-licensed-sources)
15. [Mock API-JSON schemas & simulation flow](#15-mock-api-json-schemas--simulation-flow)

---

## 1. Schema references & compliance

| Domain / Component | Authority / Source | Application / Enforcement |
| --- | --- | --- |
| Risk Simulation & Stress Testing | RBI Master Directions on Credit Risk Management & Stress Testing (2024–2025 updates) | Enforces forward-looking, scenario-based assessment; mandates tail-risk (CVaR) reporting for MSME lending decisions. |
| Monte Carlo & Internal Models | RBI Guidelines on IMA (Internal Models Approach) & Basel III/IV-aligned practices | Validates probabilistic simulation for default probability, liquidity VaR, and CVaR-style Expected Shortfall. |
| Regime-Switching Models | Basel Committee Working Paper on Stress Testing (2017, updated 2024) | Supports use of HMM-style financial regime classifiers as forward-looking state estimators in credit risk engines. |
| Integration with Digital Twin | Sahamati AA Framework & RBI Digital Lending Directions (2025) | Consented twin state as simulation input; all output metrics feed back into twin's `predicted_risk_trajectory` for audit continuity. |
| Counterfactual & Audit Traces | RBI Digital Lending Directions — Transparency & Explainability clause | All simulation runs, parameter choices, and recovery recommendations must be machine-readable and reproducible per `simulation_id`. |
| Recovery Path Modelling | RBI Fair Practices Code & Grievance Redressal Directions | Interventions must be costed, realistically achievable, and borrower-friendly; no recommendation exceeds user's capacity constraints. |
| Data Privacy | DPDPA 2023 + RBI Data Localisation | No raw PII in simulation logs; only aggregated metrics and anonymized distributions persisted. Seeded RNG ensures audit reproducibility without re-running raw data. |

All simulations are **deterministically reproducible** via a `(gstin, simulation_id, seed)` triple. A regulator can re-run any historical simulation and obtain bit-identical results.

---

## 2. Profile variance strategy

The simulation engine is calibrated to the same 5 MSME/consumer personas used across all tiers, but extends them with **regime-entry probabilities** and **cascade susceptibility scores** that are unique to Tier 6:

| Profile type | Weight | Simulation Behavior | Regime Entry Prob. (crisis) | Cascade Susceptibility |
| --- | --- | --- | --- | --- |
| **genuine_healthy** | 40% | Default prob. <12%, rapid mean-reversion, tight confidence bands; EMI cascade unlikely. | 4% | Low (0.1) |
| **genuine_struggling** | 25% | Baseline default prob. 28–48%; liquidity crash median ~18 days under mild stress; high cascade risk. | 22% | High (0.72) |
| **shell_circular** | 15% | Bimodal distribution (extreme crash or false stability); regime transitions rapid and unpredictable. | 38% | Very High (0.91) |
| **paper_trader** | 10% | Very high spending_volatility → unstable GARCH variance; confidence bands extremely wide. | 31% | High (0.68) |
| **new_to_credit** | 10% | High epistemic uncertainty (short history); Student-t distributions with heavy tails; wider fan bands. | 12% | Medium (0.45) |

Each persona initializes the **Regime HMM** with persona-specific transition matrix priors (see §4). Cascade susceptibility directly gates the EMI Cascade Model (see §6).

---

## 3. Mathematical foundations — advanced stochastic engine

This section replaces the prior simple lognormal model with a fully correlated, regime-aware, variance-clustering stochastic engine.

### 3.1 GARCH(1,1)-inspired time-varying volatility

Static σ values produce artificially smooth Monte Carlo paths. In reality, financial volatility clusters — stressed periods have elevated, autocorrelated variance. Each simulated income and expense path uses a variance that evolves per step:

$$
\sigma_t^2 = \omega + \alpha \cdot \epsilon_{t-1}^2 + \beta \cdot \sigma_{t-1}^2
$$

where:
- $\omega > 0$: long-run variance floor (persona-dependent)
- $\alpha \geq 0$: reaction coefficient (sensitivity to last shock)
- $\beta \geq 0$: persistence coefficient (how long shocks linger)
- Constraint: $\alpha + \beta < 1$ (covariance stationarity)

**Persona parameter table:**

| Persona | ω | α | β | Interpretation |
|---|---|---|---|---|
| genuine_healthy | 0.0002 | 0.05 | 0.90 | Low reaction, high persistence but tight floor |
| genuine_struggling | 0.0015 | 0.18 | 0.75 | Higher reaction; stress shocks amplify |
| shell_circular | 0.0030 | 0.30 | 0.60 | Volatile; shocks decay faster but hit harder |
| paper_trader | 0.0025 | 0.25 | 0.68 | Burst-mode volatility clusters |
| new_to_credit | 0.0010 | 0.12 | 0.80 | Elevated uncertainty; wide uncertainty cone |

For `new_to_credit` profiles where history is sparse (<6 months), income paths use **Student-t innovations** with ν = 4 degrees of freedom (heavy-tailed) rather than Gaussian, reflecting genuine epistemic uncertainty.

### 3.2 Correlated shock generation via Cholesky decomposition

The prior model sampled income and expense independently. This is statistically wrong: a job-loss event simultaneously suppresses income and may spike medical/essential expenses. All stochastic shocks are drawn from a **multivariate distribution** with a user-calibrated correlation matrix.

**Shock vector** at each daily step:

$$
\boldsymbol{\epsilon}_t = [\epsilon_{\text{income}},\ \epsilon_{\text{expense\_essential}},\ \epsilon_{\text{expense\_discretionary}},\ \epsilon_{\text{emi\_delay}}]^T
$$

**Correlation matrix** (calibrated to persona; baseline genuine_healthy example):

$$
\Sigma = \begin{bmatrix}
1.00 & -0.55 & -0.30 & -0.40 \\
-0.55 & 1.00 & 0.62 & 0.35 \\
-0.30 & 0.62 & 1.00 & 0.18 \\
-0.40 & 0.35 & 0.18 & 1.00
\end{bmatrix}
$$

Key correlations: income shock is **negatively** correlated with essential expense (income drop → more essential pressure) and with EMI delay probability. Discretionary and essential expense are **positively** correlated (lifestyle inertia under stress).

**Generation via Cholesky**:

$$
\boldsymbol{\epsilon}_t = \mathbf{L} \cdot \mathbf{z}_t, \quad \mathbf{z}_t \sim \mathcal{N}(\mathbf{0}, \mathbf{I})
$$

where $\mathbf{L}$ is the lower-triangular Cholesky factor of $\Sigma$. This guarantees that all marginal distributions remain correct while respecting the inter-variable correlation structure.

**Correlation matrices are persona-specific** — `shell_circular` has high positive correlations between all expense types (rotational liquidity floods all channels) and near-zero negative income correlation (income appears artificially stable).

### 3.3 Daily cash state evolution

The full cash state on day $t$ of simulation path $k$:

$$
C_t^{(k)} = C_{t-1}^{(k)} + I_t^{(k)} - E_{\text{ess},t}^{(k)} - E_{\text{disc},t}^{(k)} - \text{EMI}_t^{(k)} \cdot \mathbb{1}[\text{due}_t] - P_t^{(k)}
$$

where:
- $I_t^{(k)}$: stochastic income draw (GARCH variance, correlated)
- $E_{\text{ess},t}^{(k)}$: essential expense (lognormal, correlated)
- $E_{\text{disc},t}^{(k)}$: discretionary expense (adjusted by regime multiplier; see §4)
- $\text{EMI}_t^{(k)} \cdot \mathbb{1}[\text{due}_t]$: EMI payment on due-date only
- $P_t^{(k)}$: cascade penalty interest (zero unless missed EMI in previous window; see §6)

**Absorbing barrier**: If $C_t^{(k)} < -\delta_{\text{overdraft}}$ (where $\delta$ is any available credit line), the path is flagged as **defaulted at step $t$** and enters the EMI cascade module.

### 3.4 Variance reduction — Quasi-Monte Carlo with antithetic variates

Running 1,000 independent Gaussian paths wastes computational budget on redundant variance. Two orthogonal variance reduction techniques are applied:

**Antithetic Variates**: For every path $k$ using noise vector $\mathbf{z}_t^{(k)}$, a paired path $k'$ uses $-\mathbf{z}_t^{(k)}$. This exactly halves the variance of symmetric estimators at zero additional sampling cost. Effective simulation count doubles from 1,000 to 2,000-path-equivalent precision.

**Sobol Quasi-Monte Carlo**: For the first 512 paths, replace $\mathbf{z}_t$ with Sobol low-discrepancy sequences (via `scipy.stats.qmc.Sobol`). This fills the probability space uniformly rather than randomly, achieving the convergence rate $O((\log N)^d / N)$ versus standard Monte Carlo's $O(1/\sqrt{N})$. In practice, 500 Sobol paths match the accuracy of 3,000–5,000 standard Monte Carlo paths for smooth integrands.

**Combined strategy**: 256 Sobol path-pairs (antithetic) + 244 standard random path-pairs = **1,000 total paths** with effective precision equivalent to **~4,000+ standard Monte Carlo runs**, well within real-time budget.

---

## 4. Regime-switching & early warning system

### 4.1 Financial regime classifier (HMM-inspired)

The user's financial state is not continuous — it discretely occupies one of three regimes, and the transition dynamics govern how rapidly the simulation fan diverges.

**Regimes:**

| Regime | Label | Characteristics | Simulation multiplier on σ |
|---|---|---|---|
| R0 | STABLE | income_stability > 0.75, cash_buffer > 15d, emi_burden < 0.35 | 1.0× (baseline) |
| R1 | STRESSED | cash_buffer 5–15d OR emi_burden 0.35–0.55 OR debit_failure_rate > 0.08 | 1.6× |
| R2 | CRISIS | cash_buffer < 5d OR emi_burden > 0.55 OR two consecutive missed EMIs | 2.8× |

**Transition probability matrix** (baseline; updated per persona):

$$
\mathbf{A} = \begin{bmatrix}
P(R0 \to R0) & P(R0 \to R1) & P(R0 \to R2) \\
P(R1 \to R0) & P(R1 \to R1) & P(R1 \to R2) \\
P(R2 \to R0) & P(R2 \to R1) & P(R2 \to R2)
\end{bmatrix} = \begin{bmatrix}
0.92 & 0.07 & 0.01 \\
0.25 & 0.60 & 0.15 \\
0.05 & 0.30 & 0.65
\end{bmatrix}
$$

At each simulation step, the current regime is sampled from this transition matrix. The active regime then gates which expense multiplier and income suppressor applies for that step's shock generation. This creates the realistic property that distressed users tend to stay distressed, and stable users have high inertia.

**Regime update from real events**: When a real `twin_updated` event arrives mid-simulation (e.g., a salary credit), the current regime distribution is updated via a Bayes factor (see §9), potentially collapsing the simulation from R1 back toward R0.

### 4.2 Early Warning Score (EWS)

The EWS is a leading indicator computed from the simulation ensemble **before** crisis materialises. Unlike the default probability (which measures how many paths end in ruin), the EWS measures how many paths are **approaching** the crisis threshold in the near term.

$$
\text{EWS}(d) = \frac{1}{N} \sum_{k=1}^{N} \mathbb{1}\left[ \min_{t \in [1,d]} C_t^{(k)} < \theta_{\text{warning}} \right]
$$

where $\theta_{\text{warning}} = 0.5 \times \text{monthly\_emi\_total}$ (the user has less than half an EMI cycle's worth of liquid buffer).

**EWS is computed at three horizons**: 7-day, 14-day, and 30-day. When EWS(14) > 0.30, the Intervention Agent (Tier 8) is triggered **before** the Proactive Nudge threshold would normally fire, giving a 14-day advance warning window.

**EWS Severity Bands:**

| EWS(14) | Severity | Action |
|---|---|---|
| 0.00 – 0.15 | GREEN | No action; routine twin update |
| 0.15 – 0.30 | AMBER | Soft nudge via Tier 8 |
| 0.30 – 0.55 | ORANGE | EMI-at-risk alert + micro-loan pre-qualification |
| > 0.55 | RED | Immediate intervention + human escalation flag |

---

## 5. Correlated Monte Carlo engine

### 5.1 Full simulation algorithm

```
INPUT:
  twin_state       ← current Digital Twin (Tier 4)
  scenario         ← stress scenario parameters (§7)
  N = 1000         ← total simulation paths
  H = 90           ← horizon in days (adaptive; see 5.3)
  seed             ← gstin_hash XOR simulation_timestamp

INITIALISE:
  C_0 = twin_state.cash_balance_current
  σ_income_0, σ_expense_0 ← from twin_state feature vector
  Σ ← persona-calibrated correlation matrix
  L ← Cholesky(Σ)
  regime_0 ← classify_regime(twin_state)

FOR k in 1..N/2:                              # Antithetic pairs
  FOR t in 1..H:
    regime_t ← sample(A, regime_{t-1})        # Regime transition
    σ_t ← GARCH_update(σ_{t-1}, ε_{t-1})     # Time-varying vol
    z_pos ← Sobol_or_Gaussian(dim=4, seed+k)  # Low-discrepancy
    z_neg ← -z_pos                             # Antithetic
    ε_pos ← L @ z_pos * σ_t * regime_multiplier[regime_t]
    ε_neg ← L @ z_neg * σ_t * regime_multiplier[regime_t]
    
    FOR (ε, path_idx) in [(ε_pos, k), (ε_neg, k + N/2)]:
      I_t     ← apply_income_shock(scenario, ε[0])
      E_ess_t ← apply_essential_shock(scenario, ε[1])
      E_dis_t ← apply_discretionary(regime_t, ε[2])
      EMI_t   ← compute_emi(t, twin_state, ε[3])
      P_t     ← cascade_penalty(path_idx, t)   # §6
      
      C_t[path_idx] = C_{t-1}[path_idx] + I_t - E_ess_t - E_dis_t - EMI_t - P_t
      
      IF C_t[path_idx] < -overdraft_limit:
        mark_default(path_idx, t)
        trigger_cascade(path_idx, t)
        C_t[path_idx] = -overdraft_limit       # Hard floor

EXTRACT metrics from path matrix C[N × H]:
  → default_probability, CVaR, EWS, fan_chart_percentiles, EMI_stress_score
  → run recovery path modeller (§8)
  → run counterfactual engine (§11)
  → emit simulation_completed event → update twin.predicted_risk_trajectory
```

### 5.2 Output: percentile path matrix (fan chart)

All 1,000 paths are stored as a `[N × H]` matrix. The fan chart percentile series (aligned with `brand.md` specification) are extracted as:

$$
\text{Fan}_{p}(t) = \text{percentile}_{p}\left( \{C_t^{(k)}\}_{k=1}^{N} \right), \quad p \in \{10, 25, 50, 75, 90\}
$$

These five series are emitted in the simulation response for direct rendering by the Dashboard Fan Chart component (P10 → crimson dashed, P25 → amber, P50 → white 2px, P75 → acid, P90 → acid dashed — per brand spec).

### 5.3 Adaptive horizon

The simulation horizon $H$ is not fixed at 90 days. It is dynamically chosen as:

$$
H = \max\left(90,\ \min\left(180,\ \text{round}\left(\frac{2 \times \text{cash\_buffer\_days}}{\text{income\_stability}} \cdot 1.5\right)\right)\right)
$$

If `EWS(14) > 0.55` (RED severity), the horizon automatically extends to 180 days to map the full crisis arc and identify the recovery inflection point. For `genuine_healthy` profiles in baseline runs, the minimum 90 days applies.

---

## 6. EMI cascade & contagion model

This is the most novel addition to Tier 6. The prior model treated each EMI as an independent Bernoulli event. In reality, one missed EMI triggers a **compounding cascade** that dramatically changes subsequent path dynamics.

### 6.1 Cascade trigger conditions

An EMI cascade is triggered on simulation path $k$ at day $t$ if:

$$
C_t^{(k)} < \text{EMI}_{t,\text{due}} \quad \text{AND} \quad \mathbb{1}[\text{due}_t] = 1
$$

(The user's cash is insufficient to cover the scheduled EMI on its due date.)

### 6.2 Four-stage cascade model

Once triggered, the cascade propagates across four stages. Each stage has a **probability of escalation** to the next, based on `cascade_susceptibility` (persona parameter from §2):

**Stage 1 — Missed EMI (Day 0 of cascade)**
- Penalty interest rate $r_p$ applied: `base_rate + 2% p.a.` per RBI fair practices guidelines.
- New EMI amount for next cycle: $\text{EMI}_{t+30} = \text{EMI}_{\text{base}} \times (1 + r_p / 12) + \frac{\text{overdue\_principal}}{N_{\text{remaining}}}$
- Debit failure recorded: +1 to `debit_failure_rate` counter.

**Stage 2 — Credit Limit Reduction (Day 7–14 of cascade, P = 0.55 × cascade_susceptibility)**
- Simulated lender reduces revolving credit limit by 30%.
- `overdraft_limit` reduced in simulation: cash floor tightens.
- EMI burden ratio spikes in twin state: may trigger regime transition R0→R1 or R1→R2.

**Stage 3 — Second EMI Miss (Day 30 of cascade, P = 0.40 × cascade_susceptibility if Stage 2 triggered)**
- Compound overdue: two missed EMI principals now in arrears.
- Penalty rate escalates to `base_rate + 4% p.a.`
- `credit_dependency_score` in twin spikes: LLM narrative flags "progressive debt spiral."
- EWS immediately jumps one severity band regardless of current cash level.

**Stage 4 — Lender Default Filing (Day 60 of cascade, P = 0.25 × cascade_susceptibility if Stage 3 triggered)**
- NBFC/bank files overdue record with credit bureau (CIBIL-style).
- Simulation terminates this path as **hard default** with `default_type = "bureau_reported"`.
- `financial_dna` distortion applied: affected dimensions shift toward shell_circular signature.

**Cascade contagion across paths**: If >20% of paths enter Stage 2 simultaneously, a **systemic stress flag** is raised. This represents the realistic phenomenon where a borrower's credit events become correlated across lenders (bureau cross-referencing). The systemic flag increases Stage 2 escalation probability by +0.15 for all remaining paths.

### 6.3 Cascade math summary

Cumulative default probability accounting for cascade:

$$
P(\text{default} | \text{cascade}) = P(\text{miss}_1) \cdot \prod_{s=2}^{4} P(\text{escalate to stage}_s | \text{stage}_{s-1})
$$

Without cascade modelling, standard Monte Carlo underestimates true default probability by an estimated **12–28%** for `genuine_struggling` and `shell_circular` profiles based on RBI MSME NPA data patterns.

---

## 7. Stress scenario library — compound & atomic

The prior version had 4 atomic scenarios. This version defines a **structured scenario library** with atomic events, compound events (simultaneous co-occurrence), and cascading events (sequential unfolding).

### 7.1 Atomic scenarios

| Scenario ID | Name | Income Effect | Expense Effect | EMI Effect | Duration |
|---|---|---|---|---|---|
| `S_INC_DROP_20` | Mild income shock | -20% | — | — | 30d |
| `S_INC_DROP_50` | Severe income shock | -50% | — | — | 60d |
| `S_JOB_LOSS` | Job loss | -100% for 45d, +50% ramp back | +8% (stress expenses) | +15% miss prob. | 90d |
| `S_EXP_SURGE_30` | Expense surge | — | +30% essential | — | 30d |
| `S_MEDICAL` | Medical emergency | — | One-time ₹25,000–₹1,00,000 spike | +10% delay | 1 day + recovery |
| `S_RATE_HIKE` | Interest rate hike (RBI) | — | +5% essential bills | EMI floats up 0.5% | Permanent |
| `S_FRAUD` | Account freeze / fraud | -100% income for 14d | Emergency legal expense | +30% miss prob. | 14d |

### 7.2 Compound scenarios (simultaneous co-occurrence)

| Compound ID | Components | Realistic Trigger | Combined Effect |
|---|---|---|---|
| `C_JOB_MEDICAL` | S_JOB_LOSS + S_MEDICAL | Job loss causes health crisis (stress-induced) | Income → 0; large one-time expense; EMI cascade highly likely |
| `C_RATE_STRESS` | S_RATE_HIKE + S_EXP_SURGE_30 | Rate hike coincides with inflation surge | EMI floats up; essential expenses surge; pincer effect on buffer |
| `C_FRAUD_LOSS` | S_FRAUD + S_INC_DROP_20 | Fraudulent transaction causes income disruption | Account freeze + reduced income + legal costs |
| `C_FULL_STRESS` | S_JOB_LOSS + S_MEDICAL + S_RATE_HIKE | Worst-case aggregate scenario | Used for regulatory stress test; maps absolute worst-path outcome |

### 7.3 Cascading scenarios (sequential, time-offset)

These model real-world event chains where the first event causes the second:

| Cascade ID | Sequence | Time Offset | Description |
|---|---|---|---|
| `CA_INCOME_EMI` | S_INC_DROP_20 → EMI Stage 1 cascade | Day 0 → Day 30 | Income drop causes first EMI miss; cascade model takes over |
| `CA_FRAUD_SPIRAL` | S_FRAUD → S_INC_DROP_50 | Day 0 → Day 14 | Account freeze resolves but triggers credit limit cut → effective income drop |
| `CA_LIFESTYLE_DEBT` | Lifestyle inflation trend → S_EXP_SURGE_30 | Gradual over 90d | Detected by `lifestyle_inflation_trend > 0.25`; no external trigger needed |

### 7.4 Scenario composition API

The simulation request accepts a **scenario composition object** rather than a single string:

```json
{
  "scenario": {
    "type": "compound",
    "components": ["S_JOB_LOSS", "S_MEDICAL"],
    "start_day": 0,
    "duration_override": null,
    "custom_params": {
      "medical_expense_amount": 75000
    }
  }
}
```

This replaces the prior single-string `"stress_scenario"` field and allows the Dashboard's What-If Panel to compose any scenario interactively.

---

## 8. Dynamic recovery path modeller

The prior modeller returned a single `"reduce_expense_20pct"` string with no search logic. This version uses **dynamic programming over an intervention graph** to find the minimum-cost path from the current distressed state back to `STABLE` regime within $N$ days.

### 8.1 Intervention action space

Each intervention is a tuple: `(action_id, cost, daily_cashflow_delta, success_probability, side_effects)`.

| Action ID | Description | Daily CF delta | User Cost | Success Prob. | Side Effect |
|---|---|---|---|---|---|
| `A_CUT_DISC_20` | Cut discretionary 20% | +₹400–₹2,000/day | Low | 0.72 | Lifestyle impact |
| `A_CUT_DISC_40` | Cut discretionary 40% | +₹800–₹4,000/day | Medium | 0.55 | High lifestyle impact |
| `A_EMI_RESTRUC` | EMI restructuring (extend tenure) | +EMI_delta/day | Low | 0.80 | Longer debt tenure |
| `A_MICRO_LOAN` | Pre-qualified micro-loan disbursement | +loan_amount (one-time) | Medium (interest) | 0.90 | New debt obligation |
| `A_INC_SIDE` | Activate secondary income (gig/freelance) | +₹5,000–₹15,000/month | Low | 0.45 | Time cost |
| `A_CREDIT_LINE` | Draw on revolving credit line | +limit × 0.5 (one-time) | High (interest) | 0.85 | Credit utilization spike |
| `A_INSURANCE` | Emergency insurance activation | +₹15,000–₹80,000 (one-time) | Pre-paid | 0.95 | Only for medical scenario |

### 8.2 Recovery path search (Dijkstra on state graph)

**State**: `(regime, cash_buffer_days, emi_overdue_count)` — discretized into a finite graph.

**Edge**: Each intervention action is a directed edge from a distressed state to a healthier state, with **cost = (financial cost to user) + (1 - success_probability) × penalty**.

**Objective**: Find the minimum-cost path from the current state to `(STABLE, cash_buffer > 15, emi_overdue = 0)` within $N$ days.

$$
\text{Recovery Plan} = \arg\min_{\pi} \sum_{a \in \pi} \text{cost}(a) \quad \text{s.t.} \quad \text{state}(\pi, N) \in \mathcal{S}_{\text{stable}}
$$

The Dijkstra search runs over the discretized state graph in milliseconds (graph has ~200 nodes for typical horizon). It outputs a **ranked list of intervention sequences**, not just a single action.

### 8.3 Recovery output structure

```
Recovery Plan:
  Step 1 (Day 0):   A_EMI_RESTRUC    → EMI reduced by ₹4,200/month; tenure +8 months
  Step 2 (Day 7):   A_CUT_DISC_20    → Daily discretionary cap applied
  Step 3 (Day 30):  A_INC_SIDE       → Trigger gig-income nudge via Tier 8 agent

Projected recovery trajectory:
  Day 0:  Regime = CRISIS, cash_buffer = 3d
  Day 14: Regime = STRESSED, cash_buffer = 9d
  Day 45: Regime = STABLE, cash_buffer = 18d

Recovery success probability:  0.79
Alternative plan (if Step 3 fails):  A_MICRO_LOAN on Day 35 (bridge)
```

### 8.4 Sensitivity to recovery plan compliance

The modeller also computes recovery probability as a function of **plan compliance rate** (what fraction of recommended actions the user actually follows):

$$
P(\text{recovery} | \text{compliance} = c) = P_{\text{full}} \cdot c + P_{\text{floor}} \cdot (1-c)
$$

where $P_{\text{full}}$ is full-compliance recovery probability and $P_{\text{floor}}$ is spontaneous recovery probability (no action). This allows the LLM narrative (Tier 5) to communicate: *"Following this plan fully gives you a 79% chance of recovery. Even partial compliance (50%) still gives you a 51% chance — significantly better than doing nothing (22%)."*

---

## 9. Bayesian posterior updating

When the simulation is running on a 90-day horizon and a real `twin_updated` event arrives mid-simulation (e.g., a salary credit on day 18), the simulation should not be re-run from scratch. Instead, it **updates the posterior distribution of future cash states** using the observed data as evidence.

### 9.1 Prior → Likelihood → Posterior

For the income distribution, the prior at simulation start is:

$$
I \sim \text{LogNormal}(\mu_0, \sigma_0^2)
$$

calibrated from the twin's `income_stability` feature. When an observed income event $I_{\text{obs}}$ arrives on day $t_{\text{obs}}$, the posterior income distribution for the remaining horizon updates via conjugate Gaussian update (working in log-space):

$$
\mu_{\text{post}} = \frac{\sigma_0^{-2} \mu_0 + \sigma_{\text{obs}}^{-2} \ln(I_{\text{obs}})}{\sigma_0^{-2} + \sigma_{\text{obs}}^{-2}}
$$

$$
\sigma_{\text{post}}^2 = \left(\sigma_0^{-2} + \sigma_{\text{obs}}^{-2}\right)^{-1}
$$

**Effect**: A confirmed salary credit narrows the income uncertainty band. The fan chart visibly tightens around day $t_{\text{obs}}$ and forward. This is surfaced in the dashboard as: *"Your salary was confirmed on Apr 18 — simulation confidence improved."*

### 9.2 Regime posterior update (Bayes factor)

When an observed event is inconsistent with the current regime estimate (e.g., a ₹50,000 inflow during a CRISIS regime), the regime distribution is updated:

$$
P(R_j | \text{event}) = \frac{P(\text{event} | R_j) \cdot P(R_j)}{\sum_i P(\text{event} | R_i) \cdot P(R_i)}
$$

Likelihood $P(\text{event} | R_j)$ is computed from the regime's income distribution. A large positive cash event during CRISIS has high likelihood under R0 and low likelihood under R2, causing the posterior to shift toward STABLE — reducing the active simulation fan width.

---

## 10. Tail risk & fan chart outputs

### 10.1 CVaR — Conditional Value at Risk (Expected Shortfall)

Standard default probability alone is insufficient for regulatory reporting. CVaR captures the **expected loss in the worst-case tail**, which is what RBI's IMA and Basel III stress testing frameworks require.

At confidence level $\alpha$ (typically 95% or 99%):

$$
\text{VaR}_\alpha = \inf\{ x : P(L > x) \leq 1 - \alpha \}
$$

$$
\text{CVaR}_\alpha = \mathbb{E}[L \mid L > \text{VaR}_\alpha] = \frac{1}{N(1-\alpha)} \sum_{k : L^{(k)} > \text{VaR}_\alpha} L^{(k)}
$$

where $L^{(k)} = C_0 - \min_t C_t^{(k)}$ (maximum drawdown on path $k$).

Both VaR₉₅ and CVaR₉₅ are exposed as primary output metrics. CVaR is the more conservative and more informative metric: it tells the lender *how bad the bad scenarios are*, not just *how many paths fail*.

### 10.2 Full percentile output for fan chart

| Metric | Description | Dashboard rendering |
|---|---|---|
| `p10_path` | Worst-case decile daily cash series | Crimson 1px dashed, 30% opacity |
| `p25_path` | Poor-case quartile daily cash series | Amber 1px, 40% opacity |
| `p50_path` | Median (base case) daily cash series | White 2px, 80% opacity |
| `p75_path` | Good-case quartile daily cash series | Acid 1px, 40% opacity |
| `p90_path` | Best-case decile daily cash series | Acid 1px dashed, 30% opacity |
| `fan_fill` | Area between P25–P75 | Acid at 4% opacity |
| `today_marker` | Current day vertical notch | Acid dashed line |

### 10.3 EMI stress score (revised)

The prior EMI stress score was a simple fraction of missed EMIs. The revised metric weights each miss by its cascade stage:

$$
\text{EMI Stress Score} = \frac{1}{N} \sum_{k=1}^{N} \frac{\sum_{t} \text{stage}(k,t)}{4 \cdot M_{\text{total}}}
$$

where `stage(k,t)` ∈ {0,1,2,3,4} is the cascade stage reached on path $k$ at step $t$, and $M_{\text{total}}$ is total EMI due-dates in the horizon. A score of 1.0 means all paths reached hard default (Stage 4); 0.25 means average Stage 1 (first miss only).

### 10.4 Net worth delta with uncertainty bounds

The prior model returned a point estimate. The revised output includes the full distribution:

$$
\Delta W_{90d} \sim \left\{ \text{mean}: \bar{\Delta W},\ p10: \Delta W_{10},\ p90: \Delta W_{90} \right\}
$$

The uncertainty band $[\Delta W_{10}, \Delta W_{90}]$ is surfaced in the LLM narrative (Tier 5) as: *"Your projected net position 90 days from now ranges from -₹38,000 (poor scenario) to +₹12,000 (good scenario), with a median of -₹9,400."*

---

## 11. Counterfactual reasoning engine

This is a new capability with no equivalent in the prior Tier 6. It powers the Tier 10 audit dashboard's **"What would have happened?"** panel and provides genuine explanatory value to both users and regulators.

### 11.1 Counterfactual definition

A counterfactual simulation answers: *"If intervention $A$ had been applied at time $t_0 - \delta$, what would the user's current state be?"*

Formally, define:
- $\mathcal{H}_{t_0}$: the actual historical twin state sequence up to now
- $\mathcal{H}^{(A)}_{t_0}$: the counterfactual history where action $A$ was applied at $t_0 - \delta$
- $\Delta = \text{twin\_state}(t_0) - \text{twin\_state}^{(A)}(t_0)$: the counterfactual gap

The counterfactual engine re-runs the Monte Carlo simulator from $t_0 - \delta$ using the **actual historical path up to that point** (taken from the twin's immutable version history) but applying action $A$'s cash flow delta from that point forward.

### 11.2 Standard counterfactual scenarios

| Counterfactual ID | Question answered | Look-back window |
|---|---|---|
| `CF_EARLIER_RESTRUC` | What if EMI restructuring had been offered 30 days ago? | 30d |
| `CF_MICRO_LOAN_15` | What if a ₹20,000 micro-loan had been disbursed 15 days ago? | 15d |
| `CF_DISC_CUT_60` | What if discretionary cut had started 60 days ago? | 60d |
| `CF_NO_INTERVENTION` | What would have happened without any of the interventions that fired? | Full history |

### 11.3 Counterfactual output

```
Counterfactual: "If EMI restructuring had fired on Mar 12 (30 days ago):"
  Actual state today:     CRISIS, cash_buffer = 3d, risk_score = 0.71
  Counterfactual state:   STRESSED, cash_buffer = 11d, risk_score = 0.44
  Delta:                  cash_buffer +8 days, risk_score -0.27
  Intervention value:     ₹8,400 saved in penalty interest (Stage 1 cascade avoided)
  Probability of today's crisis having been avoided: 68%
```

This output is stored in `simulation.counterfactual_log` and feeds directly into the **Tier 10 Regulatory Audit Report** as evidence of the intervention agent's value.

---

## 12. Architectural decisions

### 12.1 Technology choices

| Layer / Use-case | Chosen Tech | Rejected Alternative | Rationale |
|---|---|---|---|
| **Core Simulation** | Python + NumPy (vectorized `[N×H]` matrices) | Pure LLM-based simulation | Full statistical rigor, reproducibility, and vectorized speed at 1000+ paths. |
| **Quasi-Monte Carlo** | `scipy.stats.qmc.Sobol` + antithetic variates | Standard `numpy.random` only | 6–10× variance reduction at zero additional cost; 500 paths reach 3000-run precision. |
| **Correlation Structure** | Cholesky decomposition of Σ via `numpy.linalg.cholesky` | Independent draws | Correct joint distribution for income/expense co-shocks; eliminates bias in tail estimates. |
| **Regime Model** | Calibrated transition matrix + emission distribution | Full HMM with Baum-Welch | Sufficient for 3-state discrete regime; avoids overfitting on short financial histories. |
| **GARCH Variance** | Iterative GARCH(1,1) per path step | Static σ from feature vector | Captures volatility clustering; prevents overconfident narrow fans during stressed periods. |
| **Recovery Path** | Dijkstra on discretized state graph | Brute-force enumeration | O(V log V) vs O(2ⁿ); handles 200-node graph in <5ms; allows ranked alternatives. |
| **Bayesian Update** | Conjugate Gaussian posterior (log-space) | Full MCMC | Conjugate update is O(1) per event; MCMC is orders of magnitude too slow for real-time. |
| **Counterfactual** | Re-simulation from twin version history + action delta | Separate counterfactual model | Reuses existing Monte Carlo engine; twin's immutable history provides exact replay point. |
| **Storage** | Redis (`sim:{gstin}:{sim_id}` keys) + Parquet archive | Only in-memory | Parquet for audit compliance; Redis for real-time dashboard queries. |
| **Output Bus** | Redis Pub/Sub (`simulation_completed` event) | Polling | Twin and Tier 8 agent subscribe to simulation events; no polling overhead. |

### 12.2 Pipeline structure

```
src/simulation/
    engine.py               # Core Monte Carlo runner (Sobol + antithetic)
    garch.py                # GARCH(1,1) variance evolution
    correlation.py          # Cholesky decomposition + correlated shock generation
    regime.py               # Regime HMM transition model
    cascade.py              # EMI cascade & contagion model
    scenario_library.py     # Atomic + compound + cascading scenario definitions
    recovery.py             # Dijkstra recovery path modeller
    bayesian_updater.py     # Posterior update on mid-simulation twin events
    counterfactual.py       # Counterfactual reasoning engine
    tail_risk.py            # CVaR, VaR, fan chart percentile extraction
    ews.py                  # Early Warning Score computation
    output_emitter.py       # Redis event emission + twin trajectory update
```

**Execution budget**:
- Target: full 1000-path × 90-day simulation in **<800ms** on a single CPU core
- Sobol + antithetic + vectorized NumPy achieves this without GPU
- GARCH update: O(N×H) = 90,000 scalar operations ≈ 2ms
- Cholesky draw: O(N×H×4) ≈ 8ms
- Cascade evaluation: O(N×H) per stage ≈ 15ms
- Recovery Dijkstra: <5ms
- Total estimated: ~300–500ms on CPU; well within 800ms budget

### 12.3 Simulation output → Digital Twin feedback

On `simulation_completed`, the engine emits:

```json
{
  "event": "simulation_completed",
  "gstin": "...",
  "simulation_id": "...",
  "twin_update": {
    "predicted_risk_trajectory": [0.41, 0.43, 0.47, ...],
    "ews_14d": 0.38,
    "regime_distribution": {"STABLE": 0.12, "STRESSED": 0.61, "CRISIS": 0.27},
    "recovery_plan_active": true,
    "fan_chart_cache_key": "sim:fan:29ABCDE..."
  }
}
```

The Digital Twin (Tier 4) subscribes to this event and updates its `predicted_risk_trajectory` field, making simulation outputs a first-class part of the twin state — available to LLM reasoning (Tier 5), the Intervention Agent (Tier 8), and the Audit Dashboard (Tier 10).

---

## 13. Target variables & real-world transition strategy

### 13.1 Full output metric surface

| Metric | Type | Description | Feeds |
|---|---|---|---|
| `default_probability` | float [0,1] | % paths ending in hard default | Tier 7 credit engine, Tier 8 agent |
| `cvar_95` | float (₹) | Expected loss in worst 5% paths | Tier 7 regulatory reporting |
| `var_95` | float (₹) | Max loss at 95th confidence | Tier 7, Tier 10 audit |
| `ews_7d / 14d / 30d` | float [0,1] | Early warning scores at 3 horizons | Tier 8 trigger |
| `liquidity_crash_days` | {mean, p10, p90} | Days until cash hits floor | Tier 8 nudge timing |
| `emi_stress_score` | float [0,1] | Cascade-weighted EMI risk | Tier 7, Tier 8 |
| `net_worth_delta_90d` | {mean, p10, p90} | Projected wealth change | LLM narrative |
| `fan_chart` | {p10, p25, p50, p75, p90}[H] | Daily percentile cash paths | Tier 10 dashboard |
| `regime_distribution` | {R0, R1, R2} at each horizon | Regime probability evolution | LLM narrative |
| `recovery_plan` | ordered action list | Minimum-cost recovery sequence | Tier 8 intervention |
| `counterfactual_log` | list of CF analyses | Historical intervention value | Tier 10 audit |
| `simulation_id` | string | Reproducible audit key | Tier 10 export |

### 13.2 Real-world transition

- **Development**: Synthetic twin states + synthetic feature vectors from `Data.md` pipeline.
- **Staging**: Live AA-consented data via Sahamati/Setu; GARCH parameters re-calibrated on real income/expense time series; correlation matrix Σ updated from real user cohort data.
- **Production**: Remove `generate_proxy_labels`; swap seeded income distributions with live Kalman-filtered state estimates from the twin's 90-day event history; GARCH parameters updated nightly via MLE re-estimation.
- **Regulatory audit**: All simulation runs archived to Parquet with `(gstin, sim_id, seed, params)` tuple. Any run is fully reproducible. Audit report (Tier 10) pulls simulation artifacts directly from this archive.

---

## 14. Where to get the real-data (licensed sources)

| Component | Purpose | Source |
|---|---|---|
| Stress Testing Parameters | RBI-prescribed shock scenarios for MSME lending | RBI Master Circular on Stress Testing & ICAAP guidelines (2024 update) |
| CVaR / Basel III methodology | Regulatory tail risk computation | Basel Committee Working Paper No. 306 (Expected Shortfall & IMA) |
| Regime-Switching References | HMM-style financial state modelling | Hamilton (1989) original HMM paper + RBI guidance on Model Risk Management |
| GARCH Methodology | Time-varying volatility in financial series | Bollerslev (1986) GARCH paper; `arch` Python library documentation |
| Copula & Correlation | Joint income-expense shock modelling | Sklar's Theorem; `scipy.stats` copula implementations |
| Recovery Path Modelling | Borrower-friendly intervention logic | RBI Fair Practices Code + CRISIL MSME recovery rate studies |
| Quasi-Monte Carlo | Variance reduction methodology | Sobol (1967); `scipy.stats.qmc` documentation |
| Counterfactual Methods | Causal inference for intervention evaluation | Pearl (2009) "Causality"; Rubin potential outcomes framework |
| Real Twin Data | Live financial state for simulation | Sahamati Account Aggregator Framework + Setu/Cashfree AA gateways |
| EMI Cascade Patterns | NPA escalation rates in MSME lending | RBI Financial Stability Report (latest); SIDBI MSME Pulse Report |

---

## 15. Mock API-JSON schemas & simulation flow

### 15.1 Simulation request (POST /simulation/run)

```json
{
  "gstin": "29ABCDE1234F1Z5",
  "twin_snapshot": {
    "income_stability": 0.78,
    "spending_volatility": 0.32,
    "liquidity_health": "MEDIUM",
    "risk_score": 0.41,
    "cash_buffer_days": 14,
    "emi_monthly": 28500,
    "emi_overdue_count": 0,
    "cash_balance_current": 42000,
    "cascade_susceptibility": 0.45,
    "persona": "genuine_struggling",
    "financial_dna": [0.72, 0.45, ...]
  },
  "horizon_days": null,
  "num_simulations": 1000,
  "scenario": {
    "type": "compound",
    "components": ["S_INC_DROP_20", "S_MEDICAL"],
    "start_day": 0,
    "custom_params": { "medical_expense_amount": 60000 }
  },
  "variance_reduction": {
    "sobol": true,
    "antithetic": true
  },
  "run_counterfactual": true,
  "counterfactual_lookback_days": 30,
  "seed": null
}
```

### 15.2 Simulation response

```json
{
  "gstin": "29ABCDE1234F1Z5",
  "simulation_id": "sim_20260411_152301_a7f3",
  "seed": 8834712,
  "horizon_days": 90,
  "num_paths": 1000,
  "variance_reduction_applied": ["sobol_512", "antithetic"],
  "effective_precision_equivalent": 4200,

  "default_probability": 0.31,
  "var_95": -87400,
  "cvar_95": -142800,

  "ews": {
    "ews_7d": 0.19,
    "ews_14d": 0.38,
    "ews_30d": 0.54,
    "severity": "ORANGE",
    "trigger_recommendation": "EMI_AT_RISK_ALERT + MICRO_LOAN_PRE_QUALIFY"
  },

  "liquidity_crash_days": {
    "mean": 24,
    "p10": 9,
    "p50": 22,
    "p90": 51
  },

  "emi_stress_score": 0.43,

  "net_worth_delta_90d": {
    "mean": -22800,
    "p10": -68400,
    "p50": -18200,
    "p90": 4100
  },

  "regime_distribution_at_90d": {
    "STABLE": 0.09,
    "STRESSED": 0.52,
    "CRISIS": 0.39
  },

  "fan_chart": {
    "horizon_days": 90,
    "p10": [42000, 38200, 34100, ...],
    "p25": [42000, 40100, 38400, ...],
    "p50": [42000, 41800, 41200, ...],
    "p75": [42000, 43200, 44100, ...],
    "p90": [42000, 44800, 47200, ...]
  },

  "cascade_analysis": {
    "paths_reaching_stage1": 0.28,
    "paths_reaching_stage2": 0.14,
    "paths_reaching_stage3": 0.06,
    "paths_reaching_stage4": 0.02,
    "systemic_stress_flag": false
  },

  "recovery_plan": {
    "plan_id": "rp_20260411_a7f3",
    "steps": [
      {
        "step": 1,
        "day": 0,
        "action": "A_EMI_RESTRUC",
        "description": "Extend tenure by 8 months — EMI drops by ₹4,200/month",
        "daily_cf_delta": 140,
        "success_probability": 0.80
      },
      {
        "step": 2,
        "day": 7,
        "action": "A_CUT_DISC_20",
        "description": "20% discretionary cap applied",
        "daily_cf_delta": 800,
        "success_probability": 0.72
      },
      {
        "step": 3,
        "day": 30,
        "action": "A_INC_SIDE",
        "description": "Gig-income nudge pushed via Tier 8 agent",
        "daily_cf_delta": 500,
        "success_probability": 0.45
      }
    ],
    "projected_regime_at_45d": "STABLE",
    "recovery_probability_full_compliance": 0.79,
    "recovery_probability_50pct_compliance": 0.51,
    "recovery_probability_no_action": 0.22,
    "alternative_step3": {
      "action": "A_MICRO_LOAN",
      "loan_amount": 20000,
      "trigger_day": 35
    }
  },

  "counterfactual": {
    "scenario": "CF_EARLIER_RESTRUC",
    "lookback_days": 30,
    "actual_state_today": {
      "risk_score": 0.41,
      "cash_buffer_days": 14,
      "regime": "STRESSED"
    },
    "counterfactual_state_today": {
      "risk_score": 0.27,
      "cash_buffer_days": 21,
      "regime": "STABLE"
    },
    "value_of_earlier_intervention": {
      "penalty_interest_avoided": 6200,
      "cash_buffer_gained_days": 7,
      "risk_score_improvement": 0.14,
      "crisis_probability_avoided": 0.21
    }
  },

  "twin_update_emitted": true,
  "timestamp": "2026-04-11T15:23:04Z"
}
```

### 15.3 EWS streaming endpoint (GET /simulation/ews/{gstin})

```json
{
  "gstin": "29ABCDE1234F1Z5",
  "computed_at": "2026-04-11T15:23:04Z",
  "ews_7d": 0.19,
  "ews_14d": 0.38,
  "ews_30d": 0.54,
  "severity": "ORANGE",
  "leading_indicators": [
    "Spending volatility up 18% vs 30d baseline",
    "2 debit failures in last 7 days",
    "Cash buffer declining at ₹820/day average"
  ],
  "simulation_id_source": "sim_20260411_152301_a7f3"
}
```

### 15.4 Fan chart cache fetch (GET /simulation/fan/{gstin})

```json
{
  "gstin": "29ABCDE1234F1Z5",
  "simulation_id": "sim_20260411_152301_a7f3",
  "horizon_days": 90,
  "today_index": 0,
  "currency": "INR",
  "fan_chart": {
    "p10": [...],
    "p25": [...],
    "p50": [...],
    "p75": [...],
    "p90": [...]
  },
  "regime_trace": ["STRESSED", "STRESSED", "CRISIS", ...],
  "cascade_event_markers": [
    { "day": 31, "event": "Stage1_cascade", "path_fraction": 0.28 }
  ]
}
```

---

## Implementation note

```
# Risk Simulation Engine v2 =
# Correlated Monte Carlo × Regime-Switching × EMI Cascade × Recovery Dijkstra × Bayesian Updating
# Not a predictor. A living, self-correcting probabilistic mirror of the user's financial future.
```

**What changed from v1:**

| Dimension | v1 (prior) | v2 (this document) |
|---|---|---|
| Shock model | Independent lognormals | Cholesky-correlated 4-variate draws |
| Volatility | Static σ | GARCH(1,1) time-varying per step |
| Scenarios | 4 atomic | 7 atomic + 4 compound + 3 cascading + composer API |
| Tail risk | Default probability only | Default probability + VaR₉₅ + CVaR₉₅ |
| EMI model | Independent Bernoulli | 4-stage cascade with contagion |
| Regime | None | 3-state HMM with calibrated transition matrix |
| Recovery | Single static string | Dijkstra graph search over intervention space |
| Precision | 1000 standard Monte Carlo | 500-path Sobol+antithetic ≡ ~4000+ standard |
| Mid-sim updates | None | Conjugate Bayesian posterior update |
| Counterfactual | None | Full causal counterfactual from twin version history |
| Early warning | None | EWS at 7d/14d/30d with severity band + agent trigger |
| Twin feedback | None | `simulation_completed` event updates twin trajectory |
