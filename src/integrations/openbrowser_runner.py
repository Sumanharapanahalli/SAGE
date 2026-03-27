"""
SAGE Framework — OpenBrowser Runner (gstack Integration)
=========================================================
Domain-specific execution for browser-based testing, QA, and UX validation.

Integrates with gstack's persistent headless Chromium daemon for:
  - Real browser QA testing (navigate, click, fill, screenshot)
  - Visual regression testing
  - Accessibility auditing (WCAG via real DOM inspection)
  - Security scanning (OWASP checks via browser interaction)
  - Performance benchmarking (Core Web Vitals, page load times)

Workflow: navigate → interact → verify → screenshot → report

gstack provides $B commands (~100ms latency per command) via a persistent
Chromium daemon that maintains cookies, tabs, and login sessions.

The runner gracefully degrades:
  Tier 1: gstack $B commands (real Chromium, full interaction)
  Tier 2: LLM simulation (generate test reports without real browser)

Roles: qa_engineer, system_tester, ux_designer (browser testing aspect)
Docker: none required (gstack runs locally)
"""

import json
import logging
import os
import shutil
import subprocess
import time
from typing import Any, Optional

from src.integrations.base_runner import (
    BaseRunner, RunResult, VerificationReport, VerificationFinding,
    VerificationSeverity, Exercise, ExerciseScore,
    register_supplementary_runner, BROWSER_ROLES,
)

logger = logging.getLogger("Runner.openbrowser")


def _gstack_available() -> bool:
    """Check if gstack is installed and the $B binary is available."""
    # Check standard install locations
    locations = [
        os.path.expanduser("~/.claude/skills/gstack/browse/bin/browse"),
        os.path.expanduser("~/.claude/skills/gstack/bin/browse"),
        ".claude/skills/gstack/browse/bin/browse",
    ]
    for loc in locations:
        if os.path.isfile(loc):
            return True
    # Check if $B is on PATH (compiled binary)
    return shutil.which("browse") is not None


def _find_browse_binary() -> str:
    """Find the gstack browse binary path."""
    locations = [
        os.path.expanduser("~/.claude/skills/gstack/browse/bin/browse"),
        os.path.expanduser("~/.claude/skills/gstack/bin/browse"),
        ".claude/skills/gstack/browse/bin/browse",
    ]
    for loc in locations:
        if os.path.isfile(loc):
            return loc
    path = shutil.which("browse")
    if path:
        return path
    return ""


def _run_browse_command(cmd: str, timeout: int = 30) -> dict:
    """
    Execute a gstack $B command and return the result.

    Returns dict with: success (bool), output (str), error (str), duration_ms (int).
    """
    binary = _find_browse_binary()
    if not binary:
        return {
            "success": False,
            "output": "",
            "error": "gstack browse binary not found",
            "duration_ms": 0,
        }

    start = time.monotonic()
    try:
        result = subprocess.run(
            [binary] + cmd.split(),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "success": result.returncode == 0,
            "output": result.stdout[:5000],
            "error": result.stderr[:2000] if result.returncode != 0 else "",
            "duration_ms": duration_ms,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": f"Command timed out after {timeout}s",
            "duration_ms": timeout * 1000,
        }
    except Exception as exc:
        return {
            "success": False,
            "output": "",
            "error": str(exc),
            "duration_ms": int((time.monotonic() - start) * 1000),
        }


