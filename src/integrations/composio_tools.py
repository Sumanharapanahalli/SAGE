"""
SAGE Framework — Composio Tool Integration
==========================================
Provides 100+ pre-built tool integrations for AI agents via Composio.
Each integration handles OAuth/auth automatically — no per-tool credential
management needed in SAGE.

Setup:
  1. pip install composio-langchain
  2. Set COMPOSIO_API_KEY in .env  (get at app.composio.dev)
  3. Run: composio add github   (or any app — one-time OAuth flow)
  4. In project.yaml integrations: [composio:github, composio:jira, ...]

Supported apps (subset — Composio has 100+):
  github, gitlab, jira, linear, slack, notion, confluence, salesforce,
  hubspot, asana, trello, zendesk, gmail, gcal, gdrive, sheets,
  postgres, mysql, stripe, shopify, intercom, discord, figma, ...

All imports are lazy — if composio-langchain is not installed,
tools are skipped with a warning (no crash).
"""

import logging
import os
from typing import Optional

logger = logging.getLogger("ComposioTools")


def get_composio_tools(app_names: list[str]) -> dict:
    """
    Load Composio tools for the given app names.

    Args:
        app_names: List of Composio app names (e.g. ["github", "jira"]).
                   These are the part after "composio:" in project.yaml.

    Returns:
        dict of tool_name -> callable. Empty dict if Composio unavailable.
    """
    if not app_names:
        return {}

    api_key = os.environ.get("COMPOSIO_API_KEY", "")
    if not api_key:
        logger.warning(
            "COMPOSIO_API_KEY not set — Composio tools unavailable. "
            "Get a key at app.composio.dev"
        )
        return {}

    try:
        from composio_langchain import ComposioToolSet
    except ImportError:
        logger.warning(
            "composio-langchain not installed — run: pip install composio-langchain"
        )
        return {}

    tools: dict = {}
    try:
        toolset = ComposioToolSet(api_key=api_key)
        lc_tools = toolset.get_tools(apps=app_names)
        for tool in lc_tools:
            name = getattr(tool, "name", None) or getattr(tool, "__name__", str(tool))
            tools[name] = tool
            logger.debug("Loaded Composio tool: %s", name)
        logger.info(
            "Composio: loaded %d tool(s) for apps: %s",
            len(tools),
            ", ".join(app_names),
        )
    except Exception as exc:
        logger.warning("Composio tool loading failed: %s", exc)

    return tools


def list_connected_apps() -> list[dict]:
    """
    Return a list of apps the user has connected via Composio.
    Each entry: {app: str, status: str, connected_account_id: str}
    """
    api_key = os.environ.get("COMPOSIO_API_KEY", "")
    if not api_key:
        return []
    try:
        from composio import ComposioToolSet
        toolset = ComposioToolSet(api_key=api_key)
        accounts = toolset.get_connected_accounts()
        return [
            {
                "app": getattr(a, "appName", str(a)),
                "status": getattr(a, "status", "connected"),
                "connected_account_id": getattr(a, "id", ""),
            }
            for a in (accounts or [])
        ]
    except Exception as exc:
        logger.warning("Composio list_connected_apps failed: %s", exc)
        return []


def get_connection_url(app_name: str, redirect_url: Optional[str] = None) -> Optional[str]:
    """
    Initiate a Composio OAuth connection for an app.
    Returns the URL the user should visit to authorise the connection.
    """
    api_key = os.environ.get("COMPOSIO_API_KEY", "")
    if not api_key:
        return None
    try:
        from composio import ComposioToolSet
        toolset = ComposioToolSet(api_key=api_key)
        connection = toolset.initiate_connection(
            app_name=app_name.upper(),
            redirect_url=redirect_url,
        )
        return getattr(connection, "redirectUrl", None) or getattr(connection, "redirect_url", None)
    except Exception as exc:
        logger.warning("Composio get_connection_url failed for %s: %s", app_name, exc)
        return None


def is_available() -> bool:
    """True if composio-langchain is installed and COMPOSIO_API_KEY is set."""
    if not os.environ.get("COMPOSIO_API_KEY", ""):
        return False
    try:
        import composio_langchain  # noqa: F401
        return True
    except ImportError:
        return False
