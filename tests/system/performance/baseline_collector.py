"""
Performance baseline collector.

Runs each critical path endpoint N times and persists p50/p95/p99/max
to baselines/<endpoint>.json. Committed to CI and compared by regression_detector.py.

Usage:
  python -m tests.system.performance.baseline_collector
  python -m tests.system.performance.baseline_collector --endpoint transfer_create
"""
import argparse
import asyncio
import json
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from tests.system.config import BASE_URL, SLA

BASELINE_DIR = Path(__file__).parent / "baselines"
BASELINE_DIR.mkdir(exist_ok=True)

CRITICAL_PATHS: List[Dict[str, Any]] = [
    {"name": "auth_register",    "method": "POST", "path": "/api/v1/auth/register",          "samples": 50},
    {"name": "auth_login",       "method": "POST", "path": "/api/v1/auth/login",             "samples": 100},
    {"name": "account_balance",  "method": "GET",  "path": "/api/v1/accounts/{id}/balance",  "samples": 200, "requires_auth": True},
    {"name": "transfer_create",  "method": "POST", "path": "/api/v1/transfers",              "samples": 100, "requires_auth": True},
    {"name": "transfer_get",     "method": "GET",  "path": "/api/v1/transfers/{id}",         "samples": 200, "requires_auth": True},
    {"name": "kyc_submit",       "method": "POST", "path": "/api/v1/kyc/submit",             "samples": 30,  "requires_auth": True},
    {"name": "invest_order",     "method": "POST", "path": "/api/v1/investments/orders",     "samples": 50,  "requires_auth": True},
    {"name": "portfolio_get",    "method": "GET",  "path": "/api/v1/portfolio",              "samples": 100, "requires_auth": True},
    {"name": "health",           "method": "GET",  "path": "/health",                        "samples": 200},
]


def _percentile(samples: List[float], pct: float) -> float:
    if not samples:
        return 0.0
    s = sorted(samples)
    idx = max(0, int(len(s) * pct / 100) - 1)
    return round(s[idx], 2)


def compute_stats(samples: List[float]) -> Dict[str, float]:
    return {
        "count": len(samples),
        "mean_ms": round(statistics.mean(samples), 2),
        "median_ms": round(statistics.median(samples), 2),
        "p95_ms": _percentile(samples, 95),
        "p99_ms": _percentile(samples, 99),
        "max_ms": round(max(samples), 2),
        "min_ms": round(min(samples), 2),
        "stdev_ms": round(statistics.stdev(samples), 2) if len(samples) > 1 else 0.0,
    }


async def _get_auth_token(client: httpx.AsyncClient) -> Optional[str]:
    """Register a one-off test user and return its access token."""
    user = {
        "email": f"baseline_{uuid.uuid4().hex[:8]}@test-noreply.example.com",
        "password": "Baseline@99!",
        "first_name": "Baseline",
        "last_name": "Runner",
        "date_of_birth": "1990-01-01",
        "phone": "+14155550111",
        "ssn_last4": "0000",
        "address": {"street": "1 Test St", "city": "San Francisco", "state": "CA", "zip": "94105"},
    }
    resp = await client.post("/api/v1/auth/register", json=user)
    if resp.status_code == 201:
        return resp.json().get("access_token")
    return None


async def _get_test_account(client: httpx.AsyncClient, token: str) -> Optional[str]:
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get("/api/v1/accounts", headers=headers)
    if resp.status_code == 200:
        accounts = resp.json().get("accounts", [])
        if accounts:
            return accounts[0]["account_id"]
    # Create one if none exist
    resp2 = await client.post("/api/v1/accounts",
        json={"account_type": "checking", "currency": "USD"}, headers=headers)
    if resp2.status_code == 201:
        return resp2.json()["account_id"]
    return None


async def _get_test_transfer(client: httpx.AsyncClient, token: str, account_id: str) -> Optional[str]:
    headers = {"Authorization": f"Bearer {token}"}
    dest = await client.post("/api/v1/accounts",
        json={"account_type": "savings"}, headers=headers)
    if dest.status_code != 201:
        return None
    dest_id = dest.json()["account_id"]
    payload = {
        "from_account_id": account_id,
        "to_account_id": dest_id,
        "amount_cents": 100,
        "currency": "USD",
        "idempotency_key": str(uuid.uuid4()),
    }
    r = await client.post("/api/v1/transfers", json=payload, headers=headers)
    if r.status_code in (200, 201, 202):
        return r.json()["transfer_id"]
    return None


