# SAGE Framework — Pipeline Architecture

Complete system graph showing how every component connects.
Use this to understand how data flows, where to plug in, and what runs when.

---

## 1. High-Level System Graph

```
                                    SAGE Framework
    ============================================================================

    USER / EXTERNAL                          SAGE CORE                         EXECUTION
    ==================                 ====================              ==================

    Browser (React UI)                                                   Domain Runners
    curl / API client ──────┐                                        ┌── OpenSWE (software)
    Slack webhooks ─────────┤                                        ├── OpenFW (firmware)
    n8n webhooks ───────────┤         ┌─────────────────────┐        ├── OpenEDA (PCB)
    GitHub webhooks ────────┤         │                     │        ├── OpenSim (hardware)
                            ▼         │    FastAPI Router    │        ├── OpenML (ML/AI)
                     ┌──────────┐     │   (src/interface/    │        ├── OpenDoc (docs)
                     │          │     │    api.py)           │        ├── OpenDesign (UX)
                     │  165+    │     │                     │        ├── OpenBrowser (QA)
                     │ Endpoints│─────│  27 categories      │        ├── OpenStrategy (planning)
                     │          │     │  CORS middleware     │        ├── OpenTerminal (shell)
                     └──────────┘     │  Tenant middleware   │        ├── AutoResearch (experiments)
                                      └────────┬────────────┘        └── OpenShell (sandbox)
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
                    ▼                          ▼                          ▼
          ┌─────────────────┐      ┌────────────────────┐     ┌──────────────────┐
          │  Agent Layer    │      │  Orchestration      │     │  Knowledge       │
          │                 │      │                     │     │                  │
          │  AnalystAgent   │      │  BuildOrchestrator  │     │  VectorStore     │
          │  DeveloperAgent │      │  LangGraphRunner    │     │  (ChromaDB)      │
          │  MonitorAgent   │      │  TemporalRunner     │     │                  │
          │  PlannerAgent   │      │  QueueManager       │     │  AuditLogger     │
          │  UniversalAgent │      │  ProposalStore      │     │  (SQLite)        │
          │  CriticAgent    │      │  ProposalExecutor   │     │                  │
          └────────┬────────┘      └────────┬───────────┘     │  LongTermMemory  │
                   │                        │                  └──────────────────┘
                   ▼                        ▼
          ┌─────────────────┐      ┌────────────────────┐
          │  LLM Gateway    │      │  Skill System       │
          │  (singleton)    │      │                     │
          │                 │      │  SkillRegistry      │
          │  Providers:     │      │  17 skill YAMLs     │
          │  - Gemini CLI   │      │  Engines field      │
          │  - Claude Code  │      │  Hot-reload         │
          │  - Ollama       │      │  Visibility tiers   │
          │  - Local GGUF   │      └────────────────────┘
          │  - Claude API   │
          │  - Generic CLI  │
          └─────────────────┘
```

---

## 2. Request Processing Pipeline

Every request follows the same five-phase lean loop:

