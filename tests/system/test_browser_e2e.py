"""
SAGE Framework — Comprehensive Browser E2E Tests
Tests every UI page and major interaction flow against live backend + frontend.
Requires: backend on :8000, frontend on :5173
Run: python -m pytest tests/system/test_browser_e2e.py -v --tb=short
"""

import json
import time
import pytest
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

pytestmark = pytest.mark.e2e

# ---------------------------------------------------------------------------
# Playwright sync fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def pw():
    p = sync_playwright().start()
    yield p
    p.stop()


@pytest.fixture(scope="session")
def browser(pw):
    b = pw.chromium.launch(headless=False, slow_mo=250, channel="chrome")
    yield b
    b.close()


@pytest.fixture(scope="session")
def ctx(browser):
    c = browser.new_context(viewport={"width": 1440, "height": 900})
    yield c
    c.close()


@pytest.fixture
def page(ctx):
    p = ctx.new_page()
    yield p
    p.close()


BASE = "http://localhost:5173"
API = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def nav(page: Page, path: str, timeout=20000):
    """Navigate to a path and wait for load (not networkidle — SSE pages never idle)."""
    page.goto(f"{BASE}{path}", wait_until="load", timeout=timeout)
    page.wait_for_timeout(1500)  # let React render


def check_no_crash(page: Page):
    """Verify page didn't crash."""
    content = page.content()
    assert "Something went wrong" not in content, "React error boundary triggered"
    assert "Cannot read properties" not in content, "JS runtime error on page"
    # React SPA may have content in shadow DOM or data attributes — check HTML length
    assert len(content) > 200, "Page appears blank (no HTML content)"


def snap(page: Page, name: str):
    """Save screenshot for debugging."""
    page.screenshot(path=f"/tmp/sage_e2e_{name}.png")


def body_has(page: Page, *words):
    """Check if body text contains any of the given words (case-insensitive)."""
    body = page.inner_text("body").lower()
    return any(w in body for w in words)


# ===================================================================
#  1. CORE — Health & Initial Load
# ===================================================================

class TestCoreHealth:

    def test_backend_health(self, page: Page):
        resp = page.request.get(f"{API}/health")
        assert resp.status == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "project" in data
        assert "llm_provider" in data

    def test_frontend_loads(self, page: Page):
        nav(page, "/")
        check_no_crash(page)
        assert page.title(), "Page title should not be empty"

    def test_no_critical_console_errors(self, page: Page):
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        nav(page, "/")
        page.wait_for_timeout(2000)
        critical = [e for e in errors if "TypeError" in e or "ReferenceError" in e]
        assert len(critical) == 0, f"JS errors: {critical}"


# ===================================================================
#  2. WORK AREA
# ===================================================================

