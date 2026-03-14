# Issue: Conversational Onboarding — Two-Path Setup Wizard

**Labels:** `enhancement`, `onboarding`, `ux`, `framework-core`
**Milestone:** Intelligence Layer v1
**Scope:** `sage` (framework improvement)
**Replaces:** The current single-shot `POST /onboarding/generate` endpoint (which stays as a
programmatic fallback but is no longer the primary user path)

---

## Problem

The current onboarding requires users to already know:
- What a "solution" is
- What task types, roles, and prompts mean
- What integrations they want
- Enough about SAGE to write a coherent description

This is wrong. The onboarding is the first thing a new user sees. It should do the work of
figuring SAGE out — not require the user to have already figured it out.

There are also two very different users arriving at onboarding:

| User | Situation | What they need |
|------|-----------|---------------|
| Builder A | Has an existing project, codebase, team, tools | Point SAGE at it, let it read and configure itself |
| Builder B | Has an idea, maybe a side project, starting fresh | Explore the concept with a guide, build the config together |

Both need a fundamentally different experience. Neither is served by "paste a description, get YAML".

---

## Proposed Solution

Replace the single-shot onboarding with a **two-path conversational wizard** available both in
the web UI (new `/onboarding` page) and via a stateful API session.

```
Landing: "How would you like to set up SAGE?"
         │
    ┌────┴──────────────────────────────────────────────┐
    │                                                    │
 [Path A]                                            [Path B]
 "I have an existing project"                        "I'm starting fresh"
 Analyze my codebase/repo and configure              Let's explore the idea together
 SAGE for what it finds.                             and build my config step by step.
```

---

## Path A — "Analyze My Project"

The user points SAGE at their existing work. SAGE reads it, understands it, and configures itself.

### Step 1: Point to the project

The user provides one or more of:

```
[ ] GitHub / GitLab repo URL        https://github.com/myteam/myapp
[ ] Local directory path            C:/projects/myapp
[ ] Paste key files                 README, package.json, CI config
[ ] Describe in one paragraph       "We build a Flutter app with a Node.js backend..."
```

Multiple sources can be combined — the more context, the better the result.

### Step 2: SAGE reads and understands

SAGE analyzes the provided sources and extracts:

| What it reads | What it learns |
|--------------|----------------|
| README.md | Project purpose, tech stack, team description |
| package.json / requirements.txt / pubspec.yaml | Languages, frameworks, dependencies |
| .gitlab-ci.yml / .github/workflows/ | CI/CD system, test commands, deployment targets |
| Existing issues / MR titles (if GitLab/GitHub URL given) | Common problem types, terminology |
| Folder structure | Architecture layers (frontend/backend/firmware/infra) |
| Error log samples (if pasted) | What kinds of events SAGE will be analyzing |

SAGE then presents its understanding for confirmation:

```
Here's what I found:

Project:     MyApp — Flutter mobile app + Node.js API
Stack:       Flutter 3.x (iOS/Android), Node.js 20, PostgreSQL, Docker
CI/CD:       GitHub Actions — test, build, deploy to AWS
Team size:   ~5 engineers (inferred from commit authors)
Key risks:   Crash logs, API errors, app store reviews, CI pipeline failures

Does this look right? Anything I missed?
[ Edit ] [ Looks good, continue ]
```

### Step 3: Draft YAML presented inline

SAGE generates a first draft of all three YAML files and shows them in a split view:
- Left: the evidence it used ("I added ANALYZE_CRASH because I saw crash_reporter in package.json")
- Right: the YAML draft, editable inline

Each section has an explanation:
```yaml
# SAGE found 3 types of events in your GitHub issues — mapped to these task types:
task_types:
  - ANALYZE_CRASH       # from: crash_reporter, Firebase Crashlytics in package.json
  - ANALYZE_API_ERROR   # from: error handling patterns in your CI logs
  - ANALYZE_CI_FAILURE  # from: .github/workflows/ci.yml failure cases
  - REVIEW_CODE         # always useful for any team
  - CREATE_MR           # for GitHub integration
  - PLAN_TASK           # for PlannerAgent
```

User can click any section to edit it inline. Changes regenerate downstream sections that depend on it (e.g. changing task types updates the planner prompt automatically).

### Step 4: Permissions wizard

SAGE shows only the permissions it actually needs, based on what it found:

```
To work with your project, SAGE needs these permissions.
Check off what you want to enable:

[x] GitHub — read issues, review PRs, create PRs
    → GITHUB_TOKEN: Personal Access Token with repo scope
    → Get one at: github.com/settings/tokens

[ ] Slack — send proposals for approval, receive approve/reject
    → SLACK_BOT_TOKEN + SLACK_SIGNING_SECRET
    → Setup: create a Slack app at api.slack.com/apps

[ ] AWS CloudWatch (detected in your CI config)
    → Forward alerts to SAGE via n8n — see docs/INTEGRATIONS.md#n8n

Everything below is optional. Skip for now, add later:
[ ] PagerDuty alerts → n8n
[ ] Datadog metrics  → n8n

[ Skip all — I'll add credentials later ]  [ Save .env and continue ]
```

