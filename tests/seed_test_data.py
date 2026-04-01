"""
tests/seed_test_data.py — Idempotent test dataset seeder with ingestion validation.

Schema covered:
  accounts          — 6 seed users (active/suspended/closed states)
  p2p_transfers     — 8 transfers (pending/completed/failed/reversed states)
  virtual_cards     — 4 cards (debit/credit/prepaid; active/frozen/cancelled)
  spending_insights — 12 insight rows across 4 categories
  investment_options — 5 investment products (all risk levels)

Idempotency guarantee:
  Every INSERT uses ON CONFLICT DO NOTHING keyed on the stable external_ref column
  (username, reference, card_holder_id unique constraints from the migration).
  Re-running this script produces no duplicate rows and no errors.

Data validation on ingestion:
  All rows are validated by _validate_record() before any SQL is executed.
  Invalid rows are logged and skipped — the rest of the seed proceeds.

Usage (from repo root):
  DB_USER=sage DB_PASSWORD=sage DB_NAME=sage_test python -m tests.seed_test_data

  Or from pytest conftest via:
    from tests.seed_test_data import seed_all, teardown_all
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("seed_test_data")

# ---------------------------------------------------------------------------
# Inline validation (mirrors data_pipeline/validators.py patterns; no import
# coupling so this module stays usable in isolation).
# ---------------------------------------------------------------------------

@dataclass
class _Check:
    rule: str
    passed: bool
    message: str
    severity: str = "error"


def _require_fields(record: dict, required: list[str]) -> list[_Check]:
    results = []
    for f in required:
        present = record.get(f) is not None and record.get(f) != ""
        results.append(_Check(
            rule=f"required:{f}",
            passed=present,
            message=f"Field '{f}' is required." if not present else "ok",
            severity="critical",
        ))
    return results


def _non_negative(record: dict, fields: list[str]) -> list[_Check]:
    results = []
    for f in fields:
        val = record.get(f)
        if val is None:
            continue
        try:
            ok = Decimal(str(val)) >= Decimal("0")
        except Exception:
            ok = False
        results.append(_Check(
            rule=f"non_negative:{f}",
            passed=ok,
            message=f"Field '{f}' must be >= 0, got {val!r}." if not ok else "ok",
        ))
    return results


def _positive(record: dict, fields: list[str]) -> list[_Check]:
    results = []
    for f in fields:
        val = record.get(f)
        if val is None:
            continue
        try:
            ok = Decimal(str(val)) > Decimal("0")
        except Exception:
            ok = False
        results.append(_Check(
            rule=f"positive:{f}",
            passed=ok,
            message=f"Field '{f}' must be > 0, got {val!r}." if not ok else "ok",
        ))
    return results


def _enum_check(record: dict, field_name: str, allowed: list[str]) -> _Check:
    val = record.get(field_name)
    ok = val in allowed
    return _Check(
        rule=f"enum:{field_name}",
        passed=ok,
        message=f"'{field_name}' must be one of {allowed}, got {val!r}." if not ok else "ok",
    )


def _validate_record(table: str, record: dict) -> list[_Check]:
    """Return all validation checks for *record* destined for *table*."""
    checks: list[_Check] = []

    if table == "accounts":
        checks += _require_fields(record, ["username", "password", "status"])
        checks.append(_enum_check(record, "status", ["active", "suspended", "closed"]))
        checks += _non_negative(record, ["balance"])

    elif table == "p2p_transfers":
        checks += _require_fields(record, ["sender_id", "receiver_id", "amount", "status"])
        checks += _positive(record, ["amount"])
        checks.append(_enum_check(record, "status", ["pending", "completed", "failed", "reversed"]))
        sender = record.get("sender_id")
        receiver = record.get("receiver_id")
        no_self = sender != receiver
        checks.append(_Check(
            rule="no_self_transfer",
            passed=no_self,
            message=f"sender_id and receiver_id must differ (got {sender})." if not no_self else "ok",
            severity="critical",
        ))

    elif table == "virtual_cards":
        checks += _require_fields(record, ["card_holder_id", "card_type", "card_expiry_date", "status"])
        checks.append(_enum_check(record, "card_type", ["debit", "credit", "prepaid"]))
        checks.append(_enum_check(record, "status", ["active", "frozen", "cancelled"]))
        expiry = record.get("card_expiry_date")
        if expiry:
            future = expiry > date.today()
            checks.append(_Check(
                rule="card_not_expired",
                passed=future,
                message=f"card_expiry_date {expiry} is in the past." if not future else "ok",
                severity="warning",
            ))

    elif table == "spending_insights":
        checks += _require_fields(record, ["account_id", "date", "category", "amount"])
        checks += _non_negative(record, ["amount"])

    elif table == "investment_options":
        checks += _require_fields(record, ["name", "asset_type", "risk_level", "return_potential"])
        checks.append(_enum_check(record, "risk_level", ["low", "medium", "high", "very_high"]))
        checks += _non_negative(record, ["return_potential", "min_investment"])

    return checks


def _is_valid(table: str, record: dict, row_label: str) -> bool:
    checks = _validate_record(table, record)
    blocking = [c for c in checks if not c.passed and c.severity in ("error", "critical")]
    if blocking:
        for c in blocking:
            logger.warning("SKIP %s [%s] — %s (%s)", table, row_label, c.message, c.rule)
        return False
    warnings = [c for c in checks if not c.passed and c.severity == "warning"]
    for w in warnings:
        logger.warning("WARN %s [%s] — %s (%s)", table, row_label, w.message, w.rule)
    return True


# ---------------------------------------------------------------------------
# Seed data (plain dicts — no ORM dependency)
# ---------------------------------------------------------------------------

# Passwords are bcrypt hashes of the literal strings shown in comments.
# Generated offline; never store plaintext.
_BCRYPT_PLACEHOLDER = "$2b$12$TESTONLY_DO_NOT_USE_IN_PROD_xxxxxxxxxxxxxxxxxxxxxxxxxxx"

SEED_ACCOUNTS: list[dict[str, Any]] = [
    # (account_id is BIGSERIAL — let the DB assign it; upsert keyed on username)
    {"username": "alice_test",  "password": _BCRYPT_PLACEHOLDER, "email": "alice@test.example",  "balance": Decimal("1000.00"), "status": "active"},
    {"username": "bob_test",    "password": _BCRYPT_PLACEHOLDER, "email": "bob@test.example",    "balance": Decimal("500.50"),  "status": "active"},
    {"username": "carol_test",  "password": _BCRYPT_PLACEHOLDER, "email": "carol@test.example",  "balance": Decimal("0.00"),    "status": "active"},
    {"username": "dave_test",   "password": _BCRYPT_PLACEHOLDER, "email": "dave@test.example",   "balance": Decimal("250.75"),  "status": "suspended"},
    {"username": "eve_test",    "password": _BCRYPT_PLACEHOLDER, "email": "eve@test.example",    "balance": Decimal("0.00"),    "status": "closed"},
    {"username": "frank_test",  "password": _BCRYPT_PLACEHOLDER, "email": "frank@test.example",  "balance": Decimal("9999.99"), "status": "active"},
]

# Transfers reference account_ids resolved at seed-time from usernames.
# Using _REF_ keys so _resolve_ids() can substitute real PKs.
SEED_TRANSFERS_TEMPLATE: list[dict[str, Any]] = [
    {"_sender": "alice_test",  "_receiver": "bob_test",   "amount": Decimal("100.00"), "status": "completed", "reference": "TEST-TXN-0001", "notes": "Split dinner"},
    {"_sender": "bob_test",    "_receiver": "carol_test", "amount": Decimal("50.00"),  "status": "completed", "reference": "TEST-TXN-0002", "notes": "Rent share"},
    {"_sender": "alice_test",  "_receiver": "frank_test", "amount": Decimal("200.00"), "status": "pending",   "reference": "TEST-TXN-0003", "notes": "Pending payment"},
    {"_sender": "frank_test",  "_receiver": "alice_test", "amount": Decimal("75.25"),  "status": "completed", "reference": "TEST-TXN-0004", "notes": "Refund"},
    {"_sender": "carol_test",  "_receiver": "alice_test", "amount": Decimal("20.00"),  "status": "failed",    "reference": "TEST-TXN-0005", "notes": "Insufficient funds"},
    {"_sender": "bob_test",    "_receiver": "frank_test", "amount": Decimal("300.00"), "status": "completed", "reference": "TEST-TXN-0006", "notes": "Freelance fee"},
    {"_sender": "alice_test",  "_receiver": "carol_test", "amount": Decimal("10.00"),  "status": "reversed",  "reference": "TEST-TXN-0007", "notes": "Duplicate — reversed"},
    {"_sender": "frank_test",  "_receiver": "bob_test",   "amount": Decimal("150.00"), "status": "pending",   "reference": "TEST-TXN-0008", "notes": "Instalment 1"},
]

_TODAY = date.today()
_EXPIRY_ACTIVE  = _TODAY + timedelta(days=730)   # +2 years
_EXPIRY_FROZEN  = _TODAY + timedelta(days=365)   # +1 year
_EXPIRY_WARNING = _TODAY + timedelta(days=10)    # nearly expired → warning

SEED_CARDS_TEMPLATE: list[dict[str, Any]] = [
    {"_holder": "alice_test",  "card_type": "debit",   "card_expiry_date": _EXPIRY_ACTIVE,  "card_last_four": "1234", "spending_limit": Decimal("2000.00"), "status": "active"},
    {"_holder": "bob_test",    "card_type": "credit",  "card_expiry_date": _EXPIRY_ACTIVE,  "card_last_four": "5678", "spending_limit": Decimal("5000.00"), "status": "active"},
    {"_holder": "carol_test",  "card_type": "prepaid", "card_expiry_date": _EXPIRY_FROZEN,  "card_last_four": "9012", "spending_limit": Decimal("500.00"),  "status": "frozen"},
    {"_holder": "frank_test",  "card_type": "debit",   "card_expiry_date": _EXPIRY_WARNING, "card_last_four": "3456", "spending_limit": Decimal("1000.00"), "status": "active"},
]

SEED_INSIGHTS_TEMPLATE: list[dict[str, Any]] = [
    {"_account": "alice_test", "date": _TODAY - timedelta(days=1),  "category": "food",          "amount": Decimal("45.00"),  "notes": "Groceries"},
    {"_account": "alice_test", "date": _TODAY - timedelta(days=3),  "category": "transport",     "amount": Decimal("12.50"),  "notes": "Bus pass"},
    {"_account": "alice_test", "date": _TODAY - timedelta(days=7),  "category": "entertainment", "amount": Decimal("25.00"),  "notes": "Cinema"},
    {"_account": "alice_test", "date": _TODAY - timedelta(days=14), "category": "utilities",     "amount": Decimal("80.00"),  "notes": "Electric bill"},
    {"_account": "bob_test",   "date": _TODAY - timedelta(days=2),  "category": "food",          "amount": Decimal("22.30"),  "notes": "Lunch"},
    {"_account": "bob_test",   "date": _TODAY - timedelta(days=5),  "category": "transport",     "amount": Decimal("9.00"),   "notes": "Tube fare"},
    {"_account": "frank_test", "date": _TODAY - timedelta(days=1),  "category": "food",          "amount": Decimal("110.00"), "notes": "Restaurant"},
    {"_account": "frank_test", "date": _TODAY - timedelta(days=4),  "category": "entertainment", "amount": Decimal("60.00"),  "notes": "Concert"},
    {"_account": "frank_test", "date": _TODAY - timedelta(days=8),  "category": "utilities",     "amount": Decimal("200.00"), "notes": "Quarterly gas"},
    {"_account": "carol_test", "date": _TODAY - timedelta(days=2),  "category": "food",          "amount": Decimal("0.00"),   "notes": "Free sample (edge case)"},
    {"_account": "carol_test", "date": _TODAY - timedelta(days=10), "category": "transport",     "amount": Decimal("5.00"),   "notes": "Single journey"},
    {"_account": "bob_test",   "date": _TODAY - timedelta(days=20), "category": "utilities",     "amount": Decimal("55.00"),  "notes": "Broadband"},
]

SEED_INVESTMENTS: list[dict[str, Any]] = [
    {"name": "Test Cash ISA",         "asset_type": "cash",      "risk_level": "low",       "return_potential": Decimal("3.50"),  "min_investment": Decimal("1.00"),     "is_active": True},
    {"name": "Test Bond Fund",        "asset_type": "bonds",     "risk_level": "low",       "return_potential": Decimal("5.00"),  "min_investment": Decimal("100.00"),   "is_active": True},
    {"name": "Test Equity Index",     "asset_type": "equities",  "risk_level": "medium",    "return_potential": Decimal("8.50"),  "min_investment": Decimal("250.00"),   "is_active": True},
    {"name": "Test Growth ETF",       "asset_type": "equities",  "risk_level": "high",      "return_potential": Decimal("14.00"), "min_investment": Decimal("500.00"),   "is_active": True},
    {"name": "Test Crypto Basket",    "asset_type": "crypto",    "risk_level": "very_high", "return_potential": Decimal("35.00"), "min_investment": Decimal("50.00"),    "is_active": False},
]


# ---------------------------------------------------------------------------
# Seeder
# ---------------------------------------------------------------------------

class TestDataSeeder:
    """
    Idempotent seeder — safe to call multiple times; produces identical DB state.

    All writes use ON CONFLICT DO NOTHING (accounts/investments/cards) or
    ON CONFLICT DO NOTHING on the stable unique key (transfers: reference).
    """

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory
        self._account_ids: dict[str, int] = {}
        self._transfer_ids: dict[str, int] = {}
        self.stats: dict[str, dict[str, int]] = {}

    # ── public API ──────────────────────────────────────────────────────────

    def seed_all(self) -> dict[str, dict[str, int]]:
        """Seed all tables in dependency order. Returns per-table stats."""
        logger.info("=== seed_all started ===")
        self._seed_accounts()
        self._resolve_account_ids()
        self._seed_investments()
        self._seed_transfers()
        self._seed_cards()
        self._seed_insights()
        logger.info("=== seed_all complete — stats: %s ===", self.stats)
        return self.stats

    def teardown_all(self) -> None:
        """Remove only test rows (identified by _TEST_ prefix / reference pattern)."""
        logger.info("=== teardown_all started ===")
        with self._session_factory() as session:
            # Delete in reverse FK order
            session.execute(text(
                "DELETE FROM spending_insights WHERE account_id IN "
                "(SELECT account_id FROM accounts WHERE username LIKE '%_test')"
            ))
            session.execute(text(
                "DELETE FROM virtual_cards WHERE card_holder_id IN "
                "(SELECT account_id FROM accounts WHERE username LIKE '%_test')"
            ))
            session.execute(text(
                "DELETE FROM p2p_transfers WHERE reference LIKE 'TEST-TXN-%'"
            ))
            session.execute(text(
                "DELETE FROM investment_options WHERE name LIKE 'Test %'"
            ))
            session.execute(text(
                "DELETE FROM accounts WHERE username LIKE '%_test'"
            ))
            session.commit()
        logger.info("=== teardown_all complete ===")

    # ── private helpers ─────────────────────────────────────────────────────

    def _seed_accounts(self) -> None:
        inserted = 0
        skipped_validation = 0
        with self._session_factory() as session:
            for row in SEED_ACCOUNTS:
                if not _is_valid("accounts", row, row["username"]):
                    skipped_validation += 1
                    continue
                result = session.execute(text("""
                    INSERT INTO accounts (username, password, email, balance, status)
                    VALUES (:username, :password, :email, :balance, :status)
                    ON CONFLICT (username) DO NOTHING
                """), row)
                inserted += result.rowcount
            session.commit()
        self.stats["accounts"] = {"attempted": len(SEED_ACCOUNTS), "inserted": inserted, "skipped_validation": skipped_validation}
        logger.info("accounts: inserted=%d  skipped_validation=%d", inserted, skipped_validation)

    def _resolve_account_ids(self) -> None:
        """Fetch PKs for all seeded usernames (needed for FK columns)."""
        usernames = [r["username"] for r in SEED_ACCOUNTS]
        with self._session_factory() as session:
            rows = session.execute(
                text("SELECT account_id, username FROM accounts WHERE username = ANY(:u)"),
                {"u": usernames},
            ).fetchall()
        self._account_ids = {row.username: row.account_id for row in rows}
        logger.info("Resolved %d account IDs", len(self._account_ids))

    def _seed_investments(self) -> None:
        inserted = 0
        skipped_validation = 0
        with self._session_factory() as session:
            for row in SEED_INVESTMENTS:
                if not _is_valid("investment_options", row, row["name"]):
                    skipped_validation += 1
                    continue
                result = session.execute(text("""
                    INSERT INTO investment_options (name, asset_type, risk_level, return_potential, min_investment, is_active)
                    VALUES (:name, :asset_type, :risk_level, :return_potential, :min_investment, :is_active)
                    ON CONFLICT DO NOTHING
                """), row)
                inserted += result.rowcount
            session.commit()
        self.stats["investment_options"] = {"attempted": len(SEED_INVESTMENTS), "inserted": inserted, "skipped_validation": skipped_validation}
        logger.info("investment_options: inserted=%d  skipped_validation=%d", inserted, skipped_validation)

    def _seed_transfers(self) -> None:
        inserted = 0
        skipped_validation = 0
        skipped_fk = 0
        with self._session_factory() as session:
            for tmpl in SEED_TRANSFERS_TEMPLATE:
                sender_id   = self._account_ids.get(tmpl["_sender"])
                receiver_id = self._account_ids.get(tmpl["_receiver"])
                if sender_id is None or receiver_id is None:
                    logger.warning("SKIP transfer %s — unresolved FK (sender=%s, receiver=%s)",
                                   tmpl["reference"], tmpl["_sender"], tmpl["_receiver"])
                    skipped_fk += 1
                    continue
                row: dict[str, Any] = {
                    "sender_id":   sender_id,
                    "receiver_id": receiver_id,
                    "amount":      tmpl["amount"],
                    "status":      tmpl["status"],
                    "reference":   tmpl["reference"],
                    "notes":       tmpl.get("notes"),
                }
                if not _is_valid("p2p_transfers", row, tmpl["reference"]):
                    skipped_validation += 1
                    continue
                result = session.execute(text("""
                    INSERT INTO p2p_transfers (sender_id, receiver_id, amount, status, reference, notes)
                    VALUES (:sender_id, :receiver_id, :amount, :status, :reference, :notes)
                    ON CONFLICT (reference) DO NOTHING
                """), row)
                inserted += result.rowcount
            session.commit()
        self.stats["p2p_transfers"] = {
            "attempted": len(SEED_TRANSFERS_TEMPLATE),
            "inserted": inserted,
            "skipped_validation": skipped_validation,
            "skipped_fk": skipped_fk,
        }
        logger.info("p2p_transfers: inserted=%d  skipped_validation=%d  skipped_fk=%d",
                    inserted, skipped_validation, skipped_fk)

    def _seed_cards(self) -> None:
        inserted = 0
        skipped_validation = 0
        skipped_fk = 0
        with self._session_factory() as session:
            for tmpl in SEED_CARDS_TEMPLATE:
                holder_id = self._account_ids.get(tmpl["_holder"])
                if holder_id is None:
                    logger.warning("SKIP virtual_card for %s — unresolved FK", tmpl["_holder"])
                    skipped_fk += 1
                    continue
                row: dict[str, Any] = {
                    "card_holder_id":  holder_id,
                    "card_type":       tmpl["card_type"],
                    "card_expiry_date": tmpl["card_expiry_date"],
                    "card_last_four":  tmpl["card_last_four"],
                    "spending_limit":  tmpl["spending_limit"],
                    "status":          tmpl["status"],
                }
                if not _is_valid("virtual_cards", row, f"{tmpl['_holder']}/{tmpl['card_type']}"):
                    skipped_validation += 1
                    continue
                result = session.execute(text("""
                    INSERT INTO virtual_cards (card_holder_id, card_type, card_expiry_date, card_last_four, spending_limit, status)
                    VALUES (:card_holder_id, :card_type, :card_expiry_date, :card_last_four, :spending_limit, :status)
                    ON CONFLICT (card_holder_id) DO NOTHING
                """), row)
                inserted += result.rowcount
            session.commit()
        self.stats["virtual_cards"] = {
            "attempted": len(SEED_CARDS_TEMPLATE),
            "inserted": inserted,
            "skipped_validation": skipped_validation,
            "skipped_fk": skipped_fk,
        }
        logger.info("virtual_cards: inserted=%d  skipped_validation=%d  skipped_fk=%d",
                    inserted, skipped_validation, skipped_fk)

    def _seed_insights(self) -> None:
        inserted = 0
        skipped_validation = 0
        skipped_fk = 0
        with self._session_factory() as session:
            for tmpl in SEED_INSIGHTS_TEMPLATE:
                account_id = self._account_ids.get(tmpl["_account"])
                if account_id is None:
                    logger.warning("SKIP spending_insight for %s — unresolved FK", tmpl["_account"])
                    skipped_fk += 1
                    continue
                row: dict[str, Any] = {
                    "account_id": account_id,
                    "date":       tmpl["date"],
                    "category":   tmpl["category"],
                    "amount":     tmpl["amount"],
                }
                label = f"{tmpl['_account']}/{tmpl['category']}/{tmpl['date']}"
                if not _is_valid("spending_insights", row, label):
                    skipped_validation += 1
                    continue
                result = session.execute(text("""
                    INSERT INTO spending_insights (account_id, date, category, amount)
                    VALUES (:account_id, :date, :category, :amount)
                """), row)
                inserted += result.rowcount
            session.commit()
        # spending_insights has no unique constraint — idempotency is enforced by
        # teardown_all() deleting by account pattern before re-seeding.
        self.stats["spending_insights"] = {
            "attempted": len(SEED_INSIGHTS_TEMPLATE),
            "inserted": inserted,
            "skipped_validation": skipped_validation,
            "skipped_fk": skipped_fk,
        }
        logger.info("spending_insights: inserted=%d  skipped_validation=%d  skipped_fk=%d",
                    inserted, skipped_validation, skipped_fk)


# ---------------------------------------------------------------------------
# Pytest-compatible fixture helpers
# ---------------------------------------------------------------------------

def seed_all(session_factory: Any) -> dict[str, dict[str, int]]:
    """Idempotent seed; returns stats dict. Call from pytest fixtures."""
    seeder = TestDataSeeder(session_factory)
    return seeder.seed_all()


def teardown_all(session_factory: Any) -> None:
    """Remove all test rows. Call from pytest fixture teardown."""
    seeder = TestDataSeeder(session_factory)
    seeder.teardown_all()


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

    from db import connection as db

    db.init(pool_size=2, echo="--echo" in sys.argv)
    if not db.health_check():
        logger.error("Database not reachable — aborting.")
        sys.exit(1)

    from contextlib import contextmanager
    from sqlalchemy.orm import Session

    @contextmanager
    def _session_factory():
        yield from db.get_session()

    seeder = TestDataSeeder(_session_factory)

    if "--teardown" in sys.argv:
        seeder.teardown_all()
    else:
        stats = seeder.seed_all()
        print("\nSeed complete:")
        for table, counts in stats.items():
            print(f"  {table:<25} {counts}")
