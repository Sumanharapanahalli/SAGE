"""
SAGE Framework — Main Entry Point
====================================
Generic Autonomous AI Agent Framework — configurable per project/domain.

Modes:
  cli     : Interactive human-in-the-loop CLI (default)
  api     : Start FastAPI REST server
  monitor : Start background monitoring daemon with status display
  demo    : Run quick demo with mock data to showcase all integrations

Project selection (controls which prompts, task types, and modules are active):
  --project medtech      Medical device manufacturing (default)
  --project poseengine   PoseEngine + Flutter ML/mobile project
  --project <name>       Any project in the projects/ directory

Usage:
  python src/main.py [cli|api|monitor|demo] [--project <name>]
  python src/main.py                         # cli mode, medtech project
  python src/main.py api --port 8080
  python src/main.py api --project poseengine
  SAGE_PROJECT=poseengine python src/main.py api
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import yaml


def _load_config() -> dict:
    config_path = os.path.join(PROJECT_ROOT, "config", "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def _setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ---------------------------------------------------------------------------
# CLI Mode (Human-in-the-Loop)
# ---------------------------------------------------------------------------

def run_cli():
    """Interactive CLI — mirrors the v1 CLI with all new agents available."""
    from src.agents.analyst import analyst_agent
    from src.core.llm_gateway import llm_gateway

    from src.core.project_loader import project_config
    meta = project_config.metadata
    print("\n" + "=" * 70)
    print(f"  SAGE Framework — {meta['name']}")
    print(f"  Project: {meta['project']} v{meta['version']}")
    print(f"  Mode: Interactive CLI (Human-in-the-Loop)")
    print(f"  LLM Provider: {llm_gateway.get_provider_name()}")
    print("=" * 70)
    print("Commands:")
    print("  analyze <log text>  — Analyze a log entry")
    print("  quit / exit         — Exit")
    print("  help                — Show this help")
    print("-" * 70 + "\n")

    while True:
        try:
            user_input = input("sage[ai]> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting SAGE[ai]. Goodbye.")
            break

        if not user_input:
            continue

        lower = user_input.lower()

        if lower in ("quit", "exit", "q"):
            print("Exiting SAGE[ai]. Goodbye.")
            break

        if lower in ("help", "h", "?"):
            print("  analyze <text>  — Analyze a manufacturing log entry")
            print("  quit            — Exit the CLI")
            continue

        if lower.startswith("analyze "):
            log_entry = user_input[8:].strip()
            if not log_entry:
                print("  Usage: analyze <log entry text>")
                continue

            print(f"\n  Analyzing: {log_entry[:80]}...\n")
            result = analyst_agent.analyze_log(log_entry)

            if "error" in result:
                print(f"  ERROR: {result['error']}\n")
                continue

            print("  +-- AI Analysis -----------------------------------------------+")
            print(f"  | Severity:    {result.get('severity', 'N/A')}")
            print(f"  | Root Cause:  {result.get('root_cause_hypothesis', 'N/A')}")
            print(f"  | Action:      {result.get('recommended_action', 'N/A')}")
            print(f"  | Trace ID:    {result.get('trace_id', 'N/A')}")
            print("  +---------------------------------------------------------------+")

            decision = input("\n  [A]pprove / [R]eject & Teach / [S]kip: ").strip().upper()

            if decision == "A":
                print("  Approved. Action logged.")
            elif decision == "R":
                correction = input("  Enter correction/feedback: ").strip()
                if correction:
                    analyst_agent.learn_from_feedback(log_entry, correction, result)
                    print("  Feedback learned and stored.")
            elif decision == "S":
                print("  Skipped.")
            else:
                print("  No valid decision — skipping.")

            print()

        else:
            # Treat any unrecognized input as a log entry to analyze
            print(f"  (Hint: type 'analyze {user_input}' or 'help')")


# ---------------------------------------------------------------------------
# API Mode (FastAPI Server)
# ---------------------------------------------------------------------------

def run_api(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Starts the FastAPI REST server via uvicorn."""
    try:
        import uvicorn
    except ImportError:
        print("ERROR: uvicorn not installed. Run: pip install uvicorn")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("  SAGE[ai] — FastAPI Server Mode")
    print(f"  Listening on: http://{host}:{port}")
    print(f"  API Docs:     http://localhost:{port}/docs")
    print("=" * 70 + "\n")

    uvicorn.run(
        "src.interface.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


# ---------------------------------------------------------------------------
# Monitor Mode (Daemon)
# ---------------------------------------------------------------------------

def run_monitor():
    """Starts the Monitor Agent and displays live status."""
    from src.agents.monitor import monitor_agent
    from src.agents.analyst import analyst_agent

    # Register a callback that auto-analyzes detected errors
    def on_error_event(event: dict):
        event_type = event.get("type", "unknown")
        content = event.get("content", "")
        print(f"\n  [EVENT] {event_type} from {event.get('source', '?')}: {content[:100]}")

        if event_type in ("teams_error", "metabase_error") and content:
            print("  Auto-analyzing event content...")
            result = analyst_agent.analyze_log(content)
            severity = result.get("severity", "N/A")
            action = result.get("recommended_action", "")[:60]
            print(f"  Analysis: severity={severity}, action={action}")

    monitor_agent.register_callback("*", on_error_event)

    print("\n" + "=" * 70)
    print("  SAGE[ai] — Monitor Daemon Mode")
    print("  Press Ctrl+C to stop")
    print("=" * 70)

    monitor_agent.start()

    try:
        while True:
            status = monitor_agent.get_status()
            active = status.get("active_threads", [])
            ts = datetime.now().strftime("%H:%M:%S")
            msgs = status.get("seen_messages", 0)
            issues = status.get("seen_issues", 0)
            print(
                f"\r  [{ts}] Active pollers: {len(active)} | "
                f"Msgs seen: {msgs} | Issues seen: {issues}    ",
                end="",
                flush=True,
            )
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n\n  Stopping monitor...")
        monitor_agent.stop()
        print("  Monitor stopped.")


# ---------------------------------------------------------------------------
# Demo Mode
# ---------------------------------------------------------------------------

def run_demo():
    """Runs a quick demo showcasing key system capabilities with mock data."""
    from src.agents.analyst import analyst_agent
    from src.core.llm_gateway import llm_gateway
    from src.core.queue_manager import task_queue

    print("\n" + "=" * 70)
    print("  SAGE[ai] — DEMO Mode")
    print("  Showcasing: LLM Analysis, Task Queue, Teams Bot, Developer Agent")
    print("=" * 70)

    print(f"\n  LLM Provider: {llm_gateway.get_provider_name()}")

    # --- Demo 1: Log Analysis ---
    print("\n[1/4] Log Analysis Demo")
    print("  Analyzing mock manufacturing error...")
    mock_log = (
        "ERROR 2026-03-10 14:23:01 [Sterilization] CycleID=8821 "
        "Temperature sensor fault: Reading 185C, expected 134C +/-2. "
        "Cycle aborted. ErrorCode=0x4F"
    )
    result = analyst_agent.analyze_log(mock_log)
    print(f"  Severity:   {result.get('severity', 'N/A')}")
    print(f"  Root Cause: {result.get('root_cause_hypothesis', 'N/A')[:80]}")
    print(f"  Action:     {result.get('recommended_action', 'N/A')[:80]}")
    print(f"  Trace ID:   {result.get('trace_id', 'N/A')}")

    # --- Demo 2: Task Queue ---
    print("\n[2/4] Task Queue Demo")
    t1 = task_queue.submit("ANALYZE_LOG", {"log_entry": "ERROR: Motor controller timeout"}, priority=3)
    t2 = task_queue.submit("ANALYZE_LOG", {"log_entry": "WARNING: Pressure exceeds threshold"}, priority=5)
    print(f"  Submitted 2 tasks. Queue depth: {task_queue.get_pending_count()}")
    print(f"  Task 1 ID: {t1} — status: {task_queue.get_status(t1)['status']}")
    print(f"  Task 2 ID: {t2} — status: {task_queue.get_status(t2)['status']}")

    # --- Demo 3: Teams Bot ---
    print("\n[3/4] Teams Bot Demo")
    webhook_url = os.environ.get("TEAMS_INCOMING_WEBHOOK_URL", "")
    if webhook_url:
        from src.interface.teams_bot import teams_bot
        bot_result = teams_bot.send_analysis_alert({
            "severity": "HIGH",
            "root_cause_hypothesis": "Temperature sensor fault (demo)",
            "recommended_action": "Inspect sensor connections and calibration",
            "trace_id": result.get("trace_id", "demo-trace"),
        })
        print(f"  Teams notification: {bot_result.get('status', bot_result.get('error'))}")
    else:
        print("  TEAMS_INCOMING_WEBHOOK_URL not set — skipping live Teams notification.")
        print("  (Set the env var to see adaptive card delivery)")

    # --- Demo 4: Developer Agent ---
    print("\n[4/4] Developer Agent Demo")
    gitlab_url = os.environ.get("GITLAB_URL", "")
    if gitlab_url:
        from src.agents.developer import developer_agent
        print(f"  GitLab URL: {gitlab_url}")
        mrs = developer_agent.list_open_mrs(int(os.environ.get("GITLAB_PROJECT_ID", "0")))
        if "error" not in mrs:
            print(f"  Open MRs: {mrs.get('count', 0)}")
        else:
            print(f"  GitLab error (expected without valid project): {mrs['error'][:60]}")
    else:
        print("  GITLAB_URL not set — skipping live GitLab demo.")
        print("  (Set GITLAB_URL + GITLAB_TOKEN + GITLAB_PROJECT_ID to enable)")

    print("\n" + "=" * 70)
    print("  Demo complete.")
    print("  Run 'python src/main.py api'     for REST API mode.")
    print("  Run 'python src/main.py monitor' for live event monitoring.")
    print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="SAGE Framework — Generic Autonomous AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  cli      Interactive human-in-the-loop CLI (default)
  api      Start FastAPI REST server
  monitor  Start background monitoring daemon
  demo     Quick demo of all integrations

Projects (in projects/ directory):
  medtech      Medical device manufacturing (default)
  poseengine   PoseEngine + Flutter ML/mobile
  <custom>     Any project you add to projects/

Environment variables:
  SAGE_PROJECT   Override the active project (e.g. SAGE_PROJECT=poseengine)
        """,
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="cli",
        choices=["cli", "api", "monitor", "demo"],
        help="Execution mode (default: cli)",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Active project name (default: medtech, or SAGE_PROJECT env var)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="API server host (api mode only)")
    parser.add_argument("--port", type=int, default=8000, help="API server port (api mode only)")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code changes (api mode only)")
    parser.add_argument("--log-level", default=None, help="Logging level: DEBUG/INFO/WARNING/ERROR")

    args = parser.parse_args()

    # Apply --project before any imports that trigger project_config singleton
    if args.project:
        os.environ["SAGE_PROJECT"] = args.project

    # Setup logging
    config = _load_config()
    log_level = args.log_level or config.get("system", {}).get("log_level", "INFO")
    _setup_logging(log_level)

    # Load .env if available
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(PROJECT_ROOT, ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
            logging.getLogger("main").info("Loaded .env from %s", env_path)
    except ImportError:
        pass

    mode = args.mode.lower()

    if mode == "cli":
        run_cli()
    elif mode == "api":
        run_api(host=args.host, port=args.port, reload=args.reload)
    elif mode == "monitor":
        run_monitor()
    elif mode == "demo":
        run_demo()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
