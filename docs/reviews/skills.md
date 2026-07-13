# SAGE Feature Review — `skills`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/skills.py`  
**Frontend:** `SkillsTools.tsx`  
**Review time:** 62s

---

## Verdict
The skills management interface is partly usable today for basic monitoring and enabling/disabling skills, but it contains a critical "black hole" defect that permanently locks disabled skills out of the UI, alongside a complete omission of compliance logging for state changes.

**Works:** partly
**Score:** 5/10

## What Actually Works
* **Skill Metadata Retrieval (`skills.list`):** Successfully retrieves registered skills (e.g., `agentic_engineering` and `auto_research` in the live evidence), showing their names, descriptions, and current visibility.
* **MCP Tool Mapping (`mcp.tools`):** Correctly lists all 13 discovered MCP tools (such as `browse_page`, `list_directory`, and `query_db`) with their hosting server names and descriptions.
* **Direct Skill Hot-Reloading (`skills.reload`):** The reload handler triggers the backend `skill_registry.reload()` sequence and returns updated registry counts and statistics.
* **Inline Visibility Updates (`skills.set_visibility`):** The backend handler validates parameters (validating visibility against `{"public", "private", "disabled"}`) and invokes the registry to apply the new state.
* **UI Controls:** The React frontend displays the correct values and triggers backend state updates when selecting a different visibility tier.

## System-Level Findings

### 1. Critical Severity: The Disabled Skill "Black Hole" (State-Correctness Defect)
* **Finding:** In `skills.py`, the `list` handler defaults to `include_disabled=False` unless explicitly requested. In `SkillsTools.tsx`, the `useSkills()` hook queries the list without passing this parameter.
* **Impact:** When an operator updates a skill's visibility to `"disabled"`, the mutation succeeds, and React Query invalidates the cache. Because `include_disabled` is omitted on the refetch, the disabled skill is immediately excluded from the returned dataset. The skill permanently disappears from the table, leaving the operator with zero UI mechanisms to ever re-enable it.

### 2. High Severity: Complete Absence of Compliance Audit Logging
* **Finding:** Both `set_visibility` and `reload` mutate the active capabilities of the agent framework. They bypass `ProposalStore` because they are "framework control" actions. However, `skills.py` calls the registries directly without writing to the compliance log.
* **Impact:** Direct operator modifications to safety-critical prompts, skill scopes, or registry states leave no paper trail. This violates regulatory guidelines (such as FDA Software in Medical Devices / IEC 62304) which demand deterministic traceability of system configuration changes.

### 3. Medium Severity: Silently Discarded RPC Failure Context
* **Finding:** When a mutation fails in `skills.py`, exceptions are caught and raised as a generic `RPC_SIDECAR_ERROR`. On the frontend, `mutationError` is bound to a single top-level `<ErrorBanner>` shared between both `reload` and `setVisibility`.
* **Impact:** If an operator updates a specific row's visibility and it fails, the error is displayed globally at the top of the page rather than contextually on the row. If multiple updates occur simultaneously, the errors overwrite each other, causing ambiguity.

## Usability Findings

### 1. No Discovery Refetch for MCP Tools
* **Finding:** The UI lists active MCP tools but offers no refresh/rediscover button. 
* **Impact:** If an operator restarts or registers a new local MCP server in the background, they must reload the entire desktop application to update the list of available tools.

### 2. Missing Feedback on Destructive Actions
* **Finding:** Clicking "Reload" triggers `reload.mutate()`, which returns the count of loaded skills and updated registry stats. The UI does not display a success notification or toast.
* **Impact:** The operator has no visual confirmation that the reload was successful or if the registry parser ran into syntax errors, other than manually checking the subheader count.

### 3. Aesthetic Ambiguity on Empty Descriptions
* **Finding:** When a skill description is empty (such as `auto_research` in the live evidence), the UI renders a literal `"—"`. 
* **Impact:** This does not visually distinguish between a description that is pending load, missing from the underlying YAML/JSON file, or failed to parse.

## Top 3 Fixes (optimizer-ready)

### 1. Eliminate the Disabled Skill UI Black Hole
* **Task:** Modify the frontend API/hook call for listing skills to request disabled skills, and handle their display state in the UI.
* **Files:** `SkillsTools.tsx` (and the query hook in `src/hooks/useSkills.ts` or equivalent)
* **Acceptance Criteria:**
  1. Update the `useSkills` hook query to pass `include_disabled: true` in the `skills.list` RPC parameters.
  2. Verify that when a skill is set to `"disabled"`, it remains visible in the table with its dropdown displaying `"disabled"`.
  3. Ensure the operator can toggle the dropdown back to `"public"` or `"private"` to re-enable it without database intervention.

### 2. Implement Compliance Logging for State Mutations
* **Task:** Inject audit logging hooks into the direct framework control handlers.
* **Files:** `skills.py`
* **Acceptance Criteria:**
  1. Import and invoke the workspace's audit/compliance log module inside `set_visibility` and `reload` handlers.
  2. Log the identity of the operator, the event name (`SKILL_VISIBILITY_CHANGE` or `SKILL_REGISTRY_HOT_RELOAD`), the target skill name, and the previous/new visibility states.
  3. Assert that changing visibility generates an immutable log entry in the compliance database.

