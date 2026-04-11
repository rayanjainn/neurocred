# New Features and Backend Contracts Required (Deep)

Date: 2026-04-11

## 1) Objective and pointer baseline

This file is a detailed API contract blueprint for frontend features that are either:
1. frontend-only today,
2. mock-only today,
3. partially wired to backend with mismatched contracts.

Primary pointers:
1. Frontend contracts: frontend/dib/api.ts:751
2. Frontend voice stack: frontend/src/voice/VoiceControlProvider.tsx:1
3. Twin modal flow: frontend/components/voice/VoiceModal.tsx:76
4. Strategy lab UX: frontend/components/StrategyLab.tsx:58
5. Backend route anchor: src/api/main.py:78

## 2) Feature: Global Voice Control with server-backed actions

### 2.1 Current frontend implementation pointers

1. Voice command parsing:
- frontend/src/voice/commandParser.ts:1

2. Voice action dispatch and navigation:
- frontend/src/voice/VoiceControlProvider.tsx:1

3. Action queue for post-navigation UI execution:
- frontend/src/voice/VoiceControlProvider.tsx:38
- frontend/components/DigitalTwinCard.tsx:44

### 2.2 Required backend contracts

#### Contract A: POST /voice/resolve

Purpose:
- Server-side normalization and confidence scoring of voice transcript.
- Role-aware action policy and route decision.

Request:
{
  "user_id": "u_0001",
  "role": "msme",
  "transcript": "talk to my twin",
  "session_id": "sess_001",
  "locale": "en-IN"
}

Success response:
{
  "recognized": true,
  "intent": "open_twin_chat",
  "confidence": 0.93,
  "navigate_to": "/msme/dashboard",
  "ui_action": "open_twin_chat",
  "policy": {
    "allowed": true,
    "reason": "role-permitted"
  },
  "backend_calls": [
    { "method": "POST", "path": "/twin/u_0001/chat" }
  ],
  "message": "Opening twin chat"
}

Failure response:
{
  "recognized": false,
  "intent": null,
  "confidence": 0.12,
  "message": "Sorry, I did not understand that"
}

Validation rules:
1. transcript non-empty after trim
2. max transcript length 256 chars
3. role in allowed enum
4. confidence in range 0.0 to 1.0

#### Contract B: POST /voice/actions/log

Purpose:
- Audit trail and analytics of voice interactions.

Request:
{
  "user_id": "u_0001",
  "session_id": "sess_001",
  "transcript": "show my risk",
  "intent": "show_risk",
  "executed": true,
  "latency_ms": 183,
  "source": "global_voice"
}

Response:
{
  "ok": true,
  "event_id": "voice_evt_001",
  "ts": "2026-04-11T18:00:00Z"
}

## 3) Feature: Twin chat should use backend twin service

Current gap pointers:
1. frontend/app/api/twin-chat/route.ts:1 calls external LLM directly
2. frontend/components/voice/VoiceModal.tsx:76 posts to /api/twin-chat

Recommended target contract:
1. Use existing backend POST /twin/{user_id}/chat at src/api/main.py:326
2. Ensure payload alignment from VoiceModal

Request:
{
  "message": "How can I improve my score this month?"
}

Response:
{
  "role": "twin",
  "content": "Based on your current cash buffer and filing regularity...",
  "intent": "advice",
  "avatar_expression": "calm",
  "cibil_score": 742,
  "ts": "2026-04-11T14:00:00Z"
}

Implementation note:
1. Keep frontend route handler as a thin proxy if needed for secrets.
2. Do not keep business logic in frontend API route.

## 4) Feature: Strategy Builder backendization

Affected routes:
1. /msme/strategy-lab
2. /bank/strategy-lab
3. /analyst/strategy-lab
4. /risk/strategy-lab

Current local-only pointer:
1. frontend/components/StrategyLab.tsx:58

### 4.1 Contract set

#### Contract A: GET /strategy/templates

Query:
1. role=msme|loan_officer|credit_analyst|risk_manager

Response:
{
  "role": "msme",
  "templates": [
    {
      "id": "job_loss",
      "name": "Income Shock",
      "description": "Simulate 50 percent income drop",
      "version": 3,
      "nodes": [],
      "edges": [],
      "created_by": "system",
      "updated_at": "2026-04-11T10:00:00Z"
    }
  ]
}

#### Contract B: POST /strategy/simulate

Request:
{
  "user_id": "u_0001",
  "role": "msme",
  "graph": {
    "nodes": [],
    "edges": []
  },
  "inputs": {
    "income_change_pct": -25,
    "expense_change_pct": 10,
    "target_savings_pct": 15
  },
  "assumptions": {
    "inflation_pct": 6,
    "interest_rate_pct": 11
  }
}

Response:
{
  "simulation_id": "sim_001",
  "risk_score": 58,
  "liquidity_health": "MEDIUM",
  "net_worth_projection": [20, 30, 25, 45, 60],
  "stress_level": "LOW",
  "explanations": [
    "EMI burden improves after expense correction"
  ],
  "driver_contributions": [
    { "name": "income_change_pct", "impact": -0.14 },
    { "name": "expense_change_pct", "impact": 0.06 }
  ],
  "computed_at": "2026-04-11T18:00:00Z"
}

#### Contract C: POST /strategy

