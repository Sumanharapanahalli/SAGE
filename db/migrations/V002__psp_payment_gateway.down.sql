-- =============================================================
-- Migration V002 — PSP Payment Gateway Schema (DOWN / ROLLBACK)
-- Reverses V002_up completely with no data loss on rollback.
-- Objects are dropped leaf-to-root to respect FK dependencies.
--
-- No data loss guarantee:
--   This script drops only tables introduced in V002. All V001
--   tables (accounts, p2p_transfers, etc.) are untouched.
--   The shared fn_set_updated_at() from V001 is preserved.
-- =============================================================

BEGIN;

-- ── Drop triggers: transactions ───────────────────────────────
DROP TRIGGER IF EXISTS trg_audit_transactions      ON transactions;
DROP TRIGGER IF EXISTS trg_transactions_updated_at ON transactions;

-- ── Drop triggers: card_details ───────────────────────────────
DROP TRIGGER IF EXISTS trg_audit_card_details      ON card_details;
DROP TRIGGER IF EXISTS trg_card_details_updated_at ON card_details;

-- ── Drop triggers: users ──────────────────────────────────────
DROP TRIGGER IF EXISTS trg_audit_users      ON users;
DROP TRIGGER IF EXISTS trg_users_updated_at ON users;

-- ── Drop PSP-specific audit function ─────────────────────────
-- fn_set_updated_at() is shared with V001 — do NOT drop it here.
DROP FUNCTION IF EXISTS fn_psp_audit_log();

-- ── Drop domain tables (leaf -> root) ────────────────────────
DROP TABLE IF EXISTS transactions;  -- refs users, card_details
DROP TABLE IF EXISTS card_details;  -- refs users
DROP TABLE IF EXISTS users;         -- root PSP table

-- ── Deregister migration ──────────────────────────────────────
DELETE FROM schema_migrations WHERE version = 'V002';

COMMIT;
