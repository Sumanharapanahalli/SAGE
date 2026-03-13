import os
import sys
import json

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.agents.planner import planner_agent

print("\n🚀 Starting SAGE Planner Agent Mock (PoseEngine)\n")

task_request = "We need to train a new high-resolution model on the yoga dataset for 100 epochs, then run it to extract features from our test_yoga.mp4 video, and finally create a module called 'yoga_inference' to handle real-time scoring."

print(f"User Request: '{task_request}'")
print("-" * 50)

# The planner will decompose this into standard task types from tasks.yaml
plan = planner_agent.plan_and_execute(task_request)

print("\n✅ Planner Agent Output:")
print(json.dumps(plan, indent=2))
