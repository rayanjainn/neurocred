#!/usr/bin/env bash
# One-command workflow to create high-volatility twin versions and run Monte Carlo.
#
# Example:
#   bash scripts/stress_twin_workflow.sh --user-id u_a22645da --gstin 24IEYIC0868X8Z8
#
# Auto-fix missing features / 422 setup issues:
#   bash scripts/stress_twin_workflow.sh --user-id u_a22645da --auto-fix

set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python}"

"$PYTHON_BIN" - "$@" <<'PY'
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _run(cmd: list[str]) -> None:
    print(f"[run] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def _require_ok(resp: requests.Response, ctx: str) -> dict:
    if resp.status_code >= 400:
        print(f"[error] {ctx} failed: HTTP {resp.status_code}")
        try:
            print(resp.json())
        except Exception:
            print(resp.text)
        raise SystemExit(1)
    return resp.json()


def _ensure_features(
    sess: requests.Session,
    api_base: str,
    user_id: str,
    auto_fix: bool,
) -> None:
    r = sess.get(f"{api_base}/features/{user_id}", timeout=30)
    if r.status_code == 200:
        return

    local_parquet = f"data/features/user_id={user_id}/features.parquet"
    if os.path.exists(local_parquet):
        print(f"[warn] /features/{user_id} returned HTTP {r.status_code}, but local parquet exists.")
        print("[info] Continuing; Redis feature cache will be hydrated from parquet.")
        return

    print(f"[warn] /features/{user_id} returned HTTP {r.status_code}")
    if auto_fix:
        print("[fix] Running Phase 3 feature generation and twin bootstrap...")
        _run(["bash", "scripts/phase3_features.sh"])
        sess.post(f"{api_base}/twin/bootstrap", timeout=120)

        if os.path.exists(local_parquet):
            print("[ok] Local parquet features found after auto-fix.")
            return

        r2 = sess.get(f"{api_base}/features/{user_id}", timeout=30)
        if r2.status_code == 200:
            print("[ok] Features available after auto-fix.")
            return

    print("[error] Features are missing for this user. This causes simulation 422.")
    print("[next] Run: bash scripts/phase3_features.sh")
    print("[next] Then: curl -X POST http://127.0.0.1:8001/twin/bootstrap")
    raise SystemExit(1)


def _ensure_twin(sess: requests.Session, api_base: str, user_id: str) -> None:
    r = sess.get(f"{api_base}/twin/{user_id}", timeout=30)
    if r.status_code == 200:
        return
    print(f"[warn] /twin/{user_id} returned HTTP {r.status_code}; bootstrapping twins...")
    sess.post(f"{api_base}/twin/bootstrap", timeout=120)
    r2 = sess.get(f"{api_base}/twin/{user_id}", timeout=30)
    if r2.status_code != 200:
        print("[error] Twin still unavailable after bootstrap.")
        try:
            print(r2.json())
        except Exception:
            print(r2.text)
        raise SystemExit(1)


def _hydrate_base_income_fields(rdb: redis.Redis, user_id: str, base: dict) -> dict:
    """Fill missing income/expense fields from live window aggregates when possible."""
    income_30 = _num(base.get("income_30d"), 0.0)
    essential_30 = _num(base.get("essential_30d"), 0.0)
    disc_30 = _num(base.get("discretionary_30d"), 0.0)

    if income_30 > 0 and essential_30 > 0 and disc_30 >= 0:
        return base

    raw = rdb.get(f"twin:windows:{user_id}")
    if not raw:
        return base
    try:
        w = json.loads(raw)
    except json.JSONDecodeError:
        return base

    w_income = _num(w.get("30d_total_income"), 0.0)
    w_essential = _num(w.get("30d_total_essential"), 0.0)
    w_disc = _num(w.get("30d_total_discretionary"), 0.0)
    w_emi = _num(w.get("30d_emi"), 0.0)
    w_sub = _num(w.get("30d_subscription"), 0.0)

    if income_30 <= 0 and w_income > 0:
        base["income_30d"] = w_income
        base["income_90d"] = max(_num(base.get("income_90d"), 0.0), w_income * 3.0)

    if essential_30 <= 0 and w_essential > 0:
        base["essential_30d"] = w_essential
        base["essential_90d"] = max(_num(base.get("essential_90d"), 0.0), w_essential * 3.0)

    if disc_30 <= 0 and w_disc >= 0:
        base["discretionary_30d"] = w_disc
        base["discretionary_90d"] = max(_num(base.get("discretionary_90d"), 0.0), w_disc * 3.0)

    if _num(base.get("emi_burden_ratio"), 0.0) <= 0 and _num(base.get("income_30d"), 0.0) > 0:
        total_oblig = w_emi + w_sub
        base["emi_burden_ratio"] = min(1.2, total_oblig / max(_num(base.get("income_30d"), 1.0), 1.0))

    return base


def _load_features_from_local_parquet(user_id: str) -> dict | None:
    from pathlib import Path

    import polars as pl

    path = Path(f"data/features/user_id={user_id}/features.parquet")
    if not path.exists():
        return None

    df = pl.read_parquet(path)
    if df.height == 0:
        return None

    row = df.row(0, named=True)
    row["user_id"] = user_id
    row.setdefault("computed_at", _now_iso())
    return row


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create fluctuating twin versions and run simulation for each state.",
    )
    parser.add_argument("--user-id", required=True, help="Target user_id (e.g. u_a22645da)")
    parser.add_argument("--gstin", default="", help="Optional GSTIN for explorer twin_timeline check")
    parser.add_argument("--api-base", default="http://127.0.0.1:8001", help="API base URL")
    parser.add_argument("--redis-url", default="redis://localhost:6379/0", help="Redis URL")
    parser.add_argument("--steps", type=int, default=8, help="Number of stress/recovery steps")
    parser.add_argument("--sleep-sec", type=float, default=0.25, help="Pause between steps")
    parser.add_argument("--auto-fix", action="store_true", help="Auto-run feature generation/bootstrap when needed")
    args = parser.parse_args()

    try:
        import redis
        import requests
    except Exception as exc:
        print("[error] Missing Python dependency for this script:", exc)
        print("[hint] Install deps in your env (requests, redis) and retry.")
        raise SystemExit(1)

    uid = args.user_id.strip()
    api = args.api_base.rstrip("/")

    sess = requests.Session()
    health = sess.get(f"{api}/health", timeout=15)
    _require_ok(health, "health check")

    _ensure_features(sess, api, uid, auto_fix=args.auto_fix)
    _ensure_twin(sess, api, uid)

    rdb = redis.Redis.from_url(args.redis_url, decode_responses=True)
    raw = rdb.get(f"twin:features:{uid}")
    if raw:
        base = json.loads(raw)
    else:
        base = _load_features_from_local_parquet(uid)
        if not base:
            print(f"[error] Redis key twin:features:{uid} missing and no local parquet fallback found.")
            raise SystemExit(1)
        # Prime Redis so /twin/{user_id}/update can consume this feature state.
        rdb.set(f"twin:features:{uid}", json.dumps(base, default=str))
        print("[ok] Seeded Redis feature cache from local parquet.")

    base = _hydrate_base_income_fields(rdb, uid, base)

    if _num(base.get("income_30d"), 0.0) <= 0:
        print("[error] income_30d is still missing/zero after hydration.")
        print("[why] This is the root cause of simulation 422 (missing income).")
        print("[next] Run end-to-end stream workers + feature engine, then retry.")
        raise SystemExit(1)

    # Alternating stress/recovery profiles to force material twin changes.
    profiles = [
        {"name": "stress_A", "income_mult": 0.72, "essential_mult": 1.10, "disc_mult": 1.08, "cash_buffer_days": 4.0, "debit_failure_rate_90d": 0.34, "emi_burden_ratio": 0.58, "spending_volatility_index": 0.78, "income_stability_score": 0.30, "scenario": "supply_squeeze"},
        {"name": "recover_A", "income_mult": 1.08, "essential_mult": 0.97, "disc_mult": 0.96, "cash_buffer_days": 16.0, "debit_failure_rate_90d": 0.10, "emi_burden_ratio": 0.34, "spending_volatility_index": 0.40, "income_stability_score": 0.74, "scenario": "baseline"},
        {"name": "stress_B", "income_mult": 0.60, "essential_mult": 1.20, "disc_mult": 1.10, "cash_buffer_days": 2.0, "debit_failure_rate_90d": 0.52, "emi_burden_ratio": 0.72, "spending_volatility_index": 0.90, "income_stability_score": 0.18, "scenario": "gst_shock"},
        {"name": "recover_B", "income_mult": 1.12, "essential_mult": 0.94, "disc_mult": 0.95, "cash_buffer_days": 20.0, "debit_failure_rate_90d": 0.07, "emi_burden_ratio": 0.30, "spending_volatility_index": 0.35, "income_stability_score": 0.80, "scenario": "expansion"},
    ]

    print(f"[start] user_id={uid} steps={args.steps}")
    print("[info] Writing fluctuating feature states -> /twin/{user_id}/update -> /simulation/run")

    for i in range(args.steps):
        p = profiles[i % len(profiles)]
        feat = dict(base)

        feat["income_30d"] = max(1.0, _num(base.get("income_30d"), 1.0) * p["income_mult"])
        feat["income_90d"] = max(feat["income_30d"] * 3.0, _num(base.get("income_90d"), 0.0) * p["income_mult"])
        feat["essential_30d"] = max(1.0, _num(base.get("essential_30d"), feat["income_30d"] * 0.4) * p["essential_mult"])
        feat["essential_90d"] = max(feat["essential_30d"] * 3.0, _num(base.get("essential_90d"), 0.0) * p["essential_mult"])
        feat["discretionary_30d"] = max(0.0, _num(base.get("discretionary_30d"), feat["income_30d"] * 0.2) * p["disc_mult"])
        feat["discretionary_90d"] = max(feat["discretionary_30d"] * 3.0, _num(base.get("discretionary_90d"), 0.0) * p["disc_mult"])

        feat["cash_buffer_days"] = p["cash_buffer_days"]
        feat["debit_failure_rate_90d"] = p["debit_failure_rate_90d"]
        feat["emi_burden_ratio"] = p["emi_burden_ratio"]
        feat["spending_volatility_index"] = p["spending_volatility_index"]
        feat["income_stability_score"] = p["income_stability_score"]
        feat["computed_at"] = _now_iso()

        rdb.set(f"twin:features:{uid}", json.dumps(feat))

        upd = sess.post(f"{api}/twin/{uid}/update", timeout=30)
        upd_data = _require_ok(upd, f"twin update step={i+1}")

        sim_payload = {
            "user_id": uid,
            "num_simulations": 1000,
            "run_counterfactual": True,
            "scenario_overrides": {"scenario_name": p["scenario"]},
        }
        sim = sess.post(f"{api}/simulation/run", json=sim_payload, timeout=120)

        if sim.status_code == 422:
            detail = ""
            try:
                detail = str(sim.json().get("detail", ""))
            except Exception:
                detail = sim.text
            print(f"[error] simulation step={i+1} returned 422: {detail}")
            print("[hint] 422 fix: ensure /features/{user_id} exists and income_30d > 0, then /twin/{user_id}/update")
            if args.auto_fix:
                print("[fix] Auto-fix enabled: re-running phase3 + bootstrap once.")
                _run(["bash", "scripts/phase3_features.sh"])
                sess.post(f"{api}/twin/bootstrap", timeout=120)
            raise SystemExit(1)

        sim_data = _require_ok(sim, f"simulation step={i+1}")
        d90 = _num(
            sim_data.get("simulation_windows", {})
            .get("day_90", {})
            .get("default_probability", 0.0),
            0.0,
        )

        print(
            f"[step {i+1:02d}] {p['name']:<10} "
            f"version={upd_data.get('version')} "
            f"risk={_num(upd_data.get('risk_score'), 0.0):.4f} "
            f"dp90={d90:.4f}"
        )

        time.sleep(max(0.0, args.sleep_sec))

    hist_all = _require_ok(
        sess.get(f"{api}/twin/{uid}/history", params={"limit": 200, "material_only": "false"}, timeout=30),
        "history(all)",
    )
    hist_material = _require_ok(
        sess.get(f"{api}/twin/{uid}/history", params={"limit": 200, "material_only": "true"}, timeout=30),
        "history(material)",
    )
    print(
        f"[done] history_raw={hist_all.get('count')} "
        f"history_material={hist_material.get('count')}"
    )

    gstin = args.gstin.strip()
    if gstin:
        det = _require_ok(sess.get(f"{api}/explorer/{gstin}/details", timeout=40), "explorer details")
        print(f"[explorer] twin_timeline_points={len(det.get('twin_timeline', []))}")


if __name__ == "__main__":
    main()
PY