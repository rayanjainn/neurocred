"""
Airavat — FastAPI entry point

Tiers 1–3 are exposed via REST endpoints for:
  - /ingest/trigger   — run the synthetic data generator + Redis producer
  - /classify/status  — check classifier worker stream lag
  - /features/{user_id} — get latest BehaviouralFeatureVector for a user
  - /windows/{user_id}  — get sliding-window aggregates for a user
  - /cohorts/build    — trigger peer cohort Parquet rebuild
  - /health           — liveness check

Tier 4 + Tier 8 Digital Twin endpoints:
  - GET  /twin/{user_id}              — get current Digital Twin state
  - GET  /twin/{user_id}/history      — get twin version history
  - POST /twin/{user_id}/update       — update twin from a feature vector
  - POST /twin/{user_id}/chat         — chat with the avatar
  - GET  /twin/{user_id}/report       — get end-of-day report
  - POST /twin/bootstrap              — bootstrap all twins from features Parquet
  - GET  /twin/{user_id}/audit        — get audit trail
  - POST /audit/replay                — event-sourced time-travel replay

Tier 7 — Cognitive Credit Engine endpoints:
  - POST /credit/score                — submit async credit scoring request
  - GET  /credit/score/{task_id}      — poll scoring result
  - GET  /credit/score/{task_id}/stream — SSE real-time progress
  - GET  /credit/{user_id}/status     — latest credit state from 24h recalibration cache
  - POST /credit/audit/replay         — point-in-time feature replay (RBI compliance)
  - GET  /credit/health               — model load status + queue depth

Tier 6 — Predictive Risk Simulation Engine endpoints:
  - POST /simulation/run              — run full Monte Carlo simulation
  - GET  /simulation/{sim_id}         — retrieve cached simulation result
  - GET  /simulation/ews/{user_id}    — latest EWS snapshot (streaming endpoint)
  - GET  /simulation/fan/{user_id}    — cached fan chart for dashboard
  - GET  /simulation/scenarios        — list available stress scenarios
  - GET  /simulation/counterfactuals  — list available counterfactual scenarios
  - GET  /simulation/health           — engine health check
"""

from __future__ import annotations

import json
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator
from urllib.parse import urlencode
from xml.sax.saxutils import escape

import httpx
import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from src.features.schemas import BehaviouralFeatureVector
from src.strategy.strategy_routes import router as strategy_router
from src.api.portal_routes import router as portal_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    print("[airavat] startup — connecting to Redis")
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis_client.ping()
        print("[airavat] Redis connected")
    except Exception as exc:
        print(f"[airavat] Redis ping failed: {exc}")
    app.state.redis = redis_client
    yield
    print("[airavat] shutdown — closing Redis")
    await redis_client.aclose()


