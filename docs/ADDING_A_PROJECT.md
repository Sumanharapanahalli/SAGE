# SAGE Framework — Adding a New Solution

> This guide walks through creating a complete solution configuration for a new domain. No Python code changes are needed — SAGE loads everything from YAML.

---

## Overview

A SAGE solution is defined by three YAML files in a directory under `solutions/`:

```
solutions/
└── <solution-name>/
    ├── project.yaml    Required — identity, modules, compliance standards, integrations
    ├── prompts.yaml    Required — LLM system prompts for each agent
    └── tasks.yaml      Required — valid task types and their payload schemas
```

When you run `make run PROJECT=<solution-name>` (or `python src/main.py api --project <solution-name>`), the `ProjectConfig` singleton loads these three files, merges settings over the base `config/config.yaml`, and makes everything available to all agents, the task queue, and the REST API.

The solutions directory is controlled by the `SAGE_SOLUTIONS_DIR` environment variable (default: `solutions`). You can point it at an external directory to keep solutions outside the framework root.

---

## Step 1 — Create `project.yaml`

This file defines the solution's identity and which framework features are active.

**Location:** `solutions/<name>/project.yaml`

**Minimum required fields:**

```yaml
name: "My Project Name"         # Human-readable name (shown in web UI and /health)
version: "1.0.0"                # SemVer
domain: "my-domain"             # Short slug for internal use (e.g. "fintech", "iot", "saas")
description: >
  One-paragraph description of what this project is and what SAGE does for it.

# Which web UI pages are shown for this project
# Must match keys in web/src/registry/modules.ts MODULE_REGISTRY
active_modules:
  - dashboard
  - analyst
  - developer
  - monitor
  - audit
  - improvements

# Compliance standards relevant to this project (shown in /config/project and UI)
compliance_standards:
  - "ISO/IEC 25010 (Software Quality)"
  - "OWASP Top 10"
  # Add any applicable: GDPR, ISO 27001, SOC 2, HIPAA, etc.

# Which integrations are active (used for documentation and UI status indicators)
integrations:
  - gitlab
  - teams
  # Add from: gitlab, github, teams, metabase, spira, serial, jlink,
  #            wandb, firebase, rtsp, prometheus, grafana, ci_cd

# Optional: override base config keys for this project
settings:
  memory:
    collection_name: "myproject_knowledge"   # ChromaDB collection name (must be unique)
  system:
    max_concurrent_tasks: 1                  # Keep at 1 for audit trail compliance
```

**Optional: UI label overrides**

If you want the web UI to use domain-specific language instead of the generic defaults:

```yaml
ui_labels:
  analyst_page_title:   "Security Log Analyzer"
  analyst_input_label:  "Security event log or alert text"
  developer_page_title: "Code Security Reviewer"
  monitor_page_title:   "Threat Monitor"
  dashboard_subtitle:   "Application Security Health"
```

**Real example — kappture solution:**

```yaml
name: "Kappture Human Tracking"
version: "1.0.0"
domain: "cv-tracking"
description: >
  Autonomous AI agent for the Kappture human tracking and behaviour analytics
  platform. Monitors real-time tracking pipeline health, analyzes accuracy
  and performance metrics, reviews computer vision code, and manages
  CI/CD for multi-camera tracking deployments.

active_modules:
  - dashboard
  - analyst
  - developer
  - monitor
  - audit
  - improvements

compliance_standards:
  - "GDPR Article 9 (biometric data processing)"
  - "IEEE 730 (Software Quality Assurance)"
  - "ISO/IEC 25010 (Software Quality Model)"
  - "GDPR Art. 35 (DPIA for tracking systems)"

integrations:
  - gitlab
  - github
  - teams
  - rtsp
  - prometheus
  - grafana

settings:
  memory:
    collection_name: "kappture_knowledge"
  system:
    max_concurrent_tasks: 1

ui_labels:
  analyst_page_title:    "Tracking Log Analyzer"
  analyst_input_label:   "Tracking log, accuracy report, or camera error"
  developer_page_title:  "CV Code Reviewer"
  monitor_page_title:    "Pipeline Monitor"
  dashboard_subtitle:    "Real-time Human Tracking Health"
```

---

## Step 2 — Create `prompts.yaml`

This file defines the LLM system prompts for each agent. The agents load their prompts from this file at startup via `project_config.get_prompts(agent_name)`.

**Location:** `solutions/<name>/prompts.yaml`