```
    ┌─────────────────────────────────────────────────────────────────────┐
    │                    THE SAGE LEAN LOOP                               │
    │                                                                     │
    │   ┌──────────┐   ┌──────────────┐   ┌──────────┐   ┌──────────┐  │
    │   │ 1.SURFACE│──▶│2.CONTEXTUALIZE│──▶│3.PROPOSE │──▶│ 4.DECIDE │  │
    │   │          │   │              │   │          │   │          │  │
    │   │ Signal   │   │ Vector       │   │ LLM      │   │ Human    │  │
    │   │ received │   │ memory       │   │ generates │   │ approves │  │
    │   │ (webhook,│   │ searched;    │   │ action    │   │ or       │  │
    │   │  API,    │   │ prior        │   │ proposal  │   │ rejects  │  │
    │   │  trigger)│   │ decisions    │   │ with      │   │ with     │  │
    │   │          │   │ retrieved    │   │ trace_id  │   │ feedback │  │
    │   └──────────┘   └──────────────┘   └──────────┘   └─────┬────┘  │
    │                                                           │       │
    │                        ┌───────────────────────────────────┘       │
    │                        ▼                                          │
    │                  ┌──────────┐                                     │
    │                  │5.COMPOUND│                                     │
    │                  │          │◀────── Feedback loop ───────────────│
    │                  │ Store    │                                     │
    │                  │ feedback │         Every rejection teaches.    │
    │                  │ in vector│         Every approval reinforces.  │
    │                  │ memory   │         Intelligence compounds.     │
    │                  └──────────┘                                     │
    └─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Build Orchestrator Pipeline (0 to 1 to N)

The complete product build flow from description to deployed product:

```
    POST /build/start
         │
         ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                    BUILD ORCHESTRATOR                            │
    │                                                                  │
    │  ┌──────────────┐    ┌───────────────┐    ┌──────────────────┐  │
    │  │ 1. DETECT    │───▶│ 2. ASSEMBLE   │───▶│ 3. DECOMPOSE     │  │
    │  │   DOMAIN     │    │   WORKFORCE   │    │   TASKS          │  │
    │  │              │    │               │    │                  │  │
    │  │ 14 domains   │    │ 19 agents     │    │ LLM breaks into  │  │
    │  │ (DOMAIN_     │    │ 5 teams       │    │ 32 task types    │  │
    │  │  RULES)      │    │ (WORKFORCE_   │    │ with dependency  │  │
    │  │              │    │  REGISTRY)    │    │ graph            │  │
    │  └──────────────┘    └───────────────┘    └────────┬─────────┘  │
    │                                                     │            │
    │  ┌──────────────┐    ┌───────────────┐             │            │
    │  │ 4. CRITIC    │◀───│ Task graph    │◀────────────┘            │
    │  │   REVIEW     │    │ generated     │                          │
    │  │              │    └───────────────┘                          │
    │  │ N-provider   │                                               │
    │  │ multi-critic │    Score < threshold? ──▶ Retry with feedback │
    │  │ (Gemini +    │    Score >= threshold? ──▶ Continue ▼         │
    │  │  Claude +    │                                               │
    │  │  Ollama)     │                                               │
    │  └──────┬───────┘                                               │
    │         │                                                        │
    │         ▼                                                        │
    │  ┌──────────────┐    ┌───────────────┐    ┌──────────────────┐  │
    │  │ 5. HITL      │───▶│ 6. WAVE       │───▶│ 7. PER-TASK      │  │
    │  │   PLAN GATE  │    │   EXECUTION   │    │   CRITIC REVIEW  │  │
    │  │              │    │               │    │                  │  │
    │  │ Human        │    │ Independent   │    │ Each task output │  │
    │  │ reviews and  │    │ tasks run in  │    │ reviewed before  │  │
    │  │ approves     │    │ parallel      │    │ integration      │  │
    │  │ the plan     │    │ waves         │    │                  │  │
    │  └──────────────┘    └───────────────┘    └────────┬─────────┘  │
    │                                                     │            │
    │  ┌──────────────┐    ┌───────────────┐             │            │
    │  │ 10. HITL     │◀───│ 9. CRITIC     │◀───┐        │            │
    │  │   FINAL GATE │    │   INTEGRATION │    │        │            │
    │  │              │    │   REVIEW      │    │        ▼            │
    │  │ Human final  │    │              │    │  ┌──────────────┐   │
    │  │ approval     │    │ Full product │    │  │ 8. MERGE     │   │
    │  │              │    │ review       │    └──│   INTEGRATE  │   │
    │  └──────┬───────┘    └───────────────┘       └──────────────┘   │
    │         │                                                        │
    │         ▼                                                        │
    │  ┌──────────────┐                                               │
    │  │ 11. COMPLETE │    Anti-drift checkpoints at every step       │
    │  │              │    AdaptiveRouter learns from every task       │
    │  │ Product      │    Audit log captures full trace              │
    │  │ delivered    │                                               │
    │  └──────────────┘                                               │
    └─────────────────────────────────────────────────────────────────┘
