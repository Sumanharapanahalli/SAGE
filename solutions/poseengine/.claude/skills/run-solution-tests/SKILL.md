---
name: run-solution-tests
description: Run the poseengine solution tests.
user-invocable: true
allowed-tools: Bash
---

```bash
cd C:/System-Team-repos/SystemAutonomousAgent
.venv/Scripts/pytest solutions/poseengine/tests/ -v --tb=short 2>&1
```

Report pass/fail. If no tests exist yet, say: "No tests found — create solutions/poseengine/tests/ to add solution-specific tests."
