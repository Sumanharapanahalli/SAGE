# JTBD User Personas — SAGE Framework

**Version:** 2.0.0
**Created:** 2026-03-26
**Framework:** Jobs to Be Done (JTBD) + RICE Scoring

---

## Overview

Three primary user archetypes for the SAGE Framework (Smart Agentic-Guided Empowerment), a lean agentic AI development platform for regulated and high-velocity engineering contexts. Each persona is sized using TAM/SAM/SOM methodology and scored using RICE prioritisation.

---

## Persona A — The Regulated Industry Engineering Lead

**Name:** Marcus Chen
**Title:** Engineering Manager, Medical Devices
**Archetype:** Regulated Industry Engineering Lead
**Tagline:** *"I need my AI agents to be auditable — my regulator will ask."*

### Context

- **Company size:** 50–5,000 employees
- **Industries:** Medical devices, avionics, automotive, railway, industrial safety
- **Team size:** 5–30 engineers
- **Compliance standards:** ISO 13485, IEC 62304, ISO 26262, DO-178C, IEC 61508
- **AI maturity:** Cautious adopter — has tried GitHub Copilot, wary of hallucinations in safety-critical paths
- **Representative SAGE solutions:** medtech_team, iot_medical, automotive, avionics

---

### 1. Functional Job

**Statement:** When managing a cross-functional engineering team on a regulated product, I want to automate the tedious compliance documentation, review cycles, and change impact analysis so that I can ship features faster without accumulating audit debt.

**Sub-jobs:**
- Trace every AI-suggested code change to a requirement ID automatically
- Generate draft DHF/IQ/OQ/PQ documentation from agent outputs
- Route agent proposals through the correct approval chain based on risk tier
- Keep a tamper-evident log of every AI decision for regulator inspection
- Run DRC/ERC and static analysis on hardware artifacts without manual toolchain setup

**Outcome metric:** Reduce compliance documentation effort by ≥40% per release cycle

---

### 2. Emotional Job

**Statement:** I want to feel confident that deploying AI in my workflow will not get me, my team, or my company sanctioned — and that I am not the last person standing between a bad AI output and a patient.

- **Core fear:** An AI agent produces a plausible-sounding but wrong recommendation that passes review and causes a field failure or FDA warning letter
- **Desired feeling:** In control — every agent action is visible, reversible, and traceable to a human decision
- **Tension:** Wants AI productivity gains but is professionally and personally liable for every output that ships

---

### 3. Social Job

**Statement:** I want to be known internally as the leader who modernised our development process without cutting corners on quality — and externally as someone regulators and customers trust to run a rigorous shop.

- **Internal narrative:** "I brought AI to our team AND we passed our ISO audit cleanly"
- **External narrative:** Presents SAGE-generated audit trail at notified body review as evidence of controlled AI use
- **Peer signal:** Peers at conferences who adopted AI tools recklessly got burned; this persona wants to be the counter-example

---

### 4. Hiring Criteria

**Trigger events:**
1. Upcoming regulatory submission deadline with backlog of undocumented AI-assisted changes
2. New hire onboarding: needs agent-guided knowledge transfer for regulated processes
3. Post-incident: a manual review missed something; wants AI-assisted triage with human gate
4. Competitor shipped a comparable product 30% faster — pressure to accelerate without cutting compliance
5. FDA/CE MDR audit found traceability gaps in AI-assisted development

**Switch threshold:** Will evaluate SAGE when (1) at least 1 compliance gap is attributed to manual documentation, OR (2) release velocity is below 60% of target for 2+ consecutive sprints due to documentation overhead.

**Must-haves before hiring:**
- HITL approval gate is non-negotiable — agents must never self-approve safety-critical changes
- Audit log is immutable and per-solution isolated
- Graceful degradation if LLM provider is unavailable — no production stoppage
- On-premise or private cloud deployment option for data residency requirements

---

### 5. Firing Criteria

**Dealbreakers:**
1. Any agent proposal executes without explicit human approval on safety-classified tasks
2. Audit log is incomplete, purgeable, or shared across solutions (cross-contamination risk)
3. Hallucinated compliance references (e.g., wrong standard version cited in draft DHF)
4. Cannot demonstrate to auditor that AI output was reviewed before implementation
5. Vendor lock-in to a single LLM provider violating procurement or security policy

