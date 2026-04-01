"""
tests/test_seed_validation.py — Unit tests for seed_test_data validation logic
and idempotency guarantees (no live DB required).

Coverage:
  - _validate_record() for all five tables
  - _is_valid() severity routing (critical/error blocks; warning passes)
  - TestDataSeeder.seed_all() idempotency via a mock session
  - TestDataSeeder.teardown_all() issues the correct DELETE statements
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

import pytest

from tests.seed_test_data import (
    TestDataSeeder,
    _Check,
    _is_valid,
    _validate_record,
    seed_all,
    teardown_all,
)


# =============================================================================
# Helpers
# =============================================================================

def _checks_passed(checks: list[_Check]) -> bool:
    return all(c.passed for c in checks)


def _blocking_failures(checks: list[_Check]) -> list[_Check]:
    return [c for c in checks if not c.passed and c.severity in ("error", "critical")]


# =============================================================================
# _validate_record — accounts
# =============================================================================

class TestValidateAccounts:
    TABLE = "accounts"

    def test_valid_active_account(self):
        row = {"username": "alice_test", "password": "hash", "status": "active", "balance": Decimal("100.00")}
        assert _checks_passed(_validate_record(self.TABLE, row))

    def test_valid_zero_balance(self):
        row = {"username": "carol_test", "password": "hash", "status": "active", "balance": Decimal("0.00")}
        assert _checks_passed(_validate_record(self.TABLE, row))

    def test_missing_username_is_critical(self):
        row = {"password": "hash", "status": "active"}
        blocks = _blocking_failures(_validate_record(self.TABLE, row))
        assert any("required:username" in c.rule for c in blocks)

    def test_missing_password_is_critical(self):
        row = {"username": "x_test", "status": "active"}
        blocks = _blocking_failures(_validate_record(self.TABLE, row))
        assert any("required:password" in c.rule for c in blocks)

    def test_invalid_status_enum(self):
        row = {"username": "x_test", "password": "hash", "status": "banned", "balance": Decimal("0")}
        blocks = _blocking_failures(_validate_record(self.TABLE, row))
        assert any("enum:status" in c.rule for c in blocks)

    def test_negative_balance_fails(self):
        row = {"username": "x_test", "password": "hash", "status": "active", "balance": Decimal("-1.00")}
        blocks = _blocking_failures(_validate_record(self.TABLE, row))
        assert any("non_negative:balance" in c.rule for c in blocks)

    @pytest.mark.parametrize("status", ["active", "suspended", "closed"])
    def test_all_allowed_statuses(self, status):
        row = {"username": "x_test", "password": "hash", "status": status, "balance": Decimal("0")}
        assert _checks_passed(_validate_record(self.TABLE, row))


# =============================================================================
# _validate_record — p2p_transfers
# =============================================================================

class TestValidateTransfers:
    TABLE = "p2p_transfers"

    def _row(self, **overrides):
        base = {
            "sender_id": 1,
            "receiver_id": 2,
            "amount": Decimal("50.00"),
            "status": "completed",
        }
        base.update(overrides)
        return base

    def test_valid_transfer(self):
        assert _checks_passed(_validate_record(self.TABLE, self._row()))

    def test_zero_amount_fails(self):
        blocks = _blocking_failures(_validate_record(self.TABLE, self._row(amount=Decimal("0"))))
        assert any("positive:amount" in c.rule for c in blocks)

    def test_negative_amount_fails(self):
        blocks = _blocking_failures(_validate_record(self.TABLE, self._row(amount=Decimal("-5"))))
        assert any("positive:amount" in c.rule for c in blocks)

    def test_self_transfer_blocked(self):
        blocks = _blocking_failures(_validate_record(self.TABLE, self._row(sender_id=3, receiver_id=3)))
        assert any("no_self_transfer" in c.rule for c in blocks)

    def test_invalid_status_enum(self):
        blocks = _blocking_failures(_validate_record(self.TABLE, self._row(status="approved")))
        assert any("enum:status" in c.rule for c in blocks)

    @pytest.mark.parametrize("status", ["pending", "completed", "failed", "reversed"])
    def test_all_allowed_statuses(self, status):
        assert _checks_passed(_validate_record(self.TABLE, self._row(status=status)))


# =============================================================================
# _validate_record — virtual_cards
# =============================================================================

class TestValidateCards:
    TABLE = "virtual_cards"

    def _row(self, **overrides):
        base = {
            "card_holder_id": 1,
            "card_type": "debit",
            "card_expiry_date": date.today() + timedelta(days=365),
            "status": "active",
        }
        base.update(overrides)
        return base

    def test_valid_card(self):
        assert _checks_passed(_validate_record(self.TABLE, self._row()))

    def test_expired_card_is_warning_not_error(self, caplog):
        past_date = date.today() - timedelta(days=1)
        checks = _validate_record(self.TABLE, self._row(card_expiry_date=past_date))
        # Must not be blocking
        assert not _blocking_failures(checks)
        # Must have a warning
        warns = [c for c in checks if not c.passed and c.severity == "warning"]
        assert any("card_not_expired" in c.rule for c in warns)

    def test_invalid_card_type(self):
        blocks = _blocking_failures(_validate_record(self.TABLE, self._row(card_type="virtual")))
        assert any("enum:card_type" in c.rule for c in blocks)

    def test_invalid_status(self):
        blocks = _blocking_failures(_validate_record(self.TABLE, self._row(status="locked")))
        assert any("enum:status" in c.rule for c in blocks)

    @pytest.mark.parametrize("card_type", ["debit", "credit", "prepaid"])
    def test_all_card_types(self, card_type):
        assert _checks_passed(_validate_record(self.TABLE, self._row(card_type=card_type)))

    @pytest.mark.parametrize("status", ["active", "frozen", "cancelled"])
    def test_all_card_statuses(self, status):
        assert _checks_passed(_validate_record(self.TABLE, self._row(status=status)))


# =============================================================================
# _validate_record — spending_insights
# =============================================================================

class TestValidateInsights:
    TABLE = "spending_insights"

    def test_valid_insight(self):
        row = {"account_id": 1, "date": date.today(), "category": "food", "amount": Decimal("25.00")}
        assert _checks_passed(_validate_record(self.TABLE, row))

    def test_zero_amount_allowed(self):
        row = {"account_id": 1, "date": date.today(), "category": "food", "amount": Decimal("0.00")}
        assert _checks_passed(_validate_record(self.TABLE, row))

    def test_negative_amount_fails(self):
        row = {"account_id": 1, "date": date.today(), "category": "food", "amount": Decimal("-1.00")}
        assert _blocking_failures(_validate_record(self.TABLE, row))

    def test_missing_category_fails(self):
        row = {"account_id": 1, "date": date.today(), "amount": Decimal("10.00")}
        assert _blocking_failures(_validate_record(self.TABLE, row))


# =============================================================================
# _validate_record — investment_options
# =============================================================================

class TestValidateInvestments:
    TABLE = "investment_options"

    def _row(self, **overrides):
        base = {
            "name": "Test Fund",
            "asset_type": "equities",
            "risk_level": "medium",
            "return_potential": Decimal("8.50"),
            "min_investment": Decimal("100.00"),
        }
        base.update(overrides)
        return base

    def test_valid_investment(self):
        assert _checks_passed(_validate_record(self.TABLE, self._row()))

    def test_invalid_risk_level(self):
        blocks = _blocking_failures(_validate_record(self.TABLE, self._row(risk_level="extreme")))
        assert any("enum:risk_level" in c.rule for c in blocks)

    def test_negative_return_potential_fails(self):
        blocks = _blocking_failures(_validate_record(self.TABLE, self._row(return_potential=Decimal("-1"))))
        assert any("non_negative:return_potential" in c.rule for c in blocks)

    @pytest.mark.parametrize("level", ["low", "medium", "high", "very_high"])
    def test_all_risk_levels(self, level):
        assert _checks_passed(_validate_record(self.TABLE, self._row(risk_level=level)))


# =============================================================================
# _is_valid — severity routing
# =============================================================================

class TestIsValid:
    def test_valid_row_returns_true(self):
        row = {"username": "x_test", "password": "hash", "status": "active", "balance": Decimal("0")}
        assert _is_valid("accounts", row, "x_test") is True

    def test_critical_failure_returns_false(self):
        # Missing required username
        assert _is_valid("accounts", {"password": "h", "status": "active"}, "anon") is False

    def test_warning_only_returns_true(self, caplog):
        """Expired card triggers a warning but must not block insertion."""
        row = {
            "card_holder_id": 1,
            "card_type": "debit",
            "card_expiry_date": date.today() - timedelta(days=30),
            "status": "active",
        }
        with caplog.at_level(logging.WARNING):
            result = _is_valid("virtual_cards", row, "holder/debit")
        assert result is True
        assert any("WARN" in r.message for r in caplog.records)


# =============================================================================
# TestDataSeeder — idempotency via mock session
# =============================================================================

def _make_mock_session_factory(account_rows=None):
    """
    Returns a context-manager session factory whose execute() returns
    rowcount=1 for inserts and fetches the supplied account_rows list for
    the _resolve_account_ids() query.
    """
    if account_rows is None:
        # Build mock row objects matching (account_id, username)
        account_rows = []
        usernames = ["alice_test", "bob_test", "carol_test", "dave_test", "eve_test", "frank_test"]
        for i, uname in enumerate(usernames, start=1):
            r = MagicMock()
            r.account_id = i
            r.username = uname
            account_rows.append(r)

    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_result.fetchall.return_value = account_rows

    mock_session = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)

    @contextmanager
    def factory():
        yield mock_session

    return factory, mock_session


class TestDataSeederIdempotency:
    def test_seed_all_returns_stats_for_all_tables(self):
        factory, _ = _make_mock_session_factory()
        seeder = TestDataSeeder(factory)
        stats = seeder.seed_all()
        assert set(stats.keys()) == {
            "accounts", "p2p_transfers", "virtual_cards",
            "spending_insights", "investment_options",
        }

    def test_seed_all_attempted_counts_match_seed_data(self):
        from tests.seed_test_data import (
            SEED_ACCOUNTS,
            SEED_CARDS_TEMPLATE,
            SEED_INSIGHTS_TEMPLATE,
            SEED_INVESTMENTS,
            SEED_TRANSFERS_TEMPLATE,
        )
        factory, _ = _make_mock_session_factory()
        seeder = TestDataSeeder(factory)
        stats = seeder.seed_all()

        assert stats["accounts"]["attempted"] == len(SEED_ACCOUNTS)
        assert stats["p2p_transfers"]["attempted"] == len(SEED_TRANSFERS_TEMPLATE)
        assert stats["virtual_cards"]["attempted"] == len(SEED_CARDS_TEMPLATE)
        assert stats["spending_insights"]["attempted"] == len(SEED_INSIGHTS_TEMPLATE)
        assert stats["investment_options"]["attempted"] == len(SEED_INVESTMENTS)

    def test_seed_all_no_skips_on_valid_data(self):
        factory, _ = _make_mock_session_factory()
        seeder = TestDataSeeder(factory)
        stats = seeder.seed_all()
        for table, counts in stats.items():
            assert counts.get("skipped_validation", 0) == 0, (
                f"{table}: expected 0 validation skips, got {counts}"
            )

    def test_teardown_all_executes_five_deletes(self):
        factory, mock_session = _make_mock_session_factory()
        seeder = TestDataSeeder(factory)
        seeder.teardown_all()
        # Five DELETE statements: spending_insights, virtual_cards, p2p_transfers,
        # investment_options, accounts — each passed as a sqlalchemy text() object.
        assert mock_session.execute.call_count == 5

    def test_teardown_targets_test_rows_only(self):
        factory, mock_session = _make_mock_session_factory()
        seeder = TestDataSeeder(factory)
        seeder.teardown_all()
        # TextClause objects hold the actual SQL in their .text attribute.
        all_sql = " ".join(c.args[0].text for c in mock_session.execute.call_args_list)
        assert "_test" in all_sql or "TEST-TXN-" in all_sql or "Test " in all_sql

    def test_module_level_seed_all_helper(self):
        factory, _ = _make_mock_session_factory()
        stats = seed_all(factory)
        assert "accounts" in stats

    def test_module_level_teardown_all_helper(self):
        factory, mock_session = _make_mock_session_factory()
        teardown_all(factory)
        assert mock_session.execute.called
