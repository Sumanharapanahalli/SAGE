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
        ClaudeCodeCLIProvider, ClaudeAPIProvider
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
        gw.provider = ClaudeCodeCLIProvider(llm_cfg)
    else:
        if req_model:
            llm_cfg["claude_model"] = req_model
        gw.provider = ClaudeAPIProvider(llm_cfg)

    gw.reset_usage()
    logger.info("LLM switch executed: provider=%s model=%s", req_provider, req_model)
    return {"provider": req_provider, "provider_name": gw.get_provider_name()}


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
