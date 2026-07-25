"""Browser / UI driver — headless-Chromium smoke of a web UI (generic).

Shells out to the Node script `browser.mjs` (Playwright). Verifies that every
declared view renders with no console/page errors, and runs optional click+assert
interactions. Gracefully skips if Node/Playwright isn't available.

Config (suites.browser):
  url: "http://localhost:8000"
  playwright_dir: "/tmp/pwtest"     # dir containing node_modules/playwright
                                    # (or set env TESTBENCH_PLAYWRIGHT_DIR)
  views:
    - {name: "engine",    click: ".tab-btn[data-tab='engine']"}
    - {name: "knowledge", click: ".tab-btn[data-tab='knowledge']"}
  interactions:
    - {name: "coach-preview", click: "button:has-text('Preview cue')", expect_selector: "#kp-result"}
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(cfg: dict) -> dict:
    checks = []

    def ck(name, ok, detail=""):
        checks.append(
            {"name": name, "status": "PASS" if ok else "FAIL", "detail": detail}
        )

    node = shutil.which("node")
    # env wins over config so a machine can override the (possibly placeholder) path.
    pw_dir = os.environ.get("TESTBENCH_PLAYWRIGHT_DIR") or cfg.get("playwright_dir")
    if not node:
        return {
            "passed": 0,
            "failed": 0,
            "skipped": 1,
            "checks": [
                {
                    "name": "browser",
                    "status": "PASS",
                    "detail": "node not found — skipped",
                }
            ],
            "note": "node/Playwright unavailable; browser suite skipped",
        }
    if not pw_dir or not (Path(pw_dir) / "node_modules" / "playwright").exists():
        return {
            "passed": 0,
            "failed": 0,
            "skipped": 1,
            "checks": [
                {
                    "name": "browser",
                    "status": "PASS",
                    "detail": "Playwright not installed (set playwright_dir / TESTBENCH_PLAYWRIGHT_DIR)",
                }
            ],
            "note": "Playwright unavailable; browser suite skipped",
        }

    payload = json.dumps(cfg)
    # ESM resolves `import 'playwright'` from the SCRIPT's directory (not cwd), so
    # copy the driver into pw_dir where node_modules/playwright lives.
    target = Path(pw_dir) / "_tb_browser.mjs"
    try:
        shutil.copy(HERE / "browser.mjs", target)
        proc = subprocess.run(
            [node, str(target), payload],
            cwd=pw_dir,
            capture_output=True,
            text=True,
            timeout=180,
        )
        out = proc.stdout.strip()
        # the script prints a final JSON line
        last = out.splitlines()[-1] if out else "{}"
        data = json.loads(last)
        for c in data.get("checks", []):
            ck(c["name"], c.get("ok", False), c.get("detail", ""))
        if not data.get("checks"):
            ck(
                "browser run",
                proc.returncode == 0,
                f"exit {proc.returncode}: {proc.stderr[-200:]}",
            )
    except Exception as e:  # noqa: BLE001
        ck("browser run", False, f"{type(e).__name__}: {e}")
    finally:
        try:
            target.unlink()
        except OSError:
            pass

    passed = sum(1 for c in checks if c["status"] == "PASS")
    failed = sum(1 for c in checks if c["status"] == "FAIL")
    return {"passed": passed, "failed": failed, "skipped": 0, "checks": checks}
