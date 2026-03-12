"""
SAGE[ai] - CLI Demo with Human-in-the-Loop
===================================================

Run from the project root:
    python -m src.main_v1_cli

Or:
    python src/main_v1_cli.py
"""

import time
import sys
import os
import logging

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Suppress noisy third-party loggers
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="huggingface_hub")

# Setup logging before imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

# Silence verbose libraries (httpx, huggingface, chromadb telemetry)
for noisy_logger in [
    "httpx", "httpcore", "huggingface_hub", "chromadb",
    "chromadb.telemetry", "chromadb.telemetry.product.posthog",
    "sentence_transformers", "urllib3",
]:
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

from src.core.llm_gateway import llm_gateway
from src.agents.analyst import analyst_agent


BANNER = """
============================================================
   SAGE[ai]  -  Autonomous Analyst
   Human-in-the-Loop Demo (QMS Compliant)
============================================================
"""

def show_provider_info():
    """Display which LLM provider is active."""
    name = llm_gateway.get_provider_name()
    print(f"  Active LLM Provider : {name}")
    print(f"  Mode                : Single-Lane (Thread-Locked)")
    print(f"  Audit Logging       : ON (SQLite)")
    print()


def mock_log_stream():
    """Simulate production log alerts."""
    return [
        "ERROR 2026-02-12 10:01:00 [Device_XYZ] Connection timeout to database 192.168.1.55",
        "CRITICAL 2026-02-12 10:05:00 [Servo_Controller] Overheat warning. Temp > 85C",
        "WARNING 2026-02-12 10:08:12 [WiFi_Module] Signal strength below threshold on Line 2",
    ]


def run_analysis_loop(logs):
    """Main loop: Analyze -> Propose -> Human Review -> Learn."""

    for i, log in enumerate(logs, 1):
        print(f"\n{'='*60}")
        print(f"  ALERT {i}/{len(logs)}")
        print(f"{'='*60}")
        print(f"  LOG: {log}")
        print()

        print("  Agent is analyzing...", end="", flush=True)
        analysis = analyst_agent.analyze_log(log)
        print(" Done.\n")

        # Display proposal
        trace_id = analysis.get("trace_id", "N/A")
        print(f"  +--- AI PROPOSAL (Trace: {trace_id}) ---+")
        print(f"  | SEVERITY : {analysis.get('severity', 'N/A')}")
        print(f"  | CAUSE    : {analysis.get('root_cause_hypothesis', 'N/A')}")
        print(f"  | ACTION   : {analysis.get('recommended_action', 'N/A')}")

        if analysis.get("raw_output"):
            print(f"  | RAW      : {analysis['raw_output'][:200]}...")
        print(f"  +{'='*42}+")

        # Human-in-the-loop
        while True:
            print()
            choice = input(
                "  [A]pprove  |  [R]eject & Teach  |  [S]kip  |  [Q]uit : "
            ).strip().upper()

            if choice == "A":
                print(f"\n  ACTION APPROVED. (Trace: {trace_id})")
                print(f"  >> Executing: {analysis.get('recommended_action')}")
                # In production, this would call the ActionExecutor
                break

            elif choice == "R":
                feedback = input("\n  Enter your correction/feedback:\n  > ")
                if feedback.strip():
                    print("  Learning from feedback...", end="", flush=True)
                    analyst_agent.learn_from_feedback(log, feedback, analysis)
                    print(" Saved to memory!")
                    print("  Next time this error appears, the AI will use your correction.")
                else:
                    print("  (Empty feedback, skipping learn step.)")
                break

            elif choice == "S":
                print("  Skipped.")
                break

            elif choice == "Q":
                print("\n  Shutting down. All audit logs preserved.")
                return

            else:
                print("  Invalid choice. Try A, R, S, or Q.")


def main():
    print(BANNER)
    show_provider_info()

    # Quick provider test
    print("  Testing LLM connection...", end="", flush=True)
    test_response = llm_gateway.generate(
        "Reply with exactly: OK",
        "You are a system health check. Reply with only 'OK'."
    )
    if "error" in test_response.lower():
        print(f" FAILED\n  {test_response}")
        print("\n  Please check your LLM provider config (config/config.yaml).")
        print("  If using 'gemini', ensure the Gemini CLI is installed and authenticated.")
        print("  If using 'local', ensure the GGUF model file exists.\n")
        sys.exit(1)
    else:
        print(f" OK ({test_response[:30]}...)")
    print()

    # Run
    logs = mock_log_stream()
    print(f"  Loaded {len(logs)} simulated log alerts.\n")
    run_analysis_loop(logs)

    print("\n  Session complete. Audit log saved to data/audit_log.db")


if __name__ == "__main__":
    main()
