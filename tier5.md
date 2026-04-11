# Tier 5 — Full Architecture Plan

## The Core Problem Others Get Wrong

Most people implement Tier 5 as a single prompt: "here is the user's data, write a narrative." That produces fluent text with no reasoning traceability, no statistical grounding, and no integration back into the twin. The real challenge here is threefold — the LLM must be a reasoner (not just a writer), the Contradiction Detector must be statistically rigorous (not just a keyword check), and the Interrogation Mode must be a proper state machine that modifies the twin state as its output, not just collects answers.

---

## Module 1 — Context Assembly Engine

Before a single token goes to the LLM, a dedicated assembly layer constructs a ranked, token-budgeted context object. This is critical because naively dumping all twin state, all features, and all simulation outputs will exceed any model's context window and produce unfocused reasoning.

**What gets assembled and in what priority order:**

**Priority 1 — The Delta Packet (most recent changes).** This is not the current twin state alone, it's the diff between the current version and the prior version. From Tier 4's immutable snapshot history, compute: which features moved by more than 1 standard deviation, which regime changed, which new event types appeared in the last 48 hours. This delta is the most information-dense signal and always goes in first.

**Priority 2 — The Simulation Verdict from Tier 6.** The EWS severity band, default probability, CVaR, the active recovery plan steps, and the regime distribution at 90 days. The LLM needs to know the probabilistic future to reason about whether the current behavior pattern is trending toward or away from it.

**Priority 3 — The top 5 ranked behavioral features from Tier 3**, sorted by their deviation from the peer cohort z-score. Not all 18 features — just the 5 most anomalous ones relative to cohort. This focuses the LLM on what actually matters.

**Priority 4 — Last 15 typed events from Tier 2** with their merchant categories. The LLM needs concrete transaction evidence to cite in its reasoning trace, not just aggregate statistics.

**Priority 5 — Declared income from onboarding** and the Contradiction Detector's output (described in Module 3), if a flag exists.

**Token budget enforcement:** The context object is assembled until it hits 70% of the model's context window. The remaining 30% is reserved for the output schema and reasoning trace. If a lower-priority item doesn't fit, it's summarized to a single line rather than dropped entirely.

---

## Module 2 — Structured CoT Architecture

Every LLM call in Tier 5 outputs a rigid JSON schema enforced via structured output / GBNF grammar constraints (the readme already references phi-3 mini with GBNF — this is the right call). Free-form text is never accepted from the model directly; it is always embedded inside a structured field.

The reasoning trace follows a fixed 6-step chain. Each step is a labeled JSON key:

**[OBSERVE]** — The model lists exactly which signals it sees, with numeric values. No interpretation yet.
> Example: "EMI burden ratio: 0.58 (above critical threshold 0.55). Spending volatility: 0.41 (up from 0.29 thirty days ago). Tier 6 EWS_14d: 0.38 (ORANGE severity)."

**[CLASSIFY]** — The model assigns the user's current financial situation to one of 8 canonical situation types:
- `STABLE_IMPROVING`
- `STABLE_FLAT`
- `STABLE_DEGRADING`
- `STRESSED_RECOVERABLE`
- `STRESSED_CRITICAL`
- `CRISIS_ACUTE`
- `CRISIS_SYSTEMIC`
- `ANOMALOUS_UNCLASSIFIABLE`

This classification is a structured enum field, not free text. It gates which narrative template and concern flag set is applicable.

**[HYPOTHESIZE]** — The model generates up to 3 competing hypotheses explaining the pattern. Each hypothesis has an ID, a natural language statement, and a prior probability.
> Example: "H1: User is experiencing temporary salary delay (P=0.45). H2: User has taken on new undisclosed EMI (P=0.35). H3: Lifestyle inflation is eroding buffer (P=0.20)."

**[TEST]** — Each hypothesis is tested against available evidence. The model cites specific Tier 2 events or Tier 3 features as confirming or disconfirming evidence. This is the most important step for auditability. The conclusion updates each hypothesis's posterior probability.

**[SYNTHESIZE]** — The model generates the four primary outputs (risk narrative, behavioral change summary, intent signals, concern flags) conditioned on the highest-posterior hypothesis. Each output has a `source_hypothesis` field linking it to the [TEST] step.

**[CONFIDENCE]** — A calibrated confidence score (0.0–1.0) for the overall reasoning chain, plus a flag for whether Interrogation Mode should be triggered (triggered when max hypothesis posterior < 0.55, meaning genuine ambiguity exists).

This 6-step structure means every output in the system is fully traceable — Tier 10's audit report can display the exact reasoning chain that produced a credit decision or intervention.

---

## Module 3 — Four Primary Outputs

**Risk Narrative** follows brand.md §16.2 exactly — 2 to 4 sentences, present tense verdict first, causal factor second, trajectory third, optional action fourth. The model is prompted with the brand voice guide literally included in the system prompt. The narrative is the only output that reaches the user-facing dashboard directly.

