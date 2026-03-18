# SAGE[ai] — Intelligence Layer v1 Demo
### *Demo Script — March 2026*

---

## Slide 1 — The Vision

> **1 human. An AI agent team. A billion-dollar operation.**

- Every company function → an agent role
- Founder reviews only decisions that require human judgment
- The rest runs autonomously, with a complete audit trail

**Live today.** Open source. Zero mandatory API keys.

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
git clone https://github.com/your-org/sage
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

*SAGE Framework — Open Source · Self-Hosted · Agent-First*
*397 tests passing · 22-page dashboard · 6 regulated domain solutions*
