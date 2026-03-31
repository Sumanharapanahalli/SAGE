"""
SAGE ProposalExecutor — Dispatches approved proposals to their handlers.

Called exclusively from POST /approve/{trace_id} after the ProposalStore
marks the proposal as approved. No action fires before this point.

Each action_type maps to an executor function that performs the actual
side-effectful work (file write, config switch, vector store mutation, etc).
"""

import logging
import os

from src.core.proposal_store import Proposal, RiskClass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Executor functions — one per action_type
# ---------------------------------------------------------------------------

async def _execute_yaml_edit(proposal: Proposal):
    """Write validated YAML content to a solution config file and reload."""
    import yaml as _yaml
    from src.core.project_loader import project_config, _SOLUTIONS_DIR

    file_name = proposal.payload["file"]
    content   = proposal.payload["content"]
    solution  = proposal.payload.get("solution", project_config.project_name)

    # Validate again (belt-and-suspenders)
    _yaml.safe_load(content)

    path = os.path.join(_SOLUTIONS_DIR, solution, f"{file_name}.yaml")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    project_config.reload(solution)
    logger.info("YAML edit executed: %s/%s.yaml", solution, file_name)
    return {"file": file_name, "solution": solution}


async def _execute_config_switch(proposal: Proposal):
    """Switch active solution."""
    from src.core.project_loader import project_config
    project_name = proposal.payload["project"]
    project_config.reload(project_name)
    logger.info("Config switch executed: project=%s", project_name)
    return {"project": project_name}


async def _execute_llm_switch(proposal: Proposal):
    """Switch LLM provider/model at runtime."""
    from src.core.llm_gateway import (
        LLMGateway, GeminiCLIProvider, LocalLlamaProvider,
        ClaudeCodeCLIProvider, ClaudeAPIProvider, OllamaProvider
    )
    import yaml

    req_provider = proposal.payload.get("provider", "gemini")
    req_model    = proposal.payload.get("model")

    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config", "config.yaml",
    )
    with open(config_path) as f:
        cfg = yaml.safe_load(f) or {}
    llm_cfg = cfg.get("llm", {})

    gw = LLMGateway()
    if req_provider == "gemini":
        if req_model:
            llm_cfg["gemini_model"] = req_model
        gw.provider = GeminiCLIProvider(llm_cfg)
    elif req_provider == "local":
        if req_model:
            llm_cfg["model_path"] = req_model
        gw.provider = LocalLlamaProvider(llm_cfg)
    elif req_provider == "claude-code":
        if req_model:
            llm_cfg["claude_model"] = req_model
        claude_path = proposal.payload.get("claude_path")
        if claude_path:
            llm_cfg["claude_path"] = claude_path
        gw.provider = ClaudeCodeCLIProvider(llm_cfg)
    elif req_provider == "ollama":
        if req_model:
            llm_cfg["ollama_model"] = req_model
        gw.provider = OllamaProvider(llm_cfg)
    else:
        if req_model:
            llm_cfg["claude_model"] = req_model
        gw.provider = ClaudeAPIProvider(llm_cfg)

    gw.reset_usage()

    # Persist to config.yaml if requested
    save_as_default = proposal.payload.get("save_as_default", False)
    if save_as_default:
        try:
            with open(config_path) as f:
                raw = f.read()
            # Update provider line
            import re
            raw = re.sub(r'^(\s*provider\s*:\s*).*$', f'\\g<1>"{req_provider}"', raw, flags=re.MULTILINE)
            if req_model:
                if req_provider == "gemini":
                    raw = re.sub(r'^(\s*gemini_model\s*:\s*).*$', f'\\g<1>"{req_model}"', raw, flags=re.MULTILINE)
                elif req_provider in ("claude-code", "claude"):
                    raw = re.sub(r'^(\s*claude_model\s*:\s*).*$', f'\\g<1>"{req_model}"', raw, flags=re.MULTILINE)
                elif req_provider == "ollama":
                    raw = re.sub(r'^(\s*ollama_model\s*:\s*).*$', f'\\g<1>"{req_model}"', raw, flags=re.MULTILINE)
            claude_path = proposal.payload.get("claude_path")
            if claude_path and req_provider == "claude-code":
                # Write or update claude_path line (uncomment if commented)
                if re.search(r'^\s*#?\s*claude_path\s*:', raw, re.MULTILINE):
                    raw = re.sub(r'^\s*#?\s*(claude_path\s*:).*$', f'  \\g<1> "{claude_path}"', raw, flags=re.MULTILINE)
                else:
                    raw = re.sub(r'^(\s*claude_model\s*:.*)', f'\\g<1>\n  claude_path: "{claude_path}"', raw, flags=re.MULTILINE)
            with open(config_path, "w") as f:
                f.write(raw)
            logger.info("config.yaml updated: provider=%s model=%s", req_provider, req_model)
        except Exception as exc:
            logger.warning("Failed to persist LLM default to config.yaml: %s", exc)

    logger.info("LLM switch executed: provider=%s model=%s save_as_default=%s", req_provider, req_model, save_as_default)
    return {"provider": req_provider, "provider_name": gw.get_provider_name(), "saved_as_default": save_as_default}


