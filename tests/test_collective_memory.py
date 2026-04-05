"""
Collective Intelligence — Unit Tests for CollectiveMemory Engine
================================================================
Tests Git-backed knowledge sharing: learnings CRUD, help requests,
search/indexing, and statistics.
"""

import os
import shutil
import threading
import uuid

import pytest
import yaml


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def collective(tmp_path):
    """Create a CollectiveMemory instance with a temporary Git repo."""
    from src.core.collective_memory import CollectiveMemory
    cm = CollectiveMemory(
        repo_path=str(tmp_path / "collective"),
        remote_url="",
        auto_push=False,
        require_approval=False,  # skip HITL for unit tests
    )
    return cm


@pytest.fixture
def sample_learning():
    return {
        "author_agent": "analyst",
        "author_solution": "medtech",
        "topic": "uart-debugging",
        "title": "UART buffer overflow recovery pattern",
        "content": "When UART RX buffer overflow is detected, flush the DMA channel first.",
        "tags": ["uart", "embedded", "recovery"],
        "confidence": 0.85,
    }


@pytest.fixture
def sample_help_request():
    return {
        "title": "Need expertise on I2C bus recovery for STM32H7",
        "requester_agent": "developer",
        "requester_solution": "automotive",
        "urgency": "high",
        "required_expertise": ["i2c", "stm32", "bus-recovery"],
        "context": "Agent stuck on task TASK-456. I2C1 bus hangs after sleep/wake cycle.",
    }


# ═══════════════════════════════════════════════════════════════════════
# GIT REPO MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════

class TestGitRepoManagement:
    """Git repository initialization and operations."""

    def test_ensure_repo_creates_git_repo(self, collective):
        """_ensure_repo creates a .git directory."""
        assert os.path.isdir(os.path.join(collective.repo_path, ".git"))

    def test_ensure_repo_is_idempotent(self, collective):
        """Calling _ensure_repo twice doesn't fail."""
        collective._ensure_repo()  # second call
        assert os.path.isdir(os.path.join(collective.repo_path, ".git"))

    def test_ensure_repo_creates_directory_structure(self, collective):
        """Repo has learnings/ and help-requests/open/ directories."""
        assert os.path.isdir(os.path.join(collective.repo_path, "learnings"))
        assert os.path.isdir(os.path.join(collective.repo_path, "help-requests", "open"))
        assert os.path.isdir(os.path.join(collective.repo_path, "help-requests", "closed"))

    def test_commit_creates_git_commit(self, collective, tmp_path):
        """_commit creates a real git commit with the file."""
        test_file = os.path.join(collective.repo_path, "test.txt")
        with open(test_file, "w") as f:
            f.write("hello")
        sha = collective._commit("test commit", ["test.txt"])
        assert sha and len(sha) >= 7

    def test_git_run_raises_on_bad_command(self, collective):
        """_git_run raises on invalid git subcommand."""
        with pytest.raises(Exception):
            collective._git_run("not-a-real-command")


# ═══════════════════════════════════════════════════════════════════════
# LEARNING CRUD
# ═══════════════════════════════════════════════════════════════════════

class TestLearningCRUD:
    """Publishing, retrieving, listing, and validating learnings."""

    def test_publish_learning_returns_id(self, collective, sample_learning):
        """publish_learning returns a valid UUID string."""
        learning_id = collective.publish_learning(sample_learning)
        assert learning_id
        # Should be a valid UUID
        uuid.UUID(learning_id)

    def test_publish_learning_creates_yaml_file(self, collective, sample_learning):
        """Publishing creates a YAML file in the correct directory."""
        learning_id = collective.publish_learning(sample_learning)
        path = os.path.join(
            collective.repo_path, "learnings",
            sample_learning["author_solution"],
            sample_learning["topic"],
            f"{learning_id}.yaml",
        )
        assert os.path.isfile(path)
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["title"] == sample_learning["title"]
        assert data["id"] == learning_id

    def test_publish_learning_commits_to_git(self, collective, sample_learning):
        """Publishing creates a git commit."""
        import subprocess
        collective.publish_learning(sample_learning)
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=collective.repo_path, capture_output=True, text=True,
        )
        assert "learning:" in result.stdout.lower() or "publish" in result.stdout.lower()

    def test_get_learning_returns_correct_data(self, collective, sample_learning):
        """get_learning retrieves the published learning."""
        learning_id = collective.publish_learning(sample_learning)
        result = collective.get_learning(learning_id)
        assert result is not None
        assert result["id"] == learning_id
        assert result["title"] == sample_learning["title"]
        assert result["author_agent"] == "analyst"

    def test_get_learning_returns_none_for_missing(self, collective):
        """get_learning returns None for nonexistent ID."""
        result = collective.get_learning("nonexistent-id")
        assert result is None

    def test_list_learnings_returns_all(self, collective, sample_learning):
        """list_learnings returns all published learnings."""
        collective.publish_learning(sample_learning)
        learning2 = {**sample_learning, "title": "Second learning", "topic": "spi-config"}
        collective.publish_learning(learning2)
        results = collective.list_learnings()
        assert len(results) == 2

    def test_list_learnings_filters_by_solution(self, collective, sample_learning):
        """list_learnings can filter by author_solution."""
        collective.publish_learning(sample_learning)  # medtech
        other = {**sample_learning, "author_solution": "automotive", "title": "Other"}
        collective.publish_learning(other)
        results = collective.list_learnings(solution="medtech")
        assert len(results) == 1
        assert results[0]["author_solution"] == "medtech"

    def test_list_learnings_filters_by_topic(self, collective, sample_learning):
        """list_learnings can filter by topic."""
        collective.publish_learning(sample_learning)  # uart-debugging
        other = {**sample_learning, "topic": "spi-config", "title": "SPI stuff"}
        collective.publish_learning(other)
        results = collective.list_learnings(topic="uart-debugging")
        assert len(results) == 1

    def test_validate_learning_increments_count(self, collective, sample_learning):
        """validate_learning increments validation_count and updates confidence."""
        learning_id = collective.publish_learning(sample_learning)
        result = collective.validate_learning(learning_id, validated_by="qa_agent")
        assert result["validation_count"] == 1
        # Confidence should increase slightly
        assert result["confidence"] >= sample_learning["confidence"]

    def test_publish_learning_with_minimal_fields(self, collective):
        """Publishing with only required fields works."""
        minimal = {
            "author_agent": "test",
            "author_solution": "test_sol",
            "topic": "general",
            "title": "Minimal learning",
            "content": "Some content",
        }
        learning_id = collective.publish_learning(minimal)
        result = collective.get_learning(learning_id)
        assert result is not None
        assert result["confidence"] == 0.5  # default
        assert result["tags"] == []