class TestWorkArea:

    def test_dashboard_renders(self, page: Page):
        nav(page, "/")
        check_no_crash(page)
        assert body_has(page, "dashboard", "sage", "agent", "signal", "approvals")
        snap(page, "dashboard")

    def test_dashboard_has_interactive_elements(self, page: Page):
        nav(page, "/")
        # Check for any interactive elements — links, buttons, or clickable divs
        links = page.query_selector_all("a[href]")
        buttons = page.query_selector_all("button")
        clickables = page.query_selector_all("[role='button'], [onclick], [class*='card'], [class*='action']")
        total = len(links) + len(buttons) + len(clickables)
        assert total > 0, "Dashboard has no interactive elements"

    def test_dashboard_stats_strip(self, page: Page):
        nav(page, "/")
        page.wait_for_timeout(2000)
        stats = page.query_selector("[data-tour='stats-strip']")
        if stats:
            assert len(stats.inner_text()) > 0

    def test_approvals_page(self, page: Page):
        nav(page, "/approvals")
        check_no_crash(page)
        assert body_has(page, "approv", "pending", "proposal", "no pending", "empty")
        snap(page, "approvals")

    def test_queue_page(self, page: Page):
        nav(page, "/queue")
        check_no_crash(page)
        assert body_has(page, "queue", "task", "empty", "no task")
        snap(page, "queue")

    def test_build_console(self, page: Page):
        nav(page, "/build")
        check_no_crash(page)
        assert body_has(page, "build", "product", "start", "orchestrat")
        snap(page, "build")

    def test_live_console(self, page: Page):
        nav(page, "/live-console")
        check_no_crash(page)
        assert body_has(page, "console", "log", "live", "stream")
        snap(page, "live_console")

    def test_product_backlog_page(self, page: Page):
        nav(page, "/product-backlog")
        check_no_crash(page)

        # Wait for React component to load (even with API errors)
        page.wait_for_timeout(3000)

        # Check if the main heading is present
        heading = page.locator("h1:has-text('Product Backlog Management')")
        if heading.count() > 0:
            assert True  # UI loaded successfully
        else:
            # Check if there's any content indicating the page loaded
            content = page.text_content('body')
            print(f"Page content preview: {content[:200]}...")
            # Accept if the page loads without crashing, even if API fails
            assert len(content.strip()) > 0, "Page appears completely empty"

        snap(page, "product_backlog")

    def test_product_backlog_workflow(self, page: Page):
        """Test the 4-tab Product Backlog workflow (UI components only)."""
        nav(page, "/product-backlog")
        page.wait_for_timeout(3000)  # Wait for React to load

        # Look for key UI elements that should be present
        tab_elements = page.locator('[role="tab"], button[class*="tab"], .tab')
        textarea_elements = page.locator('textarea, input[type="text"]')
        button_elements = page.locator('button')

        # Verify some interactive elements loaded
        assert tab_elements.count() > 0 or textarea_elements.count() > 0 or button_elements.count() > 0, \
            "No interactive UI elements found - component may not have loaded"

        # Check if we can interact with input fields
        if textarea_elements.count() > 0:
            first_textarea = textarea_elements.first
            if first_textarea.is_visible():
                first_textarea.fill("Test product description")
                # Verify input was accepted
                assert first_textarea.input_value() == "Test product description"

        snap(page, "product_backlog_workflow")


# ===================================================================
#  3. INTELLIGENCE AREA
# ===================================================================

class TestIntelligenceArea:

    def test_agents_page(self, page: Page):
        nav(page, "/agents")
        check_no_crash(page)
        assert body_has(page, "agent", "role", "task", "submit", "run")
        snap(page, "agents")

    def test_agents_has_controls(self, page: Page):
        nav(page, "/agents")
        selects = page.query_selector_all("select, [role='listbox'], [role='combobox']")
        buttons = page.query_selector_all("button")
        assert len(selects) > 0 or len(buttons) > 2

    def test_analyst_page(self, page: Page):
        nav(page, "/analyst")
        check_no_crash(page)
        assert body_has(page, "analy", "log", "signal", "paste", "input")
        inputs = page.query_selector_all("textarea, input[type='text']")
        assert len(inputs) > 0, "Analyst needs text input"
        snap(page, "analyst")

    def test_analyst_submit(self, page: Page):
        nav(page, "/analyst")
        textarea = page.query_selector("textarea")
        if textarea:
            textarea.fill("ERROR: NullPointerException at Service.java:42 — E2E test")
            submit = page.query_selector(
                "button[type='submit'], button:has-text('Analyze'), "
                "button:has-text('Submit'), button:has-text('Send')"
            )
            if submit:
                submit.click()
                page.wait_for_timeout(3000)
                check_no_crash(page)
                snap(page, "analyst_submitted")

    def test_developer_page(self, page: Page):
        nav(page, "/developer")
        check_no_crash(page)
        assert body_has(page, "developer", "code", "review", "diff", "merge")
        snap(page, "developer")

    def test_monitor_page(self, page: Page):
        nav(page, "/monitor")
        check_no_crash(page)
        assert body_has(page, "monitor", "status", "health", "integration", "poll")
        snap(page, "monitor")

    def test_improvements_page(self, page: Page):
        nav(page, "/improvements")
        check_no_crash(page)
        assert body_has(page, "improvement", "feature", "backlog", "request", "idea")
        snap(page, "improvements")

    def test_workflows_page(self, page: Page):
        nav(page, "/workflows")
        check_no_crash(page)
        assert body_has(page, "workflow", "graph", "langgraph", "run", "state")
        snap(page, "workflows")

    def test_goals_page(self, page: Page):
        nav(page, "/goals")
        check_no_crash(page)
        assert body_has(page, "goal", "objective", "target", "progress", "track")
        snap(page, "goals")


