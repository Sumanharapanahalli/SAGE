-- =============================================================
-- Migration V001 — Initial Schema (UP)
-- Database: PostgreSQL 14+
-- =============================================================
-- Transaction Isolation Levels:
--   READ COMMITTED (default) : DDL migrations and general reads.
--   REPEATABLE READ           : Balance reads during transfers.
--   SERIALIZABLE              : Concurrent debit/credit pairs.
--
-- All P2P balance mutations MUST be wrapped in:
--   BEGIN;
--   SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
--   ... debit sender, credit receiver ...
--   COMMIT;
-- =============================================================

BEGIN;

-- ── Extensions ────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()

-- ── Audit Log ─────────────────────────────────────────────────
-- Created first; every domain table's AFTER trigger writes here.
CREATE TABLE audit_log (
    audit_id    BIGSERIAL    PRIMARY KEY,
    table_name  VARCHAR(100) NOT NULL,
    operation   VARCHAR(10)  NOT NULL
                    CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by  TEXT         NOT NULL DEFAULT current_user,
    changed_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    old_values  JSONB,
    new_values  JSONB
);

CREATE INDEX idx_audit_table_name ON audit_log (table_name);
CREATE INDEX idx_audit_changed_at ON audit_log (changed_at DESC);
CREATE INDEX idx_audit_new_gin    ON audit_log USING GIN (new_values);
CREATE INDEX idx_audit_old_gin    ON audit_log USING GIN (old_values);

-- ── Accounts ──────────────────────────────────────────────────
CREATE TABLE accounts (
    account_id  BIGSERIAL      PRIMARY KEY,
    username    VARCHAR(255)   NOT NULL,
    password    VARCHAR(255)   NOT NULL,   -- store bcrypt/argon2 hash only
    email       VARCHAR(255),
    balance     DECIMAL(10,2)  NOT NULL DEFAULT 0.00
                    CHECK (balance >= 0.00),
    status      VARCHAR(50)    NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'suspended', 'closed')),
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_accounts_username UNIQUE (username),
    CONSTRAINT uq_accounts_email    UNIQUE (email)
);

CREATE INDEX idx_accounts_username   ON accounts (username);
CREATE INDEX idx_accounts_status     ON accounts (status);
CREATE INDEX idx_accounts_created_at ON accounts (created_at DESC);

-- ── P2P Transfers ─────────────────────────────────────────────
-- NOTE: The original spec listed sender_id + receiver_id as a
-- composite PK.  That prevents multiple transfers between the
-- same pair.  A dedicated transfer_id PK is used instead.
CREATE TABLE p2p_transfers (
    transfer_id  BIGSERIAL      PRIMARY KEY,
    sender_id    BIGINT         NOT NULL REFERENCES accounts (account_id),
    receiver_id  BIGINT         NOT NULL REFERENCES accounts (account_id),
    amount       DECIMAL(10,2)  NOT NULL CHECK (amount > 0.00),
    status       VARCHAR(50)    NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'completed', 'failed', 'reversed')),
    reference    TEXT           UNIQUE DEFAULT gen_random_uuid()::text,
    notes        TEXT,
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_p2p_no_self_transfer CHECK (sender_id <> receiver_id)
);

CREATE INDEX idx_p2p_sender_id   ON p2p_transfers (sender_id);
CREATE INDEX idx_p2p_receiver_id ON p2p_transfers (receiver_id);
CREATE INDEX idx_p2p_status      ON p2p_transfers (status);
CREATE INDEX idx_p2p_created_at  ON p2p_transfers (created_at DESC);

-- ── Virtual Cards ─────────────────────────────────────────────
CREATE TABLE virtual_cards (
    card_id          BIGSERIAL      PRIMARY KEY,
    card_holder_id   BIGINT         NOT NULL REFERENCES accounts (account_id),
    card_type        VARCHAR(255)   NOT NULL
                         CHECK (card_type IN ('debit', 'credit', 'prepaid')),
    card_expiry_date DATE           NOT NULL,
    card_last_four   CHAR(4),            -- masked PAN; never store full PAN
    spending_limit   DECIMAL(10,2),
    status           VARCHAR(50)    NOT NULL DEFAULT 'active'
                         CHECK (status IN ('active', 'frozen', 'cancelled')),
    created_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_virtual_cards_holder UNIQUE (card_holder_id)
);

