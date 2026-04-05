"""
SAGE Collective Intelligence — Git-Backed Agent Knowledge Sharing
================================================================

Agents publish learnings and help requests as structured YAML files
in a shared Git repository. Provides versioning, attribution, and
semantic search via a dedicated VectorMemory collection.

Architecture:
  - Git repo at {solutions_dir}/.collective/ (default)
  - YAML files: learnings/{solution}/{topic}/{id}.yaml
  - Help requests: help-requests/{open|closed}/{id}.yaml
  - Search index: dedicated VectorMemory(explicit_solution="__collective__")
  - Write operations protected by threading.Lock
"""

import logging
import os
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from glob import glob
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# CollectiveMemory
# ──────────────────────────────────────────────────────────────────────


class CollectiveMemory:
    """Git-backed collective intelligence for multi-agent knowledge sharing."""

    def __init__(
        self,
        repo_path: str,
        remote_url: str = "",
        auto_push: bool = False,
        require_approval: bool = True,
    ):
        self.repo_path = repo_path
        self.remote_url = remote_url
        self.auto_push = auto_push
        self.require_approval = require_approval
        self._lock = threading.Lock()
        self._git_available = True
        self._vector_store = None  # lazy init

        self._ensure_repo()

    # ── Vector store (lazy) ───────────────────────────────────────────

    @property
    def _vs(self):
        if self._vector_store is None:
            try:
                from src.memory.vector_store import VectorMemory
                self._vector_store = VectorMemory(explicit_solution="__collective__")
            except Exception:
                self._vector_store = _FallbackVectorStore()
        return self._vector_store

    # ── Git operations ────────────────────────────────────────────────

    def _git_run(self, *args, check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command in the repo directory."""
        try:
            return subprocess.run(
                ["git"] + list(args),
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
                check=check,
            )
        except FileNotFoundError:
            self._git_available = False
            raise RuntimeError("git is not installed")

    def _ensure_repo(self) -> None:
        """Initialize or clone the Git repo. Idempotent."""
        os.makedirs(self.repo_path, exist_ok=True)

        # Create directory structure
        for d in [
            "learnings",
            os.path.join("help-requests", "open"),
            os.path.join("help-requests", "closed"),
        ]:
            os.makedirs(os.path.join(self.repo_path, d), exist_ok=True)

        git_dir = os.path.join(self.repo_path, ".git")
        if os.path.isdir(git_dir):
            return  # already initialized

        try:
            if self.remote_url:
                subprocess.run(
                    ["git", "clone", self.remote_url, self.repo_path],
                    capture_output=True, text=True, timeout=60, check=True,
                )
            else:
                self._git_run("init")
                # Ensure git has a user identity for commits
                self._git_run("config", "user.email", "sage@collective.local", check=False)
                self._git_run("config", "user.name", "SAGE Collective", check=False)
                # Initial commit so HEAD exists
                readme = os.path.join(self.repo_path, "README.md")
                with open(readme, "w") as f:
                    f.write("# SAGE Collective Intelligence\n\nShared agent learnings and help requests.\n")
                self._git_run("add", "README.md")
                self._git_run("commit", "-m", "init: collective intelligence repo")
        except (subprocess.CalledProcessError, RuntimeError) as exc:
            logger.warning("Git init failed, running without version control: %s", exc)
            self._git_available = False

    def _commit(self, message: str, files: list[str]) -> str:
        """Stage files and commit. Returns commit SHA."""
        if not self._git_available:
            return ""
        with self._lock:
            for f in files:
                self._git_run("add", f)
            self._git_run("commit", "-m", message)
            result = self._git_run("rev-parse", "--short", "HEAD")
            sha = result.stdout.strip()
            if self.auto_push:
                self._push()
            return sha

    def _push(self) -> bool:
        """Push to remote. Returns True on success."""
        if not self._git_available or not self.remote_url:
            return False
        try:
            self._git_run("pull", "--rebase", check=False)
            self._git_run("push")
            return True
        except Exception as exc:
            logger.warning("Git push failed: %s", exc)
            return False

    def _pull(self) -> bool:
        """Pull from remote. Returns True on success."""
        if not self._git_available or not self.remote_url:
            return False
        try:
            self._git_run("pull")
            return True
        except Exception as exc:
            logger.warning("Git pull failed: %s", exc)
            return False

    # ── Learning CRUD ─────────────────────────────────────────────────

    def publish_learning(self, learning: dict, proposed_by: str = "system") -> str:
        """
        Publish a learning to the collective repo.

        If require_approval=True, creates a proposal instead of writing directly.
        Returns: learning ID (or proposal trace_id if gated).
        """
        learning_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        full_learning = {
            "id": learning_id,
            "author_agent": learning.get("author_agent", "unknown"),
            "author_solution": learning.get("author_solution", "unknown"),
            "topic": learning.get("topic", "general"),
            "title": learning.get("title", ""),
            "content": learning.get("content", ""),
            "tags": learning.get("tags", []),
            "confidence": learning.get("confidence", 0.5),
            "validation_count": 0,
            "created_at": now,
            "updated_at": now,
            "source_task_id": learning.get("source_task_id", ""),
        }

        if self.require_approval:
            try:
                from src.core.proposal_store import get_proposal_store, RiskClass
                store = get_proposal_store()
                proposal = store.create(
                    action_type="collective_publish",
                    risk_class=RiskClass.STATEFUL,
                    payload={"learning": full_learning},
                    description=f"Publish learning: {full_learning['title']}",
                    proposed_by=proposed_by,
                )
                return proposal.trace_id
            except Exception:
                logger.warning("Proposal store unavailable, writing directly")

        self._write_and_commit_learning(full_learning)
        return learning_id

    def _write_and_commit_learning(self, learning: dict) -> dict:
        """Write learning YAML to disk and commit."""
        solution = learning["author_solution"]
        topic = learning["topic"]
        learning_id = learning["id"]

        dir_path = os.path.join(self.repo_path, "learnings", solution, topic)
        os.makedirs(dir_path, exist_ok=True)

        file_name = f"{learning_id}.yaml"
        file_path = os.path.join(dir_path, file_name)
        rel_path = os.path.join("learnings", solution, topic, file_name)

        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(learning, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        self._commit(f"learning: {learning['title'][:60]}", [rel_path])
        self._index_learning(learning)

        logger.info("Published learning: id=%s topic=%s", learning_id, topic)
        return learning

    def get_learning(self, learning_id: str) -> Optional[dict]:
        """Retrieve a learning by ID. Searches all YAML files."""
        pattern = os.path.join(self.repo_path, "learnings", "**", f"{learning_id}.yaml")
        matches = glob(pattern, recursive=True)
        if not matches:
            return None
        with open(matches[0], encoding="utf-8") as f:
            return yaml.safe_load(f)

    def list_learnings(
        self,
        solution: str = None,
        topic: str = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List learnings, optionally filtered by solution and/or topic."""
        if solution and topic:
            pattern = os.path.join(self.repo_path, "learnings", solution, topic, "*.yaml")
        elif solution:
            pattern = os.path.join(self.repo_path, "learnings", solution, "**", "*.yaml")
        elif topic:
            pattern = os.path.join(self.repo_path, "learnings", "**", topic, "*.yaml")
        else:
            pattern = os.path.join(self.repo_path, "learnings", "**", "*.yaml")

        results = []
        for path in sorted(glob(pattern, recursive=True)):
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data:
                    results.append(data)

        return results[offset: offset + limit]

    def search_learnings(
        self,
        query: str,
        tags: list[str] = None,
        solution: str = None,
        limit: int = 10,
    ) -> list[dict]:
        """Semantic search across indexed learnings."""
        # Get all learnings from disk for filtering
        all_learnings = {l["id"]: l for l in self.list_learnings(limit=1000)}

        if query:
            # Use vector store for semantic search
            vs_results = self._vs.search(query, k=limit * 3)
            # vs_results are strings; extract IDs from them
            matched = []
            for text in vs_results:
                for lid, l in all_learnings.items():
                    if l["title"] in text or l["content"][:100] in text:
                        if lid not in [m["id"] for m in matched]:
                            matched.append(l)
            results = matched if matched else list(all_learnings.values())
        else:
            results = list(all_learnings.values())

        # Apply filters
        if tags:
            results = [r for r in results if any(t in r.get("tags", []) for t in tags)]
        if solution:
            results = [r for r in results if r.get("author_solution") == solution]

        return results[:limit]

    def validate_learning(self, learning_id: str, validated_by: str) -> dict:
        """Increment validation_count and slightly boost confidence."""
        learning = self.get_learning(learning_id)
        if not learning:
            raise ValueError(f"Learning {learning_id} not found")

        learning["validation_count"] = learning.get("validation_count", 0) + 1
        # Boost confidence slightly (asymptotic to 1.0)
        current = learning.get("confidence", 0.5)
        learning["confidence"] = min(1.0, current + (1.0 - current) * 0.1)
        learning["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Rewrite file
        pattern = os.path.join(self.repo_path, "learnings", "**", f"{learning_id}.yaml")
        matches = glob(pattern, recursive=True)
        if matches:
            with open(matches[0], "w", encoding="utf-8") as f:
                yaml.dump(learning, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            rel_path = os.path.relpath(matches[0], self.repo_path)
            self._commit(f"validate: {learning['title'][:50]} by {validated_by}", [rel_path])

        return learning

    # ── Help Request CRUD ─────────────────────────────────────────────

    def create_help_request(self, request: dict) -> str:
        """Create a help request in the open/ directory."""
        req_id = f"hr-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        full_request = {
            "id": req_id,
            "title": request.get("title", ""),
            "requester_agent": request.get("requester_agent", "unknown"),
            "requester_solution": request.get("requester_solution", "unknown"),
            "status": "open",
            "urgency": request.get("urgency", "medium"),
            "required_expertise": request.get("required_expertise", []),
            "context": request.get("context", ""),
            "created_at": now,
            "claimed_by": None,
            "responses": [],
            "resolved_at": None,
        }

        file_name = f"{req_id}.yaml"
        file_path = os.path.join(self.repo_path, "help-requests", "open", file_name)
        rel_path = os.path.join("help-requests", "open", file_name)

        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(full_request, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        self._commit(f"help-request: {full_request['title'][:60]}", [rel_path])
        logger.info("Created help request: id=%s", req_id)
        return req_id

    def _get_help_request_path(self, request_id: str) -> Optional[str]:
        """Find help request file in open/ or closed/."""
        for status_dir in ["open", "closed"]:
            path = os.path.join(self.repo_path, "help-requests", status_dir, f"{request_id}.yaml")
            if os.path.isfile(path):
                return path
        return None

    def _read_help_request(self, request_id: str) -> Optional[dict]:
        """Read help request data from disk."""
        path = self._get_help_request_path(request_id)
        if not path:
            return None
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def list_help_requests(
        self,
        status: str = "open",
        expertise: list[str] = None,
    ) -> list[dict]:
        """List help requests filtered by status and optionally expertise."""
        pattern = os.path.join(self.repo_path, "help-requests", status, "*.yaml")
        results = []
        for path in sorted(glob(pattern)):
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data:
                    if expertise:
                        req_exp = data.get("required_expertise", [])
                        if any(e in req_exp for e in expertise):
                            results.append(data)
                    else:
                        results.append(data)
        return results

    def claim_help_request(self, request_id: str, agent: str, solution: str) -> dict:
        """Claim a help request. Raises if already claimed."""
        path = os.path.join(self.repo_path, "help-requests", "open", f"{request_id}.yaml")
        if not os.path.isfile(path):
            raise ValueError(f"Help request {request_id} not found in open requests")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data.get("claimed_by"):
            raise ValueError(f"Help request {request_id} is already claimed")

        data["status"] = "claimed"
        data["claimed_by"] = {
            "agent": agent,
            "solution": solution,
            "claimed_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        rel_path = os.path.join("help-requests", "open", f"{request_id}.yaml")
        self._commit(f"claim: {data['title'][:50]} by {agent}", [rel_path])
        return data

    def respond_to_help_request(self, request_id: str, response: dict) -> dict:
        """Add a response to a help request."""
        path = self._get_help_request_path(request_id)
        if not path:
            raise ValueError(f"Help request {request_id} not found")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        response_entry = {
            "responder_agent": response.get("responder_agent", "unknown"),
            "responder_solution": response.get("responder_solution", "unknown"),
            "content": response.get("content", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        data.setdefault("responses", []).append(response_entry)

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        rel_path = os.path.relpath(path, self.repo_path)
        self._commit(
            f"respond: {data['title'][:40]} by {response_entry['responder_agent']}",
            [rel_path],
        )
        return data

    def close_help_request(self, request_id: str) -> dict:
        """Close a help request — move from open/ to closed/."""
        open_path = os.path.join(self.repo_path, "help-requests", "open", f"{request_id}.yaml")
        if not os.path.isfile(open_path):
            raise ValueError(f"Help request {request_id} not found in open requests")

        with open(open_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        data["status"] = "closed"
        data["resolved_at"] = datetime.now(timezone.utc).isoformat()

        closed_path = os.path.join(self.repo_path, "help-requests", "closed", f"{request_id}.yaml")
        with open(closed_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        os.remove(open_path)

        with self._lock:
            if self._git_available:
                self._git_run("add", os.path.join("help-requests", "closed", f"{request_id}.yaml"))
                self._git_run("rm", "--cached", os.path.join("help-requests", "open", f"{request_id}.yaml"),
                              check=False)
                self._git_run("commit", "-m", f"close: {data['title'][:50]}")

        logger.info("Closed help request: id=%s", request_id)
        return data

    # ── Sync & Indexing ───────────────────────────────────────────────

    def sync(self) -> dict:
        """Pull latest from remote and re-index all learnings."""
        pulled = self._pull()
        count = self._rebuild_index()
        return {"pulled": pulled, "indexed": count}

    def _index_learning(self, learning: dict) -> None:
        """Add a single learning to the vector store."""
        text = f"{learning['title']}\n{learning['content']}"
        metadata = {
            "id": learning["id"],
            "author_solution": learning.get("author_solution", ""),
            "topic": learning.get("topic", ""),
            "tags": ",".join(learning.get("tags", [])),
            "type": "collective_learning",
        }
        self._vs.add_entry(text, metadata=metadata)

    def _rebuild_index(self) -> int:
        """Walk all learning YAMLs and re-index into vector store."""
        pattern = os.path.join(self.repo_path, "learnings", "**", "*.yaml")
        count = 0
        for path in glob(pattern, recursive=True):
            try:
                with open(path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data and data.get("id"):
                    self._index_learning(data)
                    count += 1
            except Exception as exc:
                logger.warning("Failed to index %s: %s", path, exc)
        logger.info("Rebuilt collective index: %d learnings", count)
        return count

    def _update_manifest(self) -> None:
        """Regenerate index.yaml with current counts and distributions."""
        learnings = self.list_learnings(limit=10000)
        help_open = self.list_help_requests(status="open")

        topics: dict[str, int] = {}
        solutions: dict[str, int] = {}
        for l in learnings:
            t = l.get("topic", "general")
            topics[t] = topics.get(t, 0) + 1
            s = l.get("author_solution", "unknown")
            solutions[s] = solutions.get(s, 0) + 1

        manifest = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "learning_count": len(learnings),
            "help_request_count": len(help_open),
            "topics": topics,
            "solutions": solutions,
        }

        index_path = os.path.join(self.repo_path, "index.yaml")
        with open(index_path, "w", encoding="utf-8") as f:
            yaml.dump(manifest, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # ── Stats ─────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return contribution counts, trending topics, top contributors."""
        learnings = self.list_learnings(limit=10000)
        help_open = self.list_help_requests(status="open")
        help_closed = self.list_help_requests(status="closed")

        topics: dict[str, int] = {}
        contributors: dict[str, int] = {}
        for l in learnings:
            t = l.get("topic", "general")
            topics[t] = topics.get(t, 0) + 1
            s = l.get("author_solution", "unknown")
            contributors[s] = contributors.get(s, 0) + 1

        return {
            "learning_count": len(learnings),
            "help_request_count": len(help_open),
            "help_requests_closed": len(help_closed),
            "topics": topics,
            "contributors": contributors,
        }

    # ── Static helpers ────────────────────────────────────────────────

    @staticmethod
    def extract_learning_from_result(
        task_result: dict, agent_role: str, solution: str,
    ) -> Optional[dict]:
        """
        Extract a reusable learning from a completed task result.
        Returns a learning dict ready for publish_learning(), or None.
        """
        output = task_result.get("output", "") or task_result.get("analysis", "")
        if not output or len(output) < 50:
            return None

        return {
            "author_agent": agent_role,
            "author_solution": solution,
            "topic": task_result.get("task_type", "general"),
            "title": (task_result.get("summary", "") or output[:80]).strip(),
            "content": output[:2000],
            "tags": [],
            "confidence": 0.5,
            "source_task_id": task_result.get("task_id", ""),
        }


# ──────────────────────────────────────────────────────────────────────
# Fallback vector store (when ChromaDB unavailable)
# ──────────────────────────────────────────────────────────────────────


class _FallbackVectorStore:
    """Keyword-based fallback when VectorMemory is unavailable."""

    def __init__(self):
        self._entries: list[dict] = []

    def add_entry(self, text: str, metadata: dict = None) -> str:
        entry_id = str(uuid.uuid4())
        self._entries.append({"id": entry_id, "text": text, "metadata": metadata or {}})
        return entry_id

    def search(self, query: str, k: int = 3) -> list[str]:
        query_lower = query.lower()
        scored = []
        for entry in self._entries:
            text = entry["text"].lower()
            score = sum(1 for word in query_lower.split() if word in text)
            if score > 0:
                scored.append((score, entry["text"]))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [text for _, text in scored[:k]]

    def bulk_import(self, entries: list[dict]) -> int:
        for e in entries:
            self.add_entry(e.get("text", ""), e.get("metadata", {}))
        return len(entries)


# ──────────────────────────────────────────────────────────────────────
# Lazy singleton
# ──────────────────────────────────────────────────────────────────────

_collective_memory: Optional[CollectiveMemory] = None
_cm_lock = threading.Lock()


def get_collective_memory() -> CollectiveMemory:
    """Get or create the global CollectiveMemory instance."""
    global _collective_memory
    if _collective_memory is None:
        with _cm_lock:
            if _collective_memory is None:
                # Determine repo path from environment or defaults
                solutions_dir = os.environ.get(
                    "SAGE_SOLUTIONS_DIR",
                    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                        os.path.abspath(__file__),
                    ))), "solutions"),
                )
                repo_path = os.path.join(solutions_dir, ".collective")
                _collective_memory = CollectiveMemory(repo_path=repo_path)
    return _collective_memory