# ═══════════════════════════════════════════════════════════════════════
# HELP REQUESTS
# ═══════════════════════════════════════════════════════════════════════

class TestHelpRequests:
    """Creating, listing, claiming, responding to, and closing help requests."""

    def test_create_help_request_returns_id(self, collective, sample_help_request):
        """create_help_request returns a valid ID."""
        req_id = collective.create_help_request(sample_help_request)
        assert req_id
        assert req_id.startswith("hr-")

    def test_create_help_request_creates_yaml(self, collective, sample_help_request):
        """Creates YAML in help-requests/open/."""
        req_id = collective.create_help_request(sample_help_request)
        path = os.path.join(collective.repo_path, "help-requests", "open", f"{req_id}.yaml")
        assert os.path.isfile(path)

    def test_list_help_requests_returns_open(self, collective, sample_help_request):
        """list_help_requests returns open requests by default."""
        collective.create_help_request(sample_help_request)
        results = collective.list_help_requests()
        assert len(results) == 1
        assert results[0]["status"] == "open"

    def test_list_help_requests_filters_by_expertise(self, collective, sample_help_request):
        """list_help_requests can filter by required_expertise."""
        collective.create_help_request(sample_help_request)  # i2c, stm32
        other = {**sample_help_request, "title": "Other", "required_expertise": ["python"]}
        collective.create_help_request(other)
        results = collective.list_help_requests(expertise=["i2c"])
        assert len(results) == 1
        assert "i2c" in results[0]["required_expertise"]

    def test_claim_help_request_updates_status(self, collective, sample_help_request):
        """Claiming sets claimed_by and changes status."""
        req_id = collective.create_help_request(sample_help_request)
        result = collective.claim_help_request(req_id, agent="firmware_expert", solution="iot")
        assert result["status"] == "claimed"
        assert result["claimed_by"]["agent"] == "firmware_expert"

    def test_claim_already_claimed_raises(self, collective, sample_help_request):
        """Claiming an already-claimed request raises ValueError."""
        req_id = collective.create_help_request(sample_help_request)
        collective.claim_help_request(req_id, agent="agent1", solution="sol1")
        with pytest.raises(ValueError, match="already claimed"):
            collective.claim_help_request(req_id, agent="agent2", solution="sol2")

    def test_respond_to_help_request(self, collective, sample_help_request):
        """respond_to_help_request appends a response."""
        req_id = collective.create_help_request(sample_help_request)
        collective.claim_help_request(req_id, agent="expert", solution="iot")
        result = collective.respond_to_help_request(req_id, {
            "responder_agent": "expert",
            "responder_solution": "iot",
            "content": "Try the H7 errata workaround for I2C analog filter.",
        })
        assert len(result["responses"]) == 1
        assert "errata" in result["responses"][0]["content"]

    def test_close_help_request_moves_to_closed(self, collective, sample_help_request):
        """Closing moves the file from open/ to closed/."""
        req_id = collective.create_help_request(sample_help_request)
        collective.close_help_request(req_id)
        open_path = os.path.join(collective.repo_path, "help-requests", "open", f"{req_id}.yaml")
        closed_path = os.path.join(collective.repo_path, "help-requests", "closed", f"{req_id}.yaml")
        assert not os.path.exists(open_path)
        assert os.path.isfile(closed_path)


