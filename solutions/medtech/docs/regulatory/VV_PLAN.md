# Verification & Validation Plan
## SAGE[ai] — Autonomous Manufacturing Intelligence System

**Document ID:** SAGE-VVP-001
**Version:** 2.0.0
**Status:** Approved
**Date:** 2026-03-11

---

## 1. Purpose and Scope

This Verification and Validation (V&V) Plan defines the strategy, activities, methods, and responsibilities for verifying and validating the SAGE[ai] software system in accordance with:
- **IEC 62304:2006+AMD1:2015** §5.6 (Software Verification) and §5.7 (Software Integration and Integration Testing)
- **ISO 13485:2016** §7.3 (Design and Development)
- **FDA 21 CFR Part 11** (Electronic Records / Audit Trail Validation)

### 1.1 Scope
This plan covers all software verification and validation activities for SAGE[ai] v2.0.0, including:
- Unit tests for individual components
- Integration tests with external systems
- System-level end-to-end workflow tests
- Performance and load tests
- IQ/OQ/PQ validation (Installation, Operational, Performance Qualification)
- Compliance-specific tests (audit trail, HITL enforcement)

---

## 2. Definitions

| Term | Definition |
|---|---|
| **Verification** | Confirmation that software meets its specified requirements (Did we build it right?) |
| **Validation** | Confirmation that software meets the intended use (Did we build the right thing?) |
| **IQ** | Installation Qualification — verifies the system is installed correctly |
| **OQ** | Operational Qualification — verifies the system operates per specifications |
| **PQ** | Performance Qualification — verifies the system performs under real operating conditions |
| **Test Case** | A documented set of inputs, execution conditions, and expected results |

---

## 3. V&V Strategy

### 3.1 Verification Approach
Verification is performed at three levels:

| Level | Method | Scope |
|---|---|---|
| Unit | Automated pytest tests | Individual classes and functions |
| Integration | Automated pytest + mock servers | Agent-to-external-system interfaces |
| System | End-to-end workflow tests | Complete user workflows |

### 3.2 Validation Approach
Validation confirms SAGE[ai] meets its intended use by:
1. Executing IQ/OQ/PQ qualification scripts
2. User Acceptance Testing (UAT) with manufacturing engineers
3. Compliance-specific test execution and review

### 3.3 Test Environment Requirements

| Component | Requirement |
|---|---|
| Python | 3.11.x |
| Test framework | pytest ≥7.4 |
| Coverage tool | pytest-cov |
| Mock library | pytest-mock, unittest.mock |
| HTTP mock | responses (for GitLab/Metabase mocking) |
| CI/CD | Executed in GitLab CI pipeline |
| Database | Separate test SQLite instance (not production) |
| LLM | Mock LLM gateway for unit/integration tests |

---

## 4. Verification Test Plan

### 4.1 Unit Tests

#### UVT-001: LLM Gateway Unit Tests
**File:** `tests/test_llm_gateway.py`
**Requirements:** FR-ANAL-002, NFR-PERF-001

| Test ID | Test Case | Expected Result | Status |
|---|---|---|---|
| UVT-001-01 | Singleton pattern — two calls return same instance | assert gateway1 is gateway2 | Implemented |
| UVT-001-02 | generate() calls LLM provider with correct prompts | Mock provider receives correct arguments | Implemented |
| UVT-001-03 | Provider name returned correctly | get_provider_name() == "GeminiCLI" or "LocalLlama" | Implemented |
| UVT-001-04 | Thread lock prevents concurrent calls | Only one thread executes generate() at a time | Implemented |

#### UVT-002: Analyst Agent Unit Tests
**File:** `tests/test_analyst_agent.py`
**Requirements:** FR-ANAL-001 through FR-ANAL-007

| Test ID | Test Case | Expected Result | Status |
|---|---|---|---|
| UVT-002-01 | analyze_log() returns severity, root_cause, action | All three keys present in result | Implemented |
| UVT-002-02 | analyze_log() assigns unique trace_id | trace_id is valid UUID v4 | Implemented |
| UVT-002-03 | analyze_log() logs to audit trail | audit_logger.log_event called once | Implemented |
| UVT-002-04 | analyze_log() with empty input raises error | HTTP 400 or error dict returned | Implemented |
| UVT-002-05 | learn_from_feedback() stores to vector store | vector_store.add_feedback called | Implemented |
| UVT-002-06 | RAG context retrieved and included in prompt | search() called; result in LLM prompt | Implemented |

#### UVT-003: Developer Agent Unit Tests
**File:** `tests/test_developer_agent.py`
**Requirements:** FR-MR-001 through FR-MR-007

