# Tier 1: Multi-Source Signal Ingestion

Related Tiers: Tier 1 (Signal Ingestion)

## 1. Overview: The Financial Data Surface

Tier 1 is the ingestion foundation of FinTwin. It handles the challenges of **heterogeneous financial signals** by normalizing multi-format data into a canonical event stream. This layer is designed as an "Empty Pipeline" that can ingest both synthetic development data and real production feeds from licensed gateways.

### 1.1 Ingestion Sources

The system consumes data from five primary domains:

- **Bank Transactions**: CASA and term-deposit statements via CSV/PDF parsing or direct API.
- **UPI Logs**: Real-time NPCI-compliant payloads (P2P, P2M, Autopay).
- **SMS Transactional Alerts**: Parsed GSM-level alerts for immediate debit/credit notifications.
- **EMI & Subscription Schedules**: Debt repayment and recurring obligation trackers.
- **Account Aggregator (AA) Feeds**: Consent-based JSON payloads following Sahamati/ReBIT standards.

---

## 2. Structural Integrity & Compliance

### 2.1 Schema Normalization

Every raw event is validated against a strict JSON schema (defined in `Schema.md`) to ensure idempotency and temporal consistency.

- **Idempotency**: Every event is assigned a UUID to prevent duplicate processing.
- **Temporal Anchoring**: All events are normalized to ISO 8601 timestamps to enable sliding-window calculations in Tier 2/3.

### 2.2 Privacy & DPDPA Compliance

Tier 1 enforces PII (Personally Identifiable Information) masking at the gateway level.

- **Anonymized Keys**: User IDs are hashed before entering the stream.
- **Minimalist Payloads**: Only fields relevant to the Digital Twin (amounts, timestamps, merchants) are propagated downstream.

---

## 3. Empty Pipeline Architecture

A core design decision is the **"Empty Pipeline with Synthetic Heartbeat"**.
- During development, a synthetic generator (documented in `Data.md`) pumps realistic but fake transactions into Tier 1.
- In production, this generator is swapped for live Sahamati/Setu/Razorpay webhooks without changing a single line of downstream processing code.
