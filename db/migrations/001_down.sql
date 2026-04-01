-- =============================================================
-- Migration V001 — Initial Schema (DOWN / ROLLBACK)
-- Reverses 001_up.sql completely with no data loss.
-- Tables are dropped in leaf-to-root order to respect FKs.
-- =============================================================

BEGIN;

-- ── Drop audit triggers ───────────────────────────────────────
DROP TRIGGER IF EXISTS trg_audit_investment_options ON investment_options;
DROP TRIGGER IF EXISTS trg_audit_spending_insights  ON spending_insights;
DROP TRIGGER IF EXISTS trg_audit_virtual_cards      ON virtual_cards;
DROP TRIGGER IF EXISTS trg_audit_p2p_transfers      ON p2p_transfers;
DROP TRIGGER IF EXISTS trg_audit_accounts           ON accounts;

-- ── Drop updated_at triggers ──────────────────────────────────
DROP TRIGGER IF EXISTS trg_investment_options_updated_at ON investment_options;
DROP TRIGGER IF EXISTS trg_virtual_cards_updated_at      ON virtual_cards;
DROP TRIGGER IF EXISTS trg_p2p_transfers_updated_at      ON p2p_transfers;
DROP TRIGGER IF EXISTS trg_accounts_updated_at           ON accounts;

-- ── Drop trigger functions ────────────────────────────────────
DROP FUNCTION IF EXISTS fn_audit_log();
DROP FUNCTION IF EXISTS fn_set_updated_at();

-- ── Drop domain tables (leaf → root) ─────────────────────────
DROP TABLE IF EXISTS spending_insights;   -- refs accounts, p2p_transfers
DROP TABLE IF EXISTS virtual_cards;       -- refs accounts
DROP TABLE IF EXISTS p2p_transfers;       -- refs accounts
DROP TABLE IF EXISTS investment_options;  -- no FK deps
DROP TABLE IF EXISTS accounts;            -- root
DROP TABLE IF EXISTS audit_log;           -- no FK deps

-- ── Extensions ────────────────────────────────────────────────
-- Commented out: pgcrypto may be shared with other migrations.
-- DROP EXTENSION IF EXISTS pgcrypto;

COMMIT;
