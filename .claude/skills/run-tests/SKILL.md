---
name: run-tests
description: >
  Run the SAGE Framework test suite. Use when the user asks to run tests,
  check if something is broken, or after making code changes. Supports
  targeting specific test scopes: framework, api, llm, all, or any solution name.
user-invocable: true
allowed-tools: Bash
---

Run the appropriate test suite for the SAGE Framework based on $ARGUMENTS.

## Argument mapping

| Argument | Command |
|---|---|
| (empty) | `make test` — framework unit tests only (fastest) |
| `all` | `make test-all` — framework + all solution tests |
| `api` | `.venv/Scripts/pytest tests/test_api.py -v` |
| `llm` | `.venv/Scripts/pytest tests/test_llm_gateway.py -v` |
| `phase2` | `.venv/Scripts/pytest tests/test_phase2_n8n.py -v` |
| `phase3` | `.venv/Scripts/pytest tests/test_phase3_langgraph.py -v` |
| `phase4` | `.venv/Scripts/pytest tests/test_phase4_autogen.py -v` |
| `streaming` | `.venv/Scripts/pytest tests/test_phase5_streaming.py -v` |
| `onboarding` | `.venv/Scripts/pytest tests/test_phase6_onboarding.py -v` |
| `features` | `.venv/Scripts/pytest tests/test_phase7_11_features.py -v` |
| A solution name (e.g. `meditation_app`) | `.venv/Scripts/pytest solutions/<name>/tests/ -v` |
| A file path | Run that specific test file with pytest -v |

## Steps

1. Check that `.venv/` exists at the repo root (`C:/sandbox/SAGE`).
   If it does not, tell the user to run `make venv` first.

2. Run the command for the given argument (default: `make test`).
   Always run from `C:/sandbox/SAGE`.

3. Report:
   - Total passed / failed / skipped
   - Any failure tracebacks in full
   - Suggested fix if the failure is a known pattern (wrong sys.path, missing
     fixture, attribute name change on VectorMemory, import error from missing dep)

4. If all tests pass, confirm clearly: "All N tests passed."
