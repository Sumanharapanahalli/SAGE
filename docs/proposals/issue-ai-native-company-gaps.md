# SAGE Framework — AI-Native Company Gap Backlog

> Scope: `sage` (framework improvements)
> Source: Strategic gap analysis — 2026-03-15
> Priority tiers: T1 = enterprise blockers, T2 = expected platform features, T3 = moat/differentiation

---

## T1-001 — Authentication, RBAC & Named Approvals

**Priority:** T1 — Blocks regulated industry adoption entirely

**Problem:**
Any anonymous API call can currently approve a proposal. There is no concept of "who" approved, only "that" it was approved. Regulated industries (medtech, fintech, pharma, defence) require named approvals with person identity in the audit record.

**Scope of work:**
- SSO/OIDC integration (Okta, Azure AD, Google Workspace)
- Named approvals — audit log records `approved_by: user@company.com`
- RBAC: viewer / operator / approver / admin roles, scoped per solution
- API key management for service accounts
- Session management in the web UI (login/logout)

**Acceptance criteria:**
- Audit log entry for every approval includes `approved_by`, `approver_role`, `approver_email`
- Unauthenticated calls to `/approve/*` and `/reject/*` return 401
- Role assignment is per-solution (same user can be admin on `medtech`, viewer on `starter`)

---

## T1-002 — PII Detection, Redaction & Data Residency Controls

**Priority:** T1 — Blocks legal/security sign-off at most enterprises

**Problem:**
Prompts containing customer data, health records, or financial data are sent to LLMs with no PII scrubbing. European customers need guarantees that data does not leave their region.

**Scope of work:**
- PII detection pipeline before every `gateway.generate()` call (presidio or equivalent)
- Configurable redaction: mask, replace with placeholder, or block entirely
- Data residency config: `data_residency: EU` routes only to EU-region models
- GDPR right-to-erasure: compliant answer for audit log (pseudonymisation strategy)
- Output content filtering: block LLM responses containing injected PII

**References:**
- Microsoft Presidio (open-source, self-hostable)
- Integrate at `src/core/llm_gateway.py` pre-call hook

---

## T1-003 — Production Deployment: Kubernetes, Secrets Management, Scaling

**Priority:** T1 — Blocks IT/infra adoption

**Problem:**
Current deployment is Docker Compose with `.env` file secrets. Enterprise IT needs Kubernetes-native deployment, external secrets management, and a documented scaling story.

**Scope of work:**
- Helm chart with configurable replicas, resource limits, health/readiness probes
- Secrets management integration: HashiCorp Vault, AWS Secrets Manager, Azure Key Vault
- Document horizontal scaling model: what is safe to scale, what must stay singleton (LLMGateway lock)
- SQLite → Postgres migration path for audit log and task queue
- Graceful shutdown handling

---

## T1-004 — LLM Cost Tracking, Budget Controls & Model Routing

**Priority:** T1 — Blocks CFO/finance approval for broad rollout

**Problem:**
There is no visibility into how much LLM usage costs per team, per solution, or per day. No mechanism to prevent runaway spend or route cheap tasks to cheap models.

**Scope of work:**
- Per-tenant token tracking with estimated cost (using public model pricing tables)
- Budget limits: soft alert + hard cutoff at configurable thresholds
- Cost dashboard in web UI (daily/weekly/monthly by solution and tenant)
- Model routing by task type: configure `analyst` to use `ollama/llama3.2` and `developer` to use `gemini-2.5-pro`
- Cost reporting API: `GET /costs/summary?tenant=X&period=30d`

---

## T2-005 — Document Ingestion Pipeline

**Priority:** T2 — Without this, RAG context stays shallow (only manually added knowledge)

**Problem:**
Every company has existing knowledge in Confluence, Notion, SharePoint, Google Drive, and PDFs. SAGE has a vector store but no automated way to populate it from these sources.

**Scope of work:**
- Connectors: Confluence, Notion, SharePoint, Google Drive, PDF upload endpoint
- Chunking + embedding pipeline with configurable chunk size and overlap
- Incremental sync: re-index only changed documents
- Document versioning: track source URL, last-indexed timestamp, content hash
- `DELETE /knowledge/source/{source_id}` to purge a document and its chunks
- Scheduled re-indexing (cron-based)

**Integration path:**
Use **Composio** or **LlamaIndex readers** for connector implementations — avoids building each connector from scratch. See also T2-008 (integration catalog).

---

## T2-006 — Approval Collaboration: Comments, Multi-Approver, Delegation

**Priority:** T2 — Required for team-scale use beyond one-person approvals

**Problem:**
Approval is currently binary (one person, approve or reject). Real teams need discussion before acting, multiple sign-offs for high-risk changes, and out-of-office routing.

**Scope of work:**
- Comments on proposals (thread attached to trace_id)
- Multi-approver workflows: require N-of-M approvals before executing
- Approval delegation: "while I'm away, route my approvals to @colleague"
- @mention notifications to pull in subject matter experts
- Email digest: daily summary of pending approvals
- Push notifications via Slack/Teams (already partially supported)

---

## T2-007 — Visual Workflow Builder (No-Code LangGraph Editor)

**Priority:** T2 — Required to reach non-engineering teams

**Problem:**
LangGraph workflows require Python. Business analysts, operations teams, and domain experts cannot define automation logic without developer involvement.

**Scope of work:**
- Drag-and-drop workflow canvas in the web UI
- Node types: agent task, HITL gate, condition branch, parallel fan-out, merge
- Export to Python LangGraph code (round-trip: edit visually or in code)
- Workflow template library (approval chain, escalation ladder, multi-agent review)
- Live workflow execution view (see which node is active)

---

## T2-008 — Integration Catalog Expansion via Composio + MCP