This is a guided `.env` builder. It only asks about integrations relevant to what SAGE found.
It does not show Teams, Spira, J-Link, or serial port if there's no evidence the user needs them.

### Step 5: Verify and launch

```
Your SAGE solution 'myapp' is ready.

solutions/myapp/
  project.yaml   ✓ generated
  prompts.yaml   ✓ generated
  tasks.yaml     ✓ generated
.env             ✓ GITHUB_TOKEN saved

Test it now:
  make run PROJECT=myapp
  curl http://localhost:8000/config/project

Or send a test analysis:
  POST /analyze {"input": "NullPointerException in CheckoutService:42"}
```

---

## Path B — "Start Fresh"

The user has an idea but no existing codebase. SAGE acts as a guide, exploring the concept
through dialogue and building the config incrementally.

### Conversation flow

SAGE asks one focused question at a time. No walls of options. No long forms.
Each answer narrows the next question. The YAML builds up behind the scenes and is shown
as a live preview that updates after each answer.

```
SAGE: Hi! What are you building? Tell me in a sentence or two — it doesn't need to be
      complete. We'll figure the rest out together.

User: I'm building a fitness tracking app for personal trainers to manage their clients.

SAGE: Got it — a B2B fitness platform. Who's the main team working on it?
      [ Just me ] [ Small team (2-5) ] [ Bigger team ]

User: Small team, 3 engineers.

SAGE: What's the tech stack? (Pick what fits, or type your own)
      [ React / Node.js ] [ Flutter ] [ Python / Django ] [ Other: ___ ]

User: React frontend, Node.js API, PostgreSQL.

SAGE: What's the biggest pain right now? What would you most want SAGE to help with?
      [ Catching and triaging API errors ] [ Reviewing pull requests ]
      [ Monitoring CI/CD pipelines ] [ All of the above ] [ Something else: ___ ]

User: Mostly API errors and PR reviews.

SAGE: Do you use GitHub or GitLab?
      [ GitHub ] [ GitLab ] [ Neither yet ]

User: GitHub.

SAGE: Great. Here's a first draft of your solution config — I've set up:
      - An analyst for Node.js API errors with relevant severity levels
      - A developer agent for GitHub PR reviews
      - A planner that can coordinate multi-step investigations

      [shows live YAML preview]

      One thing I'm not sure about: your domain is fitness/health — do you handle
      any patient or health data that might need HIPAA compliance?
      [ Yes ] [ No ] [ Not sure ]

User: No, it's for trainers not patients, no PHI.

SAGE: Perfect — I'll keep compliance_standards empty for now (you can add SOC 2 later
      when you're ready).

      Now for integrations — the minimum to get started is a GitHub token.
      Want to set that up now, or skip and add credentials later?
      [ Set up GitHub token now ] [ Skip for now ]
```

### Principles for Path B

- **One question at a time.** Never show more than one decision at once.
- **Multiple choice by default, free text always available.** Reduces friction.
- **Show the YAML building in real time.** User sees the config forming alongside the conversation. Demystifies YAML.
- **Explain every choice.** "I added ANALYZE_API_ERROR because you mentioned API errors as your main pain. Rename it to anything that makes sense to your team."
- **Allow backtracking.** Every step can be edited. Going back regenerates downstream sections.
- **No dead ends.** If the user skips a question, SAGE picks a sensible default and moves on.
- **Save progress.** The conversation state is persisted so the user can close the browser and resume.

---

## Technical Design

### Onboarding Session (stateful)

A new `OnboardingSession` model tracks conversation state:

```python
class OnboardingSession(BaseModel):
    session_id: str                    # UUID
    path: Literal["analyze", "fresh"]  # which path
    step: int                          # current step index
    messages: list[dict]               # full conversation history
    draft_yaml: dict                   # {project: ..., prompts: ..., tasks: ...}
    sources_analyzed: list[str]        # URLs/paths analyzed (Path A)
    permissions_granted: list[str]     # integrations confirmed by user
    solution_name: Optional[str]       # set when user names the solution
    complete: bool                     # True when all steps done
```

Sessions are persisted in SQLite (`onboarding_sessions` table) so they survive server restarts.

### New API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/onboarding/session` | Start a new onboarding session, choose path |
| `GET` | `/onboarding/session/{id}` | Get current session state + next question |
| `POST` | `/onboarding/session/{id}/reply` | Submit user's answer, get next question + updated YAML |
| `POST` | `/onboarding/session/{id}/analyze` | Path A: submit repo URL or file content for analysis |
| `POST` | `/onboarding/session/{id}/confirm` | Confirm draft YAML and create solution files |
| `GET` | `/onboarding/session/{id}/yaml` | Get current draft YAML (for live preview) |
| `POST` | `/onboarding/session/{id}/edit-yaml` | Inline edit of draft YAML section |
| `POST` | `/onboarding/generate` | (kept) Single-shot generation — programmatic fallback |