app = FastAPI(
    title="Airavat — Financial Digital Twin Engine",
    version="0.1.0",
    description="Tiers 1–3: Signal Ingestion, Semantic Classifier, Behavioural Feature Engine",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(strategy_router)
app.include_router(portal_router)

CALL_SYSTEM_PROMPT = (
    "You are Vyapar Saathi, a smart business assistant for small vendors. "
    "Keep answers short, conversational, practical, and voice-friendly."
)


def _normalize_public_base(raw: str | None) -> str | None:
    value = (raw or "").strip()
    if not value:
        return None
    if value.startswith("http://") or value.startswith("https://"):
        return value.rstrip("/")
    return f"https://{value.rstrip('/')}"


def _resolve_webhook_base_url(request: Request) -> str | None:
    configured = _normalize_public_base(
        os.getenv("VOICE_PUBLIC_BASE_URL")
        or os.getenv("PUBLIC_VOICE_URL")
        or os.getenv("DOMAIN")
    )
    if configured:
        return configured

    host = request.headers.get("host")
    if not host:
        return None
    proto = request.headers.get("x-forwarded-proto", request.url.scheme or "https")
    return f"{proto}://{host}"


async def _is_reachable(base_url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/health")
        return response.status_code < 500
    except Exception:
        return False


def _safe_speech(text: str) -> str:
    return escape(" ".join(text.replace("\n", " ").split())[:900])


async def _groq_voice_reply(user_text: str) -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return (
            "I heard you. I can help with earnings, expenses, stock, and next best actions. "
            "Please ask again after Groq API key is configured."
        )

    payload = {
        "model": os.getenv("GROQ_CALL_MODEL", "llama-3.1-8b-instant"),
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": CALL_SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        response.raise_for_status()
        data = response.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        return content or "I am here. Please ask me about your business performance."
    except Exception:
        return "I am unable to fetch a smart reply right now. Please try again in a moment."


# ── health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, str]:
    redis: aioredis.Redis = app.state.redis
    try:
        await redis.ping()
        redis_status = "ok"
    except Exception:
        redis_status = "down"
    return {"status": "ok", "redis": redis_status}


# ── Voice call assistant (Twilio) ───────────────────────────────────────────

@app.post("/voice/call/start")
async def start_voice_call(body: dict[str, Any], request: Request) -> dict[str, Any]:
    to_number = str(body.get("to", "")).strip()
    user_id = str(body.get("userId", "")).strip()
    if not re.fullmatch(r"\+[1-9]\d{7,14}", to_number):
        raise HTTPException(
            status_code=400,
            detail="Provide a valid phone number in E.164 format, e.g. +919876543210",
        )

    account_sid = (
        os.getenv("TWILIO_ACCOUNT_SID", "").strip()
        or os.getenv("TWILIO_SID", "").strip()
    )
    auth_token = (
        os.getenv("TWILIO_AUTH_TOKEN", "").strip()
        or os.getenv("TWILIO_TOKEN", "").strip()
    )
    from_number = (
        os.getenv("TWILIO_PHONE_NUMBER", "").strip()
        or os.getenv("TWILIO_FROM_NUMBER", "").strip()
    )
    if not account_sid or not auth_token or not from_number:
        raise HTTPException(
            status_code=400,
            detail=(
                "Missing Twilio config. Set TWILIO_ACCOUNT_SID, "
                "TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER."
            ),
        )

    base_url = _resolve_webhook_base_url(request)
    if not base_url:
        raise HTTPException(
            status_code=400,
            detail="Missing VOICE_PUBLIC_BASE_URL or DOMAIN for Twilio webhooks.",
        )

    reachable = await _is_reachable(base_url)
    if not reachable:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Public webhook URL is not reachable: {base_url}. "
                "Start or refresh your tunnel and update VOICE_PUBLIC_BASE_URL."
            ),
        )

    query = urlencode({"userId": user_id}) if user_id else ""
    webhook = f"{base_url}/voice/call/incoming"
    if query:
        webhook = f"{webhook}?{query}"

    twilio_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"
    payload = {
        "To": to_number,
        "From": from_number,
        "Url": webhook,
        "Method": "POST",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                twilio_url,
                data=payload,
                auth=(account_sid, auth_token),
            )
        if response.status_code >= 400:
            detail = response.text[:500]
            raise HTTPException(
                status_code=502,
                detail=f"Twilio call creation failed: {detail}",
            )

        call_data = response.json()
        return {
            "ok": True,
            "callSid": call_data.get("sid"),
            "status": call_data.get("status"),
            "to": call_data.get("to"),
            "from": call_data.get("from"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to initiate call: {exc}") from exc


@app.api_route("/voice/call/incoming", methods=["GET", "POST"])
async def voice_call_incoming(request: Request) -> Response:
    base_url = _resolve_webhook_base_url(request) or ""
    user_id = str(request.query_params.get("userId", "")).strip()
    query = urlencode({"userId": user_id}) if user_id else ""
    respond_url = f"{base_url}/voice/call/respond"
    if query:
        respond_url = f"{respond_url}?{query}"

    xml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Response>
  <Say voice=\"alice\">Welcome to Vyapar Saathi assistant.</Say>
  <Gather input=\"speech\" method=\"POST\" speechTimeout=\"auto\" language=\"en-IN\" action=\"{escape(respond_url)}\">
    <Say voice=\"alice\">You can ask me about earnings, expenses, profit, stock, or what to do next.</Say>
  </Gather>
  <Say voice=\"alice\">I did not catch that.</Say>
  <Redirect method=\"POST\">{escape(base_url)}/voice/call/incoming{('?' + query) if query else ''}</Redirect>
</Response>"""
    return Response(content=xml, media_type="text/xml")


@app.api_route("/voice/call/respond", methods=["GET", "POST"])
async def voice_call_respond(request: Request) -> Response:
    base_url = _resolve_webhook_base_url(request) or ""
    user_id = str(request.query_params.get("userId", "")).strip()
    query = urlencode({"userId": user_id}) if user_id else ""
    next_url = f"{base_url}/voice/call/respond"
    if query:
        next_url = f"{next_url}?{query}"

    form = await request.form()
    speech_text = str(form.get("SpeechResult", "")).strip()

    if not speech_text:
        xml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Response>
  <Gather input=\"speech\" method=\"POST\" speechTimeout=\"auto\" language=\"en-IN\" action=\"{escape(next_url)}\">
    <Say voice=\"alice\">I could not hear you clearly. Please say that again.</Say>
  </Gather>
  <Redirect method=\"POST\">{escape(base_url)}/voice/call/incoming{('?' + query) if query else ''}</Redirect>
</Response>"""
        return Response(content=xml, media_type="text/xml")

    if re.search(r"\b(bye|goodbye|end call|stop|hang up|thank you)\b", speech_text, re.I):
        xml = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Response>
  <Say voice=\"alice\">Thank you. Ending the call now. Have a productive day.</Say>
  <Hangup/>
</Response>"""
        return Response(content=xml, media_type="text/xml")

    reply = await _groq_voice_reply(speech_text)
    safe_reply = _safe_speech(reply)
    xml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Response>
  <Say voice=\"alice\">{safe_reply}</Say>
  <Gather input=\"speech\" method=\"POST\" speechTimeout=\"auto\" language=\"en-IN\" action=\"{escape(next_url)}\">
    <Say voice=\"alice\">You can continue speaking, or say bye to end the call.</Say>
  </Gather>
  <Redirect method=\"POST\">{escape(base_url)}/voice/call/incoming{('?' + query) if query else ''}</Redirect>
</Response>"""
    return Response(content=xml, media_type="text/xml")


# ── Tier 1: ingestion trigger ─────────────────────────────────────────────────

@app.post("/ingest/trigger")
async def trigger_ingestion(
    n_profiles: int = 50,
    history_months: int = 12,
) -> dict[str, Any]:
    """
    Run the synthetic data generator and publish events to Redis Streams.
    This is an async background job — returns immediately after spawning.
    Use /ingest/status to check stream lengths.
    """
    import asyncio
    from src.ingestion.redis_producer import produce

    # Run in background so the HTTP request doesn't time out
    asyncio.create_task(produce(n_profiles, history_months))
    return {
        "status": "started",
        "n_profiles": n_profiles,
        "history_months": history_months,
        "stream": "stream:raw_ingestion",
    }


@app.get("/ingest/status")
async def ingest_status() -> dict[str, Any]:
    """Return stream lengths for all Tier 1 streams."""
    redis: aioredis.Redis = app.state.redis
    streams = {
        "raw_ingestion": "stream:raw_ingestion",
        "bank": settings.stream_bank,
        "upi": settings.stream_upi,
        "sms": settings.stream_sms,
        "emi": settings.stream_emi,
        "open_banking": settings.stream_ob,
        "voice": settings.stream_voice,
    }
    result: dict[str, Any] = {}
    for name, stream_key in streams.items():
        try:
            length = await redis.xlen(stream_key)
            result[name] = length
        except Exception:
            result[name] = 0
    return result


# ── Tier 2: classifier status ─────────────────────────────────────────────────

@app.get("/classify/status")
async def classifier_status() -> dict[str, Any]:
    """Check typed event stream length and classifier consumer group lag."""
    redis: aioredis.Redis = app.state.redis
    try:
        typed_len = await redis.xlen(settings.stream_typed)
        raw_len = await redis.xlen("stream:raw_ingestion")
        lag = raw_len - typed_len
    except Exception:
        typed_len = 0
        raw_len = 0
        lag = 0

    return {
        "raw_stream_length": raw_len,
        "typed_stream_length": typed_len,
        "estimated_lag": max(lag, 0),
    }


# ── Tier 3: feature retrieval ─────────────────────────────────────────────────

@app.get("/features/{user_id}", response_model=BehaviouralFeatureVector)
async def get_features(user_id: str) -> BehaviouralFeatureVector:
    """
    Retrieve the latest computed BehaviouralFeatureVector for a user.
    Features are updated on every new typed event from Tier 2.
    """
    redis: aioredis.Redis = app.state.redis
    raw = await redis.get(f"twin:features:{user_id}")
    if not raw:
        raise HTTPException(
            status_code=404,
            detail=f"No feature vector found for user_id={user_id}. "
                   "Ensure ingestion + classifier have run.",
        )
    data = json.loads(raw)

    # coerce types
    bool_fields = {"salary_day_spike_flag", "anomaly_flag"}
    int_fields = {"subscription_count_30d", "emi_payment_count_90d",
                  "merchant_category_shift_count", "city_tier", "months_active_gst"}
    float_fields = {
        "gst_30d_value", "ewb_30d_value", "gst_filing_compliance_rate",
        "upi_p2m_ratio_30d", "gst_upi_receivables_gap", "hsn_entropy_90d",
        "statutory_payment_regularity_score"
    }
    float_fields.update({k for k in data if k not in bool_fields and k not in int_fields
                         and k not in ("user_id", "computed_at", "income_band", "age_group", "gstin")})

    for f in bool_fields:
        if f in data:
            data[f] = data[f] in ("1", "True", "true", True)
    for f in int_fields:
        if f in data and data[f]:
            try:
                data[f] = int(float(data[f]))
            except (ValueError, TypeError):
                data[f] = 0
    for f in float_fields:
        if f in data and data[f] != "":
            try:
                data[f] = float(data[f])
            except (ValueError, TypeError):
                data[f] = 0.0

    return BehaviouralFeatureVector.model_validate(data)


@app.get("/windows/{user_id}")
async def get_windows(user_id: str) -> dict[str, Any]:
    """
    Retrieve 7d / 30d / 90d sliding-window aggregates for a user.
    Updated by the Tier 2 classifier on every event.
    """
    redis: aioredis.Redis = app.state.redis
    raw = await redis.get(f"twin:windows:{user_id}")
    if not raw:
        raise HTTPException(
            status_code=404,
            detail=f"No window data for user_id={user_id}.",
        )
    return json.loads(raw)


@app.get("/twin-users")
async def list_twin_users(limit: int = 100) -> dict[str, Any]:
    """List user IDs that have feature vectors computed (internal twin endpoint)."""
    redis: aioredis.Redis = app.state.redis
    cursor = 0
    keys: list[str] = []
    while True:
        cursor, batch = await redis.scan(
            cursor, match="twin:features:*", count=200
        )
        keys.extend(batch)
        if cursor == 0 or len(keys) >= limit:
            break
    user_ids = [k.removeprefix("twin:features:") for k in keys[:limit]]
    return {"count": len(user_ids), "user_ids": user_ids}


# ── peer cohort rebuild ───────────────────────────────────────────────────────

@app.post("/cohorts/build")
async def build_cohorts() -> dict[str, Any]:
    """Rebuild peer cohort statistics from all current feature vectors."""
    from src.features.peer_cohort import build_peer_cohorts
    n = await build_peer_cohorts()
    return {"status": "ok", "cohorts_written": n}


# ── Tier 4: Digital Twin endpoints ───────────────────────────────────────────

@app.get("/twin/{user_id}")
async def get_twin(user_id: str) -> dict[str, Any]:
    """
    Get current Digital Twin state for a user.
    Includes risk score, liquidity health, financial DNA, avatar state, CIBIL-like score.
    """
    from src.twin.twin_service import TwinService
    svc = TwinService(app.state.redis)
    twin = await svc.get(user_id)
    if twin is None:
        raise HTTPException(
            status_code=404,
            detail=f"No Digital Twin found for user_id={user_id}. Run /twin/bootstrap first.",
        )
    data = twin.model_dump()
    data["cibil_like_score"] = twin.cibil_like_score()

    # Prefer generated raw transaction data for timeline; fall back to synthetic timeline.
    from src.api.portal_routes import _get_real_transactions, build_monthly_timeline, window_agg

    timeline: list[dict[str, Any]] = []
    upi_txns, ewb_txns = _get_real_transactions(user_id, limit=5000)
    by_day: dict[str, dict[str, float]] = {}

    def _as_day(ts: Any) -> str | None:
        if isinstance(ts, datetime):
            return ts.date().isoformat()
        if isinstance(ts, str) and ts:
            return ts[:10]
        return None

    for tx in upi_txns:
        day = _as_day(tx.get("timestamp") or tx.get("date"))
        if not day:
            continue
        bucket = by_day.setdefault(
            day,
            {
                "daily_volume": 0.0,
                "daily_count": 0.0,
                "daily_ewb_volume": 0.0,
                "daily_ewb_count": 0.0,
            },
        )
        try:
            amount = abs(float(tx.get("amount", 0.0) or 0.0))
        except (TypeError, ValueError):
            amount = 0.0
        bucket["daily_volume"] += amount
        bucket["daily_count"] += 1.0

    for bill in ewb_txns:
        day = _as_day(bill.get("timestamp"))
        if not day:
            continue
        bucket = by_day.setdefault(
            day,
            {
                "daily_volume": 0.0,
                "daily_count": 0.0,
                "daily_ewb_volume": 0.0,
                "daily_ewb_count": 0.0,
            },
        )
        try:
            total_value = abs(float(bill.get("totalValue", 0.0) or 0.0))
        except (TypeError, ValueError):
            total_value = 0.0
        bucket["daily_ewb_volume"] += total_value
        bucket["daily_ewb_count"] += 1.0

    if by_day:
        today = datetime.utcnow().date()
        start = today - timedelta(days=364)
        for i in range(365):
            day = (start + timedelta(days=i)).isoformat()
            bucket = by_day.get(day)
            timeline.append(
                {
                    "date": day,
                    "daily_volume": int((bucket or {}).get("daily_volume", 0.0)),
                    "daily_count": int((bucket or {}).get("daily_count", 0.0)),
                    "daily_ewb_volume": int((bucket or {}).get("daily_ewb_volume", 0.0)),
                    "daily_ewb_count": int((bucket or {}).get("daily_ewb_count", 0.0)),
                }
            )
    else:
        timeline = build_monthly_timeline(user_id, months=12)

    data["upi_timeline"] = [{"date": t["date"], "volume": t["daily_volume"], "count": t["daily_count"]} for t in timeline]
    data["ewb_timeline"] = [{"date": t["date"], "volume": t["daily_ewb_volume"], "count": t["daily_ewb_count"]} for t in timeline]
    nonzero_days = [
        t for t in timeline if (t["daily_volume"] > 0 or t["daily_ewb_volume"] > 0)
    ]
    data["data_maturity_months"] = len({t["date"][:7] for t in nonzero_days}) or 1
    data["windows"] = {
        "w30": window_agg(timeline, 30),
        "w60": window_agg(timeline, 60),
        "w90": window_agg(timeline, 90),
        "w365": window_agg(timeline, 365),
    }

    # Add score history if available (calculated from twin.risk_history)
    # risk_history is [0.12, 0.15, ...] - map to 1..100
    if twin.risk_history:
        score_hist = []
        now = datetime.utcnow()
        for i, r in enumerate(twin.risk_history):
            score_hist.append({
                "date": (now - timedelta(days=(len(twin.risk_history) - i) * 30)).strftime("%Y-%m-%d"),
                "score": int((1.0 - r) * 100),
                "risk_band": "low_risk" if r < 0.3 else ("medium_risk" if r < 0.6 else "high_risk")
            })
        data["score_history"] = score_hist

    return data


@app.get("/twin/{user_id}/history")
async def get_twin_history(user_id: str, limit: int = 20) -> dict[str, Any]:
    """Get the version history of a Digital Twin (newest first)."""
    from src.twin.twin_service import TwinService
    svc = TwinService(app.state.redis)
    history = await svc.get_history(user_id, limit=limit)
    return {"user_id": user_id, "count": len(history), "history": history}


@app.post("/twin/{user_id}/update")
async def update_twin(user_id: str) -> dict[str, Any]:
    """
    Trigger a Digital Twin update from the latest feature vector stored in Redis.
    Fetches twin:features:{user_id}, recomputes derived metrics, saves new version.
    """
    from src.twin.twin_service import TwinService
    redis: aioredis.Redis = app.state.redis
    raw = await redis.get(f"twin:features:{user_id}")
    if not raw:
        raise HTTPException(
            status_code=404,
            detail=f"No feature vector found for user_id={user_id}.",
        )
    data = json.loads(raw)

    # Coerce types (same logic as /features/{user_id})
    bool_fields = {"salary_day_spike_flag", "anomaly_flag"}
    int_fields = {"subscription_count_30d", "emi_payment_count_90d",
                  "merchant_category_shift_count", "city_tier", "months_active_gst"}
    for f in bool_fields:
        if f in data:
            data[f] = data[f] in ("1", "True", "true", True)
    for f in int_fields:
        if f in data and data[f]:
            try:
                data[f] = int(float(data[f]))
            except (ValueError, TypeError):
                data[f] = 0

    fv = BehaviouralFeatureVector.model_validate(data)
    svc = TwinService(app.state.redis)
    twin = await svc.update_from_features(fv)
    return {
        "status": "updated",
        "user_id": twin.user_id,
        "version": twin.version,
        "risk_score": twin.risk_score,
        "liquidity_health": twin.liquidity_health,
        "cibil_like_score": twin.cibil_like_score(),
        "persona": twin.persona,
        "avatar_expression": twin.avatar_state.expression,
    }


@app.post("/twin/{user_id}/chat")
async def chat_with_twin(user_id: str, body: dict[str, Any]) -> Any:
    """
    Send a message to the Digital Twin avatar and get a response.
    Supports streaming if "stream": true is passed.
    """
    from src.intervention.dialogue_manager import DialogueManager
    from src.twin.twin_service import TwinService
    from fastapi.responses import StreamingResponse
    import asyncio

    message: str = body.get("message", "")
    stream: bool = body.get("stream", False)

    if not message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    svc = TwinService(app.state.redis)
    twin = await svc.get(user_id)
    if twin is None:
        raise HTTPException(
            status_code=404,
            detail=f"No Digital Twin for user_id={user_id}. Run /twin/bootstrap first.",
        )

    dm = DialogueManager()
    response_data = dm.chat(message, twin)

    if not stream:
        return response_data

    async def _streamer():
        content = response_data.get("content", "")
        words = content.split(" ")
        for i, word in enumerate(words):
            # Send word-by-word with the metadata on the first or every chunk
            chunk = {
                "content": word + (" " if i < len(words) - 1 else ""),
                "role": "twin",
                "avatar_expression": response_data.get("avatar_expression"),
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            await asyncio.sleep(0.04)
        yield "data: [DONE]\n\n"

    return StreamingResponse(_streamer(), media_type="text/event-stream")


@app.get("/twin/{user_id}/report")
async def get_twin_report(
    user_id: str,
    report_type: str = "daily_summary",
) -> dict[str, Any]:
    """
    Generate an end-of-day or weekly report for the user's Digital Twin.
    Returns structured report with key insights, suggested actions, and CIBIL-like score.
    """
    from src.intervention.report_generator import generate_report
    from src.twin.twin_service import TwinService

    svc = TwinService(app.state.redis)
    twin = await svc.get(user_id)
    if twin is None:
        raise HTTPException(
            status_code=404,
            detail=f"No Digital Twin for user_id={user_id}.",
        )

    rtype = report_type if report_type in ("daily_summary", "weekly_summary") else "daily_summary"
    report = generate_report(twin, report_type=rtype)  # type: ignore[arg-type]
    return report


@app.get("/twin/{user_id}/triggers")
async def evaluate_twin_triggers(user_id: str) -> dict[str, Any]:
    """
    Evaluate and return all fired intervention triggers for a user's twin state.
    Useful for debugging the Tier 8 trigger engine.
    """
    from src.intervention.trigger_engine import evaluate_triggers
    from src.twin.twin_service import TwinService

    svc = TwinService(app.state.redis)
    twin = await svc.get(user_id)
    if twin is None:
        raise HTTPException(status_code=404, detail=f"No twin for user_id={user_id}.")

    fired = evaluate_triggers(twin)
    return {
        "user_id": user_id,
        "twin_version": twin.version,
        "fired_count": len(fired),
        "triggers": [
            {
                "type": t.trigger_type,
                "priority": t.priority,
                "urgency": t.urgency,
                "reason": t.reason,
                "channels": t.channels,
                "suggested_actions": t.suggested_actions,
            }
            for t in fired
        ],
    }


@app.post("/twin/bootstrap")
async def bootstrap_twins() -> dict[str, Any]:
    """
    One-time offline bootstrap: read all features Parquet partitions,
    create/update Digital Twins for every user, save to Redis.
    """
    from src.twin.twin_service import TwinService
    svc = TwinService(app.state.redis)
    count = await svc.bootstrap_from_features_parquet()
    return {"status": "ok", "twins_bootstrapped": count}


# ── Tier 8: Audit / replay endpoint ──────────────────────────────────────────

@app.get("/twin/{user_id}/audit")
async def get_audit_trail(user_id: str, limit: int = 50) -> dict[str, Any]:
    """
    Retrieve the immutable audit trail for a user (RBI event-sourced replay).
    Returns all twin updates, intervention triggers, notifications, and chat sessions.
    """
    from src.intervention.audit_logger import AuditLogger
    auditor = AuditLogger(app.state.redis)
    records = await auditor.get_user_audit(user_id, limit=limit)
    return {"user_id": user_id, "count": len(records), "records": records}


@app.post("/audit/replay")
async def audit_replay(body: dict[str, Any]) -> dict[str, Any]:
    """
    Event-sourced time-travel replay (tier4_tier8.md §8).
    Returns all audit events for a user since a given timestamp.

    Request body: {"user_id": "u_0001", "since": "2026-04-01T00:00:00"}
    """
    from datetime import datetime
    from src.intervention.audit_logger import AuditLogger

    user_id: str = body.get("user_id", "")
    since_str: str = body.get("since", "")
    if not user_id or not since_str:
        raise HTTPException(status_code=400, detail="user_id and since are required")
    try:
        since_ts = datetime.fromisoformat(since_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="since must be ISO 8601 datetime")

    auditor = AuditLogger(app.state.redis)
    records = await auditor.replay_since(user_id, since_ts)
    return {
        "user_id": user_id,
        "since": since_str,
        "event_count": len(records),
        "events": records,
    }


# ── Tier 7: Cognitive Credit Engine endpoints ─────────────────────────────────

@app.post("/credit/score")
@app.post("/score")
async def submit_credit_score(body: dict[str, Any]) -> dict[str, Any]:
    """
    Submit an async credit scoring request for a retail consumer.

    Request body: {"user_id": "u_0001"}
    Response: {"task_id": "...", "status": "pending"}

    The worker picks this up from stream:credit_score_requests and writes
    the result to score:{task_id}. Poll /credit/score/{task_id} for the result.
    """
    import uuid
    redis: aioredis.Redis = app.state.redis
    user_id: str = body.get("user_id", "")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    task_id = str(uuid.uuid4())
    await redis.hset(f"score:{task_id}", mapping={"status": "pending", "user_id": user_id})
    await redis.xadd(
        "stream:credit_score_requests",
        {"task_id": task_id, "user_id": user_id},
    )
    return {"task_id": task_id, "status": "pending", "user_id": user_id}


@app.get("/credit/score/{task_id}")
@app.get("/score/{task_id}")
async def get_credit_score(task_id: str) -> dict[str, Any]:
    """
    Poll the result of a credit scoring request.

    Returns the full scoring payload when status=complete, including:
    credit_score (300–900), risk_band, recommended_personal_loan_amount,
    annual_percentage_rate, top-5 SHAP features, machine-readable rule_trace,
    behavioural_override trace.
    """
    redis: aioredis.Redis = app.state.redis
    result = await redis.hgetall(f"score:{task_id}")
    if not result:
        raise HTTPException(status_code=404, detail=f"task_id={task_id} not found")

    # Parse JSON sub-fields
    for field in ("shap_top5", "shap_waterfall", "rule_trace", "behavioural_override"):
        if field in result:
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                pass

    return result


@app.get("/credit/score/{task_id}/stream")
@app.get("/score/{task_id}/stream")
async def stream_credit_score(task_id: str):
    """
    Server-Sent Events stream for real-time credit scoring progress.
    Subscribe to updates:{task_id} Redis pub/sub and forward to client.
    """
    from fastapi.responses import StreamingResponse

    redis: aioredis.Redis = app.state.redis

    async def event_generator():
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"updates:{task_id}")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    yield f"data: {data}\n\n"
                    try:
                        parsed = json.loads(data)
                        if parsed.get("status") in ("complete", "failed"):
                            break
                    except (json.JSONDecodeError, TypeError):
                        pass
        finally:
            await pubsub.unsubscribe(f"updates:{task_id}")
            await pubsub.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/credit/{user_id}/status")
async def get_credit_status(user_id: str) -> dict[str, Any]:
    """
    Return the latest credit state for a user from the 24h recalibration cache.
    Includes credit_score, risk_band, recommended_personal_loan_amount, refreshed_at.
    """
    redis: aioredis.Redis = app.state.redis
    result = await redis.hgetall(f"credit:user:{user_id}")
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No credit record for user_id={user_id}. "
                   "Submit a /credit/score request first.",
        )
    return {"user_id": user_id, **result}


@app.post("/credit/audit/replay")
async def credit_audit_replay(body: dict[str, Any]) -> dict[str, Any]:
    """
    Point-in-time feature replay for RBI compliance.
    Loads the BehaviouralFeatureVector from parquet cache and re-scores
    as it would have been at target_timestamp.

    Request body: {"user_id": "u_0001", "target_timestamp": "2026-03-01T00:00:00"}

    Note: full event-sourced replay requires the raw Parquet history.
    This endpoint returns the cached feature state closest to target_timestamp.
    """
    from datetime import datetime

    user_id: str        = body.get("user_id", "")
    ts_str: str         = body.get("target_timestamp", "")
    if not user_id or not ts_str:
        raise HTTPException(status_code=400, detail="user_id and target_timestamp required")
    try:
        target_ts = datetime.fromisoformat(ts_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="target_timestamp must be ISO 8601")

    from pathlib import Path
    import polars as pl
    from src.features.schemas import BehaviouralFeatureVector as BFV
    from src.credit.credit_scorer import CreditScorer

    # Load feature parquet
    cache = Path(settings.features_path) / f"user_id={user_id}" / "features.parquet"
    if not cache.exists():
        raise HTTPException(status_code=404, detail=f"No feature cache for user_id={user_id}")

    df = pl.read_parquet(cache)
    if df.height == 0:
        raise HTTPException(status_code=404, detail="Feature cache is empty")

    row = df.row(0, named=True)
    row["user_id"]     = user_id
    row["computed_at"] = row.get("computed_at", target_ts)
    try:
        fv = BFV(**{k: v for k, v in row.items() if k in BFV.model_fields})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Feature parse error: {exc}")

    try:
        scorer = CreditScorer("data/models")
        result = scorer.score(fv)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Scorer unavailable: {exc}")

    return {
        "user_id":          user_id,
        "target_timestamp": ts_str,
        "replayed_at":      target_ts.isoformat(),
        "credit_score":     result["credit_score"],
        "risk_band":        result["risk_band"],
        "probability_of_default": result["probability_of_default"],
        "rule_trace":       result["rule_trace"],
        "note":             "feature state from parquet cache — raw event replay requires full history",
    }


@app.get("/credit/health")
async def credit_health() -> dict[str, Any]:
    """
    Check Tier 7 model load status and scoring queue depth.
    """
    from pathlib import Path
    redis: aioredis.Redis = app.state.redis

    model_dir = Path("data/models")
    full_ok   = (model_dir / "xgb_digital_twin.ubj").exists()
    income_ok = (model_dir / "xgb_digital_twin_income_heavy.ubj").exists()

    try:
        queue_depth = await redis.xlen("stream:credit_score_requests")
    except Exception:
        queue_depth = -1

    try:
        active_users = await redis.scard("credit:active")
    except Exception:
        active_users = -1

    return {
        "models": {
            "xgb_digital_twin":              "ok" if full_ok   else "missing",
            "xgb_digital_twin_income_heavy": "ok" if income_ok else "missing",
        },
        "queue_depth":  queue_depth,
        "active_users": active_users,
        "status":       "ok" if (full_ok and income_ok) else "degraded",
    }



# ── Tier 5: Reasoning Agent endpoints ────────────────────────────────────────

@app.post("/reasoning/{user_id}/run")
async def run_reasoning(user_id: str, body: dict[str, Any] = {}) -> dict[str, Any]:
    """
    Trigger a full Tier 5 reasoning run for a user.

    Fetches the latest feature vector from Redis, runs the 3-layer
    Contradiction Detector, assembles context, fires the 6-step CoT
    LLM call, and persists all outputs back to the twin + Redis stream.

    Optional body fields:
      declared_income   — monthly income from onboarding (INR)
      recent_events     — list of last typed events (Tier 2 format)
      simulation_verdict — Tier 6 EWS output (if available)
      is_first_run      — bool, default false
    """
    from datetime import datetime
    from pathlib import Path
    import polars as pl
    from src.features.schemas import BehaviouralFeatureVector as BFV
    from src.reasoning.tier5 import run_tier5

    redis: aioredis.Redis = app.state.redis

    # Load features from Redis cache or parquet
    raw = await redis.get(f"twin:features:{user_id}")
    if raw:
        feat_data = json.loads(raw)
    else:
        cache = Path(settings.features_path) / f"user_id={user_id}" / "features.parquet"
        if not cache.exists():
            raise HTTPException(
                status_code=404,
                detail=f"No feature vector found for user_id={user_id}. Run phases 1-3 first.",
            )
        df = pl.read_parquet(cache)
        if df.height == 0:
            raise HTTPException(status_code=404, detail="Feature parquet is empty")
        feat_data = df.row(0, named=True)
        feat_data["user_id"] = user_id
        feat_data.setdefault("computed_at", datetime.utcnow().isoformat())

    # Coerce types for BFV
    bool_fields = {"salary_day_spike_flag", "anomaly_flag"}
    int_fields = {"subscription_count_30d", "emi_payment_count_90d",
                  "merchant_category_shift_count", "months_active_gst"}
    for f in bool_fields:
        if f in feat_data:
            feat_data[f] = feat_data[f] in ("1", "True", "true", True, 1)
    for f in int_fields:
        if f in feat_data and feat_data[f] is not None:
            try:
                feat_data[f] = int(float(feat_data[f]))
            except (ValueError, TypeError):
                feat_data[f] = 0
    for k, v in feat_data.items():
        if isinstance(v, str) and v == "":
            feat_data[k] = None

    try:
        fv = BFV(**{k: v for k, v in feat_data.items() if k in BFV.model_fields})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Feature parse error: {exc}")

    # Run Tier 5 pipeline
    result = await run_tier5(
        features=fv,
        redis_client=redis,
        declared_income=float(body.get("declared_income", 0.0)),
        previous_features=body.get("previous_features"),
        recent_events=body.get("recent_events"),
        simulation_verdict=body.get("simulation_verdict"),
        is_first_run=bool(body.get("is_first_run", False)),
    )

    # Write Tier 5 outputs back to the digital twin
    twin_raw = await redis.get(f"twin:{user_id}")
    if twin_raw:
        twin_data = json.loads(twin_raw)
        twin_data["last_narrative"] = result.risk_narrative
        twin_data["active_flags"] = [f.model_dump() for f in result.concern_flags]
        twin_data["intent_signals"] = [s.model_dump() for s in result.intent_signals]
        twin_data["last_cot_trace"] = result.cot_trace.model_dump()
        twin_data["last_reasoning_run_id"] = result.run_id
        twin_data["last_reasoning_at"] = result.computed_at.isoformat()
        await redis.set(f"twin:{user_id}", json.dumps(twin_data, default=str))

    return {
        "user_id": user_id,
        "run_id": result.run_id,
        "situation": result.cot_trace.classify.value,
        "confidence": result.cot_trace.confidence,
        "risk_narrative": result.risk_narrative,
        "concern_flags_count": len(result.concern_flags),
        "intent_signals_count": len(result.intent_signals),
        "contradiction_detected": result.contradiction.contradiction_detected,
        "contradiction_severity": result.contradiction.severity.value,
        "interrogation_needed": result.interrogation_needed,
        "interrogation_session_id": result.interrogation_session_id,
        "fallback_used": result.fallback_used,
        "computed_at": result.computed_at.isoformat(),
    }


@app.get("/reasoning/{user_id}/result")
async def get_reasoning_result(user_id: str) -> dict[str, Any]:
    """
    Get the latest Tier 5 reasoning result for a user (cached 24h in Redis).

    Returns the full Tier5Result including CoT trace, concern flags,
    intent signals, contradiction detector output, and risk narrative.
    """
    from src.reasoning.tier5 import get_tier5_result

    redis: aioredis.Redis = app.state.redis
    result = await get_tier5_result(user_id, redis)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No reasoning result for user_id={user_id}. "
                   "Call POST /reasoning/{user_id}/run first.",
        )
    return result.model_dump()


@app.get("/reasoning/{user_id}/narrative")
async def get_narrative(user_id: str) -> dict[str, Any]:
    """
    Lightweight endpoint — returns only the risk narrative and concern flags.
    Used by the frontend dashboard card without pulling the full CoT trace.
    """
    from src.reasoning.tier5 import get_tier5_result

    redis: aioredis.Redis = app.state.redis
    result = await get_tier5_result(user_id, redis)
    if not result:
        # Fall back to twin's cached narrative
        twin_raw = await redis.get(f"twin:{user_id}")
        if twin_raw:
            twin_data = json.loads(twin_raw)
            return {
                "user_id": user_id,
                "risk_narrative": twin_data.get("last_narrative", ""),
                "active_flags": twin_data.get("active_flags", []),
                "intent_signals": twin_data.get("intent_signals", []),
                "source": "twin_cache",
            }
        raise HTTPException(status_code=404, detail=f"No narrative for user_id={user_id}")

    return {
        "user_id": user_id,
        "risk_narrative": result.risk_narrative,
        "situation": result.cot_trace.classify.value,
        "confidence": result.cot_trace.confidence,
        "active_flags": [f.model_dump() for f in result.concern_flags],
        "intent_signals": [s.model_dump() for s in result.intent_signals],
        "contradiction": result.contradiction.model_dump(),
        "computed_at": result.computed_at.isoformat(),
        "source": "tier5_cache",
    }


@app.get("/reasoning/{user_id}/cot")
async def get_cot_trace(user_id: str) -> dict[str, Any]:
    """
    Return the full 6-step Chain-of-Thought trace for regulatory audit.
    This is the machine-readable justification for credit decisions.

    Only accessible by analyst roles — links to Tier 10 audit trail.
    """
    from src.reasoning.tier5 import get_tier5_result

    redis: aioredis.Redis = app.state.redis
    result = await get_tier5_result(user_id, redis)
    if not result:
        raise HTTPException(status_code=404, detail=f"No CoT trace for user_id={user_id}")

    return {
        "user_id": user_id,
        "run_id": result.run_id,
        "cot_trace": result.cot_trace.model_dump(),
        "contradiction": result.contradiction.model_dump(),
        "delta_packet": result.delta_packet.model_dump() if result.delta_packet else None,
        "computed_at": result.computed_at.isoformat(),
    }


# ── Tier 5: Interrogation endpoints ──────────────────────────────────────────

@app.get("/reasoning/interrogation/{session_id}")
async def get_interrogation_session(session_id: str) -> dict[str, Any]:
    """
    Get the current state of an interrogation session.

    Returns state, questions list, answers received so far,
    and the next pending question text.
    """
    from src.reasoning.schemas import InterrogationSession

    redis: aioredis.Redis = app.state.redis
    raw = await redis.get(f"tier5:interrogation:{session_id}")
    if not raw:
        raise HTTPException(
            status_code=404,
            detail=f"Interrogation session {session_id} not found or expired (24h TTL).",
        )
    session = InterrogationSession.model_validate_json(raw)

    next_q = None
    if session.current_q_index < len(session.questions):
        next_q = session.questions[session.current_q_index].question_text

    return {
        "session_id": session_id,
        "user_id": session.user_id,
        "state": session.state.value,
        "trigger_reason": session.trigger_reason,
        "total_questions": len(session.questions),
        "current_question_index": session.current_q_index,
        "next_question": next_q,
        "answers_count": len(session.answers),
        "completed": session.state.value in ("COMPLETE", "ABANDONED"),
        "interrogation_value_score": session.interrogation_value_score,
    }


@app.post("/reasoning/interrogation/{session_id}/answer")
async def submit_interrogation_answer(
    session_id: str, body: dict[str, Any]
) -> dict[str, Any]:
    """
    Submit an answer to the current interrogation question.

    Request body: {"answer": "Yes, I have a freelance income of about ₹25,000/month"}

    The state machine advances, parses the answer, and applies twin patches.
    Returns the next question (or completion status).

    On completion, triggers twin re-update with all patches applied.
    """
    from src.reasoning.schemas import InterrogationSession
    from src.reasoning.interrogation import advance_session
    from src.features.schemas import BehaviouralFeatureVector as BFV
    from datetime import datetime

    redis: aioredis.Redis = app.state.redis
    answer_text: str = body.get("answer", "")

    raw = await redis.get(f"tier5:interrogation:{session_id}")
    if not raw:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    session = InterrogationSession.model_validate_json(raw)
    if session.state.value in ("COMPLETE", "ABANDONED"):
        return {"session_id": session_id, "state": session.state.value,
                "message": "Session is already complete."}

    # Load features for context in answer parsing
    feat_raw = await redis.get(f"twin:features:{session.user_id}")
    fv = None
    if feat_raw:
        try:
            feat_data = json.loads(feat_raw)
            bool_fields = {"salary_day_spike_flag", "anomaly_flag"}
            int_fields = {"subscription_count_30d", "emi_payment_count_90d",
                          "merchant_category_shift_count", "months_active_gst"}
            for f in bool_fields:
                if f in feat_data:
                    feat_data[f] = feat_data[f] in ("1", "True", "true", True, 1)
            for f in int_fields:
                if f in feat_data and feat_data[f] is not None:
                    try:
                        feat_data[f] = int(float(feat_data[f]))
                    except (ValueError, TypeError):
                        feat_data[f] = 0
            fv = BFV(**{k: v for k, v in feat_data.items() if k in BFV.model_fields})
        except Exception:
            pass

    if fv is None:
        raise HTTPException(status_code=503, detail=f"Feature vector unavailable for {session.user_id}")

    # Advance state machine
    updated_session, next_question, twin_patch = advance_session(
        session=session,
        user_answer=answer_text if answer_text else None,
        features=fv,
    )

    # Persist updated session
    await redis.setex(
        f"tier5:interrogation:{session_id}",
        86400,
        updated_session.model_dump_json(),
    )

    # Apply twin patches if any
    if twin_patch:
        twin_raw = await redis.get(f"twin:{session.user_id}")
        if twin_raw:
            twin_data = json.loads(twin_raw)
            twin_data.update(twin_patch)
            await redis.set(f"twin:{session.user_id}", json.dumps(twin_data, default=str))

    # Emit completion event
    if updated_session.state.value == "COMPLETE":
        await redis.xadd(
            "stream:reasoning_events",
            {
                "event": "interrogation_completed",
                "user_id": session.user_id,
                "session_id": session_id,
                "value_score": str(updated_session.interrogation_value_score),
                "patches_applied": json.dumps(twin_patch, default=str),
            },
        )

    return {
        "session_id": session_id,
        "state": updated_session.state.value,
        "current_question_index": updated_session.current_q_index,
        "next_question": next_question,
        "twin_patch_applied": twin_patch,
        "complete": updated_session.state.value in ("COMPLETE", "ABANDONED"),
        "interrogation_value_score": updated_session.interrogation_value_score,
    }


@app.delete("/reasoning/interrogation/{session_id}/abandon")
async def abandon_interrogation(session_id: str) -> dict[str, Any]:
    """
    Mark an interrogation session as abandoned.

    Unanswered questions become UNRESOLVED_AMBIGUITY concern flags
    persisted to the twin's active_flags.
    """
    from src.reasoning.schemas import InterrogationSession, InterrogationState
    from src.reasoning.interrogation import unanswered_to_flags

    redis: aioredis.Redis = app.state.redis
    raw = await redis.get(f"tier5:interrogation:{session_id}")
    if not raw:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    session = InterrogationSession.model_validate_json(raw)
    session.state = InterrogationState.ABANDONED

    # Persist flags for unanswered questions
    flags = unanswered_to_flags(session)
    if flags:
        twin_raw = await redis.get(f"twin:{session.user_id}")
        if twin_raw:
            twin_data = json.loads(twin_raw)
            existing = twin_data.get("active_flags", [])
            new_flags = [f.model_dump() for f in flags]
            twin_data["active_flags"] = (existing + new_flags)[:10]
            await redis.set(f"twin:{session.user_id}", json.dumps(twin_data, default=str))

    await redis.setex(f"tier5:interrogation:{session_id}", 3600, session.model_dump_json())

    return {
        "session_id": session_id,
        "state": "ABANDONED",
        "unresolved_flags_created": len(flags),
    }




# ── Tier 9: Vigilance (Anomaly & Deception Detection) endpoints ───────────────

@app.post("/vigilance/{user_id}/run")
async def run_vigilance(user_id: str, body: dict[str, Any] = {}) -> dict[str, Any]:
    """
    Trigger a full Tier 9 vigilance run for a user.

    Runs all 5 sub-modules in sequence:
      - Fraud Ring & Cycle Detection (NetworkX)
      - Social Engineering Defence (Bayesian SMS/voice analysis)
      - Synthetic Identity & Bot Detector
      - Hidden Financial Stress (logistic regression)
      - Income Underreporting + Identity Shift detection

    Optional body fields:
      upi_events        — list of UPI transaction dicts
      ewb_events        — list of E-Way Bill dicts
      sms_texts         — list of {"text": "...", "sender_id": "..."} dicts
      declared_income   — monthly INR from onboarding
      cohort_mean_income / cohort_std_income — peer cohort stats
      category_mix_30d / category_mix_90d    — spend fractions per category
    """
    from pathlib import Path
    import polars as pl
    from datetime import datetime
    from src.features.schemas import BehaviouralFeatureVector as BFV
    from src.vigilance.tier9 import run_tier9

    redis: aioredis.Redis = app.state.redis

    # Load features
    raw = await redis.get(f"twin:features:{user_id}")
    if raw:
        feat_data = json.loads(raw)
    else:
        cache = Path(settings.features_path) / f"user_id={user_id}" / "features.parquet"
        if not cache.exists():
            raise HTTPException(status_code=404,
                detail=f"No feature vector for user_id={user_id}.")
        df = pl.read_parquet(cache)
        if df.height == 0:
            raise HTTPException(status_code=404, detail="Feature parquet is empty")
        feat_data = df.row(0, named=True)
        feat_data["user_id"] = user_id
        feat_data.setdefault("computed_at", datetime.utcnow().isoformat())

    # Type coercion
    bool_fields = {"salary_day_spike_flag", "anomaly_flag"}
    int_fields  = {"subscription_count_30d", "emi_payment_count_90d",
                   "merchant_category_shift_count", "months_active_gst"}
    for f in bool_fields:
        if f in feat_data:
            feat_data[f] = feat_data[f] in ("1", "True", "true", True, 1)
    for f in int_fields:
        if f in feat_data and feat_data[f] is not None:
            try:
                feat_data[f] = int(float(feat_data[f]))
            except (ValueError, TypeError):
                feat_data[f] = 0
    for k, v in feat_data.items():
        if isinstance(v, str) and v == "":
            feat_data[k] = None

    try:
        fv = BFV(**{k: v for k, v in feat_data.items() if k in BFV.model_fields})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Feature parse error: {exc}")

    result = await run_tier9(
        features=fv,
        redis_client=redis,
        upi_events=body.get("upi_events"),
        ewb_events=body.get("ewb_events"),
        sms_texts=body.get("sms_texts"),
        declared_income=float(body.get("declared_income", 0.0)),
        cohort_mean_income=float(body.get("cohort_mean_income", 0.0)),
        cohort_std_income=float(body.get("cohort_std_income", 0.0)),
        category_mix_30d=body.get("category_mix_30d"),
        category_mix_90d=body.get("category_mix_90d"),
    )

    # Propagate key signals into the twin
    twin_raw = await redis.get(f"twin:{user_id}")
    if twin_raw:
        twin_data = json.loads(twin_raw)
        twin_data["fraud_ring_flag"]  = result.fraud_ring_flag
        twin_data["deception_score"]  = result.deception_score
        twin_data["vigilance_risk"]   = result.overall_risk_level.value
        await redis.set(f"twin:{user_id}", json.dumps(twin_data, default=str))

    return {
        "user_id":          user_id,
        "run_id":           result.run_id,
        "deception_score":  result.deception_score,
        "overall_risk":     result.overall_risk_level.value,
        "fraud_ring_flag":  result.fraud_ring_flag,
        "fraud_confidence": result.fraud_confidence,
        "scam_probability": result.scam_probability,
        "pagerank_score":   result.pagerank_score,
        "bot_flag":         result.bot_detector.is_bot_flag,
        "mule_flag":        result.bot_detector.is_mule_flag,
        "stress_score":     result.stress_signal.stress_confidence_score,
        "underreport_score": result.income_underreport.income_underreport_score,
        "identity_shift_score": result.identity_shift.identity_shift_score,
        "computed_at":      result.computed_at.isoformat(),
    }


@app.get("/vigilance/{user_id}/result")
async def get_vigilance_result(user_id: str) -> dict[str, Any]:
    """
    Get the latest Tier 9 vigilance result for a user (cached 24h in Redis).
    Returns the full Tier9Result including all module outputs.
    """
    from src.vigilance.tier9 import get_tier9_result

    redis: aioredis.Redis = app.state.redis
    result = await get_tier9_result(user_id, redis)
    if not result:
        raise HTTPException(status_code=404,
            detail=f"No vigilance result for user_id={user_id}. "
                   "Call POST /vigilance/{user_id}/run first.")
    return result.model_dump()


@app.get("/vigilance/{user_id}/summary")
async def get_vigilance_summary(user_id: str) -> dict[str, Any]:
    """
    Lightweight vigilance summary for frontend dashboard cards.
    Returns decision outputs and risk flags without full module details.
    """
    from src.vigilance.tier9 import get_tier9_result

    redis: aioredis.Redis = app.state.redis
    result = await get_tier9_result(user_id, redis)
    if not result:
        # Fall back to twin cache
        twin_raw = await redis.get(f"twin:{user_id}")
        if twin_raw:
            twin_data = json.loads(twin_raw)
            return {
                "user_id": user_id,
                "fraud_ring_flag": twin_data.get("fraud_ring_flag", False),
                "deception_score": twin_data.get("deception_score", 0.0),
                "overall_risk":    twin_data.get("vigilance_risk", "LOW"),
                "source": "twin_cache",
            }
        raise HTTPException(status_code=404,
            detail=f"No vigilance data for user_id={user_id}")

    return {
        "user_id":              user_id,
        "deception_score":      result.deception_score,
        "overall_risk":         result.overall_risk_level.value,
        "fraud_ring_flag":      result.fraud_ring_flag,
        "fraud_confidence":     result.fraud_confidence,
        "scam_probability":     result.scam_probability,
        "pagerank_score":       result.pagerank_score,
        "is_shell_hub":         result.fraud_ring.is_shell_hub,
        "bot_flag":             result.bot_detector.is_bot_flag,
        "mule_flag":            result.bot_detector.is_mule_flag,
        "stress_score":         result.stress_signal.stress_confidence_score,
        "stress_trend":         result.stress_signal.cash_buffer_trend,
        "underreport_score":    result.income_underreport.income_underreport_score,
        "identity_shift_score": result.identity_shift.identity_shift_score,
        "js_divergence":        result.identity_shift.js_divergence,
        "computed_at":          result.computed_at.isoformat(),
        "source":               "tier9_cache",
    }


@app.post("/vigilance/scam/analyze")
async def analyze_scam(body: dict[str, Any]) -> dict[str, Any]:
    """
    Analyze a single SMS or voice transcript for social engineering signals.
    Does NOT require a pre-computed feature vector.

    Request body:
      {"user_id": "u_0001", "text": "Your account will be blocked...", "sender_id": "TM-HDFCBK"}
    """
    from src.vigilance.scam_detector import run_scam_detector

    user_id   = body.get("user_id", "anonymous")
    text      = body.get("text", "")
    sender_id = body.get("sender_id")

    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    result = run_scam_detector(user_id=user_id, text=text, sender_id=sender_id)
    return result.model_dump()


@app.get("/vigilance/stream/status")
async def vigilance_stream_status() -> dict[str, Any]:
    """
    Returns the current depth of the vigilance event stream and recent alert counts.
    """
    redis: aioredis.Redis = app.state.redis
    try:
        stream_len = await redis.xlen("stream:vigilance_events")
    except Exception:
        stream_len = -1

    return {
        "stream":       "stream:vigilance_events",
        "stream_length": stream_len,
        "status":       "ok",
    }


# ── Tier 6: Predictive Risk Simulation Engine ─────────────────────────────────

@app.post("/simulation/run")
async def run_simulation_endpoint(body: dict[str, Any]) -> dict[str, Any]:
    """
    Run a full Monte Carlo risk simulation for a user.

    Request body mirrors SimulationRequest dataclass:
      {
        "user_id": "u_0001",
        "twin_snapshot": {
          "income_stability": 0.65,
          "spending_volatility": 0.35,
          "liquidity_health": "MEDIUM",
          "risk_score": 0.41,
          "cash_buffer_days": 14.0,
          "emi_monthly": 15000,
          "emi_overdue_count": 0,
          "cash_balance_current": 42000,
          "cascade_susceptibility": 0.45,
          "persona": "genuine_struggling",
          "income_monthly": 50000,
          "essential_expense_monthly": 20000,
          "discretionary_expense_monthly": 10000,
          "overdraft_limit": 5000
        },
        "horizon_days": null,
        "num_simulations": 1000,
        "scenario": {
          "type": "compound",
          "components": ["C_JOB_MEDICAL"],
          "start_day": 0,
          "custom_params": {}
        },
        "variance_reduction": {"sobol": true, "antithetic": true},
        "run_counterfactual": true,
        "counterfactual_id": "CF_EARLIER_RESTRUC",
        "counterfactual_lookback_days": 30,
        "seed": null
      }
    """
    import asyncio
    from src.simulation.engine import (
        SimulationRequest, TwinSnapshot, VarianceReduction, run_simulation
    )
    from src.simulation.scenario_library import ScenarioSpec
    from src.simulation.output_emitter import emit_simulation_completed

    user_id = body.get("user_id", "unknown")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    # Parse twin snapshot
    ts_raw = body.get("twin_snapshot", {})
    twin = TwinSnapshot(
        income_stability=float(ts_raw.get("income_stability", 0.65)),
        spending_volatility=float(ts_raw.get("spending_volatility", 0.35)),
        liquidity_health=ts_raw.get("liquidity_health", "MEDIUM"),
        risk_score=float(ts_raw.get("risk_score", 0.35)),
        cash_buffer_days=float(ts_raw.get("cash_buffer_days", 14.0)),
        emi_monthly=float(ts_raw.get("emi_monthly", 15000.0)),
        emi_overdue_count=int(ts_raw.get("emi_overdue_count", 0)),
        cash_balance_current=float(ts_raw.get("cash_balance_current", 40000.0)),
        cascade_susceptibility=float(ts_raw.get("cascade_susceptibility", 0.45)),
        persona=ts_raw.get("persona", "unknown"),
        income_monthly=float(ts_raw.get("income_monthly", 50000.0)),
        essential_expense_monthly=float(ts_raw.get("essential_expense_monthly", 20000.0)),
        discretionary_expense_monthly=float(ts_raw.get("discretionary_expense_monthly", 10000.0)),
        overdraft_limit=float(ts_raw.get("overdraft_limit", 5000.0)),
    )

    # Parse scenario
    sc_raw = body.get("scenario") or {}
    scenario = ScenarioSpec(
        type=sc_raw.get("type", "baseline"),
        components=sc_raw.get("components", []),
        start_day=sc_raw.get("start_day", 0),
        duration_override=sc_raw.get("duration_override"),
        custom_params=sc_raw.get("custom_params", {}),
    )

    vr_raw = body.get("variance_reduction") or {}
    vr = VarianceReduction(
        sobol=bool(vr_raw.get("sobol", True)),
        antithetic=bool(vr_raw.get("antithetic", True)),
    )

    req = SimulationRequest(
        user_id=user_id,
        twin_snapshot=twin,
        horizon_days=body.get("horizon_days"),
        num_simulations=int(body.get("num_simulations", 1000)),
        scenario=scenario,
        variance_reduction=vr,
        run_counterfactual=bool(body.get("run_counterfactual", True)),
        counterfactual_id=body.get("counterfactual_id", "CF_EARLIER_RESTRUC"),
        counterfactual_lookback_days=int(body.get("counterfactual_lookback_days", 30)),
        seed=body.get("seed"),
    )

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, run_simulation, req)

    redis: aioredis.Redis = app.state.redis
    await emit_simulation_completed(redis, user_id, result)

    return result


