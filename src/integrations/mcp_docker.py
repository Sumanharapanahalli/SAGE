"""Docker-hosted MCP tools — agents get their tools from containers, not the laptop.

SAGE's existing `mcp_registry` loads IN-PROCESS Python modules and calls them as plain
functions. That is not the Model Context Protocol: there is no server, no sandbox, and
every tool's dependencies must be installed on the host. (`.mcp.json` in the repo root is
consumed by Claude Code, not by SAGE's runtime — it has never been wired to anything here.)

This module is a real MCP client. Each server runs as a container:

    docker run --rm -i mcp/fetch

and speaks MCP over stdin/stdout. Consequences that matter:

  * NOTHING IS INSTALLED ON THE HOST. A tool's dependencies live in its image.
  * TOOLS ARE SANDBOXED. A tool sees only what the image and the mounts we pass give it.
    Filesystem access is an explicit, read-only-by-default mount, not ambient authority.
  * SERVERS ARE PROVEN, NOT REINVENTED. Images come from Docker's official MCP catalog
    (the `mcp/*` namespace), driven by the official `mcp` Python SDK. We write no protocol.

Transport is the SDK's stdio client, so we implement none of the wire format ourselves.

Config lives in `config/mcp_docker.yaml` (see that file). Tools are exposed under a
namespaced name — ``fetch.fetch``, ``git.git_log`` — so two servers cannot collide, and
registered into the existing `mcp_registry` so every agent, the ReAct tool loop, and the
desktop's `mcp.tools` RPC pick them up with no change on their side.

    from src.integrations.mcp_docker import docker_mcp
    docker_mcp.list_tools()                       # [{name, description, schema, server}]
    docker_mcp.invoke("fetch.fetch", {"url": ...})
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("DockerMCP")

_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_CONFIG = _ROOT / "config" / "mcp_docker.yaml"


@dataclass
class DockerMCPServer:
    """One MCP server, run as a container."""

    name: str
    image: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    mounts: list[dict] = field(default_factory=list)  # [{source, target, read_only}]
    network: str = "none"       # deny network by default; opt in per server
    enabled: bool = True
    timeout: int = 120

    def docker_argv(self) -> list[str]:
        """The `docker run` argv. `-i` is required: MCP speaks over stdin/stdout."""
        argv = ["docker", "run", "--rm", "-i"]
        # A tool has no business reaching the network unless its whole job is to (fetch).
        if self.network:
            argv += ["--network", self.network]
        for k, v in self.env.items():
            argv += ["-e", f"{k}={v}"]
        for m in self.mounts:
            src = str(Path(os.path.expandvars(str(m["source"]))).resolve())
            tgt = str(m["target"])
            ro = "" if m.get("read_only") is False else ",readonly"
            argv += ["--mount", f"type=bind,source={src},target={tgt}{ro}"]
        argv += [self.image, *self.args]
        return argv


class DockerMCPClient:
    """Discovers and invokes MCP tools hosted in Docker containers.

    A container is spawned per call rather than held open. That costs ~1s of startup, and
    buys statelessness: a wedged or poisoned tool process cannot corrupt the next call, and
    there is no long-lived container to leak. Tool SCHEMAS are cached, so the cost is only
    paid on invocation, not on every `list_tools()`.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.logger = logging.getLogger("DockerMCP")
        self._config_path = Path(config_path) if config_path else _DEFAULT_CONFIG
        self._servers: dict[str, DockerMCPServer] = {}
        self._tools: list[dict] = []
        self._loaded = False
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- config
    def load_config(self) -> int:
        """Read the server list. Returns how many enabled servers were configured."""
        self._servers.clear()
        if not self._config_path.exists():
            self.logger.info("no docker MCP config at %s", self._config_path)
            return 0
        try:
            import yaml

            raw = yaml.safe_load(self._config_path.read_text(encoding="utf-8")) or {}
        except Exception as e:  # noqa: BLE001
            self.logger.warning("could not read %s: %s", self._config_path, e)
            return 0

        for name, spec in (raw.get("servers") or {}).items():
            # YAML 1.1 parses a bare `on:` / `off:` / `yes:` key as a BOOLEAN, so a server
            # name can arrive as True. Tool lookup is "<server>.<tool>" string work, which
            # would then never match — the tool would exist and be permanently unreachable.
            name = str(name)
            if not isinstance(spec, dict) or not spec.get("image"):
                self.logger.warning("mcp_docker server '%s': missing 'image' — skipped", name)
                continue
            srv = DockerMCPServer(
                name=name,
                image=spec["image"],
                args=list(spec.get("args") or []),
                env=dict(spec.get("env") or {}),
                mounts=list(spec.get("mounts") or []),
                network=spec.get("network", "none"),
                enabled=bool(spec.get("enabled", True)),
                timeout=int(spec.get("timeout", 120)),
            )
            if srv.enabled:
                self._servers[name] = srv
        return len(self._servers)

    # ---------------------------------------------------------------- docker
    @staticmethod
    def docker_available() -> bool:
        """True only if the daemon actually answers. `docker` being on PATH is not enough —
        Docker Desktop ships a CLI that resolves fine while the engine is stopped."""
        if not shutil.which("docker"):
            return False
        try:
            p = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                               capture_output=True, text=True, timeout=15)
            return p.returncode == 0 and bool(p.stdout.strip())
        except Exception:  # noqa: BLE001
            return False

    def image_present(self, image: str) -> bool:
        try:
            p = subprocess.run(["docker", "image", "inspect", image],
                               capture_output=True, text=True, timeout=30)
            return p.returncode == 0
        except Exception:  # noqa: BLE001
            return False

    def pull(self, image: str, timeout: int = 900) -> bool:
        self.logger.info("pulling MCP image %s ...", image)
        try:
            p = subprocess.run(["docker", "pull", image],
                               capture_output=True, text=True, timeout=timeout)
            return p.returncode == 0
        except Exception as e:  # noqa: BLE001
            self.logger.warning("pull %s failed: %s", image, e)
            return False

    # ------------------------------------------------------------ MCP session
    async def _session(self, srv: DockerMCPServer, fn):
        """Open one MCP stdio session against a container and hand it to `fn`."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        argv = srv.docker_argv()
        params = StdioServerParameters(command=argv[0], args=argv[1:], env=None)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await fn(session)

    def _run_async(self, coro_fn, timeout: int):
        """Run an async MCP session from sync code — including from inside a running loop.

        SAGE's agents are sync, but the sidecar and API can already be inside an event loop.
        asyncio.run() would raise there, so hop to a worker thread when a loop is running.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(asyncio.wait_for(coro_fn(), timeout))
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                asyncio.run, asyncio.wait_for(coro_fn(), timeout)
            ).result(timeout=timeout + 30)

    # ---------------------------------------------------------------- discovery
    def load(self, force: bool = False) -> int:
        """Discover tools from every configured server. Returns the tool count.

        A server that cannot be reached is SKIPPED WITH A WARNING, never faked: a tool that
        is advertised but cannot run is worse than an absent one — an agent will plan around
        it and fail downstream.
        """
        with self._lock:
            if self._loaded and not force:
                return len(self._tools)

            self.load_config()
            self._tools = []

            if not self._servers:
                self._loaded = True
                return 0
            if not self.docker_available():
                self.logger.warning(
                    "Docker daemon not reachable — %d MCP server(s) unavailable: %s",
                    len(self._servers), ", ".join(self._servers),
                )
                self._loaded = True
                return 0

            for name, srv in self._servers.items():
                if not self.image_present(srv.image) and not self.pull(srv.image):
                    self.logger.warning("MCP server '%s': image %s unavailable — skipped",
                                        name, srv.image)
                    continue
                try:
                    async def _list(session):
                        return await session.list_tools()

                    result = self._run_async(lambda s=srv: self._session(s, _list), srv.timeout)
                    for t in result.tools:
                        self._tools.append({
                            "name": f"{name}.{t.name}",
                            "server": name,
                            "tool": t.name,
                            "description": t.description or "",
                            "schema": getattr(t, "inputSchema", None) or {},
                            "source": f"docker:{srv.image}",
                        })
                    self.logger.info("MCP server '%s' (%s): %d tools",
                                     name, srv.image, len(result.tools))
                except Exception as e:  # noqa: BLE001
                    self.logger.warning("MCP server '%s' failed to start: %s", name, e)

            self._loaded = True
            return len(self._tools)

    def list_tools(self) -> list[dict]:
        self.load()
        return list(self._tools)

    # ---------------------------------------------------------------- invocation
    def invoke(self, tool_name: str, args: dict | None = None) -> dict:
        """Invoke `<server>.<tool>` inside its container. Returns {result} or {error}."""
        self.load()
        args = args or {}

        if "." not in tool_name:
            return {"error": f"tool '{tool_name}' must be '<server>.<tool>'"}
        server_name, _, bare = tool_name.partition(".")
        srv = self._servers.get(server_name)
        if srv is None:
            return {"error": f"unknown MCP server '{server_name}'. "
                             f"Configured: {sorted(self._servers)}"}
        if not any(t["name"] == tool_name for t in self._tools):
            return {"error": f"unknown tool '{tool_name}'. "
                             f"Available: {[t['name'] for t in self._tools]}"}

        try:
            async def _call(session):
                return await session.call_tool(bare, args)

            res = self._run_async(lambda: self._session(srv, _call), srv.timeout)
        except Exception as e:  # noqa: BLE001
            self.logger.warning("MCP invoke %s failed: %s", tool_name, e)
            return {"error": f"{type(e).__name__}: {e}", "tool_name": tool_name}

        # Flatten MCP content blocks to text — SAGE's tool interface is text in, text out.
        parts: list[str] = []
        for block in getattr(res, "content", []) or []:
            text = getattr(block, "text", None)
            parts.append(text if text is not None else str(block))
        out = "\n".join(parts)

        if getattr(res, "isError", False):
            return {"error": out or "tool reported an error", "tool_name": tool_name}
        return {"result": out, "tool_name": tool_name}

    # ------------------------------------------------- bridge into SAGE's registry
    def register_into(self, registry) -> int:
        """Expose these tools through the existing mcp_registry.

        Agents, the ReAct loop and the desktop's `mcp.tools` RPC all read that registry, so
        registering here means Docker tools appear everywhere with no change on their side.
        """
        n = 0
        for t in self.list_tools():
            name = t["name"]

            def _call(_n=name, **kwargs):
                r = self.invoke(_n, kwargs)
                if "error" in r:
                    raise RuntimeError(r["error"])
                return r["result"]

            _call.__name__ = name.replace(".", "_")
            _call.__doc__ = t["description"]
            registry._tool_map[name] = _call  # noqa: SLF001 — the registry's own idiom
            n += 1
        if n:
            logger.info("registered %d Docker MCP tools into mcp_registry", n)
        return n


docker_mcp = DockerMCPClient()
