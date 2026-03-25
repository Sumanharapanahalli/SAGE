# SAGE — Best-of-Breed Framework Integration Strategy
*Last updated: 2026-03-24 — includes 2025/2026 ecosystem review*

**Goal:** Keep SAGE's unique compliance layer intact while replacing its weaker internals
with best-in-class open-source components. Don't reinvent — integrate.

---

## Core Principle: What SAGE Owns vs What Others Do Better

```
┌──────────────────────────────────────────────────────────────────────┐
│                      SAGE OWNS (never outsource)                     │
│  ✅ Immutable audit log           ✅ Human approval gate              │
│  ✅ Compounding feedback loop     ✅ YAML-first solution isolation     │
│  ✅ Trace ID correlation system   ✅ React dashboard                  │
└──────────────────────────────────────────────────────────────────────┘
     │           │           │           │           │           │
     ▼           ▼           ▼           ▼           ▼           ▼
 LangGraph   LlamaIndex   MCP std   LangChain   AutoGen    Langfuse
(orchestrate)  (RAG)     (tools)   (ecosystem)  (code)   (observability)
```

Every external framework's output still flows through:
`propose → audit → human decision → compound`

---

## Complete Integration Map (Updated)

| SAGE Layer | Current | Best Option | Alternative | Why |
|---|---|---|---|---|
| **Observability** | Nothing | **Langfuse** | LangSmith, Arize | LLM tracing, cost tracking, evals |
| **Tool interface standard** | Custom MCP | **MCP (official)** | OpenAPI | Industry standard as of Dec 2025 |
| **RAG / Vector Memory** | ChromaDB + MiniLM | **LlamaIndex** | pgvector | Better chunking, re-ranking, loaders |
| **Tool integrations** | Custom Python | **LangChain Tools** | Composio (multi-tenant) | 100s of pre-built connectors |
| **Long-term memory** | Feedback loop only | **mem0** | Zep | Multi-session personalized memory |
| **Event / triggers** | Polling agents | **n8n** | Temporal triggers | 400+ connectors, no polling code |
| **Orchestration** | SQLite queue | **LangGraph** | Temporal (HA), Prefect | Conditional branching, graph state |
| **Agent typing** | Custom classes | **Pydantic AI** | Keep custom | Type safety + durable execution |
| **Code agents** | Basic developer | **AutoGen + OpenHands** | smolagents (minimal) | Write→run→fix loop, sandboxed |
| **Multi-modal** | Text only | **Agno** | Keep LangGraph | Image/video/audio if needed |

---

## The Two Critical Gaps in the Original Strategy

### Gap 1 — Observability (Langfuse) — Add This First

The original strategy had no observability layer. This is a production blocker.

**Langfuse** (self-hosted, open source) gives you:
- Structured trace of every LLM call: prompt, response, tokens, latency
- Cost tracking per solution, per agent, per user
- LLM-as-a-Judge evals to auto-verify proposals before human review
- Kubernetes/Helm deployment — no vendor lock-in
- Free: 1M trace spans/month

**Where it plugs in:** one line in `LLMGateway.generate()`:

```python
# src/core/llm_gateway.py
from langfuse import Langfuse
langfuse = Langfuse()   # reads LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY from env

def generate(self, prompt: str, system_prompt: str = "") -> str:
    with self._lock:
        trace = langfuse.trace(name="llm_generate", metadata={"provider": self._provider_name})
        generation = trace.generation(name="generate", input=prompt, model=self._model_name)
        result = self.provider.generate(prompt, system_prompt)
        generation.end(output=result)
        return result
```

**Config addition:**
```yaml
# config/config.yaml
observability:
  langfuse_enabled: true
  langfuse_host: "http://langfuse:3000"    # self-hosted
```

---

### Gap 2 — MCP as the Native Tool Standard

MCP (Model Context Protocol) was donated to the Agentic AI Foundation in December 2025
and is now the official cross-vendor standard. SAGE already uses custom MCP servers in
`solutions/<name>/tools/`. The gap is treating them as one-off scripts rather than
standard MCP servers registered with the official Registry.

