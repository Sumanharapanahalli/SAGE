# SAGE[ai] — Intelligence Layer v1 Demo

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![GitHub Stars](https://img.shields.io/github/stars/Sumanharapanahalli/sage?style=social)](https://github.com/Sumanharapanahalli/sage)

### *Demo Script — March 2026 — Open Source Release*

---

## Slide 1 — The Vision

> **1 human. An AI agent team. A billion-dollar operation.**

- Every company function → an agent role
- Founder reviews only decisions that require human judgment
- The rest runs autonomously, with a complete audit trail

**Live today.** Open source under MIT. Zero mandatory API keys. Community-driven on GitHub.

---

## Slide 2 — What's New: Intelligence Layer v1

Five capabilities shipped in parallel, all live:

| # | Feature | What it unlocks |
|---|---|---|
| 1 | **HITL Approvals Inbox** | Every AI write action risk-ranked before execution |
| 2 | **SAGE Intelligence SLM** | On-device meta-agent — answers questions about itself |
| 3 | **Teacher-Student LLM** | Heavy model trains fast model — cost drops over time |
| 4 | **Conversational Onboarding** | Point at a repo → 3 YAML files generated automatically |
| 5 | **Domain Org Structure Chooser** | Pre-built regulated industry agent teams |

---

## Slide 3 — HITL Approvals Inbox

**Every AI write action goes through this inbox before executing.**

```
POST /knowledge/add  →  Proposal created (STATEFUL)  →  /approvals inbox
POST /llm/switch     →  Proposal created (EPHEMERAL)  →  /approvals inbox
DELETE /knowledge/entry →  Proposal (DESTRUCTIVE)    →  requires human note
```

**5 Risk Tiers:**

| Tier | Example | Expiry |
|---|---|---|
| INFORMATIONAL | Read-only agent query | 1 hour |
| EPHEMERAL | LLM provider switch | 8 hours |
| STATEFUL | Knowledge base edit | 7 days |
| EXTERNAL | GitLab MR creation | 14 days |
| DESTRUCTIVE | Drop table, delete agent | Never |

**Demo:** Open `/approvals` → see pending proposals → batch-approve low-risk items.

---

## Slide 4 — SAGE Intelligence SLM

**An on-device Gemma 3 1B answers questions about itself.**

- "Which endpoint do I use to switch LLM providers?" → returns API call
- Lints YAML before writing (no invalid configs committed)
- Classifies tasks: LIGHT → student SLM, HEAVY → teacher LLM
- Zero cloud calls for meta-operations

```bash
curl "http://localhost:8000/sage/ask?question=how+do+I+switch+llm+provider"
# → {"answer": "POST /llm/switch {\"provider\": \"ollama\", \"model\": \"llama3.2\"}", ...}
```

---

## Slide 5 — Teacher-Student Distillation

**Heavy model trains light model. Cost drops over time without quality loss.**

```
Input → Teacher (GPT-4/Claude Opus) → Rich analysis
                  ↓ score_confidence()
             confidence ≥ 0.85? → Save to JSONL
                  ↓
       Student (Gemma 3 / local SLM) trains on distillation examples
                  ↓
       Over time: student handles 80% of STANDARD tasks
```

Track drift: `GET /distillation/{solution}/stats`

---

## Slide 6 — Conversational Onboarding

**Two paths to a working agent solution:**

**Path A — Existing repo:**
```bash
curl -X POST http://localhost:8000/onboarding/session \
  -d '{"path": "A", "existing_path": "/home/user/my-project"}'
# LLM analyzes: stack, CI system, compliance hints
# Generates: project.yaml + prompts.yaml + tasks.yaml
# Confirms understanding before writing files
```

**Path B — Fresh Q&A:**
```bash
curl -X POST http://localhost:8000/onboarding/session -d '{"path": "B"}'
# Guided multi-turn conversation
# LLM asks about domain, team, compliance, integrations
# Same output: 3 YAML files ready to run
```

Also available in the web UI at `/onboarding`.

---

## Slide 7 — Domain Org Structure Chooser

**Pick your industry → get a pre-built agent team.**

| Industry | Roles | Standards |
|---|---|---|
| **General Engineering** | SWE, Test, Reviewer, Planner, CoS | None |
| **MedTech** | Software, QA, Risk, Regulatory, Validation, Safety, System | IEC 62304, ISO 14971, IEC 60601-1, FDA 21 CFR 820 |
| **Automotive** | HMI, ADAS, Telematics, Safety, Cybersecurity, Test, Systems | ISO 26262, UN ECE WP.29, ISO/SAE 21434 |
| **Mobile App** | iOS, Android, Backend, UX, Security, QA, DevOps | App Store, Play, GDPR |
| **Railways** | Signalling, Traction, TCMS, Safety, Verification, Cybersecurity, Systems | EN 50128, EN 50129, EN 50126 |
| **Avionics** | Avionics SW, DAL, Systems, Airworthiness, Test, Cybersecurity, DER | DO-178C, DO-254, ARP4754A |

Each template pre-loads: system prompts, task types, compliance flags.

---

## Slide 8 — SWE Agent (open-swe pattern)

**Submit a task → autonomous coding → PR opened → founder reviews.**

```
explore codebase
     ↓
plan changes
     ↓
implement (writes, runs tests)
     ↓
verify (pytest, linter)
     ↓
propose_pr (opens real GitHub PR)
     ↓ ← PAUSE FOR FOUNDER APPROVAL
finalize
```

```bash
curl -X POST http://localhost:8000/swe/task \
  -d '{"task": "Fix null pointer in CheckoutService", "repo_path": "/path/to/repo"}'
# → {"run_id": "...", "status": "awaiting_approval", "result": {"pr_url": "..."}}
```

---

## Slide 9 — Visual Workflow Diagrams

**Every LangGraph workflow → auto-generated Mermaid diagram.**

- `/workflows` page shows all workflows across all solutions
- Click any workflow → full-screen Mermaid diagram
- Always accurate — generated from `StateGraph.draw_mermaid()` at runtime
- Founder can show any stakeholder the exact flow before approving

```
flowchart TD
    explore --> plan
    plan --> implement
    implement --> verify
    verify --> propose_pr
    propose_pr -.->|awaiting_approval| finalize
    finalize --> END
```

---

## Slide 10 — Parallel Task Execution

**Multiple agents working concurrently in waves.**

- Tasks without dependencies → same wave, run in parallel
- Tasks with `depends_on: [id1, id2]` → wait for their wave
- Compliance solutions → automatic sequential fallback (single-lane)
- Runtime config: `POST /queue/config?max_workers=4&parallel_enabled=true`

**Example: 3 independent analyses → 3x faster:**
```
Wave 1: [analyze_log_A, analyze_log_B, analyze_log_C]  ← concurrent
Wave 2: [generate_report]  ← waits for wave 1
```

---

## Slide 11 — HIL Testing (Hardware-in-the-Loop)

**For embedded/IoT products: test on real hardware, generate regulatory evidence.**

```
Firmware binary
     ↓
HIL Runner (5 transports: serial, J-Link, CAN, OpenOCD, mock)
     ↓
Flash firmware → run test suite → capture results
     ↓
Regulatory evidence report (test IDs, pass/fail, firmware hash, timestamp)
     ↓
SAGE Audit Log → DHF-ready artifact
```

**Supports:** Medical IoT (IEC 62304), Automotive (ISO 26262), Avionics (DO-178C)

```bash
curl -X POST http://localhost:8000/hil/run-suite \
  -d '{"suite_name": "safety_critical", "firmware_path": "build/firmware.bin"}'
```

---

## Slide 12 — Compliance Flags Registry

**Automated compliance checklist per regulated industry.**

```bash
GET /compliance/checklist/medtech
# → 15 mandatory checkpoints: SOUP tracking, risk management, DHF, IEC 62304 Class C...

POST /compliance/gap-assessment
  {"solution_name": "iot_medical", "domain": "medtech"}
# → gap report: which standards are declared vs which flags are satisfied
```

**Industries covered:**
- MedTech: IEC 62304, ISO 14971, IEC 60601-1, FDA 21 CFR 820
- Automotive: ISO 26262 ASIL D, WP.29 CSMS, ISO/SAE 21434
- Railways: EN 50128 SIL 4, EN 50129, EN 50126 RAMS
- Avionics: DO-178C DAL A, DO-254, ARP4754A
- IoT/ICS: IEC 62443, IEC 62304, ISO 14971

---

## Slide 13 — Org Chart + Agent Traceability

**Every agent: visible, traceable, updatable.**

- `/org` — team hierarchy with `reports_to` relationships
- Live status: active (task in last 60s) / idle / error
- Daily task counts per agent
- Click any agent → full audit history → update its skills (prompts.yaml)

**API:**
```bash
GET /agents/status
# → [{name, role, status, last_task_at, tasks_today, recent_outputs}]
```

---

## Slide 14 — Dashboard: 22 Pages

All built. All connected to live backend.

**Core:** Dashboard · Approvals · Issues · Activity · Task Queue · Live Console
**Agents:** Agents · Org Chart
**Analysis:** Analyst · Developer · Monitor
**Intelligence:** Goals · Improvements · Workflows
**Config:** YAML Editor · Audit Log · LLM Settings · Integrations · Onboarding · Access Control · Costs · Settings

**Cmd+K** → command palette → jump to any page instantly.

---

## Slide 15 — Live Demo Flow

1. `./launch.sh starter` → backend + frontend start
2. Open `http://localhost:5173`
3. **Agents** → Hire Agent → describe "IoT Safety Engineer" → proposal appears in Approvals
4. **Approvals** → approve the agent → appears in Org Chart
5. **Analyst** → paste a firmware crash log → analyze → RED severity + root cause
6. **Approvals** → AI proposed "add to knowledge base" → approve
7. **Onboarding** → Path A → point at `/home/user/my-project` → YAML generated
8. **Workflows** → see SWE workflow diagram auto-generated from LangGraph
9. **Org Chart** → see all agents, live status, daily task counts

---

## Slide 16 — Quick Start

```bash
git clone https://github.com/Sumanharapanahalli/sage
cd sage
make venv            # one-time setup, creates .venv

# Pick your free LLM (no API key needed):
ollama serve && ollama pull llama3.2   # fully local
# OR
npm install -g @google/gemini-cli && gemini  # free Google login

./launch.sh starter   # starts backend + frontend

# Open http://localhost:5173
```

**That's it. No API keys. No cloud accounts. Runs on your laptop.**

---

## Slide 17 — The Five Laws

1. **Agents propose. Humans decide. Always.** The approval gate is the product.
2. **Eliminate waste at every layer.** If it can be automated correctly, it must be.
3. **Compounding intelligence over cold-start.** Every correction feeds the vector store.
4. **Vertical slices, not horizontal layers.** Every task: working end-to-end slice of value.
5. **Atomic verification is non-negotiable.** Every agent action has a defined verification step.

---

*SAGE Framework — Open Source (MIT) · Self-Hosted · Agent-First · Community-Driven*
*136 API endpoints · 27 UI pages · 79 E2E tests (78 passing) · 17+ solution templates · github.com/Sumanharapanahalli/sage*

---

## Slide — Open-Source Model

**Framework is open. Solutions are private. Community contributions welcome.**

| Layer | Visibility | How |
|---|---|---|
| **SAGE Framework** | Open source (MIT) | `github.com/Sumanharapanahalli/sage` |
| **Your solutions** | Private | Mount via `SAGE_SOLUTIONS_DIR` from a separate repo |
| **Runtime data (.sage/)** | Per-solution, gitignored | Auto-created, never committed |

- Star the repo, fork it, submit PRs
- File issues for bugs or feature requests
- Build MCP tool servers, solution templates, or workflow plugins
- See `CONTRIBUTING.md` for guidelines

---

## Slide 8 — What's New: SAGE 9 Features

Nine production-ready features shipped in SAGE 9:

| Feature | What it does |
|---|---|
| **D — Agent Budgets** | Monthly call ceilings per agent role, declared in `project.yaml` |
| **J — Undo** | Revert any approved `code_diff` proposal with one click |
| **L — Live Agents Panel** | Real-time view of active agents and their current tasks |
| **A — Task Hooks** | Pre/post shell hooks per task type in `tasks.yaml` |
| **B — Repo Map** | File tree + symbol extraction fed to Developer agent context |
| **E — Scheduled Tasks** | Cron-declared recurring tasks in `tasks.yaml`, auto-started |
| **F — Git Worktrees** | Isolated worktree per `code_diff` proposal — concurrent proposals, no conflicts |
| **K — Knowledge Sync** | Bulk-import docs/code into the vector store via `POST /knowledge/sync` |
| **G — Wave Execution** | Parallel subtask waves — queue one task, it fans out to many |

**Demo:** Open Dashboard → Active Agents panel → see live tasks in flight.

---

## Slide 9 — Action-Aware Chat

**The chat panel is now an action-routing assistant.**

Instead of just answering questions, the chat:
1. Classifies your intent using an LLM router
2. Shows a **confirmation card** for any mutating action
3. Executes after you click **Confirm**
4. Records every step in the compliance audit trail

**Example flows:**

```
User: "approve it"
→ Chat: "I'll approve the YAML edit for analyst.py threshold — proceed?"
→ [Confirm] → Proposal approved → audit log entry created
```

```
User: "queue a firmware review for MR !42"
→ Chat: "I'll submit a REVIEW_MR task for MR !42 — proceed?"
→ [Confirm] → Task queued
```

```
User: "what does PRECISERR mean?"
→ Chat: "PRECISERR is a calibration error indicating precision sensor drift..."
(No confirmation needed — pure answer)
```

**Audit model:** Every message stored with `message_type` — `user`, `answer`, `action_proposed`, `action_confirmed`, `action_cancelled`, `action_executed`. Every execute call writes to `compliance_audit_log` with `actor="human_via_chat"`.

**Demo:** Navigate to `/approvals` → open chat → type "approve the first proposal" → observe confirmation card → confirm → verify in audit log.

---

## Slide — Build Orchestrator (0→1→N)

**Describe a product in plain language → get a working codebase.**

```
"A task management app with Kanban boards and team collaboration"
     ↓
Domain detection → saas_product (auto-detected from keywords)
     ↓
Decompose → 4 components, 32 task types, 19 agents from WORKFORCE_REGISTRY
     ↓
AdaptiveRouter assigns best agent per task (Q-learning scores)
     ↓
Critic reviews plan (score: 0.85)
     ↓
HITL gate: founder approves plan
     ↓
Wave 1: [backend_api, frontend_ui] ← parallel
  → Anti-drift checkpoint ✓
Wave 2: [api_client]               ← depends on backend
  → Anti-drift checkpoint ✓
     ↓
Critic reviews code (score: 0.78)
     ↓
Integration + final review
     ↓
HITL gate: founder approves build
     ↓
Working codebase + tests + CI/CD + agentic patterns
```

**Three HITL levels:** `minimal` (final only) · `standard` (plan + final) · `strict` (plan + per-component + final)

**Critic Agent:** Actor-critic loop — every phase scored on correctness, completeness, consistency. Below threshold → agents revise automatically.

**3-tier degradation:** OpenSWE runner → LLM direct → template scaffold. Always produces a buildable output.

```bash
curl -X POST http://localhost:8000/build/start \
  -d '{"product_description": "...", "solution_name": "taskflow", "hitl_level": "standard"}'
```

**Built products are not static** — they ship with monitor agents, analyst prompts, scheduled tasks, and a seeded knowledge base.

---

## Slide — Domain Detection + Workforce Teams

**13 industry domains auto-detected. 19 agents in 5 teams. 32 task types.**

| Domain | Auto-detected from | Compliance injected |
|---|---|---|
| Medical Device | "medical", "clinical", "FDA" | IEC 62304, ISO 13485 |
| Automotive | "vehicle", "ADAS", "ECU" | ISO 26262, ASPICE |
| Avionics | "aircraft", "flight", "DO-178C" | DO-178C, ARP4754A |
| Robotics | "robot", "actuator", "ROS" | ISO 10218 |
| FinTech | "payment", "banking", "KYC" | PCI DSS, SOX |
| + 8 more | IoT, ML/AI, SaaS, Consumer, Enterprise, E-commerce, Healthcare SW, EdTech | Domain-specific |

**5 Workforce Teams:**

| Team | Lead | Members |
|---|---|---|
| Engineering | developer | qa_engineer, system_tester, devops_engineer, localization_engineer |
| Analysis | analyst | business_analyst, financial_analyst, data_scientist |
| Design | ux_designer | product_manager |
| Compliance | regulatory_specialist | legal_advisor, safety_engineer |
| Operations | operations_manager | technical_writer, marketing_strategist |

**Adaptive Router:** Q-learning agent routing — learns which agent performs best for each task type. 3+ observations before overriding defaults. Every build makes the next one smarter.

**Anti-Drift:** After each wave, outputs verified against plan. Drift logged as `BUILD_DRIFT_WARNING`. In strict mode, pauses for human review.

---

## Slide 10 — UX Intelligence Layer

**A completely redesigned interface for operator-grade clarity.**

| Improvement | What changed |
|---|---|
| **5-area accordion nav** | Work · Intelligence · Knowledge · Organization · Admin — one open at a time |
| **Solution rail** | 44px icon column — jump between solutions instantly |
| **Stats strip** | APPROVALS (red) · QUEUED (amber) · AGENTS (green) — live counts, 10s polling |
| **Resizable panels** | Drag handle between Analyst and Developer panes |
| **Per-solution themes** | Each solution has its own accent color — auto-applied from `project.yaml` |
| **Color combo preview** | Hover any color scheme in Settings to preview before applying |
| **Contextual chat** | Persistent chat panel in every page — knows your current page and live data |
| **Onboarding tour** | 6-stop spotlight tour for new solutions — auto-triggers on first load |
| **LLM heartbeat** | Amber disconnection popup if LLM provider drops — shows reconnect options |