async def _execute_config_modules(proposal: Proposal):
    """Update active modules list."""
    from src.core.project_loader import project_config
    modules = proposal.payload["modules"]
    project_config.set_active_modules(modules)
    logger.info("Modules update executed: %s", modules)
    return {"active_modules": modules}


async def _execute_knowledge_add(proposal: Proposal):
    """Add a document to the vector store."""
    from src.memory.vector_store import vector_store
    text       = proposal.payload["text"]
    metadata   = proposal.payload.get("metadata", {})
    collection = proposal.payload.get("collection")
    entry_id   = vector_store.add_entry(text, metadata=metadata, collection=collection)
    logger.info("Knowledge add executed: entry_id=%s", entry_id)
    return {"entry_id": entry_id}


async def _execute_knowledge_delete(proposal: Proposal):
    """Delete a knowledge entry from the vector store."""
    from src.memory.vector_store import vector_store
    entry_id   = proposal.payload["entry_id"]
    collection = proposal.payload.get("collection")
    vector_store.delete_entry(entry_id, collection=collection)
    logger.info("Knowledge delete executed: entry_id=%s", entry_id)
    return {"deleted": entry_id}


async def _execute_knowledge_import(proposal: Proposal):
    """Bulk-import documents to the vector store."""
    from src.memory.vector_store import vector_store
    entries    = proposal.payload["entries"]   # list of {text, metadata}
    collection = proposal.payload.get("collection")
    ids = []
    for entry in entries:
        eid = vector_store.add_entry(
            entry["text"], metadata=entry.get("metadata", {}), collection=collection
        )
        ids.append(eid)
    logger.info("Knowledge import executed: %d entries", len(ids))
    return {"imported": len(ids), "entry_ids": ids}


async def _execute_code_plan(proposal: Proposal):
    """Queue an AutoGen code plan after approval."""
    from src.integrations.autogen_runner import autogen_runner
    task      = proposal.payload["task"]
    run_id    = proposal.payload.get("run_id")
    result    = autogen_runner.plan(task, run_id=run_id)
    logger.info("Code plan executed: run_id=%s", result.get("run_id"))
    return result


async def _execute_code_execute(proposal: Proposal):
    """Execute an approved AutoGen code plan in the Docker sandbox."""
    from src.integrations.autogen_runner import autogen_runner
    run_id = proposal.payload["run_id"]
    result = autogen_runner.execute(run_id)
    logger.info("Code execute executed: run_id=%s", run_id)
    return result


async def _execute_mcp_invoke(proposal: Proposal):
    """Invoke an MCP tool after approval."""
    from src.integrations.mcp_registry import mcp_registry
    tool_name = proposal.payload["tool_name"]
    arguments = proposal.payload.get("arguments", {})
    result    = mcp_registry.invoke(tool_name, arguments)
    logger.info("MCP invoke executed: tool=%s", tool_name)
    return result


async def _execute_temporal_workflow_start(proposal: Proposal):
    """Start a Temporal durable workflow after approval."""
    from src.integrations.temporal_runner import temporal_runner
    workflow_name = proposal.payload["workflow_name"]
    payload       = proposal.payload.get("payload", {})
    result        = await temporal_runner.start_workflow(workflow_name, payload)
    logger.info("Temporal workflow started: %s", workflow_name)
    return result


async def _execute_onboarding_generate(proposal: Proposal):
    """Write onboarding-generated YAML files after approval."""
    from src.core.onboarding import generate_solution
    params = proposal.payload
    result = generate_solution(**params)
    logger.info("Onboarding generate executed: solution=%s", params.get("solution_name"))
    return result