**Why it matters:**
- Every major LLM provider now speaks MCP natively (Anthropic, OpenAI, Google)
- Anthropic's Tool Search lets agents auto-discover tools at runtime
- Community MCP servers exist for most services (Jira, Slack, GitHub, Confluence)
- No need to write custom tool code for common integrations

**Adoption path:**
1. Migrate existing custom tools to proper MCP server format
2. Add MCP server discovery to `UniversalAgent`
3. Replace LangChain tool wrappers with MCP server calls where servers exist

```python
# src/core/mcp_registry.py (new file)
import json, subprocess

class MCPRegistry:
    """Discovers and invokes MCP servers for the active solution."""

    def list_tools(self, solution: str) -> list[dict]:
        """Return all tools available from solution's MCP servers."""
        tools_dir = f"solutions/{solution}/tools"
        # Load tool manifests from each MCP server
        ...

    def invoke(self, server: str, tool: str, args: dict) -> dict:
        """Call an MCP tool. Always audited by the caller."""
        result = subprocess.run(
            ["node", f"solutions/{solution}/tools/{server}/index.js"],
            input=json.dumps({"tool": tool, "args": args}),
            capture_output=True, text=True
        )
        return json.loads(result.stdout)
```

---

## Integration 1 — Langfuse (Phase 0 — Before Everything Else)

**Risk:** Low. **Value:** High. **Effort:** Hours.

Wire into `LLMGateway.generate()` as shown above. Also trace:
- Agent proposals (on every `audit_logger.log_event()` call)
- Approval/rejection events (on `/approve` and `/reject`)
- Vector memory searches (on `vector_memory.search()`)

This gives end-to-end visibility from human input → LLM call → proposal → decision.

**Install:**
```bash
pip install langfuse
docker run -d langfuse/langfuse:latest   # self-hosted
```

---

## Integration 2 — LlamaIndex as Memory & RAG Layer (Phase 1)

**Risk:** Low. **Value:** High. **Effort:** 1–2 days.

Replace `VectorMemory._initialize_db()` with a LlamaIndex backend.
The `search()` / `add_feedback()` interface stays unchanged — no agent code changes.

```python
# src/memory/vector_store.py — LlamaIndex backend
class LlamaIndexVectorStore(VectorMemory):
    def _initialize_db(self):
        from llama_index.core import VectorStoreIndex, StorageContext
        from llama_index.vector_stores.chroma import ChromaVectorStore
        import chromadb

        client = chromadb.PersistentClient(path=str(self._db_path))
        collection = client.get_or_create_collection(self._collection_name)
        self._index = VectorStoreIndex(
            [],
            storage_context=StorageContext.from_defaults(
                vector_store=ChromaVectorStore(chroma_collection=collection)
            )
        )
        self._ready = True

    def search(self, query: str, k: int = 3) -> list[str]:
        nodes = self._index.as_retriever(similarity_top_k=k).retrieve(query)
        return [n.get_content() for n in nodes]

    def add_feedback(self, text: str, metadata: dict = None):
        from llama_index.core import Document
        self._index.insert(Document(text=text, metadata=metadata or {}))
```

**Bonus — document ingestion:**
```python
# src/integrations/document_ingestion.py
from llama_index.readers.gitlab import GitLabReader
from llama_index.readers.confluence import ConfluenceReader
from llama_index.readers.file import PDFReader

def ingest_sources(solution: str):
    """Pull docs from all configured sources into vector memory."""
    # GitLab wiki, Confluence spaces, local PDFs (ISO standards, SOPs, etc.)
    ...
```

**Config:**
```yaml
memory:
  backend: "llamaindex"       # "chroma" (default) | "llamaindex"
  rerank: true
  ingestion:
    sources:
      - type: "gitlab_wiki"
      - type: "local_dir"
        path: "solutions/{project}/docs"
      - type: "confluence"
```

---

