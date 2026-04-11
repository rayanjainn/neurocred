# Airavat API Documentation

This document outlines all the available API endpoints in the Airavat backend (FastAPI application). The APIs are divided into different tiers corresponding to the backend architecture.

---

## General / System

### 1. Health Check

- **Endpoint**: `/health`
- **Method**: `GET`
- **Description**: Liveness check for the API. It attempts to ping the underlying Redis database.
- **Request Body**: None
- **Query Parameters**: None
- **Response Shape**:
  ```json
  {
    "status": "ok",
    "redis": "ok" // or "down"
  }
  ```

---

## Tier 1: Ingestion

### 2. Trigger Ingestion

- **Endpoint**: `/ingest/trigger`
- **Method**: `POST`
- **Description**: Triggers the synthetic data generator and publishes events to Redis Streams. Runs as an asynchronous background job.
- **Query Parameters**:
  - `n_profiles` (int, default: 50): Number of user profiles to generate.
  - `history_months` (int, default: 12): Months of history to simulate.
- **Request Body**: None
- **Response Shape**:
  ```json
  {
    "status": "started",
    "n_profiles": 50,
    "history_months": 12,
    "stream": "stream:raw_ingestion"
  }
  ```

### 3. Ingestion Status

- **Endpoint**: `/ingest/status`
- **Method**: `GET`
- **Description**: Returns the current length of all Tier 1 raw event streams in Redis.
- **Request Body**: None
- **Response Shape**:
  ```json
  {
    "raw_ingestion": 100,
    "bank": 50,
    "upi": 20,
    "sms": 10,
    "emi": 5,
    "open_banking": 10,
    "voice": 5
  }
  ```

---

## Tier 2: Classifier

### 4. Classifier Status

- **Endpoint**: `/classify/status`
- **Method**: `GET`
- **Description**: Checks the typed event stream length and the classifier consumer group lag.
- **Request Body**: None
- **Response Shape**:
  ```json
  {
    "raw_stream_length": 1000,
    "typed_stream_length": 950,
    "estimated_lag": 50
  }
  ```

---

## Tier 3: Features & Peer Cohorts

### 5. Get Behavioural Features

- **Endpoint**: `/features/{user_id}`
- **Method**: `GET`
- **Description**: Retrieves the latest computed `BehaviouralFeatureVector` for a given user.
- **Path Parameters**:
  - `user_id` (string): The ID of the user (e.g., `u_0001`).
- **Request Body**: None
- **Response Shape**:
  ```json
  {
    "user_id": "u_001",
    "computed_at": "2026-04-11T12:00:00",
    "daily_avg_throughput_30d": 125000.5,
    "cash_buffer_days": 18.5,
    "debit_failure_rate_90d": 0.02,
    "end_of_month_liquidity_dip": 12000.0,
    "emi_burden_ratio": 0.35,
    "savings_rate": 0.12,
    "income_stability_score": 0.85,
    "spending_volatility_index": 0.45,
    "discretionary_ratio": 0.25,
    "cash_dependency_index": 0.15,
    "subscription_count_30d": 4,
    "emi_payment_count_90d": 2,
    "salary_day_spike_flag": false,
    "lifestyle_inflation_trend": 0.05,
    "merchant_category_shift_count": 1,
    "anomaly_flag": false,
    "top3_merchant_concentration": 0.65,
    "peer_cohort_benchmark_deviation": 0.1,
    "income_30d": 85000.0,
    "net_cashflow_30d": 20000.0,
    "gstin": "27AAAAA0000A1Z5",
    "gst_30d_value": 500000.0,
    "ewb_30d_value": 450000.0,
    "gst_filing_compliance_rate": 0.95,
    "upi_p2m_ratio_30d": 0.8,
    "gst_upi_receivables_gap": 0.05,
    "hsn_entropy_90d": 0.72,
    "statutory_payment_regularity_score": 0.9,
    "months_active_gst": 24,
    "income_band": "mid",
    "city_tier": 1,
    "age_group": "26-35",
    "data_completeness_score": 1.0
  }
  ```

### 6. Get Sliding Windows

- **Endpoint**: `/windows/{user_id}`
- **Method**: `GET`
- **Description**: Retrieves the 7d / 30d / 90d sliding-window aggregates for a specific user.
- **Path Parameters**:
  - `user_id` (string): The ID of the user.
