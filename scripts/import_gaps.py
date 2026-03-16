"""Import the 14 AI-native company gap items into feature_requests table."""
import sqlite3
import uuid
from datetime import datetime, timezone

db = 'data/audit_log.db'
conn = sqlite3.connect(db)
now = datetime.now(timezone.utc).isoformat()

gaps = [
    ('t1-001', 'SAGE Framework', 'T1-001 — Authentication, RBAC & Named Approvals',
     'Any anonymous API call can currently approve a proposal. Regulated industries require named approvals with person identity in the audit record.\n\nScope: SSO/OIDC integration (Okta, Azure AD, Google Workspace); Named approvals in audit log; RBAC: viewer/operator/approver/admin roles scoped per solution; API key management; Session management in web UI.\n\nAcceptance criteria: Audit log entry includes approved_by, approver_role, approver_email; Unauthenticated calls return 401; Role assignment is per-solution.',
     'critical'),
    ('t1-002', 'SAGE Framework', 'T1-002 — PII Detection, Redaction & Data Residency Controls',
     'Prompts containing customer data, health records, or financial data are sent to LLMs with no PII scrubbing. European customers need data residency guarantees.\n\nScope: PII detection pipeline before every gateway.generate() call (presidio or equivalent); Configurable redaction; Data residency config (EU-region routing); GDPR right-to-erasure strategy; Output content filtering.\n\nReferences: Microsoft Presidio (open-source, self-hostable). Integrate at src/core/llm_gateway.py pre-call hook.',
     'critical'),
    ('t1-003', 'SAGE Framework', 'T1-003 — Production Deployment: Kubernetes, Secrets Management, Scaling',
     'Current deployment is Docker Compose with .env secrets. Enterprise IT needs Kubernetes-native deployment, external secrets management, and a documented scaling story.\n\nScope: Helm chart with configurable replicas, resource limits, health/readiness probes; Secrets management (HashiCorp Vault, AWS Secrets Manager, Azure Key Vault); Document horizontal scaling model (LLMGateway lock stays singleton); SQLite to Postgres migration path; Graceful shutdown handling.',
     'critical'),
    ('t1-004', 'SAGE Framework', 'T1-004 — LLM Cost Tracking, Budget Controls & Model Routing',
     'No visibility into LLM usage cost per team, solution, or day. No mechanism to prevent runaway spend or route cheap tasks to cheap models.\n\nScope: Per-tenant token tracking with estimated cost; Budget limits (soft alert + hard cutoff); Cost dashboard in web UI (daily/weekly/monthly); Model routing by task type; Cost reporting API: GET /costs/summary?tenant=X&period=30d.',
     'critical'),
    ('t2-005', 'SAGE Framework', 'T2-005 — Document Ingestion Pipeline',
     'Every company has existing knowledge in Confluence, Notion, SharePoint, Google Drive, and PDFs. SAGE has a vector store but no automated way to populate it.\n\nScope: Connectors for Confluence, Notion, SharePoint, Google Drive, PDF upload; Chunking + embedding pipeline; Incremental sync; Document versioning; DELETE /knowledge/source/{source_id}; Scheduled re-indexing.\n\nIntegration path: Use Composio or LlamaIndex readers for connector implementations.',
     'high'),
    ('t2-006', 'SAGE Framework', 'T2-006 — Approval Collaboration: Comments, Multi-Approver, Delegation',
     'Approval is currently binary (one person, approve or reject). Real teams need discussion before acting, multiple sign-offs for high-risk changes, and out-of-office routing.\n\nScope: Comments on proposals (thread attached to trace_id); Multi-approver workflows (N-of-M approvals); Approval delegation; @mention notifications; Email digest of pending approvals; Push notifications via Slack/Teams.',
     'high'),
    ('t2-007', 'SAGE Framework', 'T2-007 — Visual Workflow Builder (No-Code LangGraph Editor)',
     'LangGraph workflows require Python. Business analysts and operations teams cannot define automation logic without developer involvement.\n\nScope: Drag-and-drop workflow canvas in web UI; Node types: agent task, HITL gate, condition branch, parallel fan-out, merge; Export to Python LangGraph code (round-trip); Workflow template library; Live workflow execution view.',
     'high'),
    ('t2-008', 'SAGE Framework', 'T2-008 — Integration Catalog Expansion via Composio + MCP',
     'Current integrations cover engineering (GitLab, Slack, Teams) but miss every other business function. Building individual connectors is slow.\n\nScope: Composio integration (100+ pre-built tools, OAuth handled, LangChain-native); Extend n8n integration to support outbound calls; MCP server registry per industry vertical; Allow solutions to declare composio:jira in project.yaml.\n\nComposio covers: Jira, Linear, GitHub, Salesforce, HubSpot, Notion, Google Workspace, Slack, and 90+ more.',
     'high'),
    ('t2-009', 'SAGE Framework', 'T2-009 — Reporting & ROI Dashboard',
     'No way to answer "what value has SAGE delivered?" -- a question every manager and CFO will ask within 90 days of deployment.\n\nScope: Executive dashboard: proposals generated, approval rate, avg time-to-decision, errors caught; Per-agent quality trending; Estimated time saved; ROI export (PDF/CSV); Cross-solution comparison; GET /reports/summary?period=30d&solution=all.',
     'high'),
    ('t3-010', 'SAGE Framework', 'T3-010 — Solution Marketplace / Registry (APM Vision)',
     'Every company building a medtech solution starts from scratch. No way to share, discover, or version solution packages across organisations.\n\nScope: Public registry (sage search medtech-compliance); Version pinning (sage install medtech-iso13485@2.1.0); Private registries for enterprises; Dependency declaration; Verified publisher badges; CLI: sage publish, sage install, sage update.',
     'medium'),
    ('t3-011', 'SAGE Framework', 'T3-011 — Prompt CI/CD: Eval Gates Before Hot-Reload',
     'Prompt changes via the YAML editor hot-reload immediately with no regression check. A bad prompt edit can silently degrade all future analyses.\n\nScope: Eval suite runs automatically before any prompts.yaml change takes effect; PR-style workflow; Regression detection; A/B prompt testing; Eval coverage badge in YAML editor.',
     'medium'),
    ('t3-012', 'SAGE Framework', 'T3-012 — Multi-Agent Coordination',
     'Agents today operate independently. Real AI-native workflows require agents that hand off to each other, cross-validate results, and collaborate on a shared goal.\n\nScope: Agent-to-agent task delegation with HITL gate; Supervisor agent; Parallel execution with merge step; Cross-validation (two agents review same output); Visual execution trace in Live Console.',
     'medium'),
    ('t3-013', 'SAGE Framework', 'T3-013 — Mobile Approval Interface',
     'Approvals require a desktop browser. Operations managers on the factory floor or in the field cannot act on proposals without going to a computer.\n\nScope: Mobile-first approval UI (PWA -- no app store required); Push notifications; Offline-capable with local queue; Voice approval option; Responsive redesign of existing web UI as foundation.',
     'medium'),
    ('t3-014', 'SAGE Framework', 'T3-014 — Adaptive Solution Improvement (Closed-Loop Prompt Learning)',
     'SAGE collects human feedback but prompt improvements still require a human to review the audit log and manually edit prompts.yaml. The loop is not fully closed.\n\nScope: Pattern detection (cluster rejection reasons from audit log); Auto-suggest prompt improvements; Generate eval cases automatically from past proposals; Weekly improvement digest; One-click apply with automatic eval validation.',
     'medium'),
]

existing = set(
    r[0] for r in conn.execute(
        "SELECT module_id FROM feature_requests WHERE scope='sage'"
    ).fetchall()
)
print(f"Existing sage module_ids: {existing}")

inserted = 0
skipped = 0
for (mod_id, mod_name, title, desc, priority) in gaps:
    if mod_id in existing:
        skipped += 1
        continue
    rid = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO feature_requests
           (id, module_id, module_name, title, description, priority,
            status, requested_by, scope, created_at, updated_at)
           VALUES (?,?,?,?,?,?,'pending','gap-analysis','sage',?,?)""",
        (rid, mod_id, mod_name, title, desc, priority, now, now)
    )
    inserted += 1

conn.commit()
conn.close()
print(f"Inserted: {inserted}, Skipped (duplicates): {skipped}")
