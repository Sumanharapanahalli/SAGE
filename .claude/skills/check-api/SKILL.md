---
name: check-api
description: >
  Smoke-test all live SAGE Framework API endpoints. Use when the user wants
  to verify the backend is healthy, after changes to api.py, or to diagnose
  a specific endpoint issue. $ARGUMENTS can be a specific endpoint path to
  focus on (e.g. "/llm/status") or empty to test all.
user-invocable: true
allowed-tools: Bash
---

Smoke-test the SAGE Framework REST API running at http://localhost:8000.

## Endpoints to test (when $ARGUMENTS is empty)

Run each curl and report status code + key fields. Mark ✅ pass or ❌ fail.

```bash
# Core
curl -s http://localhost:8000/health
curl -s http://localhost:8000/config/project
curl -s http://localhost:8000/config/projects

# LLM
curl -s http://localhost:8000/llm/status

# YAML editor
curl -s http://localhost:8000/config/yaml/project
curl -s http://localhost:8000/config/yaml/prompts
curl -s http://localhost:8000/config/yaml/tasks

# Audit
curl -s "http://localhost:8000/audit?limit=5"

# Monitor
curl -s http://localhost:8000/monitor/status

# Feature requests
curl -s "http://localhost:8000/feedback/feature-requests?status=pending"
```

## If $ARGUMENTS is a path

Only test that endpoint. Print the full JSON response.

## Output format

For each endpoint:
```
✅ GET /health          200  status=ok  project=medtech  llm=GeminiCLI(gemini-2.5-flash)
✅ GET /llm/status      200  calls_today=0  daily_limit=500  model=gemini-2.5-flash
❌ GET /monitor/status  500  detail="MonitorAgent not initialised"
```

## Common failures and fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| Connection refused | Backend not running | `make run PROJECT=medtech` |
| 500 on /config/yaml | solutions/ dir not found | Check `SAGE_SOLUTIONS_DIR` |
| 500 on /llm/status | LLM gateway init failed | Check Gemini CLI is installed |
| 404 on any route | Wrong FastAPI version | `make venv` to reinstall deps |
