# Backend vs Frontend Coverage Audit (Deep)

Date: 2026-04-11

## 1) Audit goal and method

This file maps:
1. What frontend pages and role flows exist.
2. Which API contracts those flows call.
3. Which of those contracts are implemented in backend.
4. Which backend capabilities are currently unused in frontend.
5. What breaks when NEXT_PUBLIC_USE_MOCK=false.

Audit sources (pointer map):
1. Frontend API surface: frontend/dib/api.ts:751
2. Frontend fetch wrapper and rewrite behavior: frontend/dib/api.ts:721 and frontend/next.config.mjs:10
3. Frontend pages: frontend/app/**/page.tsx
4. Backend route inventory: src/api/main.py:78

## 2) Role-by-role page and dependency pointer map

### MSME pointers

1. Dashboard flow:
- frontend/app/msme/dashboard/page.tsx:52 calls loanApi.list
- frontend/dib/api.ts:792 maps to /loan-requests

2. Score report flow:
- frontend/app/msme/score-report/page.tsx:35 imports scoreApi
- frontend/hooks/useScore.ts:74 calls scoreApi.submit
- frontend/dib/api.ts:764 maps submit to /score

3. Loans flow:
- frontend/app/msme/loans/page.tsx:54 uses loanApi.list
- frontend/app/msme/loans/page.tsx:55 uses permApi.list
- frontend/app/msme/loans/page.tsx:56 uses bankApi.list

4. Disputes flow:
- frontend/app/msme/disputes/page.tsx:31 uses disputeApi.list
- frontend/app/msme/disputes/page.tsx:82 uses disputeApi.create

5. Reminders flow:
- frontend/app/msme/reminders/page.tsx:34 uses reminderApi.list
- frontend/app/msme/reminders/page.tsx:62 uses reminderApi.complete

6. Guide flow:
- frontend/app/msme/guide/page.tsx:53 uses msmeApi.getGuideTopics
- frontend/dib/api.ts:942 maps to /guide-topics

7. Strategy Builder:
- frontend/app/msme/strategy-lab/page.tsx:1 renders StrategyLab
- frontend/components/StrategyLab.tsx:58 begins MSME local simulation logic
- No backend route call in this path.

### Loan Officer pointers

1. Loan queue:
- frontend/app/bank/loan-queue/page.tsx:40 uses loanApi.list
- frontend/app/bank/loan-queue/page.tsx:41 uses permApi.list
- frontend/app/bank/loan-queue/page.tsx:75 uses permApi.create

2. Decisions:
- frontend/app/bank/decisions/page.tsx:32 uses loanApi.list

3. Borrower detail:
- frontend/app/bank/msme/[loan_request_id]/page.tsx:46 uses loanApi.get
- frontend/app/bank/msme/[loan_request_id]/page.tsx:56 uses loanApi.getScore
- frontend/app/bank/msme/[loan_request_id]/page.tsx:90 uses loanApi.decide

4. Strategy Builder:
- frontend/app/bank/strategy-lab/page.tsx:1 renders StrategyLab
- No backend calls in this route path.

### Credit Analyst pointers

1. SHAP Explorer:
- frontend/app/analyst/shap-explorer/page.tsx:79 calls scoreApi.submit
- frontend/app/analyst/shap-explorer/page.tsx:83 calls scoreApi.get
- frontend/app/analyst/shap-explorer/page.tsx:47 calls analyticsApi.getCohortMedian
- frontend/app/analyst/shap-explorer/page.tsx:90 calls adminApi.getEwbDistribution
- frontend/app/analyst/shap-explorer/page.tsx:91 calls adminApi.getReceivablesGap

2. Data Explorer:
- frontend/app/analyst/data-explorer/page.tsx:48 uses adminApi.getExplorerGstins
- frontend/app/analyst/data-explorer/page.tsx:68 uses adminApi.getExplorerDetails

3. Signal Trends:
- frontend/app/analyst/signal-trends/page.tsx:69 uses adminApi.getRiskThresholds
- frontend/app/analyst/signal-trends/page.tsx:103 uses adminApi.getScoreHistory

4. Dispute queue:
- frontend/app/analyst/dispute-queue/page.tsx:33 uses disputeApi.list
- frontend/app/analyst/dispute-queue/page.tsx:71 uses disputeApi.resolve
- frontend/app/analyst/dispute-queue/page.tsx:40 uses adminApi.getGstinGraph

