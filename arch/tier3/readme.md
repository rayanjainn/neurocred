# Tier 3 Architecture - Behavioural Feature and Trend Engine

## Objective
Tier 3 converts typed transactional streams into stable behavioural feature vectors used by twining, scoring, simulation, and vigilance. It supports both online stream updates and offline batch generation.

## Implementation Scope
- Event-store based feature extraction over rolling windows.
- Cohort benchmarking and anomaly-aware metrics.
- MSME enrichment fields aligned with GST and EWB style features.

## Core Modules
- `src/features/schemas.py`
- `src/features/engine.py`
- `src/features/peer_cohort.py`

## Data Inputs
- Typed events from `stream:typed_events`.
- Existing user feature caches and optional raw parquet inputs.
- Cohort baselines from peer cohort parquet.

## Processing Layers
1. Stream Ingestion Layer
- Consumes typed events with Redis groups.
- Maintains bounded per-user event stores.

2. Feature Computation Layer
- Computes cashflow, liquidity, burden, stability, volatility, and concentration metrics.
- Produces 7d/30d/90d window aggregates.
- Derives pattern indicators such as salary-day spikes and category shifts.

3. Statistical Conditioning Layer
- KNN imputation for sparse feature fields in offline mode.
- Isolation Forest temporal anomaly flags.

4. Cohort Layer
- Builds peer-cohort statistics by segmentation.
- Computes deviation scores for contextualized risk interpretation.

5. Publication Layer
- Emits behavioural feature vectors to stream and Redis cache.
- Stores partitioned feature parquet outputs for downstream batch consumers.

## Contracts and Guarantees
- `BehaviouralFeatureVector` is the canonical Tier 3 contract.
- Computation remains deterministic under same event history.
- Feature names align with downstream twin/scoring/simulation modules.

## Redis and Storage Interfaces
- Input: `stream:typed_events`
- Output stream: `stream:behavioural_features`
- Cache: `twin:features:{user_id}`
- Batch output: `data/features/user_id=*/features.parquet`
- Cohorts: `data/features/peer_cohorts.parquet`

## Failure and Recovery Behavior
- Missing cohort file degrades gracefully to neutral baseline.
- Empty user history returns safe default metrics.
- Worker loop keeps running when individual records fail parsing.

## Outputs
- Full behavioural feature vectors for every active user.
- Cohort statistics used by contradiction/risk interpretation.

## Dependency Edges
- Upstream: Tier 2 typed events.
- Downstream: Tier 4 twin update, Tier 5 reasoning, Tier 6 simulation snapshot build, Tier 7 scoring, Tier 9 vigilance.

## What Tier 3 Enables
- Unified behavioural intelligence layer across all upper tiers.
- Feature-level consistency across online and offline pathways.
- Explainable and benchmark-aware risk primitives.