### Analyst Agent Prompts

The analyst system prompt defines the AI persona and expected JSON output schema. The LLM is instructed to return strict JSON — no markdown, no prose.

```yaml
analyst:
  system_prompt: |
    You are a Senior [Domain] Engineer with expertise in [specific area].
    Analyze the provided [input type] carefully.
    Use the provided CONTEXT from past incidents if relevant — especially
    any human corrections stored in memory.

    Output your analysis in STRICT JSON format with keys:
      severity              : "RED" | "AMBER" | "GREEN" | "UNKNOWN"
      root_cause_hypothesis : string — concise technical hypothesis
      recommended_action    : string — specific next step for the engineer
    Do not output markdown, prose, or any text outside the JSON object.

  user_prompt_template: |
    INPUT:
    {input}

    PAST CONTEXT (Human Feedback & Historical Incidents):
    {context}

    Generate Analysis JSON:

  output_schema:
    severity: "RED | AMBER | GREEN | UNKNOWN"
    root_cause_hypothesis: "string"
    recommended_action: "string"

  severity_levels:
    RED:    "Critical — immediate action required"
    AMBER:  "Warning — investigate within 4 hours"
    GREEN:  "Informational — no immediate action"
    UNKNOWN: "Unable to determine — escalate to senior engineer"
```

You can extend the output schema with domain-specific fields. For example, the kappture project adds:

```yaml
    metric_summary  : dict   — extracted key metrics (can be empty {})
    privacy_risk    : bool   — true if any personal data / GDPR concern
```

As long as your system prompt instructs the LLM to return these keys, the analyst agent will pass them through transparently.

### Developer Agent Prompts

```yaml
developer:
  review_system_prompt: |
    You are a Senior [Domain] Engineer performing a code review.
    Review the provided diff carefully for:
      - [domain-specific concerns, e.g. algorithm correctness, memory safety]
      - [compliance concerns, e.g. GDPR data handling, security]
      - [quality concerns, e.g. test coverage, error handling]
    Return STRICT JSON with keys:
      summary     : string — overall review summary
      issues      : list of { file, line, severity, description, suggestion }
      suggestions : list of string — general improvements
      approved    : bool — true only if no critical/major issues

  mr_create_system_prompt: |
    You are a Senior [Domain] Engineer creating a merge request.
    Given the issue description, create a properly structured MR with:
      - Clear, imperative title (max 72 chars)
      - Description (what, why, impact)
      - Test plan
    Return STRICT JSON with keys: title, description, source_branch, target_branch
```

### Planner Agent Prompts

The planner prompt must enumerate the exact task types defined in `tasks.yaml`. The LLM is instructed to only use task types from this list.

```yaml
planner:
  system_prompt: |
    You are a Planning Agent for [project name].
    Decompose the user's natural-language request into a sequence of atomic,
    executable tasks.

    VALID_TASK_TYPES (you MUST use only these):
      MY_TASK_TYPE_1  - Description of what this task does
      MY_TASK_TYPE_2  - Description of what this task does
      PLAN_TASK        - Sub-planning step (nested orchestration)

    Each task MUST have:
      step        : integer starting at 1
      task_type   : one of VALID_TASK_TYPES
      payload     : dict of arguments for that task type
      description : human-readable explanation of this step

    Return a JSON array only — no markdown, no explanation outside the array.
```

### Monitor Agent Prompts

```yaml
monitor:
  system_prompt: |
    You are a real-time operations monitor for [project name].
    Classify the following event from [relevant sources].
    Return STRICT JSON with keys:
      severity            : "critical" | "high" | "medium" | "low" | "info"
      requires_action     : bool
      suggested_task_type : one of the VALID_TASK_TYPES or null
      summary             : string — concise event description
```

**Real example — kappture analyst prompt (abbreviated):**

```yaml
analyst:
  system_prompt: |
    You are a Senior Computer Vision and Human Tracking Engineer with deep
    expertise in multi-camera tracking systems, re-identification algorithms,
    pose estimation, and real-time video analytics.

    Analyze the provided tracking log, accuracy report, or camera pipeline error.
    Use the provided CONTEXT from past incidents if relevant.

    Output your analysis in STRICT JSON format with keys:
      severity              : "RED" | "AMBER" | "GREEN" | "UNKNOWN"
      root_cause_hypothesis : string
      recommended_action    : string
      metric_summary        : dict   — e.g. {MOTA: 0.78, IDF1: 0.82}
      privacy_risk          : bool   — true if GDPR concern
    Do not output markdown or any text outside the JSON object.
```