```

---

## 4. Agent Gym Training Pipeline

How agents improve through practice:

```
    POST /gym/train {role, difficulty}
         │
         ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                    AGENT GYM (MuZero-inspired)                   │
    │                                                                  │
    │  ┌──────────────────────────────────────────────────────────┐   │
    │  │ EXERCISE SELECTION (3-tier priority)                      │   │
    │  │                                                          │   │
    │  │  Tier 1: Spaced Repetition (failed exercises due retry)  │   │
    │  │  Tier 2: Optimal Zone (40-70% success rate)              │   │
    │  │  Tier 3: Unseen (exploration)                            │   │
    │  │                                                          │   │
    │  │  Exercise Catalog: 661 seeds across 11 domains           │   │
    │  │  + LLM-generated variants (expandable to 50,000+)       │   │
    │  └─────────────────────────┬────────────────────────────────┘   │
    │                            │                                     │
    │                            ▼                                     │
    │  ┌──────────┐   ┌──────────────┐   ┌──────────┐                │
    │  │ 1. PLAY  │──▶│ 2. GRADE     │──▶│ 3.CRITIQUE│               │
    │  │          │   │              │   │          │               │
    │  │ Agent    │   │ Domain       │   │ N-critic │               │
    │  │ attempts │   │ runner       │   │ review   │               │
    │  │ exercise │   │ verifies     │   │ (Gemini, │               │
    │  │ via      │   │ output       │   │  Claude, │               │
    │  │ runner   │   │ (40% struct  │   │  Ollama) │               │
    │  │          │   │  60% LLM)    │   │          │               │
    │  └──────────┘   └──────────────┘   └────┬─────┘               │
    │                                          │                      │
    │  ┌──────────────┐   ┌──────────────┐    │                      │
    │  │ 5. COMPOUND  │◀──│ 4. REFLECT   │◀───┘                      │
    │  │              │   │              │                            │
    │  │ Learnings    │   │ Agent reviews│   ┌───────────────────┐   │
    │  │ stored in    │   │ its output   │   │ GLICKO-2 RATINGS  │   │
    │  │ vector       │   │ vs feedback, │   │                   │   │
    │  │ memory for   │   │ generates    │   │ Rating (1000 base)│   │
    │  │ next attempt │   │ improvement  │   │ RD (confidence)   │   │
    │  │              │   │ plan         │   │ Volatility        │   │
    │  └──────────────┘   └──────────────┘   │ Streak tracking   │   │
    │         │                               └───────────────────┘   │
    │         │                                                        │
    │         └──── Feeds back into Phase 1 ──────────────────────────│
    └─────────────────────────────────────────────────────────────────┘
```

---

## 5. Domain Runner Architecture

How tasks get executed in domain-specific environments:

```
    Build Orchestrator / Agent Gym
         │
         │  get_runner_for_role(agent_role)
         ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                    RUNNER REGISTRY                               │
    │                                                                  │
    │  Role ──────────────────────────────────▶ Runner                │
    │                                                                  │
    │  developer, qa_engineer, devops ────────▶ OpenSWE               │
    │  firmware_engineer, embedded_tester ────▶ OpenFW                │
    │  pcb_designer ──────────────────────────▶ OpenEDA               │
    │  hardware_sim_engineer ─────────────────▶ OpenSim               │
    │  data_scientist, ml_engineer ───────────▶ OpenML                │
    │  technical_writer, regulatory, legal ───▶ OpenDoc               │
    │  ux_designer ───────────────────────────▶ OpenDesign            │
    │  product_manager, marketing ────────────▶ OpenStrategy          │
    │  terminal_operator, shell_expert ───────▶ OpenTerminal          │
    │  research_engineer, ml_researcher ──────▶ AutoResearch          │
    │                                                                  │
    │  Supplementary (additive):                                      │
    │  qa_engineer, system_tester, ux ────────▶ OpenBrowser (gstack)  │
    │                                                                  │
    │  Each runner implements BaseRunner:                              │
    │    execute(task) ──▶ RunResult                                  │
    │    verify(result) ──▶ VerificationReport                        │
    │    get_exercises() ──▶ [Exercise]                               │
    │    grade_exercise() ──▶ ExerciseScore                           │
    └─────────────────────────────────────────────────────────────────┘
         │
         │  3-Tier Isolation Cascade (orthogonal to runner)
         ▼
    ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
    │ Tier 1: OpenShell│  │ Tier 2: Sandbox  │  │ Tier 3: Direct   │
    │                  │  │                  │  │                  │
    │ NVIDIA container │  │ Local clone +    │  │ LLM generation   │
    │ SSH + YAML       │  │ branch isolation │  │ in process       │
    │ policy           │  │                  │  │                  │
    │                  │  │ Falls back if    │  │ Falls back if    │
    │ Tried first      │  │ Tier 1 unavail   │  │ Tier 2 unavail   │
    └──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## 6. Skill System & Engine Injection

