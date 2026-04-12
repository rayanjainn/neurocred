# Airavat Unified Architecture (Tiers 1-10)

## Scope
This document consolidates the implemented architecture across all ten tiers based on current source behavior, API surfaces, and event/data contracts.

## End-to-End Flow
1. Tier 1 ingests and canonicalizes multi-source events into Redis streams and raw parquet artifacts.
2. Tier 2 semantically classifies merchant and transaction intent, enriches event fields, and republishes typed events.
3. Tier 3 computes behavioural features and cohort-aware metrics in online and batch modes.
4. Tier 4 updates a versioned digital twin with derived risk/liquidity/persona/avatar state.
5. Tier 5 runs structured reasoning, contradiction detection, and interrogation orchestration.
6. Tier 6 runs Monte Carlo stress simulations and emits EWS/tail-risk/fan-chart artifacts.
7. Tier 7 scores credit asynchronously with explainability and periodic recalibration.
8. Tier 8 executes proactive intervention loops, negotiations, dialogue, report generation, and audit logging.
9. Tier 9 performs vigilance analysis for fraud/scam/bot/anomaly deception signals.
10. Tier 10 assembles cross-tier audit bundles, exports compliance reports, and serves live what-if analysis.

## System Planes
- Data Plane
  - Redis streams, pubsub, hashes, sets, lists, and sorted sets.
  - Partitioned parquet stores under `data/raw/` and `data/features/`.

- Intelligence Plane
  - Semantic classification (MiniLM), behavioural feature engineering, dual XGBoost scoring, SHAP explanation.
  - Statistical reasoning, stochastic simulation, vigilance detectors.

- Orchestration Plane
  - FastAPI route layer as control gateway.
  - Long-running stream workers for classifier, feature engine, and credit scoring.
  - Autonomous intervention agent loop on twin update events.

- Governance Plane
  - Immutable twin history for material state changes.
  - Audit records and replay endpoints.
  - Tier 10 compliance bundle composition.

## API Surface (Major Domains)
- Ingestion/feature domain: `/ingest/*`, `/classify/*`, `/features/*`, `/windows/*`
- Twin/intervention domain: `/twin/*`, `/intervention/*`, `/audit/*`
- Reasoning domain: `/reasoning/*`
- Simulation domain: `/simulation/*`
- Credit domain: `/credit/*`, `/score/*`
- Vigilance domain: `/vigilance/*`
- Compliance domain: `/tier10/*`
- Portal/admin domain: routes in `src/api/portal_routes.py`

## State and Event Backbone
- Core streams
  - `stream:raw_ingestion`
  - `stream:typed_events`
  - `stream:behavioural_features`
  - `stream:credit_score_requests`
  - `stream:reasoning_events`
  - `stream:vigilance_events`
  - `stream:notifications`
  - `stream:twin_timeline`

- Core pubsub channels
  - `twin_updated`
  - `simulation_completed`
  - `updates:{task_id}`
  - `credit_events`

- Core key spaces
  - Twin: `twin:{user_id}`, `twin:{user_id}:history`
  - Features: `twin:features:{user_id}`, `twin:windows:{user_id}`
  - Credit: `score:{task_id}`, `credit:user:{user_id}`, `credit:active`
  - Reasoning: `tier5:result:{user_id}`, `tier5:interrogation:{session_id}`
  - Intervention: `tier8:offer:{user_id}`, `tier8:negotiation:{session_id}`
  - Vigilance: `tier9:result:{user_id}`
  - Simulation: `sim:{user_id}:{sim_id}`, `sim:ews:{user_id}`, `sim:fan:{user_id}`
  - Audit: `audit:{user_id}`, `audit:all`

## Tier-to-Tier Dependencies
- Tier 1 -> Tier 2: canonical raw stream.
- Tier 2 -> Tier 3: typed stream.
- Tier 3 -> Tiers 4/5/6/7/9: behavioural feature contract.
- Tier 4 -> Tiers 5/6/8/10: current and historical twin state.
- Tier 5 -> Tiers 4/10: narrative, flags, and interrogation outputs.
- Tier 6 -> Tiers 4/8/10: risk projections and EWS.
- Tier 7 -> Tiers 8/10: credit decisions and explainability.
- Tier 8 -> Tier 10: intervention and audit evidence.
- Tier 9 -> Tiers 4/8/10: vigilance/deception outcomes.

## Frontend Integration Summary
- Frontend API client maps to major backend domains in `frontend/dib/api.ts`.
- Twin chat proxy and voice transcription routes hydrate twin context in Next.js API handlers.
- Dashboard surfaces consume reasoning, vigilance, simulation, and tier10 report endpoints.

## Operational Lifecycle
- Offline bootstrap path
  - Generate synthetic data.
  - Publish raw events.
  - Compute features and cohorts.
  - Train dual XGBoost models.

- Online runtime path
  - Stream processing continuously updates features.
  - Twin state evolves from feature updates and reasoning/simulation/intervention patches.
  - Credit scoring requests are processed asynchronously.
  - Intervention agent responds to twin events.
  - Tier 10 produces audit/what-if artifacts on demand.

## Risk and Control Characteristics
- Deterministic fallback behavior in reasoning and explainability-unavailable conditions.
- Best-effort auxiliary writes for non-critical telemetry streams.
- Material-change twin history rule prevents non-essential history inflation.
- Replayable evidence chain across twin, intervention, and tier10 report layers.

## Deliverable Map
- Per-tier architecture docs and diagrams: `arch/tier1` through `arch/tier10`.
- Unified diagram: `arch/arch.erasercode`.
- Unified narrative: this file.