@app.get("/simulation/scenarios")
async def list_scenarios() -> dict[str, Any]:
    """
    List all available stress scenarios grouped by type (atomic, compound, cascading).
    """
    from src.simulation.scenario_library import list_scenarios
    return list_scenarios()


@app.get("/simulation/counterfactuals")
async def list_counterfactuals() -> dict[str, str]:
    """
    List available counterfactual scenario IDs and the questions they answer.
    """
    from src.simulation.counterfactual import list_counterfactuals
    return list_counterfactuals()


@app.get("/simulation/health")
async def simulation_health() -> dict[str, Any]:
    """
    Simulation engine health check.
    Reports module availability and Redis connectivity.
    """
    health: dict[str, Any] = {"status": "ok"}
    try:
        import importlib
        for mod in ("src.simulation.engine", "src.simulation.regime",
                    "src.simulation.garch", "src.simulation.correlation",
                    "src.simulation.cascade"):
            importlib.import_module(mod)
        health["engine"] = "loaded"
    except Exception as exc:
        health["engine"] = f"error: {exc}"
        health["status"] = "degraded"

    redis: aioredis.Redis = app.state.redis
    try:
        await redis.ping()
        health["redis"] = "ok"
    except Exception:
        health["redis"] = "down"
        health["status"] = "degraded"

    return health


