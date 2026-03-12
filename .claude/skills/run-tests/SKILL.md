---
name: run-tests
description: >
  Run the SAGE Framework test suite. Use when the user asks to run tests,
  check if something is broken, or after making code changes. Supports
  targeting specific test scopes: framework, medtech, dfs, or all.
user-invocable: true
allowed-tools: Bash
---

Run the appropriate test suite for the SAGE Framework based on $ARGUMENTS.

## Argument mapping

| Argument | Command |
|---|---|
| (empty) | `make test` — framework unit tests only (fastest) |
| `all` | `make test-all` — framework + all solution tests |
| `medtech` | `cd SystemAutonomousAgent && .venv/Scripts/pytest solutions/medtech/tests/ -v` |
| `dfs` | `cd SystemAutonomousAgent && .venv/Scripts/pytest solutions/dfs/tests/ -v` |
| `api` | `.venv/Scripts/pytest tests/test_api.py -v` |
| `llm` | `.venv/Scripts/pytest tests/test_llm_gateway.py -v` |
| A file path | Run that specific test file with pytest -v |

## Steps

1. Check that `.venv/` exists at the repo root (`C:/System-Team-repos/SystemAutonomousAgent`).
   If it doesn't, tell the user to run `make venv` first.

2. Run the command for the given argument (default: `make test`).
   Always run from `C:/System-Team-repos/SystemAutonomousAgent`.

3. Report:
   - Total passed / failed / skipped
   - Any failure tracebacks in full
   - Suggested fix if the failure is a known pattern (wrong sys.path, missing fixture,
     attribute name change on VectorMemory, etc.)

4. If all tests pass, confirm clearly: "All N tests passed."
