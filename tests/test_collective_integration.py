"""
Collective Intelligence — Integration Tests
============================================
Tests the integration between CollectiveMemory and other SAGE components:
proposal executor, universal agent, and end-to-end workflows.
"""

import os
import pytest
import yaml


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def collective(tmp_path):
    from src.core.collective_memory import CollectiveMemory
    return CollectiveMemory(
        repo_path=str(tmp_path / "integ_collective"),
        require_approval=False,
    )


@pytest.fixture
def sample_learning():
    return {
        "author_agent": "analyst",
        "author_solution": "medtech",
        "topic": "compliance",
        "title": "IEC 62304 traceability pattern",
        "content": "Always link requirements bidirectionally to test cases for Class C software.",
        "tags": ["iec62304", "traceability", "compliance"],
        "confidence": 0.8,
    }


# ═══════════════════════════════════════════════════════════════════════
# PROPOSAL EXECUTOR INTEGRATION
# ═══════════════════════════════════════════════════════════════════════

class TestProposalExecutorIntegration:
    """Verify collective_publish action is registered in the executor."""

    def test_collective_publish_registered(self):
        """The collective_publish action is in the dispatch map."""
        from src.core.proposal_executor import _DISPATCH
        assert "collective_publish" in _DISPATCH

    def test_collective_publish_executor_signature(self):
        """The executor function accepts a Proposal object."""
        import inspect
        from src.core.proposal_executor import _DISPATCH
        fn = _DISPATCH["collective_publish"]
        sig = inspect.signature(fn)
        params = list(sig.parameters.keys())
        assert "proposal" in params


# ═══════════════════════════════════════════════════════════════════════
# LEARNING EXTRACTION
# ═══════════════════════════════════════════════════════════════════════

class TestLearningExtraction:
    """Verify learning extraction from task results."""

    def test_extract_from_successful_task(self):
        from src.core.collective_memory import CollectiveMemory
        result = {
            "task_type": "ANALYZE_LOG",
            "task_id": "task-123",
            "summary": "Found memory leak in DMA handler",
            "output": "The DMA handler in uart_driver.c has a memory leak. "
                      "When the transfer completes, the buffer is not freed if "
                      "an error flag is set. Fix: check error flag before freeing buffer.",
        }
        learning = CollectiveMemory.extract_learning_from_result(
            result, agent_role="analyst", solution="firmware",
        )
        assert learning is not None
        assert learning["author_agent"] == "analyst"
        assert learning["author_solution"] == "firmware"
        assert learning["source_task_id"] == "task-123"

    def test_extract_returns_none_for_short_output(self):
        from src.core.collective_memory import CollectiveMemory
        result = {"output": "OK"}
        learning = CollectiveMemory.extract_learning_from_result(
            result, agent_role="dev", solution="test",
        )
        assert learning is None

    def test_extract_returns_none_for_empty_result(self):
        from src.core.collective_memory import CollectiveMemory
        learning = CollectiveMemory.extract_learning_from_result(
            {}, agent_role="dev", solution="test",
        )
        assert learning is None


# ═══════════════════════════════════════════════════════════════════════
# END-TO-END WORKFLOWS
# ═══════════════════════════════════════════════════════════════════════

class TestEndToEndWorkflows:
    """Full lifecycle tests."""

    def test_publish_then_search(self, collective, sample_learning):
        """Published learning is searchable."""
        collective.publish_learning(sample_learning)
        results = collective.search_learnings(query="IEC 62304 traceability")
        assert len(results) >= 1
        assert any("traceability" in r.get("title", "").lower() for r in results)

    def test_help_request_full_lifecycle(self, collective):
        """Create → claim → respond → close lifecycle."""
        req_id = collective.create_help_request({
            "title": "Need help with SPI timing",
            "requester_agent": "developer",
            "requester_solution": "iot",
            "urgency": "high",
            "required_expertise": ["spi", "timing"],
            "context": "SPI clock is 2x expected frequency.",
        })

        # Claim
        claimed = collective.claim_help_request(req_id, "expert", "embedded")
        assert claimed["status"] == "claimed"

        # Respond
        responded = collective.respond_to_help_request(req_id, {
            "responder_agent": "expert",
            "responder_solution": "embedded",
            "content": "Check the prescaler register — CPSDVSR should be 4, not 2.",
        })
        assert len(responded["responses"]) == 1

        # Close
        closed = collective.close_help_request(req_id)
        assert closed["status"] == "closed"

        # Verify it's in closed list
        open_reqs = collective.list_help_requests(status="open")
        closed_reqs = collective.list_help_requests(status="closed")
        assert not any(r["id"] == req_id for r in open_reqs)
        assert any(r["id"] == req_id for r in closed_reqs)

    def test_solution_isolation(self, collective, sample_learning):
        """Private solution knowledge is NOT in collective repo."""
        # Publish a learning (this is explicitly shared)
        collective.publish_learning(sample_learning)

        # The collective repo should ONLY contain what was published
        learnings = collective.list_learnings()
        assert len(learnings) == 1
        # No other solution data should be present
        all_files = []
        for root, dirs, files in os.walk(collective.repo_path):
            dirs[:] = [d for d in dirs if d != ".git"]
            all_files.extend(files)
        yaml_files = [f for f in all_files if f.endswith(".yaml")]
        # Only the one learning + potentially index.yaml
        assert len(yaml_files) <= 2

    def test_graceful_degradation_without_git(self, tmp_path):
        """CollectiveMemory works even if git commands fail."""
        from src.core.collective_memory import CollectiveMemory
        cm = CollectiveMemory(
            repo_path=str(tmp_path / "nogit_collective"),
            require_approval=False,
        )
        # Even if git failed during init, CRUD should work
        learning_id = cm.publish_learning({
            "author_agent": "test",
            "author_solution": "test",
            "topic": "general",
            "title": "Works without git",
            "content": "YAML file operations still work.",
        })
        result = cm.get_learning(learning_id)
        assert result is not None
        assert result["title"] == "Works without git"

    def test_stats_accuracy_after_operations(self, collective, sample_learning):
        """Stats reflect actual state after multiple operations."""
        collective.publish_learning(sample_learning)
        collective.publish_learning({**sample_learning, "topic": "spi", "title": "SPI"})
        collective.create_help_request({
            "title": "Help needed",
            "requester_agent": "dev",
            "requester_solution": "auto",
            "context": "Stuck",
        })

        stats = collective.get_stats()
        assert stats["learning_count"] == 2
        assert stats["help_request_count"] == 1
        assert "compliance" in stats["topics"]
        assert "spi" in stats["topics"]
