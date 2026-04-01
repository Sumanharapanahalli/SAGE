-- =============================================================
-- Migration V002 — PSP Payment Gateway Schema (UP)
-- Database: PostgreSQL 14+
-- =============================================================
-- Transaction Isolation Levels:
--   READ COMMITTED  (default) : DDL migrations, general reads.
--   REPEATABLE READ            : Balance/limit checks during
--                                authorisation flows.
--   SERIALIZABLE               : All financial writes — debit,
--                                credit, card charge, refund.
--
-- Application pattern for financial mutations:
--   BEGIN;
--   SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
--   -- debit sender, credit receiver, record transaction
--   COMMIT;
--
-- PCI DSS notes:
--   - users.password_hash  : bcrypt / argon2id only — never plaintext.
--   - card_details         : raw PAN must never be stored. Use a
--                            vault token (card_number_token) and keep
--                            only the masked suffix (card_number_masked).
--   - CVV (card_details.cvv): PROHIBITED post-authorisation per
--                            PCI DSS Requirement 3.2.2. Column is
--                            intentionally absent from this schema.
-- =============================================================

BEGIN;

-- ── PSP-specific audit function ───────────────────────────────
-- Extends the generic fn_audit_log() from V001 with field-level
-- masking for PSP sensitive columns before writing to audit_log.
CREATE OR REPLACE FUNCTION fn_psp_audit_log()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_old JSONB;
    v_new JSONB;
BEGIN
    v_old := CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE row_to_json(OLD)::jsonb END;
    v_new := CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE row_to_json(NEW)::jsonb END;

    -- Mask password hash: remove key entirely from audit record
    IF TG_TABLE_NAME = 'users' THEN
        v_old := v_old - 'password_hash';
        v_new := v_new - 'password_hash';
    END IF;

    -- Mask card vault token: log presence, not the token value
    IF TG_TABLE_NAME = 'card_details' THEN
        IF v_old IS NOT NULL AND v_old ? 'card_number_token' THEN
            v_old := jsonb_set(v_old, '{card_number_token}', '"[REDACTED]"');
        END IF;
        IF v_new IS NOT NULL AND v_new ? 'card_number_token' THEN
            v_new := jsonb_set(v_new, '{card_number_token}', '"[REDACTED]"');
        END IF;
    END IF;

    INSERT INTO audit_log (table_name, operation, changed_by, old_values, new_values)
    VALUES (
        TG_TABLE_NAME,
        TG_OP,
        current_user,
        v_old,
        v_new
    );
    RETURN NULL;  -- AFTER trigger; return value ignored
END;
$$;

-- ── updated_at helper (reuse V001 function if already present) ─
-- fn_set_updated_at() was created in V001; no redeclaration needed.

-- ── Users ─────────────────────────────────────────────────────
-- Stores PSP account holders. Passwords are NEVER stored in
-- plaintext; the application layer hashes before persisting.
CREATE TABLE users (
    user_id        UUID         NOT NULL DEFAULT gen_random_uuid(),
    username       VARCHAR(100) NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,   -- bcrypt / argon2id hash only
    email          VARCHAR(255) NOT NULL,
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_users            PRIMARY KEY (user_id),
    CONSTRAINT uq_users_username   UNIQUE (username),
    CONSTRAINT uq_users_email      UNIQUE (email),
    CONSTRAINT chk_users_email_fmt CHECK (
        email ~* '^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$'
    )
);

CREATE INDEX idx_users_email      ON users (email);
CREATE INDEX idx_users_username   ON users (username);
CREATE INDEX idx_users_is_active  ON users (is_active) WHERE is_active;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_audit_users
    AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW EXECUTE FUNCTION fn_psp_audit_log();

-- ── Card Details ───────────────────────────────────────────────
-- PCI DSS Requirements 3.2 / 3.3:
--   - Full PANs (card_number) must be tokenised before storage.
--   - CVV/CVC must NEVER be stored after authorisation.
--   - card_number_masked stores only the last-four suffix for
--     display purposes ("**** **** **** 4242").
--   - card_number_token is the vault reference returned by your
--     tokenisation provider (e.g. Vault, Stripe, Braintree).
CREATE TABLE card_details (
    card_id              UUID         NOT NULL DEFAULT gen_random_uuid(),
    user_id              UUID         NOT NULL,
    -- Tokenised PAN — references your card vault, never the raw PAN
    card_number_token    VARCHAR(255) NOT NULL,
    -- Display-safe masked suffix e.g. "**** **** **** 4242"
    card_number_masked   VARCHAR(19)  NOT NULL,
    -- CVV intentionally omitted: PCI DSS §3.2.2 prohibits post-auth storage
    expiry_date          DATE         NOT NULL,
    card_type            VARCHAR(50)  NOT NULL
                             CHECK (card_type IN
                                 ('VISA','MASTERCARD','AMEX','DISCOVER','OTHER')),
    billing_name         VARCHAR(255),
    is_default           BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active            BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_card_details         PRIMARY KEY (card_id),
    CONSTRAINT fk_card_details_user    FOREIGN KEY (user_id)
                                           REFERENCES users (user_id)
                                           ON DELETE RESTRICT,
    CONSTRAINT uq_card_number_token    UNIQUE (card_number_token)
);

