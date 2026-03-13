"""
SAGE Framework — LangChain Tools Integration
=============================================
Loads pre-built LangChain tool integrations based on the active solution's
`integrations` list in project.yaml.

Each tool is a plain callable: (args...) -> str | dict
These are injected into DeveloperAgent._react_loop() and UniversalAgent.

Supported integrations (grows over time — add new loaders below):
  gitlab      — GitLab REST API (already handled natively by DeveloperAgent)
  jira        — Jira issue search, create, update
  confluence  — Confluence page search
  slack       — Slack message send
  database    — SQL query execution (DATABASE_URL env var)
  github      — GitHub issues and PRs

All imports are lazy and gracefully handled — if a LangChain integration
package is not installed, the tool is skipped with a warning, not a crash.
"""

import logging
import os

logger = logging.getLogger("LangChainTools")


def get_tools_for_solution(solution_name: str = None) -> dict:
    """
    Return a dict of tool_name -> callable for the active solution.

    Reads the active project's integrations list and loads the corresponding
    LangChain tool wrappers. Always includes 'search_memory' (SAGE vector store).

    Args:
        solution_name: Optional override. Defaults to the active project.

    Returns:
        dict mapping tool name (str) to callable.
    """
    tools: dict = {}

    # --- Always available: SAGE vector memory search ---
    def _search_memory(query: str) -> str:
        try:
            from src.memory.vector_store import vector_memory
            results = vector_memory.search(query, k=3)
            return "\n---\n".join(results) if results else "No relevant memory found."
        except Exception as exc:
            return f"Memory search error: {exc}"

    tools["search_memory"] = _search_memory

    # --- Load integrations from active project config ---
    try:
        from src.core.project_loader import project_config
        integrations = project_config.metadata.get("integrations", [])
    except Exception as exc:
        logger.warning("Could not load project integrations: %s", exc)
        return tools

    for integration in integrations:
        loader = _LOADERS.get(integration)
        if loader is None:
            continue
        try:
            new_tools = loader()
            if new_tools:
                tools.update(new_tools)
                logger.info("Loaded %d tool(s) for integration: %s", len(new_tools), integration)
        except Exception as exc:
            logger.warning("Failed to load tools for '%s': %s", integration, exc)

    logger.info("Tool registry built: %s", list(tools.keys()))
    return tools


# ---------------------------------------------------------------------------
# Integration loaders — each returns a dict of tool_name -> callable
# Returns None / empty dict if deps are missing (graceful degradation)
# ---------------------------------------------------------------------------

def _load_jira_tools() -> dict:
    try:
        from langchain_community.utilities.jira import JiraAPIWrapper
        jira = JiraAPIWrapper()
        return {
            "search_jira": lambda query: jira.run(f"Search for issues: {query}"),
            "create_jira_issue": lambda summary, desc="": jira.run(
                f"Create issue with summary '{summary}' and description '{desc}'"
            ),
        }
    except ImportError:
        logger.warning("jira tools unavailable — install langchain-community")
        return {}
    except Exception as exc:
        logger.warning("Jira setup failed: %s", exc)
        return {}


def _load_confluence_tools() -> dict:
    try:
        from langchain_community.utilities.confluence import ConfluenceAPIWrapper
        conf = ConfluenceAPIWrapper()
        return {
            "search_confluence": lambda query: conf.run(query),
        }
    except ImportError:
        logger.warning("confluence tools unavailable — install langchain-community")
        return {}
    except Exception as exc:
        logger.warning("Confluence setup failed: %s", exc)
        return {}


def _load_slack_tools() -> dict:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not set — slack send tool unavailable")
        return {}
    try:
        import requests

        def _send_slack(text: str, channel: str = "#general") -> str:
            resp = requests.post(webhook_url, json={"text": text, "channel": channel}, timeout=10)
            return "sent" if resp.status_code == 200 else f"error {resp.status_code}"

        return {"send_slack_message": _send_slack}
    except Exception as exc:
        logger.warning("Slack tool setup failed: %s", exc)
        return {}


def _load_database_tools() -> dict:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        logger.warning("DATABASE_URL not set — database query tool unavailable")
        return {}
    try:
        from langchain_community.utilities import SQLDatabase
        from langchain_community.tools import QuerySQLDataBaseTool
        db   = SQLDatabase.from_uri(db_url)
        tool = QuerySQLDataBaseTool(db=db)
        return {"query_database": lambda sql: tool.run(sql)}
    except ImportError:
        logger.warning("database tools unavailable — install langchain-community sqlalchemy")
        return {}
    except Exception as exc:
        logger.warning("Database tool setup failed: %s", exc)
        return {}


def _load_github_tools() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        logger.warning("GITHUB_TOKEN not set — github tools unavailable")
        return {}
    try:
        from langchain_community.utilities.github import GitHubAPIWrapper
        gh = GitHubAPIWrapper()
        return {
            "search_github_issues": lambda query: gh.run(f"search issues: {query}"),
        }
    except ImportError:
        logger.warning("github tools unavailable — install langchain-community pygithub")
        return {}
    except Exception as exc:
        logger.warning("GitHub tool setup failed: %s", exc)
        return {}


# Registry: integration name -> loader function
_LOADERS = {
    "jira":       _load_jira_tools,
    "confluence": _load_confluence_tools,
    "slack":      _load_slack_tools,
    "database":   _load_database_tools,
    "github":     _load_github_tools,
    # "gitlab" is handled natively by DeveloperAgent — no LangChain wrapper needed
    # "teams" is handled natively by MonitorAgent — no LangChain wrapper needed
}