**Tolerance level:** Zero tolerance for compliance failures; moderate tolerance for capability gaps if roadmap is credible.

---

### 6. Current Solutions Being Displaced

| Tool | Use Case | Why Insufficient |
|------|----------|-----------------|
| GitHub Copilot | Code suggestions for embedded C and firmware | No audit trail, no domain runners for cross-compilation or DRC, no HITL gate |
| Jira + Confluence | Manual requirements traceability and compliance documentation | Fully manual, documentation debt accumulates faster than it is cleared |
| MATLAB / Simulink | Model-based development and simulation | No agent orchestration, no connection to software development lifecycle |
| Altium Designer | PCB design and DRC | No agent assistance for layout decisions, no integration with firmware or compliance workflows |
| Custom internal scripts | Cobbled-together compliance report generators | Brittle, undocumented, not maintained, no LLM reasoning |

---

### 7. Quantitative Sizing

| Metric | Value |
|--------|-------|
| TAM (global regulated engineering leads) | 1,200,000 people / $5.76B |
| SAM (companies ≥50 employees with AI budget) | 180,000 people / $864M |
| SOM (3-year, 3% SAM capture) | 5,400 people / $25.9M |
| Willingness to pay | $300–$1,200/month |
| Conversion likelihood | 7/10 |

**RICE Score:**
- Reach: 5,400 users/quarter
- Impact: 3/3
- Confidence: 75%
- Effort: 8 person-weeks
- **RICE Score: 15,188**

*High RICE due to strong willingness-to-pay and clear pain; effort moderate because runner and audit infrastructure already built.*

---

### 8. Success Metrics

1. Compliance documentation effort reduced by ≥40% per release (hours saved tracked in audit log)
2. Zero compliance findings attributable to AI-assisted changes in annual regulatory audit
3. HITL approval turnaround time under 4 hours for standard proposals
4. Agent-generated DHF sections accepted with fewer than 2 revision rounds on average
5. Domain runner verification pass rate (DRC/ERC/static analysis) above 90% on first submission

---

### 9. Pain Points (Ranked)

**#1 — Documentation debt (Critical)**
Compliance documentation effort consumes 15–25% of sprint capacity. Every AI-assisted change requires manual traceability updates in Confluence and Jira. Directly blocks regulatory submissions and causes schedule slippage.

**#2 — No safe AI tooling for regulated domains (High)**
Available tools (Copilot, ChatGPT) have no audit trail, no HITL gate, and no domain awareness for embedded C, PCB, or firmware verification. Forces teams to ban AI tools outright or use them unofficially, creating shadow risk.

**#3 — Cross-functional context loss (Medium-High)**
When an engineer leaves or a consultant finishes, domain knowledge (design decisions, compliance rationale) evaporates. Onboarding new engineers costs 4–8 weeks; repeated mistakes in compliance reviews.

---

---

## Persona B — The Solo Founder / Micro-Team CTO

**Name:** Avery Nair
**Title:** Solo Technical Founder
**Archetype:** Solo Founder / Micro-Team CTO
**Tagline:** *"I am the entire product, engineering, and ops department. I need agents that can be the rest."*

### Context

- **Company size:** 1–10 people
- **Industries:** Consumer apps, B2B SaaS, developer tools, content platforms, consulting
- **Team size:** Usually 1 (the founder) plus occasional contractors
- **Compliance burden:** Minimal — GDPR basics, App Store guidelines
- **AI maturity:** Power user — living in AI tools daily, frustrated by context-switching between ChatGPT, Cursor agents, and manual deployment
- **Representative SAGE solutions:** four_in_a_line, meditation_app, board_games, starter

---

### 1. Functional Job

**Statement:** When building and iterating a product with a team of one, I want to delegate entire work streams — development, documentation, UX review, GTM copy — to autonomous agents so that I can focus only on decisions that require my judgment as the founder.