- **Request Body**: None
- **Response Shape**: A dynamic dictionary of sliding-window aggregates.

### 7. List Users

- **Endpoint**: `/users`
- **Method**: `GET`
- **Description**: Lists user IDs that currently have feature vectors computed.
- **Query Parameters**:
  - `limit` (int, default: 100): Maximum number of user IDs to return.
- **Request Body**: None
- **Response Shape**:
  ```json
  {
    "count": 100,
    "user_ids": ["u_0000", "u_0001", "..."]
  }
  ```

### 8. Build Peer Cohorts

- **Endpoint**: `/cohorts/build`
- **Method**: `POST`
- **Description**: Manually triggers a rebuild of peer cohort statistics from all currently available feature vectors.
- **Request Body**: None
- **Response Shape**:
  ```json
  {
    "status": "ok",
    "cohorts_written": 5
  }
  ```

---

## Tier 4 & Tier 8: Digital Twin & Interventions

### 9. Get Digital Twin

- **Endpoint**: `/twin/{user_id}`
- **Method**: `GET`
- **Description**: Retrieves the current Digital Twin state for a given user, including risk score, liquidity health, financial DNA, avatar state, and CIBIL-like score.
- **Path Parameters**:
  - `user_id` (string): The ID of the user.
- **Request Body**: None
- **Response Shape**:
  ```json
  {
    "user_id": "u_001",
    "persona": "genuine_healthy",
    "risk_score": 0.28,
    "liquidity_health": "HIGH",
    "income_stability": 0.85,
    "spending_volatility": 0.35,
    "cash_buffer_days": 18.5,
    "emi_burden_ratio": 0.35,
    "financial_dna": [0.12, 0.45, "... (32 dimensions)"],
    "avatar_state": {
      "expression": "calm",
      "mood_message": "Your financial health looks stable today.",
      "liquidity_label": "HIGH"
    },
    "version": 4,
    "created_at": "2026-04-11T10:00:00Z",
    "last_updated": "2026-04-11T12:00:00Z",
    "risk_history": [0.32, 0.31, 0.28],
    "feature_history_summary": [
      { "version": 1, "ts": "2026-04-11T10:00:00Z", "risk_score": 0.32, "liquidity_health": "HIGH" }
    ],
    "cibil_like_score": 732
  }
  ```

### 10. Get Twin History

- **Endpoint**: `/twin/{user_id}/history`
- **Method**: `GET`
- **Description**: Retrieves the version history of a user's Digital Twin, sorted with the newest state first.
- **Path Parameters**:
  - `user_id` (string): The ID of the user.
- **Query Parameters**:
  - `limit` (int, default: 20): Maximum history records to return.
- **Request Body**: None
- **Response Shape**:
  ```json
  {
    "user_id": "u_0001",
    "count": 5,
    "history": [
      {
        "user_id": "u_0001",
        "version": 5,
        "risk_score": 0.25,
        "liquidity_health": "HIGH",
        "last_updated": "2026-04-11T14:00:00Z",
        "avatar_state": { "expression": "calm", "mood_message": "..." }
      }
    ]
  }
  ```

### 11. Update Twin from Features

- **Endpoint**: `/twin/{user_id}/update`
- **Method**: `POST`
- **Description**: Triggers a Twin update using the latest feature vector found in Redis for that user. Recomputes derived metrics and saves a new version.
- **Path Parameters**:
  - `user_id` (string): The ID of the user.
- **Request Body**: None
- **Response Shape**:
  ```json
  {
    "status": "updated",
    "user_id": "u_0001",
    "version": 4,
    "risk_score": 0.28,
    "liquidity_health": "HIGH",
    "cibil_like_score": 750,
    "persona": "genuine_healthy",
    "avatar_expression": "calm"
  }
  ```

### 12. Chat with Twin Avatar

- **Endpoint**: `/twin/{user_id}/chat`
- **Method**: `POST`
- **Description**: Send a conversational message to the Digital Twin avatar and receive an intelligent, contextualized response powered by a DialogueManager.
- **Path Parameters**:
  - `user_id` (string): The ID of the user.
- **Request Body**:
  ```json
  {
    "message": "What does my financial future look like?"
  }
  ```