async def measure_path(
    client: httpx.AsyncClient,
    path_def: Dict[str, Any],
    token: Optional[str],
    account_id: Optional[str],
    transfer_id: Optional[str],
) -> Dict[str, Any]:
    samples: List[float] = []
    errors = 0
    headers = {}
    if path_def.get("requires_auth") and token:
        headers["Authorization"] = f"Bearer {token}"

    # Resolve path templates
    url = path_def["path"]
    if "{id}" in url:
        if "account" in url and account_id:
            url = url.replace("{id}", account_id)
        elif "transfer" in url and transfer_id:
            url = url.replace("{id}", transfer_id)
        else:
            return {"name": path_def["name"], "skipped": True, "reason": "missing template variable"}

    for i in range(path_def["samples"]):
        # Build per-request payload for POST endpoints
        payload: Optional[Dict] = None
        if path_def["method"] == "POST":
            if "register" in url:
                payload = {
                    "email": f"bl_{uuid.uuid4().hex[:6]}@test-noreply.example.com",
                    "password": "Baseline@99!",
                    "first_name": "BL", "last_name": "User",
                    "date_of_birth": "1990-01-01", "phone": "+14155550100",
                    "ssn_last4": "0000",
                    "address": {"street": "1 Test", "city": "SF", "state": "CA", "zip": "94105"},
                }
            elif "login" in url:
                payload = {"email": "preseeded_0001@test-staging.example.com", "password": "PreSeeded@99!"}
            elif "transfers" in url and account_id:
                dest_resp = await client.post("/api/v1/accounts",
                    json={"account_type": "savings"}, headers=headers)
                dest_id = dest_resp.json().get("account_id", "acc_unknown") if dest_resp.status_code == 201 else "acc_unknown"
                payload = {
                    "from_account_id": account_id, "to_account_id": dest_id,
                    "amount_cents": 50, "currency": "USD",
                    "idempotency_key": str(uuid.uuid4()),
                }
            elif "kyc" in url:
                payload = {
                    "document_type": "passport", "document_number": "BL001",
                    "document_front_url": "https://test-assets.example.com/doc_front.jpg",
                    "document_back_url": "https://test-assets.example.com/doc_back.jpg",
                    "selfie_url": "https://test-assets.example.com/selfie.jpg",
                }
            elif "investments" in url:
                payload = {
                    "symbol": "VTI", "order_type": "market", "side": "buy",
                    "notional_usd": 5.0, "idempotency_key": str(uuid.uuid4()),
                }
            else:
                payload = {}

        start = time.perf_counter()
        try:
            if path_def["method"] == "GET":
                resp = await client.get(url, headers=headers)
            else:
                resp = await client.post(url, json=payload, headers=headers)
            elapsed_ms = (time.perf_counter() - start) * 1000
            if resp.status_code < 500:
                samples.append(elapsed_ms)
            else:
                errors += 1
        except Exception:
            errors += 1

        # Brief spacing to avoid hammering staging
        await asyncio.sleep(0.05)

    result = {
        "name": path_def["name"],
        "method": path_def["method"],
        "path": path_def["path"],
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "environment": "staging",
        "sla_p99_ms": SLA.api_p99_ms,
        "error_count": errors,
        **compute_stats(samples),
    }
    return result


async def collect_all(target: Optional[str] = None) -> List[Dict[str, Any]]:
    paths = CRITICAL_PATHS
    if target:
        paths = [p for p in CRITICAL_PATHS if p["name"] == target]
        if not paths:
            raise ValueError(f"Unknown endpoint: {target}. Valid: {[p['name'] for p in CRITICAL_PATHS]}")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        print(f"Collecting baselines against {BASE_URL}")
        token = await _get_auth_token(client)
        account_id = await _get_test_account(client, token) if token else None
        transfer_id = await _get_test_transfer(client, token, account_id) if (token and account_id) else None

        results = []
        for path_def in paths:
            print(f"  Measuring {path_def['name']} ({path_def['samples']} samples)...")
            result = await measure_path(client, path_def, token, account_id, transfer_id)
            results.append(result)

            baseline_file = BASELINE_DIR / f"{path_def['name']}.json"
            baseline_file.write_text(json.dumps(result, indent=2))
            sla_ok = result.get("p99_ms", 0) <= SLA.api_p99_ms
            print(f"    p99={result.get('p99_ms')}ms  SLA={'PASS' if sla_ok else 'FAIL'}")

    summary_file = BASELINE_DIR / "_summary.json"
    summary_file.write_text(json.dumps({
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "endpoints": [{
            "name": r["name"],
            "p99_ms": r.get("p99_ms"),
            "sla_pass": r.get("p99_ms", 999) <= SLA.api_p99_ms,
        } for r in results if not r.get("skipped")],
    }, indent=2))

    return results


def main():
    parser = argparse.ArgumentParser(description="Collect performance baselines")
    parser.add_argument("--endpoint", help="Single endpoint name to measure", default=None)
    args = parser.parse_args()
    asyncio.run(collect_all(target=args.endpoint))


if __name__ == "__main__":
    main()
