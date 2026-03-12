# Requirements Traceability Matrix (RTM)
## SAGE[ai] — Autonomous Manufacturing Intelligence System

**Document ID:** SAGE-RTM-001
**Version:** 2.0.0
**Status:** Approved
**Date:** 2026-03-11

---

## 1. Purpose

This Requirements Traceability Matrix (RTM) traces every software requirement defined in the SRS (SAGE-SRS-001) to:
1. The design element that implements it
2. The test case(s) that verify it
3. The verification result status

---

## 2. RTM Table

| Req ID | Requirement Summary | Design Element | Test Case(s) | Status |
|---|---|---|---|---|
| **FR-ANAL-001** | Accept log entry via API or CLI | `src/interface/api.py POST /analyze` | UVT-007-02, SVT-001 | Verified |
| **FR-ANAL-002** | Classify severity RED/AMBER/GREEN | `src/agents/analyst.py analyze_log()` | UVT-002-01 | Verified |
| **FR-ANAL-003** | Produce root cause + recommended action | `src/agents/analyst.py analyze_log()` | UVT-002-01 | Verified |
| **FR-ANAL-004** | Assign UUID trace_id to every analysis | `src/agents/analyst.py` → `audit_logger.log_event()` | UVT-002-02 | Verified |
| **FR-ANAL-005** | Audit log before returning result | `src/memory/audit_logger.py log_event()` | UVT-002-03, UVT-005-02 | Verified |
| **FR-ANAL-006** | RAG context retrieval | `src/memory/vector_store.py search()` | UVT-002-06 | Verified |
| **FR-ANAL-007** | No auto-execution (HITL required) | No auto-execute code path exists | UVT-007-05 (negative test) | Verified |
| **FR-HITL-001** | POST /approve/{trace_id} endpoint | `src/interface/api.py approve()` | UVT-007-04 | Verified |
| **FR-HITL-002** | POST /reject/{trace_id} endpoint | `src/interface/api.py reject()` | UVT-007-05 (adapted) | Verified |
| **FR-HITL-003** | Learn from rejection feedback | `src/agents/analyst.py learn_from_feedback()` | UVT-002-05, SVT-002 | Verified |
| **FR-HITL-004** | Audit every approval/rejection | `audit_logger.log_event()` in approve/reject | UVT-005-01, OQ-002 | Verified |
| **FR-HITL-005** | No unapproved execution | Proposal stored pending; no auto-trigger | UVT-007-05 | Verified |
| **FR-MR-001** | Create MR via GitLab API | `src/agents/developer.py create_mr_from_issue()` | UVT-003-05, IVT-001-01 | Verified |
| **FR-MR-002** | LLM drafts MR title/description | `create_mr_from_issue()` LLM call | UVT-003-05 | Verified |
| **FR-MR-003** | ReAct loop for MR review | `src/agents/developer.py _react_loop()` | UVT-003-02, UVT-003-03, OQ-007 | Verified |
| **FR-MR-004** | Review output: summary/issues/suggestions/approved | `review_merge_request()` return value | UVT-003-01 | Verified |
| **FR-MR-005** | List open MRs endpoint | `GET /mr/open` → `list_open_mrs()` | UVT-007-07, IVT-001-03 | Verified |
| **FR-MR-006** | Pipeline status endpoint | `GET /mr/pipeline` → `get_pipeline_status()` | UVT-007-08, IVT-001-04 | Verified |
| **FR-MR-007** | Post AI review as MR comment | `add_mr_comment()` | UVT-003-01 | Planned |
| **FR-MON-001** | Poll Teams for error keywords | `src/agents/monitor.py _poll_teams()` | IVT-003 | Verified |
| **FR-MON-002** | Poll Metabase for error records | `src/agents/monitor.py _poll_metabase()` | IVT-002 | Verified |
| **FR-MON-003** | Poll GitLab for sage-ai issues | `src/agents/monitor.py _poll_gitlab()` | IVT-001 | Verified |
| **FR-MON-004** | Async callback dispatch | `monitor.register_callback()` | Unit tests in test_monitor | Verified |
| **FR-MON-005** | GET /monitor/status endpoint | `src/interface/api.py monitor_status()` | UVT-007-09 | Verified |
| **FR-MON-006** | Independent thread per source | MonitorAgent three daemon threads | Functional test | Verified |
| **FR-AUDIT-001** | Append-only audit log | `src/memory/audit_logger.py` | UVT-005-02, UVT-005-03 | Verified |
| **FR-AUDIT-002** | Correct schema fields | SQLite table `compliance_audit_log` | UVT-005-04, IQ-006 | Verified |
| **FR-AUDIT-003** | No delete/modify of records | No DELETE methods in audit_logger | UVT-005-03 (code review) | Verified |
| **FR-AUDIT-004** | GET /audit with pagination | `src/interface/api.py get_audit()` | UVT-007-06 | Verified |
| **FR-AUDIT-005** | Retention per device class | Documented in CHANGE_CONTROL.md | Policy review | Documented |
| **FR-QUEUE-001** | Single-lane serialized execution | `TaskWorker` single thread | UVT-004-03 | Verified |
| **FR-QUEUE-002** | SQLite persistence + restart restore | `TaskQueue._init_db()`, `_restore_pending_tasks()` | UVT-004-02, UVT-004-06, OQ-005 | Verified |
| **FR-QUEUE-003** | Task status tracking | `TaskStatus` enum in queue_manager | UVT-004-04, UVT-004-05 | Verified |
| **FR-QUEUE-004** | No concurrent AI tasks | `TaskWorker` single-lane design | UVT-004-03, PQ-004 | Verified |
| **FR-PLAN-001** | LLM decomposes task to subtasks | `PlannerAgent.create_plan()` | UVT-006-01 | Verified |
| **FR-PLAN-002** | Only valid task types emitted | `VALID_TASK_TYPES` filter in planner | UVT-006-02 | Verified |
| **FR-PLAN-003** | Planning audited | `audit_logger.log_event()` in plan_and_execute | UVT-006-04 | Verified |
| **FR-WEB-001** | Web UI at localhost:5173 | `web/vite.config.ts` | Manual test | Verified |
| **FR-WEB-002** | 5 pages: Dashboard/Analyst/Developer/Audit/Monitor | `web/src/pages/` + `App.tsx` routes | Manual test | Verified |
| **FR-WEB-003** | Auto-refresh every 30s | TanStack Query `refetchInterval: 30_000` | Manual test | Verified |
| **FR-WEB-004** | Log submission + approve/reject UI | `LogAnalysisForm`, `ApprovalButtons` components | Manual test | Verified |
| **FR-WEB-005** | Paginated audit log with trace detail | `AuditLogTable`, `TraceDetailModal` | Manual test | Verified |
| **FR-WEB-006** | CSV export | `exportCsv()` function in AuditLog page | Manual test | Verified |
| **NFR-PERF-001** | Analysis < 60s | End-to-end timing | PQ-001 | Planned |
| **NFR-PERF-002** | MR review < 120s | End-to-end timing | PQ-001 | Planned |
| **NFR-PERF-003** | Non-LLM API < 2s | Load test | PQ-002 | Planned |
| **NFR-REL-001** | Queue survives restart | SQLite persistence | OQ-005, UVT-004-06 | Verified |
| **NFR-REL-002** | Graceful degradation | Error handling in all agent methods | UVT-003-08 | Verified |
| **NFR-SEC-001** | Credentials in env vars only | Code review of config.yaml | Code review | Verified |
| **NFR-SEC-002** | Pydantic request validation | All request models in api.py | UVT-007-03 | Verified |
| **NFR-SEC-004** | CORS configurable | `CORSMiddleware` in api.py | UVT-007-09 | Verified |
| **NFR-TRACE-001** | Every AI output has trace_id | audit_logger returns UUID | UVT-002-02, UVT-003 | Verified |
| **NFR-TRACE-002** | Approvals reference trace_id | approve/reject store trace_id in audit | UVT-007-04 | Verified |