**Sub-jobs:**
- Spin up a domain-specific agent team from a plain-English description in under 10 minutes
- Have agents propose and self-execute routine tasks (CI fixes, dependency updates, README drafts) without interrupting my flow
- Compound agent knowledge over time so I am not re-explaining the same context every session
- Switch between LLM providers based on cost and capability without changing workflows
- Build custom MCP tools that integrate my SaaS stack (Stripe, Supabase, Vercel) into agent context

**Outcome metric:** Ship features 3x faster; reduce context-switching overhead to under 30 minutes per day

---

### 2. Emotional Job

**Statement:** I want to feel like I have a full team backing me — that I am not the bottleneck on every decision and that momentum compounds rather than resets every Monday morning.

- **Core fear:** Running out of runway because I am too slow to ship, or burning out from being the single point of failure on everything
- **Desired feeling:** Leverage — the sensation that the output of the week is disproportionate to the hours I put in
- **Tension:** Wants maximum autonomy from agents but does not want to lose control of product direction or quality bar

---

### 3. Social Job

**Statement:** I want to be known in founder and indie hacker communities as someone who figured out how to run a real company alone — as proof that the one-person billion-dollar company is possible.

- **Internal narrative:** "I shipped a full product this sprint and barely wrote any boilerplate code myself"
- **External narrative:** Posts a SAGE workflow demo that generates traction in the Indie Hackers / Hacker News community, signals technical sophistication to early investors
- **Peer signal:** Twitter/X threads from founders showing impressive output with tiny teams are aspirational references

---

### 4. Hiring Criteria

**Trigger events:**
1. Just shipped v1, now drowning in support tickets, feature requests, and tech debt simultaneously
2. Lost a week re-explaining project context after hitting Claude/GPT context window limits
3. Tried to hire a contractor but onboarding took longer than doing the work themselves
4. Competitor with the same team size is shipping 2x faster (visible via public changelogs)
5. First B2B customer asking for audit log or change history before signing a contract

**Switch threshold:** Will adopt SAGE when (1) context loss from AI session resets costs 4+ hours per week, OR (2) a specific domain workflow (firmware, ML pipeline, PCB) requires toolchain integration beyond raw LLM prompting.

**Must-haves before hiring:**
- Zero-friction local setup — single `make venv` plus `make run` command
- Works with free LLM providers (Gemini CLI, Ollama) — no surprise API bills on day one
- Onboarding wizard generates working YAML config from plain English in under 5 minutes
- Agent memory persists across sessions — no context amnesia
- Can run entirely offline for IP-sensitive projects

---

### 5. Firing Criteria

**Dealbreakers:**
1. Setup complexity exceeds 30 minutes for a net-new solution
2. Agents require constant hand-holding — approval gate interrupts for every trivial action
3. No visibility into what agents are doing — black box execution
4. Memory does not compound — same mistakes made in session 10 as session 1
5. Cannot extend with custom MCP tools without touching framework Python

**Tolerance level:** Low tolerance for friction and setup complexity; high tolerance for rough edges on features they do not use yet.

---

### 6. Current Solutions Being Displaced

| Tool | Use Case | Why Insufficient |
|------|----------|-----------------|
| ChatGPT / Claude.ai (browser) | Ad-hoc code generation, planning, copywriting | No persistent memory, no multi-agent coordination, context resets destroy compounding value |
| Cursor / Windsurf | AI-assisted code editing in IDE | Scoped to code only — no product strategy, documentation, UX, or GTM agents; no vector memory |
| Linear | Task tracking and sprint planning | Fully manual — no AI-assisted planning or autonomous task execution |
| Notion AI | Documentation and knowledge base | No agentic execution — generates text but does not act; no integration with code or deployment |
| Zapier / Make | Workflow automation between SaaS tools | Rule-based only, no reasoning, cannot handle novel situations |

---

### 7. Quantitative Sizing

| Metric | Value |
|--------|-------|
| TAM (global solo/micro-team technical founders) | 4,500,000 people / $2.7B |
| SAM (technical founders with ≥1 live product and AI tooling spend) | 500,000 people / $300M |
| SOM (3-year, 5% SAM capture) | 25,000 people / $15M |
| Willingness to pay | $19–$99/month |
| Conversion likelihood | 8/10 |