**Behavioral Change Summary** is structured as a typed diff. It lists: features that improved (green, acid color), features that degraded (red, crimson color), features that are stable (neutral), and the net direction verdict. This feeds the twin's `delta_summary` field in Tier 4 versioning and is also surfaced in the Tier 10 timeline.

**Intent Signals** are forward-looking behavioral predictions derived from the [TEST] step. Examples:
- `LARGE_PURCHASE_IMMINENT` — triggered when discretionary ratio spikes before month-end without a salary event
- `NEW_CREDIT_SEEKING` — triggered when multiple P2M merchant category shifts toward loan-related merchants appear
- `INCOME_TRANSITION` — triggered when salary-day pattern breaks

Each intent signal has a probability, a 30-day expiry, and a Tier 8 trigger recommendation.

**Concern Flags** are structured risk assertions with four fields each: `flag_type` (enum), `severity` (LOW/MEDIUM/HIGH/CRITICAL), `evidence_citations` (list of specific Tier 2 event IDs or Tier 3 feature values), and `recommended_action`. Unlike the narrative, concern flags are machine-readable and feed directly into Tier 7 credit decisions and Tier 8 intervention triggers. Maximum 5 flags per run — ranking by severity × confidence.

---

## Module 4 — Contradiction Detector

This is a fully statistical module that runs before the LLM call and feeds its output into Priority 5 of the context assembly.

### Three-Layer Detection

**Layer 1 — Monthly Income Z-Test.**
From Tier 3's 90-day income window, extract month-by-month observed income totals (INCOME-typed events only). Compute observed mean μ_obs and standard deviation σ_obs. The null hypothesis is that declared income is consistent with the observed distribution.

```
z = (I_declared - μ_obs) / (σ_obs / √N_months)
```

Flag if |z| > 2.0 (95% confidence). Direction matters: z > 2.0 means over-reporting (loan fraud risk signal); z < -2.0 means under-reporting (informal income or tax signal). The z-score and direction both pass to the LLM as structured fields.

For gig workers with high income volatility (`income_stability_score` < 0.5 from Tier 3), the threshold is relaxed to |z| > 2.5 to reduce false positive rate — the higher volatility is legitimately expected.

**Layer 2 — Income Source Consistency.**
The UPI logs from Tier 2 provide counterparty VPA information. A genuine salaried income should come from a consistent P2M employer VPA or NEFT bank transfer with consistent timing (within ±3 days of declared salary date). Check: what fraction of total observed INCOME events come from the expected source type? If > 40% of income arrives from P2P transfers (friend VPAs, family transfers), this is a mismatch flag — declared "salary" is partly informal transfers.

**Layer 3 — Lifestyle Consistency Index.**
This cross-checks declared income against inferred lifestyle tier derived from spending patterns. Compute the ratio:

```
LCI = Avg Monthly Discretionary Spend / Declared Monthly Income
```

For a genuinely declared income, LCI should fall between 0.10 and 0.35 (10–35% discretionary of income is normal).
- LCI > 0.45 with a high declared income → possible over-reporting
- LCI < 0.05 with a low declared income and high cash dependency index → possible under-reporting

### Contradiction Detector Output (JSON)

```json
{
  "contradiction_detected": true,
  "z_score": 0.0,
  "direction": "OVER_REPORTED | UNDER_REPORTED | CONSISTENT",
  "layer1_flag": false,
  "layer2_flag": false,
  "layer3_lci": 0.0,
  "layer3_flag": false,
  "layers_triggered": 0,
  "severity": "LOW | MEDIUM | HIGH",
  "declared_income": 0.0,
  "observed_mean_income": 0.0,
  "confidence": 0.0
}
```

When `layers_triggered >= 2`, the Interrogation Mode is automatically scheduled with income clarification as Q1.

---

## Module 5 — Conversational Interrogation Mode

This is a proper state machine, not a chatbot loop. It has defined states, defined transitions, and every terminal state produces a twin state update.

### State Machine

```
IDLE → SIGNAL_ANALYSIS → QUESTION_RANKING → Q1_ASKED →
Q1_ANSWERED → Q2_ASKED → ... → Q5_ANSWERED →
ANSWER_PARSING → TWIN_UPDATE → RESIMULATION → COMPLETE
```

### Trigger Conditions (any one is sufficient)

- Max hypothesis posterior in Module 2's [SYNTHESIZE] step < 0.55
- Contradiction Detector `layers_triggered >= 2`
- `EWS_14d > 0.45` AND `anomaly_flag = true` (Tier 3)
- `merchant_category_shift_count > 3` in last 30 days (Tier 3) — sudden behavioral shift
- First-run for a `new_to_credit` profile (always interrogate to build baseline)

### Question Ranking Algorithm

Before Q1 is asked, all ambiguous signals are ranked by an Uncertainty Reduction Score (URS):

```
URS(signal) = severity(signal) × ambiguity(signal) × twin_impact(signal)
```

Where:
- `severity` comes from Tier 3 feature importance rankings (Schema.md §8)
- `ambiguity` is 1 minus the maximum hypothesis posterior that explains this signal
- `twin_impact` is how much the twin's `risk_score` would change if the signal resolved favorably vs unfavorably