---

## Step 3 — Create `tasks.yaml`

This file defines the complete set of task types for your domain. The `TaskQueue` dispatcher and `PlannerAgent` both validate task types against this list.

**Location:** `solutions/<name>/tasks.yaml`

```yaml
task_types:
  - MY_TASK_TYPE_1
  - MY_TASK_TYPE_2
  - CREATE_MR           # Keep this — it's universal
  - PLAN_TASK           # Keep this — required for PlannerAgent

task_descriptions:
  MY_TASK_TYPE_1: "Human-readable description of what this task does"
  MY_TASK_TYPE_2: "Human-readable description of what this task does"
  CREATE_MR:     "Create a GitLab or GitHub merge request from an issue or branch"
  PLAN_TASK:     "Use PlannerAgent to decompose a complex request into subtasks"

# Payload schemas per task type (used for validation and UI hints)
# These are documentation — the framework uses them to validate planner output
task_payloads:
  MY_TASK_TYPE_1:
    required_field: "string — description of this field"
    optional_field: "string — optional description (optional)"

  MY_TASK_TYPE_2:
    log_text:     "string — the raw log to analyze"
    pipeline_id:  "string — pipeline ID (optional)"

  CREATE_MR:
    issue_description: "string — what to fix or implement"
    project_id:        "string — project ID (optional, uses default)"

  PLAN_TASK:
    description: "string — natural language task description for the planner"
    priority:    "integer 1-10 (default: 5)"
```

**Real example — kappture tasks (abbreviated):**

```yaml
task_types:
  - ANALYZE_TRACKING_LOG
  - ANALYZE_CAMERA_ERROR
  - ANALYZE_ACCURACY_REPORT
  - ANALYZE_CI_LOG
  - REVIEW_TRACKING_CODE
  - CREATE_MR
  - MONITOR_PIPELINE
  - MONITOR_ACCURACY
  - PLAN_TASK

task_descriptions:
  ANALYZE_TRACKING_LOG:    "Analyze real-time tracking pipeline output for failures or accuracy drops"
  ANALYZE_CAMERA_ERROR:    "Diagnose RTSP stream failures, camera offline events, or feed quality issues"
  ANALYZE_ACCURACY_REPORT: "Evaluate tracking accuracy metrics (MOTA, MOTP, IDF1, FP/FN rates)"
  ...

task_payloads:
  ANALYZE_TRACKING_LOG:
    log_text:   "string — raw tracking log output"
    camera_id:  "string — camera identifier (optional)"
    time_range: "string — ISO time range (optional)"

  ANALYZE_CAMERA_ERROR:
    log_text:   "string — camera error log or RTSP failure message"
    camera_id:  "string — camera identifier"
    stream_url: "string — RTSP URL (optional, for diagnostics)"

  ANALYZE_ACCURACY_REPORT:
    report_text:    "string — accuracy metrics report text or JSON"
    baseline_mota:  "float — acceptable MOTA threshold (default 0.75)"
  ...
```

---

## Step 4 — Run the New Solution

```bash
# Start the backend (recommended — uses .venv automatically)
make run PROJECT=<name>

# Or direct Python (requires venv activated)
python src/main.py api --project <name>

# Or with environment variable
SAGE_PROJECT=<name> python src/main.py api

# To use a solutions directory outside the framework root:
SAGE_SOLUTIONS_DIR=/path/to/external/solutions make run PROJECT=<name>
```

Verify the solution loaded correctly:

```bash
curl http://localhost:8000/config/project | python -m json.tool
```

Expected output (example for a project named `myproject`):

```json
{
  "name": "My Project Name",
  "version": "1.0.0",
  "domain": "my-domain",
  "compliance_standards": ["..."],
  "active_modules": ["dashboard", "analyst", "developer", "monitor", "audit", "improvements"],
  "integrations": ["gitlab", "teams"],
  "task_types": ["MY_TASK_TYPE_1", "MY_TASK_TYPE_2", "CREATE_MR", "PLAN_TASK"],
  "task_descriptions": {
    "MY_TASK_TYPE_1": "Human-readable description...",
    ...
  }
}
```

Also verify the solution appears in the solutions list:

```bash
curl http://localhost:8000/config/projects | python -m json.tool
```

