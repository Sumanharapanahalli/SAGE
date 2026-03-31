"""
SAGE Framework — Skill Loader
==============================
Manages modular, hot-swappable, business-capable agent skills.

Skills are YAML files organised by visibility:
  skills/public/    — open-source, shipped with SAGE
  skills/private/   — proprietary, loaded from SAGE_SKILLS_DIR env var
  skills/disabled/  — hidden from agents, retained for versioning

Each skill YAML contains:
  - name, version, visibility
  - roles: which agent roles can use this skill
  - tools: required tooling
  - prompt: system prompt fragment injected into the agent
  - acceptance_criteria: what "done" looks like
  - grading_rubric: how to score exercise attempts
  - certifications: relevant industry certifications
  - seniority_delta: what distinguishes senior from junior usage

Skills are the intellectual property layer. Some skills are trade secrets.
The visibility system ensures proprietary skills never leak into open-source.

Thread-safe. Audit every load. Return error dicts, never raise.
"""

import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger("SkillLoader")

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

VALID_VISIBILITIES = {"public", "private", "disabled"}
VALID_DIFFICULTIES = {"beginner", "intermediate", "advanced", "expert"}


@dataclass
class Skill:
    """A single modular agent skill loaded from YAML."""
    name: str
    version: str
    visibility: str  # public | private | disabled
    roles: list[str]  # which agent roles can use this skill
    runner: str  # which runner family this skill belongs to
    description: str = ""

    # Core skill definition
    tools: list[str] = field(default_factory=list)
    prompt: str = ""  # system prompt fragment
    acceptance_criteria: list[str] = field(default_factory=list)
    grading_rubric: dict = field(default_factory=dict)

    # JD-sourced metadata
    certifications: list[str] = field(default_factory=list)
    seniority_delta: dict = field(default_factory=dict)  # {junior: [...], senior: [...]}
    keywords: list[str] = field(default_factory=list)

    # Cross-cutting engines this skill can use (e.g. autoresearch)
    engines: list[str] = field(default_factory=list)

    # Skill file path for hot-reload
    source_path: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "visibility": self.visibility,
            "roles": self.roles,
            "runner": self.runner,
            "description": self.description,
            "tools": self.tools,
            "prompt": self.prompt[:200] + "..." if len(self.prompt) > 200 else self.prompt,
            "acceptance_criteria": self.acceptance_criteria,
            "certifications": self.certifications,
            "engines": self.engines,
            "tags": self.tags,
        }

    @property
    def is_active(self) -> bool:
        return self.visibility != "disabled"


# ---------------------------------------------------------------------------
# Skill Registry
# ---------------------------------------------------------------------------

