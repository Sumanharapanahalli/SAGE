# SAGE Framework — Adding a New Solution

> A SAGE solution is three YAML files. No Python. No code changes. The framework reads your YAML and agents adapt to your domain automatically.

---

## Overview

Every solution lives in its own folder under `solutions/`:

```
solutions/
└── your_project/
    ├── project.yaml    What your project IS — identity, modules, standards, integrations
    ├── prompts.yaml    How agents THINK — LLM system prompts per role
    └── tasks.yaml      What agents CAN DO — task type registry and payload schemas
```

Run it with:
```bash
make run PROJECT=your_project
```

That is all. The framework loads your three files, agents adapt to your domain, and the web UI reflects your configuration.

---

## Five Ways to Create a Solution

### Option 1 — Onboarding wizard (fastest, recommended)

Describe your project in plain language. The LLM generates all three YAML files:

```bash
curl -X POST http://localhost:8000/onboarding/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "We build a SaaS invoicing platform in React and Node.js. We need to triage API errors, review pull requests, and monitor our AWS infrastructure.",
    "solution_name": "invoicing_saas",
    "compliance_standards": ["SOC 2 Type II", "GDPR"],
    "integrations": ["github", "slack"]
  }'
```

Review the generated YAML at `solutions/invoicing_saas/`, edit anything you want, then:
```bash
make run PROJECT=invoicing_saas
```

### Option 2 — Conversational onboarding (web UI)

Open `/onboarding` in the web UI. Two paths:

- **Path A** — Point to an existing local repo. The LLM analyzes your stack, CI config, and compliance hints, then generates all 3 YAML files.
- **Path B** — Guided Q&A wizard. Answer questions about your domain, team, and compliance needs.

### Option 3 — Scan existing folder

```bash
curl -X POST http://localhost:8000/onboarding/scan-folder \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/your/project", "solution_name": "my_project"}'
```

The LLM analyzes the folder structure and generates YAML tailored to the detected stack.

### Option 4 — Copy the starter template

```bash
cp -r solutions/starter solutions/your_project
# Edit the three files, then:
make run PROJECT=your_project
```

### Option 5 — Write from scratch

Follow the field-by-field guide below.

---

## The Three Files Explained

### `project.yaml` — Project Identity

Defines what your project is and which framework features are active.

**All fields:**

```yaml
# Required
name: "Your Project Name"        # Shown in web UI and API responses
version: "1.0.0"                 # Semantic version
domain: "your-domain"            # Short slug (e.g. "saas", "iot", "fintech")
description: >
  One paragraph describing your project and what SAGE does for it.

# Which web UI pages are visible
active_modules:
  - dashboard      # Overview and quick actions
  - analyst        # Log/event analysis
  - developer      # Code review and MR creation
  - monitor        # Real-time event monitoring
  - audit          # Decision history and audit trail
  - improvements   # Backlog and framework ideas
  - agents         # Universal agent roles (custom personas)
  - llm            # LLM provider switcher
  - settings       # Solution settings
  - yaml-editor    # Live YAML editing

# Compliance standards (shown in UI and /config/project — cosmetic, not enforced)
compliance_standards:
  - "SOC 2 Type II"
  - "GDPR"
  # Any string is valid — ISO 27001, HIPAA, PCI DSS, etc.

# Integrations your solution uses (drives tool loading — only list what you have configured)
integrations:
  - gitlab         # or github
  - slack
  # Options: gitlab, github, teams, slack, jira, confluence, metabase, spira, database

# Per-project settings override base config/config.yaml
settings:
  memory:
    collection_name: "your_project_knowledge"   # Must be unique across all solutions
  system:
    max_concurrent_tasks: 1                      # Keep at 1 for audit trail compliance

# Optional: override web UI labels to match your domain language
ui_labels:
  analyst_page_title:   "Error Analyzer"
  analyst_input_label:  "Paste a log entry, error, or event"
  developer_page_title: "Code Reviewer"
  monitor_page_title:   "System Monitor"
  dashboard_subtitle:   "Your Project Health"

# Optional: dashboard layout
dashboard:
  badge_color: "bg-blue-100 text-blue-800"
  context_color: "border-blue-200 bg-blue-50"
  context_items:
    - label: "Stack"
      description: "Your technology stack description"
    - label: "Key Signals"
      description: "What you monitor and analyze"
  quick_actions:
    - { label: "Analyze Error",  route: "/analyst",   description: "Triage a log or error" }
    - { label: "Review Code",    route: "/developer", description: "AI code review" }
    - { label: "Audit Trail",    route: "/audit",     description: "Decision history" }
```