- **Response Shape**:
  ```json
  {
    "role": "twin",
    "content": "Based on your current state, liquidity looks stable...",
    "intent": "forecast",
    "avatar_expression": "calm",
    "cibil_score": 750,
    "ts": "2026-04-11T14:00:00Z"
  }
  ```

### 13. Get Twin Report

- **Endpoint**: `/twin/{user_id}/report`
- **Method**: `GET`
- **Description**: Generates an end-of-day or weekly text-rich report detailing key insights and suggested actions based on the twin's status.
- **Path Parameters**:
  - `user_id` (string): The ID of the user.
- **Query Parameters**:
  - `report_type` (string, default: `"daily_summary"`): Can be `"daily_summary"` or `"weekly_summary"`.
- **Request Body**: None
- **Response Shape**:
  ```json
  {
    "report_type": "daily_summary",
    "user_id": "u_001",
    "date": "2026-04-11",
    "risk_status": "Excellent",
    "cibil_like_score": 820,
    "liquidity_health": "HIGH",
    "twin_version": 12,
    "key_insights": [
      "CIBIL-like score: 820",
      "Cash buffer healthy: 18.2 days",
      "EMI burden in control: 15%"
    ],
    "suggested_actions": [
      "Maintain your current healthy financial habits"
    ],
    "avatar_expression": "calm",
    "full_report_link": "https://app.airavat.in/report/20260411?uid=u_001",
    "generated_at": "2026-04-11T18:00:00Z",
    "opt_out_note": "Reply STOP to unsubscribe from automated reports."
  }
  ```

### 14. Evaluate Twin Triggers

- **Endpoint**: `/twin/{user_id}/triggers`
- **Method**: `GET`
- **Description**: Evaluates and returns all recently fired intervention triggers for a user based on their current twin state. Useful for debugging the Tier 8 engine.
- **Path Parameters**:
  - `user_id` (string): The ID of the user.
- **Request Body**: None
- **Response Shape**:
  ```json
  {
    "user_id": "u_0001",
    "twin_version": 4,
    "fired_count": 1,
    "triggers": [
      {
        "type": "liquidity_drop",
        "priority": "High",
        "urgency": 0.85,
        "reason": "Cash buffer below threshold",
        "channels": ["SMS", "Push"],
        "suggested_actions": ["Review expenses"]
      }
    ]
  }
  ```

### 15. Bootstrap All Twins

- **Endpoint**: `/twin/bootstrap`
- **Method**: `POST`
- **Description**: A one-time offline operation that reads all feature Parquet partitions, creates/updates Digital Twins for every single user, and saves them to Redis.
- **Request Body**: None
- **Response Shape**:
  ```json
  {
    "status": "ok",
    "twins_bootstrapped": 250
  }
  ```

### 16. Get Audit Trail

- **Endpoint**: `/twin/{user_id}/audit`
- **Method**: `GET`
- **Description**: Retrieves the immutable, event-sourced audit trail for a user. This encompasses all twin updates, intervention triggers, notifications, and chat sessions.
- **Path Parameters**:
  - `user_id` (string): The ID of the user.
- **Query Parameters**:
  - `limit` (int, default: 50): Maximum number of audit records to return.
- **Request Body**: None
- **Response Shape**:
  ```json
  {
    "user_id": "u_0001",
    "count": 10,
    "records": [
      {
        "event_id": "uuid-v4",
        "user_id": "u_001",
        "event_type": "twin_updated",
        "timestamp": "2026-04-11T12:00:00Z",
        "consent_status": true,
        "payload": {
          "version": 4,
          "risk_score": 0.28,
          "liquidity_health": "HIGH"
        }
      }
    ]
  }
  ```

### 17. Replay Audit Since

- **Endpoint**: `/audit/replay`
- **Method**: `POST`
- **Description**: Event-sourced time-travel replay that returns all audit events for a specified user since a provided timestamp. Requires the body to contain valid `user_id` and `since` arguments.
- **Request Body**:
  ```json
  {
    "user_id": "u_0001",
    "since": "2026-04-01T00:00:00"
  }
  ```
- **Response Shape**:
  ```json
  {
    "user_id": "u_0001",
    "since": "2026-04-01T00:00:00",
    "event_count": 5,
    "events": [
      {
        "event_id": "uuid-v4",
        "event_type": "notification_sent",
        "timestamp": "2026-04-11T13:00:00Z",
        "payload": {
          "channel": "SMS",
          "trigger_type": "liquidity_drop"
        }
      }
    ]
  }
  ```