**RICE Score:**
- Reach: 25,000 users/quarter
- Impact: 3/3
- Confidence: 85%
- Effort: 4 person-weeks
- **RICE Score: 159,375**

*Highest RICE score — enormous reach, self-serve acquisition, low effort because onboarding wizard and starter template already exist.*

---

### 8. Success Metrics

1. Features shipped per week increases by 3x within 90 days of adopting SAGE (tracked via git commit frequency)
2. Context-switching time between AI tools drops below 30 minutes per day (self-reported)
3. Agent memory reuse rate above 60% — majority of tasks leverage prior vector store context rather than re-prompting from scratch
4. Time-to-first-working-agent for a new domain under 10 minutes (measured via onboarding wizard telemetry)
5. LLM API cost per shipped feature decreases by 40% within 60 days due to provider switching and context reuse

---

### 9. Pain Points (Ranked)

**#1 — Context amnesia (Critical)**
Every new AI session starts from zero. The founder must re-explain the product, codebase, decisions, and constraints every single time, consuming 1–2 hours per day of pure overhead. Directly kills the compounding value that makes AI tools worthwhile for a solo operator.

**#2 — Tool fragmentation (High)**
Using ChatGPT for planning, Cursor for code, Notion AI for docs, Zapier for automation — and manually connecting the outputs. Each tool has no awareness of the others. Constant context-switching is the #1 source of cognitive load and lost momentum.

**#3 — Single point of failure (Medium-High)**
The founder is the only person who understands the full system. Agents help generate output but cannot autonomously handle novel situations. The founder cannot take a vacation without the product stalling. Unsustainable as the product grows.

---

---

## Persona C — The Enterprise AI Transformation Architect

**Name:** David Okafor
**Title:** Director of AI Platform Engineering
**Archetype:** Enterprise AI Transformation Architect
**Tagline:** *"I need to give 200 teams a controlled on-ramp to agentic AI without letting any one team blow up the whole company."*

### Context

- **Company size:** 1,000–100,000+ employees
- **Industries:** Financial services, enterprise SaaS, logistics, retail, healthcare IT
- **Team size:** Platform team of 5–20 serving 50–500 internal developer teams
- **Compliance standards:** SOC 2 Type II, ISO 27001, GDPR, HIPAA (healthcare), PCI-DSS (finance)
- **AI maturity:** Strategic evaluator — has run 3–5 AI pilots; now tasked with platformising the winners and decommissioning shadow-IT LLM experiments across business units
- **Representative SAGE solutions:** finmarkets, healthcare_it, enterprise_platform, logistics

---

### 1. Functional Job

**Statement:** When centralising AI agent capabilities across dozens of product teams, I want a platform that provides consistent governance, cost visibility, and solution isolation so that individual teams can move fast without creating compliance or security liability at the company level.

**Sub-jobs:**
- Provide each business unit a fully isolated agent environment (data, audit log, vector store) from a single platform deployment
- Enforce LLM provider policy centrally (approved models, spend caps) while giving teams flexibility on prompts and tasks
- Expose agent capabilities as an internal developer platform with self-service onboarding — wizard to working environment in under 1 day
- Aggregate cost and usage metrics across all tenants for FinOps visibility
- Integrate with existing identity (SSO/OIDC), ticketing (Jira), and secrets management (Vault)

**Outcome metric:** Reduce time-to-first-agent-in-production per new team from 6 weeks to under 3 days; full cost allocation across business units by Q3

---

### 2. Emotional Job

**Statement:** I want to feel like the platform I am building is ahead of the business's appetite — not constantly reacting to teams that have already made a mess — and that when the inevitable security review comes, I can answer every question.

- **Core fear:** A business unit deploys an LLM agent that exfiltrates customer PII, triggers a SOC 2 finding, or hallucinates financial data in a client-facing report — and it traces back to my platform
- **Desired feeling:** Confident — the guardrails are architectural, not dependent on individual team compliance
- **Tension:** Under pressure from CTO to move fast and enable teams; under simultaneous pressure from CISO and Legal to ensure control and auditability

---

### 3. Social Job

**Statement:** I want to be seen by the CTO as the architect who enabled the company's AI transformation, and by the CISO as the person who made sure it did not become a liability.

