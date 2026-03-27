"""
SAGE Framework — Exercise Catalog
====================================
Scalable exercise generation system for Agent Gym.

Architecture:
  Seed exercises (industry-grade, ~45-100 per domain, 469 total)
      ↓
  Template engine (LLM generates variants from seeds)
      ↓
  Variant exercises (~100 per seed = 50,000+ total)
      ↓
  Difficulty auto-calibration (agent success rate determines true difficulty)
      ↓
  Prerequisite graph (exercise B requires mastering exercise A)

Exercise sources:
  1. Runner-defined exercises (get_exercises) — hardcoded, always available
  2. Skill YAML catalogs — seed exercises shipped with skills
  3. Generated variants — LLM-expanded from seeds
  4. Community-contributed — loaded from SAGE_EXERCISES_DIR

Thread-safe. SQLite-backed. Domain-agnostic orchestration with domain-specific seeds.
"""

import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import yaml

logger = logging.getLogger("ExerciseCatalog")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Exercise:
    """A single training exercise for the Agent Gym."""
    id: str
    domain: str          # runner name (openfw, openswe, openml, etc.)
    skill: str           # skill name from skill YAML
    title: str
    description: str     # full exercise prompt — what the agent must do
    difficulty: str      # beginner, intermediate, advanced, expert
    tags: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    context: str = ""    # setup info, background, constraints
    task_type: str = ""  # maps to runner task types
    time_limit: int = 300  # seconds
    prerequisites: list[str] = field(default_factory=list)  # exercise IDs that must be mastered first
    seed_id: str = ""    # if this is a variant, the seed exercise it was generated from
    variant_axis: str = ""  # what dimension this variant explores (e.g., "platform", "concurrency")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "domain": self.domain,
            "skill": self.skill,
            "title": self.title,
            "description": self.description[:500] + ("..." if len(self.description) > 500 else ""),
            "difficulty": self.difficulty,
            "tags": self.tags,
            "acceptance_criteria": self.acceptance_criteria,
            "task_type": self.task_type,
            "time_limit": self.time_limit,
            "prerequisites": self.prerequisites,
            "seed_id": self.seed_id,
            "variant_axis": self.variant_axis,
        }


# ---------------------------------------------------------------------------
# Seed catalog definitions — per domain
# Each domain has ~50-100 seed exercises organized by difficulty
# ---------------------------------------------------------------------------

# Variant axes: dimensions along which exercises can be expanded
VARIANT_AXES = {
    "openfw": [
        "platform", "rtos", "peripheral", "optimization", "safety",
        "concurrency", "power_management", "communication_protocol",
        "memory_constraint", "error_recovery",
    ],
    "openswe": [
        "language", "framework", "scale", "pattern", "testing",
        "concurrency", "api_design", "database", "security", "performance",
    ],
    "openml": [
        "dataset_size", "model_type", "metric", "feature_engineering",
        "deployment", "monitoring", "fairness", "interpretability",
        "pipeline_stage", "domain_application",
    ],
    "openeda": [
        "layer_count", "signal_integrity", "power_delivery", "thermal",
        "component_density", "manufacturing_constraint", "emc_compliance",
        "impedance_matching", "via_strategy", "bom_optimization",
    ],
    "opensim": [
        "simulation_type", "clock_domain", "power_rail", "timing_constraint",
        "noise_analysis", "corner_case", "temperature_range",
        "process_variation", "testbench_complexity", "verification_method",
    ],
    "opendoc": [
        "document_type", "regulatory_standard", "audience", "compliance_level",
        "cross_reference", "traceability", "revision_control",
        "template_format", "review_stage", "localization",
    ],
    "opendesign": [
        "accessibility_level", "viewport", "interaction_pattern", "branding",
        "design_system", "animation", "dark_mode", "rtl_support",
        "component_complexity", "user_flow",
    ],
    "openbrowser": [
        "app_type", "viewport", "auth_method", "framework",
        "real_time_features", "accessibility_level", "performance_target",
        "security_posture", "i18n_scope", "test_depth",
    ],
    "openstrategy": [
        "market_size", "competition_level", "go_to_market", "pricing_model",
        "customer_segment", "regulatory_environment", "geographic_scope",
        "technology_readiness", "team_size", "funding_stage",
    ],
}