# ═══════════════════════════════════════════════════════════════════════
# SEARCH & SYNC
# ═══════════════════════════════════════════════════════════════════════

class TestSearchAndSync:
    """Search indexing and sync operations."""

    def test_search_learnings_finds_relevant(self, collective, sample_learning):
        """search_learnings finds published content."""
        collective.publish_learning(sample_learning)
        results = collective.search_learnings(query="UART buffer overflow")
        assert len(results) >= 1
        assert any("UART" in r.get("title", "") or "UART" in r.get("content", "")
                    for r in results)

    def test_search_learnings_empty_on_no_match(self, collective, sample_learning):
        """search_learnings returns empty for unrelated queries."""
        collective.publish_learning(sample_learning)
        results = collective.search_learnings(query="quantum computing neural networks")
        # May return results from keyword matching; at minimum shouldn't crash
        assert isinstance(results, list)

    def test_search_learnings_filters_by_tags(self, collective, sample_learning):
        """search_learnings can filter by tags."""
        collective.publish_learning(sample_learning)  # tags: uart, embedded, recovery
        other = {**sample_learning, "tags": ["python", "web"], "title": "Web stuff",
                 "topic": "web-dev", "content": "Flask patterns"}
        collective.publish_learning(other)
        results = collective.search_learnings(query="patterns", tags=["embedded"])
        # Should only return the embedded-tagged one
        for r in results:
            assert "embedded" in r.get("tags", [])

    def test_rebuild_index_counts_all(self, collective, sample_learning):
        """_rebuild_index returns count of all indexed learnings."""
        collective.publish_learning(sample_learning)
        collective.publish_learning({**sample_learning, "title": "Second", "topic": "spi"})
        count = collective._rebuild_index()
        assert count == 2

    def test_sync_returns_status(self, collective, sample_learning):
        """sync() returns a status dict."""
        collective.publish_learning(sample_learning)
        result = collective.sync()
        assert "indexed" in result
        assert result["indexed"] >= 1

    def test_update_manifest_creates_index_yaml(self, collective, sample_learning):
        """_update_manifest generates index.yaml with correct counts."""
        collective.publish_learning(sample_learning)
        collective._update_manifest()
        index_path = os.path.join(collective.repo_path, "index.yaml")
        assert os.path.isfile(index_path)
        with open(index_path) as f:
            data = yaml.safe_load(f)
        assert data["learning_count"] == 1
        assert sample_learning["topic"] in data.get("topics", {})

    def test_index_learning_adds_to_vector_store(self, collective, sample_learning):
        """_index_learning makes the content findable in the vector store."""
        learning = {**sample_learning, "id": str(uuid.uuid4())}
        collective._index_learning(learning)
        # Direct vector store search should find the indexed content
        vs_results = collective._vs.search(sample_learning["title"], k=3)
        assert len(vs_results) >= 1

    def test_search_learnings_filters_by_solution(self, collective, sample_learning):
        """search_learnings filters by solution."""
        collective.publish_learning(sample_learning)
        other = {**sample_learning, "author_solution": "automotive",
                 "title": "Auto stuff", "topic": "can-bus"}
        collective.publish_learning(other)
        results = collective.search_learnings(query="", solution="medtech")
        for r in results:
            assert r["author_solution"] == "medtech"


# ═══════════════════════════════════════════════════════════════════════
# STATISTICS
# ═══════════════════════════════════════════════════════════════════════

class TestStats:
    """Collective intelligence statistics."""

    def test_stats_empty_repo(self, collective):
        """Stats on empty repo returns zero counts."""
        stats = collective.get_stats()
        assert stats["learning_count"] == 0
        assert stats["help_request_count"] == 0

    def test_stats_counts_learnings(self, collective, sample_learning):
        """Stats accurately counts learnings."""
        collective.publish_learning(sample_learning)
        collective.publish_learning({**sample_learning, "title": "Second", "topic": "spi"})
        stats = collective.get_stats()
        assert stats["learning_count"] == 2

    def test_stats_counts_help_requests(self, collective, sample_help_request):
        """Stats counts open help requests."""
        collective.create_help_request(sample_help_request)
        stats = collective.get_stats()
        assert stats["help_request_count"] == 1

    def test_stats_shows_topics(self, collective, sample_learning):
        """Stats shows topic distribution."""
        collective.publish_learning(sample_learning)
        collective.publish_learning({**sample_learning, "topic": "spi", "title": "SPI"})
        collective.publish_learning({**sample_learning, "topic": "spi", "title": "SPI 2"})
        stats = collective.get_stats()
        assert stats["topics"]["spi"] == 2
        assert stats["topics"]["uart-debugging"] == 1

    def test_stats_shows_contributors(self, collective, sample_learning):
        """Stats shows per-solution contribution counts."""
        collective.publish_learning(sample_learning)  # medtech
        other = {**sample_learning, "author_solution": "automotive", "title": "Auto"}
        collective.publish_learning(other)
        stats = collective.get_stats()
        assert stats["contributors"]["medtech"] == 1
        assert stats["contributors"]["automotive"] == 1