| Test ID | Test Case | Expected Result | Status |
|---|---|---|---|
| UVT-003-01 | review_merge_request() returns summary/issues/suggestions/approved | All keys present | Implemented |
| UVT-003-02 | _react_loop() terminates on FinalAnswer | Returns FinalAnswer content | Implemented |
| UVT-003-03 | _react_loop() executes tool call | Tool callable invoked with parsed args | Implemented |
| UVT-003-04 | _react_loop() respects max_steps | Does not exceed max_steps iterations | Implemented |
| UVT-003-05 | create_mr_from_issue() calls GitLab POST | POST /projects/{id}/merge_requests called | Implemented |
| UVT-003-06 | list_open_mrs() returns MR list | merge_requests array in result | Implemented |
| UVT-003-07 | get_pipeline_status() returns status dict | status key present in result | Implemented |
| UVT-003-08 | GitLab API failure returns error dict | error key present | Implemented |

#### UVT-004: Queue Manager Unit Tests
**File:** `tests/test_queue_manager.py`
**Requirements:** FR-QUEUE-001 through FR-QUEUE-004

| Test ID | Test Case | Expected Result | Status |
|---|---|---|---|
| UVT-004-01 | submit() returns unique task_id | Valid UUID returned | Implemented |
| UVT-004-02 | submit() persists task to SQLite | Row exists in task_queue table | Implemented |
| UVT-004-03 | get_next() returns highest-priority task | Priority 1 returned before priority 5 | Implemented |
| UVT-004-04 | mark_done() updates SQLite record | status='completed' in DB | Implemented |
| UVT-004-05 | mark_failed() updates SQLite record | status='failed', error set in DB | Implemented |
| UVT-004-06 | Pending tasks restored on TaskQueue re-init | Tasks with status 'pending' re-enqueued | Implemented |

#### UVT-005: Audit Logger Unit Tests
**File:** `tests/test_audit_logger.py`
**Requirements:** FR-AUDIT-001 through FR-AUDIT-005

| Test ID | Test Case | Expected Result | Status |
|---|---|---|---|
| UVT-005-01 | log_event() returns UUID | Valid UUID v4 returned | Implemented |
| UVT-005-02 | log_event() writes to SQLite | Row present in compliance_audit_log | Implemented |
| UVT-005-03 | Records are immutable — no delete method | No delete/update methods on audit_logger | Implemented |
| UVT-005-04 | Timestamp stored in UTC | timestamp column uses UTC timezone | Implemented |

#### UVT-006: Planner Agent Unit Tests
**File:** `tests/test_planner_agent.py`
**Requirements:** FR-PLAN-001 through FR-PLAN-003

| Test ID | Test Case | Expected Result | Status |
|---|---|---|---|
| UVT-006-01 | create_plan() returns ordered list | List of dicts with step/task_type/payload | Implemented |
| UVT-006-02 | Invalid task_type filtered out | Only VALID_TASK_TYPES in result | Implemented |
| UVT-006-03 | plan_and_execute() submits tasks to queue | task_queue.submit called per step | Implemented |
| UVT-006-04 | plan_and_execute() logs to audit | audit_logger.log_event called | Implemented |

#### UVT-007: REST API Unit Tests
**File:** `tests/test_api.py`
**Requirements:** FR-WEB-001, FR-HITL-001 through FR-HITL-004

| Test ID | Test Case | Expected Result | Status |
|---|---|---|---|
| UVT-007-01 | GET /health returns 200 | status='ok' in response | Implemented |
| UVT-007-02 | POST /analyze with valid body returns 200 | trace_id in response | Implemented |
| UVT-007-03 | POST /analyze with empty body returns 400 | HTTP 400 | Implemented |
| UVT-007-04 | POST /approve/{id} with valid id returns 200 | status='approved' | Implemented |
| UVT-007-05 | POST /approve/{id} with unknown id returns 404 | HTTP 404 | Implemented |
| UVT-007-06 | GET /audit returns paginated results | entries array, total count | Implemented |
| UVT-007-07 | GET /mr/open returns MR list | merge_requests array | Implemented |
| UVT-007-08 | GET /mr/pipeline returns pipeline status | status key | Implemented |
| UVT-007-09 | CORS headers present in response | Access-Control-Allow-Origin header | Implemented |

---

### 4.2 Integration Tests

#### IVT-001: GitLab Integration Tests
**File:** `tests/integration/test_gitlab_integration.py`
**Requirements:** FR-MR-001 through FR-MR-006
**Precondition:** GITLAB_URL, GITLAB_TOKEN, GITLAB_PROJECT_ID set

| Test ID | Description |
|---|---|
| IVT-001-01 | Create MR from real GitLab issue |
| IVT-001-02 | Review a real GitLab MR |
| IVT-001-03 | List open MRs from real project |
| IVT-001-04 | Get pipeline status for a real MR |

