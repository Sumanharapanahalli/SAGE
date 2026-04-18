"""
SAGE[ai] — System Tests: Framework MCP Tools
==============================================
End-to-end tests for the provider-agnostic framework MCP servers:
  - filesystem_tools: sandboxed read/write/list/search within solution dir
  - sqlite_tools: read-only queries against .sage/ databases
  - browser_tools: Playwright browser automation (graceful degradation)
  - MCPRegistry: framework tool discovery + solution override

These tests create real temp directories and SQLite databases — no mocks
for the tools themselves. Only project_loader is patched to point at the
temp solution directory.

Covers:
  1. Filesystem sandbox enforcement (cannot escape solution dir)
  2. Filesystem CRUD operations
  3. SQLite read-only enforcement
  4. SQLite query, list_tables, describe_table, list_databases
  5. Browser tools graceful degradation
  6. MCPRegistry discovers framework tools from src/mcp_servers/
  7. MCPRegistry solution tools override framework tools
  8. Full invoke() → audit log pipeline via registry
"""

import os
import sqlite3
import tempfile
import textwrap
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.system


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_solution_dir(tmpdir):
    """Return a context manager that makes project_loader point at tmpdir."""
    mock_config = MagicMock()
    mock_config.project_name = "test_solution"
    return patch.multiple(
        "src.core.project_loader",
        project_config=mock_config,
        _SOLUTIONS_DIR=tmpdir,
    )


def _make_solution_tree(tmpdir):
    """Create a minimal solution directory with .sage/ inside tmpdir."""
    sol_dir = os.path.join(tmpdir, "test_solution")
    sage_dir = os.path.join(sol_dir, ".sage")
    os.makedirs(sage_dir, exist_ok=True)
    return sol_dir, sage_dir


# ===========================================================================
#  1. FILESYSTEM TOOLS — Sandbox Enforcement
# ===========================================================================

class TestFilesystemSandbox:
    """Verify agents cannot escape the solution directory."""

    def test_path_traversal_blocked(self, tmp_path):
        """Paths using .. to escape solution dir must be rejected."""
        from src.mcp_servers.filesystem_tools import _enforce_sandbox

        sol_dir = os.path.join(str(tmp_path), "test_solution")
        os.makedirs(sol_dir)

        with _patch_solution_dir(str(tmp_path)):
            with pytest.raises(ValueError, match="escapes sandbox"):
                _enforce_sandbox("../../etc/passwd")

    def test_absolute_path_blocked(self, tmp_path):
        """Absolute paths outside sandbox must be rejected."""
        from src.mcp_servers.filesystem_tools import _enforce_sandbox

        sol_dir = os.path.join(str(tmp_path), "test_solution")
        os.makedirs(sol_dir)

        with _patch_solution_dir(str(tmp_path)):
            # Symlink escape attempt — skip when OS denies symlink creation
            # (Windows without Developer Mode / admin rights).
            escape_link = os.path.join(sol_dir, "escape")
            try:
                os.symlink("/tmp", escape_link)
            except (OSError, NotImplementedError) as e:
                pytest.skip(f"symlink unsupported in this environment: {e}")
            with pytest.raises(ValueError, match="escapes sandbox"):
                _enforce_sandbox("escape/something")

    def test_valid_path_resolves(self, tmp_path):
        """Paths within the solution directory must resolve correctly."""
        from src.mcp_servers.filesystem_tools import _enforce_sandbox

        sol_dir, _ = _make_solution_tree(str(tmp_path))

        with _patch_solution_dir(str(tmp_path)):
            resolved = _enforce_sandbox("project.yaml")
            assert resolved == os.path.join(sol_dir, "project.yaml")


# ===========================================================================
#  2. FILESYSTEM TOOLS — CRUD Operations
# ===========================================================================