- **Internal narrative:** "Our AI platform serves 200 teams; every agent action is audited; we have had zero security incidents"
- **External narrative:** Publishes case study or conference talk on SAGE-based internal AI developer platform, establishing thought leadership in enterprise AI governance
- **Peer signal:** Other platform architects at competing companies present at re:Invent and KubeCon; this persona wants to be on that stage

---

### 4. Hiring Criteria

**Trigger events:**
1. CISO or Legal issued a moratorium on new LLM tool adoption pending a governance framework
2. FinOps team flagged uncontrolled AI API spend across business units with no cost allocation
3. CTO mandated "platformise AI" as a Q1 OKR; platform team has 90 days to deliver
4. SOC 2 audit found no audit trail exists for AI-assisted decisions in customer-facing systems
5. Three or more business units have built incompatible in-house agent frameworks; consolidation required

**Switch threshold:** Will evaluate SAGE when (1) shadow AI proliferation reaches 5+ independent business unit deployments, OR (2) first compliance finding attributable to uncontrolled AI usage is issued.

**Must-haves before hiring:**
- Multi-tenant isolation is architectural — solution A's data cannot reach solution B's agents under any conditions
- SAGE_SOLUTIONS_DIR pattern allows private solutions without modifying the framework repo
- LLM provider switching at runtime without redeployment for model policy enforcement
- REST API is the only public interface — no direct database access from business units
- Horizontal scaling path exists — queue-based, stateless API layer

---

### 5. Firing Criteria

**Dealbreakers:**
1. Tenant data isolation is logical-only (same DB table with tenant_id filter) rather than physical (.sage/ per solution with separate SQLite and ChromaDB)
2. Framework requires production access to framework source repo to add a new solution
3. No cost metering or LLM call budgets per tenant or agent
4. Cannot integrate with corporate SSO/OIDC for the approval workflow
5. Vendor requires SaaS model — enterprise security policy mandates on-premise or private cloud
6. Single point of failure on LLM provider — must support provider redundancy and failover

**Tolerance level:** Very low tolerance for security and isolation gaps; moderate tolerance for UI polish and developer ergonomics gaps if API layer is solid.

---

### 6. Current Solutions Being Displaced

| Tool | Use Case | Why Insufficient |
|------|----------|-----------------|
| ChatGPT Enterprise | Company-wide LLM access with SSO and data isolation | No agentic execution, no domain-specific runners, no per-team solution isolation, no customisable approval gates |
| Azure AI Studio / OpenAI on Azure | Managed LLM APIs with enterprise security | Requires significant custom engineering for agent orchestration and HITL gates; high implementation overhead |
| Backstage (Spotify IDP) | Internal developer portal for service discovery and scaffolding | Not AI-native — no agent reasoning, no proposal-and-approve workflow; only a catalog and template system |
| LangSmith / LangChain Hub | LLM observability and prompt management | Observability only — no agent orchestration, no HITL gates, no domain-specific runners |
| In-house Python scripts per team | Custom per-team LLM wrappers and automation | No governance, no audit trail, inconsistent quality, incompatible across teams — the definition of shadow AI |

---

### 7. Quantitative Sizing

| Metric | Value |
|--------|-------|
| TAM (global AI platform architects at enterprises ≥1,000 employees) | 180,000 people / $4.32B |
| SAM (enterprises with active AI platform initiative and approved budget) | 36,000 people / $864M |
| SOM (3-year, 1.5% SAM capture) | 540 people / $12.96M |
| Willingness to pay | $1,000–$8,000/month |
| Conversion likelihood | 5/10 |

**RICE Score:**
- Reach: 540 users/quarter
- Impact: 3/3
- Confidence: 60%
- Effort: 12 person-weeks
- **RICE Score: 8,100**

*Lower RICE due to small reachable cohort and high sales cycle effort; but highest ACV per deal — enterprise contract value 5–10x Persona 1. Long-term strategic moat.*

---

### 8. Success Metrics

