"""
SAGE Framework — Solution Constitution
=======================================
Per-solution "blue book" defining immutable principles, hard constraints,
agent voice/tone, decision rules, and knowledge priorities.

The constitution is the soul of a solution — it shapes every agent's
behavior by being injected as a preamble into system prompts.

File location:  solutions/<name>/constitution.yaml
Version history: stored inside the YAML as `_history` list.

Usage:
    from src.core.constitution import get_constitution

    c = get_constitution()
    preamble = c.build_prompt_preamble()
    injected = c.inject_into_prompt(system_prompt)
    violations = c.check_action(action_description)
"""

import copy
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class Constitution:
    """
    Loads, validates, and enforces a solution's constitution.yaml.

    Thread-safe for concurrent reads and writes via a reentrant lock.
    """

    def __init__(
        self,
        solutions_dir: str | None = None,
        solution: str | None = None,
    ):
        self._lock = threading.RLock()
        self._solutions_dir = solutions_dir or self._default_solutions_dir()
        self._solution = solution or self._default_solution()
        self._data: dict = {}
        self._path: str = ""
        self._dirty = False
        self._load()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _default_solutions_dir() -> str:
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        return os.environ.get(
            "SAGE_SOLUTIONS_DIR",
            os.path.join(project_root, "solutions"),
        )

    @staticmethod
    def _default_solution() -> str:
        return os.environ.get("SAGE_PROJECT", "").strip().lower()

    def _load(self) -> None:
        sol_dir = os.path.join(self._solutions_dir, self._solution)
        self._path = os.path.join(sol_dir, "constitution.yaml")
        if not os.path.isfile(self._path):
            self._data = {}
            return
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                self._data = yaml.safe_load(fh) or {}
        except (yaml.YAMLError, OSError) as exc:
            logger.warning("Failed to load constitution at %s: %s", self._path, exc)
            self._data = {}

    # ------------------------------------------------------------------
    # Public read properties
    # ------------------------------------------------------------------

    @property
    def is_empty(self) -> bool:
        return not self._data or (
            not self._data.get("principles")
            and not self._data.get("constraints")
        )

    @property
    def name(self) -> str:
        return self._data.get("meta", {}).get("name", "")

    @property
    def version(self) -> int:
        return self._data.get("meta", {}).get("version", 0)

    @property
    def principles(self) -> list[dict]:
        return self._data.get("principles", [])

    @property
    def constraints(self) -> list[str]:
        return self._data.get("constraints", [])

    @property
    def voice(self) -> dict:
        return self._data.get("voice", {})

    @property
    def decisions(self) -> dict:
        return self._data.get("decisions", {})

    @property
    def knowledge(self) -> dict:
        return self._data.get("knowledge", {})

    # ------------------------------------------------------------------
    # Principle accessors
    # ------------------------------------------------------------------

    def get_principle(self, principle_id: str) -> dict | None:
        with self._lock:
            for p in self.principles:
                if p.get("id") == principle_id:
                    return p
            return None

    def get_non_negotiable_principles(self) -> list[dict]:
        with self._lock:
            return [p for p in self.principles if p.get("weight", 0) >= 1.0]

    def get_principles_by_priority(self) -> list[dict]:
        with self._lock:
            return sorted(self.principles, key=lambda p: p.get("weight", 0), reverse=True)

    # ------------------------------------------------------------------
    # Prompt injection
    # ------------------------------------------------------------------

    def build_prompt_preamble(self) -> str:
        """Build a text preamble from the constitution for injection into agent prompts."""
        if self.is_empty:
            return ""

        sections: list[str] = []
        sections.append("## Solution Constitution\n")

        # Principles
        if self.principles:
            sections.append("### Guiding Principles (by priority)")
            for p in self.get_principles_by_priority():
                weight_tag = " [NON-NEGOTIABLE]" if p.get("weight", 0) >= 1.0 else ""
                sections.append(f"- {p.get('text', '')}{weight_tag}")

        # Constraints
        if self.constraints:
            sections.append("\n### Hard Constraints (violations are rejected)")
            for c in self.constraints:
                sections.append(f"- {c}")

        # Voice
        if self.voice:
            tone = self.voice.get("tone", "")
            avoid = self.voice.get("avoid", [])
            if tone:
                sections.append(f"\n### Communication Style\nTone: {tone}")
            if avoid:
                sections.append(f"Avoid: {', '.join(avoid)}")

        return "\n".join(sections) + "\n"

    def inject_into_prompt(self, system_prompt: str) -> str:
        """Prepend constitution preamble to an existing system prompt."""
        preamble = self.build_prompt_preamble()
        if not preamble:
            return system_prompt
        return preamble + "\n" + system_prompt

    # ------------------------------------------------------------------
    # Constraint checking
    # ------------------------------------------------------------------

    def check_action(self, action_description: str) -> dict:
        """
        Check if an action description violates any hard constraints.
        Returns {"allowed": bool, "violations": [str]}.
        """
        if self.is_empty:
            return {"allowed": True, "violations": []}

        violations = []
        desc_lower = action_description.lower()
        for constraint in self.constraints:
            # Extract key phrases from constraint for matching
            keywords = self._extract_constraint_keywords(constraint)
            if all(kw in desc_lower for kw in keywords):
                violations.append(constraint)

        return {
            "allowed": len(violations) == 0,
            "violations": violations,
        }

    def _extract_constraint_keywords(self, constraint: str) -> list[str]:
        """Extract meaningful keywords from a constraint for matching."""
        # Look for quoted paths or specific terms
        lower = constraint.lower()
        keywords = []
        # Extract /path/ patterns
        import re
        paths = re.findall(r'/\w+/', lower)
        keywords.extend(paths)
        # If we found paths, that's enough for matching
        if keywords:
            return keywords
        # Otherwise use significant words (skip common ones)
        skip = {"never", "always", "must", "should", "all", "any", "the",
                "a", "an", "in", "on", "be", "is", "are", "not", "no",
                "without", "with", "to", "of", "for", "and", "or"}
        words = [w for w in lower.split() if w not in skip and len(w) > 2]
        return words[:3]  # top 3 significant words

    def check_escalation(self, text: str) -> dict:
        """
        Check if text contains escalation keywords defined in decisions.
        Returns {"should_escalate": bool, "matched_keywords": [str]}.
        """
        keywords = self.decisions.get("escalation_keywords", [])
        if not keywords:
            return {"should_escalate": False, "matched_keywords": []}

        text_lower = text.lower()
        matched = [kw for kw in keywords if kw.lower() in text_lower]
        return {
            "should_escalate": len(matched) > 0,
            "matched_keywords": matched,
        }

    def can_auto_approve(self, category: str) -> bool:
        """Check if a category is in the auto-approve list."""
        auto_cats = self.decisions.get("auto_approve_categories", [])
        return category.lower() in [c.lower() for c in auto_cats]

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def add_principle(self, id: str, text: str, weight: float = 0.5) -> None:
        with self._lock:
            if self.get_principle(id) is not None:
                raise ValueError(f"Principle '{id}' already exists")
            self._ensure_data_structure()
            self._data["principles"].append({"id": id, "text": text, "weight": weight})
            self._dirty = True

    def update_principle(self, principle_id: str, **kwargs) -> None:
        with self._lock:
            p = self.get_principle(principle_id)
            if p is None:
                raise ValueError(f"Principle '{principle_id}' not found")
            for k, v in kwargs.items():
                p[k] = v
            self._dirty = True

    def remove_principle(self, principle_id: str) -> None:
        with self._lock:
            before = len(self.principles)
            self._data["principles"] = [
                p for p in self.principles if p.get("id") != principle_id
            ]
            if len(self._data["principles"]) == before:
                raise ValueError(f"Principle '{principle_id}' not found")
            self._dirty = True

    def add_constraint(self, constraint: str) -> None:
        with self._lock:
            self._ensure_data_structure()
            self._data.setdefault("constraints", []).append(constraint)
            self._dirty = True

    def remove_constraint(self, constraint: str) -> None:
        with self._lock:
            constraints = self._data.get("constraints", [])
            if constraint not in constraints:
                raise ValueError(f"Constraint not found: {constraint}")
            constraints.remove(constraint)
            self._dirty = True

    def update_voice(self, **kwargs) -> None:
        with self._lock:
            self._ensure_data_structure()
            self._data.setdefault("voice", {}).update(kwargs)
            self._dirty = True

    def update_decisions(self, **kwargs) -> None:
        with self._lock:
            self._ensure_data_structure()
            self._data.setdefault("decisions", {}).update(kwargs)
            self._dirty = True

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, changed_by: str = "system") -> None:
        """Save constitution to disk, auto-incrementing version and recording history."""
        with self._lock:
            self._ensure_data_structure()
            meta = self._data["meta"]
            meta["version"] = meta.get("version", 0) + 1
            meta["last_updated"] = datetime.now(timezone.utc).isoformat()
            meta["updated_by"] = changed_by

            # Append to version history
            history = self._data.setdefault("_history", [])
            history.append({
                "version": meta["version"],
                "changed_by": changed_by,
                "timestamp": meta["last_updated"],
            })

            # Ensure directory exists
            os.makedirs(os.path.dirname(self._path), exist_ok=True)

            with open(self._path, "w", encoding="utf-8") as fh:
                yaml.dump(self._data, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)

            self._dirty = False
            logger.info("Constitution saved: v%d by %s at %s", meta["version"], changed_by, self._path)

    def reload(self) -> None:
        """Reload constitution from disk."""
        with self._lock:
            self._load()
            self._dirty = False

    def get_version_history(self) -> list[dict]:
        return self._data.get("_history", [])

    def to_dict(self) -> dict:
        """Return a deep copy of the full constitution data."""
        with self._lock:
            return copy.deepcopy(self._data)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Validate the constitution structure. Returns list of error strings (empty = valid)."""
        if self.is_empty:
            return []

        errors: list[str] = []
        seen_ids: set[str] = set()

        for i, p in enumerate(self.principles):
            if "id" not in p:
                errors.append(f"Principle {i}: missing 'id' field")
            if "text" not in p:
                errors.append(f"Principle {i}: missing 'text' field")
            weight = p.get("weight", 0.5)
            if not (0.0 <= weight <= 1.0):
                errors.append(f"Principle {i} ('{p.get('id', '?')}'): weight {weight} out of range [0, 1]")
            pid = p.get("id", "")
            if pid in seen_ids:
                errors.append(f"Principle {i}: duplicate id '{pid}'")
            if pid:
                seen_ids.add(pid)

        return errors

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "is_empty": self.is_empty,
                "name": self.name,
                "version": self.version,
                "principle_count": len(self.principles),
                "constraint_count": len(self.constraints),
                "non_negotiable_count": len(self.get_non_negotiable_principles()),
                "has_voice": bool(self.voice),
                "has_decisions": bool(self.decisions),
                "has_knowledge": bool(self.knowledge),
                "history_entries": len(self.get_version_history()),
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_data_structure(self) -> None:
        """Ensure minimum data structure exists."""
        if "meta" not in self._data:
            self._data["meta"] = {
                "name": "",
                "version": 0,
                "last_updated": "",
                "updated_by": "",
            }
        if "principles" not in self._data:
            self._data["principles"] = []


# ---------------------------------------------------------------------------
# Lazy singleton
# ---------------------------------------------------------------------------

_instance: Constitution | None = None
_instance_lock = threading.Lock()


def get_constitution() -> Constitution:
    """Return the module-level Constitution singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = Constitution()
    return _instance
