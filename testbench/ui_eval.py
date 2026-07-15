"""Gemini visual UI evaluator — let Gemini "see" a running web interface.

Claude can inspect a UI via the browser tools; this gives Gemini the same access:
screenshot a URL (headless Playwright) and have Gemini (multimodal, gemini-3.5-flash)
grade the *rendered* interface — design, consistency, accessibility — not just the
code. Works for ANY project's web UI (SAGE's dashboard, a product's app, ...).

This closes the loop: the Evaluator-Optimizer can now use a VISUAL evaluator for UI
work — Claude changes the code, the page is re-rendered, Gemini looks at the result.

Run:
  python testbench/ui_eval.py --url http://localhost:5173 \
     --criteria "consistent design system, accessible, no clashing styles" --out shot.png
  python testbench/ui_eval.py --image some-screenshot.png --criteria "..."

Needs: Node + Playwright (point TESTBENCH_PLAYWRIGHT_DIR at a node_modules/playwright)
for --url; the `gemini` CLI on PATH for the evaluation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

EVAL_SYSTEM = (
    "You are a senior product designer evaluating a screenshot of a web UI. Judge ONLY "
    "what you can see in the image against the criteria. Respond with ONLY a JSON object: "
    '{"score": <0-10>, "pass": <true|false>, "feedback": "<specific, visual, actionable: '
    'name what you see and what to change>"}. Be concrete about layout, colour consistency, '
    "contrast/accessibility, and visual hierarchy."
)


def screenshot(url: str, out: Path) -> Path:
    node = shutil.which("node")
    pw = os.environ.get("TESTBENCH_PLAYWRIGHT_DIR")
    if not node:
        raise RuntimeError("node not found")
    if not pw or not (Path(pw) / "node_modules" / "playwright").exists():
        raise RuntimeError("Playwright not found — set TESTBENCH_PLAYWRIGHT_DIR")
    target = Path(pw) / "_tb_screenshot.mjs"
    shutil.copy(
        HERE / "drivers" / "screenshot.mjs", target
    )  # ESM resolves playwright from pw
    try:
        p = subprocess.run(
            [node, str(target), url, str(out)],
            cwd=pw,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if p.returncode != 0 or not out.exists():
            raise RuntimeError(f"screenshot failed: {p.stderr[-200:]}")
        return out
    finally:
        try:
            target.unlink()
        except OSError:
            pass


def gemini_visual_eval(
    image: Path, criteria: str, model: str = "gemini-3.5-flash"
) -> dict:
    gem = shutil.which("gemini") or shutil.which("gemini.cmd")
    if not gem:
        raise RuntimeError("gemini CLI not found")
    # gemini reads an attached file with @<name>; run from the image's dir so the
    # relative @name resolves, and pass the prompt on stdin.
    prompt = (
        f"{EVAL_SYSTEM}\n\nCRITERIA:\n{criteria}\n\n"
        f"Evaluate this UI screenshot. @{image.name}\n\nJSON only."
    )
    p = subprocess.run(
        [gem, "-m", model],
        input=prompt,
        cwd=str(image.parent),
        capture_output=True,
        text=True,
        timeout=180,
        encoding="utf-8",
        errors="replace",
    )
    out = (p.stdout or "").strip()
    m = re.search(r"\{.*\}", out, re.DOTALL)
    if not m:
        return {
            "score": 0,
            "pass": False,
            "feedback": f"(no JSON from gemini) {out[:160]}",
        }
    try:
        return json.loads(m.group(0))
    except (ValueError, TypeError):
        return {"score": 0, "pass": False, "feedback": f"(unparseable) {out[:160]}"}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gemini visual UI evaluator")
    ap.add_argument("--url", help="URL to screenshot + evaluate")
    ap.add_argument("--image", help="existing screenshot to evaluate")
    ap.add_argument(
        "--criteria",
        default="consistent design system, accessible (good contrast, "
        "not colour-only), clear hierarchy, no clashing styles",
    )
    ap.add_argument(
        "--out",
        default="ui_eval_shot.png",
        help="where to save the screenshot (with --url)",
    )
    ap.add_argument("--model", default="gemini-3.5-flash")
    args = ap.parse_args(argv)

    if args.image:
        img = Path(args.image).resolve()
    elif args.url:
        img = screenshot(args.url, Path(args.out).resolve())
        print(f"screenshot -> {img}")
    else:
        ap.error("provide --url or --image")

    result = gemini_visual_eval(img, args.criteria, args.model)
    print(f"\n=== Gemini visual eval ({args.model}) ===")
    print(f"  score: {result.get('score')}  pass: {result.get('pass')}")
    print(f"  feedback: {result.get('feedback')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