How skills and cross-cutting engines compose at runtime:

```
    ┌──────────────────────────────────────────────────────────────────┐
    │                    SKILL SYSTEM                                   │
    │                                                                   │
    │  skills/public/              SkillRegistry                       │
    │  ├── firmware_engineering    ┌─────────────────────┐             │
    │  │   engines: [auto_research]│ Indexes by:         │             │
    │  ├── machine_learning       │  - name → Skill     │             │
    │  │   engines: [auto_research]│  - role → [Skill]  │             │
    │  ├── software_engineering   │  - runner → [Skill] │             │
    │  │   engines: [auto_research]│  - tag → [Skill]   │             │
    │  ├── pcb_design             └─────────┬───────────┘             │
    │  │   engines: [auto_research]          │                         │
    │  ├── ... (9 with engines)              │                         │
    │  ├── product_strategy (no engine)      │                         │
    │  ├── terminal_operations (no engine)   │                         │
    │  └── auto_research (the engine)        │                         │
    │                                         │                         │
    │  build_prompt_for_role("firmware_engineer"):                     │
    │  ┌──────────────────────────────────────┐                       │
    │  │ ## Skill: firmware_engineering        │ ◀── Primary skill    │
    │  │ You are a senior firmware engineer... │                       │
    │  │                                       │                       │
    │  │ ## Engine: auto_research              │ ◀── Injected engine  │
    │  │ You have access to the auto_research  │     (because skill   │
    │  │ engine for autonomous experiments...  │      declares it)    │
    │  └──────────────────────────────────────┘                       │
    └──────────────────────────────────────────────────────────────────┘
```

---

## 7. Meta-Optimization Loop

How agent harnesses evolve over time:

```
    ┌─────────────────────────────────────────────────────────────────┐
    │                META-OPTIMIZER (outer loop)                       │
    │                                                                  │
    │  Agent Gym sessions produce execution traces                    │
    │         │                                                        │
    │         ▼                                                        │
    │  ┌──────────────┐   ┌───────────────┐   ┌──────────────────┐   │
    │  │ 1. COLLECT   │──▶│ 2. PROPOSE    │──▶│ 3. EVALUATE      │   │
    │  │   traces     │   │   improvement │   │   against        │   │
    │  │   from audit │   │   via LLM     │   │   baseline       │   │
    │  │   log        │   │               │   │                  │   │
    │  │              │   │ Targets:      │   │ Run proposal on  │   │
    │  │ Full traces  │   │ system_prompt │   │ exercise set,    │   │
    │  │ not just     │   │ tool_schema   │   │ measure delta    │   │
    │  │ scores       │   │ strategy      │   │                  │   │
    │  │ (50% vs 34%) │   │ config        │   │                  │   │
    │  └──────────────┘   └───────────────┘   └────────┬─────────┘   │
    │                                                   │              │
    │  ┌──────────────┐   ┌───────────────┐            │              │
    │  │ 5. CONVERGE  │◀──│ 4. PERSIST    │◀───────────┘              │
    │  │              │   │              │                            │
    │  │ Plateau      │   │ SQLite       │   Accepted? Harness       │
    │  │ detection    │   │ iteration    │   updated. Agents get     │
    │  │ (variance    │   │ history      │   better prompts/tools.   │
    │  │  < 2.0)      │   │              │                            │
    │  └──────────────┘   └───────────────┘                           │
    └─────────────────────────────────────────────────────────────────┘
```

---

## 8. AutoResearch Experiment Loop

How autonomous experiments run:

