# I Built an Open-Source AI Agent Framework for Regulated Industries. Here's What I Learned.

**TL;DR:** I open-sourced SAGE — a multi-agent orchestration framework where AI proposes and humans decide. Built for medical devices, automotive, fintech, and any industry where "the AI did it" isn't an acceptable answer during an audit. 110K lines of code. 2,000+ tests. Zero mandatory API keys.

**GitHub:** https://github.com/Sumanharapanahalli/SAGE

---

## The Problem No One Is Solving

Every AI agent framework I evaluated — LangGraph, CrewAI, AutoGen, Dify — treats human approval as *optional*. A configurable flag. A nice-to-have.

That's fine for building chatbots and content generators.

It's not fine when:
- A wrong decision fails an FDA 21 CFR Part 11 audit
- An unapproved code change violates IEC 62304 software lifecycle requirements
- An agent action triggers an ISO 13485 corrective action
- A safety-critical system needs provable human oversight for every decision

I spent the last month building SAGE (Smart Agentic-Guided Empowerment) to fix this.

---

## What Makes SAGE Different

### 1. Agents Propose. Humans Decide. Always.

This isn't a toggle. It's the architecture. Every agent proposal — code change, YAML edit, knowledge deletion, agent hire — requires explicit human sign-off before execution. The approval gate is immutable and audited.

Framework control operations (switching LLM providers, toggling modules) execute immediately — because those are the operator's own actions, not agent actions. The distinction matters for compliance.

### 2. Nine State-of-the-Art Orchestration Modules

SAGE doesn't just route tasks to agents. It implements cutting-edge agentic patterns:

- **Reflection Engine** — Bounded self-correction (Reflexion/LATS): generate → critique → improve, with plateau detection
- **Plan Selector** — Beam search over candidate plans (Tree of Thought): generate N plans, score each, select best
- **Consensus Engine** — Multi-agent voting (majority, weighted, unanimous) with automatic human escalation on disagreement
- **Budget Manager** — Per-scope token and cost tracking with configurable limits and hard stops
- **Tool Executor** — ReAct pattern: agents call tools (file_read, git_diff, search_code) during execution
- **Agent Spawner** — Recursive agent composition with depth and concurrency limits
- **Backtrack Planner** — HTN-style re-planning when subtasks fail repeatedly
- **Memory Planner** — RAG-in-the-loop: augment planning with past successes and collective knowledge
- **Event Bus** — Real-time SSE streaming to the web dashboard

These aren't demos. They're production modules with full API endpoints, web UI, and 87 tests.

### 3. Collective Intelligence — Agents That Share Knowledge

This is the feature I'm most excited about. Agents don't just work in silos anymore.

When an analyst agent in your medtech solution discovers a UART debugging pattern, it can publish that learning to a shared Git-backed knowledge commons. An embedded engineer in your automotive solution can find it via semantic search.

Help requests work the same way: an agent stuck on I2C bus recovery can request help from any agent with that expertise, across any solution.

Knowledge compounds. Every team benefits from every other team's discoveries.

### 4. Solution Constitution — Your AI Team's "Blue Book"

Every solution can define a `constitution.yaml` — immutable principles that shape agent behavior:

```yaml
principles:
  - id: safety-first
    text: "Patient safety overrides all other priorities."
    weight: 1.0  # non-negotiable

constraints:
  - "Never modify files in /critical/ without approval"

voice:
  tone: "precise, clinical, evidence-based"
  avoid: ["marketing speak", "vague estimates"]
```

This gets injected into every agent's system prompt. Non-negotiable principles are marked `[NON-NEGOTIABLE]`. Constraints are checked against proposed actions. Escalation keywords trigger mandatory human review.

No code changes needed. Just YAML.

### 5. Zero API Keys Required

SAGE works with:
- Gemini CLI (browser OAuth, no key)
- Claude Code CLI (existing auth, no key)
- Ollama (fully offline)
- Local GGUF models (air-gapped, GPU-direct)

You can run the entire framework on a machine with no internet connection. This matters in regulated environments where data can't leave the building.

---

## By the Numbers

| Metric | Value |
|--------|-------|
| Production code | ~110,000 lines (84K Python + 26K TypeScript) |
| Automated tests | 2,000+ (100% pass rate) |
| REST API endpoints | 280+ |
| React UI pages | 36 |
| Agent roles | 5 core + 19 specialist |
| Domain runners | 11 (software, firmware, PCB, ML, docs, etc.) |
| Orchestrator modules | 9 SOTA patterns |
| Industry domains tested | 10 (100-solution stress test) |
| Compliance standards | IEC 62304, ISO 26262, DO-178C, EN 50128, 21 CFR Part 11 |

---

## Who This Is For

- **Medical device companies** needing IEC 62304 + FDA compliance with AI assistance
- **Automotive teams** working under ISO 26262 / AUTOSAR
- **Fintech companies** requiring SOC 2 / PCI DSS audit trails
- **Any regulated industry** where "the model hallucinated" won't satisfy your auditor

But also:

- **Solo founders** who want an AI agent team that compounds intelligence over time
- **Engineering teams** tired of rebuilding agent infrastructure from scratch
- **Anyone** who believes AI should amplify human judgment, not replace it

---

## What I Learned Building This

**1. Governance is a feature, not friction.** The approval gate isn't bureaucracy — it's what makes the system trustable. Every rejection teaches the agents something. After 6 months, your agents will be dramatically better than day one, without any model retraining.

**2. YAML-first configuration is underrated.** Adding a new industry domain to SAGE requires editing 3 YAML files. No Python. No framework changes. This is how agent frameworks should work.

**3. Collective intelligence compounds.** The moment agents can share knowledge across teams, the value curve changes from linear to exponential. One team's debugging insight becomes every team's advantage.

**4. Constitution > prompts.** Defining agent behavior through structured principles, constraints, and decision rules is more maintainable and auditable than tweaking system prompts. The constitution is version-controlled, editable via UI, and enforced automatically.

**5. Transparent failure reporting matters.** Our 100-solution stress test had a 2% end-to-end success rate in the first run. We reported that honestly. We documented root causes. We built the Reflection Engine and Backtrack Planner to address them. That's how real engineering works.

---

## Try It

```bash
git clone https://github.com/Sumanharapanahalli/SAGE.git
cd SAGE
make venv
make run PROJECT=starter
make ui
```

MIT Licensed. No API keys required. Running in 15 minutes.

Star it if you find it useful. Open issues if you find bugs. PRs welcome.

---

*SAGE is built on lean development methodology: eliminate waste, shorten feedback loops, amplify human judgment. The agents get smarter with every human decision. That's not a marketing claim — it's the architecture.*

#AI #AgentFramework #OpenSource #RegulatedIndustry #MedicalDevices #Compliance #LeanDevelopment #MultiAgentSystems #HumanInTheLoop
