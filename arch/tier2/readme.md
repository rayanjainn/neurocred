# Tier 2 Architecture - Semantic Classification and Stream Enrichment

## Objective
Tier 2 transforms canonical ingestion events into typed financial events by assigning merchant category, transaction type, recurrence flag, and anomaly flag. It is the semantic bridge between raw telemetry and behavior features.

## Implementation Scope
- Merchant semantic classification with hybrid rule + embedding approach.
- Event-by-event enrichment and republish.
- Per-user sliding window maintenance for quick aggregates.

## Core Modules
- `src/classifier/merchant_classifier.py`
- `src/classifier/event_processor.py`

## Data Inputs
- Canonical events from `stream:raw_ingestion`.
- Merchant strings, amounts, statuses, provenance, and timestamps.

## Processing Layers
1. Consumer Layer
- Uses Redis stream consumer group for pull/ack workflow.
- Reads batches and reconstructs canonical events from Redis string fields.

2. Classification Layer
- Fast rule pre-filter for high-confidence categories.
- MiniLM embedding similarity against anchor phrase centroids.
- Confidence threshold fallback to `OTHER`.

3. Enrichment Layer
- Writes `merchant_category`, `transaction_type`, and confidence.
- Sets `recurrence_flag` from provenance rules.
- Computes anomaly flags from failed status, z-score outliers, and velocity bursts.

4. Window Update Layer
- Maintains user deques and computes 7d/30d/90d aggregates.
- Stores window rollups in Redis for immediate diagnostics.

5. Publish Layer
- Emits enriched events to `stream:typed_events`.
- Acknowledges consumed raw events.

## Contracts and Guarantees
- Deterministic merchant classification behavior for repeated strings via cache.
- Stable category to transaction-type mapping.
- Backpressure-safe stream consumer semantics through Redis groups.

## Redis and Storage Interfaces
- Input: `stream:raw_ingestion`
- Output: `stream:typed_events`
- Windows cache: `twin:windows:{user_id}`

## Failure and Recovery Behavior
- Malformed records are skipped, not fatal to worker loop.
- `BUSYGROUP` initialization is handled safely.
- Event processing remains online under partial parse failures.

## Outputs
- Typed events suitable for feature engineering.
- Rolling aggregate snapshots for diagnostics and fast reads.

## Dependency Edges
- Upstream: Tier 1 canonical stream.
- Downstream: Tier 3 feature engine consumes typed events.

## What Tier 2 Enables
- Semantic understanding of cashflow events.
- Reliable category and transaction type features.
- Real-time behavior monitoring readiness.