---

## Tier 5: Reasoning Agent

### 18. Run Reasoning Agent

- **Endpoint**: `/reasoning/{user_id}/run`
- **Method**: `POST`
- **Description**: Triggers a full Tier 5 reasoning run. Analyzes contradictions, behavioral changes, and generates a Chain-of-Thought reasoning trace.
- **Path Parameters**:
  - `user_id` (string): The ID of the user.
- **Request Body** (Optional):
  ```json
  {
    "declared_income": 45000.0,
    "is_first_run": false
  }
  ```
- **Response Shape**:
  ```json
  {
    "user_id": "u_001",
    "run_id": "uuid-v4",
    "situation": "lifestyle_inflation",
    "confidence": 0.92,
    "risk_narrative": "...",
    "concern_flags_count": 2,
    "intent_signals_count": 1,
    "contradiction_detected": false,
    "interrogation_needed": false
  }
  ```

### 19. Get Reasoning Result

- **Endpoint**: `/reasoning/{user_id}/result`
- **Method**: `GET`
- **Description**: Returns the full structured Tier 5 result from the latest run.
- **Path Parameters**:
  - `user_id` (string): The ID of the user.
- **Response Shape**: Full `Tier5Result` object including `cot_trace`.

### 20. Get Risk Narrative

- **Endpoint**: `/reasoning/{user_id}/narrative`
- **Method**: `GET`
- **Description**: Lightweight endpoint returning only the risk narrative and active concern flags for frontend cards.
- **Path Parameters**:
  - `user_id` (string): The ID of the user.

### 21. Get CoT Trace (Audit)

- **Endpoint**: `/reasoning/{user_id}/cot`
- **Method**: `GET`
- **Description**: Returns the full 6-step Chain-of-Thought trace for regulatory audit.

---

## Tier 5: Conversational Interrogation

### 22. Get Interrogation Session

- **Endpoint**: `/reasoning/interrogation/{session_id}`
- **Method**: `GET`
- **Description**: Returns the current state of an interrogation session and the next question.

### 23. Submit Interrogation Answer

- **Endpoint**: `/reasoning/interrogation/{session_id}/answer`
- **Method**: `POST`
- **Description**: Submits an answer to the current question and advances the state machine.
- **Request Body**:
  ```json
  {
    "answer": "Yes, I have additional income from freelancing."
  }
  ```

### 24. Abandon Interrogation

- **Endpoint**: `/reasoning/interrogation/{session_id}/abandon`
- **Method**: `DELETE`
- **Description**: Abandons the session. Unanswered questions are converted into persistent `UNRESOLVED_AMBIGUITY` concern flags.

---

## Tier 9: Vigilance — Anomaly & Deception Detection

### 25. Run Vigilance Agent

- **Endpoint**: `/vigilance/{user_id}/run`
- **Method**: `POST`
- **Description**: Triggers a full Tier 9 vigilance run — Fraud Ring Detection, Social Engineering Defence, Bot Detection, Stress Analysis, Income Underreporting, and Identity Shift.
- **Path Parameters**:
  - `user_id` (string): The ID of the user.
- **Request Body** (all optional):
  ```json
  {
    "upi_events": [...],
    "sms_texts": [{"text": "Your account will be blocked...", "sender_id": "TM-HDFCBK"}],
    "declared_income": 45000.0,
    "cohort_mean_income": 48000.0,
    "cohort_std_income": 12000.0
  }
  ```
- **Response Shape**:
  ```json
  {
    "user_id": "u_001",
    "run_id": "uuid-v4",
    "deception_score": 0.12,
    "overall_risk": "LOW",
    "fraud_ring_flag": false,
    "fraud_confidence": 0.05,
    "scam_probability": 0.03,
    "pagerank_score": 0.002,
    "bot_flag": false,
    "mule_flag": false,
    "stress_score": 0.21,
    "underreport_score": 0.08,
    "identity_shift_score": 0.10
  }
  ```

### 26. Get Vigilance Result

- **Endpoint**: `/vigilance/{user_id}/result`
- **Method**: `GET`
- **Description**: Returns the full Tier 9 result including all module outputs (cached 24h).

### 27. Get Vigilance Summary

