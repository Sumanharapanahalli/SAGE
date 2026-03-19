"""
SAGE[ai] - Developer Agent
===========================
Handles code-related tasks: reviewing PRs, creating MRs from issues,
proposing code patches, and interacting with hardware debuggers.

Integrates with:
  - GitLab REST API (MR creation, review, pipeline status)
  - LLM Gateway (AI-powered code review and patch proposals)
  - Audit Logger (ISO 13485 compliance trail)
"""

import json
import logging
import os
import uuid
from typing import Optional

import requests
import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "config.yaml",
)


def _load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


class DeveloperAgent:
    """
    Developer Agent: AI-powered code review, MR creation, and patch proposals.

    All actions are audited via the ISO 13485 audit logger.
    No direct code changes are made — proposals require human approval.
    """

    def __init__(self):
        self.logger = logging.getLogger("DeveloperAgent")
        config = _load_config()
        gitlab_cfg = config.get("gitlab", {})

        # GitLab connection settings (env vars take priority over config)
        self.gitlab_url = os.environ.get(
            "GITLAB_URL",
            str(gitlab_cfg.get("url", "")).replace("${GITLAB_URL}", "")
        ).rstrip("/")

        self.gitlab_token = os.environ.get(
            "GITLAB_TOKEN",
            str(gitlab_cfg.get("token", "")).replace("${GITLAB_TOKEN}", "")
        )

        self.default_project_id = os.environ.get(
            "GITLAB_PROJECT_ID",
            str(gitlab_cfg.get("default_project_id", "")).replace("${GITLAB_PROJECT_ID}", "")
        )

        if not self.gitlab_url:
            self.logger.warning("GITLAB_URL not configured. GitLab operations will fail.")
        if not self.gitlab_token:
            self.logger.warning("GITLAB_TOKEN not configured. GitLab operations will fail.")

        self._api_base = f"{self.gitlab_url}/api/v4" if self.gitlab_url else ""
        self._headers = {"Private-Token": self.gitlab_token} if self.gitlab_token else {}

        # Lazy-load shared singletons to avoid circular import at module level
        self._llm_gateway = None
        self._audit_logger = None

    @property
    def llm(self):
        if self._llm_gateway is None:
            from src.core.llm_gateway import llm_gateway
            self._llm_gateway = llm_gateway
        return self._llm_gateway

    @property
    def audit(self):
        if self._audit_logger is None:
            from src.memory.audit_logger import audit_logger
            self._audit_logger = audit_logger
        return self._audit_logger

    # -----------------------------------------------------------------------
    # ReAct Loop (Reason + Act multi-step reasoning)
    # -----------------------------------------------------------------------

    def _react_loop(self, task: str, tools: dict, max_steps: int = 5) -> str:
        """
        ReAct (Reason + Act) reasoning loop for multi-step agentic tasks.

        The agent alternates between Thought → Action → Observation until it
        produces a FinalAnswer. Each Action calls one of the provided tools.

        Args:
            task:      Natural-language description of the task to complete.
            tools:     Dict of {tool_name: callable(**kwargs) -> str | dict}
            max_steps: Maximum reasoning steps before forcing a final answer.

        Returns:
            Final answer string (typically JSON for structured outputs).
        """
        tool_descriptions = "\n".join(
            f"  - {name}: {fn.__doc__.strip().splitlines()[0] if fn.__doc__ else 'No description'}"
            for name, fn in tools.items()
        )

        system_prompt = (
            "You are an autonomous software engineering agent using the ReAct (Reason + Act) pattern.\n"
            "You have access to the following tools:\n"
            f"{tool_descriptions}\n\n"
            "At each step output exactly:\n"
            "  Thought: <your reasoning about the current state>\n"
            "  Action: <tool_name>(<json_args>)\n"
            "OR, when you have enough information:\n"
            "  Thought: <final reasoning>\n"
            "  FinalAnswer: <your complete answer — MUST be valid JSON for structured outputs>\n\n"
            "Rules:\n"
            "  1. Always write a Thought before any Action or FinalAnswer.\n"
            "  2. Call only ONE tool per step.\n"
            "  3. Tool arguments must be a JSON object inside the parentheses.\n"
            "  4. FinalAnswer must be strict JSON — no markdown fences."
        )

        # Inject repo map for codebase-aware reviews
        try:
            from src.core.repo_map import generate_repo_map
            import os as _os
            _PROJECT_ROOT = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
            _repo_map = generate_repo_map(_PROJECT_ROOT, max_files=40)
            system_prompt = system_prompt + "\n\n" + _repo_map
        except Exception as _rme:
            self.logger.debug("Repo map unavailable: %s", _rme)

        history: list[str] = [f"Task: {task}"]

        for step in range(max_steps):
            user_prompt = "\n".join(history) + "\n\nStep:"
            response = self.llm.generate(user_prompt, system_prompt)
            history.append(response)

            # Check for FinalAnswer
            if "FinalAnswer:" in response:
                idx = response.index("FinalAnswer:")
                return response[idx + len("FinalAnswer:"):].strip()

            # Parse Action: tool_name({...})
            if "Action:" in response:
                action_idx = response.index("Action:")
                action_line = response[action_idx + len("Action:"):].split("\n")[0].strip()
                try:
                    tool_name = action_line[: action_line.index("(")].strip()
                    args_str = action_line[action_line.index("(") + 1 : action_line.rindex(")")].strip()
                    tool_args = json.loads(args_str) if args_str else {}
                except (ValueError, json.JSONDecodeError) as exc:
                    history.append(f"Observation: Error parsing action '{action_line}': {exc}")
                    continue

                if tool_name in tools:
                    try:
                        obs = tools[tool_name](**tool_args)
                        observation = json.dumps(obs, indent=2) if isinstance(obs, (dict, list)) else str(obs)
                    except Exception as exc:
                        observation = f"Error executing {tool_name}: {exc}"
                else:
                    observation = f"Unknown tool '{tool_name}'. Available: {list(tools.keys())}"

                history.append(f"Observation: {observation}")
            # If neither FinalAnswer nor Action, loop continues with accumulated history

        # Force a final answer after max_steps
        forced_prompt = (
            "\n".join(history)
            + "\n\nYou have reached the step limit. Output your FinalAnswer now (valid JSON):"
        )
        response = self.llm.generate(forced_prompt, system_prompt)
        if "FinalAnswer:" in response:
            idx = response.index("FinalAnswer:")
            return response[idx + len("FinalAnswer:"):].strip()
        return response

    # -----------------------------------------------------------------------
    # Internal HTTP helpers
    # -----------------------------------------------------------------------

    def _gl_get(self, path: str, params: dict = None) -> tuple:
        """GET from GitLab API. Returns (data, error_string)."""
        if not self._api_base:
            return None, "GITLAB_URL not configured."
        try:
            resp = requests.get(
                f"{self._api_base}{path}",
                headers=self._headers,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json(), None
        except requests.RequestException as e:
            self.logger.error("GitLab GET %s failed: %s", path, e)
            return None, str(e)

    def _gl_post(self, path: str, body: dict) -> tuple:
        """POST to GitLab API. Returns (data, error_string)."""
        if not self._api_base:
            return None, "GITLAB_URL not configured."
        try:
            resp = requests.post(
                f"{self._api_base}{path}",
                headers={**self._headers, "Content-Type": "application/json"},
                json=body,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json(), None
        except requests.RequestException as e:
            self.logger.error("GitLab POST %s failed: %s", path, e)
            return None, str(e)

    # -----------------------------------------------------------------------
    # Public Methods
    # -----------------------------------------------------------------------

    def review_merge_request(self, project_id: int, mr_iid: int) -> dict:
        """
        Fetches a MR's diff from GitLab and sends it to the LLM for code review.

        Args:
            project_id: GitLab project numeric ID
            mr_iid:     Merge Request internal ID (IID)

        Returns:
            dict with keys: 'summary', 'issues', 'suggestions', 'approved' (bool), 'trace_id'
        """
        self.logger.info("Reviewing MR !%d in project %d", mr_iid, project_id)

        # 1. Fetch MR metadata
        mr_data, err = self._gl_get(f"/projects/{project_id}/merge_requests/{mr_iid}")
        if err:
            return {"error": f"Failed to fetch MR: {err}"}

        mr_title = mr_data.get("title", "Unknown")
        mr_description = mr_data.get("description", "")
        source_branch = mr_data.get("source_branch", "")
        target_branch = mr_data.get("target_branch", "")
        author = mr_data.get("author", {}).get("name", "Unknown")

        # 2. Fetch diff
        diff_data, err = self._gl_get(f"/projects/{project_id}/merge_requests/{mr_iid}/diffs")
        if err:
            self.logger.warning("Could not fetch diff: %s", err)
            diff_text = "(diff unavailable)"
        else:
            diff_parts = []
            for d in (diff_data if isinstance(diff_data, list) else []):
                diff_parts.append(f"--- {d.get('old_path', '')}\n+++ {d.get('new_path', '')}\n{d.get('diff', '')}")
            diff_text = "\n\n".join(diff_parts) or "(no diff changes)"

        # 3. Run ReAct loop — agent reasons over pipeline status + diff before reviewing
        _diff_snapshot = diff_text  # capture for closure

        def _tool_get_pipeline(**kwargs):
            """Gets CI/CD pipeline status for this merge request."""
            pid = kwargs.get("project_id", project_id)
            mid = kwargs.get("mr_iid", mr_iid)
            return self.get_pipeline_status(project_id=int(pid), mr_iid=int(mid))

        def _tool_get_diff(**_kwargs):
            """Returns the merge request unified diff (truncated to 6000 chars)."""
            return {"diff": _diff_snapshot[:6000]}

        def _tool_get_mr_info(**_kwargs):
            """Returns title, author, branches and description of the merge request."""
            return {
                "title": mr_title,
                "author": author,
                "source_branch": source_branch,
                "target_branch": target_branch,
                "description": mr_description[:1000],
            }

        tools = {
            "get_pipeline_status": _tool_get_pipeline,
            "get_diff": _tool_get_diff,
            "get_mr_info": _tool_get_mr_info,
        }

        react_task = (
            f"Perform a thorough code review of MR !{mr_iid} (project {project_id}).\n"
            f"MR Title: {mr_title} | Author: {author} | {source_branch} → {target_branch}\n\n"
            "Follow these steps:\n"
            "1. Call get_pipeline_status to check the CI result.\n"
            "2. Call get_diff to retrieve the code changes.\n"
            "3. Analyse the diff for bugs, security issues, and domain-specific compliance concerns.\n"
            "4. Produce FinalAnswer as strict JSON with keys:\n"
            "   'summary' (string), 'issues' (array), 'suggestions' (array), 'approved' (bool)."
        )

        response_text = self._react_loop(react_task, tools, max_steps=5)

        try:
            response_text = response_text.replace("```json", "").replace("```", "").strip()
            review = json.loads(response_text)
        except json.JSONDecodeError:
            self.logger.error("LLM did not return valid JSON for MR review.")
            review = {
                "summary": "AI review parsing failed.",
                "issues": ["LLM output could not be parsed as JSON"],
                "suggestions": [],
                "approved": False,
                "raw_output": response_text,
            }

        # 4. Audit log
        trace_id = self.audit.log_event(
            actor="DeveloperAgent",
            action_type="MR_REVIEW",
            input_context=f"project={project_id} mr_iid={mr_iid} title={mr_title}",
            output_content=json.dumps(review),
            metadata={"project_id": project_id, "mr_iid": mr_iid, "source_branch": source_branch},
        )

        review["trace_id"] = trace_id
        review["mr_iid"] = mr_iid
        review["mr_title"] = mr_title
        self.logger.info("MR !%d review complete. Approved: %s (trace: %s)", mr_iid, review.get("approved"), trace_id)
        return review

    def create_mr_from_issue(self, project_id: int, issue_iid: int, source_branch: Optional[str] = None) -> dict:
        """
        Gets an issue's details, uses LLM to draft an MR, and creates it in GitLab.

        Args:
            project_id:    GitLab project ID
            issue_iid:     Issue internal ID (IID)
            source_branch: Branch name to use (auto-generated if not provided)

        Returns:
            dict with MR URL, title, and trace_id, or 'error'.
        """
        self.logger.info("Creating MR from issue #%d in project %d", issue_iid, project_id)

        # 1. Fetch issue
        issue_data, err = self._gl_get(f"/projects/{project_id}/issues/{issue_iid}")
        if err:
            return {"error": f"Failed to fetch issue: {err}"}

        issue_title = issue_data.get("title", "Unknown Issue")
        issue_description = issue_data.get("description", "")
        issue_labels = issue_data.get("labels", [])

        # 2. Auto-generate branch name if not provided
        if not source_branch:
            slug = issue_title.lower().replace(" ", "-")[:40]
            # Remove non-alphanumeric except hyphens
            slug = "".join(c for c in slug if c.isalnum() or c == "-")
            source_branch = f"sage-ai/{issue_iid}-{slug}"

        # 3. Use LLM to draft MR title and description
        # Prefer solution-level mr_create_system_prompt from prompts.yaml / SKILL.md
        try:
            from src.core.project_loader import project_config
            _dev_prompts = project_config.get_prompts().get("developer", {})
            system_prompt = _dev_prompts.get(
                "mr_create_system_prompt",
                (
                    "You are a software development agent. "
                    "Given a GitLab issue, draft a concise merge request title and description. "
                    "Output strict JSON with keys: 'mr_title' (string) and 'mr_description' (string, markdown). "
                    "The description should reference the issue, explain the proposed changes, and list testing steps. "
                    "Do not output markdown fences."
                )
            )
            _sol_ctx = project_config.solution_context
            if _sol_ctx:
                system_prompt = _sol_ctx + "\n\n" + system_prompt
            _skill = project_config.skill_content
            if _skill:
                system_prompt = system_prompt + "\n\n## Domain Skills\n" + _skill
        except Exception:
            system_prompt = (
                "You are a software development agent. "
                "Given a GitLab issue, draft a concise merge request title and description. "
                "Output strict JSON with keys: 'mr_title' (string) and 'mr_description' (string, markdown). "
                "The description should reference the issue, explain the proposed changes, and list testing steps. "
                "Do not output markdown fences."
            )

        user_prompt = (
            f"Issue #{issue_iid}: {issue_title}\n"
            f"Labels: {', '.join(issue_labels)}\n"
            f"Description:\n{issue_description[:3000]}\n\n"
            "Draft an MR title and description for this issue:"
        )

        response_text = self.llm.generate(user_prompt, system_prompt)

        try:
            response_text = response_text.replace("```json", "").replace("```", "").strip()
            mr_draft = json.loads(response_text)
            mr_title = mr_draft.get("mr_title", f"Fix: {issue_title}")
            mr_description = mr_draft.get("mr_description", f"Resolves #{issue_iid}\n\n{issue_description}")
        except json.JSONDecodeError:
            self.logger.warning("LLM output not valid JSON, using fallback MR title/description.")
            mr_title = f"Fix: {issue_title}"
            mr_description = f"Resolves #{issue_iid}\n\n{issue_description}"

        # 4. Get default branch for the project
        project_data, _ = self._gl_get(f"/projects/{project_id}")
        target_branch = (project_data or {}).get("default_branch", "main")

        # 5. Create the MR via GitLab API
        mr_body = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": mr_title,
            "description": mr_description + f"\n\nCloses #{issue_iid}",
            "labels": "sage-ai",
            "remove_source_branch": True,
        }

        mr_data, err = self._gl_post(f"/projects/{project_id}/merge_requests", mr_body)
        if err:
            self.audit.log_event(
                actor="DeveloperAgent",
                action_type="MR_CREATE_FAILED",
                input_context=f"project={project_id} issue_iid={issue_iid}",
                output_content=f"Error: {err}",
                metadata={"project_id": project_id, "issue_iid": issue_iid},
            )
            return {"error": f"Failed to create MR: {err}"}

        mr_url = mr_data.get("web_url", "")
        mr_iid = mr_data.get("iid")

        # 6. Audit log
        trace_id = self.audit.log_event(
            actor="DeveloperAgent",
            action_type="MR_CREATED",
            input_context=f"project={project_id} issue_iid={issue_iid}",
            output_content=json.dumps({"mr_iid": mr_iid, "mr_url": mr_url, "mr_title": mr_title}),
            metadata={"project_id": project_id, "issue_iid": issue_iid, "mr_iid": mr_iid},
        )

        self.logger.info("MR !%s created from issue #%d: %s", mr_iid, issue_iid, mr_url)
        return {
            "mr_iid": mr_iid,
            "mr_url": mr_url,
            "mr_title": mr_title,
            "source_branch": source_branch,
            "target_branch": target_branch,
            "issue_iid": issue_iid,
            "trace_id": trace_id,
        }

    def list_open_mrs(self, project_id: int) -> dict:
        """
        Lists all open merge requests for a project.

        Args:
            project_id: GitLab project ID

        Returns:
            dict with 'merge_requests' list and 'count'.
        """
        data, err = self._gl_get(f"/projects/{project_id}/merge_requests", params={"state": "opened"})
        if err:
            return {"error": err}

        mrs = []
        for mr in (data or []):
            mrs.append({
                "iid": mr.get("iid"),
                "title": mr.get("title"),
                "author": mr.get("author", {}).get("name", "Unknown"),
                "source_branch": mr.get("source_branch"),
                "target_branch": mr.get("target_branch"),
                "created_at": mr.get("created_at", ""),
                "web_url": mr.get("web_url", ""),
                "labels": mr.get("labels", []),
                "pipeline_status": mr.get("pipeline", {}).get("status", "none") if mr.get("pipeline") else "none",
            })

        self.logger.info("Listed %d open MRs for project %d", len(mrs), project_id)
        return {"merge_requests": mrs, "count": len(mrs), "project_id": project_id}

    def get_pipeline_status(self, project_id: int, mr_iid: int) -> dict:
        """
        Gets the CI/CD pipeline status for a merge request.

        Args:
            project_id: GitLab project ID
            mr_iid:     Merge Request IID

        Returns:
            dict with 'status', 'pipeline_id', 'stages', or 'error'.
        """
        # Get MR details including pipeline
        mr_data, err = self._gl_get(f"/projects/{project_id}/merge_requests/{mr_iid}")
        if err:
            return {"error": err}

        pipeline = mr_data.get("pipeline") or mr_data.get("head_pipeline")
        if not pipeline:
            return {"status": "no_pipeline", "mr_iid": mr_iid, "message": "No pipeline associated with this MR."}

        pipeline_id = pipeline.get("id")

        # Get detailed pipeline info
        pipeline_detail, err = self._gl_get(f"/projects/{project_id}/pipelines/{pipeline_id}")
        if err:
            return {
                "status": pipeline.get("status", "unknown"),
                "pipeline_id": pipeline_id,
                "web_url": pipeline.get("web_url", ""),
            }

        # Get jobs
        jobs_data, _ = self._gl_get(f"/projects/{project_id}/pipelines/{pipeline_id}/jobs")
        stages = {}
        for job in (jobs_data or []):
            stage = job.get("stage", "unknown")
            if stage not in stages:
                stages[stage] = []
            stages[stage].append({
                "name": job.get("name"),
                "status": job.get("status"),
                "duration": job.get("duration"),
                "web_url": job.get("web_url", ""),
            })

        return {
            "mr_iid": mr_iid,
            "pipeline_id": pipeline_id,
            "status": pipeline_detail.get("status"),
            "created_at": pipeline_detail.get("created_at"),
            "finished_at": pipeline_detail.get("finished_at"),
            "duration": pipeline_detail.get("duration"),
            "web_url": pipeline_detail.get("web_url", ""),
            "stages": stages,
        }

    def propose_code_patch(self, file_path: str, error_description: str, current_code: str) -> dict:
        """
        Uses the LLM to propose a code patch for a given error/issue.

        Args:
            file_path:         Path of the file to patch (context only, not read from disk)
            error_description: Description of the bug or required change
            current_code:      The current source code content

        Returns:
            dict with 'patch' (unified diff format), 'explanation', and 'trace_id'.
        """
        self.logger.info("Proposing patch for %s: %s", file_path, error_description[:80])

        system_prompt = (
            "You are a Senior Embedded Software Engineer. "
            "You will be given a file path, an error description, and the current source code. "
            "Produce ONLY a unified diff patch (standard `diff -u` format) fixing the described issue. "
            "Output strict JSON with keys: "
            "'patch' (string: the complete unified diff), "
            "'explanation' (string: what was changed and why), "
            "'confidence' (string: 'high'/'medium'/'low'). "
            "Do not output markdown fences. The patch MUST be valid unified diff format."
        )

        user_prompt = (
            f"File: {file_path}\n"
            f"Error/Issue: {error_description}\n\n"
            f"Current Code:\n{current_code[:6000]}\n\n"
            "Provide the fix as a unified diff JSON:"
        )

        response_text = self.llm.generate(user_prompt, system_prompt)

        try:
            response_text = response_text.replace("```json", "").replace("```", "").strip()
            patch_result = json.loads(response_text)
        except json.JSONDecodeError:
            self.logger.error("LLM did not return valid JSON for patch proposal.")
            patch_result = {
                "patch": "",
                "explanation": "AI output parsing failed.",
                "confidence": "low",
                "raw_output": response_text,
            }

        # Audit log
        trace_id = self.audit.log_event(
            actor="DeveloperAgent",
            action_type="CODE_PATCH_PROPOSAL",
            input_context=f"file={file_path} error={error_description[:200]}",
            output_content=json.dumps(patch_result),
            metadata={"file_path": file_path, "confidence": patch_result.get("confidence", "unknown")},
        )

        patch_result["trace_id"] = trace_id
        patch_result["file_path"] = file_path
        self.logger.info("Patch proposed for %s (confidence: %s, trace: %s)", file_path, patch_result.get("confidence"), trace_id)
        return patch_result

    def add_mr_comment(self, project_id: int, mr_iid: int, comment: str) -> dict:
        """
        Posts a comment (note) on a GitLab merge request.

        Args:
            project_id: GitLab project ID
            mr_iid:     Merge Request IID
            comment:    Comment text (Markdown supported)

        Returns:
            dict with 'note_id', 'web_url', or 'error'.
        """
        self.logger.info("Adding comment to MR !%d in project %d", mr_iid, project_id)

        data, err = self._gl_post(
            f"/projects/{project_id}/merge_requests/{mr_iid}/notes",
            {"body": comment},
        )
        if err:
            return {"error": f"Failed to post MR comment: {err}"}

        note_id = data.get("id")

        # Audit log
        self.audit.log_event(
            actor="DeveloperAgent",
            action_type="MR_COMMENT_ADDED",
            input_context=f"project={project_id} mr_iid={mr_iid}",
            output_content=comment[:500],
            metadata={"project_id": project_id, "mr_iid": mr_iid, "note_id": note_id},
        )

        self.logger.info("Comment added to MR !%d (note_id: %s)", mr_iid, note_id)
        return {
            "note_id": note_id,
            "mr_iid": mr_iid,
            "project_id": project_id,
            "status": "posted",
        }


# ---------------------------------------------------------------------------
# Global access point
# ---------------------------------------------------------------------------
developer_agent = DeveloperAgent()