---

### `prompts.yaml` — How Agents Think

This file gives each agent domain expertise. The quality of this file directly determines the quality of agent output. Be specific about your stack and domain.

**Structure:**

```yaml
analyst:            # Triages logs, errors, events
developer:          # Reviews code, creates MRs
planner:            # Decomposes requests into tasks
monitor:            # Classifies real-time events
roles:              # Custom expert personas (optional, as many as you want)
```

#### The analyst prompt

The most important prompt. Give it domain expertise and tell it exactly what JSON to return:

```yaml
analyst:
  system_prompt: |
    You are a Senior [Your Domain] Engineer with expertise in [specific skills].
    Analyze the provided [log type / error type / signal type] carefully.
    Use the provided CONTEXT from past incidents — especially human corrections.

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
    RED:     "Critical — immediate action required"
    AMBER:   "Warning — investigate within 4 hours"
    GREEN:   "Informational — no immediate action"
    UNKNOWN: "Unable to determine — escalate"
```

You can add domain-specific output fields. Any keys your analyst prompt returns will be passed through to the API response and the audit log automatically.

#### The developer prompt

```yaml
developer:
  review_system_prompt: |
    You are a Senior [Domain] Engineer performing a code review.
    Review the provided diff for:
      - [Domain-specific concern 1]
      - [Domain-specific concern 2]
      - Security, performance, and maintainability
    Return STRICT JSON with keys:
      summary     : string
      issues      : list of { file, line, severity, description, suggestion }
      suggestions : list of string
      approved    : bool

  mr_create_system_prompt: |
    You are a Senior [Domain] Engineer creating a merge request.
    Given the issue description, return STRICT JSON with keys:
      title, description, source_branch, target_branch
```

#### The planner prompt

The planner must list exactly the same task types as your `tasks.yaml`:

```yaml
planner:
  system_prompt: |
    You are a Planning Agent for [project name].
    Decompose requests into atomic tasks using only these VALID_TASK_TYPES:
      YOUR_TASK_TYPE_1  - What this task does
      YOUR_TASK_TYPE_2  - What this task does
      CREATE_MR         - Create a merge request
      PLAN_TASK         - Sub-planning step

    Each task MUST have: step, task_type, payload, description.
    Return a JSON array only.
```

#### The monitor prompt

```yaml
monitor:
  system_prompt: |
    You are a real-time monitor for [project name].
    Classify the following event. Return STRICT JSON with keys:
      severity            : "critical" | "high" | "medium" | "low" | "info"
      requires_action     : bool
      suggested_task_type : one of your task types or null
      summary             : string
```

#### Custom roles (the agents page)

Add as many specialist personas as your team needs:

```yaml
roles:
  senior_architect:
    name: "Senior Architect"
    description: "Architecture review, design decisions, and technical debt assessment"
    system_prompt: |
      You are a Senior Software Architect. When given a design question or code:
      1. Identify structural concerns and coupling issues
      2. Evaluate against SOLID principles and your team's architecture decisions
      3. Propose concrete improvements with trade-off analysis

      Always output structured JSON with:
        summary, analysis, recommendations, next_steps, severity, confidence

  security_reviewer:
    name: "Security Reviewer"
    description: "Threat modelling, vulnerability assessment, and secure coding review"
    system_prompt: |
      You are a Security Engineer. When given code or an architecture question:
      1. Apply OWASP Top 10 and threat modelling frameworks
      2. Identify specific vulnerability patterns in the code
      3. Propose fixes with priority ordering

      Always output structured JSON with:
        summary, analysis, recommendations, next_steps, severity, confidence
```

---

### `tasks.yaml` — What Agents Can Do

Defines every valid task type. The planner and task queue both validate against this list.