```
    POST /research/session {workspace, metric_name, run_command, max_experiments}
         │
         ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                AUTORESEARCH ENGINE (hill climbing)               │
    │                                                                  │
    │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   │
    │  │1.PROPOSE │──▶│ 2.APPLY  │──▶│3.EXECUTE │──▶│4.MEASURE │   │
    │  │          │   │          │   │          │   │          │   │
    │  │ LLM      │   │ search/  │   │ Run with │   │ Regex    │   │
    │  │ generates│   │ replace  │   │ wall-    │   │ extract  │   │
    │  │ hypothesis│  │ changes  │   │ clock    │   │ metric   │   │
    │  │ + code   │   │ to files │   │ budget   │   │ from     │   │
    │  │ change   │   │          │   │ (300s)   │   │ stdout   │   │
    │  └──────────┘   └──────────┘   └──────────┘   └────┬─────┘   │
    │                                                      │         │
    │                                          ┌───────────┘         │
    │                                          ▼                     │
    │                                   ┌──────────────┐             │
    │                                   │  5. DECIDE   │             │
    │                                   │              │             │
    │                              ┌────┤ Improved?    ├────┐        │
    │                              │    └──────────────┘    │        │
    │                              ▼                        ▼        │
    │                       ┌──────────┐           ┌──────────┐     │
    │                       │   KEEP   │           │ DISCARD  │     │
    │                       │          │           │          │     │
    │                       │ git      │           │ git      │     │
    │                       │ commit   │           │ reset    │     │
    │                       │ stays    │           │ --hard   │     │
    │                       │          │           │ HEAD~1   │     │
    │                       │ Baseline │           │          │     │
    │                       │ updated  │           │          │     │
    │                       └──────────┘           └──────────┘     │
    │                              │                        │        │
    │                              └────────┬───────────────┘        │
    │                                       ▼                        │
    │                              ┌──────────────┐                  │
    │                              │  6. LOOP     │                  │
    │                              │  Next        │                  │
    │                              │  experiment  │──▶ Back to 1     │
    │                              └──────────────┘                  │
    └─────────────────────────────────────────────────────────────────┘
```

---

## 9. Approval System (Two Tiers)

```
    ┌─────────────────────────────────────────────────────────────────┐
    │              APPROVAL ARCHITECTURE                               │
    │                                                                  │
    │  TIER 1: Framework Control (IMMEDIATE)                          │
    │  ──────────────────────────────────────                          │
    │  POST /config/switch    ──▶ Executes immediately                │
    │  POST /llm/switch       ──▶ No proposal created                 │
    │  POST /config/modules   ──▶ Returns {status: "switched"}        │
    │  POST /skills/reload    ──▶ These are operator actions           │
    │                                                                  │
    │  TIER 2: Agent Proposals (REQUIRES APPROVAL)                    │
    │  ──────────────────────────────────────────                      │
    │  yaml_edit              ─┐                                      │
    │  implementation_plan     │  ┌──────────────┐  ┌──────────────┐ │
    │  code_diff               ├──▶ ProposalStore │──▶  /approvals  │ │
    │  knowledge_delete        │  │  (SQLite)    │  │  (UI page)   │ │
    │  agent_hire              │  │  risk-rated  │  │  Human sees  │ │
    │                         ─┘  │  expiry-     │  │  and decides │ │
    │                              │  aware       │  └──────┬───────┘ │
    │                              └──────────────┘         │         │
    │                                                       ▼         │
    │                          ┌──────────────────────────────┐       │
    │                          │  POST /approve/{trace_id}    │       │
    │                          │  or                          │       │
    │                          │  POST /reject/{trace_id}     │       │
    │                          │                              │       │
    │                          │  Approve: ProposalExecutor   │       │
    │                          │  dispatches side-effect      │       │
    │                          │                              │       │
    │                          │  Reject: feedback stored in  │       │
    │                          │  vector memory (compounds)   │       │
    │                          └──────────────────────────────┘       │
    └─────────────────────────────────────────────────────────────────┘
```

---

## 10. Onboarding Pipeline

How new solutions get created:

```
    ┌─────────────────────────────────────────────────────────────────┐
    │              ONBOARDING FLOW                                     │
    │                                                                  │
    │  PATH A: Analyze existing project                               │
    │  ─────────────────────────────────                              │
    │  POST /onboarding/analyze                                       │
    │    ├── text: "Flutter app with HIPAA"                           │
    │    ├── path: "/path/to/project"                                 │
    │    └── url: "https://github.com/org/repo"                       │
    │         │                                                        │
    │         ▼                                                        │
    │  OnboardingAnalyzer ──▶ ProjectSignals                          │
    │    detected_stack: [Flutter, Firebase]                           │
    │    detected_ci: GitHub Actions                                  │
    │    compliance_hints: [HIPAA]                                    │
    │    suggested_roles: [analyst, developer, planner]               │
    │                                                                  │
    │  PATH B: Generate from description                              │
    │  ─────────────────────────────────                              │
    │  POST /onboarding/generate                                      │
    │    {"description": "...", "solution_name": "..."}               │
    │         │                                                        │
    │         ▼                                                        │
    │  LLM generates 3 YAML files:                                    │
    │    project.yaml  ──▶ What the solution IS                       │
    │    prompts.yaml  ──▶ How agents THINK                           │
    │    tasks.yaml    ──▶ What agents CAN DO                         │
    │         │                                                        │
    │         ▼                                                        │
    │  POST /onboarding/save-solution                                 │
    │    Writes to SAGE_SOLUTIONS_DIR/<name>/                         │
    │    Auto-creates .sage/ directory                                │
    │                                                                  │
    │  PATH C: Scan local folder                                      │
    │  ─────────────────────────                                      │
    │  POST /onboarding/scan-folder {folder_path}                     │
    │    FolderScanner ──▶ LLM ──▶ 3 YAML files                      │
    │                                                                  │
    │  PATH D: Conversational                                         │
    │  ─────────────────────                                          │
    │  POST /onboarding/session ──▶ Start session                     │
    │  POST /onboarding/session/{id}/message ──▶ Chat                 │
    │  POST /onboarding/session/{id}/generate ──▶ Create YAMLs        │
    └─────────────────────────────────────────────────────────────────┘
```

---

## 11. Data Flow Summary

```
    External Input                 Processing                    Persistence
    ──────────────                 ──────────                    ───────────

    HTTP Request ───▶ FastAPI ───▶ Agent/Orchestrator ──┬──▶ .sage/audit_log.db
                                       │                │      (compliance record)
                                       ▼                │
                                  LLM Gateway ──────────┼──▶ .sage/chroma_db/
                                  (Gemini/Claude/       │      (vector memory)
                                   Ollama/Local)        │
                                       │                ├──▶ .sage/auto_research.db
                                       ▼                │      (experiment history)
                                  Domain Runner ────────┤
                                  (execute + verify)    ├──▶ .sage/gym.db
                                       │                │      (training history)
                                       ▼                │
                                  Proposal Store ───────┼──▶ .sage/meta_optimizer.db
                                  (await approval)      │      (harness evolution)
                                       │                │
                                       ▼                └──▶ Git commits
                                  Human Decision              (experiment tracker)
                                  (approve/reject)
```

---

## 12. API Endpoint Map by Category

| # | Category | Endpoints | Key Files |
|---|---|---|---|
| 1 | Core & Health | 14 | `api.py` |
| 2 | Analysis & Agents | 12 | `api.py`, agents/ |
| 3 | Approval Queue | 8 | `proposal_store.py`, `proposal_executor.py` |
| 4 | Audit & Activity | 6 | `audit_logger.py` |
| 5 | Knowledge Base | 8 | `vector_store.py`, `long_term_memory.py` |
| 6 | Monitoring | 4 | `api.py` |
| 7 | Webhooks | 4 | `api.py`, `slack_approver.py` |
| 8 | LLM Management | 6 | `llm_gateway.py` |
| 9 | Eval/Benchmarking | 4 | `eval_runner.py` |
| 10 | Onboarding | 9 | `onboarding.py`, `onboarding_session.py`, `onboarding_analyzer.py` |
| 11 | Build Orchestrator | 8 | `build_orchestrator.py` |
| 12 | SWE Agent | 2 | `openswe_runner.py` |
| 13 | Workflow (LangGraph) | 4 | `langgraph_runner.py` |
| 14 | Organization | 6 | `org_loader.py` |
| 15 | Feature Requests | 6 | `api.py` |
| 16 | Agent Gym | 12 | `agent_gym.py`, `exercise_catalog.py` |
| 17 | Skills | 7 | `skill_loader.py` |
| 18 | Runners | 4 | `base_runner.py` |
| 19 | Meta-Optimization | 4 | `meta_optimizer.py` |
| 20 | AutoResearch | 5 | `auto_research.py` |
| 21 | Streaming (SSE) | 3 | `api.py` |
| 22 | Multi-Tenant | 2 | `tenant.py` |
| 23 | YAML Editor | 4 | `api.py` |
| 24 | Cost Tracking | 3 | `api.py` |
| 25 | Data Transformation | 4 | `routes/data_transformation.py` |
| 26 | Voice Data | 3 | `routes/voice_data.py` |
| 27 | Sandbox Execution | 2 | `sandbox_runner.py`, `openshell_runner.py` |