CREATE INDEX idx_vc_holder_id ON virtual_cards (card_holder_id);
CREATE INDEX idx_vc_status    ON virtual_cards (status);
CREATE INDEX idx_vc_expiry    ON virtual_cards (card_expiry_date);

-- ── Spending Insights ─────────────────────────────────────────
-- account_id added: original spec omitted the owner FK.
CREATE TABLE spending_insights (
    id           BIGSERIAL      PRIMARY KEY,
    account_id   BIGINT         NOT NULL REFERENCES accounts (account_id),
    date         DATE           NOT NULL DEFAULT CURRENT_DATE,
    category     VARCHAR(255)   NOT NULL,
    amount       DECIMAL(10,2)  NOT NULL CHECK (amount >= 0.00),
    source_ref   BIGINT         REFERENCES p2p_transfers (transfer_id),
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_si_account_id   ON spending_insights (account_id);
CREATE INDEX idx_si_date         ON spending_insights (date DESC);
CREATE INDEX idx_si_category     ON spending_insights (category);
CREATE INDEX idx_si_account_date ON spending_insights (account_id, date DESC);

-- ── Investment Options ────────────────────────────────────────
CREATE TABLE investment_options (
    id               BIGSERIAL      PRIMARY KEY,
    name             VARCHAR(255)   NOT NULL,
    asset_type       VARCHAR(255)   NOT NULL,
    risk_level       VARCHAR(50)    NOT NULL
                         CHECK (risk_level IN ('low', 'medium', 'high', 'very_high')),
    return_potential DECIMAL(10,2)  NOT NULL CHECK (return_potential >= 0.00),
    description      TEXT,
    min_investment   DECIMAL(10,2)  NOT NULL DEFAULT 0.00,
    is_active        BOOLEAN        NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_io_asset_type ON investment_options (asset_type);
CREATE INDEX idx_io_risk_level ON investment_options (risk_level);
CREATE INDEX idx_io_is_active  ON investment_options (is_active);

-- ── updated_at auto-maintenance ───────────────────────────────
CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_accounts_updated_at
    BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_p2p_transfers_updated_at
    BEFORE UPDATE ON p2p_transfers
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_virtual_cards_updated_at
    BEFORE UPDATE ON virtual_cards
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_investment_options_updated_at
    BEFORE UPDATE ON investment_options
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

-- ── Audit trigger ─────────────────────────────────────────────
-- SECURITY DEFINER ensures the insert always succeeds regardless
-- of the calling role's direct privileges on audit_log.
CREATE OR REPLACE FUNCTION fn_audit_log()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    INSERT INTO audit_log (table_name, operation, changed_by, old_values, new_values)
    VALUES (
        TG_TABLE_NAME,
        TG_OP,
        current_user,
        CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE row_to_json(OLD)::jsonb END,
        CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE row_to_json(NEW)::jsonb END
    );
    RETURN NULL;  -- AFTER trigger; return value is ignored
END;
$$;

CREATE TRIGGER trg_audit_accounts
    AFTER INSERT OR UPDATE OR DELETE ON accounts
    FOR EACH ROW EXECUTE FUNCTION fn_audit_log();

CREATE TRIGGER trg_audit_p2p_transfers
    AFTER INSERT OR UPDATE OR DELETE ON p2p_transfers
    FOR EACH ROW EXECUTE FUNCTION fn_audit_log();

CREATE TRIGGER trg_audit_virtual_cards
    AFTER INSERT OR UPDATE OR DELETE ON virtual_cards
    FOR EACH ROW EXECUTE FUNCTION fn_audit_log();

CREATE TRIGGER trg_audit_spending_insights
    AFTER INSERT OR UPDATE OR DELETE ON spending_insights
    FOR EACH ROW EXECUTE FUNCTION fn_audit_log();

CREATE TRIGGER trg_audit_investment_options
    AFTER INSERT OR UPDATE OR DELETE ON investment_options
    FOR EACH ROW EXECUTE FUNCTION fn_audit_log();

COMMIT;