### Repo Analysis (`src/core/onboarding_analyzer.py`)

For Path A, a new `OnboardingAnalyzer` class:

```python
class OnboardingAnalyzer:
    def analyze_github_repo(self, url: str) -> ProjectSignals: ...
    def analyze_local_path(self, path: str) -> ProjectSignals: ...
    def analyze_text(self, text: str) -> ProjectSignals: ...

class ProjectSignals(BaseModel):
    detected_stack: list[str]          # ["Flutter", "Node.js", "PostgreSQL"]
    detected_ci: Optional[str]         # "GitHub Actions"
    detected_integrations: list[str]   # ["github", "slack"] (from .env or CI config)
    detected_domains: list[str]        # ["mobile", "api", "database"]
    compliance_hints: list[str]        # ["HIPAA"] if health keywords found
    suggested_task_types: list[str]    # inferred from stack + issues
    suggested_roles: list[str]         # inferred from team signals
    evidence: dict[str, str]           # field → why SAGE inferred it
```

For GitHub/GitLab URLs: fetch README, package.json/requirements.txt, CI config via the public API (no auth needed for public repos; use stored token for private repos).

For local paths: walk the directory, read key files (README, manifests, CI configs). Never read source code files directly — only manifests, configs, and documentation.

### Web UI (`web/src/pages/Onboarding.tsx`)

A dedicated `/onboarding` route with:
- **Path selector** — two large cards, clear descriptions
- **Path A**: file/URL input + analysis loading state + evidence + YAML split view
- **Path B**: chat-style interface, message history, live YAML preview sidebar
- **Permissions wizard**: checkbox list, inline `.env` instructions, "test this connection" buttons
- **Final summary**: file list, launch command, copy button

The onboarding page is accessible even before any solution is loaded (special case in the router).

---

## Files Added / Modified

| File | Change |
|------|--------|
| `src/core/onboarding.py` | Add `OnboardingSession`, `OnboardingConversation`, session persistence |
| `src/core/onboarding_analyzer.py` | New — `OnboardingAnalyzer`, `ProjectSignals` |
| `src/interface/api.py` | Add all new `/onboarding/session/*` endpoints |
| `data/audit_log.db` | New `onboarding_sessions` table |
| `web/src/pages/Onboarding.tsx` | New — full onboarding UI (Path A + Path B) |
| `web/src/App.tsx` | Wire `/onboarding` route |
| `web/src/components/layout/Sidebar.tsx` | Add "Setup Wizard" link (shown when no solution loaded, or always) |
| `tests/test_onboarding_v2.py` | New — unit + integration tests for both paths |

---

## Implementation Plan

### Step 1 — Session model + basic API skeleton
- `OnboardingSession` model, SQLite persistence
- `POST /onboarding/session`, `GET /onboarding/session/{id}`, `POST /onboarding/session/{id}/reply`
- Path B conversation only (no repo analysis yet)
- Questions hardcoded as a state machine (10 steps)
- Draft YAML updates after each answer via existing `onboarding.py` LLM call

### Step 2 — Path B web UI
- Chat interface in React
- Live YAML preview sidebar (syntax highlighted, editable)
- Progress indicator
- Session resume from localStorage

### Step 3 — Permissions wizard
- `POST /onboarding/session/{id}/confirm`
- Integration checklist, `.env` builder
- "Test connection" buttons per integration

### Step 4 — Path A: repo analysis
- `OnboardingAnalyzer` for GitHub URLs (public repos, no auth)
- Local directory analysis
- Evidence display in split view

### Step 5 — Path A web UI + polish
- File/URL input with drag-and-drop
- Analysis loading state with "found X signals" feedback
- YAML split view with evidence annotations

---

## Acceptance Criteria

- [ ] Path B completes in ≤ 12 conversational turns for a typical project
- [ ] Path A correctly identifies stack and suggests task types for a public GitHub repo (test with starter, meditation_app, and one external repo)
- [ ] Permissions wizard only shows integrations relevant to what was detected
- [ ] Generated YAML passes all checks from `docs/ADDING_A_PROJECT.md` Checklist
- [ ] Session survives server restart (SQLite persistence)
- [ ] All existing onboarding tests still pass; `POST /onboarding/generate` unchanged
- [ ] Web UI works on mobile viewport (responsive)

---

## Open Questions

1. **Private repo access**: For Path A with a private GitLab/GitHub repo, should the user
   provide a token upfront (before SAGE knows it needs it)? Or should SAGE first try
   without auth, hit a 403, and then ask?
   Recommendation: try without auth first, ask for token only if needed.

2. **Conversation LLM**: Should Path B use the SAGE Framework SLM (Issue #1) for the
   conversational turns, or the full cloud LLM?
   Recommendation: full LLM for quality; SLM integration can be added later as an
   optimization once Issue #1 is built.

3. **Minimum viable**: Is Path A (repo analysis) a blocker for the first release, or can
   v1 ship with Path B only?
   Recommendation: ship Path B first (pure conversation, no repo analysis). Path A is Step 4+
   and can be a follow-up PR.
