# Tier 1 Architecture - Signal Ingestion and Canonicalization

## Objective
Tier 1 synthesizes and normalizes raw financial telemetry into a single canonical event contract that downstream tiers can trust. It is the source of truth for event shape, provenance, and stream publication.

## Implementation Scope
- Raw event generation for personas and timelines.
- Canonical schema enforcement via Pydantic models.
- Redis stream publication to source-specific and unified ingestion streams.

## Core Modules
- `src/ingestion/generator.py`
- `src/ingestion/schemas.py`
- `src/ingestion/redis_producer.py`

## Data Inputs
- Synthetic persona and profile parameters from generator constants.
- Time windows and event cadence rules.
- Merchant templates and transaction distributions.

## Processing Layers
1. Profile Synthesis Layer
- Creates profile populations across persona types.
- Generates user-level identifiers and business metadata.

2. Event Fabrication Layer
- Produces bank, UPI, SMS, EMI, open-banking, GST, and EWB style records.
- Uses seeded stochastic models for reproducibility and variance.

3. Canonicalization Layer
- Maps source events to `CanonicalEvent` shape.
- Preserves provenance in `source_provenance`.
- Standardizes timestamps, status, channel, signed amounts, and identifiers.

4. Stream Emission Layer
- Publishes to `stream:raw_ingestion` and source streams.
- Creates consumer groups if missing.
- Performs batched `XADD` writes with maxlen trimming.

## Contracts and Guarantees
- Canonical event contract defines mandatory fields for all downstream tiers.
- Event IDs support idempotency handling.
- Signed amount convention is stable: positive inflow, negative outflow.
- Ingestion-time stream ordering is explicit; event-time semantics are handled downstream.

## Redis and Storage Interfaces
- Unified stream: `stream:raw_ingestion`
- Source streams: bank, upi, sms, emi, open banking, voice
- Consumer groups initialized for classifier and feature workers
- Offline artifacts: chunked Parquet files under `data/raw/`

## Failure and Recovery Behavior
- Redis availability is validated before publish loop.
- Stream group creation tolerates `BUSYGROUP` responses.
- Serialization is deterministic to avoid malformed entries.

## Outputs
- Canonical, provenance-rich events in Redis streams.
- Raw parquet datasets for offline and replay flows.

## Dependency Edges
- Upstream: none (bootstrap tier).
- Downstream: Tier 2 classifier consumes `stream:raw_ingestion`.

## What Tier 1 Enables
- Uniform semantics across heterogeneous financial signals.
- Deterministic replay and synthetic scenario generation.
- Stable data contract for semantic classification and feature extraction.
