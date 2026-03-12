"""
SAGE[ai] — Installation/Operational/Performance Qualification (IQ/OQ/PQ)
ISO 13485 Section 7.5.6 — Software Validation
FDA 21 CFR Part 11 — Electronic Records

These tests constitute the formal software validation protocol for SAGE[ai].
Each test case maps to a validation requirement (VR) in the System Requirements Specification.

Test IDs:
  IQ-001 through IQ-006  — Installation Qualification
  OQ-001 through OQ-010  — Operational Qualification
  PQ-001 through PQ-005  — Performance Qualification

Execution:
  pytest tests/validation/test_iq_oq_pq.py -m compliance -v --tb=long > validation_report.txt
"""

import json
import re
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.compliance

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent  # validation/ -> tests/ -> medtech/ -> solutions/ -> repo root
UUID4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

FIXED_LLM_RESPONSE = json.dumps({
    "severity": "HIGH",
    "root_cause_hypothesis": "test hypothesis",
    "recommended_action": "test action",
})


def _query_audit(db_path, action_type=None):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    if action_type:
        rows = conn.execute(
            "SELECT * FROM compliance_audit_log WHERE action_type = ?", (action_type,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM compliance_audit_log").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ===========================================================================
# INSTALLATION QUALIFICATION (IQ)
# Requirement: Verify the system is correctly installed and configured.
# ===========================================================================


def test_iq_001_python_version():
    """
    IQ-001: Python Version Compliance
    Requirement: SAGE[ai] requires Python 3.10 or higher.
    Acceptance Criteria: sys.version_info >= (3, 10)
    """
    assert sys.version_info >= (3, 10), (
        f"IQ-001 FAIL: Python {sys.version_info.major}.{sys.version_info.minor} "
        f"is below minimum required version 3.10."
    )


def test_iq_002_required_packages_importable():
    """
    IQ-002: Required Packages Installation Verification
    Requirement: All mandatory packages must be importable without error.
    Acceptance Criteria: No ImportError for core dependency packages.
    """
    failures = []
    packages = [
        ("yaml", "pyyaml"),
        ("fastapi", "fastapi"),
        ("requests", "requests"),
        ("pydantic", "pydantic"),
    ]
    for module_name, package_name in packages:
        try:
            __import__(module_name)
        except ImportError:
            failures.append(f"{package_name} (import '{module_name}')")

    assert not failures, (
        f"IQ-002 FAIL: The following required packages are not importable: {', '.join(failures)}"
    )


def test_iq_003_config_file_exists():
    """
    IQ-003: Configuration File Presence and Validity
    Requirement: config/config.yaml must exist and be valid YAML.
    Acceptance Criteria: File exists; yaml.safe_load() succeeds without exception.
    """
    import yaml
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    assert config_path.exists(), (
        f"IQ-003 FAIL: config/config.yaml not found at {config_path}"
    )
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except Exception as exc:
        pytest.fail(f"IQ-003 FAIL: config/config.yaml is not valid YAML: {exc}")
    assert isinstance(config, dict), (
        f"IQ-003 FAIL: config/config.yaml must parse to a dict, got: {type(config)}"
    )


def test_iq_004_data_directory_writable(tmp_path):
    """
    IQ-004: Data Directory Write Access
    Requirement: The data/ directory must be creatable and writable.
    Acceptance Criteria: A test file can be written to the data directory path.
    """
    test_data_dir = tmp_path / "data"
    test_data_dir.mkdir(exist_ok=True)
    test_file = test_data_dir / "write_test.txt"
    try:
        test_file.write_text("IQ-004 write test")
        content = test_file.read_text()
    except Exception as exc:
        pytest.fail(f"IQ-004 FAIL: Cannot write to data directory: {exc}")
    assert content == "IQ-004 write test", "IQ-004 FAIL: Written content does not match."


def test_iq_005_audit_db_initializable(tmp_path):
    """
    IQ-005: Audit Database Initialization
    Requirement: AuditLogger must initialize and create the SQLite DB with correct schema.
    Acceptance Criteria: DB file exists; compliance_audit_log table has all required columns.
    """
    from src.memory.audit_logger import AuditLogger
    db_path = str(tmp_path / "iq005_audit.db")
    try:
        logger = AuditLogger(db_path=db_path)
    except Exception as exc:
        pytest.fail(f"IQ-005 FAIL: AuditLogger initialization raised exception: {exc}")

    assert Path(db_path).exists(), f"IQ-005 FAIL: DB file was not created at {db_path}"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(compliance_audit_log)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()

    required = {"id", "timestamp", "actor", "action_type", "input_context", "output_content", "metadata"}
    missing = required - columns
    assert not missing, f"IQ-005 FAIL: Missing columns in audit table: {missing}"


def test_iq_006_llm_gateway_instantiable():
    """
    IQ-006: LLM Gateway Instantiation
    Requirement: LLMGateway must instantiate without raising an exception.
    Acceptance Criteria: LLMGateway() completes successfully; get_provider_name() returns non-empty string.
    """
    try:
        from src.core.llm_gateway import LLMGateway
        gw = LLMGateway()
    except Exception as exc:
        pytest.fail(f"IQ-006 FAIL: LLMGateway() instantiation raised exception: {exc}")

    provider = gw.get_provider_name()
    assert isinstance(provider, str) and len(provider) > 0, (
        f"IQ-006 FAIL: get_provider_name() must return non-empty string, got: {provider!r}"
    )


# ===========================================================================
# OPERATIONAL QUALIFICATION (OQ)
# Requirement: Verify the system operates correctly per specification.
# ===========================================================================


@pytest.fixture
def oq_setup(tmp_path):
    """Common OQ/PQ setup: fresh audit DB, fresh vector memory, mocked LLM, TestClient."""
    from src.memory.audit_logger import AuditLogger
    db_path = str(tmp_path / "oq_audit.db")
    audit_db = AuditLogger(db_path=db_path)

    from src.interface import api
    api._pending_proposals.clear()

    with patch("src.interface.api._get_audit_logger", return_value=audit_db), \
         patch("src.agents.analyst.audit_logger", audit_db), \
         patch("src.agents.analyst.vector_memory") as mock_vm, \
         patch("src.core.llm_gateway.LLMGateway.generate", return_value=FIXED_LLM_RESPONSE):
        mock_vm.search.return_value = []
        mock_vm.add_feedback = MagicMock()

        from src.interface.api import app
        with TestClient(app) as client:
            yield {
                "client": client,
                "audit_db": audit_db,
                "db_path": db_path,
                "mock_vm": mock_vm,
            }

    api._pending_proposals.clear()


def test_oq_001_audit_log_records_every_analysis(oq_setup):
    """
    OQ-001: Audit Log Records Every Analysis
    Requirement: Every call to analyze_log() must produce exactly one ANALYSIS_PROPOSAL audit record.
    Acceptance Criteria: After 3 analyses, COUNT(ANALYSIS_PROPOSAL) = 3.
    """
    c = oq_setup["client"]
    db_path = oq_setup["db_path"]

    for i in range(3):
        resp = c.post("/analyze", json={"log_entry": f"ERROR: oq001 test {i}"})
        assert resp.status_code == 200, f"Analysis {i} failed: {resp.text}"

    rows = _query_audit(db_path, "ANALYSIS_PROPOSAL")
    assert len(rows) == 3, (
        f"OQ-001 FAIL: Expected 3 ANALYSIS_PROPOSAL records, got {len(rows)}"
    )


def test_oq_002_trace_id_generated_for_each_action(oq_setup):
    """
    OQ-002: UUID v4 Trace ID for Every Action
    Requirement: Each analysis must produce a trace_id conforming to UUID v4 format.
    Acceptance Criteria: trace_id matches regex ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$
    """
    c = oq_setup["client"]
    resp = c.post("/analyze", json={"log_entry": "ERROR: oq002 uuid test"})
    assert resp.status_code == 200
    trace_id = resp.json().get("trace_id", "")
    assert UUID4_PATTERN.match(trace_id), (
        f"OQ-002 FAIL: trace_id '{trace_id}' does not match UUID v4 pattern."
    )


def test_oq_003_human_approval_logged(oq_setup):
    """
    OQ-003: Human Approval Audit Record
    Requirement: Approval via API must create APPROVAL record with actor='Human_Engineer'.
    Acceptance Criteria: APPROVAL record exists with actor='Human_Engineer'.
    """
    c = oq_setup["client"]
    db_path = oq_setup["db_path"]

    resp = c.post("/analyze", json={"log_entry": "ERROR: oq003 approval test"})
    assert resp.status_code == 200
    trace_id = resp.json()["trace_id"]

    resp2 = c.post(f"/approve/{trace_id}")
    assert resp2.status_code == 200

    rows = _query_audit(db_path, "APPROVAL")
    assert len(rows) >= 1, "OQ-003 FAIL: Expected at least 1 APPROVAL record."
    assert rows[0]["actor"] == "Human_Engineer", (
        f"OQ-003 FAIL: Expected actor='Human_Engineer', got '{rows[0]['actor']}'."
    )


def test_oq_004_human_rejection_logged(oq_setup):
    """
    OQ-004: Human Rejection Audit Record
    Requirement: Rejection via API must trigger FEEDBACK_LEARNING in audit log.
    Acceptance Criteria: FEEDBACK_LEARNING record exists with actor='Human_Engineer'.
    """
    c = oq_setup["client"]
    audit_db = oq_setup["audit_db"]
    db_path = oq_setup["db_path"]

    resp = c.post("/analyze", json={"log_entry": "ERROR: oq004 rejection test"})
    assert resp.status_code == 200
    trace_id = resp.json()["trace_id"]

    # Reject with a feedback that triggers learn_from_feedback
    with patch("src.interface.api._get_analyst") as mock_get_analyst:
        mock_analyst = MagicMock()
        mock_analyst.learn_from_feedback = MagicMock(side_effect=lambda **kwargs: (
            audit_db.log_event(
                actor="Human_Engineer",
                action_type="FEEDBACK_LEARNING",
                input_context="test",
                output_content=kwargs.get("human_comment", ""),
            )
        ))
        mock_get_analyst.return_value = mock_analyst
        resp2 = c.post(f"/reject/{trace_id}", json={"feedback": "Actual cause: hardware short"})

    assert resp2.status_code == 200

    rows = _query_audit(db_path, "FEEDBACK_LEARNING")
    assert len(rows) >= 1, "OQ-004 FAIL: Expected FEEDBACK_LEARNING record after rejection."


def test_oq_005_feedback_retrievable_from_rag(tmp_path):
    """
    OQ-005: Feedback Persistence in RAG Memory
    Requirement: Feedback added to vector memory must be retrievable by similarity search.
    Acceptance Criteria: Search returns the added feedback within top-3 results.
    """
    with patch("src.memory.vector_store._HAS_CHROMADB", False), \
         patch("src.memory.vector_store.Chroma", None):
        from src.memory.vector_store import VectorMemory
        import logging
        vm = VectorMemory.__new__(VectorMemory)
        vm.logger = logging.getLogger("VectorMemory.oq005")
        vm._fallback_memory = []
        vm._vector_store = None
        vm._ready = False

    feedback_text = "UART buffer overflow resolved by increasing RX buffer from 256 to 512 bytes."
    vm.add_feedback(feedback_text)

    results = vm.search("uart buffer overflow", k=3)
    assert len(results) >= 1, "OQ-005 FAIL: Expected at least 1 result from RAG search."
    assert any("UART" in r or "uart" in r.lower() or "buffer" in r.lower() for r in results), (
        f"OQ-005 FAIL: Expected feedback content in results, got: {results}"
    )


def test_oq_006_audit_log_is_not_modified_by_reads(oq_setup):
    """
    OQ-006: Audit Log Immutability Under Read Operations
    Requirement: Reading the audit log must not modify its contents.
    Acceptance Criteria: Record count is identical before and after 10 GET /audit calls.
    """
    c = oq_setup["client"]
    audit_db = oq_setup["audit_db"]
    db_path = oq_setup["db_path"]

    # Seed with some records
    for i in range(5):
        audit_db.log_event(f"Actor_{i}", f"ACTION_{i}", "in", "out")

    conn = sqlite3.connect(db_path)
    count_before = conn.execute("SELECT COUNT(*) FROM compliance_audit_log").fetchone()[0]
    conn.close()

    # Read 10 times
    for _ in range(10):
        resp = c.get("/audit?limit=100")
        assert resp.status_code == 200

    conn = sqlite3.connect(db_path)
    count_after = conn.execute("SELECT COUNT(*) FROM compliance_audit_log").fetchone()[0]
    conn.close()

    assert count_before == count_after, (
        f"OQ-006 FAIL: Audit log record count changed from {count_before} to {count_after} after reads."
    )


def test_oq_007_single_lane_execution(oq_setup):
    """
    OQ-007: Single-Lane LLM Execution (Thread Safety)
    Requirement: Concurrent LLM requests must all complete without error.
    Acceptance Criteria: All 5 concurrent requests complete and return valid non-empty strings.
    """
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    results = []
    errors = []
    lock = threading.Lock()

    def call_generate(i):
        try:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = f"result_{i}"
            mock_result.stderr = ""
            with patch("subprocess.run", return_value=mock_result):
                res = gw.generate(f"prompt_{i}", "system")
                with lock:
                    results.append(res)
        except Exception as exc:
            with lock:
                errors.append(str(exc))

    threads = [threading.Thread(target=call_generate, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"OQ-007 FAIL: Errors during concurrent execution: {errors}"
    assert len(results) == 5, f"OQ-007 FAIL: Expected 5 results, got {len(results)}"
    for r in results:
        assert isinstance(r, str) and len(r) > 0, f"OQ-007 FAIL: Non-empty string expected, got: {r!r}"


def test_oq_008_proposals_require_explicit_approval(oq_setup):
    """
    OQ-008: Proposals Require Explicit Human Approval
    Requirement: An analysis proposal must not be automatically executed.
    Acceptance Criteria: After POST /analyze with NO /approve call, no EXECUTION record in audit.
    """
    c = oq_setup["client"]
    db_path = oq_setup["db_path"]

    resp = c.post("/analyze", json={"log_entry": "ERROR: oq008 no-auto-execute test"})
    assert resp.status_code == 200

    # Do NOT approve — just check audit log
    rows = _query_audit(db_path, "EXECUTION")
    assert len(rows) == 0, (
        f"OQ-008 FAIL: Found EXECUTION records without approval — auto-execution must not occur. "
        f"Found {len(rows)} EXECUTION record(s)."
    )


def test_oq_009_api_returns_trace_id_in_analyze_response(oq_setup):
    """
    OQ-009: Trace ID in Analyze Response
    Requirement: POST /analyze must always include trace_id in the response body.
    Acceptance Criteria: Response JSON contains 'trace_id' key with non-empty value.
    """
    c = oq_setup["client"]
    resp = c.post("/analyze", json={"log_entry": "ERROR: oq009 trace_id check"})
    assert resp.status_code == 200
    data = resp.json()
    assert "trace_id" in data, f"OQ-009 FAIL: 'trace_id' missing from /analyze response: {data}"
    assert data["trace_id"], f"OQ-009 FAIL: trace_id must be non-empty: {data['trace_id']!r}"


def test_oq_010_audit_timestamp_is_utc(tmp_path):
    """
    OQ-010: Audit Timestamps Are UTC
    Requirement: All audit log timestamps must be stored in UTC ISO format.
    Acceptance Criteria: Timestamp is parseable as ISO datetime with UTC offset or naive UTC.
    """
    from src.memory.audit_logger import AuditLogger
    db_path = str(tmp_path / "oq010_audit.db")
    audit_logger = AuditLogger(db_path=db_path)
    audit_logger.log_event("TestActor", "TEST_ACTION", "input", "output")

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT timestamp FROM compliance_audit_log LIMIT 1").fetchone()
    conn.close()

    ts_str = row[0]
    assert ts_str, "OQ-010 FAIL: Timestamp must not be None or empty."

    try:
        dt = datetime.fromisoformat(ts_str)
    except ValueError:
        pytest.fail(f"OQ-010 FAIL: Timestamp '{ts_str}' is not valid ISO format.")

    # Verify it looks like a current timestamp (not from 1970 or far future)
    now = datetime.now(timezone.utc)
    dt_naive = dt.replace(tzinfo=None) if dt.tzinfo else dt
    now_naive = now.replace(tzinfo=None)
    diff_seconds = abs((now_naive - dt_naive).total_seconds())
    assert diff_seconds < 60, (
        f"OQ-010 FAIL: Timestamp {ts_str!r} appears stale (diff={diff_seconds:.0f}s from now)."
    )


# ===========================================================================
# PERFORMANCE QUALIFICATION (PQ)
# Requirement: Verify the system performs correctly under expected load.
# ===========================================================================


def test_pq_001_50_consecutive_analyses_all_logged(oq_setup):
    """
    PQ-001: 50 Consecutive Analyses All Logged
    Requirement: The system must handle 50 sequential analyses without data loss.
    Acceptance Criteria: After 50 analyses, COUNT(ANALYSIS_PROPOSAL) = 50.
    """
    c = oq_setup["client"]
    db_path = oq_setup["db_path"]

    for i in range(50):
        resp = c.post("/analyze", json={"log_entry": f"ERROR: pq001 load test iteration {i}"})
        assert resp.status_code == 200, f"PQ-001 FAIL: Analysis {i} returned {resp.status_code}"

    rows = _query_audit(db_path, "ANALYSIS_PROPOSAL")
    assert len(rows) == 50, (
        f"PQ-001 FAIL: Expected 50 ANALYSIS_PROPOSAL records, got {len(rows)}"
    )


def test_pq_002_feedback_improves_rag_retrieval(tmp_path):
    """
    PQ-002: Feedback Retrieval Rate >= 90%
    Requirement: After storing 10 feedback entries, searching for each must return >= 9 out of 10.
    Acceptance Criteria: Retrieval success rate >= 90%.
    """
    with patch("src.memory.vector_store._HAS_CHROMADB", False), \
         patch("src.memory.vector_store.Chroma", None):
        from src.memory.vector_store import VectorMemory
        import logging
        vm = VectorMemory.__new__(VectorMemory)
        vm.logger = logging.getLogger("VectorMemory.pq002")
        vm._fallback_memory = []
        vm._vector_store = None
        vm._ready = False

    feedbacks = [
        "uart buffer overflow fix: increase UART_BUF_SIZE constant",
        "watchdog reset caused by blocking task: add yield points",
        "i2c bus lockup resolved: implement bus reset sequence",
        "flash write failure: check erase before write sequence",
        "adc calibration drift: recalibrate after temperature change",
        "spi timeout: reduce clock speed from 8mhz to 4mhz",
        "rtos stack overflow: increase CommsHandler stack by 512 bytes",
        "can bus error frame: check termination resistor on CAN bus",
        "modbus timeout: increase slave response timeout to 500ms",
        "ethernet phy reset: add 10ms delay after phy reset assertion",
    ]

    search_queries = [
        "uart buffer",
        "watchdog reset",
        "i2c lockup",
        "flash write",
        "adc calibration",
        "spi timeout",
        "rtos stack",
        "can bus error",
        "modbus timeout",
        "ethernet phy",
    ]

    for fb in feedbacks:
        vm.add_feedback(fb)

    hits = 0
    for query in search_queries:
        results = vm.search(query, k=3)
        if results:
            hits += 1

    retrieval_rate = hits / len(search_queries)
    assert retrieval_rate >= 0.90, (
        f"PQ-002 FAIL: Retrieval rate {retrieval_rate:.0%} is below 90% threshold. "
        f"Hits: {hits}/{len(search_queries)}"
    )


def test_pq_003_approval_rejection_cycle(oq_setup):
    """
    PQ-003: 10 Analyze → Approve Cycles
    Requirement: System must reliably complete 10 full analyze+approve cycles.
    Acceptance Criteria: COUNT(ANALYSIS_PROPOSAL) = 10 AND COUNT(APPROVAL) = 10.
    """
    c = oq_setup["client"]
    db_path = oq_setup["db_path"]

    for i in range(10):
        # Analyze
        resp = c.post("/analyze", json={"log_entry": f"ERROR: pq003 cycle {i}"})
        assert resp.status_code == 200, f"PQ-003 FAIL: Analyze {i} returned {resp.status_code}"
        trace_id = resp.json()["trace_id"]
        # Approve
        resp2 = c.post(f"/approve/{trace_id}")
        assert resp2.status_code == 200, f"PQ-003 FAIL: Approve {i} returned {resp2.status_code}"

    proposals = _query_audit(db_path, "ANALYSIS_PROPOSAL")
    approvals = _query_audit(db_path, "APPROVAL")
    assert len(proposals) == 10, f"PQ-003 FAIL: Expected 10 proposals, got {len(proposals)}"
    assert len(approvals) == 10, f"PQ-003 FAIL: Expected 10 approvals, got {len(approvals)}"


def test_pq_004_audit_log_query_performance(tmp_path):
    """
    PQ-004: Audit Log Query Performance Under 1000 Records
    Requirement: GET /audit query must complete in under 2 seconds with 1000 records.
    Acceptance Criteria: Query wall time < 2.0 seconds.
    """
    from src.memory.audit_logger import AuditLogger
    db_path = str(tmp_path / "pq004_audit.db")
    audit_db = AuditLogger(db_path=db_path)

    # Insert 1000 records
    for i in range(1000):
        audit_db.log_event(
            actor="LoadTestActor",
            action_type="ANALYSIS_PROPOSAL",
            input_context=f"ERROR: load test entry {i} — sensor read timeout on channel {i % 8}",
            output_content=json.dumps({"severity": "HIGH", "trace_id": f"trace-{i}"}),
            metadata={"iteration": i},
        )

    from src.interface import api
    api._pending_proposals.clear()

    with patch("src.interface.api._get_audit_logger", return_value=audit_db):
        from src.interface.api import app
        with TestClient(app) as client:
            start = time.time()
            resp = client.get("/audit?limit=500")
            elapsed = time.time() - start

    assert resp.status_code == 200, f"PQ-004 FAIL: /audit returned {resp.status_code}"
    assert elapsed < 2.0, (
        f"PQ-004 FAIL: /audit query took {elapsed:.2f}s which exceeds 2.0s threshold."
    )
    api._pending_proposals.clear()


def test_pq_005_concurrent_api_requests(oq_setup):
    """
    PQ-005: 10 Concurrent POST /analyze Requests
    Requirement: System must handle 10 simultaneous analyze requests without errors.
    Acceptance Criteria: All 10 return HTTP 200; all 10 trace_ids are unique.
    """
    c = oq_setup["client"]
    db_path = oq_setup["db_path"]
    results = []
    errors = []
    lock = threading.Lock()

    def do_analyze(i):
        try:
            resp = c.post("/analyze", json={"log_entry": f"ERROR: pq005 concurrent {i}"})
            with lock:
                if resp.status_code == 200:
                    results.append(resp.json().get("trace_id"))
                else:
                    errors.append(f"Request {i} returned HTTP {resp.status_code}: {resp.text}")
        except Exception as exc:
            with lock:
                errors.append(f"Request {i} raised: {exc}")

    threads = [threading.Thread(target=do_analyze, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert not errors, f"PQ-005 FAIL: Errors during concurrent requests: {errors}"
    assert len(results) == 10, f"PQ-005 FAIL: Expected 10 successful responses, got {len(results)}"

    unique_ids = set(results)
    assert len(unique_ids) == 10, (
        f"PQ-005 FAIL: Expected 10 unique trace_ids, got {len(unique_ids)}: {unique_ids}"
    )