```yaml
task_types:
  - YOUR_TASK_TYPE_1
  - YOUR_TASK_TYPE_2
  - CREATE_MR          # Keep — required for GitLab/GitHub integration
  - PLAN_TASK          # Keep — required for PlannerAgent

task_descriptions:
  YOUR_TASK_TYPE_1: "Plain-English description of what this task does"
  YOUR_TASK_TYPE_2: "Plain-English description of what this task does"
  CREATE_MR:        "Create a merge/pull request from an issue or branch"
  PLAN_TASK:        "Decompose a natural-language request into subtasks"

# Payload schemas document what each task expects
# The framework uses these to validate planner output
task_payloads:
  YOUR_TASK_TYPE_1:
    required_field: "string — description"
    optional_field: "string — description (optional)"

  CREATE_MR:
    issue_description: "string — what to fix or implement"
    project_id:        "string — project ID (optional)"
    target_branch:     "string — e.g. 'main' (optional)"

  PLAN_TASK:
    description: "string — natural language task for the planner"
    priority:    "integer — 1-10 (default 5)"
```

---

## Complete Examples

17 example solutions are included in the repository. Key examples:

### Starter — Generic template

`solutions/starter/` — blank template for any domain. Copy this to start fresh.

```bash
make run PROJECT=starter
```

### Meditation App — Flutter mobile + Node.js backend

`solutions/meditation_app/` — consumer mobile app, GDPR compliance.

```bash
make run PROJECT=meditation_app
```

### Four in a Line — Casual game studio

`solutions/four_in_a_line/` — cross-platform casual game, GDPR and app store guidelines.

```bash
make run PROJECT=four_in_a_line
```

### Medical Device Software Team — Regulated engineering team

`solutions/medtech_team/` — embedded firmware + clinical web + DevOps, full ISO 13485 / IEC 62304 compliance.

```bash
make run PROJECT=medtech_team
```

### Automotive — Infotainment & telematics

`solutions/automotive/` — ISO 26262, UN ECE WP.29, ISO/SAE 21434 compliance.

```bash
make run PROJECT=automotive
```

### Additional Solutions

| Solution | Domain |
|---|---|
| `avionics` | Avionics SW (DO-178C, DO-254, ARP4754A) |
| `iot_medical` | IoT medical device (IEC 62304, ISO 14971) |
| `elder_fall_detection` | Fall detection IoT (HIPAA) |
| `fall_detection_firmware` | Fall detection firmware (IEC 62304) |
| `finmarkets` | Financial markets (SOC 2, PCI DSS) |
| `kappture` | Point-of-sale (PCI DSS) |
| `poseengine` | Pose estimation ML |
| `medtech_sample` | Medical device (IEC 62304, ISO 13485) |
| `tictac_arena` | Board game |
| `sol_a`, `sol_b` | Multi-solution org examples |

---

## Checklist Before Going Live

- [ ] `project.yaml` — name, domain, description, active_modules filled in
- [ ] `collection_name` in `settings.memory` is unique (no clash with other solutions)
- [ ] `prompts.yaml` — analyst prompt returns strict JSON with at minimum severity, root_cause_hypothesis, recommended_action
- [ ] Planner prompt lists exactly the same task types as `tasks.yaml`
- [ ] `tasks.yaml` — task_types, task_descriptions, task_payloads all complete
- [ ] `CREATE_MR` and `PLAN_TASK` included in task_types
- [ ] Backend starts cleanly: `make run PROJECT=your_project`
- [ ] `GET /config/project` returns your correct metadata and task types
- [ ] `POST /analyze` returns valid JSON with expected fields
- [ ] Solution appears in `GET /config/projects`
- [ ] Web UI loads with your custom labels

---

## Common Mistakes

**Planner generates unknown task types**

If the PlannerAgent returns a task type not in your `tasks.yaml`, the queue rejects it. Fix: ensure the `VALID_TASK_TYPES` list in your planner system prompt exactly matches `tasks.yaml`.

**ChromaDB collection name collision**

Two solutions sharing the same `collection_name` will mix their memories. Always use `<projectname>_knowledge` as the value.

**Analyst returns non-JSON**

The system prompt must say: "Do not output markdown, prose, or any text outside the JSON object." Without this, some LLM providers wrap output in markdown code fences.

**Web UI shows generic labels instead of your domain labels**

The UI fetches labels from `GET /config/project` at page load. Check that your `ui_labels` keys in `project.yaml` are spelled correctly and the backend is running your solution (not a cached previous one).

**Developer page shows an error**

The developer page requires GitLab or GitHub to be configured. If you are not using it, remove `developer` from `active_modules` in your `project.yaml`.
