---
name: run-solution-tests
description: >
  Run the medtech solution test suite (IQ/OQ/PQ validation tests + e2e tests).
  Use after any change to medtech YAML configs, prompts, or solution-specific tools.
user-invocable: true
allowed-tools: Bash
---

Run the medtech solution test suite.

```bash
cd C:/System-Team-repos/SystemAutonomousAgent
.venv/Scripts/pytest solutions/medtech/tests/ -v --tb=short 2>&1
```

Report:
- Total passed / failed / skipped
- Any IQ/OQ/PQ validation failures in full (these are compliance-critical)
- Suggested fix for known failure patterns:
  - `fixture not found` → conftest.py missing or SAGE_ROOT path depth wrong
  - `PROJECT_ROOT` error → count parent levels from test file to repo root (should be 5)
  - `vm._vector_store` AttributeError → use `_vector_store` not `vector_store`
  - `GITLAB_URL not configured` in e2e → set `agent._api_base` in the test fixture

If all tests pass, confirm: "All medtech solution tests passed — IQ/OQ/PQ validated."