---

## 3. Coverage Summary

| Category | Total Requirements | Verified | Planned | In Progress |
|---|---|---|---|---|
| Functional — Analysis | 7 | 7 | 0 | 0 |
| Functional — HITL | 5 | 5 | 0 | 0 |
| Functional — MR | 7 | 6 | 1 | 0 |
| Functional — Monitor | 6 | 6 | 0 | 0 |
| Functional — Audit | 5 | 5 | 0 | 0 |
| Functional — Queue | 4 | 4 | 0 | 0 |
| Functional — Planner | 3 | 3 | 0 | 0 |
| Functional — Web UI | 6 | 6 | 0 | 0 |
| Non-Functional | 10 | 7 | 3 | 0 |
| **TOTAL** | **53** | **49** | **4** | **0** |

**Verification coverage: 92.5% verified, 7.5% planned (performance tests pending hardware setup)**

---

## 4. Unverified Requirements Action Plan

| Req ID | Planned Completion | Owner |
|---|---|---|
| FR-MR-007 (post review as comment) | Next release | Developer |
| NFR-PERF-001 (analysis latency) | QA sprint | QA Engineer |
| NFR-PERF-002 (MR review latency) | QA sprint | QA Engineer |
| NFR-PERF-003 (API response time) | QA sprint | QA Engineer |

---

*Document Owner: Systems Engineering / Quality Assurance*
*Next Review Date: 2026-09-11*