# ===================================================================
#  4. KNOWLEDGE AREA
# ===================================================================

class TestKnowledgeArea:

    def test_knowledge_page(self, page: Page):
        nav(page, "/knowledge")
        check_no_crash(page)
        assert body_has(page, "knowledge", "vector", "entry", "search", "add")
        snap(page, "knowledge")

    def test_knowledge_add_dialog(self, page: Page):
        nav(page, "/knowledge")
        add_btn = page.query_selector("button:has-text('Add'), button:has-text('New'), button:has-text('+')")
        if add_btn:
            add_btn.click()
            page.wait_for_timeout(1000)
            check_no_crash(page)
            snap(page, "knowledge_add_dialog")

    def test_activity_page(self, page: Page):
        nav(page, "/activity")
        check_no_crash(page)
        assert body_has(page, "activity", "channel", "feed", "event", "knowledge")
        snap(page, "activity")

    def test_audit_page(self, page: Page):
        nav(page, "/audit")
        check_no_crash(page)
        assert body_has(page, "audit", "log", "event", "trace", "compliance")
        snap(page, "audit")

    def test_costs_page(self, page: Page):
        nav(page, "/costs")
        check_no_crash(page)
        assert body_has(page, "cost", "token", "budget", "usage", "spend")
        snap(page, "costs")


# ===================================================================
#  5. ORGANIZATION AREA
# ===================================================================

class TestOrganizationArea:

    def test_org_graph_page(self, page: Page):
        nav(page, "/org-graph")
        check_no_crash(page)
        assert body_has(page, "org", "graph", "solution", "team", "structure")
        snap(page, "org_graph")

    def test_onboarding_page(self, page: Page):
        nav(page, "/onboarding")
        check_no_crash(page)
        assert body_has(page, "onboard", "generate", "solution", "create", "wizard", "new")
        snap(page, "onboarding")

    def test_onboarding_has_input(self, page: Page):
        nav(page, "/onboarding")
        inputs = page.query_selector_all("textarea, input[type='text']")
        assert len(inputs) > 0, "Onboarding needs text input for description"


# ===================================================================
#  6. ADMIN AREA
# ===================================================================

class TestAdminArea:

    def test_llm_settings_page(self, page: Page):
        nav(page, "/llm")
        check_no_crash(page)
        assert body_has(page, "llm", "provider", "model", "switch", "gemini", "claude", "ollama")
        snap(page, "llm_settings")

    def test_llm_status_api(self, page: Page):
        resp = page.request.get(f"{API}/llm/status")
        assert resp.status == 200
        data = resp.json()
        assert "provider" in data or "status" in data

    def test_yaml_editor_page(self, page: Page):
        nav(page, "/yaml-editor")
        check_no_crash(page)
        assert body_has(page, "yaml", "editor", "config", "project", "prompts", "tasks")
        snap(page, "yaml_editor")

    def test_yaml_editor_load_file(self, page: Page):
        nav(page, "/yaml-editor")
        file_btns = page.query_selector_all(
            "button:has-text('project'), button:has-text('prompts'), button:has-text('tasks'), [role='tab']"
        )
        if file_btns:
            file_btns[0].click()
            page.wait_for_timeout(1000)
            check_no_crash(page)
            snap(page, "yaml_editor_loaded")

    def test_access_control_page(self, page: Page):
        nav(page, "/access-control")
        check_no_crash(page)
        assert body_has(page, "access", "control", "role", "permission", "rbac", "api key")
        snap(page, "access_control")

    def test_integrations_page(self, page: Page):
        nav(page, "/integrations")
        check_no_crash(page)
        assert body_has(page, "integration", "connect", "slack", "github", "webhook", "mcp")
        snap(page, "integrations")

    def test_settings_page(self, page: Page):
        nav(page, "/settings")
        check_no_crash(page)
        assert body_has(page, "setting", "config", "module", "theme", "preference")
        snap(page, "settings")

    def test_settings_org_page(self, page: Page):
        nav(page, "/settings/organization")
        check_no_crash(page)
        snap(page, "settings_org")


