# SAGE Framework — Architecture Study

> Comprehensive architecture review, limitations analysis, and pattern recommendations.
> Written for any developer or architect evaluating or extending SAGE.

**Date:** 2026-04-03
**Scope:** Full framework — not just communication, but LLM abstraction, memory, execution, API design, testing, scalability, and extensibility.
**Codebase snapshot:** 120+ Python source files, ~72,000 LOC (48,700 Python + 23,000 TypeScript), 227+ API endpoints, 39 UI pages, 11 domain runners.

**Latest additions:** Product Owner agent, Systems Engineering framework (IEEE 15288/IEC 62304), regulatory compliance (21 CFR Part 11), Connector Framework (GitHub/filesystem), complexity-based model routing, BFTS tree search, persistent chat/goals stores.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Architecture Overview](#2-current-architecture-overview)
3. [Architecture Patterns SAGE Already Uses](#3-architecture-patterns-sage-already-uses)
4. [Strengths](#4-strengths)
5. [Limitations & Bottlenecks](#5-limitations--bottlenecks)
6. [Industry Architecture Patterns Evaluated](#6-industry-architecture-patterns-evaluated)
7. [Framework Comparisons](#7-framework-comparisons)
8. [Anti-Patterns to Avoid](#8-anti-patterns-to-avoid)
9. [Recommendations](#9-recommendations)
10. [Evolution Roadmap](#10-evolution-roadmap)
11. [Appendix: Code References](#appendix-code-references)

---

## 1. Executive Summary

SAGE is a **hybrid monolith** combining five architecture patterns: Orchestrator-Worker, Microkernel/Plugin, CQRS+Event Sourcing, ReAct loops, and Pipeline/DAG execution. This is architecturally sound for a framework at SAGE's current scale (single-operator, ~10 concurrent users).

**What works well:**
- YAML-driven agent configuration (no code changes for new roles)
- 3-tier execution cascade (OpenShell → Sandbox → OpenSWE)
- BaseRunner abstraction for domain-specific execution
- Full audit trail (every action logged)
- Graceful degradation (every integration is best-effort)

**What limits growth:**
- **Single-lane LLM lock** — `threading.Lock` serializes ALL inference across all agents
- **5,717-line monolithic api.py** — 174 endpoints in one file
- **SQLite under concurrent writes** — no connection pooling, WAL mode not enforced
- **No circuit breakers** — one failing integration blocks request threads
- **Unbounded in-memory state** — BuildOrchestrator stores full run history in RAM
- **Thread-unsafe fallback paths** — vector store's in-memory fallback has no locking

**Recommendation:** Evolve as a **Modular Monolith** (not microservices). Split api.py into route modules, replace the single LLM lock with a semaphore pool, add SQLite WAL + connection pooling, and introduce circuit breakers on integration boundaries. This keeps deployment simplicity while removing the bottlenecks.

---

## 2. Current Architecture Overview

### 2.1 High-Level Topology

```
┌────────────────────────────────────────────────────────────────┐
│  React UI (web/src/)                                           │
│  ─ pages, components, API client                               │
└──────────────────────┬─────────────────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼─────────────────────────────────────────┐
│  FastAPI (src/interface/api.py) — 174 endpoints, 5717 lines    │
│  ─ Single Python process, uvicorn                              │
├────────────────────────────────────────────────────────────────┤
│  Core Layer (src/core/)                                        │
│  ┌──────────┐ ┌────────────┐ ┌─────────────┐ ┌──────────────┐ │
│  │LLMGateway│ │QueueManager│ │ProposalStore│ │BuildOrchestrt│ │
│  │(singleton│ │(6 locks,   │ │(SQLite)     │ │(2878 lines,  │ │
│  │ 1 lock)  │ │ in-memory) │ │             │ │ Q-learning)  │ │
│  └──────────┘ └────────────┘ └─────────────┘ └──────────────┘ │
│  ┌──────────┐ ┌────────────┐ ┌─────────────┐ ┌──────────────┐ │
│  │AgentGym  │ │SkillLoader │ │EvalRunner   │ │MetaOptimizer │ │
│  │(Glicko-2)│ │(YAML hot-  │ │(SQLite)     │ │(SQLite)      │ │
│  │          │ │ reload)    │ │             │ │              │ │
│  └──────────┘ └────────────┘ └─────────────┘ └──────────────┘ │
│  ┌──────────┐ ┌────────────────────────────────────────────┐ │
│  │SystemsEng│ │AutoResearch (Hill-climbing optimization)    │ │
│  │IEEE15288 │ │                                            │ │
│  │IEC62304  │ │                                            │ │
│  └──────────┘ └────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────┤
│  Agent Layer (src/agents/)                                     │
│  Analyst, Developer, Monitor, Planner, Universal, Critic,      │
│  Product Owner ─ All share single LLMGateway instance          │
├────────────────────────────────────────────────────────────────┤
│  Memory Layer (src/memory/)                                    │
│  ┌──────────────┐ ┌───────────────┐ ┌────────────────────┐    │
│  │AuditLogger   │ │VectorStore    │ │LongTermMemory      │    │
│  │(SQLite)      │ │(ChromaDB /    │ │(vector + semantic)  │    │
│  │              │ │ in-memory FB) │ │                     │    │
│  └──────────────┘ └───────────────┘ └────────────────────┘    │
├────────────────────────────────────────────────────────────────┤
│  Integration Layer (src/integrations/) — 26 runners            │
│  ┌────────┐┌────────┐┌────────┐┌───────┐┌────────┐┌────────┐ │
│  │OpenSWE ││OpenFW  ││OpenEDA ││OpenML ││OpenDoc ││OpenSim │ │
│  ├────────┤├────────┤├────────┤├───────┤├────────┤├────────┤ │
│  │Terminal││Browser ││Design  ││Stratgy││Shell   ││Sandbox │ │
│  ├────────┤├────────┤├────────┤├───────┤├────────┤├────────┤ │
│  │LangGrph││AutoGen ││Temporal││Slack  ││MCP    ││LangChn │ │
│  └────────┘└────────┘└────────┘└───────┘└────────┘└────────┘ │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
Signal (webhook/API/schedule)
  → api.py receives request
    → QueueManager enqueues task
      → Agent picks task from queue
        → LLMGateway.generate() [acquires lock, blocks all other agents]
          → Provider (Gemini CLI / Claude / Ollama / local)
        → Agent produces Proposal
          → ProposalStore persists to SQLite
            → Human reviews at /approvals
              → Approved: ProposalExecutor dispatches
              → Rejected: feedback → VectorStore (compounding)
```

### 2.3 Module Inventory

| Subsystem | Files | Total LOC | Key Pattern |
|---|---|---|---|
| API Interface | 1 | 5,717 | Monolithic router |
| Core Engine | 16 | 11,200 | Singleton + locks |
| Agents | 6 | 2,800 | Role-based, YAML-driven |
| Memory | 4 | 1,600 | SQLite + ChromaDB |
| Integrations | 26 | 14,500 | BaseRunner + graceful degradation |
| Modules | 8 | 1,200 | Zero-dependency utilities |
| Skills | 10 YAML | — | Declarative capability registry |

---

## 3. Architecture Patterns SAGE Already Uses

SAGE is not a single-pattern framework. It's a hybrid of five patterns, each applied where it fits:

### 3.1 Orchestrator-Worker (Primary)

**Where:** `BuildOrchestrator` → task decomposition → wave execution → agents
**How it works:** The orchestrator decomposes a product description into a task graph (32 task types), groups independent tasks into parallel waves, and dispatches them to agents via the `AdaptiveRouter` (Q-learning).

```
BuildOrchestrator (orchestrator)
  ├── Wave 1: [architecture_task, requirements_task]  ← parallel
  ├── Wave 2: [impl_task_1, impl_task_2, impl_task_3] ← parallel
  └── Wave 3: [integration_test, deployment]           ← sequential
```

**Verdict:** Well-suited. This is the standard pattern for complex multi-agent workflows (used by LangGraph, CrewAI, DeerFlow).

### 3.2 Microkernel / Plugin (Extensions)

**Where:** `BaseRunner` ABC → 11 domain runners, `SkillLoader` → YAML skills, `MCP Registry` → tools
**How it works:** The core framework defines extension points. Domain runners, skills, and tools plug in without modifying framework code. New domains are added by implementing `BaseRunner` with 4 methods.

**Verdict:** Excellent. This is SAGE's strongest architectural decision. It enables the "11+ domain" requirement without bloating the core.

### 3.3 CQRS + Event Sourcing (Audit)

**Where:** `AuditLogger` (write-side), `/audit/*` endpoints (read-side), `ProposalStore` (event log)
**How it works:** Every action is an immutable event in SQLite. The audit log is append-only. Proposals have lifecycle states (pending → approved/rejected → executed). The vector store compounds from these events.

**Verdict:** Sound for compliance. The append-only audit log is critical for ISO 13485 / IEC 62304. However, it's informal CQRS — the read and write models share the same SQLite database and schema.

### 3.4 ReAct Loop (Per-Task)

**Where:** Each agent's task execution: observe → think → act → observe
**How it works:** Agents follow a ReAct pattern where they reason about the task, select a tool/action, execute it, observe the result, and iterate.

**Verdict:** Industry standard. Used by every major agent framework.

### 3.5 Pipeline / DAG (Wave Execution)

**Where:** `_compute_waves()` in BuildOrchestrator
**How it works:** Tasks are organized into dependency waves. Tasks within a wave have no dependencies on each other and run in parallel.

**Verdict:** Correct pattern for maximizing throughput with dependency constraints.

---

## 4. Strengths

### 4.1 YAML-First Agent Configuration
Adding a new agent role requires editing `prompts.yaml`, not Python. This is a significant advantage over frameworks like AutoGen (code-defined agents) or early LangChain (code-heavy chain construction). Only CrewAI and SAGE take YAML-first seriously.

### 4.2 Graceful Degradation Everywhere
Every integration wraps in try/except with a meaningful fallback:
- No ChromaDB? Falls back to in-memory dict
- No Gemini CLI? Falls back to primary LLM only for critic
- No gstack? Falls back to LLM-simulated browser testing
- No Docker? Falls back to local sandbox
- No Temporal? Falls back to LangGraph

This "runs anywhere" philosophy is rare in agent frameworks and critical for single-operator deployments.

### 4.3 3-Tier Execution Cascade
OpenShell → Sandbox → OpenSWE gives defense-in-depth for code execution. Most frameworks have a single execution model (Docker or nothing). SAGE's cascade means it works on any machine.

### 4.4 BaseRunner Abstraction
The `BaseRunner` ABC with 4 required methods (`execute`, `verify`, `get_exercises`, `grade_exercise`) creates a clean contract for domain runners. This is comparable to Haystack's `Component` protocol but specialized for agent execution.

### 4.5 Full Audit Trail
Every `generate()` call, every proposal, every approval/rejection is logged with a `trace_id`. This is table-stakes for regulated industries but rare in open-source agent frameworks.

### 4.6 Compounding Intelligence
The vector store accumulates human corrections, making future agent context richer. This is the Memento principle — behavioral improvement without model retraining. No other framework implements this systematically.

### 4.7 Product Owner Agent — Requirements Engineering
**File:** `src/agents/product_owner.py`
Converts basic customer inputs ("I want a fitness app") into structured product backlogs following proper Product Management principles:
- **5W1H Method**: Who, What, When, Where, Why, How questioning for requirements clarity
- **User Story Creation**: Proper "As a [persona], I want [capability] so that [benefit]" format
- **MoSCoW Prioritization**: Must Have, Should Have, Could Have, Won't Have classification
- **INVEST Criteria**: Independent, Negotiable, Valuable, Estimable, Small, Testable stories
- **Iterative Refinement**: Structured interview process with clarifying questions

This eliminates the "requirements engineering gap" where customers provide vague descriptions and expect developers to guess the product vision. No comparable capability exists in other agent frameworks.

### 4.8 Systems Engineering Framework — IEEE 15288 Compliance
**File:** `src/core/systems_engineering.py`
Full systems engineering lifecycle following IEEE 15288 standards with regulatory compliance built-in:
- **Requirements Traceability**: 4 bidirectional matrices (User Needs→Requirements→Design→Verification→Validation)
- **V-Model Implementation**: Structured decomposition with verification at each level
- **Risk Assessment**: ISO 31000 compliant with mitigation tracking
- **Change Control**: Formal process per IEC 62304 §6.1 with impact analysis
- **Electronic Signatures**: 21 CFR Part 11 compliance for regulated industries
- **Regulatory Documents**: Auto-generated SRS, SAD, V&V Plan, Risk Management File, SOUP Inventory
- **Compliance Scoring**: Automated readiness assessment for regulatory submissions

This positions SAGE uniquely for regulated industries (medical devices, automotive, aerospace) where formal systems engineering processes are mandatory. No other agent framework provides this level of regulatory compliance.

---

## 5. Limitations & Bottlenecks

### 5.1 🔴 Single-Lane LLM Lock (Critical)

**File:** `src/core/llm_gateway.py:572`
**Problem:** A single `threading.Lock()` serializes ALL LLM inference across all agents.

```python
self._lock = threading.Lock()

def generate(self, prompt, system_prompt=...):
    with self._lock:       # ← ALL agents wait here
        return self._provider.generate(prompt, system_prompt)
```

**Impact:** If 5 agents need LLM inference simultaneously, they queue behind a single lock. A 30-second Gemini CLI call blocks every other agent for 30 seconds. Wave-parallel execution degrades to sequential under LLM load.

**Why it exists:** "GPU safety + QMS compliance" (code comment). Valid for local GPU inference (single GPU can only process one request). Not valid for cloud providers (Gemini, Claude API) which handle their own concurrency.

**Recommendation:** Replace with a `threading.Semaphore(n)` where `n` depends on the provider:
- `n=1` for `local` and `ollama` (single GPU)
- `n=5+` for `gemini`, `claude`, `claude-code` (cloud APIs with server-side concurrency)

### 5.2 🔴 Monolithic api.py (Critical)

**File:** `src/interface/api.py` — 5,717 lines, 174 endpoints, 214 functions
**Problem:** Every endpoint, every import, every lazy accessor, every request handler lives in a single file.

**Impact:**
- Difficult to navigate, review, or test individual endpoint groups
- Import-time side effects affect everything
- IDE performance degrades
- No clear ownership boundaries (who owns `/build/*` vs `/gym/*`?)

**Industry comparison:** FastAPI's own documentation recommends `APIRouter` for splitting. Every production FastAPI app above ~50 endpoints uses routers.

**Recommendation:** Split into `src/interface/routes/` with one router per domain:
```
routes/
  build.py       # /build/* endpoints
  gym.py         # /gym/* endpoints
  knowledge.py   # /knowledge/* endpoints
  approvals.py   # /approvals/* endpoints
  config.py      # /config/*, /llm/* endpoints
  research.py    # /research/* endpoints
  meta.py        # /meta/* endpoints
  integrations.py # /workflow/*, /webhook/* endpoints
  skills.py      # /skills/* endpoints
```

### 5.3 🟡 SQLite Under Concurrent Writes (Moderate)

**Problem:** 12+ `sqlite3.connect()` calls in api.py alone, none using connection pooling or WAL mode. SQLite's default journal mode locks the entire database on writes.

**Impact:** Under concurrent writes (multiple proposals being approved, gym training sessions, audit events), SQLite throws `database is locked` errors or blocks.

**Recommendation:**
1. Enable WAL mode: `PRAGMA journal_mode=WAL` on every connection
2. Use a connection pool (or at minimum, a shared connection per database file)
3. Consider `aiosqlite` for async FastAPI endpoints

### 5.4 🟡 No Circuit Breakers (Moderate)

**Problem:** Integration calls (Gemini CLI, Slack, Temporal, LangGraph) have no circuit breaker pattern. A failing external service causes repeated timeouts.

**Impact:** If Gemini CLI hangs, every multi-critic review blocks for the full timeout period on every request. There's no "back off after N failures" logic.

**Recommendation:** Add a simple circuit breaker per integration:
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, reset_timeout=60):
        self.failures = 0
        self.threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure = 0
        self.state = "closed"  # closed → open → half-open
```

### 5.5 🟡 Unbounded In-Memory State (Moderate)

**Problem:** `BuildOrchestrator` stores full run history in `self._runs` dict. `QueueManager` keeps all completed tasks in memory. No eviction or archival.

**Impact:** Long-running instances accumulate memory. After hundreds of builds, the process may OOM. Not a problem for single-operator daily use, but a concern for continuous operation.

**Recommendation:** Evict completed runs after N hours or persist to SQLite and clear from memory.

### 5.6 🟡 Thread-Unsafe Fallback Paths (Moderate)

**File:** `src/memory/vector_store.py`
**Problem:** When ChromaDB is unavailable, the vector store falls back to an in-memory dict. This fallback has no locking, but multiple agents may write to it concurrently.

**Recommendation:** Add a `threading.Lock` around the fallback dict operations, or use `threading.local()` for per-thread state.

### 5.7 🟢 Singletons Make Testing Harder (Minor)

**Problem:** `LLMGateway` and `SageIntelligence` use singleton patterns. Tests must monkey-patch `_instance` to inject mocks. No dependency injection container.

**Impact:** Test setup is brittle. Parallel test execution can cause state leakage.

**Recommendation:** For now, the singleton pattern is acceptable for a single-process framework. If SAGE ever needs multi-process deployment, switch to a DI container (e.g., `dependency-injector` or FastAPI's `Depends`).

### 5.8 🟢 No Structured Error Types (Minor)

**Problem:** Most error handling uses generic `except Exception` with string error messages. No hierarchy of framework-specific exceptions.

**Impact:** Callers can't distinguish between "LLM provider timed out" and "invalid prompt format" — both are generic exceptions.

**Recommendation:** Define a small exception hierarchy:
```python
class SAGEError(Exception): pass
class LLMProviderError(SAGEError): pass
class LLMTimeoutError(LLMProviderError): pass
class ProposalExpiredError(SAGEError): pass
class RunnerUnavailableError(SAGEError): pass
```

---

## 6. Industry Architecture Patterns Evaluated

### 6.1 Pattern Comparison Matrix

| Pattern | Fits SAGE? | Why / Why Not |
|---|---|---|
| **Monolithic** | ✅ Current | Simple deployment, single process. Hits limits at scale. |
| **Modular Monolith** | ✅✅ Recommended | Keep single process, enforce module boundaries. Best of both worlds. |
| **Microservices** | ❌ Overkill | SAGE's target is 1 operator + AI team, not distributed systems. Adds deployment complexity without proportional benefit. |
| **Serverless/FaaS** | ❌ Wrong fit | Agent tasks are long-running (minutes), not request/response. Cold starts kill UX. |
| **Actor Model** (Ray/Erlang) | 🟡 Future option | Would solve the LLM lock problem elegantly. But Ray is a heavy dependency for a "runs anywhere" framework. |
| **Blackboard** | 🟡 Partial fit | Agents already share state through vector store + audit log, which is a loose blackboard. Formalizing it adds complexity without clear benefit. |
| **Pub/Sub** (Kafka/NATS) | ❌ Overkill | SAGE's event volume doesn't justify a message broker. The EventBus module is sufficient. |
| **Hierarchical Multi-Agent** | ✅ Already used | BuildOrchestrator is the supervisor; agents are workers. This is correct. |
| **Swarm / P2P** | ❌ Wrong fit | SAGE needs deterministic, auditable execution. Swarm patterns sacrifice auditability for flexibility. |
| **Pipeline / DAG** | ✅ Already used | Wave execution in BuildOrchestrator. Correct pattern. |
| **Microkernel / Plugin** | ✅ Already used | BaseRunner + SkillLoader + MCP. SAGE's strongest pattern. |
| **CQRS + Event Sourcing** | ✅ Already used | Audit log + proposal store. Could be formalized further. |

### 6.2 Deployment Architecture Patterns

| Pattern | Description | Scalability | Complexity | SAGE Fit |
|---|---|---|---|---|
| **Monolithic** | Single process, everything co-located | ~10-50 concurrent users | Low | ✅ Current |
| **Modular Monolith** | Single process, enforced module boundaries | Same as monolith + better maintainability | Low-Medium | ✅✅ Recommended |
| **Microservices** | Each agent/subsystem is a service | Horizontal, per-subsystem | Very High | ❌ Overkill until 50+ users |
| **Serverless/FaaS** | Agents as functions (Lambda) | Auto-scale to thousands | Medium | ❌ Wrong fit — agent tasks are long-running, cold starts kill UX |
| **Hybrid (Majestic Monolith)** | Monolith core + extracted worker services | Core scales vertically, workers horizontally | Medium | 🟡 Future target |

**The Majestic Monolith path (from DHH / Basecamp):** Start monolith, extract services only when specific pain points demand it. For SAGE, the extraction order when needed:
1. **First:** Code execution workers (runners) — different security/scaling profile
2. **Second:** LLM gateway — connection pooling, multi-provider routing
3. **Third:** Vector store — already semi-external (ChromaDB server mode)
4. **Never extract:** Approval flow, audit log, agent orchestration — these must remain consistent and transactional

Each extraction should be triggered by a **measured** pain point. "We hit the connection limit on our LLM provider" is valid. "We might need to scale someday" is not.

### 6.3 Recommended Pattern: Modular Monolith

A **Modular Monolith** keeps the single-process, single-deployment simplicity while enforcing clean boundaries between subsystems:

```
┌─────────────────────────────────────────────────────┐
│  SAGE Process                                        │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐       │
│  │ API Module │  │ Core      │  │ Memory    │       │
│  │ (routes/) │  │ Module    │  │ Module    │       │
│  │           │  │           │  │           │       │
│  │ Depends on│─→│ Depends on│─→│ No deps   │       │
│  │ Core,     │  │ Memory    │  │           │       │
│  │ Memory    │  │           │  │           │       │
│  └───────────┘  └───────────┘  └───────────┘       │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐       │
│  │ Agent     │  │Integration│  │ Skill     │       │
│  │ Module    │  │ Module    │  │ Module    │       │
│  │           │  │ (runners) │  │ (YAML)    │       │
│  │ Depends on│─→│ Depends on│  │ No deps   │       │
│  │ Core, LLM │  │ Core      │  │           │       │
│  └───────────┘  └───────────┘  └───────────┘       │
└─────────────────────────────────────────────────────┘
```

**Rules:**
1. Each module has a public API (explicit exports). No reaching into another module's internals.
2. Dependencies flow one direction: API → Core → Memory. Never reverse.
3. Integrations depend on Core interfaces, never on API or other integrations.
4. Agents depend on Core and LLM, never on integrations directly (use runner registry).

This is achievable with Python's existing module system — no new dependencies required. It's the path taken by Basecamp (Ruby), Shopify (Ruby), and Stripe (Ruby/Java) before microservices.

---

## 7. Framework Comparisons

### 7.1 Comparison Table

| Feature | SAGE | LangGraph | CrewAI | AutoGen/AG2 | Swarm | DSPy | Haystack | Claude SDK |
|---|---|---|---|---|---|---|---|---|
| **Agent definition** | YAML | Code (StateGraph) | YAML + Code | Code | Code | Code (signatures) | Code (pipeline) | Code |
| **Concurrency** | Single lock | Async checkpoints | Sequential/Hierarchical | Async messages | Sync handoffs | N/A | Async pipeline | Async |
| **State persistence** | SQLite + audit | Checkpointer (Postgres/SQLite) | Memory module | None built-in | None | None | Document stores | None built-in |
| **HITL gates** | Proposal queue + Slack | `interrupt_before` | `human_input_mode` | Human proxy agent | None | None | None | `human` tool |
| **Extension model** | BaseRunner + YAML skills | Custom nodes | Custom tools | Code agents | Function handoffs | Modules | Components | Tool definitions |
| **Multi-LLM** | Yes (7 providers) | Via LangChain | Via LangChain | Via AutoGen config | OpenAI only | Via LM clients | Via model adapters | Claude only |
| **Audit trail** | Full (SQLite + trace_id) | Via LangSmith | Via CrewAI+ | None | None | None | None | None |
| **Domain runners** | 11 specialized | None | None | None | None | None | None | None |
| **Production use** | Regulated industries | General purpose | General teams | Research | Prototype | ML pipelines | Search/RAG | General purpose |

### 7.2 Key Takeaways from Each Framework

**LangGraph** — Best-in-class state management. Its `Checkpointer` pattern (save/restore graph state at any node) is worth studying. SAGE's `_checkpoint()` method in BuildOrchestrator does similar work but in a less formalized way.

**CrewAI** — Closest to SAGE in philosophy (YAML agents, role-based). But CrewAI lacks domain runners, audit trails, and regulated-industry support. SAGE's approach is strictly more capable.

**AutoGen/AG2** — Conversation-based multi-agent is elegant for research but difficult to audit. In regulated industries, you need to trace "which agent decided what and why" — AutoGen's chat-based approach makes this hard.

**OpenAI Swarm** — Minimal and educational. The "handoff" pattern (one agent transfers control to another) is simpler than SAGE's queue-based dispatch but doesn't support parallel execution or audit trails.

**DSPy** — Fundamentally different: it optimizes prompts programmatically. Not an agent framework. However, SAGE's MetaOptimizer has overlap with DSPy's optimization philosophy — could be a future integration point.

**Haystack** — Pipeline-based, focused on RAG and search. The `Component` protocol is analogous to SAGE's `BaseRunner`. Haystack 2.0's pipeline composition is elegant.

**Claude Agent SDK** — Lightweight, tool-focused. The `human` tool for HITL is minimal but effective. SAGE's proposal queue is more sophisticated for regulated workflows.

### 7.3 Subsystem Pattern Deep-Dive

#### LLM Gateway Concurrency Models

| Model | How It Works | Used By | When Right for SAGE |
|---|---|---|---|
| **Single lock (mutex)** | One inference at a time, all agents queue | SAGE (`threading.Lock`) | CLI providers (Gemini CLI, Claude Code) — the CLI itself is the serialization point |
| **Connection pool / semaphore** | N concurrent connections, semaphore controls concurrency | LiteLLM, most production frameworks | API providers (Anthropic API, Ollama HTTP) with server-side concurrency |
| **Async (asyncio)** | Non-blocking I/O, event loop handles many requests | LangChain async, Haystack | Best throughput for I/O-bound LLM calls; requires async-compatible stack |
| **Worker processes** | Separate processes communicate via queue | Distributed AutoGen | Local model inference where you need CPU/GPU isolation |

Key insight: SAGE's single lock is not inherently wrong — it's a deliberate choice that simplifies reasoning about concurrent state. The bottleneck is LLM inference time (seconds to minutes), not lock acquisition (microseconds). The lock only becomes a problem when using API-based providers with high concurrency limits.

#### Execution Sandbox Landscape

| Technology | Isolation | Startup | Capability | Example Users |
|---|---|---|---|---|
| **Docker** | Process + FS + network namespace | 1-5s | Full OS, GPU passthrough | SAGE runners, AutoGen |
| **Firecracker microVMs** | Full VM, minimal overhead | 125ms | Lightweight VM, strong isolation | E2B.dev, AWS Lambda |
| **gVisor** | Syscall interception | 1-3s | Same as Docker + intercepted syscalls | Google Cloud Run |
| **WASM** | Language-level sandbox | <10ms | Very fast, very limited (no FS, no network) | Experimental only |
| **tmux session** | None (same user, same FS) | Instant | Full system access | SAGE OpenTerminal |

SAGE's 3-tier cascade (OpenShell → Sandbox → OpenSWE) is well-designed: try most isolated first, fall back gracefully. The cascade is transparent to the agent — it doesn't know which tier executed its code.

#### Memory Tier Architecture (Emerging Consensus)

| Tier | Scope | Persistence | SAGE Implementation | Gap |
|---|---|---|---|---|
| **Short-term** | Single agent turn | In-process | Context window (implicit) | None |
| **Medium-term (session)** | Multi-turn task / build run | Session duration | ❌ Not explicit | Add per-build session memory that accumulates during workflow and summarizes to long-term at completion |
| **Long-term** | Cross-session, cross-agent | Permanent | vector_store + audit_log | None — this is SAGE's strength |

The missing **session memory tier** causes vector store pollution with intermediate state. The OpenTerminal runner's "proactive context summarization" already implements session memory for terminal tasks — generalizing this to all runners would be valuable.

### 7.4 What SAGE Has That Others Don't

1. **Domain-specific execution runners** (11 and growing) — no other framework has firmware cross-compilation, PCB DRC, SPICE simulation, etc.
2. **3-tier execution cascade** — graceful degradation from container → local → LLM-direct
3. **Compounding vector memory from human feedback** — the Memento pattern
4. **Agent Gym with Glicko-2 ratings** — measurable agent skill improvement via experimental verification (real compile/test/simulate, not LLM-judging-LLM)
4a. **Gym-as-Lab** — 3-tier grading (experimental 40% + LLM critic 30% + structural 30%), critic-refined acceptance criteria, optional human expert critic (2x weight), editable critic prompts
5. **Full audit trail for regulated industries** — ISO 13485 / IEC 62304 compatible
6. **YAML-only domain onboarding** — 3 files to define a complete agent team

### 7.4 What SAGE Should Borrow

| From | Pattern | Why |
|---|---|---|
| LangGraph | Formal checkpointer with pluggable backends | SAGE's checkpoint is ad-hoc; a formal Checkpointer interface would enable Postgres/Redis backends |
| DSPy | Prompt optimization loop | SAGE's MetaOptimizer is close; could adopt DSPy's metric-driven optimization |
| Haystack 2.0 | Typed pipeline connections | SAGE's runners pass dicts; typed inputs/outputs would catch integration errors earlier |
| Claude SDK | Lightweight `human` tool | For simple HITL, a tool-based approach is cleaner than a proposal queue |
| LangGraph | Async-first execution | SAGE is sync with threads; async would improve throughput without the concurrency bugs |

---

## 8. Anti-Patterns to Avoid

### 8.1 Active Anti-Patterns in SAGE

| Anti-Pattern | Where in SAGE | Severity | Fix |
|---|---|---|---|
| **God File** | `api.py` (5,717 lines, 174 endpoints) | High | Split into `routes/` modules |
| **Global Bottleneck** | `LLMGateway` single lock | High | Provider-aware semaphore |
| **Implicit Singletons** | `LLMGateway._instance`, `SageIntelligence._instance` | Medium | DI or explicit instantiation |
| **Stringly-Typed Errors** | Generic `except Exception` everywhere | Medium | Exception hierarchy |
| **Shared Mutable State** | In-memory fallback dict in VectorStore | Medium | Add locking or use `concurrent.futures` |

### 8.2 Anti-Patterns to Watch For

| Anti-Pattern | Description | SAGE Risk |
|---|---|---|
| **Chatty Agents** | Agents talk to each other via LLM calls instead of data passing | Low — SAGE uses queues, not agent-to-agent chat |
| **LLM as Router** | Using LLM inference for simple routing decisions | Low — AdaptiveRouter uses Q-learning, not LLM |
| **Test Pollution** | Singletons leaking state between tests | Medium — `_instance` must be reset in test fixtures |
| **Provider Lock-in** | Tight coupling to one LLM provider | Low — 7 providers supported via ABC |
| **Premature Microservices** | Splitting into services before outgrowing the monolith | Low — but resist the urge; modular monolith is the right next step |
| **God Agent** | One agent that handles every task type | Low — SAGE has 6 specialized agents + domain runners |

---

## 9. Recommendations

### 9.1 Priority 1 — Fix Now (High Impact, Low Effort)

#### R1: Provider-Aware LLM Concurrency
Replace `threading.Lock()` with `threading.Semaphore(n)`:
```python
# In LLMGateway.__init__:
PROVIDER_CONCURRENCY = {
    "local": 1, "ollama": 1,           # GPU-bound
    "gemini": 5, "claude": 5,          # Cloud APIs
    "claude-code": 3, "generic-cli": 2  # CLI tools
}
self._semaphore = threading.Semaphore(
    PROVIDER_CONCURRENCY.get(provider, 1)
)
```
**Effort:** ~20 lines changed. **Impact:** 3-5x throughput for cloud LLM providers.

#### R2: SQLite WAL Mode
Add `PRAGMA journal_mode=WAL` to every `sqlite3.connect()`:
```python
def _get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn
```
**Effort:** ~30 lines. **Impact:** Eliminates "database is locked" under concurrent writes.

#### R3: Split api.py into Route Modules
Use FastAPI's `APIRouter`:
```python
# src/interface/routes/build.py
from fastapi import APIRouter
router = APIRouter(prefix="/build", tags=["build"])

@router.post("/start")
async def start_build(...): ...
```
```python
# src/interface/api.py (reduced to ~200 lines)
from src.interface.routes import build, gym, knowledge, ...
app.include_router(build.router)
app.include_router(gym.router)
```
**Effort:** ~2-3 hours (mechanical refactor). **Impact:** Maintainability, code review, IDE performance.

### 9.2 Priority 2 — Build Soon (High Impact, Medium Effort)

#### R4: Circuit Breakers on Integration Boundaries
Wrap each external integration (Gemini CLI, Slack, Temporal, etc.) in a circuit breaker. After N consecutive failures, skip the integration for a cooldown period.

#### R5: Typed Runner Contracts
Replace dict-based `RunResult` with typed dataclasses:
```python
@dataclass
class RunResult:
    success: bool
    artifacts: list[Artifact]
    metrics: dict[str, float]
    trace_id: str
    duration_ms: int
```

#### R6: Connection Pooling for SQLite
Create a `DatabasePool` that manages connections per database file, with WAL mode and busy timeout pre-configured.

#### R7: Bounded In-Memory State
Add an eviction policy to `BuildOrchestrator._runs` and `QueueManager`:
- Completed runs: evict after 24 hours (persist to SQLite first)
- Active runs: keep in memory
- Failed runs: keep for 1 hour for debugging

#### R7.5: JSON Schema Validation for All YAML Files
SAGE's YAML-first approach (project.yaml, prompts.yaml, tasks.yaml, skills/*.yaml) is a differentiator. Add JSON Schema validation at load time to catch config errors at startup, not at runtime when an agent fails:
```python
# In project_loader.py or skill_loader.py:
import jsonschema
schema = load_schema("schemas/project.schema.json")
jsonschema.validate(yaml_data, schema)  # Fail fast at startup
```

### 9.3 Priority 3 — Plan for Future (Strategic)

#### R8: Async-First Migration
Migrate from sync threads to `asyncio` for the FastAPI path. This is a larger effort but eliminates the entire class of thread-safety issues.

#### R9: OpenTelemetry Integration
Replace custom audit trail with OpenTelemetry spans for distributed tracing. The audit log stays as the compliance record; OTel adds observability.

#### R10: CloudEvents Envelope
Wrap internal events in CloudEvents format for standardized event routing. This enables future integration with event-driven systems (n8n, Kafka, etc.).

#### R11: Formal Checkpointer Interface
Extract BuildOrchestrator's checkpoint logic into a `Checkpointer` protocol (inspired by LangGraph):
```python
class Checkpointer(Protocol):
    def save(self, run_id: str, state: dict) -> None: ...
    def load(self, run_id: str) -> dict | None: ...
    def list_checkpoints(self, run_id: str) -> list[str]: ...
```
Implementations: SQLiteCheckpointer (default), RedisCheckpointer (future), PostgresCheckpointer (future).

---

## 10. Evolution Roadmap

### Phase 1: Modular Monolith (Now → 1 month)
- [x] Split api.py into route modules (R3) — gym.py, research.py extracted
- [x] Provider-aware LLM semaphore (R1) — `PROVIDER_CONCURRENCY` map, 6 providers
- [x] SQLite WAL mode everywhere (R2) — `src/core/db.py` with `get_connection()`
- [x] Thread-safe vector store fallback (§5.6) — `_fallback_lock` on in-memory dict
- [x] Exception hierarchy (R5 partial) — `src/core/exceptions.py`, 10 typed exceptions

### Phase 2: Resilience (1 → 3 months)
- [ ] Circuit breakers on integrations (R4)
- [ ] Connection pooling (R6)
- [ ] Bounded in-memory state (R7)
- [ ] Typed runner contracts (R5)
- [x] OpenTelemetry spans (R9) — `src/core/tracing.py`, wired into LLM gateway

### Phase 3: Protocol Standards (3 → 6 months)
- [x] CloudEvents envelope (R10) — `src/modules/cloud_events.py`, v1.0 spec, EventBus integration
- [ ] Formal Checkpointer interface (R11)
- [ ] Async-first migration (R8)
- [ ] A2A (Google Agent-to-Agent) for cross-framework interop

### Phase 4: Scale (6+ months)
- [ ] Optional Redis/Postgres backends (via Checkpointer)
- [ ] Worker process pool (for CPU-bound tasks)
- [ ] Rate limiting + quotas per tenant
- [ ] Multi-node deployment (only if operator count justifies it)

---

## Appendix: Code References

### Key Files by Concern

| Concern | File | Lines | Notes |
|---|---|---|---|
| API surface | `src/interface/api.py` | 5,717 | Needs splitting (R3) |
| LLM abstraction | `src/core/llm_gateway.py` | 1,166 | Single lock bottleneck (R1) |
| Task orchestration | `src/integrations/build_orchestrator.py` | 2,878 | AdaptiveRouter + waves |
| Agent training | `src/core/agent_gym.py` | 1,297 | Glicko-2 + spaced repetition |
| Skill registry | `src/core/skill_loader.py` | ~400 | YAML hot-reload |
| Runner base | `src/integrations/base_runner.py` | 692 | ABC for all domain runners |
| Audit | `src/memory/audit_logger.py` | ~400 | SQLite append-only |
| Vector memory | `src/memory/vector_store.py` | ~400 | ChromaDB + fallback |
| Queue | `src/core/queue_manager.py` | 1,209 | 6 locks, in-memory |
| Proposals | `src/core/proposal_store.py` | ~300 | SQLite-backed |
| Exercise seeds | `src/core/exercise_seeds.py` | 3,552 | 661 exercises, 11 domains |

### Singleton Instances

| Singleton | File | Thread-Safe? |
|---|---|---|
| `LLMGateway` | `llm_gateway.py:738` | Yes (explicit lock) |
| `SageIntelligence` | `sage_intelligence.py:51` | No (no lock on `_instance`) |
| `project_config` | `project_loader.py` | Module-level, immutable after load |

### Lock Inventory

| Lock | File | Protects |
|---|---|---|
| `LLMGateway._lock` | `llm_gateway.py:572` | All LLM inference (bottleneck) |
| `QueueManager._lock` | `queue_manager.py` | Task queue state |
| `QueueManager._task_lock` | `queue_manager.py` | Individual task updates |
| `QueueManager._priority_lock` | `queue_manager.py` | Priority queue |
| `QueueManager._dep_lock` | `queue_manager.py` | Dependency tracking |
| `QueueManager._wave_lock` | `queue_manager.py` | Wave execution state |
| `QueueManager._schedule_lock` | `queue_manager.py` | Scheduled tasks |
| `AgentGym._lock` | `agent_gym.py` | Training session state |

---

## Document History

| Date | Author | Change |
|---|---|---|
| 2026-03-31 | Claude (Architecture Study) | Initial comprehensive review |
