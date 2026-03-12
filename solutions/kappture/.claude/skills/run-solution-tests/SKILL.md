---
name: run-solution-tests
description: Run the kappture solution tests.
user-invocable: true
allowed-tools: Bash
---

```bash
cd C:/System-Team-repos/SystemAutonomousAgent
.venv/Scripts/pytest solutions/kappture/tests/ -v --tb=short 2>&1
```

Report pass/fail. If no tests exist yet, say: "No tests found — create solutions/kappture/tests/ to add solution-specific tests."