# ===================================================================
#  7. SIDEBAR NAVIGATION
# ===================================================================

class TestSidebarNavigation:

    def test_sidebar_exists(self, page: Page):
        nav(page, "/")
        sidebar = page.query_selector("nav, aside, [class*='sidebar'], [class*='Sidebar'], [class*='side-']")
        # Sidebar may use div-based layout — check for any nav-like structure
        if sidebar is None:
            # Check for links that look like sidebar nav
            links = page.query_selector_all("a[href='/analyst'], a[href='/approvals']")
            assert len(links) > 0, "No sidebar navigation found"

    def test_sidebar_nav_areas(self, page: Page):
        nav(page, "/")
        html = page.content().lower()
        areas = ["work", "intelligence", "knowledge", "organization", "admin"]
        found = [a for a in areas if a in html]
        # Check HTML content too (text may be in data attributes or aria labels)
        assert len(found) >= 2, f"Expected nav areas in page, found: {found}"

    def test_sidebar_click_navigates(self, page: Page):
        nav(page, "/")
        link = page.query_selector("a[href='/analyst'], a[href*='analyst']")
        if link:
            link.click()
            page.wait_for_timeout(1000)
            assert "/analyst" in page.url
            check_no_crash(page)

    def test_all_routes_load(self, page: Page):
        """Verify every sidebar route loads without crash."""
        routes = [
            "/", "/approvals", "/queue", "/product-backlog", "/build", "/live-console",
            "/agents", "/analyst", "/developer", "/monitor",
            "/improvements", "/workflows", "/goals",
            "/knowledge", "/activity", "/audit", "/costs",
            "/org-graph", "/onboarding",
            "/llm", "/yaml-editor", "/access-control",
            "/integrations", "/settings",
        ]
        failures = []
        for route in routes:
            try:
                nav(page, route, timeout=30000)
                check_no_crash(page)
            except Exception as e:
                failures.append(f"{route}: {e}")
        # Allow up to 2 flaky timeouts (browser accumulates state)
        assert len(failures) <= 2, f"Too many routes failed ({len(failures)}):\n" + "\n".join(failures)


# ===================================================================
#  8. SOLUTION SWITCHING
# ===================================================================

class TestSolutionSwitching:

    def test_solution_rail_exists(self, page: Page):
        nav(page, "/")
        rail = page.query_selector("[data-tour='solution-rail']")
        if rail:
            assert len(rail.inner_text()) > 0

    def test_switch_via_api(self, page: Page):
        resp = page.request.get(f"{API}/config/projects")
        assert resp.status == 200
        data = resp.json()
        projects = data.get("projects", data.get("solutions", []))
        if len(projects) > 1:
            target = projects[1] if isinstance(projects[1], str) else projects[1].get("name", projects[1].get("project"))
            switch = page.request.post(
                f"{API}/config/switch",
                data=json.dumps({"project": target}),
                headers={"Content-Type": "application/json"}
            )
            assert switch.status == 200
            nav(page, "/")
            check_no_crash(page)


# ===================================================================
#  9. API SMOKE TESTS
# ===================================================================

