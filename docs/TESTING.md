# SAGE Framework — Testing Guide

**Document ID:** SAGE-AI-TEST-001
**Version:** 4.0
**Date:** 2026-03-24
**Classification:** Quality Management System Documentation
**Standard:** ISO 13485:2016 Section 7.5.6 — Software Validation

---

## Table of Contents

1. [Overview](#1-overview)
2. [Directory Structure](#2-directory-structure)
3. [Running Tests](#3-running-tests)
4. [Test Fixtures Reference](#4-test-fixtures-reference)
5. [Unit Test Cases](#5-unit-test-cases)
6. [Integration Test Cases](#6-integration-test-cases)
7. [MCP Server Test Cases](#7-mcp-server-test-cases)
8. [End-to-End Test Cases](#8-end-to-end-test-cases)
9. [Compliance Validation Tests (IQ/OQ/PQ)](#9-compliance-validation-tests-iqoqpq)
10. [Test Data](#10-test-data)
11. [Continuous Integration](#11-continuous-integration)
12. [Interpreting Results](#12-interpreting-results)
13. [Adding New Tests](#13-adding-new-tests)

---

## 1. Overview

### Test Philosophy

SAGE uses a four-tier testing pyramid aligned with ISO 13485 software validation requirements:

```
         ┌───────────┐
         │  IQ/OQ/PQ │  ← Formal compliance validation (medtech solution)
         ├───────────┤
         │  System   │  ← Full API lifecycle E2E (58 tests)
         ├───────────┤
         │    E2E    │  ← Full pipeline, mocked LLM
         ├───────────┤
         │Integration│  ← Live external services, skipped if unconfigured
         ├───────────┤
         │   Unit    │  ← Isolated, mocked, fast (53 test files)
         └───────────┘
```

**Tier 1 — Unit Tests** (`@pytest.mark.unit`):
Self-contained tests with all external dependencies mocked. No network calls, no hardware, no real databases beyond SQLite in tmp_path. Run in seconds. Target: 90%+ line coverage on `src/`. Includes nano-module tests in `tests/modules/`.

**Tier 2 — Integration Tests** (`@pytest.mark.integration`):
Tests that connect to real external services (GitLab, Teams, Metabase, Spira). Auto-skipped when the required environment variables are not present. Run against staging/test environments — never production.

**Tier 3 — End-to-End Tests** (`@pytest.mark.e2e`):
Full API pipeline tests using FastAPI TestClient with real AuditLogger (SQLite in tmp_path) and mocked LLM. Verify multi-step flows like analyze → approve → audit trail.

**Tier 4 — Compliance Tests** (`@pytest.mark.compliance`):
Formal IQ/OQ/PQ tests per ISO 13485 Section 7.5.6. These live in `solutions/medtech/tests/validation/` and constitute the software validation protocol for the medical device QMS. Output of `pytest -m compliance --tb=long` serves as validation evidence.

### Test Counts Summary

| Suite | Location | Files | Notes |
|---|---|---|---|
| Framework (all) | `tests/` | 53 test files | `make test` |
| — Nano-modules | `tests/modules/` | 5 test files | Subset of framework, instant |
| — System E2E | `tests/system/` | 1 test file (58 tests) | Full API lifecycle |
| medtech solution | `solutions/medtech/tests/` | varies | `make test-medtech` |
| **Total** | | **53+ files** | `make test-all` |

### Coverage Targets

| Layer | Target | Notes |
|---|---|---|
| Unit | 90% line coverage | `src/` |
| Nano-modules | 100% line coverage | `src/modules/` |
| Integration | Critical paths only | Live services required |
| E2E | Key user workflows | Analyze/approve, MR, monitor |
| Compliance | 100% IQ/OQ/PQ pass | Required for QMS sign-off |

### pytest Markers

| Marker | Purpose | External Deps? |
|---|---|---|
| `unit` | Fast isolated tests (includes nano-module tests) | None |
| `integration` | Live service tests | GitLab / Teams / Metabase / Spira |
| `e2e` | Full pipeline | None (LLM mocked) |
| `hardware` | J-Link/Serial device | Physical hardware |
| `compliance` | IQ/OQ/PQ formal validation (medtech) | None (all mocked) |
| `mcp` | MCP server tool tests | Requires `fastmcp` |
| `slow` | Tests taking >5 seconds | — |

---

## 2. Directory Structure

The test suite is split between **framework tests** (in `tests/`) and **solution tests** (in `solutions/<name>/tests/`).

### Framework Tests (`tests/`) — 53 test files

```
tests/
│
├── conftest.py                         # Shared fixtures for all test tiers
│
├── modules/                            # Nano-module tests
│   ├── test_severity.py
│   ├── test_json_extractor.py
│   ├── test_trace_id.py
│   ├── test_payload_validator.py
│   └── test_event_bus.py
│
├── system/                             # System E2E tests (58 tests)
│   └── test_system_e2e.py
│
├── test_llm_gateway.py                 # LLM Gateway unit tests
├── test_audit_logger.py                # AuditLogger unit tests
├── test_vector_store.py                # VectorMemory unit tests
├── test_analyst_agent.py               # AnalystAgent unit tests
├── test_developer_agent.py             # DeveloperAgent unit tests
├── test_monitor_agent.py               # MonitorAgent unit tests
├── test_queue_manager.py               # TaskQueue/TaskWorker unit tests
├── test_api.py                         # FastAPI endpoint unit tests
├── test_agent_endpoints.py             # Agent run/stream endpoint tests
├── test_agent_factory.py               # Agent factory / hire tests
├── test_agents_active_endpoint.py      # Active agents status endpoint
├── test_build_orchestrator.py          # Build orchestrator unit tests
├── test_build_orchestrator_e2e.py      # Build orchestrator E2E tests
├── test_budget_enforcement.py          # LLM budget enforcement tests
├── test_chat_audit.py                  # Chat audit trail tests
├── test_chat_execute_endpoint.py       # Chat execute action tests
├── test_chat_router.py                 # Chat router unit tests
├── test_critic_agent.py                # Critic agent tests
├── test_cross_team_routing.py          # Cross-team task routing tests
├── test_dev_users_endpoint.py          # Dev users endpoint tests
├── test_folder_scanner.py              # Folder scanner tests
├── test_knowledge_channel.py           # Knowledge channel tests
├── test_knowledge_sync.py              # Knowledge sync tests
├── test_llm_health_endpoint.py         # LLM health endpoint tests
├── test_multi_llm.py                   # Multi-LLM provider pool tests
├── test_onboarding_import_endpoints.py # Onboarding import endpoints
├── test_onboarding_org.py              # Onboarding org template tests
├── test_openshell_runner.py            # OpenShell sandbox tests
├── test_openswe_runner.py              # OpenSWE runner tests
├── test_org_api.py                     # Org API endpoint tests
├── test_org_loader.py                  # Org loader unit tests
├── test_org_project_loader.py          # Org project loader tests
├── test_org_vector.py                  # Org vector store tests
├── test_phase15_mcp.py                 # MCP integration tests
├── test_phase1_integrations.py         # Phase 1 integration tests
├── test_phase2_n8n.py                  # n8n webhook tests
├── test_phase3_langgraph.py            # LangGraph integration tests
├── test_phase4_autogen.py              # AutoGen integration tests
├── test_phase5_streaming.py            # SSE streaming tests
├── test_phase6_onboarding.py           # Onboarding feature tests
├── test_phase7_11_features.py          # Phase 7-11 feature tests
├── test_proposal_executor.py           # Proposal executor tests
├── test_repo_map.py                    # Repo map tests
├── test_task_completion.py             # Task completion tests
├── test_task_hooks.py                  # Task hook tests
├── test_task_scheduler.py              # Task scheduler tests
├── test_undo_endpoint.py               # Proposal undo tests
├── test_wave_subagents.py              # Wave sub-agent tests
└── test_worktree_manager.py            # Git worktree manager tests
```

### medtech Solution Tests (`solutions/medtech/tests/`) — 32 tests

```
solutions/medtech/tests/
│
├── mcp/
│   ├── test_serial_mcp.py         # Serial port MCP server tests
│   ├── test_jlink_mcp.py          # J-Link MCP server tests (hardware-skippable)
│   ├── test_metabase_mcp.py       # Metabase MCP server tests
│   ├── test_spira_mcp.py          # Spira MCP server tests
│   └── test_teams_mcp.py          # Teams MCP server tests
│
├── integration/
│   ├── test_gitlab_integration.py   # GitLab API integration tests
│   ├── test_teams_integration.py    # Teams Graph API integration tests
│   ├── test_metabase_integration.py # Metabase integration tests
│   └── test_spira_integration.py    # Spira integration tests
│
├── e2e/
│   ├── test_analyze_approve_flow.py        # Analyze/approve/reject E2E
│   ├── test_mr_workflow.py                 # MR create/review E2E
│   └── test_monitor_to_notification_flow.py # Monitor event routing E2E
│
└── validation/
    └── test_iq_oq_pq.py           # ISO 13485 IQ/OQ/PQ formal validation
```

---

## 3. Running Tests

### Prerequisites

```bash
# Create virtual environment (one-time)
make venv

# For MCP server tests, also install fastmcp into the venv:
.venv\Scripts\pip install fastmcp   # Windows
# .venv/bin/pip install fastmcp     # Linux/Mac
```

### Make Shortcuts (Recommended)

```bash
make test               # Framework unit tests (tests/)
make test-all           # Framework + medtech solution tests
make test-api           # API endpoint tests only
make test-compliance    # Compliance/IQ/OQ/PQ tests (medtech QMS sign-off)
make test-medtech       # medtech solution tests
make test-medtech-team  # medtech_team solution tests
make test-meditation-app # meditation_app solution tests
make test-four-in-a-line # four_in_a_line solution tests
make test-solution PROJECT=X  # Any solution's tests
make test-mcp           # MCP server tests (needs fastmcp)
make test-integration   # Integration tests (needs live services)
```

### Nano-Module Tests (instant)

```bash
# Run just the nano-module tests (119 tests, no deps, very fast)
pytest tests/modules/ -v
```

### All Framework Unit Tests

```bash
# All unit tests (no external deps, fast)
pytest -m unit

# All tests except hardware and integration
pytest -m "not hardware and not integration"

# Specific test file
pytest tests/test_api.py -v

# Specific test function
pytest tests/test_audit_logger.py::test_log_event_returns_uuid -v

# With coverage report
pytest -m unit --cov=src --cov-report=html

# With coverage in terminal
pytest -m unit --cov=src --cov-report=term-missing

# Run and stop after first failure
pytest -x

# Show 10 slowest tests
pytest --durations=10
```

### medtech Solution Tests

```bash
# All medtech solution tests
make test-medtech
# Equivalent to: pytest solutions/medtech/tests/ -v

# Compliance/validation tests only (for QMS sign-off)
pytest -m compliance -v --tb=long

# Compliance tests with output saved to file (validation evidence)
pytest -m compliance --tb=long > docs/validation_report.txt

# MCP tests (require fastmcp installed)
pytest solutions/medtech/tests/mcp/ -v

# Integration tests (require configured env vars — auto-skipped if absent)
pytest -m integration -v

# E2E tests only
pytest -m e2e -v

# Hardware tests (requires J-Link + serial device)
pytest -m hardware -v
```

### Environment Variables for Integration Tests

Set these to enable integration test tiers:

```bash
# GitLab integration
export GITLAB_URL="https://gitlab.yourcompany.com"
export GITLAB_TOKEN="glpat-xxxxxxxxxxxx"
export GITLAB_PROJECT_ID="123"
export GITLAB_TEST_MR_IID="7"   # Optional: specific MR for review/pipeline tests

# Microsoft Teams
export TEAMS_TENANT_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export TEAMS_CLIENT_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export TEAMS_CLIENT_SECRET="your-client-secret"
export TEAMS_TEAM_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export TEAMS_CHANNEL_ID="19:xxxxxxxx@thread.tacv2"
export TEAMS_INCOMING_WEBHOOK_URL="https://yourcompany.webhook.office.com/webhookb2/..."

# Metabase
export METABASE_URL="https://metabase.yourcompany.com"
export METABASE_USERNAME="admin@yourcompany.com"
export METABASE_PASSWORD="your-password"
export METABASE_ERROR_QUESTION_ID="42"

# Spira
export SPIRA_URL="https://spira.yourcompany.com"
export SPIRA_USERNAME="apiuser"
export SPIRA_API_KEY="{your-api-key}"
export SPIRA_PROJECT_ID="1"
```

---

## 4. Test Fixtures Reference

All fixtures are defined in `tests/conftest.py` and are available to all test modules.

| Fixture | Scope | Description | Usage |
|---|---|---|---|
| `tmp_audit_db` | function | Fresh `AuditLogger` backed by a temp SQLite file. Each test gets isolated storage. | `def test_foo(tmp_audit_db): tmp_audit_db.log_event(...)` |
| `tmp_vector_memory` | function | `VectorMemory` instance in fallback mode (no ChromaDB). In-memory keyword search only. | `def test_foo(tmp_vector_memory): tmp_vector_memory.add_feedback(...)` |
| `mock_llm_gateway` | function | Patches `LLMGateway.generate()` to return fixed JSON: `{"severity": "HIGH", "root_cause_hypothesis": "test hypothesis", "recommended_action": "test action"}` | `def test_foo(mock_llm_gateway): ...` |
| `mock_gitlab_responses` | function | Dict of realistic GitLab API response dicts for MR, diff, issue, pipeline, jobs, notes. | `def test_foo(mock_gitlab_responses): mr_data = mock_gitlab_responses["mr"]` |
| `api_client` | function | `fastapi.testclient.TestClient` wrapping the SAGE[ai] FastAPI `app`. | `def test_foo(api_client): resp = api_client.get("/health")` |
| `mock_serial_port` | function | Patches `serial.Serial` and `serial.tools.list_ports.comports`. Returns dict with mock objects. | `def test_foo(mock_serial_port): ...` |
| `mock_jlink` | function | Patches `pylink.JLink`. Returns dict with `JLink` class mock and `instance` mock. | `def test_foo(mock_jlink): mock_jlink["instance"].memory_read.return_value = [...]` |
| `mock_metabase_session` | function | Patches `requests.post` (auth) and `requests.get` (data) for Metabase API. | `def test_foo(mock_metabase_session): ...` |
| `mock_spira_requests` | function | Patches `requests.get` and `requests.post` for Spira REST API calls. | `def test_foo(mock_spira_requests): ...` |
| `mock_teams_requests` | function | Patches `msal.ConfidentialClientApplication`, `requests.post` (webhook), and `requests.get` (Graph API). | `def test_foo(mock_teams_requests): ...` |
| `sample_log_entries` | function | List of 5 realistic embedded device log strings for use as test inputs. | `def test_foo(sample_log_entries): analyze(sample_log_entries[0])` |

---

## 5. Unit Test Cases

### LLM Gateway (`tests/test_llm_gateway.py`)

| Test ID | Test Name | What It Verifies | Pass Criteria |
|---|---|---|---|
| UT-LLM-001 | `test_singleton_pattern` | LLMGateway() returns same instance on multiple calls | `LLMGateway() is LLMGateway()` |
| UT-LLM-002 | `test_gemini_provider_selected_by_default` | Default config selects Gemini provider | provider_name contains "Gemini" |
| UT-LLM-003 | `test_local_provider_selected_when_configured` | Config `provider: local` instantiates LocalLlamaProvider | `isinstance(gw.provider, LocalLlamaProvider)` |
| UT-LLM-004 | `test_generate_returns_string` | Subprocess stdout returned as generate() result | result == "OK" |
| UT-LLM-005 | `test_generate_handles_timeout` | TimeoutExpired yields error string mentioning "timed out" | "timed out" in result.lower() |
| UT-LLM-006 | `test_generate_handles_missing_gemini_cli` | FileNotFoundError yields graceful error string | "error" or "not found" in result.lower() |
| UT-LLM-007 | `test_thread_lock_serializes_calls` | 3 concurrent threads all complete without exception | All 3 results are non-empty strings, no errors |
| UT-LLM-008 | `test_gemini_cli_filters_hook_lines` | "Loaded cached registry" and "Hook registry:" lines filtered from output | result == "Actual response" |
| UT-LLM-009 | `test_get_provider_name_returns_string` | get_provider_name() returns non-empty string | isinstance(name, str) and len(name) > 0 |

### Audit Logger (`tests/test_audit_logger.py`)

| Test ID | Test Name | What It Verifies | Pass Criteria |
|---|---|---|---|
| UT-AUD-001 | `test_db_initialized_with_correct_schema` | compliance_audit_log table has all required columns | All 7 required columns present |
| UT-AUD-002 | `test_log_event_returns_uuid` | log_event() returns valid UUID v4 string | Matches UUID4 regex pattern |
| UT-AUD-003 | `test_log_event_persists_to_db` | Logged event appears in SQLite with correct fields | Row with actor, action_type matches inputs |
| UT-AUD-004 | `test_log_event_all_fields_stored` | All 7 fields stored correctly including metadata | All fields match expected values |
| UT-AUD-005 | `test_multiple_events_stored` | 10 log_event() calls produce 10 rows | COUNT(*) == 10 |
| UT-AUD-006 | `test_metadata_stored_as_json` | metadata dict stored as valid JSON string | json.loads(stored) matches input dict |
| UT-AUD-007 | `test_log_event_with_none_metadata` | metadata=None accepted without exception | Row stored, no exception raised |
| UT-AUD-008 | `test_timestamp_format` | Stored timestamp parseable as ISO datetime | datetime.fromisoformat() succeeds |
| UT-AUD-009 | `test_audit_log_is_append_only` | Two events both retained after logging | Both IDs present in database |
| UT-AUD-010 | `test_trace_id_is_unique_per_event` | 5 log_event() calls yield 5 distinct IDs | len(set(ids)) == 5 |

### Vector Store (`tests/test_vector_store.py`)

| Test ID | Test Name | What It Verifies | Pass Criteria |
|---|---|---|---|
| UT-VEC-001 | `test_search_returns_empty_on_empty_memory` | Empty VectorMemory returns [] on search | result == [] |
| UT-VEC-002 | `test_add_feedback_stores_to_fallback` | add_feedback() makes doc retrievable | "test doc" in search("test") |
| UT-VEC-003 | `test_search_k_limits_results` | k=2 limits results to max 2 | len(results) <= 2 |
| UT-VEC-004 | `test_keyword_matching_in_fallback` | Keyword present in stored doc is found | search("timeout") returns match |
| UT-VEC-005 | `test_add_multiple_feedbacks` | 3 docs all retrievable individually | Each findable by unique keyword |
| UT-VEC-006 | `test_search_with_no_matching_keywords` | Non-matching query returns [] | result == [] |
| UT-VEC-007 | `test_metadata_accepted_without_error` | add_feedback with metadata= does not raise | No exception raised |
| UT-VEC-008 | `test_fallback_used_when_chromadb_unavailable` | ChromaDB absent → fallback initializes, is usable | vector_store is None; search works |

### Analyst Agent (`tests/test_analyst_agent.py`)

| Test ID | Test Name | What It Verifies | Pass Criteria |
|---|---|---|---|
| UT-ANA-001 | `test_analyze_log_returns_required_fields` | Result has severity, root_cause_hypothesis, recommended_action, trace_id | All 4 keys present |
| UT-ANA-002 | `test_analyze_log_creates_audit_record` | ANALYSIS_PROPOSAL record created in audit DB | COUNT(ANALYSIS_PROPOSAL) >= 1 |
| UT-ANA-003 | `test_analyze_log_trace_id_is_uuid` | trace_id in result is UUID v4 | Matches UUID4 regex |
| UT-ANA-004 | `test_analyze_log_handles_json_parse_failure` | Non-JSON LLM output still returns valid result dict | All 4 keys present with fallback values |
| UT-ANA-005 | `test_analyze_log_uses_rag_context` | RAG context included in LLM prompt | "PAST CONTEXT" in captured prompt |
| UT-ANA-006 | `test_learn_from_feedback_adds_to_memory` | learn_from_feedback() calls vector_memory.add_feedback() | add_feedback called with learning text |
| UT-ANA-007 | `test_learn_from_feedback_creates_audit_record` | FEEDBACK_LEARNING record created with actor=Human_Engineer | Record exists with correct actor |
| UT-ANA-008 | `test_analyze_log_with_empty_string` | analyze_log("") does not raise exception | Returns dict without exception |
| UT-ANA-009 | `test_analyze_log_with_long_entry` | 10000-char input handled without exception | Returns dict without exception |
| UT-ANA-010 | `test_severity_values` | HIGH/MEDIUM/LOW/CRITICAL pass through unchanged | result["severity"] == input severity |

### Developer Agent (`tests/test_developer_agent.py`)

| Test ID | Test Name | What It Verifies | Pass Criteria |
|---|---|---|---|
| UT-DEV-001 | `test_init_reads_env_vars` | GITLAB_URL and GITLAB_TOKEN read from environment | agent.gitlab_url/token match env vars |
| UT-DEV-002 | `test_init_warns_when_no_gitlab_url` | Missing GITLAB_URL triggers warning log | Warning logged or URL is empty |
| UT-DEV-003 | `test_review_mr_returns_required_fields` | review_merge_request() returns 7 required fields | summary, issues, suggestions, approved, trace_id, mr_iid, mr_title present |
| UT-DEV-004 | `test_review_mr_creates_audit_record` | MR_REVIEW record in audit DB | COUNT(MR_REVIEW) >= 1 |
| UT-DEV-005 | `test_review_mr_handles_gitlab_error` | ConnectionError returns dict with "error" key | "error" in result |
| UT-DEV-006 | `test_create_mr_from_issue_returns_mr_url` | create_mr_from_issue() returns mr_url, mr_iid, trace_id | All 3 keys present |
| UT-DEV-007 | `test_create_mr_auto_generates_branch_name` | source_branch=None generates `sage-ai/{iid}-...` pattern | branch starts with "sage-ai/" and contains iid |
| UT-DEV-008 | `test_create_mr_creates_audit_record` | MR_CREATED record in audit DB | COUNT(MR_CREATED) >= 1 |
| UT-DEV-009 | `test_create_mr_logs_failure_to_audit` | GitLab 403 → MR_CREATE_FAILED in audit DB | COUNT(MR_CREATE_FAILED) >= 1 |
| UT-DEV-010 | `test_list_open_mrs_returns_list` | list_open_mrs() returns merge_requests list with count=2 | count == 2 and isinstance(list) |
| UT-DEV-011 | `test_get_pipeline_status_no_pipeline` | MR with no pipeline → status="no_pipeline" | result["status"] == "no_pipeline" |
| UT-DEV-012 | `test_get_pipeline_status_with_pipeline` | MR with pipeline → stages dict populated | "stages" in result and isinstance(dict) |
| UT-DEV-013 | `test_propose_code_patch_returns_diff` | propose_code_patch() returns patch, explanation, confidence | All 3 keys present |
| UT-DEV-014 | `test_propose_code_patch_creates_audit_record` | CODE_PATCH_PROPOSAL record in audit DB | COUNT(CODE_PATCH_PROPOSAL) >= 1 |
| UT-DEV-015 | `test_add_mr_comment_posts_to_gitlab` | add_mr_comment() returns note_id + audit record | note_id in result, MR_COMMENT_ADDED in audit |
| UT-DEV-016 | `test_add_mr_comment_handles_error` | Network exception → dict with "error" key | "error" in result |

### Monitor Agent (`tests/test_monitor_agent.py`)

| Test ID | Test Name | What It Verifies | Pass Criteria |
|---|---|---|---|
| UT-MON-001 | `test_monitor_initializes` | MonitorAgent() instantiates without exception | No exception raised |
| UT-MON-002 | `test_register_callback_stores_handler` | Callback stored in _callbacks dict | callback_fn in agent._callbacks["teams_error"] |
| UT-MON-003 | `test_start_creates_daemon_threads` | start() with config creates alive daemon threads | At least 1 alive thread, all daemon=True |
| UT-MON-004 | `test_stop_terminates_threads` | stop() after start() terminates all threads | No alive threads after stop + wait |
| UT-MON-005 | `test_on_event_calls_registered_callback` | _on_event() dispatches to registered callback | callback_fn called with correct payload |
| UT-MON-006 | `test_on_event_creates_audit_record` | _on_event() creates EVENT_TEAMS_ERROR audit record | COUNT(EVENT_TEAMS_ERROR) >= 1 |
| UT-MON-007 | `test_get_status_returns_dict` | get_status() returns dict with "running" key | isinstance(dict) and "running" in result |
| UT-MON-008 | `test_poll_metabase_handles_no_errors` | Empty error list from Metabase → no callback fired | callback not called |
| UT-MON-009 | `test_poll_teams_handles_no_messages` | Empty messages from Teams → no callback fired | callback not called |

### Queue Manager (`tests/test_queue_manager.py`)

| Test ID | Test Name | What It Verifies | Pass Criteria |
|---|---|---|---|
| UT-QUE-001 | `test_submit_returns_task_id` | submit() returns non-empty string | len(task_id) > 0 |
| UT-QUE-002 | `test_task_id_is_unique` | 5 submissions produce 5 distinct IDs | len(set(ids)) == 5 |
| UT-QUE-003 | `test_get_pending_count` | 3 submissions → get_pending_count() == 3 | count == 3 |
| UT-QUE-004 | `test_get_next_returns_task` | get_next() returns Task with correct task_type | task.task_type == "REVIEW_MR" |
| UT-QUE-005 | `test_mark_done_removes_from_pending` | After mark_done(), pending count decreases | count == 1 (was 2) |
| UT-QUE-006 | `test_get_status_pending` | Freshly submitted task → status == "pending" | status["status"] == "pending" |
| UT-QUE-007 | `test_get_status_done` | After mark_done() → status == "completed" | status["status"] == COMPLETED |
| UT-QUE-008 | `test_queue_fifo_order` | Equal-priority tasks dequeued in submission order | A→B→C dequeue order |
| UT-QUE-009 | `test_worker_dispatches_to_analyst` | ANALYZE_LOG task routes to analyst_agent.analyze_log() | analyze_log() called |
| UT-QUE-010 | `test_worker_handles_exception` | Dispatch exception → task marked FAILED, worker survives | status == FAILED |

### API Endpoints (`tests/test_api.py`)

| Test ID | Test Name | Endpoint | What It Verifies | Pass Criteria |
|---|---|---|---|---|
| UT-API-001 | `test_health_returns_200` | GET /health | Returns HTTP 200 with status ok | status_code == 200, body["status"] == "ok" |
| UT-API-002 | `test_health_contains_provider_info` | GET /health | llm_provider key in response | "llm_provider" in response |
| UT-API-003 | `test_health_shows_configured_integrations` | GET /health | environment flags match env vars | Boolean flags correct |
| UT-API-004 | `test_analyze_returns_proposal` | POST /analyze | Valid request → 200 with trace_id | status == 200, "trace_id" in body |
| UT-API-005 | `test_analyze_rejects_empty_log` | POST /analyze | Empty log_entry → 400 | status == 400 |
| UT-API-006 | `test_analyze_stores_pending_proposal` | POST /analyze | Returned trace_id is approvable | Subsequent POST /approve returns 200 |
| UT-API-007 | `test_approve_valid_trace_id` | POST /approve/{trace_id} | Valid trace_id → 200 with "approved" | status == 200, body["status"] == "approved" |
| UT-API-008 | `test_approve_invalid_trace_id` | POST /approve/{trace_id} | Unknown trace_id → 404 | status == 404 |
| UT-API-009 | `test_approve_creates_audit_record` | POST /approve/{trace_id} | APPROVAL record in audit DB | COUNT(APPROVAL) >= 1 |
| UT-API-010 | `test_approve_removes_from_pending` | POST /approve/{trace_id} | Second approval → 404 | status == 404 |
| UT-API-011 | `test_reject_valid_trace_id` | POST /reject/{trace_id} | Valid trace_id → 200 with "rejected" | status == 200, body["status"] == "rejected" |
| UT-API-012 | `test_reject_invalid_trace_id` | POST /reject/{trace_id} | Unknown trace_id → 404 | status == 404 |
| UT-API-013 | `test_reject_triggers_learning` | POST /reject/{trace_id} | learn_from_feedback() called with feedback | Called with feedback text |
| UT-API-014 | `test_audit_returns_entries` | GET /audit | Returns entries list | "entries" in body, len >= 1 |
| UT-API-015 | `test_audit_pagination` | GET /audit | limit/offset params work | Different records at different offsets |
| UT-API-016 | `test_audit_max_limit_500` | GET /audit | limit=9999 capped at 500 | body["limit"] == 500 |
| UT-API-017 | `test_mr_create_valid_request` | POST /mr/create | Valid body → 200 | status == 200 |
| UT-API-018 | `test_mr_create_missing_fields` | POST /mr/create | Missing project_id → 422 | status == 422 |
| UT-API-019 | `test_mr_create_propagates_error` | POST /mr/create | Agent error → 500 | status == 500 |
| UT-API-020 | `test_mr_review_valid_request` | POST /mr/review | Valid body → 200 | status == 200 |
| UT-API-021 | `test_mr_review_returns_approved_flag` | POST /mr/review | approved field in response | "approved" in body |
| UT-API-022 | `test_monitor_status_returns_dict` | GET /monitor/status | Returns dict with "running" | isinstance(dict) and "running" in body |
| UT-API-023 | `test_teams_webhook_accepts_json` | POST /webhook/teams | Valid JSON → 200 | status == 200 |
| UT-API-024 | `test_teams_webhook_creates_audit_record` | POST /webhook/teams | WEBHOOK_RECEIVED in audit DB | COUNT(WEBHOOK_RECEIVED) >= 1 |
| UT-API-025 | `test_teams_webhook_rejects_invalid_json` | POST /webhook/teams | Malformed body → 400/422 | status in (400, 422) |

---

## 6. Integration Test Cases

All integration tests auto-skip when the required environment variables are not set.

| Test ID | Component | Preconditions | What It Tests | Expected Result |
|---|---|---|---|---|
| IT-GL-001 | GitLab | GITLAB_URL, GITLAB_TOKEN | API reachability via GET /projects | 200 OK, list response |
| IT-GL-002 | GitLab | GITLAB_URL, GITLAB_TOKEN, GITLAB_PROJECT_ID | list_open_mrs() on real project | Valid MR list structure |
| IT-GL-003 | GitLab | All above + GITLAB_TEST_MR_IID | get_pipeline_status() on real MR | Valid status string |
| IT-GL-004 | GitLab | All above + GITLAB_TEST_MR_IID | review_merge_request() on real MR | All 7 fields present |
| IT-TM-001 | Teams | TEAMS_TENANT_ID, TEAMS_CLIENT_ID, TEAMS_CLIENT_SECRET | MSAL token acquisition | token_obtained == True |
| IT-TM-002 | Teams | All above + TEAMS_TEAM_ID | list_team_channels() | Valid channels list |
| IT-TM-003 | Teams | All above + TEAMS_CHANNEL_ID | get_recent_messages() | Valid messages list |
| IT-TM-004 | Teams | All above + TEAMS_INCOMING_WEBHOOK_URL | send_notification() webhook POST | status == "sent" |
| IT-MB-001 | Metabase | METABASE_URL, METABASE_USERNAME, METABASE_PASSWORD | Session token acquisition | token_obtained == True |
| IT-MB-002 | Metabase | All above | list_dashboards() | Valid dashboards list |
| IT-MB-003 | Metabase | All above + METABASE_ERROR_QUESTION_ID | get_question_results() | row_count >= 0, rows list |
| IT-MB-004 | Metabase | All above + METABASE_ERROR_QUESTION_ID | get_new_errors() | has_new_errors bool, count >= 0 |
| IT-SP-001 | Spira | SPIRA_URL, SPIRA_USERNAME, SPIRA_API_KEY, SPIRA_PROJECT_ID | get_project_info() | project_id matches input |
| IT-SP-002 | Spira | All above | list_incidents() | Valid incidents list |
| IT-SP-003 | Spira | All above | list_requirements() | Valid requirements list |
| IT-SP-004 | Spira | All above | list_releases() | Valid releases list |

---

## 7. MCP Server Test Cases

### Serial Port MCP (`tests/mcp/test_serial_mcp.py`)

| Test ID | Test Name | What It Tests | Pass Criteria |
|---|---|---|---|
| MCP-SER-001 | `test_list_serial_ports_returns_ports` | 2 mocked ports → count=2 with correct keys | count == 2, device/description/hwid present |
| MCP-SER-002 | `test_list_serial_ports_no_serial_installed` | SERIAL_AVAILABLE=False → error dict | "error" in result |
| MCP-SER-003 | `test_list_serial_ports_empty` | comports() returns [] → count=0 | count == 0, ports == [] |
| MCP-SER-004 | `test_send_command_sends_and_reads` | Command sent, response read | "response" in result, no error |
| MCP-SER-005 | `test_send_command_serial_exception` | SerialException → error dict | "error" in result |
| MCP-SER-006 | `test_send_command_includes_port_in_result` | Port name echoed in result | result["port"] == input port |
| MCP-SER-007 | `test_read_serial_output_captures_output` | Serial data captured in output | "output" in result |
| MCP-SER-008 | `test_read_serial_output_returns_lines` | "line1\nline2\nline3" → 3-item lines list | len(lines) == 3 |
| MCP-SER-009 | `test_open_persistent_connection_returns_id` | Open returns 8-char connection_id | len(conn_id) == 8 |
| MCP-SER-010 | `test_open_persistent_connection_stores_connection` | ID stored in _persistent_connections | conn_id in _persistent_connections |
| MCP-SER-011 | `test_close_connection_removes_from_store` | Close removes from _persistent_connections | conn_id not in _persistent_connections |
| MCP-SER-012 | `test_close_connection_invalid_id` | Unknown ID → error dict with known_ids | "error" in result, "known_ids" in result |
| MCP-SER-013 | `test_multiple_persistent_connections` | 2 connections have unique IDs | id1 != id2, len(_persistent_connections) == 2 |

### J-Link MCP (`tests/mcp/test_jlink_mcp.py`)

| Test ID | Test Name | What It Tests | Pass Criteria |
|---|---|---|---|
| MCP-JLK-001 | `test_connect_jlink_opens_connection` | connect returns status="connected" | status == "connected", no error |
| MCP-JLK-002 | `test_connect_jlink_device_name_stored` | _jlink_instance set after connect | _jlink_instance is not None |
| MCP-JLK-003 | `test_disconnect_clears_state` | disconnect sets _jlink_instance = None | _jlink_instance is None |
| MCP-JLK-004 | `test_disconnect_when_not_connected` | disconnect without connect → graceful dict | isinstance(result, dict) |
| MCP-JLK-005 | `test_read_memory_returns_hex` | memory_read → hex string in result | "hex_data" in result, all hex chars |
| MCP-JLK-006 | `test_read_memory_correct_length` | 4 bytes → 8 hex chars | len(hex_str) == 8 |
| MCP-JLK-007 | `test_write_memory_calls_jlink` | write_memory calls jlink.memory_write | Called with correct address |
| MCP-JLK-008 | `test_read_registers_returns_dict` | read_registers returns {"registers": {name: value}} | All register names present |
| MCP-JLK-009 | `test_flash_firmware_validates_file_exists` | Non-existent file → error dict | "error" mentions file not found |
| MCP-JLK-010 | `test_reset_target_with_halt` | reset_target(halt=True) passes halt=True | jlink.reset called with halt=True |
| MCP-JLK-011 | `test_get_jlink_info_returns_hardware_info` | get_jlink_info() returns serial_number, firmware_version | Both keys present, no error |
| MCP-JLK-012 | `test_read_rtt_returns_string` | read_rtt_output() returns "output" as string | isinstance(output, str) |
| MCP-JLK-013 | `test_connect_when_already_connected` | Second connect does not raise exception | isinstance(result2, dict) |

### Metabase MCP (`tests/mcp/test_metabase_mcp.py`)

| Test ID | Test Name | What It Tests | Pass Criteria |
|---|---|---|---|
| MCP-MB-001 | `test_get_session_token_posts_to_api` | POST /api/session called, token returned | token == "token123" |
| MCP-MB-002 | `test_get_session_token_handles_auth_failure` | 401 response → None returned | token is None |
| MCP-MB-003 | `test_get_question_results_calls_correct_endpoint` | /api/card/{id}/query/json URL used | URL contains correct path |
| MCP-MB-004 | `test_get_question_results_returns_data` | Rows returned from response | row_count == 2, "rows" in result |
| MCP-MB-005 | `test_list_dashboards_returns_list` | /api/dashboard → dashboards list | count == 2, "dashboards" in result |
| MCP-MB-006 | `test_get_dashboard_returns_cards` | /api/dashboard/{id} → cards list | card_count == 2 |
| MCP-MB-007 | `test_search_errors_uses_configured_question_id` | METABASE_ERROR_QUESTION_ID env var used | URL contains correct question ID |
| MCP-MB-008 | `test_search_errors_filters_by_time` | Old rows excluded from since_hours filter | Only recent row returned |
| MCP-MB-009 | `test_get_new_errors_returns_recent_only` | 1 recent + 2 old → count=1 | count == 1, has_new_errors == True |
| MCP-MB-010 | `test_missing_env_vars_return_error` | METABASE_URL empty → error dict | "error" in result |
| MCP-MB-011 | `test_handles_metabase_connection_error` | ConnectionError → graceful error dict | "error" in result |

### Spira MCP (`tests/mcp/test_spira_mcp.py`)

| Test ID | Test Name | What It Tests | Pass Criteria |
|---|---|---|---|
| MCP-SP-001 | `test_list_incidents_calls_correct_endpoint` | /projects/{id}/incidents URL used | URL contains correct path |
| MCP-SP-002 | `test_list_incidents_returns_list` | 3 incidents → count=3 | count == 3, "incidents" is list |
| MCP-SP-003 | `test_list_incidents_filters_by_status` | status_id=2 → params include status_id | params["status_id"] == 2 |
| MCP-SP-004 | `test_get_incident_returns_incident` | GET incident → incident_id == 101 | result["incident_id"] == 101 |
| MCP-SP-005 | `test_get_incident_not_found` | 404 → error dict | "error" in result |
| MCP-SP-006 | `test_create_incident_posts_to_api` | POST body contains Name and Description | Both keys in POST body |
| MCP-SP-007 | `test_create_incident_returns_id` | Created incident has IncidentId → incident_id=999 | result["incident_id"] == 999 |
| MCP-SP-008 | `test_update_incident_sends_put` | GET then PUT sequence executed | No error in result |
| MCP-SP-009 | `test_list_requirements_returns_list` | Requirements list returned | "requirements" in result |
| MCP-SP-010 | `test_get_test_runs_returns_runs` | Test runs list returned | "test_runs" in result |
| MCP-SP-011 | `test_list_releases_returns_releases` | Releases list returned | "releases" in result |
| MCP-SP-012 | `test_get_project_info_returns_project` | Project info with ProjectId returned | result["project_id"] == 1 |
| MCP-SP-013 | `test_auth_params_included_in_every_request` | username and api-key in all requests | Both params present with correct values |

### Teams MCP (`tests/mcp/test_teams_mcp.py`)

| Test ID | Test Name | What It Tests | Pass Criteria |
|---|---|---|---|
| MCP-TM-001 | `test_get_access_token_uses_msal` | MSAL acquire_token_for_client called | Called; token == "mock-graph-token" |
| MCP-TM-002 | `test_get_access_token_handles_failure` | MSAL returns no token → None | token is None |
| MCP-TM-003 | `test_list_team_channels_calls_graph_api` | /teams/{id}/channels URL + Bearer auth | URL and Authorization header correct |
| MCP-TM-004 | `test_get_recent_messages_returns_messages` | 3 messages returned | count == 3 |
| MCP-TM-005 | `test_get_recent_messages_top_param` | top=5 → $top=5 in params | params["$top"] == 5 |
| MCP-TM-006 | `test_get_messages_since_filters_by_time` | Old message excluded by time filter | Only recent message returned |
| MCP-TM-007 | `test_search_error_messages_filters_keywords` | Only messages with "error" returned | 1 error message, "INFO boot" excluded |
| MCP-TM-008 | `test_send_notification_posts_to_webhook` | POST to webhook URL | POST called to correct URL, status="sent" |
| MCP-TM-009 | `test_send_notification_includes_title` | Title present in POST payload | Title string found in payload |
| MCP-TM-010 | `test_send_alert_uses_configured_webhook` | TEAMS_INCOMING_WEBHOOK_URL used | POST to configured URL |
| MCP-TM-011 | `test_send_alert_color_by_severity` | error vs info → different calls | 2 POST calls made |
| MCP-TM-012 | `test_missing_tenant_id_returns_error` | TEAMS_TENANT_ID empty → None | token is None |

---

## 8. End-to-End Test Cases

### Analyze/Approve Flow (`tests/e2e/test_analyze_approve_flow.py`)

| Test ID | Scenario | Preconditions | Steps | Expected Audit Trail |
|---|---|---|---|---|
| E2E-001 | Full analyze-then-approve | Mocked LLM, real AuditLogger | POST /analyze → POST /approve/{trace_id} | ANALYSIS_PROPOSAL + APPROVAL records |
| E2E-002 | Analyze-then-reject with learning | Mocked LLM, real AuditLogger | POST /analyze → POST /reject/{trace_id} with feedback | ANALYSIS_PROPOSAL + FEEDBACK_LEARNING records |
| E2E-003 | Proposal removed after approve | Prior E2E-001 state cleared | POST /analyze → POST /approve → POST /approve (again) | Second approve returns 404 |
| E2E-004 | Proposal removed after reject | Prior state cleared | POST /analyze → POST /reject → POST /reject (again) | Second reject returns 404 |
| E2E-005 | 5 concurrent analyses | Mocked LLM, thread-safe TestClient | 5 threads POST /analyze simultaneously | 5 unique trace_ids, 5 ANALYSIS_PROPOSAL records |

### MR Workflow (`tests/e2e/test_mr_workflow.py`)

| Test ID | Scenario | Preconditions | Steps | Expected Outcome |
|---|---|---|---|---|
| E2E-006 | Create MR from issue | Mocked GitLab HTTP + LLM | POST /mr/create → verify response | 200 OK, trace_id returned, MR_CREATED in audit |
| E2E-007 | Review MR and post comment | Mocked GitLab HTTP + LLM | POST /mr/review → add_mr_comment() | MR_REVIEW + MR_COMMENT_ADDED in audit |
| E2E-008 | MR create failure logged | Mocked GitLab 403 | POST /mr/create → 403 from GitLab | 500 returned, MR_CREATE_FAILED in audit |

### Monitor to Notification Flow (`tests/e2e/test_monitor_to_notification_flow.py`)

| Test ID | Scenario | Preconditions | Steps | Expected Outcome |
|---|---|---|---|---|
| E2E-009 | Teams error triggers analyst | Registered callback | _on_event("teams_error", payload) | analyst.analyze_log() called with error content |
| E2E-010 | Metabase error triggers notification | Registered callback | _on_event("metabase_error", payload) | Teams alert function called |
| E2E-011 | GitLab issue triggers MR creation | Registered callback | _on_event("gitlab_issue", payload) | developer.create_mr_from_issue() called with issue_iid |

---

## 9. Compliance Validation Tests (IQ/OQ/PQ)

### Formal Test Protocol

**Standard:** ISO 13485:2016 Section 7.5.6 / FDA 21 CFR Part 11
**File:** `tests/validation/test_iq_oq_pq.py`
**Execution command for evidence generation:**

```bash
pytest tests/validation/test_iq_oq_pq.py -m compliance -v --tb=long 2>&1 | tee docs/validation_report.txt
```

### Installation Qualification (IQ)

| Test ID | Requirement Reference | Test Description | Acceptance Criteria | Test Method |
|---|---|---|---|---|
| IQ-001 | SRS-SYS-001: Python Version | Python 3.10+ installed | sys.version_info >= (3, 10) | Automated assertion |
| IQ-002 | SRS-SYS-002: Dependencies | All required packages importable | No ImportError for pyyaml, fastapi, requests, pydantic | Import attempt + assertion |
| IQ-003 | SRS-SYS-003: Configuration | config/config.yaml valid and present | File exists; yaml.safe_load() succeeds | File check + parse |
| IQ-004 | SRS-SYS-004: Data Directory | data/ directory writable | Write + read test file succeeds | File I/O test |
| IQ-005 | SRS-AUD-001: Audit DB | AuditLogger initializes with correct schema | DB created; 7 required columns present | Schema inspection via PRAGMA |
| IQ-006 | SRS-LLM-001: LLM Gateway | LLMGateway instantiates without error | No exception; get_provider_name() returns string | Instantiation + name check |

### Operational Qualification (OQ)

| Test ID | Requirement Reference | Test Description | Acceptance Criteria | Test Method |
|---|---|---|---|---|
| OQ-001 | SRS-AUD-002: Every Analysis Logged | Each analysis produces audit record | COUNT(ANALYSIS_PROPOSAL) == 3 after 3 analyses | POST /analyze × 3, DB count check |
| OQ-002 | SRS-TRC-001: UUID Trace IDs | Each action gets UUID v4 trace_id | trace_id matches UUID4 regex | Regex validation |
| OQ-003 | SRS-APP-001: Approval Logged | Approval creates audit record with correct actor | APPROVAL record with actor="Human_Engineer" | DB query after POST /approve |
| OQ-004 | SRS-REJ-001: Rejection Logged | Rejection triggers FEEDBACK_LEARNING audit record | FEEDBACK_LEARNING record exists | DB query after POST /reject |
| OQ-005 | SRS-RAG-001: Feedback Retrievable | Added feedback findable by search | Search returns added feedback in top-3 | add_feedback + search validation |
| OQ-006 | SRS-AUD-003: Read Immutability | Read operations do not modify audit log | COUNT before == COUNT after 10 reads | Count before/after 10 GET /audit |
| OQ-007 | SRS-LLM-002: Thread Safety | Concurrent LLM calls all succeed | 5 concurrent calls all return non-empty strings | Threading test, no errors |
| OQ-008 | SRS-APP-002: No Auto-Execution | Proposals not auto-executed | No EXECUTION record after analyze (no approve) | DB query for absent EXECUTION records |
| OQ-009 | SRS-TRC-002: API Returns Trace ID | POST /analyze always returns trace_id | "trace_id" in response body, non-empty | Response body check |
| OQ-010 | SRS-AUD-004: UTC Timestamps | Audit timestamps are UTC ISO format | datetime.fromisoformat() succeeds; diff from now < 60s | Timestamp parse + freshness check |

### Performance Qualification (PQ)

| Test ID | Requirement Reference | Test Description | Acceptance Criteria | Test Method |
|---|---|---|---|---|
| PQ-001 | SRS-PERF-001: 50 Sequential Analyses | System handles 50 consecutive analyses | COUNT(ANALYSIS_PROPOSAL) == 50 | POST /analyze × 50, DB count |
| PQ-002 | SRS-RAG-002: 90% Retrieval Rate | RAG retrieves 90%+ of stored feedback | hits/queries >= 0.90 | Store 10, search 10, count hits |
| PQ-003 | SRS-PERF-002: 10 Approve Cycles | 10 full analyze+approve cycles succeed | 10 proposals + 10 approvals in DB | Loop 10× analyze+approve, DB count |
| PQ-004 | SRS-PERF-003: Query Performance | GET /audit < 2s with 1000 records | elapsed < 2.0 seconds | Insert 1000, time the query |
| PQ-005 | SRS-PERF-004: Concurrent API Requests | 10 concurrent /analyze requests succeed | All 200 OK; all 10 trace_ids unique | 10 threads, collect results |

---

## 10. Test Data

### Sample Log Entries (`sample_log_entries` fixture)

| Index | Log Entry | Simulates |
|---|---|---|
| 0 | `ERROR [uart_driver.c:142] UART1 RX buffer overflow: received 512 bytes, buffer capacity 256` | Serial buffer overflow |
| 1 | `CRITICAL [watchdog.c:88] Watchdog timeout expired — system halted. Last task: SENSOR_POLL` | Watchdog reset |
| 2 | `ERROR [flash_controller.c:310] Flash write failed at address 0x08040000: HAL_ERROR status 0x02` | Flash write failure |
| 3 | `WARNING [i2c_bus.c:205] I2C1 bus stuck LOW — attempting recovery sequence (attempt 3/3)` | I2C bus lockup |
| 4 | `ERROR [rtos_hooks.c:57] Stack overflow detected in task 'CommsHandler' (stack high watermark: 48 bytes)` | RTOS stack overflow |

### Fixed LLM Response (Mock)

Used across unit and E2E tests to eliminate LLM variability:

```json
{
  "severity": "HIGH",
  "root_cause_hypothesis": "test hypothesis",
  "recommended_action": "test action"
}
```

### Mock GitLab Responses (`mock_gitlab_responses` fixture)

| Key | Content |
|---|---|
| `mr` | Full MR object with pipeline (iid=7, project=123) |
| `mr_diffs` | Single file diff (uart_driver.c, +512 bytes) |
| `issue` | Issue object (iid=45, "UART RX buffer too small") |
| `project` | Project object (id=123, default_branch=main) |
| `mr_created` | New MR response (iid=8) |
| `pipeline` | Pipeline object (id=555, status=passed) |
| `jobs` | 2 jobs (build: success, test: success) |
| `note` | MR note (id=9001) |

---

## 11. Continuous Integration

### GitHub Actions Configuration

Create `.github/workflows/test.yml`:

```yaml
name: SAGE[ai] Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov httpx

      - name: Run unit tests with coverage
        run: |
          pytest -m unit --cov=src --cov=mcp_servers \
                 --cov-report=xml --cov-report=term-missing \
                 -v --tb=short

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          fail_ci_if_error: false

  e2e-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt pytest httpx
      - run: pytest -m e2e -v --tb=short

  compliance-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt pytest httpx
      - name: Run compliance validation tests
        run: |
          pytest -m compliance -v --tb=long 2>&1 | tee validation_report.txt
      - name: Upload validation report
        uses: actions/upload-artifact@v4
        with:
          name: validation-report
          path: validation_report.txt
          retention-days: 90

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    env:
      GITLAB_URL: ${{ secrets.GITLAB_URL }}
      GITLAB_TOKEN: ${{ secrets.GITLAB_TOKEN }}
      GITLAB_PROJECT_ID: ${{ secrets.GITLAB_PROJECT_ID }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt pytest httpx
      - run: pytest -m integration -v --tb=short
```

### GitLab CI Configuration

Create `.gitlab-ci.yml`:

```yaml
stages:
  - unit
  - e2e
  - compliance
  - integration

variables:
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"

cache:
  paths:
    - .cache/pip

unit-tests:
  stage: unit
  image: python:3.11
  script:
    - pip install -r requirements.txt pytest pytest-cov httpx
    - pytest -m unit --cov=src --cov=mcp_servers
             --cov-report=term-missing -v --tb=short
  artifacts:
    reports:
      junit: report.xml
    when: always

e2e-tests:
  stage: e2e
  image: python:3.11
  script:
    - pip install -r requirements.txt pytest httpx
    - pytest -m e2e -v --tb=short
  needs: [unit-tests]

compliance-tests:
  stage: compliance
  image: python:3.11
  script:
    - pip install -r requirements.txt pytest httpx
    - pytest -m compliance -v --tb=long 2>&1 | tee validation_report.txt
  artifacts:
    paths:
      - validation_report.txt
    expire_in: 1 year
  needs: [unit-tests]

integration-tests:
  stage: integration
  image: python:3.11
  only:
    - main
  script:
    - pip install -r requirements.txt pytest httpx
    - pytest -m integration -v --tb=short
  needs: [e2e-tests]
```

---

## 12. Interpreting Results

### What a Passing Run Looks Like

```
============================= test session info ==============================
platform win32 -- Python 3.11.9, pytest-8.1.0, ...
rootdir: C:\System-Team-repos\SystemAutonomousAgent
configfile: pytest.ini

collected 80 items

tests/test_llm_gateway.py::test_singleton_pattern PASSED               [  1%]
tests/test_llm_gateway.py::test_gemini_provider_selected_by_default PASSED [  2%]
...
tests/validation/test_iq_oq_pq.py::test_pq_005_concurrent_api_requests PASSED [100%]

========================== 80 passed in 12.34s ==============================
```

### Common Failures and Fixes

| Failure | Likely Cause | Fix |
|---|---|---|
| `ImportError: No module named 'fastmcp'` | Missing dependency | `pip install fastmcp` |
| `ImportError: No module named 'msal'` | MSAL not installed | `pip install msal` |
| `FileNotFoundError: config/config.yaml` | Wrong working directory | Run pytest from project root |
| `IntegrityError` in audit tests | Shared audit DB state | Use `tmp_audit_db` fixture (not global `audit_logger`) |
| `404` from approve in E2E | Singleton `_pending_proposals` not cleared | Ensure `api._pending_proposals.clear()` in fixture teardown |
| `LLMGateway singleton` state leaking | Singleton not reset between tests | Call `_reset_llm_gateway_singleton()` in tests that need fresh instance |
| Hardware tests fail | J-Link or serial device not connected | Run with `-m "not hardware"` or connect device |
| Integration tests skip | Env vars not set | Set required env vars (see Section 3) |
| `TimeoutExpired` in PQ tests | System under heavy load | Increase `timeout` in pytest.ini or reduce concurrency |

### Coverage Report Interpretation

```bash
# Generate HTML coverage report
pytest -m unit --cov=src --cov=mcp_servers --cov-report=html

# Open in browser
start htmlcov/index.html      # Windows
open htmlcov/index.html       # macOS
xdg-open htmlcov/index.html  # Linux
```

Lines marked red in the HTML report are untested. Prioritize covering:
- Error handling branches in agents
- Fallback paths in VectorMemory
- Edge cases in queue_manager

---

## 13. Adding New Tests

### Conventions

1. **File naming:** `test_<component>.py` in the appropriate directory
2. **Class naming:** `Test<Component>` (optional — function-based tests are preferred)
3. **Function naming:** `test_<what_it_does>` — descriptive, lowercase with underscores
4. **Markers:** Always mark tests with at least one of `unit`, `integration`, `e2e`, `hardware`, `compliance`
5. **Fixtures:** Use `tmp_audit_db` (not global `audit_logger`) for isolated audit testing
6. **Mocking:** Mock all external calls in unit tests. Use `patch()` as context managers, not decorators, for clarity
7. **Assertions:** One logical concept per test; use descriptive failure messages

### Template for a New Unit Test

```python
"""
Tests for MyNewComponent (src/my_module.py)
"""
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.unit


def test_my_component_does_something_specific(tmp_audit_db):
    """
    Brief description: what this test verifies and why it matters.
    """
    # Arrange
    with patch("src.core.llm_gateway.LLMGateway.generate", return_value='{"key": "value"}'), \
         patch("src.my_module.audit_logger", tmp_audit_db):
        from src.my_module import MyComponent
        component = MyComponent()

    # Act
    result = component.do_something("input data")

    # Assert
    assert "expected_key" in result, f"Expected 'expected_key' in result: {result}"
    assert result["expected_key"] == "expected_value"
```

### Template for a New Compliance Test

```python
def test_oq_NNN_brief_name(oq_setup):
    """
    OQ-NNN: Short Requirement Title
    Requirement: [SRS reference] — Exact requirement statement from SRS.
    Acceptance Criteria: Measurable pass/fail criterion.
    """
    c = oq_setup["client"]
    db_path = oq_setup["db_path"]

    # Test steps...
    resp = c.post("/analyze", json={"log_entry": "ERROR: test"})

    # Assertions with clear failure messages
    assert resp.status_code == 200, f"OQ-NNN FAIL: Expected 200, got {resp.status_code}"
```

### Adding a New MCP Server Test

1. Create `tests/mcp/test_<server_name>_mcp.py`
2. Import from `mcp_servers.<server_name>_server`
3. Patch module-level variables (e.g., `METABASE_URL`) with `patch.object(srv, "METABASE_URL", "https://test.local")`
4. Reset any module-level state (caches, connection stores) before each test
5. Mark with `@pytest.mark.unit`

### Test ID Assignment

When adding new tests, assign IDs in the next available sequence:
- Unit tests: `UT-<COMPONENT>-<NNN>` (e.g., UT-LLM-010)
- Integration: `IT-<SERVICE>-<NNN>` (e.g., IT-GL-005)
- MCP: `MCP-<SRV>-<NNN>` (e.g., MCP-SER-014)
- E2E: `E2E-<NNN>` (e.g., E2E-012)
- Compliance: `IQ/OQ/PQ-<NNN>` (e.g., OQ-011)

Document new test cases in this TESTING.md in the appropriate table.

---

*This document is part of the SAGE[ai] Quality Management System.*
*Maintained by the System Engineering Team.*
*For questions, contact the QMS document owner.*