## Integration 3 — mem0 for Long-Term Agent Memory (Phase 1 — Optional)

**Risk:** Low. **Value:** Medium (only if multi-session memory is required).

LlamaIndex is great for document retrieval. mem0 adds *personalized* memory:
"this engineer always prefers root-cause first, recommendation second."
"this project never approves firmware flash without a test report."

```python
# src/memory/long_term_memory.py (new file)
from mem0 import Memory

class LongTermMemory:
    def __init__(self, solution: str):
        self._mem = Memory()
        self._solution = solution

    def remember(self, text: str, user_id: str, metadata: dict = None):
        """Store a preference or pattern for a specific user/project."""
        self._mem.add(text, user_id=user_id, metadata=metadata or {})

    def recall(self, query: str, user_id: str, limit: int = 5) -> list[str]:
        """Retrieve relevant memories for a user/project."""
        results = self._mem.search(query, user_id=user_id, limit=limit)
        return [r["memory"] for r in results["results"]]
```

Usage in agents — inject into context before every LLM call:
```python
# Before generating proposal
user_memories = long_term_memory.recall(query=log_entry, user_id=actor)
context_injection = "\n".join(user_memories)
```

---

## Integration 4 — LangChain Tools (Phase 1) + Composio Path (Future)

**Phase 1 (Internal single-tenant):** LangChain community tools.

```python
# src/integrations/langchain_tools.py
from langchain_community.tools import JiraAPIWrapper, ConfluenceAPIWrapper
from langchain_community.utilities import SQLDatabase
from langchain_community.tools import QuerySQLDataBaseTool

def get_tools_for_solution(solution_name: str) -> dict:
    tools = {}
    integrations = project_config.metadata.get("integrations", [])

    if "jira" in integrations:
        jira = JiraAPIWrapper()
        tools["search_jira"] = lambda q: jira.run(f"search: {q}")
        tools["create_jira_issue"] = lambda s, d: jira.run(f"create issue: {s} — {d}")

    if "confluence" in integrations:
        tools["search_confluence"] = ConfluenceAPIWrapper().run

    if "database" in integrations:
        db = SQLDatabase.from_uri(os.environ["DATABASE_URL"])
        tools["query_database"] = QuerySQLDataBaseTool(db=db).run

    return tools
```

**Future (multi-tenant SaaS):** Migrate to **Composio** — handles per-user OAuth,
token refresh, and tenant isolation automatically. 500+ tools, production-hardened.
Plan this migration when SAGE scales to serve multiple customer organizations.

---

## Integration 5 — n8n as Event / Trigger Layer (Phase 2)

**Risk:** Low. **Value:** High (eliminates all custom polling code).

n8n detects events from any system and calls SAGE's REST API. SAGE focuses on
reasoning; n8n handles connectivity.

```
PagerDuty alert      ─┐
Jira issue created   ─┤
GitLab push event    ─┤──▶ n8n workflow ──▶ POST /analyze ──▶ SAGE approval loop
Slack message        ─┤                      or /tasks/submit
Cron schedule        ─┘
```

**n8n HTTP Request node:**
```json
{
  "method": "POST",
  "url": "http://sage-backend:8000/analyze",
  "body": {
    "log_entry": "{{ $json.alert_description }}",
    "source": "{{ $json.source_system }}",
    "metadata": { "triggered_by": "n8n", "workflow_id": "{{ $workflow.id }}" }
  }
}
```

**Config:**
```yaml
monitor:
  mode: "n8n"           # "polling" | "n8n" | "both"
  n8n_webhook_secret: "${N8N_WEBHOOK_SECRET}"
```

---

## Integration 6 — LangGraph as Orchestration Engine (Phase 3)

**Risk:** Medium. **Value:** High. **Effort:** 1 week.

Replaces SAGE's linear queue with a state machine that supports conditional branching,
parallel execution, and human-in-the-loop interrupts — which map directly to SAGE's
approval gate.