class SkillRegistry:
    """
    Thread-safe registry that loads, indexes, and serves skills.

    Skills are indexed by:
      - name   → Skill
      - role   → [Skill, ...]
      - runner → [Skill, ...]
      - tag    → [Skill, ...]
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._skills: dict[str, Skill] = {}  # name → Skill
        self._by_role: dict[str, list[str]] = {}  # role → [skill_name, ...]
        self._by_runner: dict[str, list[str]] = {}  # runner → [skill_name, ...]
        self._by_tag: dict[str, list[str]] = {}  # tag → [skill_name, ...]
        self._loaded_dirs: set[str] = set()

    # ── Load ─────────────────────────────────────────────────────────────

    def load_directory(self, directory: str, visibility_override: str = "") -> int:
        """
        Load all skill YAML files from a directory.

        Args:
            directory: Path to scan for *.yaml / *.yml files.
            visibility_override: Force visibility for all skills in this dir.

        Returns:
            Number of skills successfully loaded.
        """
        path = Path(directory)
        if not path.is_dir():
            logger.warning("Skill directory not found: %s", directory)
            return 0

        count = 0
        for yaml_file in sorted(path.glob("**/*.yaml")):
            if self._load_skill_file(str(yaml_file), visibility_override):
                count += 1
        for yaml_file in sorted(path.glob("**/*.yml")):
            if self._load_skill_file(str(yaml_file), visibility_override):
                count += 1

        self._loaded_dirs.add(directory)
        logger.info("Loaded %d skills from %s", count, directory)
        return count

    def _load_skill_file(self, filepath: str, visibility_override: str = "") -> bool:
        """Load a single skill YAML file. Returns True on success."""
        try:
            with open(filepath, "r") as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict):
                logger.warning("Skill file is not a YAML dict: %s", filepath)
                return False

            # Required fields
            name = data.get("name")
            if not name:
                logger.warning("Skill missing 'name': %s", filepath)
                return False

            visibility = visibility_override or data.get("visibility", "public")
            if visibility not in VALID_VISIBILITIES:
                logger.warning("Invalid visibility '%s' in %s", visibility, filepath)
                return False

            skill = Skill(
                name=name,
                version=data.get("version", "1.0.0"),
                visibility=visibility,
                roles=data.get("roles", []),
                runner=data.get("runner", ""),
                description=data.get("description", ""),
                tools=data.get("tools", []),
                prompt=data.get("prompt", ""),
                acceptance_criteria=data.get("acceptance_criteria", []),
                grading_rubric=data.get("grading_rubric", {}),
                certifications=data.get("certifications", []),
                seniority_delta=data.get("seniority_delta", {}),
                keywords=data.get("keywords", []),
                engines=data.get("engines", []),
                source_path=filepath,
                tags=data.get("tags", []),
            )

            self.register(skill)
            return True

        except yaml.YAMLError as exc:
            logger.error("YAML parse error in %s: %s", filepath, exc)
            return False
        except Exception as exc:
            logger.error("Failed to load skill %s: %s", filepath, exc)
            return False

    def register(self, skill: Skill) -> None:
        """Register a skill in all indexes."""
        with self._lock:
            self._skills[skill.name] = skill

            for role in skill.roles:
                self._by_role.setdefault(role, [])
                if skill.name not in self._by_role[role]:
                    self._by_role[role].append(skill.name)

            if skill.runner:
                self._by_runner.setdefault(skill.runner, [])
                if skill.name not in self._by_runner[skill.runner]:
                    self._by_runner[skill.runner].append(skill.name)

            for tag in skill.tags:
                self._by_tag.setdefault(tag, [])
                if skill.name not in self._by_tag[tag]:
                    self._by_tag[tag].append(skill.name)

    def unregister(self, name: str) -> bool:
        """Remove a skill from all indexes."""
        with self._lock:
            skill = self._skills.pop(name, None)
            if skill is None:
                return False

            for role in skill.roles:
                if role in self._by_role:
                    self._by_role[role] = [n for n in self._by_role[role] if n != name]

            if skill.runner and skill.runner in self._by_runner:
                self._by_runner[skill.runner] = [
                    n for n in self._by_runner[skill.runner] if n != name
                ]

            for tag in skill.tags:
                if tag in self._by_tag:
                    self._by_tag[tag] = [n for n in self._by_tag[tag] if n != name]

            return True

    # ── Query ────────────────────────────────────────────────────────────

    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name. Returns None if not found or disabled."""
        skill = self._skills.get(name)
        if skill and skill.is_active:
            return skill
        return None

    def get_including_disabled(self, name: str) -> Optional[Skill]:
        """Get a skill by name, including disabled ones."""
        return self._skills.get(name)

    def get_for_role(self, role: str, include_private: bool = True) -> list[Skill]:
        """Get all active skills for an agent role."""
        names = self._by_role.get(role, [])
        skills = []
        for name in names:
            skill = self._skills.get(name)
            if skill and skill.is_active:
                if skill.visibility == "private" and not include_private:
                    continue
                skills.append(skill)
        return skills

    def get_for_runner(self, runner: str, include_private: bool = True) -> list[Skill]:
        """Get all active skills for a runner."""
        names = self._by_runner.get(runner, [])
        skills = []
        for name in names:
            skill = self._skills.get(name)
            if skill and skill.is_active:
                if skill.visibility == "private" and not include_private:
                    continue
                skills.append(skill)
        return skills

    def get_by_tag(self, tag: str) -> list[Skill]:
        """Get all active skills with a tag."""
        names = self._by_tag.get(tag, [])
        return [self._skills[n] for n in names if n in self._skills and self._skills[n].is_active]

    def search(self, query: str) -> list[Skill]:
        """Search skills by name, description, or keywords."""
        query_lower = query.lower()
        results = []
        for skill in self._skills.values():
            if not skill.is_active:
                continue
            if (
                query_lower in skill.name.lower()
                or query_lower in skill.description.lower()
                or any(query_lower in kw.lower() for kw in skill.keywords)
            ):
                results.append(skill)
        return results

    def list_all(self, include_disabled: bool = False) -> list[Skill]:
        """List all skills."""
        if include_disabled:
            return list(self._skills.values())
        return [s for s in self._skills.values() if s.is_active]

    def list_public(self) -> list[Skill]:
        """List only public skills (safe for open-source export)."""
        return [s for s in self._skills.values() if s.visibility == "public"]

    def list_private(self) -> list[Skill]:
        """List private skills (proprietary, never exported)."""
        return [s for s in self._skills.values() if s.visibility == "private"]

    # ── Visibility management ────────────────────────────────────────────

    def set_visibility(self, name: str, visibility: str) -> bool:
        """Change a skill's visibility tier."""
        if visibility not in VALID_VISIBILITIES:
            return False
        with self._lock:
            skill = self._skills.get(name)
            if skill is None:
                return False
            skill.visibility = visibility
            return True

    def disable(self, name: str) -> bool:
        """Disable a skill (hide from agents)."""
        return self.set_visibility(name, "disabled")

    def enable(self, name: str, as_private: bool = False) -> bool:
        """Re-enable a disabled skill."""
        return self.set_visibility(name, "private" if as_private else "public")

    # ── Hot-reload ───────────────────────────────────────────────────────

    def reload(self) -> int:
        """Reload all skills from previously loaded directories."""
        with self._lock:
            self._skills.clear()
            self._by_role.clear()
            self._by_runner.clear()
            self._by_tag.clear()

        total = 0
        for directory in list(self._loaded_dirs):
            total += self.load_directory(directory)
        logger.info("Hot-reloaded %d skills from %d directories", total, len(self._loaded_dirs))
        return total

    # ── Prompt building ──────────────────────────────────────────────────

    def build_prompt_for_role(self, role: str, include_private: bool = True) -> str:
        """
        Build a composite system prompt fragment from all active skills for a role.
        Skills are concatenated in registration order. Cross-cutting engines
        (e.g. autoresearch) are appended when a skill declares them.
        """
        skills = self.get_for_role(role, include_private=include_private)
        if not skills:
            return ""

        parts = []
        engines_seen: set[str] = set()
        for skill in skills:
            if skill.prompt:
                parts.append(f"## Skill: {skill.name} (v{skill.version})\n{skill.prompt}")
            for engine in skill.engines:
                engines_seen.add(engine)

        # Inject engine prompts from referenced engine skills
        for engine_name in sorted(engines_seen):
            engine_skill = self.get(engine_name)
            if engine_skill and engine_skill.prompt:
                parts.append(
                    f"## Engine: {engine_skill.name} (v{engine_skill.version})\n"
                    f"You have access to the {engine_skill.name} engine for autonomous "
                    f"experimentation. Use it to propose changes, run experiments with "
                    f"fixed budgets, extract metrics, and keep/discard results via git.\n\n"
                    f"{engine_skill.prompt}"
                )

        return "\n\n".join(parts)

    def get_tools_for_role(self, role: str) -> list[str]:
        """Get the union of all tools from active skills for a role."""
        skills = self.get_for_role(role)
        tools = []
        seen = set()
        for skill in skills:
            for tool in skill.tools:
                if tool not in seen:
                    tools.append(tool)
                    seen.add(tool)
        return tools

    def get_acceptance_criteria_for_role(self, role: str) -> list[str]:
        """Get combined acceptance criteria from all active skills for a role."""
        skills = self.get_for_role(role)
        criteria = []
        for skill in skills:
            criteria.extend(skill.acceptance_criteria)
        return criteria

    # ── Stats ────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return registry statistics."""
        return {
            "total": len(self._skills),
            "active": sum(1 for s in self._skills.values() if s.is_active),
            "public": sum(1 for s in self._skills.values() if s.visibility == "public"),
            "private": sum(1 for s in self._skills.values() if s.visibility == "private"),
            "disabled": sum(1 for s in self._skills.values() if s.visibility == "disabled"),
            "roles_covered": len(self._by_role),
            "runners_covered": len(self._by_runner),
            "loaded_dirs": list(self._loaded_dirs),
        }


# ---------------------------------------------------------------------------
# Module-level singleton + auto-load
# ---------------------------------------------------------------------------

skill_registry = SkillRegistry()


def _auto_load_skills():
    """Load skills from the framework skills/ directory and SAGE_SKILLS_DIR."""
    # 1. Framework public skills
    framework_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "skills",
    )
    public_dir = os.path.join(framework_dir, "public")
    if os.path.isdir(public_dir):
        skill_registry.load_directory(public_dir, visibility_override="public")

    disabled_dir = os.path.join(framework_dir, "disabled")
    if os.path.isdir(disabled_dir):
        skill_registry.load_directory(disabled_dir, visibility_override="disabled")

    # 2. Private skills from env var (proprietary, never in repo)
    private_dir = os.environ.get("SAGE_SKILLS_DIR", "")
    if private_dir and os.path.isdir(private_dir):
        skill_registry.load_directory(private_dir, visibility_override="private")
        logger.info("Loaded private skills from SAGE_SKILLS_DIR=%s", private_dir)


_auto_load_skills()