#### IVT-002: Metabase Integration Tests
**File:** `tests/integration/test_metabase_integration.py`
**Requirements:** FR-MON-002

#### IVT-003: Teams Integration Tests
**File:** `tests/integration/test_teams_integration.py`
**Requirements:** FR-MON-001

---

### 4.3 End-to-End System Tests

#### SVT-001: Analyze → Approve Workflow
**File:** `tests/e2e/test_analyze_approve_flow.py`
**Requirements:** FR-ANAL-001 to FR-ANAL-007, FR-HITL-001 to FR-HITL-005

Steps:
1. POST /analyze with test log entry
2. Verify trace_id returned and audit record exists
3. POST /approve/{trace_id}
4. Verify approval logged in audit trail

#### SVT-002: Analyze → Reject → Learn Workflow
Steps:
1. POST /analyze
2. POST /reject/{trace_id} with feedback
3. Verify feedback ingested into vector store
4. POST /analyze with similar log entry
5. Verify RAG context includes previous feedback

#### SVT-003: MR Creation and Review Workflow
Steps:
1. POST /mr/create with project_id and issue_iid
2. Verify MR URL returned and audit logged
3. POST /mr/review with project_id and mr_iid
4. Verify ReAct loop executed (multiple steps in trace)
5. Verify review result contains summary/issues/suggestions/approved

---

## 5. IQ/OQ/PQ Qualification

### 5.1 Installation Qualification (IQ)

| IQ Test | Verification Method | Acceptance Criteria |
|---|---|---|
| IQ-001: Python version | `python --version` | Python 3.11.x |
| IQ-002: Dependencies installed | `pip check` | No conflicts reported |
| IQ-003: SQLite DB created | Check file exists at `data/audit_log.db` | File exists and is writable |
| IQ-004: Config loaded | `python src/main.py --help` exits 0 | No errors |
| IQ-005: API starts | `python src/main.py api` and `curl /health` | HTTP 200 with status='ok' |
| IQ-006: task_queue table exists | SQLite query | Table present with correct schema |

### 5.2 Operational Qualification (OQ)

| OQ Test | Verification Method | Acceptance Criteria |
|---|---|---|
| OQ-001: Log analysis | POST /analyze with known error | severity, root_cause, recommended_action returned |
| OQ-002: Approval workflow | POST /approve → audit log checked | APPROVAL record with correct actor |
| OQ-003: HITL enforcement | Attempt to approve non-existent trace | HTTP 404 |
| OQ-004: Audit immutability | No delete exposed | No DELETE endpoint or method |
| OQ-005: Task queue persistence | Submit task → kill process → restart → check queue | Task re-enqueued |
| OQ-006: CORS headers | `curl -H Origin: http://localhost:5173 /health` | Allow-Origin header present |
| OQ-007: ReAct loop | POST /mr/review → check audit | Multiple REACT_STEP entries in trace |

### 5.3 Performance Qualification (PQ)

| PQ Test | Method | Acceptance Criteria |
|---|---|---|
| PQ-001: Analysis latency | Time POST /analyze over 10 runs | p95 < 60 seconds |
| PQ-002: API response time | Time GET /health, /audit, /monitor/status | p95 < 2 seconds |
| PQ-003: Queue throughput | Submit 100 tasks, measure completion time | All complete without data loss |
| PQ-004: Concurrent requests | 10 simultaneous POST /analyze requests | All queued; single-lane enforced |
| PQ-005: Audit log scale | Insert 10,000 records; query with pagination | Query returns in < 2 seconds |

---

## 6. Test Execution and Reporting

### 6.1 Test Execution Commands

```bash
# Unit tests only
pytest -m unit --tb=short

# Integration tests (requires env vars)
pytest -m integration --tb=long

# Compliance / validation tests
pytest -m compliance --tb=long --html=reports/compliance_report.html

# Full suite with coverage
pytest --cov=src --cov-report=html:reports/coverage
```

### 6.2 Pass/Fail Criteria

| Test Category | Minimum Pass Rate | Compliance Action if Failed |
|---|---|---|
| Unit tests | 100% | Block release |
| Integration tests | ≥95% | Investigate; document deviations |
| E2E system tests | 100% | Block release |
| IQ/OQ/PQ | 100% | Block release; open CAPA |

### 6.3 Deviation Handling
Any test failure during a formal qualification run SHALL be documented as a deviation and assigned a CAPA (Corrective and Preventive Action). The system SHALL NOT be released until all deviations are resolved or formally accepted with risk justification.

---

## 7. Traceability

The Requirements Traceability Matrix (RTM.md) maps every requirement in the SRS to the verification test cases in this plan and the corresponding test results.

---

*Document Owner: Systems Engineering / Quality Assurance*
*Next Review Date: 2026-09-11*
