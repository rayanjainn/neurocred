# Tier 4 Architecture - Stateful Digital Twin Core

## Objective
Tier 4 materializes a versioned digital twin per user, deriving risk state and avatar signals from Tier 3 features. It is the central mutable state model with immutable history semantics for material changes.

## Implementation Scope
- Twin schema and embedding generation.
- Feature-driven twin updates and persona inference.
- Redis persistence for current and historical snapshots.

## Core Modules
- `src/twin/twin_model.py`
- `src/twin/twin_embedding.py`
- `src/twin/twin_store.py`
- `src/twin/twin_service.py`

## Data Inputs
- Behavioural feature vectors from Tier 3.
- Existing twin state and history from Redis.
- Optional state patches from reasoning, intervention, and simulation outcomes.

## Processing Layers
1. Derivation Layer
- Computes liquidity class, liquidity index, income stability blend, credit dependency, and risk score.
- Builds 32-dimensional financial DNA embedding with deterministic projection and interaction terms.

2. Persona and Avatar Layer
- Infers persona from multi-feature signals.
- Produces avatar expression and mood state based on liquidity and concern flags.

3. Versioning Layer
- Distinguishes material vs non-material state updates.
- Increments version and appends history only when material fields change.

4. Persistence Layer
- Stores current twin in Redis key-space.
- Stores immutable snapshots in history list.
- Emits timeline stream and pubsub update events.

## Contracts and Guarantees
- `DigitalTwin` model is canonical state contract.
- Version history preserves auditability for material state transitions.
- Derived fields are bounded and validated at model level.

## Redis and Storage Interfaces
- Current state: `twin:{user_id}`
- History: `twin:{user_id}:history`
- Timeline stream: `stream:twin_timeline`
- Pub/Sub channel: `twin_updated`

## Failure and Recovery Behavior
- Wrong Redis type recovery path reconstructs from hashes where possible.
- Validation fallback for legacy snapshot shapes.
- Best-effort stream timeline append does not block primary persistence.

## Outputs
- Current digital twin state for API and UI.
- Immutable snapshots for replay and audit.
- Update events consumed by intervention agent and other tiers.

## Dependency Edges
- Upstream: Tier 3 features.
- Downstream: Tier 5 reasoning context, Tier 6 scenario snapshot and risk projection patches, Tier 8 trigger evaluation, Tier 10 report assembly.

## What Tier 4 Enables
- Unified, explainable, and versioned user financial state.
- Event-driven orchestration across intervention and analytics.
- Durable audit trail for compliance-grade replay.