```python
# src/integrations/langgraph_runner.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from src.memory.audit_logger import AuditLogger

audit = AuditLogger()

def build_analysis_workflow():
    graph = StateGraph(AnalysisState)

    graph.add_node("analyze", run_analyst_agent)
    graph.add_node("plan", run_planner_agent)
    graph.add_node("execute", run_developer_agent)
    graph.add_node("human_review", wait_for_approval)   # Maps to SAGE's approval gate

    graph.add_edge("analyze", "plan")
    graph.add_edge("plan", "human_review")
    graph.add_conditional_edges(
        "human_review",
        lambda s: "execute" if s["approved"] else END
    )

    # Checkpoint to SQLite — survives restarts
    checkpointer = SqliteSaver.from_conn_string("solutions/{project}/data/checkpoints.db")
    return graph.compile(checkpointer=checkpointer, interrupt_before=["human_review"])
```

**Every node transition is audited before it happens.** LangGraph's `interrupt_before`
fires before the approval node — SAGE captures the pending state and waits for human
input at `/approve/{trace_id}` as normal.

---

## Integration 7 — Pydantic AI for Type-Safe Agents (Phase 3 — Optional)

Pydantic AI is philosophically aligned with SAGE:
- Mandatory human approval gate (built-in, not bolted on)
- Durable execution with Temporal (agents survive restarts)
- Type safety catches errors at write-time, not runtime
- Native MCP support

Use it as a drop-in for `UniversalAgent` when refactoring for Phase 3:

```python
# src/agents/universal_typed.py
from pydantic_ai import Agent
from pydantic import BaseModel

class AgentProposal(BaseModel):
    summary: str
    analysis: str
    recommendations: list[str]
    severity: Literal["RED", "AMBER", "GREEN"]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    next_steps: list[str]

typed_agent = Agent(
    "claude-sonnet-4-6",
    result_type=AgentProposal,       # Type-safe output — no JSON parsing failures
    system_prompt="You are a {role}. Analyze the input and respond with a structured proposal."
)
```

The `AgentProposal` return type guarantees the shape of every proposal — no more
`extract_json()` fragility.

---

## Integration 8 — AutoGen + OpenHands for Code Agents (Phase 4)

**Risk:** High (code execution). **Value:** High. **Effort:** 1 week + Docker setup.

Use AutoGen for multi-agent team orchestration. Use OpenHands as the sandboxed
code execution worker inside the team.

```
AutoGen Orchestrator
  ├── AnalyzerAgent   — reads the bug report
  ├── CoderAgent      — writes the fix (OpenHands runtime)
  ├── TesterAgent     — runs tests, reports failures
  └── ReviewerAgent   — checks output against coding standards
        │
        ▼
  SAGE proposal — human approves before code is committed
```

```python
# src/integrations/autogen_runner.py
import autogen

def run_code_task(problem: str, trace_id: str) -> dict:
    """AutoGen writes, tests, iterates. SAGE governs the output."""
    config_list = [{"model": "claude-sonnet-4-6", "api_key": os.environ["ANTHROPIC_API_KEY"]}]

    engineer = autogen.AssistantAgent("Engineer", llm_config={"config_list": config_list})
    executor = autogen.UserProxyAgent(
        "Executor",
        human_input_mode="NEVER",
        code_execution_config={"work_dir": "/tmp/sage_sandbox", "use_docker": True}
    )

    result = executor.initiate_chat(engineer, message=problem, max_turns=8)

    # Audit every exchange
    for msg in result.chat_history:
        audit.log_event(actor=f"AutoGen_{msg['role']}", action_type="CODE_STEP",
                        input_context=problem, output_content=msg["content"][:2000],
                        metadata={"trace_id": trace_id})

    # Return as SAGE proposal — approval required before git commit
    return {"status": "pending_review", "trace_id": trace_id,
            "summary": result.summary, "action": "Review code, approve to commit"}
```

**Lighter alternative — smolagents:** If the use case is pure code generation
(no multi-agent team dynamics), Hugging Face's smolagents is cleaner and smaller
(<1,000 lines of framework code).