5. Strategy Builder:
- frontend/app/analyst/strategy-lab/page.tsx:1 renders StrategyLab
- No backend calls in this route path.

### Risk Manager pointers

1. Fraud queue:
- frontend/app/risk/fraud-queue/page.tsx:47 uses adminApi.getFraudAlerts
- frontend/app/risk/fraud-queue/page.tsx:36 uses adminApi.getFraudAlert

2. Fraud topology:
- frontend/app/risk/fraud-topology/page.tsx:51 uses adminApi.getGlobalGraph
- frontend/app/risk/fraud-topology/page.tsx:55 uses adminApi.getGstinGraph

3. Thresholds:
- frontend/app/risk/thresholds/page.tsx:78 uses adminApi.getRiskThresholds
- frontend/app/risk/thresholds/page.tsx:112 uses adminApi.updateRiskThresholds

4. Strategy Builder:
- frontend/app/risk/strategy-lab/page.tsx:1 renders StrategyLab
- No backend calls in this route path.

### Admin pointers

1. Overview:
- frontend/app/admin/overview/page.tsx:50 uses scoreApi.health -> /health
- frontend/app/admin/overview/page.tsx:55 uses adminApi.getUsers -> /users
- frontend/app/admin/overview/page.tsx:56 uses adminApi.getAuditLog -> /audit-log
- frontend/app/admin/overview/page.tsx:57 uses bankApi.list -> /banks

2. Users:
- frontend/app/admin/users/page.tsx:52 uses adminApi.getUsers
- frontend/app/admin/users/page.tsx:84 uses adminApi.updateUser
- frontend/app/admin/users/page.tsx:93 uses adminApi.resetUserPassword

3. Banks:
- frontend/app/admin/banks/page.tsx:36 uses bankApi.list
- frontend/app/admin/banks/page.tsx:67 uses bankApi.update
- frontend/app/admin/banks/page.tsx:77 uses bankApi.create

4. API keys:
- frontend/app/admin/api-keys/page.tsx:47 uses adminApi.getApiKeys
- frontend/app/admin/api-keys/page.tsx:76 uses adminApi.revokeApiKey
- frontend/app/admin/api-keys/page.tsx:89 uses adminApi.rotateApiKey
- frontend/app/admin/api-keys/page.tsx:98 uses adminApi.getApiKeyUsage
- frontend/app/admin/api-keys/page.tsx:106 uses adminApi.createApiKey

5. Audit log:
- frontend/app/admin/audit-log/page.tsx:55 uses adminApi.getAuditLog
- frontend/app/admin/audit-log/page.tsx:94 uses adminApi.replayAudit

## 3) Frontend API contract inventory (from api.ts)

Primary contract blocks:
1. authApi at frontend/dib/api.ts:751
2. scoreApi at frontend/dib/api.ts:762
3. loanApi at frontend/dib/api.ts:791
4. permApi at frontend/dib/api.ts:808
5. disputeApi at frontend/dib/api.ts:823
6. reminderApi at frontend/dib/api.ts:842
7. bankApi at frontend/dib/api.ts:851
8. adminApi at frontend/dib/api.ts:866
9. notifApi at frontend/dib/api.ts:923
10. msmeApi at frontend/dib/api.ts:936
11. analyticsApi at frontend/dib/api.ts:946

## 4) Backend route inventory (implemented today)

Backend service entry: src/api/main.py:61

### Core and tiers 1 to 4/8

1. GET /health at src/api/main.py:78
2. POST /ingest/trigger at src/api/main.py:91
3. GET /ingest/status at src/api/main.py:114
4. GET /classify/status at src/api/main.py:139
5. GET /features/{user_id} at src/api/main.py:161
6. GET /windows/{user_id} at src/api/main.py:208
7. GET /users at src/api/main.py:224
8. POST /cohorts/build at src/api/main.py:243
9. GET /twin/{user_id} at src/api/main.py:253
10. GET /twin/{user_id}/history at src/api/main.py:272
11. POST /twin/{user_id}/update at src/api/main.py:281
12. POST /twin/{user_id}/chat at src/api/main.py:326
13. GET /twin/{user_id}/report at src/api/main.py:354
14. GET /twin/{user_id}/triggers at src/api/main.py:379
15. POST /twin/bootstrap at src/api/main.py:412
16. GET /twin/{user_id}/audit at src/api/main.py:426
17. POST /audit/replay at src/api/main.py:438

### Tier 7 credit

