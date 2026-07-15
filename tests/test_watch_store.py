"""Unit tests for the WatchStore — durable, idempotent watcher state.

These prove the "never lose a comment / never rework it twice" guarantee and the
single-writer lease that stops the Pi daemon and a desktop watcher double-acting.
"""

from __future__ import annotations

import pytest

from src.core.watch_store import WatchStore

pytestmark = pytest.mark.unit


def _store(tmp_path):
    return WatchStore(str(tmp_path / "watch.db"))


# --------------------------------------------------------------------------- #
# Idempotent comment handling
# --------------------------------------------------------------------------- #
def test_handled_is_false_until_marked(tmp_path):
    s = _store(tmp_path)
    assert s.handled("mr1", "c1") is False
    s.mark_handled("mr1", "c1")
    assert s.handled("mr1", "c1") is True


def test_mark_handled_is_idempotent(tmp_path):
    s = _store(tmp_path)
    s.mark_handled("mr1", "c1")
    s.mark_handled("mr1", "c1")  # must not raise on the PK conflict
    assert s.handled("mr1", "c1") is True


def test_handled_is_scoped_per_mr_and_comment(tmp_path):
    s = _store(tmp_path)
    s.mark_handled("mr1", "c1")
    assert s.handled("mr1", "c2") is False
    assert s.handled("mr2", "c1") is False


def test_state_survives_a_fresh_store_instance(tmp_path):
    # The durability guarantee: a "restarted" process (new WatchStore on the same
    # file) still sees what the previous one handled.
    _store(tmp_path).mark_handled("mr1", "c1")
    assert _store(tmp_path).handled("mr1", "c1") is True


# --------------------------------------------------------------------------- #
# Cursor
# --------------------------------------------------------------------------- #
def test_cursor_defaults_and_bump(tmp_path):
    s = _store(tmp_path)
    assert s.get_cursor("mr1") == {"rework_count": 0, "last_decision": ""}
    assert s.bump_rework("mr1") == 1
    assert s.bump_rework("mr1") == 2
    s.set_decision("mr1", "CHANGES_REQUESTED")
    cur = s.get_cursor("mr1")
    assert cur["rework_count"] == 2
    assert cur["last_decision"] == "CHANGES_REQUESTED"


# --------------------------------------------------------------------------- #
# Single-writer lease
# --------------------------------------------------------------------------- #
def test_lease_acquire_and_contention(tmp_path):
    s = _store(tmp_path)
    assert s.acquire("mr1", "daemon") is True
    # same owner re-acquires fine
    assert s.acquire("mr1", "daemon") is True
    # a different owner is blocked while the lease is live
    assert s.acquire("mr1", "desktop") is False


def test_lease_release_frees_it(tmp_path):
    s = _store(tmp_path)
    assert s.acquire("mr1", "daemon") is True
    s.release("mr1", "daemon")
    assert s.acquire("mr1", "desktop") is True


def test_expired_lease_can_be_taken_over(tmp_path):
    s = _store(tmp_path)
    # ttl=0 → already-expired lease; another owner may take it.
    assert s.acquire("mr1", "daemon", ttl_seconds=0) is True
    assert s.acquire("mr1", "desktop") is True


def test_release_only_by_holder(tmp_path):
    s = _store(tmp_path)
    s.acquire("mr1", "daemon")
    s.release("mr1", "desktop")  # not the holder — no-op
    assert s.acquire("mr1", "desktop") is False  # daemon still holds it
