"""Tests for Docker-hosted MCP tools.

The container-dependent tests are marked `docker` and skip when the daemon is not
reachable, so CI without Docker stays green. Everything that can be asserted without a
daemon — argv construction, the security defaults, graceful degradation — is asserted
unconditionally, because those are the parts that silently do damage if they regress.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.integrations.mcp_docker import DockerMCPClient, DockerMCPServer

pytestmark = pytest.mark.unit

docker_up = pytest.mark.skipif(
    not DockerMCPClient.docker_available(),
    reason="Docker daemon not reachable",
)


# --------------------------------------------------------------- argv / security defaults
def test_argv_is_interactive_and_removed():
    """MCP speaks over stdin/stdout, so -i is mandatory; --rm or containers pile up."""
    argv = DockerMCPServer(name="fetch", image="mcp/fetch").docker_argv()
    assert argv[:4] == ["docker", "run", "--rm", "-i"]
    assert argv[-1] == "mcp/fetch"


def test_network_is_denied_by_default():
    """A tool with ambient network access is an exfiltration path. Deny unless asked."""
    argv = DockerMCPServer(name="git", image="mcp/git").docker_argv()
    assert "--network" in argv and argv[argv.index("--network") + 1] == "none"


def test_network_can_be_opted_into():
    argv = DockerMCPServer(
        name="fetch", image="mcp/fetch", network="bridge"
    ).docker_argv()
    assert argv[argv.index("--network") + 1] == "bridge"


def test_mounts_are_readonly_unless_explicitly_writable(tmp_path):
    """A tool that can write to the repo can bypass the HITL gate by editing code directly."""
    srv = DockerMCPServer(
        name="fs",
        image="mcp/filesystem",
        mounts=[{"source": str(tmp_path), "target": "/workspace"}],
    )
    mount = srv.docker_argv()[srv.docker_argv().index("--mount") + 1]
    assert mount.endswith(",readonly")
    assert "target=/workspace" in mount


def test_mount_can_be_made_writable_explicitly(tmp_path):
    srv = DockerMCPServer(
        name="fs",
        image="mcp/filesystem",
        mounts=[{"source": str(tmp_path), "target": "/w", "read_only": False}],
    )
    mount = srv.docker_argv()[srv.docker_argv().index("--mount") + 1]
    assert not mount.endswith(",readonly")


def test_env_is_passed(tmp_path):
    argv = DockerMCPServer(name="x", image="img", env={"TOKEN": "abc"}).docker_argv()
    assert "-e" in argv and "TOKEN=abc" in argv


# ------------------------------------------------------------------------------- config
def _write_cfg(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "mcp_docker.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_disabled_servers_are_not_loaded(tmp_path):
    cfg = _write_cfg(
        tmp_path,
        """
        servers:
          alpha: {image: mcp/fetch, enabled: true}
          beta:  {image: mcp/git,   enabled: false}
    """,
    )
    c = DockerMCPClient(config_path=cfg)
    assert c.load_config() == 1
    assert "alpha" in c._servers and "beta" not in c._servers


def test_yaml_boolean_server_names_are_coerced_to_strings(tmp_path):
    """YAML 1.1 parses bare `on:`/`off:`/`yes:` as BOOLEANS, so a server keyed `on:` arrives
    as True. An unquoted name would then be a bool, and `"<server>.<tool>"` lookups — which
    are string ops — would silently never match. Coerce, so the tool is still reachable."""
    cfg = _write_cfg(
        tmp_path,
        """
        servers:
          on: {image: mcp/fetch}
    """,
    )
    c = DockerMCPClient(config_path=cfg)
    assert c.load_config() == 1
    assert "True" in c._servers
    assert all(isinstance(k, str) for k in c._servers)


def test_server_without_image_is_skipped_not_crashed(tmp_path):
    cfg = _write_cfg(
        tmp_path,
        """
        servers:
          broken: {args: ["x"]}
          good:   {image: mcp/fetch}
    """,
    )
    c = DockerMCPClient(config_path=cfg)
    assert c.load_config() == 1
    assert "good" in c._servers


def test_missing_config_is_not_fatal(tmp_path):
    c = DockerMCPClient(config_path=tmp_path / "nope.yaml")
    assert c.load_config() == 0
    assert c.load() == 0  # must degrade, not raise
    assert c.list_tools() == []


def test_invoke_requires_namespaced_name(tmp_path):
    c = DockerMCPClient(config_path=tmp_path / "nope.yaml")
    assert "error" in c.invoke("fetch", {})  # missing "<server>."


def test_invoke_unknown_server_errors_cleanly(tmp_path):
    c = DockerMCPClient(config_path=tmp_path / "nope.yaml")
    r = c.invoke("ghost.tool", {})
    assert "error" in r and "ghost" in r["error"]


# -------------------------------------------------------------------- real containers
@docker_up
def test_discovers_and_invokes_a_real_containerised_tool(tmp_path):
    """The whole point: a tool runs in a container, and nothing is installed on the host."""
    cfg = _write_cfg(
        tmp_path,
        """
        servers:
          fetch:
            image: mcp/fetch
            network: bridge
            timeout: 180
    """,
    )
    c = DockerMCPClient(config_path=cfg)
    if not c.image_present("mcp/fetch") and not c.pull("mcp/fetch"):
        pytest.skip("mcp/fetch image unavailable")

    tools = c.list_tools()
    names = [t["name"] for t in tools]
    assert "fetch.fetch" in names, f"expected fetch.fetch, got {names}"
    assert tools[0]["source"].startswith("docker:")

    r = c.invoke("fetch.fetch", {"url": "https://example.com", "max_length": 300})
    assert "result" in r, r
    assert "Example Domain" in r["result"]


@docker_up
def test_registers_into_the_shared_registry(tmp_path):
    """Agents read mcp_registry — Docker tools must appear there, not in a side channel."""
    cfg = _write_cfg(
        tmp_path,
        """
        servers:
          fetch: {image: mcp/fetch, network: bridge, timeout: 180}
    """,
    )
    c = DockerMCPClient(config_path=cfg)
    if not c.image_present("mcp/fetch"):
        pytest.skip("mcp/fetch image not pulled")

    class _Reg:
        def __init__(self):
            self._tool_map = {}

    reg = _Reg()
    assert c.register_into(reg) >= 1
    assert "fetch.fetch" in reg._tool_map
    assert callable(reg._tool_map["fetch.fetch"])