### 3. Isolate Mutation Errors and Provide Success Feedback
* **Task:** Scope visibility loader states to specific rows and add toast notifications on successful reload.
* **Files:** `SkillsTools.tsx`
* **Acceptance Criteria:**
  1. Replace the global `setVisibility.isPending` check on the dropdown with a row-specific pending state (matching on the skill's name).
  2. Display a success toast or inline banner upon successful reload: `"Successfully reloaded {skills_loaded} skills."` using the returned mutation payload.
  3. Contextually render visibility update errors inline near the specific dropdown rather than in the global top-level `<ErrorBanner>`.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    skills.list
  -> {"skills": [{"name": "agentic_engineering", "version": "1.0.0", "visibility": "public", "roles": ["agentic_engineer"], "runner": "openswe", "description": "Agentic AI engineering skills for building autonomous agent systems. Covers agent frameworks, tool use, multi-agent orchestration, memory systems, evaluation, and production agent deployments.\n", "tools": ["python", "langgraph", "crewai", "autogen", "anthropic-sdk", "openai-sdk", "mcp-sdk", "temporal", "docker", "fastapi", "websockets", "redis", "sqlite"], "prompt": "You are a senior agentic AI engineer specializing in autonomous agent systems:\n- Agent framework design (LangGraph, CrewAI, AutoGen, custom)\n- Tool use and function calling (MCP, OpenAI tools, Anthrop...", "acceptance_criteria": ["Agent completes assigned task autonomously", "All tool calls have proper error handling", "HITL gate present for destructive or high-stakes actions", "Agent loop terminates (circuit breaker tested)", "Actions audited with trace IDs", "Memory compounding verified (next run uses prior learnings)"], "certifications": ["LangChain Certified Developer", "Anthropic Agent SDK (emerging)", "DeepLearning.AI Multi-Agent Systems"], "engines": ["auto_research"], "tags": ["agents", "agentic-ai", "tool-use", "multi-agent", "orchestration", "mcp"]}, {"name": "auto_research", "version": "1.0.0", "visibility": "public", "roles": ["research_engineer", "ml_researcher"], "runner": "autoresearch", "description": "", "tools": ["python3", "uv", "git", "tensorboard", "wandb", "optuna", "pytest"], "prompt": "You are a senior ML research engineer with deep expertise in autonomous experimentation.\nYou design, execute, and analyze experiments using a disciplined hill-climbing approach.\n\nYour workflow follows...", "acceptance_criteria": ["Experiment hypothesis is stated before execution", "Code change is minimal and focused on one variable", "Metric is correctly extracted from output", "Keep/discard decision is based on metric comparison", "Git state is clean after each experiment (commit or reset)", "Results are logged with full provenance"], "certifications": ["Google ML Cert", "Stanford CS229", "Stanford CS231n", "NeurIPS Reproducibility"], "engines": [], "tags": ["ml-research", "experimentation", "autonomous", "optimization"]}, {"name": "brainstorming", "version": "1.0.0", "visibility": "public", "roles": ["planner", "analyst", "product_owner", "business_analyst", "developer", "swe_engineer"], "runner": "openswe", "description": "Structured brainstorming and ideation skill. Guides agents through divergent thinking, idea evaluation, and convergence to actionable proposals. Uses techniques from design thinking and lean methodology.\n", "tools": ["markdown", "mermaid", "yaml"], "prompt": "You facilitate structured brainstorming sessions:\n\n## Brainstorming Process\n1. **DEFINE** \u00e2\u20ac\u201d Frame the problem clearly\n   - Write a \"How Might We\" (HMW) statement\n   - Identify constraints and succes...", "acceptance_cr  ...[TRUNCATED BY THE AUDIT HARNESS FOR LENGTH — the real RPC response was complete, valid JSON. Do NOT report this as a defect.]

[LIVE OK]    mcp.tools
  -> {"tools": [{"name": "browse_page", "description": "Navigate to a URL and extract page content.", "server": "mcp_servers.browser_tools"}, {"name": "click_and_extract", "description": "Navigate to a page, click an element, and extract resulting content.", "server": "mcp_servers.browser_tools"}, {"name": "describe_table", "description": "Get schema information for a table in a .sage/ database.", "server": "mcp_servers.sqlite_tools"}, {"name": "file_exists", "description": "Check if a file or directory exists in the solution directory.", "server": "mcp_servers.filesystem_tools"}, {"name": "fill_form", "description": "Navigate to a page, fill form fields, and optionally submit.", "server": "mcp_servers.browser_tools"}, {"name": "list_databases", "description": "List all .db files in the active solution's .sage/ directory.", "server": "mcp_servers.sqlite_tools"}, {"name": "list_directory", "description": "List files and directories within the active solution directory.", "server": "mcp_servers.filesystem_tools"}, {"name": "list_tables", "description": "List all tables in a .sage/ database.", "server": "mcp_servers.sqlite_tools"}, {"name": "query_db", "description": "Execute a read-only SQL query against a .sage/ database.", "server": "mcp_servers.sqlite_tools"}, {"name": "read_file", "description": "Read a file from the active solution directory.", "server": "mcp_servers.filesystem_tools"}, {"name": "screenshot_page", "description": "Capture a screenshot of a web page.", "server": "mcp_servers.browser_tools"}, {"name": "search_files", "description": "Recursively search for files matching a glob pattern.", "server": "mcp_servers.filesystem_tools"}, {"name": "write_file", "description": "Write content to a file in the active solution directory.", "server": "mcp_servers.filesystem_tools"}], "count": 13}
```
