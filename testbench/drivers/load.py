"""Load / concurrency driver — N concurrent user journeys + a read-throughput burst.

Generic: a journey is a list of GET paths every simulated user walks; the burst
fires M concurrent reads at one endpoint. Stdlib only (threads + urllib).

Config (suites.load):
  base_url: "http://localhost:8000"
  users: 20
  journey: ["/api/v1/overview", "/api/v1/modules", "/api/v1/personas"]
  burst:
    endpoint: "/api/v1/engine/profile"
    n: 200
  max_p95_s: 20            # optional gate: fail if journey p95 exceeds this
"""
from __future__ import annotations

import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor


def _get(url, timeout=30):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            r.read()
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:  # noqa: BLE001
        return -1


def run(cfg: dict) -> dict:
    # Force IPv4 (see api.py) — 'localhost'->::1 makes urllib wait on the IPv6
    # connect, which would dominate the load timings and report fake throughput.
    base = cfg.get("base_url", "http://localhost:8000").rstrip("/").replace("localhost", "127.0.0.1")
    users = int(cfg.get("users", 20))
    journey = cfg.get("journey", ["/health"])
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    # N concurrent journeys
    def one_user(_i):
        durs = []
        ok = True
        for p in journey:
            t0 = time.perf_counter()
            code = _get(base + p)
            durs.append(time.perf_counter() - t0)
            if code not in (200, 404):
                ok = False
        return ok, durs

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=min(users, 64)) as ex:
        results = list(ex.map(one_user, range(users)))
    wall = time.perf_counter() - t0
    ok_users = sum(1 for ok, _ in results if ok)
    all_durs = sorted(d for _, ds in results for d in ds)
    p95 = all_durs[min(len(all_durs) - 1, int(len(all_durs) * 0.95))] if all_durs else 0
    ck(f"{users} concurrent journeys succeed", ok_users == users,
       f"{ok_users}/{users} ok in {wall:.1f}s, p95={p95:.2f}s")
    if cfg.get("max_p95_s"):
        ck(f"journey p95 < {cfg['max_p95_s']}s", p95 <= cfg["max_p95_s"], f"p95={p95:.2f}s")

    # read-throughput burst
    burst = cfg.get("burst")
    if burst:
        n = int(burst.get("n", 200))
        url = base + burst["endpoint"]
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=min(n, 64)) as ex:
            codes = list(ex.map(lambda _i: _get(url), range(n)))
        dt = time.perf_counter() - t0
        oks = sum(1 for c in codes if c == 200)
        ck(f"read burst {n} concurrent", oks == n,
           f"{oks}/{n} ok in {dt:.2f}s -> {n/dt:.0f} req/s")

    passed = sum(1 for c in checks if c["status"] == "PASS")
    failed = sum(1 for c in checks if c["status"] == "FAIL")
    return {"passed": passed, "failed": failed, "skipped": 0, "checks": checks}
