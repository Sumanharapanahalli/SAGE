# Software Testing Report Template
## SAGE[ai] — Autonomous Manufacturing Intelligence System

**Document ID:** SAGE-TR-001
**Version:** 2.0.0
**Template Status:** Approved
**Date:** 2026-03-11

---
> **Instructions:** Copy this template for each formal test execution. Replace all `[PLACEHOLDER]` values.
> Remove this instruction block before approving the completed report.

---

## Test Report Header

| Field | Value |
|---|---|
| **Report ID** | [e.g., TR-2026-001] |
| **Report Date** | [YYYY-MM-DD] |
| **Software Version** | [e.g., 2.0.0] |
| **Git Commit** | [SHA hash] |
| **Test Type** | [Unit / Integration / System / IQ/OQ/PQ] |
| **Test Executor** | [Name, Role] |
| **Environment** | [OS, Python version, hardware specs] |
| **Test Plan Reference** | SAGE-VVP-001 v2.0.0 |

---

## 1. Test Scope

### 1.1 Objectives
[Describe the objectives of this test run. E.g., "Verify all unit tests pass following the addition of the ReAct loop to DeveloperAgent."]

### 1.2 Items Under Test
| Component | Version | Notes |
|---|---|---|
| [e.g., src/agents/developer.py] | [2.0.0] | [Modified in this release] |

### 1.3 Out of Scope
[List any items excluded from this test run and justification.]

---

## 2. Test Environment

### 2.1 Software Environment

| Component | Version |
|---|---|
| OS | [Windows 11 / Ubuntu 22.04] |
| Python | [3.11.x] |
| pytest | [7.x] |
| LLM Provider | [Gemini CLI / Local Llama] |
| GitLab | [Connected / Mocked] |

### 2.2 Hardware Environment
| Component | Specification |
|---|---|
| CPU | [e.g., Intel Core i7-12700] |
| RAM | [e.g., 32 GB] |
| Storage | [e.g., 512 GB NVMe SSD] |
| GPU (if Local Llama) | [e.g., NVIDIA RTX 4060, 8 GB VRAM] |

### 2.3 Environment Deviations
[Document any deviations from the defined test environment and their potential impact.]

---

## 3. Test Execution Summary

| Category | Total | Passed | Failed | Skipped | Pass Rate |
|---|---|---|---|---|---|
| Unit Tests | | | | | |
| Integration Tests | | | | | |
| E2E System Tests | | | | | |
| IQ Tests | | | | | |
| OQ Tests | | | | | |
| PQ Tests | | | | | |
| **TOTAL** | | | | | |

**Overall Result:** [PASS / FAIL / CONDITIONAL PASS]

---

## 4. Detailed Test Results

### 4.1 Unit Test Results

```
pytest -m unit --tb=short

[Paste full pytest output here]
```

**Summary:**
- Tests executed: [N]
- Passed: [N]
- Failed: [N]
- Coverage: [N]%

### 4.2 Integration Test Results

```
pytest -m integration --tb=long

[Paste full pytest output here]
```

### 4.3 E2E System Test Results

| Test ID | Test Name | Result | Notes |
|---|---|---|---|
| SVT-001 | Analyze → Approve workflow | PASS / FAIL | |
| SVT-002 | Analyze → Reject → Learn workflow | PASS / FAIL | |
| SVT-003 | MR Creation and Review workflow | PASS / FAIL | |

### 4.4 IQ/OQ/PQ Results

| Test ID | Description | Expected | Actual | Result |
|---|---|---|---|---|
| IQ-001 | Python version | 3.11.x | | |
| IQ-002 | pip check | No conflicts | | |
| IQ-003 | SQLite DB created | File exists | | |
| IQ-004 | Config loaded | Exit 0 | | |
| IQ-005 | API starts | HTTP 200 /health | | |
| IQ-006 | task_queue table | Schema correct | | |
| OQ-001 | Log analysis | severity/root_cause returned | | |
| OQ-002 | Approval workflow | APPROVAL audit record | | |
| OQ-003 | HITL enforcement | HTTP 404 on bad trace | | |
| OQ-004 | Audit immutability | No DELETE method | | |
| OQ-005 | Queue persistence | Tasks restored on restart | | |
| OQ-006 | CORS headers | Allow-Origin present | | |
| OQ-007 | ReAct loop | Multi-step trace in audit | | |
| PQ-001 | Analysis latency p95 | < 60s | | |
| PQ-002 | API response p95 | < 2s | | |
| PQ-003 | Queue throughput | 100 tasks complete | | |

---

## 5. Defects and Deviations

### 5.1 Failed Tests

| Defect ID | Test ID | Severity | Description | Root Cause | Resolution |
|---|---|---|---|---|---|
| [DEF-001] | [UVT-XXX] | [Critical/Major/Minor] | [Description] | [Cause] | [Action] |

### 5.2 Deviations from Test Plan

| Deviation ID | Description | Justification | Risk Assessment | Approval |
|---|---|---|---|---|
| [DEV-001] | [What deviated] | [Why] | [Impact on results] | [Approver name] |

---

## 6. Performance Results

| Metric | Target | Measured | Pass/Fail |
|---|---|---|---|
| Analysis latency (p95) | < 60s | | |
| MR review latency (p95) | < 120s | | |
| API non-LLM latency (p95) | < 2s | | |
| Web UI load time | < 3s | | |

---

## 7. Test Coverage

| Module | Statements | Covered | Coverage % |
|---|---|---|---|
| src/agents/analyst.py | | | |
| src/agents/developer.py | | | |
| src/agents/monitor.py | | | |
| src/agents/planner.py | | | |
| src/core/queue_manager.py | | | |
| src/core/llm_gateway.py | | | |
| src/memory/audit_logger.py | | | |
| src/memory/vector_store.py | | | |
| src/interface/api.py | | | |
| **Overall** | | | **≥80% required** |

---

## 8. Conclusion and Recommendation

### 8.1 Test Conclusion
[Summarise the overall test outcome. State whether the software meets its requirements as specified in SAGE-SRS-001.]

### 8.2 Recommendation
- [ ] **APPROVED FOR RELEASE** — All tests passed; no open critical/major defects
- [ ] **CONDITIONAL APPROVAL** — Minor deviations accepted; see §5.2
- [ ] **NOT APPROVED** — Failed tests require resolution before release

### 8.3 Outstanding Actions
| Action | Owner | Due Date | Priority |
|---|---|---|---|
| | | | |

---

## 9. Signatures

| Role | Name | Signature | Date |
|---|---|---|---|
| Test Executor | | | |
| Technical Reviewer | | | |
| QA Reviewer | | | |
| Approval Authority | | | |

---

*Template Owner: Quality Assurance Team*
*Template Version: 2.0.0*
