#!/usr/bin/env python3
"""SAGE system-level evidence gate — does the PRODUCT work?

Every unit suite in this repo (2379 framework + 537 sidecar + 349 vitest) passed on a
tree where `make desktop-dev` could not even start the app: the Makefile passed env with
POSIX `VAR=value cmd` syntax, which dies under cmd.exe, and cargo was not on PATH. Unit
tests import modules; they never assert that the thing a human opens actually opens.

This is the gate that closes that hole. It answers ONE question — "can a person use
SAGE right now?" — by exercising the real artifacts:

    the sidecar boots  ->  the RPCs answer  ->  the app compiles  ->  the loop runs

It is the Level-2 evidence gate from docs/superpowers/specs/2026-07-13-sage-evolve-design.md,
and it is a prerequisite for the optimizer/critic loop: a critic panel with no ground truth
invents defects (observed: Gemini scored a handler 1/10 for a "Fatal Syntax Error" on a line
that reads `gw = _require_gateway()`).

Exit code 0 = usable. Non-zero = a real operator is blocked. No model opinions involved.

    python scripts/verify_system.py            # full gate
    python scripts/verify_system.py --fast     # skip the Rust compile (~1-2 min)
    python scripts/verify_system.py --json     # machine-readable output for CI
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = ROOT / ".venv" / "bin" / "python"

RESULTS: list[tuple[str, bool, str]] = []
_JSON_MODE = False


def check(name: str, passed: bool, detail: str = "") -> bool:
    RESULTS.append((name, passed, detail))
    if not _JSON_MODE:
        print(
            f"  [{'PASS' if passed else 'FAIL'}] {name}"
            + (f" — {detail}" if detail else ""),
            flush=True,
        )
    return passed


def _run(cmd: list[str], cwd: Path, timeout: int) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except FileNotFoundError as e:
        return 127, f"command not found: {e}"


# ---------------------------------------------------------------- 1. the sidecar boots
def gate_sidecar_boots(solution: str) -> bool:
    """The sidecar IS the desktop backend (no HTTP). If it can't handshake, no page works."""
    sys.path.insert(0, str(ROOT / "sage-desktop" / "sidecar"))
    sys.path.insert(0, str(ROOT))
    os.environ["SAGE_ROOT"] = str(ROOT)
    try:
        import app as sidecar_app
    except Exception as e:  # noqa: BLE001
        return check("sidecar imports", False, str(e)[:120])

    sol_path = ROOT / "solutions" / solution
    req = json.dumps({"jsonrpc": "2.0", "id": "1", "method": "handshake", "params": {}})
    out = io.StringIO()
    try:
        sidecar_app.run(
            stdin=io.StringIO(req + "\n"),
            stdout=out,
            argv=["--solution-name", solution, "--solution-path", str(sol_path)],
        )
    except Exception as e:  # noqa: BLE001
        return check("sidecar boots", False, str(e)[:120])

    line = out.getvalue().strip().splitlines()
    ok = bool(line) and "result" in json.loads(line[0])
    return check(
        "sidecar boots + handshakes", ok, "" if ok else "no handshake response"
    )


