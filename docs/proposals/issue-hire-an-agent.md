# Issue: Hire an Agent — JD-to-Agent Wizard

**Labels:** `enhancement`, `onboarding`, `agents`, `framework-core`
**Milestone:** Intelligence Layer v1
**Scope:** `sage` (framework improvement)
**Related:** Conversational Onboarding (Issue #4), HITL Design Pattern (Issue #5)

---

## Summary

Let users "hire" a new AI agent the same way they'd hire a human: write a job description
(or paste a reference JD), and SAGE structures it into a fully configured agent role —
system prompt, tool access, task types, eval suite, and a place on the team.

The metaphor is intentional. Teams already know how to write JDs. A Senior QA Engineer JD
contains everything needed to define a QA agent: responsibilities, required skills, what
good output looks like, escalation criteria. SAGE just reads it and builds the config.

---

## Problem

Adding a new agent role today requires:
1. Understanding the `prompts.yaml` schema
2. Writing a well-structured system prompt from scratch
3. Knowing which task types to add to `tasks.yaml`
4. Understanding how the UniversalAgent dispatches roles
5. Manually writing an eval suite to verify the agent works

Most users do not want to become SAGE experts to add a new capability. They want to describe
what they need and have it work. The JD metaphor gives them a mental model they already have.

---

## User Flow

### Entry points

Three ways to trigger the wizard:

1. **Web UI** — "Agents" page → **+ Hire New Agent** button
2. **API** — `POST /agents/hire` with a JD or description
3. **Onboarding wizard** — at the end of Path B ("Would you like to add specialist roles to
   your team?")

### The wizard

```
┌──────────────────────────────────────────────────────────────────┐
│  HIRE A NEW AGENT                                                │
│                                                                  │
│  How would you like to define this role?                         │
│                                                                  │
│  ┌─────────────────────┐  ┌─────────────────────┐               │
│  │  Paste a Job        │  │  Describe what you  │               │
│  │  Description        │  │  need in plain      │               │
│  │                     │  │  language           │               │
│  │  Use an existing    │  │                     │               │
│  │  JD from your HR    │  │  "I need someone    │               │
│  │  system or a        │  │  who reviews        │               │
│  │  reference role     │  │  security issues    │               │
│  │  from LinkedIn etc  │  │  in our PRs"        │               │
│  └─────────────────────┘  └─────────────────────┘               │
└──────────────────────────────────────────────────────────────────┘
```

---

## Path A — Paste a Job Description

The user pastes any JD — their own, a LinkedIn post, a reference from another company.
SAGE reads it as a metaprompt and extracts the agent definition.

### Example input

```
Senior QA Engineer — MedTech Platform

Responsibilities:
- Own end-to-end testing strategy for our clinical web application and embedded firmware
- Review code changes for test coverage gaps and regression risks
- Triage incoming defect reports, classify severity, and escalate safety-relevant issues
- Maintain IEC 62304 test documentation and ensure traceability to requirements
- Coordinate with the DevOps team on CI/CD pipeline failures

Required skills:
- 5+ years in QA for regulated medical devices
- Deep knowledge of IEC 62304, ISO 14971, FDA 21 CFR Part 11
- Experience with unit testing, integration testing, and system validation
- Strong knowledge of Python, pytest, and CI/CD tools
```

### What SAGE extracts

SAGE reads the JD as a metaprompt and identifies:

| JD element | Extracted to |
|-----------|-------------|
| "Own end-to-end testing strategy" | Role description in `prompts.yaml` |
| "Triage defect reports, classify severity" | Maps to `ANALYZE_DEFECT` task type |
| "Review code for test coverage gaps" | Maps to `REVIEW_CODE` task type with QA lens |
| "Escalate safety-relevant issues" | `safety_relevant` field in output schema |
| "IEC 62304, ISO 14971" | `compliance_standards` in analyst prompt context |
| "5+ years in QA for medical devices" | Persona in system prompt: "You are a Senior QA Engineer with 5+ years in regulated medical device software..." |
| "Coordinate with DevOps on CI/CD" | `ANALYZE_CI_FAILURE` task type |

### Structured output

SAGE presents its understanding before generating anything:

```
I read the JD. Here's how I've structured this agent:

Role key:      quality_engineer
Display name:  Senior QA Engineer
Persona:       "You are a Senior QA Engineer specialising in regulated medical device
               software (IEC 62304 / ISO 14971 / FDA 21 CFR Part 11)..."

This agent will handle:
  ANALYZE_DEFECT       — triage defect reports with severity + safety_relevant flag
  REVIEW_CODE (QA)     — review code for test coverage gaps and regression risks
  ANALYZE_CI_FAILURE   — diagnose CI/CD pipeline failures

Output always includes:
  severity             RED | AMBER | GREEN
  safety_relevant      bool — true if the issue could affect patient safety
  iec62304_reference   string — relevant IEC 62304 clause if applicable
  recommended_action   string

Does this match what you had in mind?
[ Looks good ] [ Edit ] [ Start over ]
```

---

## Path B — Plain Language Description

For users who do not have a JD. One focused question at a time.

```
SAGE: What should this agent be an expert in?
      (e.g. "security vulnerabilities in our API", "mobile app performance",
      "data pipeline failures")

User: Security vulnerabilities in our Node.js API — OWASP top 10, dependency
      issues, that kind of thing.

SAGE: Got it — a security reviewer. What should it look at?
      [ Pull requests / code diffs ]
      [ Deployed API responses / logs ]
      [ Dependency audit reports ]
      [ All of the above ]

User: Mainly pull requests and dependency reports.

SAGE: What does "good" look like? What should it always flag, and what's
      outside its scope?

User: Always flag: SQL injection, hardcoded secrets, outdated deps with CVEs.
      Out of scope: performance, styling, business logic.

SAGE: One more — how should it communicate findings? (this shapes the output format)
      [ List of issues with severity and fix suggestion ]
      [ Pass/fail with a summary ]
      [ Detailed narrative report ]

User: List of issues with severity and fix suggestion.

SAGE: Here's your Security Reviewer agent:

      Role key:     security_reviewer
      Task types:   REVIEW_CODE_SECURITY, ANALYZE_DEPENDENCY_REPORT
      Always flags: SQL injection, hardcoded secrets, CVEs in deps
      Output:       [{issue, severity, file, line, fix_suggestion}]

      [ Preview full YAML ] [ Looks good, add to team ] [ Edit ]
```

---

## The Metaprompt Architecture

The JD → agent conversion is itself an LLM call with a carefully structured metaprompt.
This is the core technical piece.

```python
METAPROMPT = """
You are an AI agent architect. Your job is to read a job description or role description
and convert it into a precise SAGE agent configuration.

A SAGE agent has:
1. A role_key (snake_case identifier)
2. A display name
3. A system_prompt (the LLM's persona and instructions)
4. task_types (list of task type names this agent handles)
5. An output_schema (the JSON fields this agent always returns)
6. An eval_case (a single test case to verify the agent works)

Rules for the system_prompt:
- Open with: "You are a [seniority] [role title] with expertise in [domain]."
- List 3-5 specific responsibilities drawn from the JD
- Define the output JSON schema explicitly: "Always return strict JSON with keys: ..."
- Include domain-specific quality criteria from the JD's "required skills" section
- End with: "Do not output markdown, prose, or any text outside the JSON object."

Rules for task_types:
- Name them in SCREAMING_SNAKE_CASE
- Each maps to one specific type of input (a log, a diff, a report, a metric)
- Maximum 5 task types per role
- Always include a description string

Rules for output_schema:
- Always include: severity (RED|AMBER|GREEN), summary (string), recommended_action (string)
- Add domain-specific fields based on the JD (e.g. safety_relevant, cve_ids, test_coverage_pct)

Given this job description or role description:
{jd_or_description}

And this solution context:
{solution_context}

Return a JSON object with keys: role_key, name, description, system_prompt,
task_types (list of {name, description}), output_schema (dict), eval_case ({input, expected_keywords}).
"""
```

---

## What Gets Created

When the user approves, SAGE creates (via a `STATEFUL` HITL proposal — see Issue #5):

### 1. Role added to `prompts.yaml`

```yaml
roles:
  quality_engineer:                          # ← new role appended here
    name: "Senior QA Engineer"
    description: "Owns test strategy, defect triage, and IEC 62304 traceability"
    system_prompt: |
      You are a Senior QA Engineer specialising in regulated medical device software
      with deep expertise in IEC 62304, ISO 14971, and FDA 21 CFR Part 11.

      When given a defect report, code diff, or CI failure:
      1. Classify severity using the RED/AMBER/GREEN scale, with RED reserved for
         issues that could affect patient safety
      2. Identify the root cause with specific reference to source files or test gaps
      3. Note the relevant IEC 62304 clause if applicable (e.g. §5.5.2 unit testing)
      4. Recommend a specific next action for the engineering team

      Always output strict JSON with keys:
        severity            : "RED" | "AMBER" | "GREEN"
        safety_relevant     : bool
        iec62304_reference  : string or null
        root_cause          : string
        recommended_action  : string
        test_gaps           : list of strings

      Do not output markdown, prose, or any text outside the JSON object.
```

### 2. Task types added to `tasks.yaml`

```yaml
task_types:
  - ANALYZE_DEFECT          # ← new
  - REVIEW_CODE_QA          # ← new

task_descriptions:
  ANALYZE_DEFECT:   "Triage a defect report with severity, safety flag, and IEC 62304 ref"
  REVIEW_CODE_QA:   "Review a code diff for test coverage gaps and regression risks"

task_payloads:
  ANALYZE_DEFECT:
    defect_text:     "string — defect description, stack trace, or bug report"
    component:       "string — affected component or module (optional)"
    reporter:        "string — who reported it (optional)"
  REVIEW_CODE_QA:
    diff_text:       "string — git diff or code snippet to review"
    test_files:      "string — existing test files for context (optional)"
```

### 3. Eval case added to `evals/`

```yaml
# solutions/medtech_team/evals/quality_engineer.yaml
name: "QA Agent — defect triage"
description: "Verify the QA agent classifies defects correctly"
cases:
  - id: "safety_critical_001"
    role: "quality_engineer"
    input: "Watchdog timer not resetting — device may lock up during patient monitoring"
    expected_keywords: ["RED", "safety_relevant", "watchdog", "IEC 62304"]
    max_response_length: 2000
```

### 4. Planner prompt updated

The planner prompt in `prompts.yaml` has its `VALID_TASK_TYPES` list updated to include the new task types, keeping planner and tasks.yaml in sync automatically.

---

## Agent "Employment" Lifecycle

Extending the hiring metaphor gives users a clear mental model for managing agents:

| Action | API | Description |
|--------|-----|-------------|
| **Hire** | `POST /agents/hire` | Create agent from JD or description |
| **Brief** | `POST /agents/{key}/brief` | Update system prompt with new instructions |
| **Review** | `GET /agents/{key}/performance` | Eval scores, approval rates, rejection patterns |
| **Reassign** | `PATCH /agents/{key}/tasks` | Change which task types the agent handles |
| **Promote** | `POST /agents/{key}/promote` | Make this agent the default for a task type |
| **Let go** | `DELETE /agents/{key}` | Remove agent (DESTRUCTIVE proposal, HITL gated) |

All mutating actions go through the HITL `ProposalStore` (Issue #5).

The "Review" endpoint surfaces data the system already collects:
- Avg eval score over last 30 days
- Human approval rate (approvals / total proposals)
- Top rejection reasons (from feedback text, clustered by SLM)
- Task type breakdown

---

## Integration with Existing Features

**Onboarding (Issue #4):** At the end of Path B — "Would you like to add specialist roles?
I can help you hire a security reviewer, a performance analyst, or any other expert your
team needs."

**HITL (Issue #5):** All writes (prompts.yaml, tasks.yaml, evals/) go through `STATEFUL`
proposals. The user sees a diff of exactly what will change before approving.

**Eval runner (Phase 9):** Every hired agent automatically gets an eval case. Run it with
`POST /eval/run {"suite": "quality_engineer"}` immediately after hiring to verify the agent
produces sensible output.

**SAGE Framework SLM (Issue #1):** The SLM can pre-screen JD text — checking if it's
actually a JD vs. a random paste — before sending to the full LLM. Saves a cloud call on
bad inputs.

---

## Files Added / Modified

| File | Change |
|------|--------|
| `src/core/agent_factory.py` | New — `AgentFactory`, metaprompt, JD → role config conversion |
| `src/interface/api.py` | Add `POST /agents/hire`, `GET /agents/{key}/performance`, lifecycle endpoints |
| `web/src/pages/Agents.tsx` | Add "Hire New Agent" button + wizard modal |
| `web/src/components/agents/HireWizard.tsx` | New — two-path wizard (JD paste vs. plain language) |
| `web/src/components/agents/AgentCard.tsx` | Add performance stats, promote/let-go actions |
| `tests/test_agent_factory.py` | New — metaprompt extraction unit tests |

---

## Implementation Plan

### Step 1 — AgentFactory + metaprompt
- `src/core/agent_factory.py`: `jd_to_role_config(jd_text, solution_context) -> RoleConfig`
- Metaprompt defined as a constant, structured output parsed by `json_extractor`
- Unit tests with fixture JDs from different domains

### Step 2 — API endpoints
- `POST /agents/hire` (both paths — JD text or conversation)
- Returns HITL proposal (STATEFUL) — user must approve before files are written
- `POST /approve/{trace_id}` executor writes prompts.yaml, tasks.yaml, eval file

### Step 3 — Plain language conversation path
- Reuse `OnboardingSession` state machine from Issue #4
- 4–6 focused questions, builds `RoleConfig` incrementally

### Step 4 — Web UI wizard
- `HireWizard.tsx`: two-path modal, live preview of generated YAML
- `AgentCard.tsx`: add performance stats panel
- Agents page: hire button, agent lifecycle actions

### Step 5 — Agent performance endpoint
- `GET /agents/{key}/performance`: query audit log + eval history
- Surface in UI as a simple stats card per agent

---

## Acceptance Criteria

- [ ] Pasting a 200-word JD produces a valid `RoleConfig` with all required fields
- [ ] Generated system prompt always includes persona, responsibilities, strict JSON instruction
- [ ] Generated task types are added to both `prompts.yaml` and `tasks.yaml` atomically (both or neither)
- [ ] Planner prompt's VALID_TASK_TYPES is updated automatically
- [ ] An eval case is created for every hired agent
- [ ] All file writes go through a HITL STATEFUL proposal (diff shown before approval)
- [ ] `DELETE /agents/{key}` goes through a DESTRUCTIVE proposal
- [ ] `GET /agents/{key}/performance` returns approval rate and eval scores
- [ ] All existing tests pass (`make test`)
