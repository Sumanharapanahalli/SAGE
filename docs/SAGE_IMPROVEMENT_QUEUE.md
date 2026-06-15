# SAGE Improvement Queue — run the loop on Gemini's findings

Each loop-ready item from Gemini's platform observation (`docs/SAGE_GEMINI_OBSERVATIONS.md`), as a ready-to-run Evaluator-Optimizer command (Claude fixes -> gemini-3.5-flash grades). Each result is a **proposal** — review the `OUT` file and apply it through the human approval gate. Run them one at a time so you review each.

```bash
# 1. Unblock concurrency: kill the thread-locked LLM gateway singleton (agent-framework)
make optimize TASK="Unblock concurrency: kill the thread-locked LLM gateway singleton — Remove the global lock; gate only local GPU models with a semaphore while letting API providers run concurrently via an async client (httpx). Convert the gateway from a sin" OUT=/tmp/sage_fix_1.txt

# 2. Establish UI primitives and collapse to one styling strategy (tokens via Tailwind) (web-reuse)
make optimize TASK="Establish UI primitives and collapse to one styling strategy (tokens via Tailwind) — Bootstrap web/src/components/ui/ (Button, Card, Modal, Select) built on Tailwind that consume the index.css CSS variables. Wire tokens into tailwind.config" OUT=/tmp/sage_fix_2.txt

# 3. Enforce single-source-of-truth components and extract shared logic (web-reuse)
make optimize TASK="Enforce single-source-of-truth components and extract shared logic — Delete the inline ProposalCard/ToastContainer copies and import the canonical components. Extract a useProposals hook (fetch/filter/approve/reject/batchApprove) and lib/da" OUT=/tmp/sage_fix_3.txt

# 4. Fix header status, color, and label consistency in the dashboard chrome (visual-ui)
make optimize TASK="Fix header status, color, and label consistency in the dashboard chrome — Consolidate status into one labeled colored dot ('Online'/'Offline') at >=4.5:1 contrast. Define a color strategy (one CTA accent, one status palette, neutral high-co" OUT=/tmp/sage_fix_4.txt

# 5. Decouple providers and make tracing always-on-but-pluggable (agent-framework)
make optimize TASK="Decouple providers and make tracing always-on-but-pluggable — Refactor all providers behind a common ABC (gemini via official SDK/REST, local, claude) so a mock provider can be injected in tests. Make instrumentation non-optional: propagate" OUT=/tmp/sage_fix_5.txt

# 6. Make the Evaluator-Optimizer loop self-sharpening with generated rubrics (agent-framework)
make optimize TASK="Make the Evaluator-Optimizer loop self-sharpening with generated rubrics — Add a Criteria Generation step: before the first optimization pass, have the high-capability evaluator/teacher model generate a task-specific rubric/checklist from t" OUT=/tmp/sage_fix_6.txt

```

## Manual (architecture — too large for one loop pass)

- **Decompose the src/core God-module into bounded contexts** (architecture) — Split src/core into bounded sub-packages (governance, execution, tenancy, compliance), migrating progressively starting with execution and governance. Pair with absolute path alias
- **Establish hard multi-tenant isolation and a unified observability stack** (architecture) — Re-architect to physical/virtual isolation (K8s namespaces or per-tenant container groups) as the default deployment target. Stand up a structured-logging schema feeding OpenTeleme

For UI-visual fixes, pair with `make ui-eval URL=<page>` so Gemini re-grades the rendered result.