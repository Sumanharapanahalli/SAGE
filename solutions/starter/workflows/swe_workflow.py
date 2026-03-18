"""
SAGE SWE Workflow — open-swe pattern
=====================================
Autonomous software engineer workflow. Follows the explore → plan → implement
→ verify → submit cycle. Based on open-swe (github.com/langchain-ai/open-swe).

Agent-first: runs explore → plan → implement → verify → propose_pr autonomously,
then pauses at `finalize` for human approval (interrupt_before=["finalize"]).
This surfaces the PR proposal to the human before marking the task complete.

For solutions WITHOUT compliance_standards, the human sees the PR and approves
or rejects — the agent never asks mid-task.

Usage:
  POST /workflow/run
  {"workflow_name": "swe_workflow", "state": {"task": "Fix the null pointer bug in CheckoutService"}}

  POST /workflow/run
  {"workflow_name": "swe_workflow", "state": {
      "task": "Add retry logic to PaymentService",
      "repo_path": "/path/to/repo",
      "repo_url": "https://github.com/org/repo.git"
  }}

  POST /workflow/resume
  {"run_id": "<id>", "feedback": {"approved": true}}
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from typing import TypedDict, Optional, List

from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class SWEState(TypedDict, total=False):
    # Input
    task: str                       # The task / issue description
    repo_path: str                  # Path to existing local repo (default: cwd)
    repo_url: str                   # Optional: clone from remote URL
    solution_name: str

    # Exploration
    workspace_dir: str              # Resolved workspace (may be cloned or repo_path)
    repo_context: str               # README + AGENTS.md concatenated
    file_tree: str                  # Top-level directory listing
    tech_stack: str                 # Detected language / framework
    test_command: str               # Inferred test command (e.g. "pytest tests/")
    agents_md: str                  # AGENTS.md content (open-swe convention)
    exploration_summary: str        # LLM-generated codebase understanding

    # Planning
    plan: List[str]                 # Ordered list of change steps
    todos: List[dict]               # [{file, action, description}]
    implementation_plan: str        # Full LLM-generated plan text

    # Implementation
    changes_made: List[str]         # Files changed
    implementation_result: str
    diff_summary: str

    # Verify
    test_results: str               # Stdout from test run
    tests_passed: bool

    # Submit
    branch_name: str
    commit_sha: str
    pr_title: str
    pr_body: str
    pr_url: str

    # Meta
    run_id: str
    trace_id: str
    error: Optional[str]
    approved: bool                  # Set by human during HITL gate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_workspace(state: SWEState) -> tuple[str, bool]:
    """
    Return (workspace_dir, was_cloned).
    Priority: repo_url clone > repo_path > cwd.
    """
    repo_url = state.get("repo_url", "")
    repo_path = state.get("repo_path", "")

    if repo_url:
        from src.integrations.sandbox_runner import sandbox_runner
        result = sandbox_runner.clone_repo(repo_url)
        if result["success"]:
            return result["workspace_dir"], True
        logger.warning("Clone failed for %s: %s", repo_url, result.get("error"))

    if repo_path and os.path.isdir(repo_path):
        return os.path.abspath(repo_path), False

    # Fall back to current working directory (SAGE repo itself)
    return os.getcwd(), False


def _safe_execute(cmd: str, workspace_dir: str, timeout: int = 120) -> dict:
    """Wrapper around sandbox_runner.execute that never raises."""
    from src.integrations.sandbox_runner import sandbox_runner
    return sandbox_runner.execute(cmd, workspace_dir, timeout=timeout)


def _llm_generate(prompt: str, max_tokens: int = 1500) -> str:
    """Call LLMGateway; return empty string on failure."""
    try:
        from src.core.llm_gateway import llm_gateway
        return llm_gateway.generate(prompt, max_tokens=max_tokens)
    except Exception as e:
        logger.error("LLM generate failed: %s", e)
        return ""


# ---------------------------------------------------------------------------
# Node 1: explore
# ---------------------------------------------------------------------------

def explore(state: SWEState) -> SWEState:
    """
    Read README.md, AGENTS.md, and the top-level file tree.
    Detect tech stack and test command. Ask LLM for exploration summary.
    """
    task = state.get("task", "")
    workspace_dir, was_cloned = _resolve_workspace(state)

    # Read README
    readme_result = _safe_execute(
        "cat README.md 2>/dev/null || cat readme.md 2>/dev/null || echo ''",
        workspace_dir,
    )
    readme = readme_result.get("stdout", "")[:3000]

    # Read AGENTS.md (open-swe convention)
    agents_md_result = _safe_execute("cat AGENTS.md 2>/dev/null || echo ''", workspace_dir)
    agents_md = agents_md_result.get("stdout", "").strip()

    # File tree — top two levels
    tree_result = _safe_execute(
        "find . -maxdepth 2 -not -path '*/.git/*' -not -path '*/node_modules/*' "
        "-not -path '*/__pycache__/*' -not -path '*/.venv/*' | sort | head -80",
        workspace_dir,
    )
    file_tree = tree_result.get("stdout", "")[:2000]

    # Detect tech stack and test command
    has_pytest = _safe_execute("test -f pytest.ini || test -f setup.cfg || test -f pyproject.toml", workspace_dir)
    has_package_json = _safe_execute("test -f package.json", workspace_dir)
    has_makefile = _safe_execute("test -f Makefile", workspace_dir)

    tech_stack = "unknown"
    test_command = "echo 'No test command detected'"

    if has_pytest.get("returncode") == 0:
        tech_stack = "python"
        test_command = "python -m pytest tests/ -x -q 2>&1 | head -50"
    elif has_package_json.get("returncode") == 0:
        # Check if npm test is defined
        pkg_result = _safe_execute("cat package.json", workspace_dir)
        pkg_json = pkg_result.get("stdout", "")
        tech_stack = "node"
        if "jest" in pkg_json.lower():
            test_command = "npx jest --passWithNoTests 2>&1 | head -50"
        else:
            test_command = "npm test -- --passWithNoTests 2>&1 | head -50"
    elif has_makefile.get("returncode") == 0:
        make_result = _safe_execute("cat Makefile | grep -E '^test'", workspace_dir)
        if make_result.get("stdout", "").strip():
            test_command = "make test 2>&1 | head -50"

    # Compose context for LLM
    agents_section = f"\n\nAGENTS.md (repo conventions — follow these):\n{agents_md}" if agents_md else ""
    repo_context = f"README:\n{readme}{agents_section}"

    explore_prompt = f"""You are a senior software engineer exploring a codebase to plan implementation.