class OpenBrowserRunner(BaseRunner):
    """Browser testing and QA execution runner using gstack's Chromium daemon."""

    def __init__(self):
        super().__init__(
            name="openbrowser",
            roles=list(BROWSER_ROLES),
            docker_image="",  # no docker — gstack runs locally
        )
        self._gstack_available = None  # lazy check

    def _check_gstack(self) -> bool:
        """Lazy check for gstack availability."""
        if self._gstack_available is None:
            self._gstack_available = _gstack_available()
            if self._gstack_available:
                self.logger.info("gstack browser daemon available")
            else:
                self.logger.info("gstack not installed — browser tests will use LLM simulation")
        return self._gstack_available

    def execute(self, task, workspace, sandbox_handle=None):
        run_id = self._new_run_id()
        try:
            description = task.get("description", "")
            task_type = task.get("task_type", "BROWSER_QA")
            url = task.get("payload", {}).get("url", "")

            if self._check_gstack() and url:
                return self._execute_with_gstack(run_id, task_type, description, url)
            else:
                return self._execute_with_llm(run_id, task_type, description, url)

        except Exception as exc:
            self.logger.error("OpenBrowser execute failed: %s", exc)
            return self._make_error(run_id, str(exc))

    def _execute_with_gstack(self, run_id: str, task_type: str, description: str, url: str) -> RunResult:
        """Execute browser test using real gstack Chromium daemon."""
        results = []
        screenshots = []
        errors = []
        metrics = {}

        # Step 1: Navigate to URL
        nav = _run_browse_command(f"goto {url}")
        results.append(f"Navigation: {'OK' if nav['success'] else 'FAILED'} ({nav['duration_ms']}ms)")
        if not nav["success"]:
            errors.append(f"Navigation failed: {nav['error']}")

        # Step 2: Take interactive snapshot (see all elements)
        snap = _run_browse_command("snapshot -i")
        results.append(f"Snapshot: {len(snap['output'])} chars")
        page_structure = snap["output"]

        # Step 3: Check console for errors
        console = _run_browse_command("console")
        console_errors = [line for line in console["output"].split("\n")
                         if "error" in line.lower() or "exception" in line.lower()]
        metrics["console_errors"] = len(console_errors)
        if console_errors:
            results.append(f"Console errors: {len(console_errors)}")
            errors.extend(console_errors[:5])

        # Step 4: Check network for failed requests
        network = _run_browse_command("network")
        failed_requests = [line for line in network["output"].split("\n")
                          if any(code in line for code in ["4xx", "5xx", "failed", "error"])]
        metrics["failed_requests"] = len(failed_requests)

        # Step 5: Take screenshot
        screenshot_path = f"/tmp/sage_qa_{run_id[:8]}.png"
        screenshot = _run_browse_command(f"screenshot {screenshot_path}")
        if screenshot["success"]:
            screenshots.append({"path": screenshot_path, "type": "screenshot", "size": 0})

        # Step 6: Check basic accessibility
        a11y = _run_browse_command("snapshot -a")
        metrics["accessibility_tree_size"] = len(a11y["output"])

        # Step 7: Performance metrics via JS
        perf = _run_browse_command('js "JSON.stringify(performance.timing)"')
        if perf["success"]:
            try:
                timing = json.loads(perf["output"])
                if isinstance(timing, dict):
                    load_time = timing.get("loadEventEnd", 0) - timing.get("navigationStart", 0)
                    metrics["page_load_ms"] = load_time
                    metrics["dom_ready_ms"] = timing.get("domContentLoadedEventEnd", 0) - timing.get("navigationStart", 0)
            except (json.JSONDecodeError, TypeError):
                pass

        # Use LLM to analyze findings and generate QA report
        from src.core.llm_gateway import llm_gateway

        analysis_prompt = (
            f"You are a QA engineer testing a web application.\n\n"
            f"## Task\n{description}\n\n"
            f"## URL\n{url}\n\n"
            f"## Page Structure (accessibility snapshot)\n"
            f"```\n{page_structure[:3000]}\n```\n\n"
            f"## Console Errors\n{chr(10).join(console_errors[:10]) if console_errors else 'None'}\n\n"
            f"## Metrics\n{json.dumps(metrics, indent=2)}\n\n"
            f"Based on the page structure and test results, generate a QA report:\n"
            f"1. Page load status and performance\n"
            f"2. Interactive elements found and their states\n"
            f"3. Accessibility issues detected\n"
            f"4. Console/network errors\n"
            f"5. Bugs or issues found\n"
            f"6. Recommendations\n\n"
            f"Return as JSON: {{\"bugs\": [...], \"accessibility_issues\": [...], "
            f"\"performance\": {{...}}, \"recommendations\": [...], \"overall_score\": 0-100}}"
        )

        report = llm_gateway.generate(
            analysis_prompt,
            system_prompt="You are a thorough QA engineer. Return valid JSON.",
            trace_name="openbrowser.qa_report",
        )

        output = "\n".join(results) + "\n\n" + report

        return self._make_result(
            run_id=run_id,
            status="completed",
            tier="gstack",
            output=output,
            artifacts=screenshots,
            metrics=metrics,
            errors=errors,
        )

    def _execute_with_llm(self, run_id: str, task_type: str, description: str, url: str) -> RunResult:
        """Simulate browser testing via LLM when gstack is not available."""
        from src.core.llm_gateway import llm_gateway

        system_prompt = (
            "You are a senior QA engineer and browser testing specialist.\n"
            "Generate realistic browser test results including:\n"
            "- Page load analysis and performance metrics\n"
            "- Interactive element inventory\n"
            "- Accessibility audit (WCAG 2.1 AA)\n"
            "- Security checks (OWASP Top 10 surface-level)\n"
            "- Visual consistency check\n"
            "- Bug report for any issues found\n\n"
            "Output as JSON: {\"test_plan\": [...], \"results\": [...], "
            "\"bugs\": [{\"severity\": \"...\", \"description\": \"...\", \"steps\": [...]}], "
            "\"accessibility\": {\"wcag_level\": \"...\", \"violations\": [...]}, "
            "\"performance\": {\"load_time_ms\": N, \"core_web_vitals\": {...}}, "
            "\"security\": {\"findings\": [...]}, "
            "\"overall_score\": 0-100, \"recommendations\": [...]}\n"
        )

        url_context = f"\nTarget URL: {url}" if url else ""
        prompt = f"Task: {description}{url_context}"

        response = llm_gateway.generate_for_task(
            task_type=task_type,
            prompt=prompt,
            system_prompt=system_prompt,
            trace_name="openbrowser.llm_simulate",
        )

        metrics = {"mode": "llm_simulation"}
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(response[start:end])
                metrics["bugs_found"] = len(parsed.get("bugs", []))
                metrics["a11y_violations"] = len(parsed.get("accessibility", {}).get("violations", []))
                metrics["overall_score"] = parsed.get("overall_score", 0)
        except (json.JSONDecodeError, TypeError):
            pass

        return self._make_result(
            run_id=run_id,
            status="completed",
            tier="llm_simulation",
            output=response,
            metrics=metrics,
        )

    def verify(self, result, task):
        findings = []
        score = 30.0

        if result.status == "error":
            return VerificationReport(passed=False, score=0.0, findings=[
                VerificationFinding("execution", VerificationSeverity.ERROR, "Failed"),
            ])

        metrics = result.metrics or {}

        # Console errors
        console_errors = metrics.get("console_errors", 0)
        if console_errors == 0:
            score += 15
            findings.append(VerificationFinding(
                "console", VerificationSeverity.PASS, "No console errors",
            ))
        elif console_errors <= 3:
            score += 5
            findings.append(VerificationFinding(
                "console", VerificationSeverity.WARNING,
                f"{console_errors} console errors detected",
            ))
        else:
            findings.append(VerificationFinding(
                "console", VerificationSeverity.ERROR,
                f"{console_errors} console errors detected",
            ))

        # Failed requests
        failed_reqs = metrics.get("failed_requests", 0)
        if failed_reqs == 0:
            score += 10
            findings.append(VerificationFinding(
                "network", VerificationSeverity.PASS, "All network requests succeeded",
            ))
        else:
            findings.append(VerificationFinding(
                "network", VerificationSeverity.ERROR,
                f"{failed_reqs} failed network requests",
            ))

        # Page load time
        load_ms = metrics.get("page_load_ms", 0)
        if 0 < load_ms < 3000:
            score += 15
            findings.append(VerificationFinding(
                "performance", VerificationSeverity.PASS,
                f"Page loaded in {load_ms}ms (< 3s threshold)",
            ))
        elif load_ms >= 3000:
            score += 5
            findings.append(VerificationFinding(
                "performance", VerificationSeverity.WARNING,
                f"Slow page load: {load_ms}ms (> 3s threshold)",
            ))

        # Has output with QA content
        output_lower = (result.output or "").lower()
        qa_kws = ["bug", "issue", "test", "pass", "fail", "accessibility",
                   "performance", "security", "recommendation"]
        kw_hits = sum(1 for k in qa_kws if k in output_lower)
        if kw_hits >= 4:
            score += 15
        elif kw_hits >= 2:
            score += 8

        # Screenshots captured
        if result.artifacts:
            score += 10
            findings.append(VerificationFinding(
                "evidence", VerificationSeverity.PASS,
                f"{len(result.artifacts)} screenshots captured",
            ))

        # Accessibility tree
        if metrics.get("accessibility_tree_size", 0) > 100:
            score += 5

        score = min(score, 100.0)
        return VerificationReport(
            passed=score >= 40.0, score=score,
            findings=findings, metrics=metrics,
        )

    def get_toolchain(self):
        base = super().get_toolchain()
        base["tools"] = [
            "gstack-browse", "chromium", "playwright",
            "accessibility-checker", "lighthouse", "axe-core",
        ]
        base["packages"] = ["bun", "playwright", "axe-core"]
        base["gstack_available"] = self._check_gstack()
        return base

    def get_workflow(self):
        return [
            {"step": 1, "name": "navigate", "description": "Navigate to target URL"},
            {"step": 2, "name": "snapshot", "description": "Capture interactive snapshot with element refs"},
            {"step": 3, "name": "interact", "description": "Test user flows (click, fill, verify)"},
            {"step": 4, "name": "audit", "description": "Check console errors, network, accessibility"},
            {"step": 5, "name": "screenshot", "description": "Capture visual evidence"},
            {"step": 6, "name": "report", "description": "Generate QA report with findings"},
        ]

    def get_experience_keys(self):
        return ["task_type", "url_domain", "bug_type", "a11y_violation", "domain"]

    def get_exercises(self, difficulty="intermediate"):
        """Load from central catalog, fall back to hardcoded browser exercises."""
        catalog = self._load_catalog_exercises(difficulty)
        if catalog:
            return catalog

        from src.integrations.base_runner import Exercise as Ex

        exercises = {
            "beginner": [
                Ex(id="browser-b01", role="qa_engineer", task_type="BROWSER_QA",
                   difficulty="beginner",
                   description="Test a simple login form: navigate to the page, fill email and password fields, submit, verify success message appears",
                   acceptance_criteria=["Navigate to login URL", "Fill form fields", "Submit form", "Verify success/error state"],
                   expected_artifacts=["qa_report.json", "screenshot.png"],
                   tags=["login", "form", "basic"]),
                Ex(id="browser-b02", role="qa_engineer", task_type="BROWSER_QA",
                   difficulty="beginner",
                   description="Verify a landing page loads correctly: check title, hero section visibility, navigation links, and console for JS errors",
                   acceptance_criteria=["Page loads", "Title correct", "Hero visible", "No console errors"],
                   expected_artifacts=["qa_report.json"],
                   tags=["landing", "smoke-test"]),
                Ex(id="browser-b03", role="system_tester", task_type="BROWSER_SMOKE",
                   difficulty="beginner",
                   description="Perform a basic smoke test: hit 5 core URLs and verify each returns 200, has correct title, and loads within 3 seconds",
                   acceptance_criteria=["All URLs load", "Correct titles", "Under 3s each", "No errors"],
                   expected_artifacts=["smoke_report.json"],
                   tags=["smoke", "performance"]),
            ],
            "intermediate": [
                Ex(id="browser-i01", role="qa_engineer", task_type="BROWSER_QA",
                   difficulty="intermediate",
                   description="Test a multi-step checkout flow: add item to cart, proceed to checkout, fill shipping/billing, submit order, verify confirmation page",
                   acceptance_criteria=["Cart operations work", "Form validation works", "Payment flow completes", "Confirmation displayed", "No console errors"],
                   expected_artifacts=["qa_report.json", "screenshots/"],
                   tags=["checkout", "e2e", "forms"]),
                Ex(id="browser-i02", role="ux_designer", task_type="BROWSER_A11Y",
                   difficulty="intermediate",
                   description="Run a full WCAG 2.1 AA accessibility audit on a dashboard page: check color contrast, keyboard navigation, ARIA labels, focus management, screen reader compatibility",
                   acceptance_criteria=["Contrast ratios >= 4.5:1", "All interactive elements keyboard-accessible", "ARIA labels present", "Focus order logical", "No missing alt text"],
                   expected_artifacts=["a11y_report.json", "annotated_screenshot.png"],
                   tags=["accessibility", "wcag", "audit"]),
                Ex(id="browser-i03", role="system_tester", task_type="BROWSER_PERF",
                   difficulty="intermediate",
                   description="Benchmark page performance: measure Core Web Vitals (LCP, FID, CLS), resource sizes, time to interactive, and compare against thresholds",
                   acceptance_criteria=["LCP < 2.5s", "FID < 100ms", "CLS < 0.1", "Resource breakdown", "Performance score"],
                   expected_artifacts=["perf_report.json"],
                   tags=["performance", "core-web-vitals", "benchmark"]),
            ],
            "advanced": [
                Ex(id="browser-a01", role="qa_engineer", task_type="BROWSER_QA",
                   difficulty="advanced",
                   description="Test responsive design across 3 viewports (mobile 375px, tablet 768px, desktop 1440px): verify layout adapts, no overflow, touch targets adequate on mobile, navigation collapses to hamburger menu",
                   acceptance_criteria=["3 viewport screenshots", "No horizontal overflow", "Mobile touch targets >= 44px", "Responsive nav works", "All content accessible"],
                   expected_artifacts=["responsive_report.json", "mobile.png", "tablet.png", "desktop.png"],
                   tags=["responsive", "mobile", "viewport"]),
                Ex(id="browser-a02", role="system_tester", task_type="BROWSER_SECURITY",
                   difficulty="advanced",
                   description="Perform surface-level security audit: check for exposed API keys in source, CSP headers, HTTPS enforcement, cookie security flags, XSS-prone input fields, and open redirect vulnerabilities",
                   acceptance_criteria=["CSP headers checked", "Cookie flags audited", "Input sanitization tested", "HTTPS enforced", "No exposed secrets in source"],
                   expected_artifacts=["security_report.json"],
                   tags=["security", "owasp", "audit"]),
                Ex(id="browser-a03", role="qa_engineer", task_type="BROWSER_REGRESSION",
                   difficulty="advanced",
                   description="Visual regression testing: capture baseline screenshots of 5 critical pages, simulate a deploy, re-capture, diff the before/after screenshots, flag any visual regressions above 1% pixel difference",
                   acceptance_criteria=["Baseline captured", "Post-deploy captured", "Diff computed", "Regressions flagged with threshold", "Report generated"],
                   expected_artifacts=["regression_report.json", "diffs/"],
                   tags=["regression", "visual", "diff"]),
            ],
            "expert": [
                Ex(id="browser-x01", role="qa_engineer", task_type="BROWSER_QA",
                   difficulty="expert",
                   description="Full end-to-end test of a SaaS application: test authentication (login, OAuth, MFA), RBAC (admin vs user permissions), real-time features (WebSocket updates), file upload/download, and error recovery (network disconnect handling)",
                   acceptance_criteria=["Auth flow tested", "RBAC verified", "WebSocket tested", "File ops work", "Error recovery works", "Comprehensive report"],
                   expected_artifacts=["full_qa_report.json", "screenshots/"],
                   tags=["e2e", "full-suite", "enterprise"]),
                Ex(id="browser-x02", role="system_tester", task_type="BROWSER_LOAD",
                   difficulty="expert",
                   description="Browser-based load impact test: open 10 concurrent tabs of the same app, measure memory footprint per tab, track performance degradation curve, identify memory leaks via heap snapshots, report ceiling capacity",
                   acceptance_criteria=["10-tab test completed", "Memory per tab tracked", "Degradation curve plotted", "Leak detection", "Capacity ceiling identified"],
                   expected_artifacts=["load_report.json"],
                   tags=["load", "memory", "scalability"]),
            ],
        }
        return exercises.get(difficulty, exercises["intermediate"])

    def grade_exercise(self, exercise, result):
        """Structural checks (40%) + LLM-as-judge (60%)."""
        score = 0.0
        criteria = {}
        hints = []

        if result.status == "completed":
            score += 15
            criteria["execution_success"] = True

        output_lower = (result.output or "").lower()
        metrics = result.metrics or {}

        # QA methodology keywords
        qa_kws = ["test", "verify", "assert", "check", "validate", "confirm",
                   "expect", "should", "pass", "fail", "bug", "issue"]
        qa_hits = sum(1 for k in qa_kws if k in output_lower)
        if qa_hits >= 5:
            score += 15
            criteria["qa_methodology"] = True
        elif qa_hits >= 2:
            score += 8
        else:
            hints.append("Include systematic test steps with assertions and verifications")

        # Browser interaction keywords
        browser_kws = ["navigate", "click", "fill", "submit", "screenshot",
                       "snapshot", "console", "network", "viewport", "scroll",
                       "element", "selector", "page", "url", "dom"]
        browser_hits = sum(1 for k in browser_kws if k in output_lower)
        if browser_hits >= 4:
            score += 15
            criteria["browser_interaction"] = True
        elif browser_hits >= 2:
            score += 8
        else:
            hints.append("Demonstrate actual browser interactions (navigate, click, fill, verify)")

        # Accessibility coverage
        a11y_kws = ["wcag", "aria", "contrast", "keyboard", "focus",
                     "screen reader", "alt text", "accessible", "a11y"]
        if sum(1 for k in a11y_kws if k in output_lower) >= 2:
            score += 10
            criteria["accessibility_checked"] = True
        else:
            hints.append("Include accessibility checks (WCAG, ARIA, contrast, keyboard nav)")

        # Performance awareness
        perf_kws = ["load time", "performance", "core web vital", "lcp", "fid", "cls",
                     "time to interactive", "first contentful paint", "resource"]
        if sum(1 for k in perf_kws if k in output_lower) >= 2:
            score += 10
            criteria["performance_checked"] = True

        # Evidence (screenshots/artifacts)
        if result.artifacts:
            score += 10
            criteria["visual_evidence"] = True
        elif "screenshot" in output_lower:
            score += 5

        # Bug report structure
        bug_kws = ["severity", "steps to reproduce", "expected", "actual", "priority"]
        if sum(1 for k in bug_kws if k in output_lower) >= 2:
            score += 10
            criteria["structured_bug_reports"] = True

        # Security awareness
        sec_kws = ["xss", "csrf", "injection", "owasp", "csp", "cors",
                    "cookie", "https", "authentication", "authorization"]
        if sum(1 for k in sec_kws if k in output_lower) >= 2:
            score += 10
            criteria["security_aware"] = True

        if result.verification and result.verification.passed:
            score += 5
            criteria["verification_passed"] = True

        return self._combined_grade(
            exercise, result, min(score, 100.0), criteria, hints,
            domain_context=(
                "Grade as a senior QA engineer with browser testing expertise. Check for:\n"
                "- Systematic test methodology (not random clicking)\n"
                "- Proper assertions and verifications at each step\n"
                "- Accessibility testing (WCAG 2.1 AA minimum)\n"
                "- Performance awareness (load times, Core Web Vitals)\n"
                "- Security surface checks (OWASP basics)\n"
                "- Visual evidence (screenshots, annotated snapshots)\n"
                "- Structured bug reports (severity, steps, expected vs actual)\n"
                "- Edge case coverage (error states, empty states, boundary values)"
            ),
        )


# ---------------------------------------------------------------------------
# Self-register
# ---------------------------------------------------------------------------

_runner = OpenBrowserRunner()
register_supplementary_runner(_runner)