1. POST /credit/score at src/api/main.py:470
2. GET /credit/score/{task_id} at src/api/main.py:496
3. GET /credit/score/{task_id}/stream at src/api/main.py:522
4. GET /credit/{user_id}/status at src/api/main.py:557
5. POST /credit/audit/replay at src/api/main.py:574
6. GET /credit/health at src/api/main.py:637

### Tier 5 reasoning

1. POST /reasoning/{user_id}/run at src/api/main.py:673
2. GET /reasoning/{user_id}/result at src/api/main.py:776
3. GET /reasoning/{user_id}/narrative at src/api/main.py:797
4. GET /reasoning/{user_id}/cot at src/api/main.py:834
5. GET /reasoning/interrogation/{session_id} at src/api/main.py:861
6. POST /reasoning/interrogation/{session_id}/answer at src/api/main.py:898
7. DELETE /reasoning/interrogation/{session_id}/abandon at src/api/main.py:1000

### Tier 9 vigilance

1. POST /vigilance/{user_id}/run at src/api/main.py:1043
2. GET /vigilance/{user_id}/result at src/api/main.py:1149
3. GET /vigilance/{user_id}/summary at src/api/main.py:1166
4. POST /vigilance/scam/analyze at src/api/main.py:1212
5. GET /vigilance/stream/status at src/api/main.py:1234

## 5) Gap matrix: frontend expectation vs backend implementation

### Fully available (directly compatible)

1. /health
2. /audit/replay (exists but payload/UX mismatch risk remains)

### Available but namespace or response mismatch

1. Frontend /score* vs backend /credit/score*
2. Frontend /users object list vs backend /users returning {count, user_ids}
3. Frontend admin audit replay expects summary style while backend returns event replay model

### Missing in backend (critical)

1. /auth/login, /auth/logout, /auth/me
2. /loan-requests*
3. /permissions*
4. /disputes*
5. /reminders*
6. /banks*
7. /api-keys*
8. /audit-log
9. /fraud-alerts*
10. /risk-thresholds
11. /transactions/*
12. /explorer/*
13. /score-history
14. /notifications*
15. /guide-topics
16. /chat
17. /analytics/cohort-median

## 6) Strategy Builder deep gap statement

Current implementation pointers:
1. frontend/app/msme/strategy-lab/page.tsx:1
2. frontend/app/bank/strategy-lab/page.tsx:1
3. frontend/app/analyst/strategy-lab/page.tsx:1
4. frontend/app/risk/strategy-lab/page.tsx:1
5. Local simulation logic starts at frontend/components/StrategyLab.tsx:58

Missing server contracts:
1. Strategy template fetch
2. Simulation engine run
3. Save and versioning
4. Cross-role publish and approval
5. Simulation history and rollback
6. Explainability artifact storage

Operational impact:
1. No reproducibility of simulation decisions.
2. No auditability for underwriting/risk policy usage.
3. No shared state between MSME, analyst, risk, and bank roles.

## 7) Runtime architecture notes (important)

1. Frontend rewrite sends /api/* to backend host:
- frontend/next.config.mjs:10

2. Frontend also contains internal Next handlers (bypass backend):
- frontend/app/api/chat/route.ts:1
- frontend/app/api/twin-chat/route.ts:1

3. Twin chat currently bypasses backend twin orchestrator and directly calls external LLM provider in frontend runtime.

## 8) Priority alignment plan (delivery order)

### P0 (blockers for non-mock mode)

1. Score namespace harmonization: /score* vs /credit/score*
2. Users contract harmonization
3. Core transactional domains: loan-requests, permissions, disputes, reminders
4. Notifications domain for app shell and voice actions

### P1 (risk and analyst parity)

1. fraud-alerts
2. risk-thresholds
3. transactions graph and derived analytics
4. explorer and score-history
5. analytics/cohort-median

### P2 (admin and platform maturity)

1. banks and api-keys lifecycle
2. audit-log list endpoint
3. guide-topics and chat service hardening
4. strategy backend services

### P3 (advanced backend integration)

1. reasoning endpoints surfaced to analyst/risk/admin screens
2. vigilance endpoints surfaced to fraud and risk views

## 9) Verification checklist

1. Set NEXT_PUBLIC_USE_MOCK=false.
2. Validate all role landing pages render without 404 API failures.
3. Validate submit score and fetch score in msme + analyst flows.
4. Validate notifications in app shell with read and mark-all-read actions.
5. Validate strategy-lab persistence lifecycle once backend is added.

