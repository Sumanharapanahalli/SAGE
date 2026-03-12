"""
Setup script: Configures Gemini CLI to use all SAGE[ai] MCP servers.
Run once: python scripts/setup_gemini_mcp.py

This script:
  1. Reads (or creates) ~/.gemini/settings.json
  2. Adds/updates the mcpServers section with all SAGE[ai] servers
  3. Writes the updated settings back
  4. Prints a success summary and instructions for the GitLab MCP
"""

import json
import os
import sys

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
MCP_DIR = os.path.join(PROJECT_ROOT, "mcp_servers")

GEMINI_DIR = os.path.expanduser("~/.gemini")
SETTINGS_PATH = os.path.join(GEMINI_DIR, "settings.json")


# ---------------------------------------------------------------------------
# MCP Server Definitions
# ---------------------------------------------------------------------------

def _server_entry(name: str, script: str, env: dict = None) -> dict:
    """Builds a Gemini MCP server entry."""
    entry = {
        "command": sys.executable,  # Use the same Python interpreter running this script
        "args": [script],
    }
    if env:
        entry["env"] = env
    return entry


SAGE_MCP_SERVERS = {
    "sage-serial": _server_entry(
        "sage-serial",
        os.path.join(MCP_DIR, "serial_port_server.py"),
    ),
    "sage-jlink": _server_entry(
        "sage-jlink",
        os.path.join(MCP_DIR, "jlink_server.py"),
    ),
    "sage-metabase": _server_entry(
        "sage-metabase",
        os.path.join(MCP_DIR, "metabase_server.py"),
        env={
            "METABASE_URL": "${METABASE_URL}",
            "METABASE_USERNAME": "${METABASE_USERNAME}",
            "METABASE_PASSWORD": "${METABASE_PASSWORD}",
            "METABASE_ERROR_QUESTION_ID": "${METABASE_ERROR_QUESTION_ID}",
        },
    ),
    "sage-spira": _server_entry(
        "sage-spira",
        os.path.join(MCP_DIR, "spira_server.py"),
        env={
            "SPIRA_URL": "${SPIRA_URL}",
            "SPIRA_USERNAME": "${SPIRA_USERNAME}",
            "SPIRA_API_KEY": "${SPIRA_API_KEY}",
            "SPIRA_PROJECT_ID": "${SPIRA_PROJECT_ID}",
        },
    ),
    "sage-teams": _server_entry(
        "sage-teams",
        os.path.join(MCP_DIR, "teams_server.py"),
        env={
            "TEAMS_TENANT_ID": "${TEAMS_TENANT_ID}",
            "TEAMS_CLIENT_ID": "${TEAMS_CLIENT_ID}",
            "TEAMS_CLIENT_SECRET": "${TEAMS_CLIENT_SECRET}",
            "TEAMS_INCOMING_WEBHOOK_URL": "${TEAMS_INCOMING_WEBHOOK_URL}",
        },
    ),
}


# ---------------------------------------------------------------------------
# Main Setup Logic
# ---------------------------------------------------------------------------

def setup():
    print("=" * 60)
    print("  SAGE[ai] — Gemini CLI MCP Setup")
    print("=" * 60)

    # 1. Ensure ~/.gemini directory exists
    os.makedirs(GEMINI_DIR, exist_ok=True)
    print(f"\n  Gemini config dir: {GEMINI_DIR}")

    # 2. Read existing settings or start fresh
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            try:
                settings = json.load(f)
            except json.JSONDecodeError:
                print(f"  WARNING: Existing {SETTINGS_PATH} is invalid JSON. Starting fresh.")
                settings = {}
        print(f"  Loaded existing settings: {SETTINGS_PATH}")
    else:
        settings = {}
        print(f"  No existing settings found — creating new: {SETTINGS_PATH}")

    # 3. Merge MCP servers
    if "mcpServers" not in settings:
        settings["mcpServers"] = {}

    existing_count = len(settings["mcpServers"])
    added = []
    updated = []

    for server_name, server_config in SAGE_MCP_SERVERS.items():
        if server_name in settings["mcpServers"]:
            settings["mcpServers"][server_name] = server_config
            updated.append(server_name)
        else:
            settings["mcpServers"][server_name] = server_config
            added.append(server_name)

    # 4. Write back
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

    # 5. Print summary
    print(f"\n  MCP servers configured: {len(settings['mcpServers'])} total")
    if added:
        print(f"  Added:   {', '.join(added)}")
    if updated:
        print(f"  Updated: {', '.join(updated)}")

    print("\n  Server paths:")
    for name, cfg in SAGE_MCP_SERVERS.items():
        script = cfg.get("args", [""])[0]
        exists = "OK" if os.path.isfile(script) else "MISSING"
        print(f"    {name:<20} [{exists}] {script}")

    # 6. GitLab MCP instructions (npm-based, not Python)
    print("\n" + "-" * 60)
    print("  GitLab MCP (npm-based — manual setup required):")
    print("")
    print("  Add to ~/.gemini/settings.json manually:")
    print("""
    "gitlab": {
      "command": "npx",
      "args": ["-y", "@zereight/mcp-gitlab"],
      "env": {
        "GITLAB_URL": "https://your-gitlab.example.com",
        "GITLAB_TOKEN": "your-personal-access-token"
      }
    }
    """)
    print("  Requires Node.js + npm installed.")
    print("-" * 60)

    print(f"\n  Settings written to: {SETTINGS_PATH}")
    print("\n  Next steps:")
    print("  1. Copy .env.example to .env and fill in your credentials")
    print("  2. Ensure Gemini CLI is authenticated: gemini --version")
    print("  3. Test MCP servers: python mcp_servers/serial_port_server.py")
    print("  4. Start SAGE[ai]:  python src/main.py demo")
    print("\n  Setup complete!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    setup()