---

## Alternative Vector Store: pgvector

If your deployment already runs PostgreSQL (for audit log, project metadata, etc.),
**pgvector** is a natural fit over ChromaDB:

- **ACID compliant** — transactions, rollbacks, full consistency guarantees
- **Zero new infrastructure** — just a PostgreSQL extension
- **Better concurrent writes** — critical for multi-user production deployments
- **Familiar SQL interface** — team already knows Postgres

```python
# src/memory/vector_store.py — pgvector backend (alternative to LlamaIndex/ChromaDB)
from pgvector.psycopg2 import register_vector
import psycopg2, numpy as np

class PgVectorStore(VectorMemory):
    def _initialize_db(self):
        self._conn = psycopg2.connect(os.environ["DATABASE_URL"])
        register_vector(self._conn)
        with self._conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id SERIAL PRIMARY KEY,
                    content TEXT,
                    embedding vector(384),
                    metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        self._conn.commit()
        self._ready = True

    def search(self, query: str, k: int = 3) -> list[str]:
        embedding = self._embed(query)
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT content FROM memory ORDER BY embedding <-> %s LIMIT %s",
                (embedding, k)
            )
            return [row[0] for row in cur.fetchall()]
```

**Use pgvector if:** PostgreSQL is already your primary database.
**Use LlamaIndex/ChromaDB if:** You want a separate, dedicated vector store.

---

## Alternative Orchestration: Temporal.io

LangGraph is the right default for Phase 3. Consider Temporal only if you need:
- **99.99% uptime guarantees** (multi-region replication, automatic failover)
- **Workflows that run for days/weeks** (e.g., waiting for a hardware test result)
- **Strict exactly-once execution** (no duplicate task execution ever)

Temporal adds operational complexity (separate Temporal server, worker processes),
but maps cleanly to SAGE's task model: every SAGE task becomes a Temporal workflow,
every agent call becomes an activity, every approval gate becomes a signal.

**Decision:** LangGraph for Phase 3. Revisit Temporal if uptime SLAs require it.

---

## What NOT to Replace

These are SAGE's core moat — replacing them would make SAGE just another framework:

| Component | Why to keep it |
|---|---|
| **Audit logger** | Immutable SQLite record — ISO/FDA compliance depends on it |
| **Approval gate** (`/approve`, `/reject`) | The entire point of SAGE — agents propose, humans decide |
| **Feedback ingestion** (`learn_from_feedback`) | The compounding loop — measurable improvement over time |
| **YAML-first solutions** | Domain isolation — zero framework changes for new industries |
| **React dashboard** | The human interface to the approval gate |
| **Trace ID system** | Links audit log ↔ vector memory ↔ UI ↔ approvals end-to-end |

---

## Dependency Summary

```bash
# Phase 0 (Observability)
pip install langfuse

# Phase 1 (Memory, RAG, Tools)
pip install llama-index-core llama-index-vector-stores-chroma
pip install llama-index-readers-gitlab llama-index-readers-confluence
pip install langchain-community
pip install mem0ai                          # Optional: long-term memory

# Phase 2 (Events)
# n8n is external service — no Python deps

# Phase 3 (Orchestration)
pip install langgraph
pip install pydantic-ai                    # Optional: typed agents

# Phase 4 (Code Agents)
pip install pyautogen
# OpenHands runs as a Docker container — no Python package

# Alternative Vector Store (if on PostgreSQL)
pip install pgvector psycopg2-binary
```

---

## Integration Status — All Phases Complete

### Phase 0 — Observability
- [x] Langfuse wired into `LLMGateway.generate()` — every LLM call traced
- [x] Observability enabled via `config/config.yaml` `observability.langfuse_enabled`
- [x] Cost and latency visible per provider, per solution

### Phase 1 — Memory, RAG, Tools
- [x] LlamaIndex as vector store backend (`memory.backend: llamaindex`)
- [x] LangChain tools loaded per solution via `src/integrations/langchain_tools.py`
- [x] mem0 long-term memory via `src/integrations/long_term_memory.py`