CREATE INDEX idx_card_user_id       ON card_details (user_id);
CREATE INDEX idx_card_active        ON card_details (user_id, is_active)
                                        WHERE is_active;
CREATE INDEX idx_card_expiry        ON card_details (expiry_date);
CREATE INDEX idx_card_type          ON card_details (card_type);

CREATE TRIGGER trg_card_details_updated_at
    BEFORE UPDATE ON card_details
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_audit_card_details
    AFTER INSERT OR UPDATE OR DELETE ON card_details
    FOR EACH ROW EXECUTE FUNCTION fn_psp_audit_log();

-- ── Transactions ───────────────────────────────────────────────
-- Records every payment event. Status transitions:
--   PENDING -> PROCESSING -> COMPLETED
--                        -> FAILED
--   COMPLETED -> REFUNDED
--   COMPLETED -> REVERSED
--   COMPLETED -> DISPUTED
--
-- Isolation: all writes to this table MUST use SERIALIZABLE.
-- idempotency_key prevents duplicate charges from retries.
CREATE TABLE transactions (
    transaction_id   UUID          NOT NULL DEFAULT gen_random_uuid(),
    sender_id        UUID,
    receiver_id      UUID,
    card_id          UUID,
    amount           NUMERIC(19,4) NOT NULL CHECK (amount > 0),
    currency         CHAR(3)       NOT NULL DEFAULT 'USD',  -- ISO 4217
    -- "timestamp" per spec; named initiated_at to avoid reserved-word
    -- collision in PostgreSQL. Application alias: "timestamp".
    initiated_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    card_type        VARCHAR(50),
    status           VARCHAR(20)   NOT NULL DEFAULT 'PENDING'
                         CHECK (status IN
                             ('PENDING','PROCESSING','COMPLETED',
                              'FAILED','REFUNDED','REVERSED','DISPUTED')),
    reference_id     VARCHAR(255),   -- external PSP / acquirer reference
    idempotency_key  VARCHAR(255),   -- client-supplied, prevents double-charge
    failure_reason   TEXT,
    metadata         JSONB,
    completed_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_transactions          PRIMARY KEY (transaction_id),
    CONSTRAINT fk_txn_sender            FOREIGN KEY (sender_id)
                                            REFERENCES users (user_id)
                                            ON DELETE RESTRICT,
    CONSTRAINT fk_txn_receiver          FOREIGN KEY (receiver_id)
                                            REFERENCES users (user_id)
                                            ON DELETE RESTRICT,
    CONSTRAINT fk_txn_card              FOREIGN KEY (card_id)
                                            REFERENCES card_details (card_id)
                                            ON DELETE RESTRICT,
    CONSTRAINT uq_txn_idempotency_key   UNIQUE (idempotency_key),
    CONSTRAINT chk_txn_no_self_transfer CHECK (
        sender_id IS DISTINCT FROM receiver_id OR sender_id IS NULL
    )
);

-- Query columns: sender, receiver, card, status, time range, reference.
CREATE INDEX idx_txn_sender_id       ON transactions (sender_id);
CREATE INDEX idx_txn_receiver_id     ON transactions (receiver_id);
CREATE INDEX idx_txn_card_id         ON transactions (card_id);
CREATE INDEX idx_txn_status          ON transactions (status);
CREATE INDEX idx_txn_initiated_at    ON transactions (initiated_at DESC);
CREATE INDEX idx_txn_reference_id    ON transactions (reference_id);
CREATE INDEX idx_txn_card_type       ON transactions (card_type);
-- Composite: sender's transactions by status + time (most common query)
CREATE INDEX idx_txn_sender_status   ON transactions (sender_id,   status, initiated_at DESC);
CREATE INDEX idx_txn_receiver_status ON transactions (receiver_id, status, initiated_at DESC);
-- Partial: open/in-flight transactions (reconciliation scans)
CREATE INDEX idx_txn_open            ON transactions (initiated_at DESC)
                                         WHERE status IN ('PENDING','PROCESSING');

CREATE TRIGGER trg_transactions_updated_at
    BEFORE UPDATE ON transactions
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_audit_transactions
    AFTER INSERT OR UPDATE OR DELETE ON transactions
    FOR EACH ROW EXECUTE FUNCTION fn_psp_audit_log();

-- ── Register migration ────────────────────────────────────────
INSERT INTO schema_migrations (version, applied_at)
VALUES ('V002', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;
