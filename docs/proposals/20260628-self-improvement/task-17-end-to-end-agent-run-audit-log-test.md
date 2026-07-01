# Task 17: End-to-end agent run -> audit log test

**Category:** testing  
**Score:** 0.0/10  
**Converged:** False  
**Iterations:** 3  
**Elapsed:** 25s  

---

## Task

Add an integration test in tests/test_integration_agent_audit.py that: (1) posts a task to /agent/run via TestClient; (2) polls /agent/status until complete; (3) checks /audit/log contains an entry for that task_id; (4) checks the audit entry has the correct agent role and status. Mock the LLM provider to return a deterministic response.

## Criteria

test_integration_agent_audit.py exists with at least 2 test cases; LLM is mocked (no real API calls); audit log entry is verified by task_id; tests pass with pytest.

## Proposal (submit to HITL approval gate)

Error from Claude Code CLI: Unknown error

---

## Iteration History

**Iter 1** — score 0.0 pass=False  
Feedback: (no parseable feedback)  

**Iter 2** — score 0.0 pass=False  
Feedback: (no parseable feedback)  

**Iter 3** — score 0.0 pass=False  
Feedback: (no parseable feedback)  

