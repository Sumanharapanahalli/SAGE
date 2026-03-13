"""
SAGE Framework — MCP Registry
==============================
Discovers and manages MCP (Model Context Protocol) servers for the active
solution. Provides a unified interface for agents to list and invoke tools
without knowing which server file they live in.

Architecture:
  solutions/<name>/mcp_servers/*.py   ← each file is an MCP server module
                                         containing `mcp = FastMCP(...)`
                                         with @mcp.tool() decorated functions

  MCPRegistry.list_tools()            ← returns all available tools with docs
  MCPRegistry.invoke(tool, args)      ← calls any tool by name

Every tool invocation is audit-logged with a trace_id.

The registry is domain-agnostic: it discovers whatever tools the active
solution defines, not a hardcoded list.
"""

import importlib
import importlib.util
import logging
import os
import sys

logger = logging.getLogger("MCPRegistry")


class MCPRegistry:
    """
    Discovers MCP server modules in solutions/<name>/mcp_servers/ and
    provides a unified tool interface for agents.

    Usage:
        from src.integrations.mcp_registry import mcp_registry
        tools = mcp_registry.list_tools()
        result = mcp_registry.invoke("flash_firmware", {"bin_path": "..."})
    """

    def __init__(self):
        self._servers: dict[str, object] = {}   # module_name -> module
        self._tool_map: dict[str, callable] = {}  # tool_name -> function
        self._loaded_solution: str = ""

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _get_mcp_dir(self) -> str:
        """Resolve path to active solution's mcp_servers/ directory."""
        try:
            from src.core.project_loader import project_config, _SOLUTIONS_DIR
            return os.path.join(_SOLUTIONS_DIR, project_config.project_name, "mcp_servers")
        except Exception:
            return ""

    def load(self, force: bool = False) -> int:
        """
        Discover and import all MCP server modules for the active solution.

        Args:
            force: Re-discover even if already loaded for this solution.

        Returns:
            Number of tools registered.
        """
        try:
            from src.core.project_loader import project_config
            solution = project_config.project_name
        except Exception:
            solution = ""

        if not force and solution == self._loaded_solution and self._tool_map:
            return len(self._tool_map)

        self._servers.clear()
        self._tool_map.clear()
        self._loaded_solution = solution

        mcp_dir = self._get_mcp_dir()
        if not mcp_dir or not os.path.isdir(mcp_dir):
            logger.debug("No mcp_servers/ directory found at: %s", mcp_dir)
            return 0

        # Add solution dir to sys.path so servers can do relative imports
        solution_dir = os.path.dirname(mcp_dir)
        if solution_dir not in sys.path:
            sys.path.insert(0, solution_dir)

        for filename in sorted(os.listdir(mcp_dir)):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue
            self._load_server(mcp_dir, filename)

        logger.info(
            "MCPRegistry loaded %d tool(s) from %d server(s) [solution: %s]",
            len(self._tool_map), len(self._servers), solution,
        )
        return len(self._tool_map)

    def _load_server(self, mcp_dir: str, filename: str) -> None:
        """Import a single MCP server module and register its tools."""
        module_name = filename[:-3]  # strip .py
        module_path = os.path.join(mcp_dir, filename)

        try:
            spec = importlib.util.spec_from_file_location(
                f"mcp_servers.{module_name}", module_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self._servers[module_name] = module

            # Find the FastMCP instance — conventionally named `mcp`
            mcp_instance = getattr(module, "mcp", None)
            if mcp_instance is None:
                logger.debug("No 'mcp' attribute in %s — skipping", filename)
                return

            # Extract registered tools from FastMCP
            tool_count = self._register_tools_from_mcp(module_name, module, mcp_instance)
            logger.debug("Loaded server %s — %d tool(s)", filename, tool_count)

        except Exception as exc:
            logger.warning("Could not load MCP server %s: %s", filename, exc)

    def _register_tools_from_mcp(self, server_name: str, module, mcp_instance) -> int:
        """
        Extract tool callables from a FastMCP instance.

        FastMCP stores tools in ._tools (dict[name -> Tool]) where each Tool
        has a .fn callable. Fall back to scanning module functions decorated
        with __mcp_tool__ if the private attr is absent.
        """
        count = 0

        # FastMCP internal: _tool_manager._tools or ._tools
        raw_tools: dict = {}
        for attr in ("_tool_manager", "_tools"):
            obj = getattr(mcp_instance, attr, None)
            if obj is not None:
                if hasattr(obj, "_tools"):
                    raw_tools = getattr(obj, "_tools", {})
                elif isinstance(obj, dict):
                    raw_tools = obj
                if raw_tools:
                    break

        if raw_tools:
            for tool_name, tool_obj in raw_tools.items():
                fn = getattr(tool_obj, "fn", None) or getattr(tool_obj, "func", None)
                if callable(fn):
                    self._tool_map[tool_name] = fn
                    count += 1
            return count

        # Fallback: scan module-level callables tagged by FastMCP decorator
        for attr_name in dir(module):
            fn = getattr(module, attr_name, None)
            if callable(fn) and getattr(fn, "_is_mcp_tool", False):
                self._tool_map[attr_name] = fn
                count += 1

        return count

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def list_tools(self) -> list[dict]:
        """
        Return metadata for all registered tools.

        Returns:
            List of dicts: [{name, description, server}, ...]
        """
        self.load()
        tools = []
        for tool_name, fn in self._tool_map.items():
            tools.append({
                "name":        tool_name,
                "description": (fn.__doc__ or "").strip().split("\n")[0],
                "server":      getattr(fn, "__module__", "unknown"),
            })
        return sorted(tools, key=lambda t: t["name"])

    def invoke(self, tool_name: str, args: dict = None, trace_id: str = None) -> dict:
        """
        Call a registered MCP tool by name and audit the invocation.

        Args:
            tool_name: Name of the tool to invoke.
            args:      Keyword arguments to pass to the tool function.
            trace_id:  Optional SAGE trace ID for audit correlation.

        Returns:
            dict with 'result' key on success, 'error' key on failure.
        """
        self.load()
        args = args or {}

        fn = self._tool_map.get(tool_name)
        if fn is None:
            available = list(self._tool_map.keys())
            return {
                "error": f"Tool '{tool_name}' not found. Available: {available}",
                "tool_name": tool_name,
            }

        try:
            result = fn(**args)
            self._audit(tool_name, args, result, trace_id, success=True)
            return {"result": result, "tool_name": tool_name}
        except Exception as exc:
            logger.error("MCP tool '%s' raised: %s", tool_name, exc)
            self._audit(tool_name, args, str(exc), trace_id, success=False)
            return {"error": str(exc), "tool_name": tool_name}

    def _audit(self, tool_name: str, args: dict, result, trace_id: str, success: bool) -> None:
        """Write MCP tool invocation to the audit log."""
        try:
            import json
            from src.memory.audit_logger import audit_logger
            audit_logger.log_event(
                actor="MCPRegistry",
                action_type="MCP_TOOL_INVOKED",
                input_context=f"{tool_name}({json.dumps(args)[:300]})",
                output_content=str(result)[:500],
                metadata={
                    "tool_name": tool_name,
                    "success": success,
                    **({"trace_id": trace_id} if trace_id else {}),
                },
            )
        except Exception as exc:
            logger.debug("Audit log for MCP tool failed (non-fatal): %s", exc)

    def as_react_tools(self, trace_id: str = None) -> dict:
        """
        Return tools as a dict compatible with DeveloperAgent._react_loop().

        Each value is a callable that accepts keyword args and returns a string.
        """
        self.load()
        react_tools = {}
        for tool_name in self._tool_map:
            # Capture tool_name in closure
            def _make_caller(name):
                def _call(**kw):
                    r = self.invoke(name, kw, trace_id=trace_id)
                    return r.get("result", r.get("error", "no result"))
                _call.__name__ = name
                return _call
            react_tools[tool_name] = _make_caller(tool_name)
        return react_tools


# Global singleton — lazily loads tools on first use
mcp_registry = MCPRegistry()