TASK: {task}

FILE TREE:
{file_tree}

{repo_context[:2000]}

Provide a concise exploration summary (under 400 words):
1. What this codebase does and its tech stack
2. Files most relevant to the task (with paths)
3. Likely location of the bug or feature gap
4. Implementation approach — what to change and where
5. Any risks or special conventions to follow

Be specific about file paths. Do not guess if uncertain — flag unknowns."""

    exploration_summary = _llm_generate(explore_prompt, max_tokens=600)

    return {
        **state,
        "workspace_dir": workspace_dir,
        "repo_context": repo_context,
        "file_tree": file_tree,
        "tech_stack": tech_stack,
        "test_command": test_command,
        "agents_md": agents_md,
        "exploration_summary": exploration_summary,
    }


# ---------------------------------------------------------------------------
# Node 2: plan
# ---------------------------------------------------------------------------

def plan(state: SWEState) -> SWEState:
    """
    Use LLM to generate a structured plan as an ordered list of file edits.
    Populates plan (list of steps) and todos (list of {file, action, description}).
    """
    task = state.get("task", "")
    exploration_summary = state.get("exploration_summary", "")
    agents_md = state.get("agents_md", "")
    file_tree = state.get("file_tree", "")
    workspace_dir = state.get("workspace_dir", "")

    # Read a sample of files mentioned in the exploration
    file_samples = ""
    relevant_files = re.findall(r'(?:^|\s)([\w./\-]+\.(?:py|ts|js|go|java|yaml|yml|json))', exploration_summary)
    for rel_path in relevant_files[:4]:
        rel_path = rel_path.strip()
        full_path = os.path.join(workspace_dir, rel_path)
        if os.path.isfile(full_path):
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()[:1500]
                file_samples += f"\n\n--- {rel_path} ---\n{content}"
            except Exception:
                pass

    agents_section = f"\nRepo conventions (AGENTS.md — you MUST follow these):\n{agents_md}\n" if agents_md else ""

    plan_prompt = f"""You are a senior software engineer creating a minimal implementation plan.