---

## Step 5 — Test Your Configuration

### Smoke Test — Analyst Agent

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"log_entry": "Sample error log from my domain: connection timeout to service X"}'
```

The response should include a `severity`, `root_cause_hypothesis`, `recommended_action`, and `trace_id`. If your analyst prompt includes additional output fields, they should appear here too.

### Smoke Test — Planner Agent

Submit a request that should decompose into multiple tasks:

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"log_entry": "Please investigate the latest CI failure and create a fix MR"}'
```

If your planner prompt and task types are correct, the PlannerAgent will generate a JSON array of steps using only the task types you defined.

### Check the Audit Log

```bash
curl http://localhost:8000/audit?limit=5 | python -m json.tool
```

Every test call above should appear in the audit log with `actor: "AnalystAgent"` or `actor: "PlannerAgent"`.

---

## Step 6 (Optional) — Add Custom Web UI Module Metadata

Each web UI page is registered in `web/src/registry/modules.ts`. If you want domain-specific improvement hints and feature descriptions for your project's pages, update the `MODULE_REGISTRY` in that file.

The registry maps module IDs (which must match the `active_modules` keys in `project.yaml`) to `ModuleMetadata` objects:

```typescript
// In web/src/registry/modules.ts

import type { ModuleMetadata } from '../types/module'

export const MODULE_REGISTRY: Record<string, ModuleMetadata> = {
  analyst: {
    id: 'analyst',
    name: 'Log Analyzer',        // Override with your domain label if desired
    description: 'Analyze logs and events using AI-powered root cause analysis.',
    version: '1.2.0',
    route: '/analyst',
    features: [
      'RAG-powered context from past incidents',
      'Severity classification (RED/AMBER/GREEN)',
      'Human-in-the-loop approval/rejection',
      'Feedback learning loop to ChromaDB',
    ],
    improvementHints: [
      'Add bulk log upload (paste multiple events)',
      'Show confidence score next to severity badge',
      'Export analysis results to PDF',
    ],
  },
  // ... other modules
}
```

The `name` and `description` in this registry are what appear in the ModuleWrapper header strip at the top of each page. The `improvementHints` are the clickable suggestions in the info panel.

If you do not update the registry, the existing generic module metadata is used — the project still works correctly, it just shows generic labels rather than domain-specific ones.

---

## Checklist

Before considering your solution configuration complete:

- [ ] `solutions/<name>/project.yaml` created with all required fields
- [ ] `collection_name` in `settings.memory` is unique (does not clash with medtech, poseengine, or kappture)
- [ ] `solutions/<name>/prompts.yaml` created with `analyst`, `developer`, `planner`, and `monitor` sections
- [ ] Analyst prompt instructs the LLM to output strict JSON with at minimum `severity`, `root_cause_hypothesis`, `recommended_action`
- [ ] Planner prompt lists the exact same task types as `tasks.yaml`
- [ ] `solutions/<name>/tasks.yaml` created with `task_types`, `task_descriptions`, and `task_payloads`
- [ ] `CREATE_MR` and `PLAN_TASK` included in `task_types` (universally required)
- [ ] Backend starts without errors: `make run PROJECT=<name>`
- [ ] `GET /config/project` returns correct metadata and task types
- [ ] `POST /analyze` returns valid JSON with expected severity field
- [ ] Solution appears in `GET /config/projects`
- [ ] Web UI loads and shows correct page titles and input labels

---

## Common Mistakes

**Planner generates invalid task types**

If the PlannerAgent generates task types not in your `tasks.yaml`, the task will be rejected when submitted to the queue. Fix: ensure the planner system prompt in `prompts.yaml` lists exactly the same task types as `tasks.yaml`.

**ChromaDB collection name collision**

If two projects share the same `collection_name`, their episodic memories will be mixed. Always use a project-specific name such as `<projectname>_knowledge`.

**Analyst returns non-JSON output**

The analyst system prompt must contain the instruction: "Do not output markdown, prose, or any text outside the JSON object." Without this, Gemini CLI sometimes wraps output in markdown fences. The agent has a JSON parse fallback but a clean JSON prompt is always better.

**UI labels not adapting**

The web UI fetches project labels from `GET /config/project` on load. If you add a new project and the labels do not change in the UI, check: (1) the backend is running with the new project, (2) `ui_labels` keys in `project.yaml` match exactly what the frontend reads (see `web/src/` for the exact key names used).