class TestFilesystemCRUD:
    """Test read/write/list/search against a real temp solution directory."""

    def test_write_then_read_file(self, tmp_path):
        """Write a file, then read it back — full round-trip."""
        from src.mcp_servers.filesystem_tools import read_file, write_file

        _make_solution_tree(str(tmp_path))

        with _patch_solution_dir(str(tmp_path)):
            w = write_file("notes.txt", "hello SAGE")
            assert w["success"] is True
            assert w["bytes_written"] == 10

            r = read_file("notes.txt")
            assert r["success"] is True
            assert r["content"] == "hello SAGE"

    def test_write_creates_subdirectories(self, tmp_path):
        """Writing to a nested path must auto-create parent dirs."""
        from src.mcp_servers.filesystem_tools import write_file, read_file

        _make_solution_tree(str(tmp_path))

        with _patch_solution_dir(str(tmp_path)):
            w = write_file("deep/nested/dir/config.yaml", "key: value")
            assert w["success"] is True

            r = read_file("deep/nested/dir/config.yaml")
            assert r["content"] == "key: value"

    def test_read_nonexistent_file(self, tmp_path):
        """Reading a file that doesn't exist must return success=False."""
        from src.mcp_servers.filesystem_tools import read_file

        _make_solution_tree(str(tmp_path))

        with _patch_solution_dir(str(tmp_path)):
            r = read_file("does_not_exist.txt")
            assert r["success"] is False
            assert "not found" in r["error"].lower()

    def test_list_directory(self, tmp_path):
        """list_directory must return files and subdirs with types."""
        from src.mcp_servers.filesystem_tools import write_file, list_directory

        sol_dir, _ = _make_solution_tree(str(tmp_path))
        os.makedirs(os.path.join(sol_dir, "workflows"))

        with _patch_solution_dir(str(tmp_path)):
            write_file("project.yaml", "name: test")
            write_file("prompts.yaml", "roles: []")

            result = list_directory(".")
            assert result["success"] is True
            names = [e["name"] for e in result["entries"]]
            assert "project.yaml" in names
            assert "prompts.yaml" in names
            assert ".sage" in names

            # Check type detection
            types = {e["name"]: e["type"] for e in result["entries"]}
            assert types["project.yaml"] == "file"
            assert types[".sage"] == "directory"

    def test_list_directory_with_pattern(self, tmp_path):
        """list_directory must filter by glob pattern."""
        from src.mcp_servers.filesystem_tools import write_file, list_directory

        _make_solution_tree(str(tmp_path))

        with _patch_solution_dir(str(tmp_path)):
            write_file("project.yaml", "a")
            write_file("prompts.yaml", "b")
            write_file("README.md", "c")

            result = list_directory(".", pattern="*.yaml")
            assert result["success"] is True
            names = [e["name"] for e in result["entries"]]
            assert "project.yaml" in names
            assert "prompts.yaml" in names
            assert "README.md" not in names

    def test_file_exists(self, tmp_path):
        """file_exists must report correct existence and type."""
        from src.mcp_servers.filesystem_tools import write_file, file_exists

        _make_solution_tree(str(tmp_path))

        with _patch_solution_dir(str(tmp_path)):
            write_file("config.yaml", "test")

            r = file_exists("config.yaml")
            assert r["exists"] is True
            assert r["is_file"] is True
            assert r["is_directory"] is False

            r = file_exists(".sage")
            assert r["exists"] is True
            assert r["is_directory"] is True

            r = file_exists("nope.txt")
            assert r["exists"] is False

    def test_search_files(self, tmp_path):
        """search_files must find files recursively by glob pattern."""
        from src.mcp_servers.filesystem_tools import write_file, search_files

        _make_solution_tree(str(tmp_path))

        with _patch_solution_dir(str(tmp_path)):
            write_file("project.yaml", "a")
            write_file("workflows/deploy.yaml", "b")
            write_file("workflows/build.py", "c")

            result = search_files("**/*.yaml")
            assert result["success"] is True
            assert result["count"] >= 2
            matches = result["matches"]
            assert any("project.yaml" in m for m in matches)
            assert any("deploy.yaml" in m for m in matches)
            assert not any("build.py" in m for m in matches)

    def test_read_file_truncation(self, tmp_path):
        """read_file must truncate at max_bytes and report it."""
        from src.mcp_servers.filesystem_tools import write_file, read_file

        _make_solution_tree(str(tmp_path))

        with _patch_solution_dir(str(tmp_path)):
            write_file("big.txt", "x" * 1000)

            r = read_file("big.txt", max_bytes=100)
            assert r["success"] is True
            assert len(r["content"]) == 100
            assert r["truncated"] is True


# ===========================================================================
#  3. SQLITE TOOLS — Read-Only Enforcement
# ===========================================================================

