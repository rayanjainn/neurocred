# Tier 10 Architecture - Compliance, What-If, and Regulatory Reporting

## Objective
Tier 10 packages all tier outputs into regulator-ready audit bundles and live what-if decisions for operations and dashboards.

## Implementation Scope
- Unified audit artifact assembly across twin, reasoning, intervention, vigilance, credit, and simulation.
- JSON and PDF report export.
- Live what-if orchestration endpoint combining scenario simulation with twin/credit deltas.

## Core Modules and Surfaces
- Tier 10 endpoints and helpers inside `src/api/main.py`
- `_collect_tier10_audit_bundle(...)`
- `_tier10_report_lines(...)`
- `POST /tier10/whatif/live`
- `GET /tier10/report/{user_id}`

## Data Inputs
- Tier 4 current and historical twin snapshots.
- Tier 5 reasoning traces and narratives.
- Tier 6 simulation caches, EWS, and fan chart outputs.
- Tier 7 credit decisions and portal audit actions.
- Tier 8 trigger and audit event records.
- Tier 9 vigilance result payloads.

## Processing Layers
1. Evidence Collection Layer
- Pulls all tier-local caches and stores by user.
- Normalizes missing sections to null-safe payloads.

2. Audit Bundle Layer
- Constructs machine-readable evidence package with section headers.
- Preserves generated timestamp, user id, and regulatory-standard metadata.

3. Report Rendering Layer
- Returns raw JSON evidence for system integration.
- Renders compact single-page PDF summary without external dependencies.

4. Live What-If Layer
- Accepts scenario modifiers and forwards to simulation endpoint logic.
- Returns latency, SLA status, scenario params, updated twin state, and projected credit update hints.

## Contracts and Guarantees
- JSON output is comprehensive and suitable for downstream compliance tooling.
- PDF output is deterministic compact summary and references JSON for full fidelity.
- Live what-if includes explicit SLA telemetry and updated state snapshots.

## Redis and Storage Interfaces
- Reads from tier caches and audit stores, no dedicated Tier 10 table.
- Uses existing keys from tiers 4 through 9.

## Failure and Recovery Behavior
- Missing per-tier artifacts are represented without breaking overall report response.
- Unsupported format returns explicit client error.
- What-if endpoint validates required user identity input.

## Outputs
- Full multi-tier evidence bundle in JSON.
- Downloadable compact compliance PDF.
- Live scenario decision payload for dashboard and analyst workflows.

## Dependency Edges
- Upstream: all previous tiers.
- Downstream: frontend admin and analyst surfaces, external audit consumption.

## What Tier 10 Enables
- Single-click traceability from model state to communication actions.
- Cross-tier explainability for governance and regulator review.
- Operational what-if workflows tied to live twin state.