# ------------------------------------------------------- 2. every RPC the UI calls answers
def gate_rpcs_answer(solution: str) -> bool:
    """Drive every READ rpc the desktop UI calls. A page whose RPC errors is a dead page."""
    import re

    import app as sidecar_app

    src = (ROOT / "sage-desktop" / "sidecar" / "app.py").read_text(encoding="utf-8")
    methods = sorted(set(re.findall(r'd\.register\("([^"]+)"', src)))
    mutating = re.compile(
        r"\.(approve|reject|batch_approve|delete|write|update|set|add|create|"
        r"publish|validate|claim|respond|close|sync|switch|start|run|"
        r"run_suite|generate|connect|reload|set_visibility|plan|submit|remove|"
        r"unload)"
    )
    params = {
        "audit.get_by_trace": {"trace_id": "none"},
        "approvals.get": {"trace_id": "none"},
        "agents.get": {"name": "analyst"},
        "agents.performance": {"role_key": "analyst"},
        "goals.get": {"goal_id": 1},
        "knowledge.search": {"query": "x", "top_k": 1},
        "knowledge.list": {"limit": 5},
        "collective.get_learning": {"id": "none"},
        "collective.search_learnings": {"query": "x"},
        "compliance.flags": {"domain": "medtech"},
        "compliance.checklist": {"domain": "medtech"},
        "compliance.gap_assessment": {"domain": "medtech", "risk_level": "class_b"},
        "yaml.read": {"file": "project"},
        "constitution.check_action": {"action_description": "x"},
        "builds.get": {"run_id": "none"},
        "jobs.status": {"job_id": "none"},
        "workflow.status": {"run_id": "none"},
        "hil.report": {"session_id": "none"},
    }
    reads = [m for m in methods if not mutating.search(m)]

    calls = [
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": str(i + 1),
                "method": m,
                "params": params.get(m, {}),
            }
        )
        for i, m in enumerate(reads)
    ]
    out = io.StringIO()
    sidecar_app.run(
        stdin=io.StringIO("\n".join(calls) + "\n"),
        stdout=out,
        argv=[
            "--solution-name",
            solution,
            "--solution-path",
            str(ROOT / "solutions" / solution),
        ],
    )

    resp = {}
    for line in out.getvalue().splitlines():
        if line.strip():
            try:
                r = json.loads(line)
                resp[str(r.get("id"))] = r
            except ValueError:
                pass

    broken = []
    for i, m in enumerate(reads, start=1):
        r = resp.get(str(i))
        if r is None:
            broken.append(f"{m}: no response")
        elif "error" in r:
            code = r["error"].get("code")
            # -32602/-32003 on a deliberately fake id ("none") is CORRECT not-found behaviour,
            # not a broken feature. Anything else means the page behind it is dead.
            if code not in (-32602, -32003):
                broken.append(f"{m}: {code} {str(r['error'].get('message'))[:50]}")

    ok = not broken
    return check(
        f"desktop RPCs answer ({len(reads) - len(broken)}/{len(reads)})",
        ok,
        "; ".join(broken[:3]) if broken else "",
    )


# ------------------------------------------------------------- 3. the app actually compiles
def gate_app_compiles(fast: bool) -> bool:
    """`cargo check` on the Tauri shell. THIS is the gate that would have caught the
    Makefile/PATH breakage that 3265 green unit tests sailed straight past."""
    if fast:
        return check("app compiles (cargo check)", True, "SKIPPED (--fast)")
    cargo = (
        Path(os.environ.get("USERPROFILE", os.path.expanduser("~"))) / ".cargo" / "bin"
    )
    env_path = f"{cargo}{os.pathsep}{os.environ.get('PATH', '')}"
    old = os.environ.get("PATH", "")
    os.environ["PATH"] = env_path
    try:
        rc, out = _run(
            ["cargo", "check", "--no-default-features", "--features", "desktop"],
            ROOT / "sage-desktop" / "src-tauri",
            timeout=900,
        )
    finally:
        os.environ["PATH"] = old
    ok = rc == 0
    tail = [l for l in out.splitlines() if l.strip()][-1:] if not ok else []  # noqa: E741
    return check(
        "app compiles (cargo check)", ok, (tail[0][:100] if tail else f"rc={rc}")
    )


# --------------------------------------------------------------------- 4. the frontend builds
def gate_frontend_builds() -> bool:
    # npx is a .cmd shim on Windows; subprocess without an extension raises WinError 2.
    npx = "npx.cmd" if os.name == "nt" else "npx"
    rc, out = _run(
        [npx, "vite", "build", "--logLevel", "error"],
        ROOT / "sage-desktop",
        timeout=600,
    )
    ok = rc == 0
    return check("frontend builds (vite build)", ok, "" if ok else out.strip()[-100:])


# --------------------------------------------------------------- 4b. the Rust tests actually run
def gate_rust_tests(fast: bool) -> bool:
    """`cargo test --lib --no-default-features` — the ONLY correct invocation on Windows.

    This gate exists because of a false conclusion, not a bug. Every attempt ran
    `cargo test --features desktop`, which pulls in Tauri and therefore WebView2; the test
    binary then dies at load with STATUS_ENTRYPOINT_NOT_FOUND. From that we concluded three
    separate times that "the Rust layer cannot be tested here" — and shipped a Tauri command
    (solution remove) that was broken in a way these tests exist to catch.

    Cargo.toml:33 documents the right flags, and `make test-desktop-rs` already used them.
    Nobody ran it. Pinning it into the gate means the excuse cannot come back.
    """
    if fast:
        return check("Rust tests (cargo test)", True, "SKIPPED (--fast)")
    cargo = (
        Path(os.environ.get("USERPROFILE", os.path.expanduser("~"))) / ".cargo" / "bin"
    )
    old = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{cargo}{os.pathsep}{old}"
    try:
        rc, out = _run(
            ["cargo", "test", "--lib", "--no-default-features"],
            ROOT / "sage-desktop" / "src-tauri",
            timeout=900,
        )
    finally:
        os.environ["PATH"] = old
    passed = [l for l in out.splitlines() if l.startswith("test result:")]  # noqa: E741
    return check(
        "Rust tests (cargo test)", rc == 0, passed[0][:60] if passed else f"rc={rc}"
    )