Top 5 signals by URS become the basis for the 5 questions.

### Question Generation

Questions are LLM-generated but template-constrained. The LLM is given the top signal and a question template type, and fills in the specific values.

| Template | Text |
|---|---|
| `INCOME_CLARIFY` | "We noticed your observed income of ₹{observed_mean} differs from your declared ₹{declared}. Do you have additional income sources not reflected in your bank transactions?" |
| `EXPENSE_EXPLAIN` | "Your spending in {category} increased by {pct}% in the last 30 days versus your 90-day baseline. Is this a one-time event or an ongoing change?" |
| `FUTURE_COMMITMENT` | "Our simulation shows an EMI stress event is likely in {N} days. Are you planning any new financial commitments in the next 60 days?" |
| `ASSET_DISCLOSURE` | "Do you have liquid assets (FDs, savings in other accounts) not captured in the connected accounts? This may improve your credit assessment." |
| `BEHAVIORAL_INTENT` | "Your spending pattern suggests {intent_signal}. Can you share more context about this change?" |

Questions are adaptive — Q2 is conditioned on Q1's answer. If Q1 reveals an additional income source, Q2 immediately pivots to ask for its estimated amount and consistency, rather than following the pre-ranked list blindly.

### Answer Parsing

Each answer goes through a lightweight structured extraction step (separate LLM call with a narrow extraction prompt, or regex for numeric values). Extracted fields:

- Numeric amounts (₹ values mentioned)
- Time references (dates, frequencies)
- Boolean confirmations
- New entity mentions (new employer, new loan, new account)

### Twin State Integration

Parsed answers directly patch specific twin fields via the Tier 4 update lifecycle. This is a hard state update, not a soft "consider this information":

| Answer | Twin Update |
|---|---|
| Confirmed additional income source | Update `monthly_income_proxy`, re-run Tier 3 features |
| Confirmed upcoming large expense | Inject a future stress event into Tier 6 simulation |
| Confirmed new EMI | Add to `recurring_schedules` stream, update `emi_burden_ratio` |
| Confirmed liquid asset | Update `cash_buffer_days` calculation baseline |

After all 5 questions, Tier 6 is re-triggered with the updated twin state. The simulation delta (before vs after interrogation) is stored as `interrogation_value_score` — how much the uncertainty bands narrowed. This feeds into Tier 10's audit log as evidence that the interrogation was productive.

**Non-compliance handling:** If the user abandons the interview after Q2, the answered questions are still integrated. The unanswered signals remain as HIGH-severity concern flags with the label `UNRESOLVED_AMBIGUITY` — they don't disappear, they persist until resolved.

---

## Module 6 — Integration Points with All Other Tiers

### Receives From

| Tier | Data |
|---|---|
| Tier 2 | Last N typed events with merchant categories and anomaly flags |
| Tier 3 | All 18 behavioral features, peer cohort z-scores, EMA windows |
| Tier 4 | Current twin state, version history for delta computation, declared income from onboarding |
| Tier 6 | Default probability, CVaR, EWS at 3 horizons, fan chart percentiles, recovery plan, counterfactual analysis, regime distribution |

### Emits To

| Tier | Data |
|---|---|
| Tier 4 | Risk narrative → `twin.last_narrative`; concern flags → `twin.active_flags`; intent signals → `twin.intent_signals`; full CoT trace → `twin.last_cot_trace` |
| Tier 6 | Interrogation answers that update twin state trigger a full re-simulation |
| Tier 7 | Concern flags (`INCOME_CONTRADICTION`, `HIGH_CASCADE_RISK`) are direct inputs to credit decisioning |
| Tier 8 | Intent signals (`LARGE_PURCHASE_IMMINENT`, `INCOME_TRANSITION`) trigger early intervention before threshold would normally fire |
| Tier 10 | Full CoT trace + contradiction detector output + interrogation transcript stored immutably for regulatory audit |

### Redis Events Emitted

| Event | Description |
|---|---|
| `reasoning_completed` | Contains narrative, flags, intents, CoT trace; triggers Tier 8 evaluation |
| `interrogation_started` | Pushes first question to UI |
| `interrogation_completed` | Triggers twin update + re-simulation |
| `contradiction_flagged` | High-priority event consumed by Tier 7 and Tier 9 |

---

## What Makes This Architecture Genuinely Advanced

The key insight is that Tier 5 is not a reporting layer — it is a reasoning agent that closes the loop. The CoT trace is not decoration; it is the machine-readable justification that every downstream credit decision, intervention, and audit entry is pinned to. The Contradiction Detector's three-layer statistical approach means the LLM is never asked to detect income fraud through intuition — the math already flagged it; the LLM's job is to reason about why and generate the right question to resolve it. And the Interrogation Mode's state machine ensures that ambiguity has a defined resolution path, not an open-ended chat loop that could go anywhere.

The other key difference from a naive implementation: **the LLM never updates the twin state by itself.** It produces a structured output that the twin update service validates and applies. This separation keeps the twin's integrity intact — the LLM is an advisor, not an actor.