**Priority:** T2 — Limits reach to engineering teams only without broader connectors

**Problem:**
Current integrations cover engineering (GitLab, Slack, Teams) but miss every other business function. Building individual connectors is slow.

**Recommended approach — single package for maximum coverage:**

**[Composio](https://composio.dev)** is the best single addition:
- 100+ pre-built tool integrations specifically designed for AI agents
- Handles OAuth flows automatically (no per-integration auth code)
- Works natively with LangChain (already in SAGE via `langchain_tools.py`)
- Covers: Jira, Linear, GitHub, Salesforce, HubSpot, Notion, Google Workspace, Slack, and 90+ more
- Self-hostable option available

**Complement with n8n (already in SAGE):**
- n8n covers 400+ integrations as trigger sources and action targets
- Already integrated at `POST /webhook/n8n` — extend bidirectionally (SAGE → n8n → external system)

**Combined coverage:**
```
MCP servers       → custom/internal tools (already built)
Composio          → SaaS business tools (Jira, Salesforce, Notion, GitHub...)
n8n               → enterprise/legacy systems + complex multi-step automations
```

**Scope of work:**
- Add `ComposioToolSet` loader to `src/integrations/langchain_tools.py`
- Allow solutions to declare `integrations: [composio:jira, composio:salesforce]` in `project.yaml`
- Extend n8n integration to support outbound calls (SAGE triggers n8n workflows, not just receives)
- MCP server registry: publish community-contributed MCP servers per industry vertical

---

## T2-009 — Reporting & ROI Dashboard

**Priority:** T2 — Required for executive sponsorship and expansion budget

**Problem:**
There is no way to answer "what value has SAGE delivered?" — a question every manager and CFO will ask within 90 days of deployment.

**Scope of work:**
- Executive dashboard page: proposals generated, approval rate, avg time-to-decision, errors caught
- Per-agent quality trending: is agent accuracy improving week-over-week?
- Estimated time saved: configurable "this task type normally takes X minutes manually"
- ROI export: PDF or CSV report for a given period
- Cross-solution comparison: which team gets the most value?
- `GET /reports/summary?period=30d&solution=all` API endpoint

---

## T3-010 — Solution Marketplace / Registry (APM Vision)

**Priority:** T3 — Largest long-term network effect and moat

**Problem:**
Every company building a medtech solution starts from scratch. There is no way to share, discover, or version solution packages across organisations.

**Scope of work:**
- Public registry: `sage search medtech-compliance` returns community solutions
- Version pinning: `sage install medtech-iso13485@2.1.0`
- Private registries: enterprises share solutions internally across business units
- Dependency declaration: a solution can depend on another (`depends_on: base-compliance-v1`)
- Verified publisher badges for quality-reviewed solutions
- CLI: `sage publish`, `sage install`, `sage update`

---

## T3-011 — Prompt CI/CD: Eval Gates Before Hot-Reload

**Priority:** T3 — Quality differentiation, prevents regressions in production

**Problem:**
Prompt changes via the YAML editor hot-reload immediately with no regression check. A bad prompt edit can silently degrade all future analyses.

**Scope of work:**
- Eval suite runs automatically before any `prompts.yaml` change takes effect
- PR-style workflow: proposed change → run evals → show pass/fail diff → confirm apply
- Regression detection: "this change would fail 3 of your 12 existing eval cases"
- A/B prompt testing: run two variants in parallel, auto-promote winner based on approval rate
- Eval coverage badge in YAML editor: "8/12 cases passing"

---

## T3-012 — Multi-Agent Coordination

**Priority:** T3 — Enables complex cross-functional automation

**Problem:**
Agents today operate independently. Real AI-native workflows require agents that hand off to each other, cross-validate results, and collaborate on a shared goal.

**Scope of work:**
- Agent-to-agent task delegation with HITL gate between each handoff
- Supervisor agent: decomposes a high-level goal into subtasks, assigns to specialist agents
- Parallel execution with merge step: fan out to 3 agents, merge results with consensus check
- Cross-validation: two agents review same output, human only sees result if they agree
- Visual execution trace in Live Console: see the full agent collaboration graph

---

## T3-013 — Mobile Approval Interface

**Priority:** T3 — Required for operations, manufacturing, field teams

**Problem:**
Approvals require a desktop browser. Operations managers on the factory floor or in the field cannot act on proposals without going to a computer.

**Scope of work:**
- Mobile-first approval UI (PWA — no app store required)
- Push notifications: proposal arrives → phone notification → approve in 2 taps
- Offline-capable: queue approvals locally, sync when reconnected
- Voice approval option for hands-free environments
- Responsive redesign of the existing web UI as foundation

---

## T3-014 — Adaptive Solution Improvement (Closed-Loop Prompt Learning)

**Priority:** T3 — The compounding intelligence flywheel made fully automatic

**Problem:**
SAGE collects human feedback (approvals/rejections) but prompt improvements still require a human to review the audit log and manually edit `prompts.yaml`. The loop is not fully closed.

**Scope of work:**
- Pattern detection: cluster rejection reasons from the audit log
- Auto-suggest prompt improvements: "Your analyst is rejected 34% of the time for network errors — here's a suggested prompt update"
- Generate eval cases automatically from past approved/rejected proposals
- Weekly improvement digest: "3 prompt improvements are ready for your review"
- One-click apply with automatic eval validation before hot-reload

---

## Implementation Notes

- All T1 items should be treated as pre-requisites for any enterprise deal
- T2-008 (Composio integration) is the highest ROI item per engineering day — one package unlocks 100+ integrations
- T3-010 (marketplace) should be designed early even if not implemented — solution YAML format decisions made now will be hard to change later
- All items should follow the SAGE HITL pattern — even framework configuration changes (like adding an integration) should go through a proposal/approve flow
