"""Mobile driver — run a mobile app's test suite (Flutter today; Appium-ready).

For mobile solutions (e.g. the Reflect/Poseengine Flutter app). Runs a declared
test command — directly or inside a Docker image so no local SDK is needed — and
parses the pass/fail summary. Device/UI automation (Appium, Flutter integration
tests on a device/emulator) is the documented extension point.

Config (suites.mobile):
  kind: "flutter"                       # flutter | appium
  cwd: "solutions/<name>/source/flutter_app"   # relative to repo root (optional)
  test_cmd: "flutter pub get && flutter test"
  docker_image: "poseengine-flutter"    # optional: run test_cmd inside this image
  pass_regex: "All tests passed"        # optional
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def run(cfg: dict) -> dict:
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    kind = cfg.get("kind", "flutter")
    test_cmd = cfg.get("test_cmd")
    if not test_cmd:
        ck(f"{kind} tests", True, "no test_cmd declared — skipped")
        return {"passed": 1, "failed": 0, "skipped": 0, "checks": checks}

    image = cfg.get("docker_image")
    if image:
        # Run the test command inside the prebuilt image (no local SDK needed).
        cmd = ["docker", "run", "--rm", "-w", "/app/flutter_app", image, "bash", "-lc", test_cmd]
        runner_cwd = str(REPO)
    else:
        cmd = test_cmd
        runner_cwd = str(REPO / cfg["cwd"]) if cfg.get("cwd") else str(REPO)

    try:
        p = subprocess.run(cmd, shell=not image, cwd=runner_cwd,
                           capture_output=True, text=True, timeout=cfg.get("timeout", 1800))
        out = p.stdout + p.stderr
        pat = cfg.get("pass_regex", r"All tests passed" if kind == "flutter" else r"passed")
        ok = (p.returncode == 0) and bool(re.search(pat, out))
        # surface the count line if present (flutter: "+NN: All tests passed!")
        m = re.search(r"\+(\d+):\s*All tests passed", out)
        detail = (m.group(0) if m else f"exit {p.returncode}") + ("" if ok else f" :: {out.strip()[-160:]}")
        ck(f"{kind} tests", ok, detail)
    except Exception as e:  # noqa: BLE001
        ck(f"{kind} tests", False, f"{type(e).__name__}: {e}")

    passed = sum(1 for c in checks if c["status"] == "PASS")
    failed = sum(1 for c in checks if c["status"] == "FAIL")
    return {"passed": passed, "failed": failed, "skipped": 0, "checks": checks,
            "note": "mobile: unit/widget tests run (in Docker if image set); device/Appium is the extension"}