async def _execute_implementation_plan(proposal: Proposal):
    """
    Execute an approved implementation plan.

    DEVELOP steps → CodingAgent writes code, creates a code_diff proposal for director review.
    All other steps → queue via TaskQueue as before.
    """
    import asyncio
    from src.core.proposal_store import get_proposal_store, RiskClass as _RC
    from src.core.queue_manager import task_queue

    steps        = proposal.payload.get("steps", [])
    plan_trace   = proposal.trace_id
    queued_ids   = []
    diff_proposals = []

    for step in steps:
        task_type = step.get("task_type", "").upper()

        if task_type == "DEVELOP":
            # Run CodingAgent in a thread (it's synchronous but may be slow)
            from src.agents.coder import coding_agent
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, coding_agent.implement_step, step, plan_trace
            )

            # Create a code_diff proposal for director review
            store = get_proposal_store()
            diff_proposal = store.create(
                action_type  = "code_diff",
                risk_class   = _RC.STATEFUL,
                payload      = {
                    "summary":       result["summary"],
                    "diff":          result["diff"],
                    "written_files": result["written_files"],
                    "test_result":   result["test_result"],
                    "tests_passed":  result["tests_passed"],
                    "plan_trace_id": plan_trace,
                    "step":          step,
                },
                description  = f"Code diff: {step.get('description', 'implementation')[:80]}",
                reversible   = True,   # rejection reverts via git checkout
                proposed_by  = "CodingAgent",
                required_role = "admin",
            )
            diff_proposals.append(diff_proposal.trace_id)
            logger.info("code_diff proposal created: %s", diff_proposal.trace_id)

            # Create isolated worktree for this code_diff proposal
            try:
                from src.core.worktree_manager import WorktreeManager
                _wt_mgr = WorktreeManager()
                _wt_mgr.create(diff_proposal.trace_id)
            except Exception as _wt_exc:
                logger.warning("Worktree creation failed (non-fatal): %s", _wt_exc)

        else:
            # Determine source scope from feature_request if available
            task_source = "sage"
            try:
                from src.core.queue_manager import _DB_PATH as _QDB
                import sqlite3 as _sq
                _conn = _sq.connect(_QDB)
                _conn.row_factory = _sq.Row
                _row = _conn.execute(
                    "SELECT scope FROM feature_requests WHERE plan_trace_id = ?",
                    (plan_trace,),
                ).fetchone()
                _conn.close()
                if _row:
                    task_source = _row["scope"]  # "sage" or "solution"
                else:
                    # Default: framework-generic task types → sage
                    _framework_types = {"ANALYZE", "DEVELOP", "REVIEW", "TEST", "PLAN", "DOCUMENT"}
                    task_source = "sage" if task_type.upper() in _framework_types else "solution"
            except Exception as _exc:
                logger.warning("Could not resolve task source scope: %s", _exc)

            task_id = task_queue.submit(
                task_type=task_type,
                payload=step.get("payload", {}),
                priority=5,
                plan_trace_id=plan_trace,
                source=task_source,
            )
            queued_ids.append(task_id)

    logger.info("Implementation plan executed: %d tasks queued, %d diff proposals created",
                len(queued_ids), len(diff_proposals))
    return {
        "tasks_queued":     len(queued_ids),
        "task_ids":         queued_ids,
        "diff_proposals":   diff_proposals,
        "diff_proposal_count": len(diff_proposals),
    }


async def _execute_code_diff(proposal: Proposal):
    """
    Execute an approved code_diff proposal.

    On approval: git add -A && git commit with a descriptive message.
    The commit records the director who approved it.
    """
    import subprocess

    diff     = proposal.payload.get("diff", "")
    summary  = proposal.payload.get("summary", "AI-generated code changes")
    files    = proposal.payload.get("written_files", [])
    tests_ok = proposal.payload.get("tests_passed", False)

    if not diff or diff.strip() == "(no changes detected)":
        return {"committed": False, "reason": "No changes to commit — diff was empty."}

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Use isolated worktree if available
    try:
        from src.core.worktree_manager import WorktreeManager
        _wt = WorktreeManager()
        _wt_path = _wt.get_path(proposal.trace_id)
        if _wt_path:
            root = _wt_path
            logger.info("code_diff executing in worktree: %s", root)
    except Exception as _wt_exc:
        logger.debug("Worktree lookup failed, using repo root: %s", _wt_exc)

    try:
        # Stage all changes
        subprocess.run(["git", "add", "-A"], cwd=root, check=True, timeout=10)

        # Commit
        commit_msg = (
            f"feat(sage-ai): {summary[:72]}\n\n"
            f"Implemented by CodingAgent via approved plan.\n"
            f"Files changed: {', '.join(files[:10])}\n"
            f"Tests passed: {tests_ok}\n"
            f"Approved proposal: {proposal.trace_id}\n\n"
            f"Co-Authored-By: SAGE CodingAgent <noreply@sage-ai>"
        )
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=root, check=True, timeout=15,
        )
        logger.info("code_diff committed: trace_id=%s", proposal.trace_id)
        return {"committed": True, "files": files, "summary": summary}

    except subprocess.CalledProcessError as exc:
        logger.error("git commit failed: %s", exc)
        return {"committed": False, "reason": str(exc)}