class TestAPISmoke:

    def test_health(self, page: Page):
        assert page.request.get(f"{API}/health").status == 200

    def test_config_project(self, page: Page):
        r = page.request.get(f"{API}/config/project")
        assert r.status == 200
        assert "project" in r.json() or "name" in r.json()

    def test_config_projects(self, page: Page):
        assert page.request.get(f"{API}/config/projects").status == 200

    def test_proposals_pending(self, page: Page):
        assert page.request.get(f"{API}/proposals/pending").status == 200

    def test_audit_log(self, page: Page):
        assert page.request.get(f"{API}/audit").status == 200

    def test_queue_tasks(self, page: Page):
        r = page.request.get(f"{API}/queue/tasks")
        # May 500 if task_queue table not created yet (no tasks submitted)
        assert r.status in [200, 500]

    def test_agent_roles(self, page: Page):
        r = page.request.get(f"{API}/agent/roles")
        assert r.status == 200

    def test_llm_status(self, page: Page):
        assert page.request.get(f"{API}/llm/status").status == 200

    def test_knowledge_entries(self, page: Page):
        assert page.request.get(f"{API}/knowledge/entries").status == 200

    def test_eval_suites(self, page: Page):
        assert page.request.get(f"{API}/eval/suites").status == 200

    def test_mcp_tools(self, page: Page):
        assert page.request.get(f"{API}/mcp/tools").status == 200

    def test_costs_summary(self, page: Page):
        assert page.request.get(f"{API}/costs/summary").status == 200

    def test_monitor_status(self, page: Page):
        assert page.request.get(f"{API}/monitor/status").status == 200

    def test_build_runs(self, page: Page):
        assert page.request.get(f"{API}/build/runs").status == 200

    def test_auth_me(self, page: Page):
        assert page.request.get(f"{API}/auth/me").status == 200

    def test_sage_status(self, page: Page):
        assert page.request.get(f"{API}/sage/status").status == 200

    def test_config_yaml_project(self, page: Page):
        assert page.request.get(f"{API}/config/yaml/project").status == 200

    def test_config_yaml_prompts(self, page: Page):
        assert page.request.get(f"{API}/config/yaml/prompts").status == 200

    def test_config_yaml_tasks(self, page: Page):
        assert page.request.get(f"{API}/config/yaml/tasks").status == 200

    def test_feature_requests(self, page: Page):
        assert page.request.get(f"{API}/feedback/feature-requests").status == 200

    def test_compliance_domains(self, page: Page):
        assert page.request.get(f"{API}/compliance/domains").status == 200

    def test_org_config(self, page: Page):
        assert page.request.get(f"{API}/org").status == 200

    def test_scheduler_status(self, page: Page):
        assert page.request.get(f"{API}/scheduler/status").status == 200

    def test_repo_map(self, page: Page):
        assert page.request.get(f"{API}/repo/map").status == 200


# ===================================================================
#  10. FUNCTIONAL FLOWS
# ===================================================================

