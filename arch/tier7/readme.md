# Tier 7 Architecture - Credit Scoring, Explainability, and Recalibration

## Objective
Tier 7 computes asynchronous credit decisions from behavioural features, with dual-model routing, SHAP explainability, rule traces, and periodic recalibration.

## Implementation Scope
- Score-request saga worker over Redis streams.
- Dual XGBoost inference with thin-file routing.
- Behavioural trajectory override integration.
- SHAP top-driver and waterfall explanation generation.
- 24-hour recalibration sweeps.

## Core Modules
- `src/credit/credit_scorer.py`
- `src/credit/shap_explainer.py`
- `src/credit/scoring_worker.py`
- `src/credit/recalibration.py`
- `src/credit/schemas.py`
- `src/credit/credit_trainer.py`
- `src/scoring/trainer.py`

## Data Inputs
- Tier 3 behavioural feature vectors from parquet/cache.
- Tier 4 twin risk trajectory for optional boost.
- Model artifacts from training outputs.

## Processing Layers
1. Request Intake Layer
- Receives task requests through API and stream queue.
- Tracks task status in Redis hashes.

2. Feature Resolution Layer
- Loads latest per-user feature vector.
- Supports deterministic demo fallback when needed.

3. Scoring Layer
- Auto-routes to full or income-heavy model via data completeness.
- Predicts default probability and maps to 300-900 score.
- Computes expected-loss based loan sizing and APR bands.

4. Override and Audit Layer
- Applies behavioural trajectory score boost when improving.
- Generates machine-readable rule trace for decision audit.

5. Explainability Layer
- Produces SHAP top-5 features and waterfall decomposition.

6. Persistence and Notification Layer
- Stores full results and active-user state.
- Publishes progress events for SSE clients.
- Recalibration job updates stale limits and emits limit reduction events.

## Contracts and Guarantees
- `CreditScoreResult` is canonical scoring response shape.
- Rule trace always includes model routing and threshold checks.
- Explainability payload is attached when explainer is available.

## Redis and Storage Interfaces
- Queue: `stream:credit_score_requests`
- Task state: `score:{task_id}`
- Active users set: `credit:active`
- Latest user credit hash: `credit:user:{user_id}`
- Update channel: `updates:{task_id}`
- Recalibration channel: `credit_events`

## Failure and Recovery Behavior
- Worker failures mark task as `failed` with error message.
- Explainer unavailability degrades gracefully to score-only mode.
- Recalibration sweep continues across per-user exceptions.

## Outputs
- Async credit score decisions with limits and rates.
- Explainable attribution payloads for UI and audit.
- Periodic state refresh and limit-drift control.

## Dependency Edges
- Upstream: Tier 3 features, Tier 4 trend history.
- Downstream: Tier 8 intervention personalization, Tier 10 credit decision bundle.

## What Tier 7 Enables
- Production-style score decisioning with auditable internals.
- Real-time and periodic consistency across user credit state.
- Explainability-ready outputs for regulator and analyst workflows.
