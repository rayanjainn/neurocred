<div align="center">

# NeuroCred

**A cognitive digital twin & credit engine for Indian MSMEs**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?style=flat-square&logo=nextdotjs)](https://nextjs.org)
[![Redis](https://img.shields.io/badge/Redis-Streams-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

*Built at Airavat Hackathon · Team Pookies*

</div>

---

Traditional credit scoring looks backward. NeuroCred looks forward.

It builds a **live, versioned digital twin** of a business from raw transactional signals — UPI logs, bank feeds, SMS alerts, EMI records — and runs a cognitive credit engine on top of it. Monte Carlo simulations, LLM narrative reasoning, anomaly detection, and autonomous interventions all working together, in real time.

---

## Architecture

A ten-tier async pipeline from raw telemetry to credit decision:

```
Multi-Source Ingestion  →  Redis Streams  →  Event Classifier
        ↓
Feature Extractor  →  Digital Twin State  →  LLM Reasoner
        ↓                                        ↓
  Risk Simulator  ←→  Anomaly Detector  →  Cognitive Engine
        ↓
Intervention Agent  →  Live Dashboard  →  Audit Export
```

| Tier | Name | What it does |
|------|------|-------------|
| 1 | Multi-source ingestion | Bank APIs, UPI logs, SMS alerts, EMI records |
| 2 | Event stream processor | Real-time typed event classification, sliding windows |
| 3 | Behavioural feature engine | Volatility scoring, income stability, peer benchmarking |
| 4 | Digital twin state layer | Stateful versioned twin with DNA fingerprint + temporal replay |
| 5 | LLM reasoning layer | Narrative intelligence with chain-of-thought, contradiction detection |
| 6 | Predictive risk simulation | Monte Carlo projections, stress tests, recovery path modelling |
| 7 | Cognitive credit engine | Behaviour-aware dynamic decisioning with bureau integration |
| 8 | Proactive intervention agent | Autonomous nudges, micro-loan push, EMI negotiation |
| 9 | Anomaly & deception detection | Fraud signals, scam defence, synthetic identity scoring |
| 10 | Audit repository & dashboard | Live dashboard, what-if simulation, regulatory export |

---

## Key Ideas

**Digital Twin** — not a flat database. An event-sourced object that maintains the full DNA of the MSME. Replay to any millisecond with `/audit/replay`. Generate a behavioral fingerprint from spending cadence and counterparty entropy.

**LLM Reasoning** — Phi-3 Mini with GBNF grammar constraints. Produces plain-language "Reasoning Reports" that explain credit decisions, citing specific anomalies from sliding windows.

**Proactive Agent** — independent of the user. Monitors the twin for cashflow stress. Detects a ₹5,000 EMI failure risk 48 hours out and automatically pushes a short-term credit offer before the user ever knows there's a problem.

---

## Math

**Spending volatility (z-score):**

$$\sigma_{30d} = \sqrt{\frac{\sum (v_i - \bar{v})^2}{n}}$$

**Income stability index:**

$$\text{ISI} = \frac{\mu_{\text{monthly inbound}}}{\text{CV}_{\text{monthly inbound}} + 1}$$

**Monte Carlo default probability:**

$$P(\text{default}) = \frac{1}{N} \sum_{k=1}^{N} \mathbb{1}(\text{state}_k \in \text{insolvency})$$

---

## Getting Started

```bash
# install the backend
pip install -e .

# install the frontend
cd frontend && npm install && cd ..

# run everything (redis + workers + api + frontend)
./scripts/run_online.sh
```

Detailed setup in [`docs/howtorun.md`](docs/howtorun.md).

---

## Docs

All technical deep-dives live in [`/docs`](docs/):

- [`api.md`](docs/api.md) — REST API reference
- [`schema.md`](docs/schema.md) — data schemas
- [`math.md`](docs/math.md) — mathematical foundations
- [`theory.md`](docs/theory.md) — regulatory theory
- [`Backend.md`](docs/Backend.md) — backend architecture
- [`tier1.md`](docs/tier1.md) – [`tier9.md`](docs/tier9.md) — per-tier deep dives

---

<div align="center">

**NeuroCred** — because your credit score shouldn't be a rearview mirror.

</div>