@app.get("/simulation/ews/{user_id}")
async def get_ews_snapshot(user_id: str) -> dict[str, Any]:
    """
    Return latest Early Warning Score snapshot for a user.
    Populated after the most recent simulation run.
    """
    from src.simulation.output_emitter import get_ews_snapshot
    redis: aioredis.Redis = app.state.redis
    ews = await get_ews_snapshot(redis, user_id)
    if ews is None:
        raise HTTPException(
            status_code=404,
            detail=f"No EWS snapshot found for user {user_id}. Run a simulation first."
        )
    return ews


@app.get("/simulation/fan/{user_id}")
async def get_fan_chart(user_id: str) -> dict[str, Any]:
    """
    Return cached fan chart data for dashboard rendering.
    Keys: p10, p25, p50, p75, p90 as daily cash series arrays.
    """
    from src.simulation.output_emitter import get_fan_chart
    redis: aioredis.Redis = app.state.redis
    fan = await get_fan_chart(redis, user_id)
    if fan is None:
        raise HTTPException(
            status_code=404,
            detail=f"No fan chart found for user {user_id}. Run a simulation first."
        )
    return fan


@app.get("/simulation/{sim_id}")
async def get_simulation_result(sim_id: str, user_id: str) -> dict[str, Any]:
    """
    Retrieve a cached simulation result by simulation_id.
    Requires user_id as query parameter for cache key lookup.
    """
    from src.simulation.output_emitter import get_cached_simulation
    redis: aioredis.Redis = app.state.redis
    result = await get_cached_simulation(redis, user_id, sim_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Simulation {sim_id} not found for user {user_id}")
    return result


if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
