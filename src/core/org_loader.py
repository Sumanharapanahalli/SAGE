"""
SAGE Framework — OrgLoader
Loads org.yaml, detects cycles, merges prompts/tasks across parent chain, resolves channels.
Gracefully degrades when org.yaml is absent.
"""
import logging
import os
import re
from typing import Optional
import yaml

logger = logging.getLogger(__name__)


class OrgLoaderError(Exception):
    pass


class OrgLoader:
    """
    Reads org.yaml once at construction. Immutable after init.
    Re-instantiate via reload_org_loader() after org.yaml changes.

    Gracefully degrades: when org.yaml is absent, all methods return
    empty lists, False, or None — existing single-solution behaviour unchanged.
    """

    def __init__(self, solutions_dir: str):
        self._solutions_dir = solutions_dir
        self._org: dict = {}
        self._load()

    @property
    def org_name(self) -> Optional[str]:
        return self._org.get("org", {}).get("name")

    @property
    def root_solution(self) -> Optional[str]:
        return self._org.get("org", {}).get("root_solution")

    def get_parent_chain(self, solution_name: str) -> list:
        chain = []
        current = solution_name
        visited = set()
        while current:
            if current in visited:
                raise OrgLoaderError(f"Cycle at '{current}' in parent chain")
            visited.add(current)
            chain.append(current)
            project = self._load_yaml(os.path.join(self._solutions_dir, current, "project.yaml"))
            current = project.get("parent")
        return chain

    def get_merged_prompts(self, solution_name: str) -> dict:
        """Merge prompts.yaml root→child. Child key wins on conflict."""
        merged: dict = {}
        for name in reversed(self.get_parent_chain(solution_name)):
            data = self._load_yaml(os.path.join(self._solutions_dir, name, "prompts.yaml"))
            merged.update(data)
        return merged

    def get_merged_tasks(self, solution_name: str) -> dict:
        """Merge tasks.yaml root→child. Child entry replaces parent entirely on conflict."""
        merged_types: list = []
        merged_desc: dict = {}
        merged_payloads: dict = {}
        merged_hooks: dict = {}
        merged_policies: dict = {}
        for name in reversed(self.get_parent_chain(solution_name)):
            data = self._load_yaml(os.path.join(self._solutions_dir, name, "tasks.yaml"))
            for t in data.get("task_types", []):
                if t not in merged_types:
                    merged_types.append(t)
            merged_desc.update(data.get("task_descriptions", {}))
            merged_payloads.update(data.get("task_payloads", {}))
            merged_hooks.update(data.get("task_hooks", {}))
            merged_policies.update(data.get("task_sandbox_policies", {}))
        result: dict = {"task_types": merged_types}
        if merged_desc:
            result["task_descriptions"] = merged_desc
        if merged_payloads:
            result["task_payloads"] = merged_payloads
        if merged_hooks:
            result["task_hooks"] = merged_hooks
        if merged_policies:
            result["task_sandbox_policies"] = merged_policies
        return result

    def get_channel_collection_names(self, solution_name: str) -> list:
        """Return chroma collection names this solution consumes."""
        channels = self._org.get("org", {}).get("knowledge_channels", {})
        return [
            self._normalize_channel(name)
            for name, conf in channels.items()
            if solution_name in conf.get("consumers", [])
        ]

    def get_channel_db_path(self) -> Optional[str]:
        root = self.root_solution
        if not root:
            return None
        path = os.path.join(self._solutions_dir, root, ".sage", "chroma_db")
        return path

    def get_producer_channel_name(self, solution_name: str, channel_label: str) -> Optional[str]:
        """Return normalized collection name if solution is a producer for channel_label, else None."""
        channels = self._org.get("org", {}).get("knowledge_channels", {})
        if channel_label not in channels:
            return None
        if solution_name in channels[channel_label].get("producers", []):
            return self._normalize_channel(channel_label)
        return None

    def is_route_allowed(self, source_solution: str, target_solution: str) -> bool:
        if not self.org_name:
            return False
        project = self._load_yaml(
            os.path.join(self._solutions_dir, source_solution, "project.yaml")
        )
        return any(r.get("target") == target_solution for r in project.get("cross_team_routes", []))

    def get_all_routes(self) -> list:
        """Return all cross_team_routes across all solutions as [{source, target}]."""
        result = []
        if not os.path.isdir(self._solutions_dir):
            return result
        for name in os.listdir(self._solutions_dir):
            sol_dir = os.path.join(self._solutions_dir, name)
            if not os.path.isdir(sol_dir):
                continue
            proj = self._load_yaml(os.path.join(sol_dir, "project.yaml"))
            for r in proj.get("cross_team_routes", []):
                result.append({"source": name, "target": r.get("target", "")})
        return result

    def _load(self):
        org_path = os.path.join(self._solutions_dir, "org.yaml")
        if not os.path.exists(org_path):
            logger.debug("No org.yaml at %s — org features disabled", org_path)
            return
        self._org = self._load_yaml(org_path)
        self._detect_cycles()
        logger.info("OrgLoader: loaded org '%s'", self.org_name)

    def _detect_cycles(self):
        if not os.path.isdir(self._solutions_dir):
            return
        for name in os.listdir(self._solutions_dir):
            if not os.path.isdir(os.path.join(self._solutions_dir, name)):
                continue
            visited: set = set()
            current: Optional[str] = name
            while current:
                if current in visited:
                    raise OrgLoaderError(
                        f"Circular inheritance cycle detected: '{current}' appears twice "
                        f"in the parent chain starting from '{name}'"
                    )
                visited.add(current)
                current = self._load_yaml(
                    os.path.join(self._solutions_dir, current, "project.yaml")
                ).get("parent")

    @staticmethod
    def _normalize_channel(name: str) -> str:
        return "channel_" + re.sub(r'[^a-z0-9_]', '_', name.lower())

    @staticmethod
    def _load_yaml(path: str) -> dict:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                return yaml.safe_load(fh) or {}
        return {}


# Module-level singleton
_SOLUTIONS_DIR = os.environ.get(
    "SAGE_SOLUTIONS_DIR",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "solutions",
    ),
)

org_loader = OrgLoader(_SOLUTIONS_DIR)


def reload_org_loader() -> "OrgLoader":
    global org_loader
    org_loader = OrgLoader(_SOLUTIONS_DIR)
    return org_loader