---

## 13. Solution YAML Contract

Every solution plugs in via exactly 3 YAML files:

```
    solutions/<name>/
    ├── project.yaml          WHAT the solution IS
    │   ├── project_name
    │   ├── description
    │   ├── active_modules    (which UI modules to show)
    │   ├── theme             (CSS vars for branding)
    │   └── compliance        (standards: ISO, FDA, etc.)
    │
    ├── prompts.yaml          HOW agents THINK
    │   ├── roles             (analyst, developer, custom_role...)
    │   ├── system_prompts    (per-role LLM instructions)
    │   └── tool_access       (what each role can use)
    │
    ├── tasks.yaml            WHAT agents CAN DO
    │   ├── task_types        (ANALYZE_LOG, CREATE_MR, custom...)
    │   ├── routing           (which role handles which task)
    │   └── workflows         (multi-step task sequences)
    │
    └── .sage/                RUNTIME STATE (auto-created, gitignored)
        ├── audit_log.db      (all proposals, approvals, audit trail)
        └── chroma_db/        (vector knowledge store)
```

---

## Quick Start for Your Project

```bash
# 1. Describe your project
curl -X POST http://localhost:8000/onboarding/generate \
  -d '{"description": "E-commerce platform with ML recommendations",
       "solution_name": "ecommerce_ml"}'

# 2. Switch to it
curl -X POST http://localhost:8000/config/switch \
  -d '{"project": "ecommerce_ml"}'

# 3. Build something
curl -X POST http://localhost:8000/build/start \
  -d '{"description": "Add personalized product recommendation engine"}'

# 4. Train agents
curl -X POST http://localhost:8000/gym/train \
  -d '{"role": "data_scientist", "difficulty": "intermediate"}'

# 5. Run experiments
curl -X POST http://localhost:8000/research/session \
  -d '{"workspace": "./ml_model", "metric_name": "val_accuracy",
       "run_command": "python train.py", "max_experiments": 10,
       "direction": "higher"}'
```

---

## 14. Integration Health Report

Full-codebase audit of all public functions/methods wired into the pipeline.

```
AREA               FILES   PUBLIC ITEMS   WIRED   HEALTH
─────────────────────────────────────────────────────
src/core/            39       95+          93      98%
src/integrations/    26       52           50      96%
src/interface/        4      140+         138      98%
src/agents/           7       20+          20     100%
src/memory/           3       15           14      93%
src/modules/          5       14           14     100%
─────────────────────────────────────────────────────
TOTAL               84      336+         329      98%
```

**Key connections wired in this audit:**
- `RoleGenerator` → `proposal_executor._execute_agent_hire()` (was duplicating YAML logic)
- `propose_code_patch()` → `POST /developer/propose-patch`
- `add_mr_comment()` → `POST /mr/comment`
- `get_plan_status()` → `POST /planner/status`
- `long_term_memory.remember()` → rejection feedback handler (compounding intelligence)
- `teams_bot.send_mr_created()` → MR creation endpoint
- `teams_bot.send_approval_request()` → analysis proposal creation
- `org_aware_query()` → `POST /knowledge/search` with `org_filter` param
- `get_tools_for_solution()` → `GET /integrations/langchain/tools`
- `as_react_tools()` → CodingAgent `_react_loop()` MCP tool injection
- `EventBus.publish()` → MonitorAgent event dispatch
- `trace_id.is_valid()` → approve/reject endpoint input validation
