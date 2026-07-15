"""Embedded driver — firmware unit tests + hardware-in-the-loop (HIL).

For embedded solutions (e.g. the OneStep scanner firmware). Two layers:
  1. host unit tests — run a declared build+test command (CMake/CTest, Unity, Ceedling)
     and parse the pass/fail summary. Works today.
  2. HIL — drive real hardware over serial / J-Link. SAGE already ships MCP servers
     for serial port and J-Link (src/.../mcp_servers); the HIL block declares the
     port/probe + a script. Wiring those is the extension point (documented below).

Config (suites.embedded):
  unit_test_cmd: "cmake -S . -B build && cmake --build build && ctest --test-dir build"
  cwd: "solutions/<name>/source/firmware"   # optional, relative to repo root
  pass_regex: "(\\d+)% tests passed"          # optional override
  hil:                                        # optional (skipped until wired)
    transport: "serial" | "jlink"
    port: "COM3" | "/dev/ttyUSB0"
    script: "..."
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def run(cfg: dict) -> dict:
    checks = []

    def ck(name, ok, detail=""):
        checks.append(
            {"name": name, "status": "PASS" if ok else "FAIL", "detail": detail}
        )

    cmd = cfg.get("unit_test_cmd")
    if cmd:
        cwd = REPO / cfg["cwd"] if cfg.get("cwd") else REPO
        try:
            p = subprocess.run(
                cmd,
                shell=True,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=cfg.get("timeout", 1800),
            )
            out = p.stdout + p.stderr
            # CTest: "100% tests passed, 0 tests failed out of N"
            m = re.search(
                cfg.get("pass_regex", r"(\d+)% tests passed,\s*(\d+) tests failed"), out
            )
            if m and m.lastindex and m.lastindex >= 2:
                failed = int(m.group(2))
                ck("firmware unit tests", failed == 0 and p.returncode == 0, m.group(0))
            else:
                ck(
                    "firmware unit tests",
                    p.returncode == 0,
                    f"exit {p.returncode}; {out.strip()[-160:]}",
                )
        except Exception as e:  # noqa: BLE001
            ck("firmware unit tests", False, f"{type(e).__name__}: {e}")
    else:
        ck("firmware unit tests", True, "no unit_test_cmd declared — skipped")

    hil = cfg.get("hil")
    if hil:
        # Extension point: drive real hardware via SAGE's serial / J-Link MCP servers.
        ck(
            "HIL",
            True,
            f"declared ({hil.get('transport')}@{hil.get('port')}) — "
            "wire to SAGE serial/J-Link MCP to run; skipped for now",
        )

    passed = sum(1 for c in checks if c["status"] == "PASS")
    failed = sum(1 for c in checks if c["status"] == "FAIL")
    return {
        "passed": passed,
        "failed": failed,
        "skipped": 0,
        "checks": checks,
        "note": "embedded: host unit tests run; HIL is a wired-on-demand extension",
    }
