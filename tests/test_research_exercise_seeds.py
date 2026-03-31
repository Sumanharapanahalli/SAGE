"""
SAGE Framework — AutoResearch Exercise Seeds TDD Tests
========================================================
Tests for the autoresearch exercise domain in the seed catalog.

Exercises cover:
  - Hyperparameter optimization (learning rate, batch size, schedules)
  - Architecture search (model depth, width, attention heads)
  - Training strategies (regularization, data augmentation, curriculum)
  - Loss function design (custom losses, multi-objective)
  - Data pipeline optimization (preprocessing, sampling)
  - Evaluation methodology (metrics, cross-validation)
  - Experiment reproducibility (seeds, checkpointing)
  - Resource efficiency (memory, compute, mixed precision)
"""

import pytest

pytestmark = pytest.mark.unit


class TestResearchSeedCatalog:
    """Verify autoresearch exercise seeds exist and are well-formed."""

    def test_autoresearch_seeds_exist(self):
        from src.core.exercise_seeds import get_all_seeds
        seeds = get_all_seeds()
        assert "autoresearch" in seeds

    def test_seed_count_minimum(self):
        """Should have at least 60 seed exercises."""
        from src.core.exercise_seeds import get_all_seeds
        seeds = get_all_seeds()["autoresearch"]
        assert len(seeds) >= 60

    def test_all_difficulties_represented(self):
        from src.core.exercise_seeds import get_all_seeds
        seeds = get_all_seeds()["autoresearch"]
        difficulties = {s["difficulty"] for s in seeds}
        assert "beginner" in difficulties
        assert "intermediate" in difficulties
        assert "advanced" in difficulties
        assert "expert" in difficulties

    def test_each_seed_has_required_fields(self):
        from src.core.exercise_seeds import get_all_seeds
        seeds = get_all_seeds()["autoresearch"]
        for seed in seeds:
            assert "title" in seed, f"Missing title in seed: {seed}"
            assert "difficulty" in seed, f"Missing difficulty in seed: {seed}"
            assert "tags" in seed, f"Missing tags in seed: {seed}"
            assert "description" in seed, f"Missing description in seed: {seed}"
            assert "acceptance_criteria" in seed, f"Missing criteria in seed: {seed}"
            assert len(seed["acceptance_criteria"]) >= 2, f"Need >=2 criteria: {seed['title']}"

    def test_tags_are_lists(self):
        from src.core.exercise_seeds import get_all_seeds
        seeds = get_all_seeds()["autoresearch"]
        for seed in seeds:
            assert isinstance(seed["tags"], list)
            assert len(seed["tags"]) >= 1

    def test_descriptions_are_substantial(self):
        """Descriptions should be detailed enough for an agent to act on."""
        from src.core.exercise_seeds import get_all_seeds
        seeds = get_all_seeds()["autoresearch"]
        for seed in seeds:
            assert len(seed["description"]) >= 50, f"Description too short: {seed['title']}"

    def test_difficulty_distribution(self):
        """Roughly balanced across difficulties."""
        from src.core.exercise_seeds import get_all_seeds
        seeds = get_all_seeds()["autoresearch"]
        counts = {}
        for s in seeds:
            d = s["difficulty"]
            counts[d] = counts.get(d, 0) + 1
        for diff in ["beginner", "intermediate", "advanced", "expert"]:
            assert counts.get(diff, 0) >= 10, f"Too few {diff} exercises: {counts.get(diff, 0)}"

    def test_topic_coverage(self):
        """Seeds should cover key research domains."""
        from src.core.exercise_seeds import get_all_seeds
        seeds = get_all_seeds()["autoresearch"]
        all_tags = set()
        for s in seeds:
            all_tags.update(s["tags"])
        expected_topics = ["hyperparameter", "architecture", "training", "evaluation"]
        for topic in expected_topics:
            assert any(topic in tag for tag in all_tags), f"Missing topic coverage: {topic}"

    def test_task_types_set(self):
        """Each seed should have a task_type."""
        from src.core.exercise_seeds import get_all_seeds
        seeds = get_all_seeds()["autoresearch"]
        for seed in seeds:
            assert seed.get("task_type", "") != "", f"Missing task_type: {seed['title']}"

    def test_seeds_have_metric_info(self):
        """Research seeds should specify metric_name and direction."""
        from src.core.exercise_seeds import get_all_seeds
        seeds = get_all_seeds()["autoresearch"]
        for seed in seeds:
            assert "metric_name" in seed, f"Missing metric_name: {seed['title']}"
            assert "metric_direction" in seed, f"Missing metric_direction: {seed['title']}"
            assert seed["metric_direction"] in ("lower", "higher"), \
                f"Invalid direction: {seed['metric_direction']}"
