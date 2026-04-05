"""Tests for BFTS tree search evaluator."""
import pytest

from src.core.tree_search import TreeSearchEvaluator, SearchNode


class TestSearchNode:
    def test_create_node(self):
        node = SearchNode(solution="print('hello')", score=0.5)
        assert node.solution == "print('hello')"
        assert node.score == 0.5
        assert node.children == []
        assert node.depth == 0

    def test_add_child(self):
        parent = SearchNode(solution="v1", score=0.3)
        child = parent.add_child("v2", 0.7)
        assert len(parent.children) == 1
        assert child.depth == 1
        assert child.parent is parent


class TestTreeSearchEvaluator:
    @pytest.fixture
    def evaluator(self):
        def scorer(solution: str) -> float:
            return len(solution) / 100.0  # longer = better (toy scorer)
        return TreeSearchEvaluator(scorer=scorer, max_depth=3, branching_factor=2)

    def test_evaluate_returns_best(self, evaluator):
        candidates = ["short", "a medium length solution", "this is the longest candidate solution by far"]
        best = evaluator.evaluate(candidates)
        assert best is not None
        assert best.score > 0

    def test_search_tree_has_depth(self, evaluator):
        candidates = ["a", "bb"]
        evaluator.evaluate(candidates)
        root = evaluator.root
        assert root is not None
        # At least some children should exist
        assert len(root.children) > 0

    def test_max_iterations_respected(self):
        def scorer(s: str) -> float:
            return 0.5
        ev = TreeSearchEvaluator(scorer=scorer, max_depth=2, branching_factor=2, max_iterations=3)
        ev.evaluate(["a", "b", "c"])
        assert ev.iterations <= 3

    def test_empty_candidates(self, evaluator):
        best = evaluator.evaluate([])
        assert best is None

    def test_pruning_keeps_top_k(self):
        scores = {}
        def scorer(s: str) -> float:
            return scores.get(s, 0.0)
        scores = {"a": 0.1, "b": 0.9, "c": 0.5}
        ev = TreeSearchEvaluator(scorer=scorer, max_depth=1, branching_factor=2)
        best = ev.evaluate(["a", "b", "c"])
        assert best.solution == "b"