### Phase 1.5 — MCP as Native Standard
- [x] MCP tool discovery and invocation via `src/integrations/mcp_registry.py`
- [x] MCP servers defined per solution in `solutions/<name>/mcp_servers/`

### Phase 2 — Event Layer
- [x] n8n webhook receiver at `POST /webhook/n8n` with HMAC-SHA256 verification
- [x] Event-to-task routing by `event_type` field
- [x] Monitor mode configurable: `mode: "n8n"` in config

### Phase 3 — Orchestration
- [x] LangGraph orchestration engine via `src/integrations/langgraph_runner.py`
- [x] `interrupt_before` maps to SAGE approval gate — `POST /workflow/resume`
- [x] SqliteSaver checkpoints (MemorySaver fallback)
- [x] Workflow YAML pattern documented — `solutions/<name>/workflows/`

### Phase 4 — Code Agents
- [x] AutoGen plan → approve → execute via `src/integrations/autogen_runner.py`
- [x] Docker sandboxed execution (`_run_in_docker`) with local subprocess fallback
- [x] `CODE_TASK` task type — requires human approval before execution

### Phases 5–11 — Additional Platform Features
- [x] Phase 5: SSE streaming — `POST /analyze/stream`, `POST /agent/stream`, `GET /logs/stream`
- [x] Phase 6: Onboarding wizard — `POST /onboarding/generate`, session-based, folder scanning
- [x] Phase 7: Knowledge base CRUD — `GET/POST/DELETE /knowledge/...`, bulk sync
- [x] Phase 8: Slack two-way approval — Block Kit + `POST /webhook/slack`
- [x] Phase 9: Eval & benchmarking — `POST /eval/run`, `GET /eval/history`
- [x] Phase 10: Multi-tenant isolation — `X-SAGE-Tenant` header + ContextVar
- [x] Phase 11: Temporal durable workflows + LangGraph fallback

### Phase 12 — Build Orchestrator
- [x] Phase 12.0: End-to-end product build pipeline — `POST /build/start`
- [x] Phase 12.1: Domain-aware build detection — 13+ domains with keyword matching
- [x] Phase 12.2: Workforce registry — 19 agents, 5 teams, 32 task types
- [x] Phase 12.3: Adaptive router — Q-learning agent selection per task type
- [x] Phase 12.4: Anti-drift checkpoints — `BUILD_DRIFT_WARNING` audit events

### Additional Platform Features (Post Phase 12)
- [x] Multi-LLM provider pool with parallel generation strategies (voting, fastest, fallback, quality)
- [x] Task routing by task type to different LLM providers
- [x] PII detection and data residency controls
- [x] Budget controls per solution and per role
- [x] OpenShell sandboxed code execution
- [x] Action-aware chat with audit trail
- [x] Org graph with knowledge channels and task routing
- [x] 136 API endpoints across 22 categories
- [x] 27 UI pages in 5-area sidebar
- [x] 53 test files including 58 system E2E tests

---

## Summary

```
                    SAGE (compliance layer — never changes)
                               │
        ┌──────────┬───────────┼────────────┬──────────────┬───────────────┐
        ▼          ▼           ▼            ▼              ▼               ▼
   Langfuse    LlamaIndex   MCP std    LangChain      LangGraph      AutoGen
  (Phase 0)    (Phase 1)  (Phase 1.5)  (Phase 1)      (Phase 3)     (Phase 4)
  observe all  smarter RAG  tool std   pre-built      conditional   code agents
  LLM calls    & doc ingest & discovery integrations   orchestration & sandboxed
                    +            +           +               +         execution
                  mem0         n8n       Composio        Pydantic AI  OpenHands
              (long-term)   (Phase 2)   (future,      (typed agents)  (sandbox)
               memory       event-driv  multi-tenant)
```

SAGE contributes what no other framework provides: the audit log, the approval gate,
and the compounding feedback loop. Everything else is best sourced from the ecosystem.
```