TASK: {task}

EXPLORATION:
{exploration_summary}

FILE TREE:
{file_tree[:1000]}
{agents_section}
RELEVANT FILE CONTENT:
{file_samples[:2000]}

Create a precise, ordered implementation plan. Output STRICT JSON:
{{
  "plan": ["step 1 description", "step 2 description", ...],
  "todos": [
    {{"file": "path/to/file.py", "action": "edit|create", "description": "what to change"}},
    ...
  ],
  "test_command_override": null,
  "pr_title": "fix: resolve null pointer in CheckoutService",
  "pr_body": "## What\\nDescribe the change.\\n\\n## Why\\nExplain the reason.\\n\\n## How to test\\nTest steps."
}}

Rules:
- Prefer editing existing files over creating new ones
- Minimal changes only — do not refactor unrelated code
- pr_title must follow: <type>: <lowercase description> (type: feat|fix|refactor|test|docs|chore)
- test_command_override: set only if you have a better targeted test command, else null"""

    raw = _llm_generate(plan_prompt, max_tokens=1200)

    # Parse JSON from LLM output
    plan_steps: List[str] = []
    todos: List[dict] = []
    pr_title = f"feat: {task[:60].lower()}"
    pr_body = f"## What\n{task}\n\n## Why\nAutomated via SAGE SWE Agent\n\n## How to test\nRun the test suite."
    implementation_plan = raw

    try:
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            import json
            data = json.loads(json_match.group(0))
            plan_steps = data.get("plan", [])
            todos = data.get("todos", [])
            if data.get("pr_title"):
                pr_title = data["pr_title"]
            if data.get("pr_body"):
                pr_body = data["pr_body"]
            if data.get("test_command_override"):
                state = {**state, "test_command": data["test_command_override"]}
    except Exception as e:
        logger.warning("Could not parse plan JSON: %s — using raw text", e)
        # Extract steps from numbered list as fallback
        plan_steps = re.findall(r'(?:^|\n)\s*\d+\.\s+(.+)', raw)
        todos = []

    return {
        **state,
        "plan": plan_steps,
        "todos": todos,
        "implementation_plan": implementation_plan,
        "pr_title": pr_title,
        "pr_body": pr_body,
    }


# ---------------------------------------------------------------------------
# Node 3: implement
# ---------------------------------------------------------------------------

def implement(state: SWEState) -> SWEState:
    """
    Execute the implementation plan file by file.
    For each todo, read the current file content then ask LLM to produce the
    updated version. Writes the result via sandbox_runner.
    """
    workspace_dir = state.get("workspace_dir", "")
    task = state.get("task", "")
    todos = state.get("todos", [])
    plan_steps = state.get("plan", [])
    implementation_plan = state.get("implementation_plan", "")
    agents_md = state.get("agents_md", "")

    if not workspace_dir or not os.path.isdir(workspace_dir):
        return {
            **state,
            "implementation_result": "No valid workspace — cannot implement without a repo.",
            "changes_made": [],
            "diff_summary": "No changes",
        }

    from src.integrations.sandbox_runner import sandbox_runner

    changes_made: List[str] = []
    agents_section = f"\nRepo conventions (AGENTS.md):\n{agents_md}\n" if agents_md else ""

    # If todos list is populated, implement file by file
    if todos:
        for todo in todos:
            file_path = todo.get("file", "").strip()
            action = todo.get("action", "edit")
            description = todo.get("description", "")

            if not file_path:
                continue

            # Read existing content
            existing_content = ""
            full_path = os.path.join(workspace_dir, file_path)
            if os.path.isfile(full_path) and action == "edit":
                read_result = sandbox_runner.read_file(file_path, workspace_dir)
                existing_content = read_result.get("content", "") or ""

            existing_section = f"\nCURRENT FILE CONTENT ({file_path}):\n```\n{existing_content[:3000]}\n```" if existing_content else f"\n(Creating new file: {file_path})"

            impl_prompt = f"""You are implementing a specific file change as part of a software task.