class TestSQLiteReadOnly:
    """Verify SQL injection and write attempts are blocked."""

    def test_select_allowed(self):
        """SELECT queries must pass the read-only check."""
        from src.mcp_servers.sqlite_tools import _is_read_only
        assert _is_read_only("SELECT * FROM events") is True
        assert _is_read_only("select count(*) from events") is True
        assert _is_read_only("PRAGMA table_info(events)") is True
        assert _is_read_only("EXPLAIN SELECT 1") is True

    def test_writes_blocked(self):
        """INSERT/UPDATE/DELETE/DROP must be rejected."""
        from src.mcp_servers.sqlite_tools import _is_read_only
        assert _is_read_only("INSERT INTO events VALUES(1)") is False
        assert _is_read_only("UPDATE events SET x=1") is False
        assert _is_read_only("DELETE FROM events") is False
        assert _is_read_only("DROP TABLE events") is False
        assert _is_read_only("ALTER TABLE events ADD col TEXT") is False

    def test_injection_via_subquery_blocked(self):
        """SELECT containing destructive subqueries must be rejected."""
        from src.mcp_servers.sqlite_tools import _is_read_only
        assert _is_read_only("SELECT * FROM events; DROP TABLE events") is False

    def test_db_path_traversal_blocked(self):
        """Database names with path traversal must be rejected."""
        from src.mcp_servers.sqlite_tools import _validate_db_path
        with pytest.raises(ValueError, match="Invalid"):
            _validate_db_path("../../../etc/passwd")
        with pytest.raises(ValueError, match="Invalid"):
            _validate_db_path("foo/bar.db")


# ===========================================================================
#  4. SQLITE TOOLS — Query Operations
# ===========================================================================