def _generate_seed_catalog() -> dict[str, list[dict]]:
    """
    Return comprehensive seed exercise catalog from exercise_seeds module.

    ~530 seed exercises across 8 domains, each expandable to thousands
    of variants via LLM generation. Seeds are sourced from industry
    certifications, professional training programs, and domain standards.
    """
    from src.core.exercise_seeds import get_all_seeds
    return get_all_seeds()



# ---------------------------------------------------------------------------
# Exercise Catalog
# ---------------------------------------------------------------------------

class ExerciseCatalog:
    """
    Scalable exercise catalog for Agent Gym.

    Manages seed exercises, generates variants, tracks prerequisites,
    and auto-calibrates difficulty based on agent success rates.
    """

    def __init__(self, db_path: str = ""):
        self.logger = logging.getLogger("ExerciseCatalog")
        if not db_path:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                ".gym_catalog.db",
            )
        self.db_path = db_path
        self._lock = threading.Lock()
        self._exercises: dict[str, Exercise] = {}  # id → Exercise
        self._domain_index: dict[str, list[str]] = {}  # domain → [exercise_ids]
        self._difficulty_index: dict[str, dict[str, list[str]]] = {}  # domain → difficulty → [ids]
        self._prerequisites: dict[str, list[str]] = {}  # exercise_id → [prereq_ids]

        self._init_db()
        self._load_seed_catalog()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS exercises (
                        id TEXT PRIMARY KEY,
                        domain TEXT NOT NULL,
                        skill TEXT DEFAULT '',
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        difficulty TEXT DEFAULT 'intermediate',
                        tags_json TEXT DEFAULT '[]',
                        acceptance_json TEXT DEFAULT '[]',
                        context TEXT DEFAULT '',
                        task_type TEXT DEFAULT '',
                        time_limit INTEGER DEFAULT 300,
                        prerequisites_json TEXT DEFAULT '[]',
                        seed_id TEXT DEFAULT '',
                        variant_axis TEXT DEFAULT '',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_ex_domain ON exercises(domain);
                    CREATE INDEX IF NOT EXISTS idx_ex_difficulty ON exercises(difficulty);
                    CREATE INDEX IF NOT EXISTS idx_ex_seed ON exercises(seed_id);
                """)
                conn.commit()
            finally:
                conn.close()

    def _load_seed_catalog(self):
        """Load seed exercises into memory and DB."""
        catalog = _generate_seed_catalog()
        loaded = 0

        for domain, seeds in catalog.items():
            for seed in seeds:
                ex_id = self._make_id(domain, seed["title"])
                exercise = Exercise(
                    id=ex_id,
                    domain=domain,
                    skill=f"{domain}_skill",
                    title=seed["title"],
                    description=seed["description"],
                    difficulty=seed["difficulty"],
                    tags=seed.get("tags", []),
                    acceptance_criteria=seed.get("acceptance_criteria", []),
                    task_type=seed.get("task_type", ""),
                    time_limit=seed.get("time_limit", 300),
                    prerequisites=seed.get("prerequisites", []),
                )
                self._register(exercise)
                loaded += 1

        self.logger.info("Loaded %d seed exercises across %d domains", loaded, len(catalog))

    def _make_id(self, domain: str, title: str) -> str:
        """Generate deterministic exercise ID from domain + title."""
        slug = re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')
        short_hash = hashlib.md5(f"{domain}:{title}".encode()).hexdigest()[:6]
        return f"{domain}_{slug}_{short_hash}"

    def _register(self, exercise: Exercise) -> None:
        """Register an exercise in memory indexes."""
        self._exercises[exercise.id] = exercise

        if exercise.domain not in self._domain_index:
            self._domain_index[exercise.domain] = []
        if exercise.id not in self._domain_index[exercise.domain]:
            self._domain_index[exercise.domain].append(exercise.id)

        if exercise.domain not in self._difficulty_index:
            self._difficulty_index[exercise.domain] = {}
        if exercise.difficulty not in self._difficulty_index[exercise.domain]:
            self._difficulty_index[exercise.domain][exercise.difficulty] = []
        if exercise.id not in self._difficulty_index[exercise.domain][exercise.difficulty]:
            self._difficulty_index[exercise.domain][exercise.difficulty].append(exercise.id)

        if exercise.prerequisites:
            self._prerequisites[exercise.id] = exercise.prerequisites

    # ── Query ────────────────────────────────────────────────────────

    def get(self, exercise_id: str) -> Optional[Exercise]:
        return self._exercises.get(exercise_id)

    def get_for_domain(self, domain: str, difficulty: str = "") -> list[Exercise]:
        """Get exercises for a domain, optionally filtered by difficulty."""
        if difficulty and domain in self._difficulty_index:
            ids = self._difficulty_index.get(domain, {}).get(difficulty, [])
        else:
            ids = self._domain_index.get(domain, [])
        return [self._exercises[eid] for eid in ids if eid in self._exercises]

    def get_for_tags(self, tags: list[str], domain: str = "") -> list[Exercise]:
        """Get exercises matching any of the given tags."""
        tag_set = set(tags)
        results = []
        source = self._exercises.values()
        if domain:
            source_ids = self._domain_index.get(domain, [])
            source = [self._exercises[eid] for eid in source_ids if eid in self._exercises]
        for ex in source:
            if tag_set & set(ex.tags):
                results.append(ex)
        return results

    def check_prerequisites(self, exercise_id: str, mastered_ids: set[str]) -> bool:
        """Check if all prerequisites for an exercise are mastered."""
        prereqs = self._prerequisites.get(exercise_id, [])
        return all(p in mastered_ids for p in prereqs)

    def count(self, domain: str = "") -> dict:
        """Count exercises by domain and difficulty."""
        if domain:
            exercises = self.get_for_domain(domain)
            by_diff = {}
            for ex in exercises:
                by_diff[ex.difficulty] = by_diff.get(ex.difficulty, 0) + 1
            return {"domain": domain, "total": len(exercises), "by_difficulty": by_diff}

        total = 0
        by_domain = {}
        for d, ids in self._domain_index.items():
            by_domain[d] = len(ids)
            total += len(ids)
        return {"total": total, "by_domain": by_domain}

    # ── Variant generation ───────────────────────────────────────────

    def generate_variants(
        self,
        domain: str,
        count: int = 10,
        difficulty: str = "",
        axis: str = "",
    ) -> list[Exercise]:
        """
        Generate exercise variants from seed exercises using LLM.

        Args:
            domain: Which domain to generate for
            count: Number of variants to generate
            difficulty: Optional difficulty filter for seeds
            axis: Optional variant axis (e.g., "platform", "scale")

        Returns:
            List of generated Exercise objects (also registered in catalog)
        """
        seeds = self.get_for_domain(domain, difficulty)
        if not seeds:
            return []

        # Pick seeds that aren't already variants
        original_seeds = [s for s in seeds if not s.seed_id]
        if not original_seeds:
            original_seeds = seeds[:5]

        axes = VARIANT_AXES.get(domain, ["complexity", "scale", "constraint"])
        if axis:
            axes = [axis]

        generated = []
        try:
            from src.core.llm_gateway import llm_gateway

            # Generate in batches
            batch_size = min(count, 10)
            seed_sample = original_seeds[:min(5, len(original_seeds))]

            for batch_start in range(0, count, batch_size):
                remaining = min(batch_size, count - batch_start)
                seed = seed_sample[batch_start % len(seed_sample)]
                target_axis = axes[batch_start % len(axes)]

                prompt = (
                    f"Generate {remaining} exercise variants for a {domain} training gym.\n\n"
                    f"Base exercise:\n"
                    f"  Title: {seed.title}\n"
                    f"  Description: {seed.description}\n"
                    f"  Difficulty: {seed.difficulty}\n"
                    f"  Tags: {seed.tags}\n\n"
                    f"Variation axis: {target_axis}\n"
                    f"Generate variants that explore the '{target_axis}' dimension.\n"
                    f"Each variant should be progressively harder or test a different aspect.\n\n"
                    f"Return JSON array: [\n"
                    f'  {{"title": "...", "description": "...", "difficulty": "beginner|intermediate|advanced|expert", '
                    f'"tags": [...], "acceptance_criteria": [...], "task_type": "{seed.task_type}"}}\n'
                    f"]\n\n"
                    f"Make descriptions detailed and specific. Include concrete technical requirements."
                )

                response = llm_gateway.generate(
                    prompt,
                    f"You are an expert {domain} trainer creating practice exercises. "
                    f"Generate realistic, verifiable exercises that test real skills.",
                    trace_name=f"exercise_catalog.generate.{domain}",
                )

                # Parse response
                response = response.replace("```json", "").replace("```", "").strip()
                match = re.search(r'\[[\s\S]*\]', response)
                if match:
                    variants = json.loads(match.group(0))
                    for v in variants[:remaining]:
                        ex = Exercise(
                            id=self._make_id(domain, v.get("title", f"variant_{len(generated)}")),
                            domain=domain,
                            skill=seed.skill,
                            title=v.get("title", "Generated variant"),
                            description=v.get("description", ""),
                            difficulty=v.get("difficulty", seed.difficulty),
                            tags=v.get("tags", seed.tags),
                            acceptance_criteria=v.get("acceptance_criteria", []),
                            task_type=v.get("task_type", seed.task_type),
                            seed_id=seed.id,
                            variant_axis=target_axis,
                        )
                        self._register(ex)
                        self._save_exercise(ex)
                        generated.append(ex)

        except Exception as exc:
            self.logger.error("Variant generation failed: %s", exc)

        self.logger.info("Generated %d variants for %s", len(generated), domain)
        return generated

    def _save_exercise(self, ex: Exercise) -> None:
        """Persist a generated exercise to SQLite."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO exercises
                    (id, domain, skill, title, description, difficulty, tags_json,
                     acceptance_json, context, task_type, time_limit,
                     prerequisites_json, seed_id, variant_axis)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ex.id, ex.domain, ex.skill, ex.title, ex.description,
                    ex.difficulty, json.dumps(ex.tags), json.dumps(ex.acceptance_criteria),
                    ex.context, ex.task_type, ex.time_limit,
                    json.dumps(ex.prerequisites), ex.seed_id, ex.variant_axis,
                ))
                conn.commit()
            finally:
                conn.close()

    def load_generated(self) -> int:
        """Load previously generated exercises from SQLite."""
        loaded = 0
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    "SELECT * FROM exercises WHERE seed_id != ''"
                ).fetchall()
                for row in rows:
                    ex = Exercise(
                        id=row["id"],
                        domain=row["domain"],
                        skill=row["skill"],
                        title=row["title"],
                        description=row["description"],
                        difficulty=row["difficulty"],
                        tags=json.loads(row["tags_json"]),
                        acceptance_criteria=json.loads(row["acceptance_json"]),
                        context=row["context"],
                        task_type=row["task_type"],
                        time_limit=row["time_limit"],
                        prerequisites=json.loads(row["prerequisites_json"]),
                        seed_id=row["seed_id"],
                        variant_axis=row["variant_axis"],
                    )
                    self._register(ex)
                    loaded += 1
            finally:
                conn.close()

        if loaded:
            self.logger.info("Restored %d generated exercises from SQLite", loaded)
        return loaded

    # ── Template-based bulk variant generation (no LLM) ─────────────

    def generate_template_variants(self, domain: str = "", target_count: int = 10000) -> int:
        """
        Generate exercise variants structurally using template multiplication.
        No LLM needed — instant generation of thousands of exercises.

        Strategy: seed × difficulty × constraint_modifier × scale_modifier
        469 seeds × 4 difficulties × 5 constraints × 5 scales = ~47,000 exercises

        Returns number of variants generated.
        """
        DIFFICULTY_LEVELS = ["beginner", "intermediate", "advanced", "expert"]

        CONSTRAINT_MODIFIERS = {
            "openswe": [
                ("under strict memory limits (max 256MB heap)", "memory_constrained"),
                ("with zero external dependencies allowed", "no_deps"),
                ("targeting 100% branch coverage in tests", "full_coverage"),
                ("that must handle 10K concurrent requests", "high_concurrency"),
                ("following MISRA-C style strict coding standards", "strict_standards"),
                ("with comprehensive error recovery for every failure mode", "error_recovery"),
                ("that must complete in under 50ms p99 latency", "low_latency"),
                ("using event-driven architecture only", "event_driven"),
                ("with full OpenTelemetry observability built in", "observable"),
                ("that is backward compatible with v1 API consumers", "backward_compat"),
            ],
            "openml": [
                ("on a dataset with 100M+ rows and 500 features", "large_scale"),
                ("with strict fairness constraints (demographic parity < 0.05)", "fairness"),
                ("that must run inference in under 10ms on CPU", "fast_inference"),
                ("with full explainability (SHAP values for every prediction)", "explainable"),
                ("on streaming data with concept drift detection", "streaming"),
                ("with differential privacy guarantees (epsilon=1.0)", "private"),
                ("that must work on edge devices (< 50MB model size)", "edge_deploy"),
                ("with automated retraining pipeline on data drift", "auto_retrain"),
                ("handling heavily imbalanced classes (1:1000 ratio)", "imbalanced"),
                ("with A/B test framework for model comparison", "ab_testing"),
            ],
            "openfw": [
                ("for a Cortex-M0 with only 32KB flash and 8KB RAM", "tiny_mcu"),
                ("that must meet ASIL-D automotive safety requirements", "asil_d"),
                ("with over-the-air (OTA) firmware update support", "ota_update"),
                ("running on bare metal with no RTOS", "bare_metal"),
                ("with full MISRA-C:2012 compliance required", "misra_full"),
                ("targeting sub-microsecond interrupt latency", "realtime"),
                ("with dual-redundant failover architecture", "redundant"),
                ("that must operate in -40°C to +125°C range", "extreme_temp"),
                ("with encrypted boot chain and secure element", "secure_boot"),
                ("meeting IEC 62304 Class C safety requirements", "safety_critical"),
            ],
            "openeda": [
                ("for a 12-layer HDI PCB with 0.1mm trace/space", "hdi"),
                ("that must pass MIL-STD-810G environmental testing", "mil_spec"),
                ("with controlled impedance for 10Gbps differential pairs", "high_speed"),
                ("using only automotive-grade components (AEC-Q100)", "automotive"),
                ("with full thermal analysis and heatsink design", "thermal"),
                ("targeting IPC Class 3 reliability standards", "ipc_class3"),
                ("for a flex-rigid PCB with 3 flex zones", "flex_rigid"),
                ("with EMC pre-compliance analysis built in", "emc_ready"),
                ("using exotic materials (Rogers 4003C, Isola I-Speed)", "exotic_mat"),
                ("that must fit in a 10mm × 10mm footprint", "miniature"),
            ],
            "opensim": [
                ("with Monte Carlo analysis across 1000 process corners", "monte_carlo"),
                ("including full thermal simulation at 85°C junction temp", "thermal_sim"),
                ("with EMI/EMC spectral analysis up to 6GHz", "emi_analysis"),
                ("targeting signal integrity for DDR5 at 4800MT/s", "ddr5_si"),
                ("with power integrity analysis including PDN impedance", "power_integrity"),
                ("using mixed-signal simulation (analog + digital)", "mixed_signal"),
                ("with radiation hardness analysis for space applications", "rad_hard"),
                ("including aging/reliability simulation over 20-year lifetime", "aging"),
                ("with cross-domain coupling analysis (thermal-electrical)", "multi_physics"),
                ("targeting automotive SPICE Level 2 compliance", "auto_spice"),
            ],
            "opendoc": [
                ("for FDA 510(k) premarket notification submission", "fda_510k"),
                ("following ISO 14971 risk management process", "iso_14971"),
                ("for a CE marking technical file (MDR 2017/745)", "ce_marking"),
                ("targeting CMMI Level 3 process documentation", "cmmi_l3"),
                ("with full traceability matrix from requirements to tests", "traceability"),
                ("for a SOC 2 Type II audit evidence package", "soc2"),
                ("following IEEE 830 SRS format with formal methods", "ieee_830"),
                ("for HIPAA compliance documentation package", "hipaa"),
                ("with multi-language localization for 10 markets", "localized"),
                ("targeting automotive ASPICE Level 3 documentation", "aspice"),
            ],
            "opendesign": [
                ("meeting WCAG 2.2 AAA accessibility standards", "wcag_aaa"),
                ("for a kiosk with only touch input (no keyboard)", "kiosk"),
                ("supporting RTL languages (Arabic, Hebrew) natively", "rtl_native"),
                ("with dark mode, high contrast, and reduced motion variants", "a11y_variants"),
                ("for elderly users (min 18px font, high contrast ratios)", "senior_ux"),
                ("that works offline-first with sync indicators", "offline_first"),
                ("with voice control as primary interaction method", "voice_ui"),
                ("for a 320px smartwatch screen", "smartwatch"),
                ("with real-time collaboration (Figma-like cursors)", "collaborative"),
                ("following Material Design 3 with custom theme", "material3"),
            ],
            "openbrowser": [
                ("on a single-page application with client-side routing", "spa"),
                ("with strict Content Security Policy (no inline scripts)", "strict_csp"),
                ("testing across 3 viewports (mobile, tablet, desktop)", "responsive"),
                ("with authentication via OAuth/SSO providers", "sso_auth"),
                ("on a PWA with offline mode and service workers", "pwa"),
                ("with real-time WebSocket features requiring sync testing", "realtime"),
                ("on an internationalized app with RTL language support", "i18n_rtl"),
                ("with strict WCAG 2.2 AAA accessibility requirements", "wcag_aaa"),
                ("behind a CDN with aggressive caching (test cache invalidation)", "cdn_cached"),
                ("on a micro-frontend architecture with 5 independently deployed modules", "microfrontend"),
            ],
            "openstrategy": [
                ("for a pre-seed startup with $0 marketing budget", "bootstrapped"),
                ("entering a market dominated by 3 incumbents", "red_ocean"),
                ("for a B2B2C marketplace with network effects", "marketplace"),
                ("requiring regulatory approval in 5+ jurisdictions", "multi_regulatory"),
                ("with a freemium model targeting 2% conversion", "freemium"),
                ("for a hardware+software product with 18-month dev cycle", "hw_sw_combo"),
                ("targeting enterprise customers with 12-month sales cycles", "enterprise_sales"),
                ("in a market undergoing rapid regulatory change", "regulatory_flux"),
                ("for a product requiring FDA + CE + TGA approvals", "global_regulatory"),
                ("with a land-and-expand strategy in a saturated market", "land_expand"),
            ],
        }

        SCALE_MODIFIERS = [
            ("at startup scale (1 engineer, MVP)", "startup"),
            ("at growth scale (10-person team, Series A)", "growth"),
            ("at enterprise scale (100+ engineers, multi-region)", "enterprise"),
            ("at hyperscale (1000+ services, global deployment)", "hyperscale"),
            ("as an open-source project with community contributors", "open_source"),
        ]

        domains = [domain] if domain else list(VARIANT_AXES.keys())
        generated_count = 0

        for dom in domains:
            seeds = self.get_for_domain(dom)
            original_seeds = [s for s in seeds if not s.seed_id]
            if not original_seeds:
                continue

            constraints = CONSTRAINT_MODIFIERS.get(dom, CONSTRAINT_MODIFIERS.get("openswe", []))

            for seed in original_seeds:
                if generated_count >= target_count:
                    break

                for diff in DIFFICULTY_LEVELS:
                    if diff == seed.difficulty:
                        continue  # Skip same difficulty as original

                    for constraint_desc, constraint_tag in constraints:
                        if generated_count >= target_count:
                            break

                        # Template: seed description + constraint + difficulty
                        variant_desc = (
                            f"{seed.description}\n\n"
                            f"Additional constraint: {constraint_desc}"
                        )
                        variant_criteria = list(seed.acceptance_criteria) + [
                            f"Meets {constraint_tag} requirements"
                        ]
                        variant_id = self._make_id(
                            dom, f"{seed.id}_{diff}_{constraint_tag}"
                        )

                        if variant_id in self._exercises:
                            continue

                        ex = Exercise(
                            id=variant_id,
                            domain=dom,
                            skill=seed.skill,
                            title=f"{seed.title} ({constraint_tag}, {diff})",
                            description=variant_desc,
                            difficulty=diff,
                            tags=list(seed.tags) + [constraint_tag, diff],
                            acceptance_criteria=variant_criteria,
                            task_type=seed.task_type,
                            seed_id=seed.id,
                            variant_axis=constraint_tag,
                        )
                        self._register(ex)
                        self._save_exercise(ex)
                        generated_count += 1

                    # Also generate scale variants for intermediate+ difficulty
                    for scale_desc, scale_tag in SCALE_MODIFIERS:
                        if generated_count >= target_count:
                            break

                        variant_desc = (
                            f"{seed.description}\n\n"
                            f"Scale context: {scale_desc}"
                        )
                        variant_id = self._make_id(
                            dom, f"{seed.id}_{seed.difficulty}_{scale_tag}"
                        )
                        if variant_id in self._exercises:
                            continue

                        ex = Exercise(
                            id=variant_id,
                            domain=dom,
                            skill=seed.skill,
                            title=f"{seed.title} ({scale_tag})",
                            description=variant_desc,
                            difficulty=seed.difficulty,
                            tags=list(seed.tags) + [scale_tag],
                            acceptance_criteria=list(seed.acceptance_criteria) + [
                                f"Appropriate for {scale_tag} context"
                            ],
                            task_type=seed.task_type,
                            seed_id=seed.id,
                            variant_axis=scale_tag,
                        )
                        self._register(ex)
                        self._save_exercise(ex)
                        generated_count += 1

            self.logger.info(
                "Template variants for %s: %d exercises total",
                dom, len(self._domain_index.get(dom, [])),
            )

        self.logger.info(
            "Template generation complete: %d new variants (%d total exercises)",
            generated_count, len(self._exercises),
        )
        return generated_count

    # ── Stats ────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Catalog statistics."""
        total = len(self._exercises)
        seeds = sum(1 for ex in self._exercises.values() if not ex.seed_id)
        variants = total - seeds
        domains = {}
        for domain, ids in self._domain_index.items():
            difficulties = {}
            for eid in ids:
                ex = self._exercises.get(eid)
                if ex:
                    difficulties[ex.difficulty] = difficulties.get(ex.difficulty, 0) + 1
            domains[domain] = {"total": len(ids), "by_difficulty": difficulties}

        return {
            "total_exercises": total,
            "seed_exercises": seeds,
            "generated_variants": variants,
            "domains": domains,
            "variant_axes": {d: len(axes) for d, axes in VARIANT_AXES.items()},
        }


# Module-level singleton
exercise_catalog = ExerciseCatalog()