TASK: {task}
FILE: {file_path}
CHANGE NEEDED: {description}
{existing_section}
{agents_section}

Output ONLY the complete updated file content. No markdown fences, no explanation, no FILE: header.
Write production-quality code. Preserve all existing functionality unless the task requires changing it."""

            new_content = _llm_generate(impl_prompt, max_tokens=2000)

            if new_content.strip():
                # Strip accidental markdown fences
                new_content = re.sub(r'^```\w*\n', '', new_content.strip())
                new_content = re.sub(r'\n```$', '', new_content.strip())

                write_result = sandbox_runner.write_file(file_path, new_content + "\n", workspace_dir)
                if write_result.get("success"):
                    changes_made.append(file_path)
                else:
                    logger.warning("Failed to write %s: %s", file_path, write_result.get("error"))

    else:
        # Fallback: ask LLM for FILE blocks covering all changes
        plan_text = "\n".join(plan_steps) if plan_steps else implementation_plan

        fallback_prompt = f"""Implement the following plan in a software repository.

TASK: {task}

PLAN:
{plan_text}
{agents_section}

For each file to create or modify, output exactly:

FILE: path/to/file.py
```
<complete file content>
```

Output only FILE blocks. Most critical files first. Never create backup files."""

        raw = _llm_generate(fallback_prompt, max_tokens=3000)
        file_blocks = re.findall(r'FILE: ([^\n]+)\n```(?:\w+)?\n([\s\S]*?)```', raw)
        for file_path, content in file_blocks:
            file_path = file_path.strip()
            write_result = sandbox_runner.write_file(file_path, content.strip() + "\n", workspace_dir)
            if write_result.get("success"):
                changes_made.append(file_path)

    # Stage all changes
    _safe_execute("git add -A", workspace_dir)

    # Get diff summary
    diff_result = _safe_execute("git diff --stat HEAD", workspace_dir)
    diff_summary = diff_result.get("stdout", "").strip() or "No staged changes detected"

    impl_result = (
        f"Applied changes to {len(changes_made)} file(s): {', '.join(changes_made)}"
        if changes_made
        else "No file changes produced — check LLM output and plan"
    )

    return {
        **state,
        "changes_made": changes_made,
        "implementation_result": impl_result,
        "diff_summary": diff_summary,
    }


# ---------------------------------------------------------------------------
# Node 4: verify
# ---------------------------------------------------------------------------

def verify(state: SWEState) -> SWEState:
    """
    Run only the tests related to changed files.
    Derives a targeted test command from changed_files + tech_stack.
    Falls back to the full test_command detected in explore.
    """
    workspace_dir = state.get("workspace_dir", "")
    changes_made = state.get("changes_made", [])
    tech_stack = state.get("tech_stack", "unknown")
    base_test_command = state.get("test_command", "")

    if not workspace_dir or not os.path.isdir(workspace_dir):
        return {**state, "test_results": "No workspace — skipping tests.", "tests_passed": True}

    if not changes_made:
        return {**state, "test_results": "No changes made — skipping tests.", "tests_passed": True}

    # Build targeted test command
    targeted_cmd = base_test_command

    if tech_stack == "python":
        # Find test files corresponding to changed source files
        test_paths = []
        for f in changes_made:
            # e.g. src/foo/bar.py → tests/test_bar.py or tests/foo/test_bar.py
            basename = os.path.splitext(os.path.basename(f))[0]
            candidates = [
                f"tests/test_{basename}.py",
                f"tests/{os.path.dirname(f)}/test_{basename}.py",
                f"test_{basename}.py",
            ]
            for candidate in candidates:
                full = os.path.join(workspace_dir, candidate)
                if os.path.isfile(full):
                    test_paths.append(candidate)
                    break

        if test_paths:
            targeted_cmd = f"python -m pytest {' '.join(test_paths)} -x -q 2>&1 | head -60"
        else:
            targeted_cmd = "python -m pytest -x -q 2>&1 | head -60"

    elif tech_stack == "node":
        # Jest can filter by changed file names
        if changes_made:
            basenames = [os.path.splitext(os.path.basename(f))[0] for f in changes_made]
            pattern = "|".join(basenames[:5])
            targeted_cmd = f"npx jest --testPathPattern='{pattern}' --passWithNoTests 2>&1 | head -60"

    test_result = _safe_execute(targeted_cmd, workspace_dir, timeout=120)
    test_output = test_result.get("stdout", "") + test_result.get("stderr", "")
    test_output = test_output[:2000]
    tests_passed = test_result.get("returncode", 1) == 0

    return {
        **state,
        "test_results": test_output or "No test output",
        "tests_passed": tests_passed,
    }


# ---------------------------------------------------------------------------
# Node 5: propose_pr
# ---------------------------------------------------------------------------

def propose_pr(state: SWEState) -> SWEState:
    """
    Commit staged changes to a new branch. If GITHUB_TOKEN is set, open a
    real PR via the GitHub API. Otherwise populate pr_url with instructions.
    """
    workspace_dir = state.get("workspace_dir", "")
    task = state.get("task", "")
    pr_title = state.get("pr_title", f"feat: {task[:60].lower()}")
    pr_body = state.get("pr_body", "")
    changes_made = state.get("changes_made", [])
    diff_summary = state.get("diff_summary", "")
    test_results = state.get("test_results", "")

    if not workspace_dir or not os.path.isdir(workspace_dir):
        return {
            **state,
            "commit_sha": "",
            "pr_url": "No workspace — PR not created.",
        }

    # Generate a branch name
    slug = re.sub(r'[^a-z0-9-]', '-', task[:40].lower()).strip('-')
    branch_name = f"sage-swe/{slug}-{str(uuid.uuid4())[:6]}"

    # Create branch
    _safe_execute(
        f"git checkout -b {branch_name} 2>/dev/null || git checkout {branch_name}",
        workspace_dir,
    )

    # Configure git author if not already set
    _safe_execute("git config user.email 'sage-swe@localhost' 2>/dev/null || true", workspace_dir)
    _safe_execute("git config user.name 'SAGE SWE Agent' 2>/dev/null || true", workspace_dir)

    # Commit
    escaped_title = pr_title.replace('"', '\\"')
    commit_result = _safe_execute(
        f'git commit -m "{escaped_title}" --allow-empty',
        workspace_dir,
    )
    commit_sha = ""
    if commit_result.get("returncode") == 0:
        sha_result = _safe_execute("git rev-parse --short HEAD", workspace_dir)
        commit_sha = sha_result.get("stdout", "").strip()

    # Try GitHub API if GITHUB_TOKEN is set
    github_token = os.environ.get("GITHUB_TOKEN", "")
    pr_url = ""

    if github_token and commit_sha:
        try:
            # Get remote URL
            remote_result = _safe_execute("git remote get-url origin", workspace_dir)
            remote_url = remote_result.get("stdout", "").strip()

            # Parse owner/repo from URL
            repo_match = re.search(r'github\.com[:/]([^/]+)/([^/.]+)', remote_url)
            if repo_match:
                import urllib.request
                import json

                owner = repo_match.group(1)
                repo = repo_match.group(2).replace(".git", "")

                # Push branch
                push_result = _safe_execute(
                    f"git push origin {branch_name}",
                    workspace_dir,
                    timeout=60,
                )

                if push_result.get("returncode") == 0:
                    # Get default branch
                    default_branch_result = _safe_execute(
                        "git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'",
                        workspace_dir,
                    )
                    base_branch = default_branch_result.get("stdout", "main").strip() or "main"

                    # Build PR body with test results appended
                    full_body = pr_body
                    if test_results:
                        full_body += f"\n\n## Test Results\n```\n{test_results[:500]}\n```"
                    full_body += f"\n\n---\n*Opened by SAGE SWE Agent — commit `{commit_sha}`*"

                    payload = json.dumps({
                        "title": pr_title,
                        "body": full_body,
                        "head": branch_name,
                        "base": base_branch,
                    }).encode()

                    req = urllib.request.Request(
                        f"https://api.github.com/repos/{owner}/{repo}/pulls",
                        data=payload,
                        headers={
                            "Authorization": f"Bearer {github_token}",
                            "Accept": "application/vnd.github+json",
                            "Content-Type": "application/json",
                        },
                    )
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        pr_data = json.loads(resp.read().decode())
                        pr_url = pr_data.get("html_url", "")
        except Exception as e:
            logger.warning("GitHub PR creation failed: %s", e)

    if not pr_url:
        pr_url = (
            f"Branch '{branch_name}' ready (commit: {commit_sha or 'pending'})."
            f" Push to remote and open PR manually, or set GITHUB_TOKEN for automatic PR creation."
        )

    return {
        **state,
        "branch_name": branch_name,
        "commit_sha": commit_sha,
        "pr_url": pr_url,
    }


# ---------------------------------------------------------------------------
# Node 6: finalize  (HITL gate — interrupt_before this node)
# ---------------------------------------------------------------------------

def finalize(state: SWEState) -> SWEState:
    """
    Log task completion to the audit trail.
    Called after human approval at the HITL gate.
    """
    task = state.get("task", "")
    pr_url = state.get("pr_url", "")
    commit_sha = state.get("commit_sha", "")
    changes_made = state.get("changes_made", [])
    tests_passed = state.get("tests_passed", False)

    try:
        from src.memory.audit_logger import audit_logger
        audit_logger.log_event(
            actor="SWEAgent",
            action_type="SWE_TASK_COMPLETE",
            input_context=task[:200],
            output_content=f"PR: {pr_url} | commit: {commit_sha} | files: {changes_made}",
            metadata={
                "changes_made": changes_made,
                "tests_passed": tests_passed,
                "pr_url": pr_url,
                "commit_sha": commit_sha,
            },
        )
    except Exception as e:
        logger.debug("Audit log for SWE task failed (non-fatal): %s", e)

    logger.info(
        "SWE task complete — PR: %s | commit: %s | files changed: %s",
        pr_url, commit_sha, changes_made,
    )

    return state


# ---------------------------------------------------------------------------
# Graph — agent-first; HITL gate before finalize
# ---------------------------------------------------------------------------
#
# The workflow runs fully autonomously through propose_pr, then pauses at
# `finalize` for human review of the PR proposal. The human calls
# POST /workflow/resume with {"approved": true} to complete.
#
# This follows the SAGE SOUL.md principle: "Agents propose. Humans decide."
# The agent never asks permission mid-task — it acts, then surfaces the result.

graph = StateGraph(SWEState)
graph.add_node("explore", explore)
graph.add_node("plan", plan)
graph.add_node("implement", implement)
graph.add_node("verify", verify)
graph.add_node("propose_pr", propose_pr)
graph.add_node("finalize", finalize)

graph.set_entry_point("explore")
graph.add_edge("explore", "plan")
graph.add_edge("plan", "implement")
graph.add_edge("implement", "verify")
graph.add_edge("verify", "propose_pr")
graph.add_edge("propose_pr", "finalize")
graph.add_edge("finalize", END)

# interrupt_before=["finalize"] pauses after propose_pr so the human
# can review the PR before the task is marked complete in the audit log.
workflow = graph.compile(interrupt_before=["finalize"])
