# SAGE LangGraph Workflow Diagrams

Generated from compiled LangGraph StateGraph workflows using `workflow.get_graph().draw_mermaid()`.

Nodes with `__interrupt = before` are HITL gates — the workflow pauses before that node for human approval.

---

## 1. Build Workflow (0->1->N Pipeline)

**File:** `solutions/starter/workflows/build_workflow.py`
**HITL gates:** `review_plan`, `review_build`

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([__start__]):::first
	decompose(decompose)
	critic_plan(critic_plan)
	review_plan(review_plan -- HITL gate):::hitl
	scaffold(scaffold)
	execute_agents(execute_agents)
	critic_code(critic_code)
	integrate(integrate)
	critic_integration(critic_integration)
	review_build(review_build -- HITL gate):::hitl
	finalize(finalize)
	__end__([__end__]):::last
	__start__ --> decompose;
	decompose --> critic_plan;
	critic_plan --> review_plan;
	review_plan --> scaffold;
	scaffold --> execute_agents;
	execute_agents --> critic_code;
	critic_code --> integrate;
	integrate --> critic_integration;
	critic_integration --> review_build;
	review_build --> finalize;
	finalize --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
	classDef hitl fill:#fef3c7,stroke:#f59e0b,stroke-width:2px
```

**Flow:** Decompose description into tasks -> Critic reviews plan -> Human approves plan -> Scaffold directories -> Execute agents (parallel waves) -> Critic reviews code -> Integrate -> Critic reviews integration -> Human approves build -> Finalize

---

## 2. Analysis Workflow (Minimal HITL Pattern)

**File:** `solutions/starter/workflows/analysis_workflow.py`
**HITL gates:** `finalize`

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([__start__]):::first
	analyze(analyze)
	finalize(finalize -- HITL gate):::hitl
	__end__([__end__]):::last
	__start__ --> analyze;
	analyze --> finalize;
	finalize --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
	classDef hitl fill:#fef3c7,stroke:#f59e0b,stroke-width:2px
```

**Flow:** AI analyzes input -> Human reviews analysis -> Finalize (store feedback in vector memory)

---

## 3. HIL Workflow (Hardware-in-the-Loop Regulated Testing)

**File:** `solutions/starter/workflows/hil_workflow.py`
**HITL gates:** `submit_evidence`

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([__start__]):::first
	flash_firmware(flash_firmware)
	run_hil_suite(run_hil_suite)
	collect_evidence(collect_evidence)
	generate_report(generate_report)
	submit_evidence(submit_evidence -- HITL gate):::hitl
	__end__([__end__]):::last
	__start__ --> flash_firmware;
	flash_firmware --> run_hil_suite;
	run_hil_suite --> collect_evidence;
	collect_evidence --> generate_report;
	generate_report --> submit_evidence;
	submit_evidence --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
	classDef hitl fill:#fef3c7,stroke:#f59e0b,stroke-width:2px
```

**Flow:** Flash firmware -> Run HIL test suite -> Collect evidence (logs, traces) -> Generate regulatory report -> Human approves evidence -> Submit to audit log (DHF/TCF)

---

## 4. SWE Workflow (Autonomous Coding Agent)

**File:** `solutions/starter/workflows/swe_workflow.py`
**HITL gates:** `finalize`

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([__start__]):::first
	explore(explore)
	plan(plan)
	implement(implement)
	verify(verify)
	propose_pr(propose_pr)
	finalize(finalize -- HITL gate):::hitl
	__end__([__end__]):::last
	__start__ --> explore;
	explore --> plan;
	plan --> implement;
	implement --> verify;
	verify --> propose_pr;
	propose_pr --> finalize;
	finalize --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
	classDef hitl fill:#fef3c7,stroke:#f59e0b,stroke-width:2px
```

**Flow:** Explore codebase (README, file tree, tech stack) -> Plan changes (LLM-generated TODO list) -> Implement file-by-file -> Verify (targeted tests) -> Propose PR (branch + commit + optional GitHub PR) -> Human approves -> Finalize (audit log)

---

## Viewing These Diagrams

These Mermaid diagrams render natively in:
- GitHub Markdown preview
- VS Code with Mermaid extension
- Any Mermaid live editor (mermaid.live)

To regenerate from code:
```python
from solutions.starter.workflows.build_workflow import workflow
print(workflow.get_graph().draw_mermaid())
```