- **Endpoint**: `/vigilance/{user_id}/summary`
- **Method**: `GET`
- **Description**: Lightweight summary for frontend dashboard. Includes JS-divergence, stress trend, and all risk flags.

### 28. Analyze Scam (Ad-hoc)

- **Endpoint**: `/vigilance/scam/analyze`
- **Method**: `POST`
- **Description**: Analyze a single SMS/voice transcript without needing a pre-computed feature vector.
- **Request Body**:
  ```json
  {
    "user_id": "u_0001",
    "text": "Dear customer, your account will be suspended. Share OTP immediately.",
    "sender_id": "TM-SCAMR"
  }
  ```
- **Response Shape**:
  ```json
  {
    "scam_probability": 0.92,
    "is_scam_alert": true,
    "urgency_score": 0.85,
    "authority_score": 0.0,
    "otp_phishing_score": 0.90,
    "risk_level": "CRITICAL",
    "recommended_action": "ALERT: Block transaction and notify user."
  }
  ```

### 29. Vigilance Stream Status

- **Endpoint**: `/vigilance/stream/status`
- **Method**: `GET`
- **Description**: Returns the depth of the `stream:vigilance_events` Redis stream.

---

## Tier 7: Cognitive Credit Engine

### 25. Submit Credit Score Request

- **Endpoint**: `/credit/score`
- **Method**: `POST`
- **Description**: Submits an asynchronous credit scoring request. The worker picks this up from the credit request stream and writes the result to a unique task ID.
- **Request Body**:
  ```json
  {
    "user_id": "u_0001"
  }
  ```
- **Response Shape**:
  ```json
  {
    "task_id": "uuid-v4",
    "status": "pending",
    "user_id": "u_0001"
  }
  ```

### 26. Get Credit Score Result

- **Endpoint**: `/credit/score/{task_id}`
- **Method**: `GET`
- **Description**: Polls for the final result of a credit scoring task. Returns the full scoring report once complete.
- **Path Parameters**:
  - `task_id` (string): The task ID returned by the initial submission.
- **Response Shape**:
  ```json
  {
    "status": "complete",
    "user_id": "u_0001",
    "credit_score": 742,
    "risk_band": "low_risk",
    "probability_of_default": 0.042,
    "recommended_personal_loan_amount": 2500000,
    "annual_percentage_rate": 11.5,
    "shap_top5": {
      "income_30d": 0.12,
      "gst_filing_compliance_rate": -0.08,
      "emi_burden_ratio": 0.05
    },
    "rule_trace": {
      "msme_gst_check": {
        "result": "PASSED",
        "score_impact": 15
      }
    }
  }
  ```

### 27. Stream Credit Score Progress

- **Endpoint**: `/credit/score/{task_id}/stream`
- **Method**: `GET`
- **Description**: Server-Sent Events (SSE) stream for real-time scoring progress updates.
- **Path Parameters**:
  - `task_id` (string): The task ID to monitor.
- **Response Mode**: `text/event-stream`

### 28. Get Latest Credit Status

- **Endpoint**: `/credit/{user_id}/status`
- **Method**: `GET`
- **Description**: Retrieves the latest scoring result for a user from the 24-hour recalibration cache.
- **Path Parameters**:
  - `user_id` (string): The ID of the user.
- **Response Shape**:
  ```json
  {
    "user_id": "u_0001",
    "credit_score": "742",
    "risk_band": "low_risk",
    "recommended_personal_loan_amount": "2500000",
    "refreshed_at": "2026-04-11T12:00:00"
  }
  ```

### 29. Cognitive Credit Audit Replay

- **Endpoint**: `/credit/audit/replay`
- **Method**: `POST`
- **Description**: Point-in-time feature replay for RBI compliance audits. Re-scores the user based on cached features at the target timestamp.
- **Request Body**:
  ```json
  {
    "user_id": "u_0001",
    "target_timestamp": "2026-03-15T10:00:00"
  }
  ```
- **Response Shape**: Scoring result object as it would have appeared at the target timestamp.

### 30. Credit Engine Health

- **Endpoint**: `/credit/health`
- **Method**: `GET`
- **Description**: Checks the health of the credit engine, including model load status and request queue depth.
- **Response Shape**:
  ```json
  {
    "models": {
      "xgb_digital_twin": "ok",
      "xgb_digital_twin_income_heavy": "ok"
    },
    "queue_depth": 0,
    "status": "ok"
  }
  ```