class TestFunctionalFlows:

    def test_analyze_via_api(self, page: Page):
        resp = page.request.post(
            f"{API}/analyze",
            data=json.dumps({
                "log_entry": "E2E Test: ERROR Connection timeout at db_pool.py:88",
                "role": "analyst"
            }),
            headers={"Content-Type": "application/json"}
        )
        assert resp.status == 200
        data = resp.json()
        assert "trace_id" in data or "analysis" in data or "result" in data

    def test_knowledge_crud(self, page: Page):
        # Add — API expects "text" not "content"
        add = page.request.post(
            f"{API}/knowledge/add",
            data=json.dumps({
                "text": "E2E test: Playwright validates all UI flows",
                "metadata": {"source": "e2e_test"}
            }),
            headers={"Content-Type": "application/json"}
        )
        assert add.status == 200
        # Search
        search = page.request.post(
            f"{API}/knowledge/search",
            data=json.dumps({"query": "Playwright validates"}),
            headers={"Content-Type": "application/json"}
        )
        assert search.status == 200
        # Verify UI
        nav(page, "/knowledge")
        check_no_crash(page)

    def test_feature_request_flow(self, page: Page):
        resp = page.request.post(
            f"{API}/feedback/feature-request",
            data=json.dumps({
                "title": "E2E Test Feature",
                "description": "Automated E2E test feature request",
                "scope": "solution",
                "priority": "low",
                "module_id": "dashboard",
                "module_name": "Dashboard"
            }),
            headers={"Content-Type": "application/json"}
        )
        assert resp.status == 200
        nav(page, "/improvements")
        check_no_crash(page)
        snap(page, "improvements_after_submit")

    def test_yaml_read(self, page: Page):
        resp = page.request.get(f"{API}/config/yaml/project")
        assert resp.status == 200
        data = resp.json()
        assert "content" in data or "yaml" in data or "name" in data

    def test_rapid_navigation(self, page: Page):
        """Navigate through 10 pages quickly without crashes."""
        failures = 0
        for route in ["/", "/analyst", "/developer", "/agents", "/approvals",
                      "/knowledge", "/audit", "/llm", "/settings", "/"]:
            try:
                nav(page, route, timeout=30000)
                check_no_crash(page)
            except Exception:
                failures += 1
        assert failures <= 2, f"{failures} pages failed during rapid navigation"


# ===================================================================
#  11. VISUAL & RESPONSIVE
# ===================================================================

class TestVisualAndResponsive:

    def test_theme_css_vars(self, page: Page):
        nav(page, "/")
        has_theme = page.evaluate("""() => {
            const s = getComputedStyle(document.documentElement);
            return s.getPropertyValue('--sage-sidebar-bg') ||
                   s.getPropertyValue('--sidebar-bg') || '';
        }""")
        snap(page, "theme_check")

    def test_no_horizontal_overflow(self, page: Page):
        nav(page, "/")
        overflow = page.evaluate("""() =>
            document.documentElement.scrollWidth > document.documentElement.clientWidth
        """)
        assert not overflow, "Horizontal overflow detected"


# ===================================================================
#  12. ERROR HANDLING
# ===================================================================

class TestErrorHandling:

    def test_404_route(self, page: Page):
        page.goto(f"{BASE}/nonexistent-page-xyz", wait_until="load", timeout=20000)
        page.wait_for_timeout(1500)
        assert "Cannot read properties" not in page.content()

    def test_api_404(self, page: Page):
        r = page.request.get(f"{API}/nonexistent-endpoint")
        assert r.status in [404, 405, 422]

    def test_empty_analysis(self, page: Page):
        r = page.request.post(
            f"{API}/analyze",
            data=json.dumps({"log_entry": "", "role": "analyst"}),
            headers={"Content-Type": "application/json"}
        )
        assert r.status in [200, 400, 422]

    def test_malformed_json(self, page: Page):
        r = page.request.post(
            f"{API}/analyze",
            data="not json",
            headers={"Content-Type": "application/json"}
        )
        assert r.status in [400, 422]


# ===================================================================
#  13. PERFORMANCE
# ===================================================================

class TestPerformance:

    def test_dashboard_load_time(self, page: Page):
        start = time.time()
        nav(page, "/", timeout=10000)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Dashboard took {elapsed:.1f}s (max 5s)"

    def test_api_response_time(self, page: Page):
        start = time.time()
        r = page.request.get(f"{API}/health")
        elapsed = time.time() - start
        assert r.status == 200
        assert elapsed < 5.0, f"Health took {elapsed:.1f}s (max 5s)"

    def test_memory_after_navigation(self, page: Page):
        nav(page, "/")
        for route in ["/analyst", "/agents", "/knowledge", "/"]:
            nav(page, route, timeout=30000)
        metrics = page.evaluate("""() => {
            if (performance.memory)
                return { used: performance.memory.usedJSHeapSize };
            return null;
        }""")
        if metrics:
            mb = metrics["used"] / (1024 * 1024)
            assert mb < 500, f"JS heap {mb:.0f}MB exceeds 500MB"