Request:
{
  "user_id": "u_0001",
  "name": "Q2 Defensive Plan",
  "role": "msme",
  "graph": { "nodes": [], "edges": [] },
  "last_simulation_id": "sim_001"
}

Response:
{
  "strategy_id": "str_001",
  "version": 1,
  "saved_at": "2026-04-11T18:02:00Z"
}

#### Contract D: GET /strategy/{strategy_id}/history

Response:
{
  "strategy_id": "str_001",
  "versions": [
    {
      "version": 1,
      "saved_at": "2026-04-11T18:02:00Z",
      "saved_by": "u_0001",
      "summary": "baseline simulation"
    }
  ]
}

#### Contract E: POST /strategy/{strategy_id}/publish

Request:
{
  "target": "loan_officer",
  "notes": "Use this plan for underwriting context"
}

Response:
{
  "ok": true,
  "published_to": "loan_officer",
  "published_at": "2026-04-11T18:05:00Z",
  "publication_id": "pub_001"
}

### 4.2 Non-functional requirements for strategy contracts

1. Idempotency key for simulate and save.
2. Version conflict detection for concurrent edits.
3. Audit events for create/update/publish.
4. Explainability payload retention for compliance.

## 5) Feature: Score and SHAP harmonization

Current pointers:
1. frontend/dib/api.ts:764 uses /score
2. src/api/main.py:470 exposes /credit/score

### Recommended migration (no breaking frontend)

1. Add backend aliases:
- POST /score -> call /credit/score
- GET /score/{task_id} -> call /credit/score/{task_id}
- GET /score/{task_id}/stream -> call /credit/score/{task_id}/stream

2. Keep canonical docs on /credit/score*.

## 6) Feature: Notifications and fraud alerts for dashboards and voice

Frontend pointers:
1. app shell notification actions in frontend/dib/authContext.tsx:49
2. notifApi contracts in frontend/dib/api.ts:923
3. fraud queue calls in frontend/app/risk/fraud-queue/page.tsx:47

Required routes:
1. GET /notifications?unread=true|false
2. PUT /notifications/{id}/read
3. PUT /notifications/read-all
4. GET /fraud-alerts
5. GET /fraud-alerts/{gstin}

Notification response shape:
[
  {
    "id": "notif_001",
    "title": "High EMI burden detected",
    "body": "Your EMI burden crossed threshold",
    "read": false,
    "action_url": "/msme/score-report",
    "created_at": "2026-04-11T09:00:00Z",
    "severity": "high"
  }
]

## 7) Role-specific backend contract packs

### MSME pack

1. /loan-requests*
2. /permissions*
3. /disputes*
4. /reminders*
5. /guide-topics
6. /strategy*

### Loan Officer pack

1. /loan-requests*
2. /permissions*
3. /loan-requests/{id}/score
4. /strategy* (consume and publish workflows)

### Credit Analyst pack

1. /explorer/*
2. /transactions/*
3. /analytics/cohort-median
4. /score-history
5. /risk-thresholds
6. /strategy*

### Risk Manager pack

1. /fraud-alerts*
2. /transactions/graph
3. /risk-thresholds
4. /strategy*

### Admin pack

1. /banks*
2. /users full contract
3. /api-keys*
4. /audit-log
5. /audit/replay alignment

## 8) Reuse opportunities from existing backend capabilities

Available today, recommended for immediate UI integration:
1. /twin/{user_id}/chat from src/api/main.py:326
2. /credit/{user_id}/status from src/api/main.py:557
3. /credit/health from src/api/main.py:637
4. /reasoning/{user_id}/narrative from src/api/main.py:797
5. /vigilance/{user_id}/summary from src/api/main.py:1166

## 9) Error model standardization for all new contracts

Recommended error envelope:
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "target_savings_pct must be between 0 and 100",
    "field": "inputs.target_savings_pct",
    "request_id": "req_001"
  }
}

Recommended HTTP mapping:
1. 400 validation
2. 401 auth
3. 403 role policy denied
4. 404 resource missing
5. 409 version conflict
6. 422 semantic invalid state
7. 500 unexpected

## 10) Security and governance pointers

1. Add role-based access checks for strategy publish and admin APIs.
2. Add audit logging for voice intents that trigger actions.
3. Mask sensitive PII in logs for transcripts and financial prompts.
4. Use request_id propagation across frontend and backend logs.

## 11) Delivery plan

### Phase 1

1. score aliases
2. twin chat backend integration
3. notifications and fraud alerts

### Phase 2

1. loan, permissions, disputes, reminders
2. users contract harmonization
3. basic strategy simulate/save/history

### Phase 3

1. explorer, transactions, thresholds, score-history, analytics/cohort-median
2. api-keys, audit-log, guide-topics

### Phase 4

1. reasoning and vigilance UI exposure
2. strategy publish and cross-role governance

## 12) Acceptance criteria (expanded)

1. Voice command talk to my twin opens modal and response comes from backend /twin/{user_id}/chat.
2. Voice command show my risk fetches /credit/{user_id}/status and updates UI card.
3. Notifications command opens unread list from backend notifications API.
4. Strategy Builder supports create, simulate, save, history, publish.
5. All role dashboards load with NEXT_PUBLIC_USE_MOCK=false for core workflows.
6. Error responses are standardized and traceable by request_id.
