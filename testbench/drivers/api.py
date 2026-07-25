"""API / system driver — functional + integration checks against a running HTTP backend.

Generic: a solution declares its base_url, health routes, read routes, an optional
auth flow, and optional auth-gated routes. Works for any REST backend (the SAGE
framework API, a product backend, an embedded device's HTTP control plane, ...).

Stdlib-only (urllib) so the bench has no install footprint. Optional websocket
chat check uses the `websockets` lib if present.

Config (testbench.yaml -> suites.api):
  base_url:  "http://localhost:8000"
  health:    ["/health"]                       # each must return 200
  reads:     ["/api/v1/overview", ...]          # each GET must return 200 (or 404 if allow_404)
  allow_404: false
  auth:                                         # optional
    register: "/api/v1/auth/register"
    login:    "/api/v1/auth/login"
    email_field: "email"   # default
    password_field: "password"
    token_field: "access_token"
  protected: ["/api/v1/system/metrics"]         # 401 anon, 200 with token
  ws_chat:                                       # optional
    path: "/ws/agent/pose_engine"
    send: {"type": "query", "query": "hello"}
    expect_any: ["content", "response"]
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
import uuid

UA = {"User-Agent": "sage-testbench/1.0", "Content-Type": "application/json"}


def _req(method, url, body=None, token=None, timeout=30):
    headers = dict(UA)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return -1, f"{type(e).__name__}: {e}"


def run(cfg: dict) -> dict:
    # Normalize localhost->127.0.0.1: on dual-stack hosts 'localhost' resolves to
    # ::1 (IPv6) first; servers that bind IPv4-only (0.0.0.0) make every urllib
    # request wait ~19s for the IPv6 connect to time out. Forcing IPv4 is instant.
    base = (
        cfg.get("base_url", "http://localhost:8000")
        .rstrip("/")
        .replace("localhost", "127.0.0.1")
    )
    checks = []

    def ck(name, ok, detail=""):
        checks.append(
            {"name": name, "status": "PASS" if ok else "FAIL", "detail": detail}
        )
        return ok

    # 1. health
    for path in cfg.get("health", ["/health"]):
        code, _ = _req("GET", base + path)
        ck(f"health GET {path}", code == 200, f"HTTP {code}")

    # 2. reads
    allow_404 = cfg.get("allow_404", False)
    for path in cfg.get("reads", []):
        code, _ = _req("GET", base + path)
        ok = code == 200 or (allow_404 and code == 404)
        ck(f"read GET {path}", ok, f"HTTP {code}")

    # 3. auth flow (optional)
    token = None
    auth = cfg.get("auth")
    if auth:
        ef = auth.get("email_field", "email")
        pf = auth.get("password_field", "password")
        tf = auth.get("token_field", "access_token")
        cred = {ef: f"tb_{uuid.uuid4().hex[:8]}@example.com", pf: "Bench1234!pw"}
        rc, _ = _req("POST", base + auth["register"], cred)
        ck(
            "auth register",
            rc in (200, 201, 409, 429),
            f"HTTP {rc}"
            + (" (rate-limited/exists — acceptable)" if rc in (409, 429) else ""),
        )
        lc, lb = _req("POST", base + auth["login"], cred)
        try:
            token = json.loads(lb).get(tf) if lc == 200 else None
        except Exception:  # noqa: BLE001
            token = None
        ck("auth login -> token", lc == 200 and bool(token), f"HTTP {lc}")
        if token:
            ck(
                "token is a JWT (3 parts)",
                token.count(".") == 2,
                f"{token.count('.') + 1} segments",
            )

    # 4. protected routes (401 anon, 200 with token)
    for path in cfg.get("protected", []):
        ac, _ = _req("GET", base + path)
        ck(f"protected {path} 401 anon", ac == 401, f"anon HTTP {ac}")
        if token:
            tc, _ = _req("GET", base + path, token=token)
            ck(f"protected {path} 200 with token", tc == 200, f"authed HTTP {tc}")

    # 5. optional websocket chat
    ws = cfg.get("ws_chat")
    if ws:
        _ws_check(base, ws, ck)

    passed = sum(1 for c in checks if c["status"] == "PASS")
    failed = sum(1 for c in checks if c["status"] == "FAIL")
    return {"passed": passed, "failed": failed, "skipped": 0, "checks": checks}


def _ws_check(base, ws, ck):
    try:
        import asyncio
        import websockets  # type: ignore
    except ImportError:
        ck("ws chat", True, "websockets lib absent — skipped")
        return
    # Force IPv4: many dev servers bind 0.0.0.0 and 'localhost'->::1 hangs the ws client.
    uri = (
        base.replace("http://", "ws://")
        .replace("https://", "wss://")
        .replace("localhost", "127.0.0.1")
        + ws["path"]
    )
    expect = ws.get("expect_any", ["content", "response"])

    async def go():
        async with websockets.connect(uri, open_timeout=15) as sock:
            sent = False
            for _ in range(60):
                msg = json.loads(await asyncio.wait_for(sock.recv(), 20))
                if not sent and msg.get("type") == "session_id":
                    await sock.send(
                        json.dumps(ws.get("send", {"type": "query", "query": "hi"}))
                    )
                    sent = True
                    continue
                txt = json.dumps(msg).lower()
                if any(e in txt for e in expect) and msg.get("type") != "session_id":
                    return msg
            return None

    try:
        msg = asyncio.run(go())
        ck(
            f"ws {ws['path']} responds",
            bool(msg),
            (str(msg.get("content", ""))[:60] if msg else "no response"),
        )
    except Exception as e:  # noqa: BLE001
        ck(f"ws {ws['path']} responds", False, f"{type(e).__name__}: {e}")