async def _revert_code_diff(proposal: Proposal):
    """
    Called when a code_diff proposal is rejected.
    Reverts all uncommitted changes so the working tree is clean.
    """
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        subprocess.run(["git", "checkout", "--", "."], cwd=root, check=True, timeout=10)
        subprocess.run(["git", "clean", "-fd"], cwd=root, check=True, timeout=10)
        logger.info("code_diff reverted: trace_id=%s", proposal.trace_id)
        return {"reverted": True}
    except subprocess.CalledProcessError as exc:
        logger.error("git revert failed: %s", exc)
        return {"reverted": False, "reason": str(exc)}


async def _execute_agent_hire(proposal: Proposal):
    """Append a new agent role to prompts.yaml and optionally task types to tasks.yaml.

    Delegates YAML persistence to RoleGenerator for consistency.
    """
    import yaml as _yaml
    from src.core.project_loader import project_config, _SOLUTIONS_DIR
    from src.core.role_generator import role_generator

    p         = proposal.payload
    role_id   = p["role_id"]
    solution  = p.get("solution", project_config.project_name)
    sol_dir   = os.path.join(_SOLUTIONS_DIR, solution)

    # ── 1. Update prompts.yaml via RoleGenerator ──────────────────────────
    role_data = {
        "name":          p["name"],
        "description":   p["description"],
        "icon":          p["icon"],
        "system_prompt": p["system_prompt"],
    }
    role_generator.add_role_to_yaml(solution, role_id, role_data)

    # ── 2. Update tasks.yaml (if task_types provided) ─────────────────────
    new_task_types = p.get("task_types", [])
    if new_task_types:
        tasks_path = os.path.join(sol_dir, "tasks.yaml")
        with open(tasks_path, "r", encoding="utf-8") as fh:
            tasks = _yaml.safe_load(fh) or {}

        existing = tasks.get("task_types", [])
        added = [t for t in new_task_types if t not in existing]
        tasks["task_types"] = existing + added

        if "task_descriptions" not in tasks:
            tasks["task_descriptions"] = {}
        for t in added:
            tasks["task_descriptions"][t] = f"Task handled by {p['name']}"

        with open(tasks_path, "w", encoding="utf-8") as fh:
            _yaml.dump(tasks, fh, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # ── 3. Hot-reload ──────────────────────────────────────────────────────
    project_config.reload(solution)
    logger.info("Agent hired: role_id=%s solution=%s", role_id, solution)
    return {"role_id": role_id, "solution": solution, "task_types_added": new_task_types}


# ---------------------------------------------------------------------------
# Dispatch map
# ---------------------------------------------------------------------------

_DISPATCH: dict = {
    "yaml_edit":                 _execute_yaml_edit,
    "config_switch":             _execute_config_switch,
    "llm_switch":                _execute_llm_switch,
    "config_modules":            _execute_config_modules,
    "knowledge_add":             _execute_knowledge_add,
    "knowledge_delete":          _execute_knowledge_delete,
    "knowledge_import":          _execute_knowledge_import,
    "code_plan":                 _execute_code_plan,
    "code_execute":              _execute_code_execute,
    "mcp_invoke":                _execute_mcp_invoke,
    "temporal_workflow_start":   _execute_temporal_workflow_start,
    "onboarding_generate":       _execute_onboarding_generate,
    "agent_hire":                _execute_agent_hire,
    "implementation_plan":       _execute_implementation_plan,
    "code_diff":                 _execute_code_diff,
}


# ---------------------------------------------------------------------------
# Public executor entry point
# ---------------------------------------------------------------------------

async def execute_approved_proposal(proposal: Proposal) -> dict:
    """
    Dispatch an approved proposal to its handler.
    Returns the execution result dict.
    Raises RuntimeError if the action_type is not registered.
    """
    handler = _DISPATCH.get(proposal.action_type)
    if handler is None:
        raise RuntimeError(
            f"No executor registered for action_type '{proposal.action_type}'. "
            f"Registered: {sorted(_DISPATCH.keys())}"
        )
    try:
        result = await handler(proposal)
        logger.info(
            "Proposal executed: trace_id=%s action=%s",
            proposal.trace_id, proposal.action_type,
        )
        return result or {}
    except Exception as exc:
        logger.error(
            "Proposal execution failed: trace_id=%s action=%s error=%s",
            proposal.trace_id, proposal.action_type, exc,
        )
        raise
