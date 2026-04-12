# Tier 5 Architecture - Reasoning and Interrogation Engine

## Objective
Tier 5 generates structured reasoning over twin features and contradictions, producing narrative, concern flags, intent signals, and optional interrogation workflows. It turns numeric state into explainable, actionable intelligence.

## Implementation Scope
- Contradiction detection across multi-layer statistical checks.
- Context assembly under token budgets.
- Structured CoT generation with fallback safety path.
- Interrogation session lifecycle and answer-to-patch translation.

## Core Modules
- `src/reasoning/schemas.py`
- `src/reasoning/context_assembler.py`
- `src/reasoning/contradiction_detector.py`
- `src/reasoning/cot_engine.py`
- `src/reasoning/interrogation.py`
- `src/reasoning/tier5.py`

## Data Inputs
- Latest behavioural features from Tier 3.
- Current and prior twin snapshots from Tier 4.
- Optional recent event slices and simulation verdict hints.
- Declared income context.

## Processing Layers
1. Contradiction Layer
- Runs Layer 1 z-test, Layer 2 source consistency proxy, and Layer 3 lifestyle consistency index.
- Produces severity, direction, and confidence.

2. Context Assembly Layer
- Prioritizes delta packet, simulation verdict, anomalous features, recent events, and income contradiction.
- Enforces prompt token budgets.

3. CoT Reasoning Layer
- Requests strict JSON reasoning outputs from LLM.
- Parses hypotheses, narrative, intent signals, and flags.
- Uses deterministic fallback path on parse/transport failure.

4. Trigger and Session Layer
- Applies interrogation trigger logic from confidence/contradiction/shift conditions.
- Builds ranked questions with uncertainty-reduction scoring.
- Persists session and handles per-answer state transitions.

5. Persistence and Emission Layer
- Caches latest Tier 5 result.
- Emits reasoning and contradiction events.
- Supports downstream twin patching and replay.

## Contracts and Guarantees
- `Tier5Result` is canonical reasoning contract.
- Concern flags capped and sorted by severity-confidence product.
- Interrogation sessions are explicit state machines, not free-form chat.

## Redis and Storage Interfaces
- Result cache: `tier5:result:{user_id}`
- Session store: `tier5:interrogation:{session_id}`
- Event stream: `stream:reasoning_events`

## Failure and Recovery Behavior
- LLM and parsing failures degrade to threshold-based fallback narrative/flags.
- Session abandonment creates unresolved ambiguity flags.
- Feature-unavailable pathways return controlled API errors.

## Outputs
- Risk narrative and behavioural change summary.
- Intent signals and concern flags.
- Interrogation session IDs and patches for twin update.

## Dependency Edges
- Upstream: Tier 3 features, Tier 4 history/state, optional Tier 6 verdicts.
- Downstream: Tier 4 state patching, Tier 8/10 audit and intervention surfaces.

## What Tier 5 Enables
- Auditable machine reasoning over behavioural risk.
- Human-like explanation without losing deterministic controls.
- Targeted interrogation to reduce uncertainty before decisions.
