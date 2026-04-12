# Tier 9 Architecture - Vigilance, Anomaly, and Deception Detection

## Objective
Tier 9 detects fraud rings, social engineering attempts, synthetic/bot behavior, hidden stress, underreporting, and identity shifts. It produces a composite deception signal and structured risk outputs for downstream action.

## Implementation Scope
- Graph-based fraud ring detection with temporal consistency.
- Scam analysis from message text and sender metadata.
- Bot/mule heuristics from timing, network, and throughput signatures.
- Statistical anomaly modules for stress, income underreporting, and identity drift.
- Aggregated risk and deception scoring with event emission.

## Core Modules
- `src/vigilance/schemas.py`
- `src/vigilance/fraud_ring.py`
- `src/vigilance/scam_detector.py`
- `src/vigilance/bot_detector.py`
- `src/vigilance/anomaly_detector.py`
- `src/vigilance/tier9.py`

## Data Inputs
- Tier 3 behavioural feature vectors.
- Optional UPI and EWB transaction event batches.
- Optional SMS or voice-transcript text samples.
- Declared and cohort income statistics.

## Processing Layers
1. Fraud Graph Layer
- Builds temporal directed multigraph.
- Computes SCCs and cycle evidence with temporal monotonicity checks.
- Calculates PageRank and shell-hub indicators.

2. Social Engineering Layer
- Scores urgency, authority impersonation, and OTP phishing patterns.
- Combines signals via Bayesian update into scam probability.

3. Bot and Mule Layer
- Detects improbable interval regularity.
- Measures hub-spoke concentration and mule DNA signatures.

4. Behavioural Anomaly Layer
- Computes logistic stress confidence.
- Scores progressive underreporting relative to cohorts.
- Measures identity shift using JS divergence and behavioural deltas.

5. Aggregation and Emission Layer
- Aggregates module-level risk to overall vigilance level.
- Computes composite deception score.
- Caches results and emits vigilance events.

## Contracts and Guarantees
- `Tier9Result` is canonical output contract with all module payloads.
- Risk levels use standardized enum bands.
- Deception score range is bounded to [0, 1].

## Redis and Storage Interfaces
- Result cache: `tier9:result:{user_id}`
- Event stream: `stream:vigilance_events`
- API summary endpoint uses cached result or twin fallback fields.

## Failure and Recovery Behavior
- Missing optional channels degrade gracefully.
- Empty event sets produce low-signal default outputs rather than crashes.
- Module-level failures are contained by orchestrator logic.

## Outputs
- Detailed vigilance artifact bundle with module evidence.
- Lightweight summary fields for dashboards.
- Fraud/scam/bot flags consumable by upper-tier decision layers.

## Dependency Edges
- Upstream: Tier 3 features, optional Tier 1/2 derived raw event slices.
- Downstream: Tier 4 state annotations, Tier 8 intervention logic, Tier 10 reporting.

## What Tier 9 Enables
- Intent-aware risk beyond pure credit behavior.
- Early interception of scam and laundering patterns.
- Explainable vigilance posture for analysts and audit.