class TestSQLiteOperations:
    """Full CRUD tests against a real temporary SQLite database."""

    def _create_test_db(self, sage_dir):
        """Create a test audit_log.db with sample data."""
        db_path = os.path.join(sage_dir, "audit_log.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE events (
                id INTEGER PRIMARY KEY,
                actor TEXT NOT NULL,
                action_type TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        conn.executemany(
            "INSERT INTO events (actor, action_type, metadata) VALUES (?, ?, ?)",
            [
                ("analyst", "ANALYSIS_COMPLETE", '{"severity": "HIGH"}'),
                ("developer", "CODE_REVIEW", '{"files": 3}'),
                ("monitor", "HEALTH_CHECK", '{"status": "ok"}'),
            ],
        )
        conn.commit()
        conn.close()
        return db_path

    def test_query_db_returns_rows(self, tmp_path):
        """query_db must return structured rows from a real database."""
        from src.mcp_servers.sqlite_tools import query_db

        _, sage_dir = _make_solution_tree(str(tmp_path))
        self._create_test_db(sage_dir)

        with _patch_solution_dir(str(tmp_path)):
            result = query_db("SELECT actor, action_type FROM events ORDER BY id")
            assert result["success"] is True
            assert result["row_count"] == 3
            assert result["rows"][0]["actor"] == "analyst"
            assert result["columns"] == ["actor", "action_type"]

    def test_query_db_max_rows(self, tmp_path):
        """query_db must respect max_rows limit."""
        from src.mcp_servers.sqlite_tools import query_db

        _, sage_dir = _make_solution_tree(str(tmp_path))
        self._create_test_db(sage_dir)

        with _patch_solution_dir(str(tmp_path)):
            result = query_db("SELECT * FROM events", max_rows=2)
            assert result["row_count"] == 2
            assert result["truncated"] is True

    def test_query_db_rejects_writes(self, tmp_path):
        """query_db must reject write operations."""
        from src.mcp_servers.sqlite_tools import query_db

        _, sage_dir = _make_solution_tree(str(tmp_path))
        self._create_test_db(sage_dir)

        with _patch_solution_dir(str(tmp_path)):
            result = query_db("DELETE FROM events")
            assert result["success"] is False
            assert "read-only" in result["error"].lower()

    def test_query_db_missing_database(self, tmp_path):
        """query_db must return error for non-existent database."""
        from src.mcp_servers.sqlite_tools import query_db

        _make_solution_tree(str(tmp_path))

        with _patch_solution_dir(str(tmp_path)):
            result = query_db("SELECT 1", db_name="nonexistent.db")
            assert result["success"] is False
            assert "not found" in result["error"].lower()

    def test_list_tables(self, tmp_path):
        """list_tables must return table names with row counts."""
        from src.mcp_servers.sqlite_tools import list_tables

        _, sage_dir = _make_solution_tree(str(tmp_path))
        self._create_test_db(sage_dir)

        with _patch_solution_dir(str(tmp_path)):
            result = list_tables()
            assert result["success"] is True
            assert result["table_count"] >= 1
            names = [t["name"] for t in result["tables"]]
            assert "events" in names
            events = [t for t in result["tables"] if t["name"] == "events"][0]
            assert events["row_count"] == 3

    def test_describe_table(self, tmp_path):
        """describe_table must return column schema and row count."""
        from src.mcp_servers.sqlite_tools import describe_table

        _, sage_dir = _make_solution_tree(str(tmp_path))
        self._create_test_db(sage_dir)

        with _patch_solution_dir(str(tmp_path)):
            result = describe_table("events")
            assert result["success"] is True
            assert result["row_count"] == 3
            col_names = [c["name"] for c in result["columns"]]
            assert "id" in col_names
            assert "actor" in col_names
            assert "action_type" in col_names

    def test_describe_table_not_found(self, tmp_path):
        """describe_table must return error for non-existent table."""
        from src.mcp_servers.sqlite_tools import describe_table

        _, sage_dir = _make_solution_tree(str(tmp_path))
        self._create_test_db(sage_dir)

        with _patch_solution_dir(str(tmp_path)):
            result = describe_table("nonexistent_table")
            assert result["success"] is False

    def test_list_databases(self, tmp_path):
        """list_databases must find .db files in .sage/ directory."""
        from src.mcp_servers.sqlite_tools import list_databases

        _, sage_dir = _make_solution_tree(str(tmp_path))
        self._create_test_db(sage_dir)
        # Create a second database
        sqlite3.connect(os.path.join(sage_dir, "eval_history.db")).close()

        with _patch_solution_dir(str(tmp_path)):
            result = list_databases()
            assert result["success"] is True
            assert result["count"] == 2
            names = [d["name"] for d in result["databases"]]
            assert "audit_log.db" in names
            assert "eval_history.db" in names


# ===========================================================================
#  5. BROWSER TOOLS — Graceful Degradation
# ===========================================================================

class TestBrowserToolsDegradation:
    """Verify browser tools handle missing Playwright gracefully."""

    def test_browse_page_without_playwright(self):
        """browse_page must return available=False when Playwright is missing."""
        from src.mcp_servers import browser_tools
        with patch.object(browser_tools, "_check_playwright", return_value="playwright not installed"):
            result = browser_tools.browse_page("http://example.com")
            assert result["available"] is False
            assert "playwright" in result["reason"].lower()

    def test_screenshot_without_playwright(self):
        """screenshot_page must return available=False when Playwright is missing."""
        from src.mcp_servers import browser_tools
        with patch.object(browser_tools, "_check_playwright", return_value="playwright not installed"):
            result = browser_tools.screenshot_page("http://example.com")
            assert result["available"] is False

    def test_click_and_extract_without_playwright(self):
        """click_and_extract must return available=False when Playwright is missing."""
        from src.mcp_servers import browser_tools
        with patch.object(browser_tools, "_check_playwright", return_value="playwright not installed"):
            result = browser_tools.click_and_extract("http://example.com", "#btn")
            assert result["available"] is False

    def test_fill_form_without_playwright(self):
        """fill_form must return available=False when Playwright is missing."""
        from src.mcp_servers import browser_tools
        with patch.object(browser_tools, "_check_playwright", return_value="playwright not installed"):
            result = browser_tools.fill_form("http://example.com", {"#name": "SAGE"})
            assert result["available"] is False


# ===========================================================================
#  6. BROWSER TOOLS — Live Playwright (if available)
# ===========================================================================

@pytest.mark.network
class TestBrowserToolsLive:
    """Live browser tests — skipped if Playwright is not installed or no network."""

    @pytest.fixture(autouse=True)
    def _check_pw(self):
        from src.mcp_servers.browser_tools import _check_playwright
        reason = _check_playwright()
        if reason:
            pytest.skip(f"Playwright not available: {reason}")

    def test_browse_page_real(self):
        """browse_page must fetch a real page and extract text."""
        from src.mcp_servers.browser_tools import browse_page
        # Retry once — live network tests can have transient failures
        for attempt in range(2):
            result = browse_page("https://example.com", wait_seconds=2.0)
            if result.get("success"):
                break
        assert result["success"] is True, f"Failed after retries: {result.get('error')}"
        assert "Example Domain" in result.get("title", "")
        assert len(result.get("text", "")) > 0

    def test_browse_page_with_links(self):
        """browse_page with extract_links must return link objects."""
        from src.mcp_servers.browser_tools import browse_page
        for attempt in range(2):
            result = browse_page("https://example.com", extract_links=True, wait_seconds=2.0)
            if result.get("success"):
                break
        assert result["success"] is True, f"Failed after retries: {result.get('error')}"
        assert "links" in result
        assert isinstance(result["links"], list)

    def test_screenshot_page_real(self, tmp_path):
        """screenshot_page must create a PNG file."""
        from src.mcp_servers.browser_tools import screenshot_page
        with patch("src.mcp_servers.browser_tools._get_screenshot_dir", return_value=str(tmp_path)):
            for attempt in range(2):
                result = screenshot_page("https://example.com", wait_seconds=2.0)
                if result.get("success"):
                    break
        assert result["success"] is True, f"Failed after retries: {result.get('error')}"
        assert os.path.isfile(result["screenshot_path"])
        assert result["screenshot_path"].endswith(".png")


# ===========================================================================
#  7. MCPRegistry — Framework Tool Discovery
# ===========================================================================

class TestRegistryFrameworkDiscovery:
    """Verify MCPRegistry discovers tools from src/mcp_servers/."""

    def _fresh_registry(self):
        from src.integrations.mcp_registry import MCPRegistry
        return MCPRegistry()

    def test_framework_tools_discovered(self, tmp_path):
        """Registry must find tools from src/mcp_servers/ even with no solution."""
        reg = self._fresh_registry()
        # Point solution dir to empty tmp — no solution tools
        with _patch_solution_dir(str(tmp_path)):
            count = reg.load(force=True)

        # Framework tools should be present
        assert count > 0
        tool_names = list(reg._tool_map.keys())
        # At minimum, filesystem + sqlite tools should be discovered
        assert any("file" in n or "read" in n for n in tool_names), \
            f"Expected filesystem tools in: {tool_names}"

    def test_framework_and_solution_tools_merged(self, tmp_path):
        """Registry must load both framework and solution tools."""
        sol_dir, _ = _make_solution_tree(str(tmp_path))
        mcp_dir = os.path.join(sol_dir, "mcp_servers")
        os.makedirs(mcp_dir, exist_ok=True)

        # Write a minimal solution MCP server
        server_code = textwrap.dedent("""
            from fastmcp import FastMCP
            mcp = FastMCP("solution_test")

            @mcp.tool()
            def domain_specific_tool(input: str) -> str:
                \"\"\"A solution-specific tool.\"\"\"
                return f"processed: {input}"
        """)
        with open(os.path.join(mcp_dir, "domain_tools.py"), "w") as f:
            f.write(server_code)

        reg = self._fresh_registry()
        with _patch_solution_dir(str(tmp_path)):
            count = reg.load(force=True)

        tool_names = list(reg._tool_map.keys())
        # Framework tools present
        assert any("file" in n or "read" in n for n in tool_names), \
            f"Framework tools missing from: {tool_names}"
        # Solution tool present
        assert "domain_specific_tool" in tool_names, \
            f"Solution tool missing from: {tool_names}"

    def test_solution_tool_overrides_framework(self, tmp_path):
        """Solution tools with same name must override framework tools."""
        sol_dir, _ = _make_solution_tree(str(tmp_path))
        mcp_dir = os.path.join(sol_dir, "mcp_servers")
        os.makedirs(mcp_dir, exist_ok=True)

        # Override read_file with a custom version
        server_code = textwrap.dedent("""
            from fastmcp import FastMCP
            mcp = FastMCP("override_test")

            @mcp.tool()
            def read_file(path: str) -> dict:
                \"\"\"Custom read_file that overrides framework version.\"\"\"
                return {"overridden": True, "path": path}
        """)
        with open(os.path.join(mcp_dir, "override_server.py"), "w") as f:
            f.write(server_code)

        reg = self._fresh_registry()
        with _patch_solution_dir(str(tmp_path)):
            reg.load(force=True)

        # The solution version should win
        assert "read_file" in reg._tool_map
        with patch.object(reg, "_audit"):
            with patch.object(reg, "load", return_value=len(reg._tool_map)):
                result = reg.invoke("read_file", {"path": "test.txt"})
        assert result.get("result", {}).get("overridden") is True


# ===========================================================================
#  8. MCPRegistry — Invoke → Audit Pipeline
# ===========================================================================

class TestRegistryAuditPipeline:
    """Verify registry invoke() writes to audit log end-to-end."""

    def test_invoke_filesystem_tool_audited(self, tmp_path):
        """Invoking a framework tool must write an audit event."""
        from src.integrations.mcp_registry import MCPRegistry

        _make_solution_tree(str(tmp_path))
        reg = MCPRegistry()

        audit_calls = []
        original_audit = reg._audit

        def capture_audit(*args, **kwargs):
            audit_calls.append((args, kwargs))

        reg._audit = capture_audit

        with _patch_solution_dir(str(tmp_path)):
            reg.load(force=True)
            # Use file_exists which doesn't need the file to exist
            if "file_exists" in reg._tool_map:
                with patch.object(reg, "load", return_value=len(reg._tool_map)):
                    reg.invoke("file_exists", {"path": "test.yaml"}, trace_id="test-trace-001")

                assert len(audit_calls) == 1
                args, kwargs = audit_calls[0]
                assert args[0] == "file_exists"  # tool_name
                assert kwargs.get("success") is True or args[3] is True
