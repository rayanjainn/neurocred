PROBLEM STATEMENT
F-2
AGENTIC AI
Real-Time Financial Behavioral Digital Twin & Cognitive
Credit Engine
Problem Overview
Traditional financial systems are fundamentally reactive credit scores
lag weeks behind real behaviour, fraud is detected only after money is
gone, and lenders have no live view of a borrower's evolving financial
health. There is no production system today that builds a living,
continuously updated AI representation of a user's financial life.
Your challenge is to build an Agentic AI system that continuously
observes multi-source financial signals and constructs a stateful,
evolving Digital Twin of each user. This twin must autonomously
predict risk, simulate future financial states, generate proactive
interventions, and power adaptive credit decisions all in real time, with
full explainability.
This is not a budgeting app or a credit-scoring model. This is a
continuously learning AI entity that mirrors, simulates, and acts on a
human's financial life across 10 progressive tiers. All tiers must be
attempted; partial credit is awarded per completed tier.
PROBLEM STATEMENT
AGENTIC AI
Real-Time Financial Behavioral Digital Twin & Cognitive
Credit Engine
Challenge Tiers at a Glance
Sr No. Pillar Focus Area
1 Multi-Source Signal
Ingestion
Bank transactions, UPI logs,
SMS alerts, EMI schedules,
open-banking feeds
2 Event Stream Processor
Real-time typed financial
event classification and
sliding-window aggregation
3 Behavioural Feature
Engine
Spending volatility, income
stability, peer cohort
benchmarking, trend
detection
4 Digital Twin State Layer
Stateful, versioned user
financial twin with DNA
fingerprint and temporal
replay
5 LLM Reasoning Layer
Narrative intelligence, chain-
of-thought reasoning,
contradiction detection
6 Predictive Risk
Simulation
Monte Carlo risk projections,
stress tests, recovery path
modelling
7 Cognitive Credit Engine
Behaviour-aware dynamic
credit decisioning with bureau
integration
8 Proactive Intervention
Agent
Autonomous contextual
financial nudges, micro-loan
push, EMI negotiation
9 Anomaly & Deception
Detection
Fraud signals, scam defence,
synthetic identity scoring
10 Audit Repository &
Dashboard
Full-stack live dashboard,
what-if simulation, regulatory
audit export
PROBLEM STATEMENT
AGENTIC AI
Real-Time Financial Behavioral Digital Twin & Cognitive
Credit Engine
Expected Features
Tier 1 — Multi-Source Financial Signal Ingestion Engine
Simulate ingestion from bank transactions, UPI payment logs, SMS transaction-
alert parsing, recurring EMI schedules, open-banking feeds, and voice-call
transcripts as an unstructured signal source.
Normalise all sources into a unified canonical financial event schema with source
provenance tags, idempotent deduplication, and late-arrival handling.
Produce a real-time event stream (Kafka-lite or Redis Streams) consumed by all
downstream tiers.
Tier 2 — Financial Event Stream Processor & Semantic Classifier
Convert raw records into typed, enriched financial events (INCOME,
EXPENSE
_
ESSENTIAL, EMI
_
PAYMENT, SUBSCRIPTION, etc.), each carrying merchant
category, channel, recurrence flag, and anomaly flag.
Build a sliding-window aggregator producing 7-day, 30-day, and 90-day financial
summaries updated on every new event.
Classify merchant categories using a lightweight embedded NLP model hardcoded
lookup tables are not accepted.
Tier 3 — Behavioural Feature Extraction & Trend Engine
Continuously compute spending volatility index, income stability score, discretionary
ratio, EMI burden ratio, savings rate, and cash dependency index.
Detect time-series patterns: end-of-month liquidity dips, salary-day spending spikes,
progressive lifestyle inflation, and sudden merchant-category shifts.
Build a Peer Cohort Benchmarking Layer comparing user features against anonymised
cohort averages by income band, city tier, and age group.
Tier 4 — Digital Twin State Object & Persistence Layer
Maintain a stateful, continuously updated Digital Twin object per user including
financial persona, risk trend (time-series), liquidity health, credit dependency score, and
peer deviation score.
Implement a Twin Versioning System where every state update creates an immutable
snapshot; full historical twin evolution must be reconstructable at any timestamp.
Build a Financial DNA Fingerprint a compact 32-dimension embedding vector
representing the user's behavioural signature, updatable incrementally and comparable
across users.
PROBLEM STATEMENT
AGENTIC AI ( F-2 )
Real-Time Financial Behavioral Digital Twin & Cognitive
Credit Engine
Expected Features
Tier 5 — LLM Reasoning & Narrative Intelligence Layer
An LLM agent must process the twin state and recent event deltas to produce a risk narrative,
behavioural change summary, intent signals, and concern flags — with structured chain-of-thought
reasoning traces on every output.
Build a Contradiction Detector that cross-checks declared income from onboarding against
observed transaction income and flags statistically significant mismatches.
Implement a Conversational Interrogation Mode where the agent conducts a structured 5-question
adaptive interview to resolve ambiguous signals and integrate answers back into twin state.
Tier 6 — Predictive Risk Simulation Engine
Run Monte Carlo simulations projecting the user's financial state 30, 60, and 90 days
forward across 1,000 scenario paths, outputting default probability, liquidity crash
date, EMI stress score, and projected net worth delta.
Support parameterised stress-test injections: income drop, expense surge, job loss,
medical emergency — each producing a full impact report.
Build a Recovery Path Modeller that simulates the minimum intervention required to
return a distressed user to stability within N days.
Tier 7 — Adaptive Cognitive Credit Engine
Replace static loan approval with a dynamic, behaviour-aware credit decisioning engine
integrated with a self-built mock bureau API, outputting eligible amount, risk-adjusted
rate, recommended tenure, and a full machine-readable rule trace.
Implement a Behavioural Credit Override where a user with a low bureau score but an
improving digital twin trajectory can receive a higher offer, with full audit justification.
For revolving credit, the engine must adjust limits every 24 hours based on twin state
changes, with user notification events on limit reductions.
Tier 8 — Proactive Financial Intervention Agent
An autonomous agent monitors twin state continuously and fires contextual,
personalised interventions — overspend warnings, EMI-at-risk alerts, savings
opportunities, lifestyle inflation flags — without any human trigger.
When liquidity health drops below a threshold, proactively generate a pre-qualified
micro-loan offer and deliver it via simulated push notification.
Engage in a structured multi-turn negotiation dialogue to discuss EMI restructuring,
simulate the impact of each proposed change, and seek user confirmation.
PROBLEM STATEMENT
AGENTIC AI
Real-Time Financial Behavioral Digital Twin & Cognitive
Credit Engine
Expected Features
Tier 9 — Anomaly, Intent & Deception Detection Layer
Detect behavioural anomalies beyond simple transaction rules: hidden financial stress
signals, progressive income underreporting, and identity behaviour shifts.
Build a Social Engineering Defence Module that analyses SMS and voice transcripts for
urgency manipulation, authority impersonation, and OTP phishing patterns, outputting
a scam probability score with full signal breakdown.
Build a Synthetic Identity Detector using a behavioural consistency score to flag users
whose transaction patterns are statistically improbable for a real human — indicative of
bot or mule accounts.
Tier 10 — Explainable Audit Repository & Live Simulation Dashboard
Build a full-stack compliance dashboard surfacing: digital twin evolution timeline, risk
projection graph, intervention history, credit decision log, and anomaly heatmap.
Implement a Live What-If Simulation Panel where parameter changes (income -20%,
spending +30%, job loss) update the twin state, risk score, and credit limit live within 10
seconds.
Generate a one-click Regulatory Audit Report (PDF/JSON) containing twin state history,
all LLM reasoning traces, credit decisions, intervention log, anomaly detections, and
simulation artifacts — generated live from the demo session.