1. Number of internal teams onboarded to SAGE platform per quarter — target: 10 teams per quarter by end of year 1
2. Shadow AI incidents eliminated — reduction in security and compliance findings attributable to uncontrolled LLM usage from baseline to zero within 6 months
3. Time-to-first-agent-in-production per new team reduced from 6 weeks to under 3 days (measured from onboarding wizard initiation to first approved proposal)
4. LLM spend visibility — 100% of AI API costs attributed to specific business unit and solution by end of Q3
5. Platform NPS from internal developer teams above 40 within 12 months of launch (measured via quarterly internal survey)

---

### 9. Pain Points (Ranked)

**#1 — Shadow AI proliferation (Critical)**
Individual business units have deployed 5–15 incompatible LLM integrations with no audit trail, no governance, no isolation, and no visibility to the platform team. The CISO is aware and demanding action within 90 days. Direct compliance and security liability — a single incident could result in regulatory action or customer data breach.

**#2 — No enterprise-grade agentic AI platform off the shelf (High)**
Every available option (Azure AI Studio, LangSmith, Vertex AI) requires 6–12 months of custom engineering to add multi-tenant isolation, HITL gates, domain runners, and cost metering. Forces the platform team to build from scratch, consuming headcount that could be delivering product value.

**#3 — CTO versus CISO tension is unresolvable without architecture (High)**
CTO demands AI-enabled teams by Q1; CISO demands audit trail and isolation before any AI tool is approved. Without a platform that satisfies both simultaneously, the platform architect is caught in the middle indefinitely and cannot make forward progress.

---

---

## Cross-Persona Analysis

### Shared Functional Jobs (All 3 Personas)

1. **Compound agent knowledge over time** — all 3 personas need context that does not reset
2. **Human approval gate for high-stakes actions** — all 3 need control, for different reasons (compliance, quality, governance)
3. **Multi-LLM provider flexibility** — cost, policy, and capability reasons differ but the requirement is the same across all three

### Divergent Needs

| Dimension | P1 Regulated Lead | P2 Solo Founder | P3 Enterprise Architect |
|-----------|------------------|----------------|------------------------|
| Approval gate | Mandatory for all proposals — non-negotiable | Optional and configurable — interrupts are a dealbreaker | Mandatory for cross-team actions; optional for internal dev |
| Deployment model | On-premise or private cloud; data residency in jurisdiction | Local or personal cloud; zero infrastructure overhead | Private cloud with SSO, network policies, and FinOps |
| Primary value metric | Audit coverage % and compliance documentation velocity | Features shipped per week and context-switching time saved | Teams onboarded per quarter and shadow-AI incidents eliminated |

### Persona Priority for SAGE Roadmap

| Priority | Persona | Reasoning |
|----------|---------|-----------|
| **Immediate focus** | P2 — Indie Founder | Highest RICE at 159,375; self-serve acquisition; open-source flywheel already in motion |
| **Strategic moat** | P1 — Regulated Lead | Highest willingness-to-pay; strongest differentiation via audit trail and HITL gate; defensible against generic LLM tools |
| **Enterprise upside** | P3 — Enterprise Architect | Lowest near-term RICE but highest ACV per deal; multi-tenant isolation already architecturally present |

---

## Action Items (Product)

1. **Add persona-branching onboarding wizard:** Ask "What describes you best?" on first run and pre-configure approval gate defaults (P1=strict, P2=minimal, P3=tenant-scoped)
2. **Build a compliance-first starter template for P1** that ships with IEC 62304 / ISO 13485 task YAML pre-wired and DHF document generation prompts
3. **Create a zero-friction quickstart path for P2:** Single `make demo` command that spins up a working 3-agent team from a plain-English description in under 5 minutes
4. **Add per-tenant LLM spend metering and budget caps** (cost_limit_usd per solution) to satisfy P3 FinOps requirements — this is a P3 hiring gate
5. **Instrument audit_log.db with persona-segment tags** so SAGE can surface per-archetype analytics and validate RICE assumptions empirically
6. **Publish official SAGE Docker image with SSO/OIDC middleware hooks** to unblock P3 enterprise procurement
7. **Write a regulated industry cookbook** (SAGE + IEC 62304 traceability) as a publicly available reference implementation to drive P1 inbound via conference and SEO

---

*Generated by SAGE Framework product analysis — 2026-03-26*
