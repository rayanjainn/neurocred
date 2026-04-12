# Tier 8 Architecture - Intervention, Negotiation, Dialogue, and Audit

## Objective
Tier 8 operationalizes proactive interventions on top of twin state changes, including trigger evaluation, relevance scoring, multi-channel notification, negotiation workflows, report generation, and immutable auditing.

## Implementation Scope
- Trigger and relevance logic over latest twin state.
- Offer generation and structured EMI negotiation sessions.
- Avatar dialogue response engine for twin chat.
- Notification dispatch to push/sms/whatsapp (simulated transport in current code).
- Audit logging and replay support.

## Core Modules
- `src/intervention/trigger_engine.py`
- `src/intervention/negotiation_engine.py`
- `src/intervention/dialogue_manager.py`
- `src/intervention/notification_service.py`
- `src/intervention/report_generator.py`
- `src/intervention/audit_logger.py`
- `src/intervention/agent_orchestrator.py`

## Data Inputs
- Twin updates via pubsub and direct API reads.
- User consent and acceptance history signals.
- Trigger urgency, personalization and safety factors.

## Processing Layers
1. Event Listen Layer
- Subscribes to `twin_updated` updates.
- Loads current twin and optional short history context.

2. Trigger Evaluation Layer
- Evaluates liquidity, EMI, overspend, lifestyle, savings, fraud, and new-to-credit triggers.
- Produces urgency, priority, channels, and suggested actions.

3. Relevance and Action Layer
- Computes weighted relevance score.
- Dispatches only when relevance threshold and consent conditions pass.

4. Negotiation Layer
- Generates prequalified offer based on cibil-like proxy and stress severity.
- Runs turn-based intent parsing and restructuring impact simulation.
- Commits twin patch on confirmation.

5. Dialogue Layer
- Detects chat intents and builds contextualized twin responses.
- Supports system-prompt construction for LLM replacement path.

6. Reporting and Audit Layer
- Produces daily/weekly summaries with actions and risk status.
- Stores immutable audit events and supports replay-since timestamp.

## Contracts and Guarantees
- Trigger output contract includes `type`, `priority`, `urgency`, `reason`, and actions.
- Negotiation sessions are stateful and persisted with TTL.
- Audit records are append-only and globally indexed.

## Redis and Storage Interfaces
- Pubsub input: `twin_updated`
- Notification stream: `stream:notifications`
- Offer cache: `tier8:offer:{user_id}`
- Negotiation cache: `tier8:negotiation:{session_id}`
- Audit sets: `audit:{user_id}` and `audit:all`

## Failure and Recovery Behavior
- Dispatch path is best effort by channel.
- Consent-off state yields no send side effects.
- Negotiation retrieval validates user-session consistency.

## Outputs
- User-facing intervention events and conversation responses.
- Structured negotiation outcomes and projected impacts.
- Regulatory-grade audit trails and replay artifacts.

## Dependency Edges
- Upstream: Tier 4 twin state/events, Tier 6 stress outputs, Tier 7 risk context.
- Downstream: Tier 10 report and audit bundle aggregation.

## What Tier 8 Enables
- Closed-loop proactive engagement beyond passive scoring.
- Explainable, actionable, and persisted user interventions.
- Compliance-friendly communication and auditability.