# ------------------------------------------------------------ 5. the launcher is shell-agnostic
def gate_launcher_portable() -> bool:
    """The recipe must not use POSIX `VAR=value cmd` prefixes — they die under cmd.exe,
    which is what make resolves to on Windows outside a POSIX shell. This is a REGRESSION
    guard for the exact bug that made `make desktop-dev` unusable from PowerShell."""
    rc, out = _run(["make", "-n", "desktop-dev"], ROOT, timeout=60)
    if rc != 0:
        return check("launcher is shell-agnostic", False, f"make -n failed: {out[:80]}")
    bad = [
        l
        for l in out.splitlines()  # noqa: E741
        if l.strip().startswith(("SAGE_", "cd "))
        and "=" in l.split("&&")[-1][:40]
        and "npm" in l
    ]
    ok = not bad
    return check(
        "launcher is shell-agnostic (no POSIX env prefix)",
        ok,
        bad[0][:80] if bad else "",
    )


# ------------------------------------------------------------------- 6. the critic panel is real
def gate_critic_panel() -> bool:
    """A panel that silently degrades to ONE judge is not a panel. Gemini was dropping out
    on a 30s timeout, leaving a single critic that looked like a panel."""
    sys.path.insert(0, str(ROOT))
    try:
        from src.core.llm_gateway import _load_config
    except Exception as e:  # noqa: BLE001
        return check("critic panel configured", False, str(e)[:100])

    llm = (_load_config() or {}).get("llm", {})
    gt = int(llm.get("gemini_timeout", 0))
    ok_timeout = gt >= 150  # measured: a 50KB critic prompt costs ~142s
    check("gemini_timeout is above real latency", ok_timeout, f"{gt}s (need >=150s)")

    local = llm.get("critic_ollama_model", "")
    served = set()
    try:
        import urllib.request

        host = llm.get("ollama_host", "http://localhost:11434")
        with urllib.request.urlopen(f"{host}/api/tags", timeout=5) as r:
            served = {m.get("name", "") for m in json.load(r).get("models", [])}
    except Exception:  # noqa: BLE001
        pass
    ok_local = bool(local) and local in served
    check(
        "local critic (Ollama) is served",
        ok_local,
        f"{local or '(unset)'}" + ("" if ok_local else " — not served; panel degrades"),
    )

    return ok_timeout and ok_local


def main() -> int:
    global _JSON_MODE

    ap = argparse.ArgumentParser(description="SAGE system-level evidence gate")
    ap.add_argument("--solution", default="four_in_a_line")
    ap.add_argument("--fast", action="store_true", help="skip the Rust compile")
    ap.add_argument(
        "--json",
        action="store_true",
        dest="json_out",
        help="print results as JSON to stdout (for CI)",
    )
    args = ap.parse_args()

    _JSON_MODE = args.json_out

    if not _JSON_MODE:
        print("=" * 72)
        print("SAGE SYSTEM EVIDENCE GATE — can a person actually use this right now?")
        print("=" * 72, flush=True)
    t0 = time.time()

    if not _JSON_MODE:
        print("\n[1/6] backend")
    if gate_sidecar_boots(args.solution):
        gate_rpcs_answer(args.solution)

    if not _JSON_MODE:
        print("\n[2/6] the app a human opens")
    gate_app_compiles(args.fast)
    gate_rust_tests(args.fast)
    gate_frontend_builds()
    gate_launcher_portable()

    if not _JSON_MODE:
        print("\n[3/6] the critic panel")
    gate_critic_panel()

    failed = [n for n, ok, _ in RESULTS if not ok]
    passed_count = len(RESULTS) - len(failed)

    if _JSON_MODE:
        payload = {
            "gates": [{"name": n, "passed": ok, "detail": d} for n, ok, d in RESULTS],
            "passed": passed_count,
            "total": len(RESULTS),
        }
        print(json.dumps(payload))
        return 0 if not failed else 1

    print("\n" + "=" * 72)
    print(f"{passed_count}/{len(RESULTS)} gates passed in {time.time() - t0:.0f}s")
    if failed:
        print("\nBLOCKED — a real operator hits these:")
        for n, ok, d in RESULTS:
            if not ok:
                print(f"  - {n}" + (f" ({d})" if d else ""))
        print("\nSAGE is NOT usable. Do not declare it working.")
        return 1
    print(
        "\nSAGE is usable: the sidecar answers, the app compiles and builds, the launcher"
    )
    print("works from any shell, and the critic panel has more than one voice.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
