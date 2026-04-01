-- =============================================================================
-- Document Ingestion Pipeline — DDL
-- Idempotent: all statements use IF NOT EXISTS / ON CONFLICT DO NOTHING
-- Supports: invoices, receipts, contracts
-- Schema version: 1.0.0
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Metadata / audit
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id          TEXT        PRIMARY KEY,
    source_type     TEXT        NOT NULL CHECK (source_type IN ('invoice','receipt','contract')),
    started_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at     TIMESTAMP,
    records_read    INTEGER     DEFAULT 0,
    records_written INTEGER     DEFAULT 0,
    records_failed  INTEGER     DEFAULT 0,
    status          TEXT        NOT NULL DEFAULT 'running'
                                CHECK (status IN ('running','success','partial','failed')),
    error_message   TEXT
);

CREATE TABLE IF NOT EXISTS ingestion_errors (
    error_id        SERIAL      PRIMARY KEY,
    run_id          TEXT        REFERENCES pipeline_runs(run_id),
    source_file     TEXT,
    raw_record      JSONB,
    error_type      TEXT        NOT NULL,
    error_detail    TEXT,
    occurred_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- Reference / lookup
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS currencies (
    code    CHAR(3) PRIMARY KEY,
    name    TEXT    NOT NULL
);

INSERT INTO currencies (code, name) VALUES
    ('USD','US Dollar'), ('EUR','Euro'), ('GBP','British Pound'),
    ('JPY','Japanese Yen'), ('CAD','Canadian Dollar')
ON CONFLICT (code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Vendors / counterparties (shared across document types)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS parties (
    party_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     TEXT        UNIQUE,          -- source system ID
    name            TEXT        NOT NULL,
    tax_id          TEXT,
    address         JSONB,
    contact         JSONB,
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_parties_external_id ON parties(external_id);
CREATE INDEX IF NOT EXISTS idx_parties_name        ON parties(name);

-- ---------------------------------------------------------------------------
-- INVOICES
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     TEXT        UNIQUE NOT NULL,    -- dedup key
    invoice_number  TEXT        NOT NULL,
    vendor_id       UUID        REFERENCES parties(party_id),
    customer_id     UUID        REFERENCES parties(party_id),
    invoice_date    DATE        NOT NULL,
    due_date        DATE,
    currency        CHAR(3)     REFERENCES currencies(code),
    subtotal        NUMERIC(18,4),
    tax_amount      NUMERIC(18,4),
    discount_amount NUMERIC(18,4) DEFAULT 0,
    total_amount    NUMERIC(18,4) NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'draft'
                                CHECK (status IN ('draft','sent','paid','overdue','cancelled','void')),
    payment_terms   TEXT,
    notes           TEXT,
    source_file     TEXT,
    raw_data        JSONB,
    ingested_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoice_line_items (
    line_id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id      UUID        NOT NULL REFERENCES invoices(invoice_id) ON DELETE CASCADE,
    line_number     INTEGER     NOT NULL,
    description     TEXT        NOT NULL,
    quantity        NUMERIC(12,4) NOT NULL DEFAULT 1,
    unit_price      NUMERIC(18,4) NOT NULL,
    unit            TEXT,
    tax_rate        NUMERIC(6,4) DEFAULT 0,
    line_total      NUMERIC(18,4) NOT NULL,
    gl_account      TEXT,
    cost_center     TEXT,
    UNIQUE (invoice_id, line_number)
);

CREATE INDEX IF NOT EXISTS idx_invoices_vendor       ON invoices(vendor_id);
CREATE INDEX IF NOT EXISTS idx_invoices_date         ON invoices(invoice_date);
CREATE INDEX IF NOT EXISTS idx_invoices_status       ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoice_lines_invoice ON invoice_line_items(invoice_id);

-- ---------------------------------------------------------------------------
-- RECEIPTS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS receipts (
    receipt_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     TEXT        UNIQUE NOT NULL,    -- dedup key
    receipt_number  TEXT,
    merchant_id     UUID        REFERENCES parties(party_id),
    transaction_date DATE       NOT NULL,
    transaction_time TIME,
    currency        CHAR(3)     REFERENCES currencies(code),
    subtotal        NUMERIC(18,4),
    tax_amount      NUMERIC(18,4) DEFAULT 0,
    tip_amount      NUMERIC(18,4) DEFAULT 0,
    total_amount    NUMERIC(18,4) NOT NULL,
    payment_method  TEXT        CHECK (payment_method IN
                                    ('cash','credit_card','debit_card','digital_wallet',
                                     'check','bank_transfer','other','unknown')),
    card_last_four  CHAR(4),
    category        TEXT,
    expense_report  TEXT,
    reimbursable    BOOLEAN     DEFAULT FALSE,
    source_file     TEXT,
    raw_data        JSONB,
    ingested_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS receipt_line_items (
    line_id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_id      UUID        NOT NULL REFERENCES receipts(receipt_id) ON DELETE CASCADE,
    line_number     INTEGER     NOT NULL,
    description     TEXT        NOT NULL,
    quantity        NUMERIC(12,4) DEFAULT 1,
    unit_price      NUMERIC(18,4) NOT NULL,
    line_total      NUMERIC(18,4) NOT NULL,
    category        TEXT,
    UNIQUE (receipt_id, line_number)
);

CREATE INDEX IF NOT EXISTS idx_receipts_merchant     ON receipts(merchant_id);
CREATE INDEX IF NOT EXISTS idx_receipts_date         ON receipts(transaction_date);
CREATE INDEX IF NOT EXISTS idx_receipts_category     ON receipts(category);

-- ---------------------------------------------------------------------------
-- CONTRACTS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS contracts (
    contract_id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id         TEXT    UNIQUE NOT NULL,    -- dedup key
    contract_number     TEXT    NOT NULL,
    title               TEXT    NOT NULL,
    contract_type       TEXT    NOT NULL
                                CHECK (contract_type IN
                                    ('msa','nda','sow','purchase_order','lease','employment',
                                     'license','service_agreement','partnership','other')),
    status              TEXT    NOT NULL DEFAULT 'draft'
                                CHECK (status IN
                                    ('draft','review','negotiation','active','expired',
                                     'terminated','renewed')),
    effective_date      DATE,
    expiration_date     DATE,
    auto_renew          BOOLEAN DEFAULT FALSE,
    renewal_notice_days INTEGER,
    contract_value      NUMERIC(18,4),
    currency            CHAR(3) REFERENCES currencies(code),
    governing_law       TEXT,
    jurisdiction        TEXT,
    summary             TEXT,
    key_obligations     JSONB,  -- [{party, obligation, due_date}, ...]
    payment_schedule    JSONB,  -- [{amount, due_date, milestone}, ...]
    source_file         TEXT,
    raw_data            JSONB,
    ingested_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contract_parties (
    id              SERIAL      PRIMARY KEY,
    contract_id     UUID        NOT NULL REFERENCES contracts(contract_id) ON DELETE CASCADE,
    party_id        UUID        NOT NULL REFERENCES parties(party_id),
    role            TEXT        NOT NULL CHECK (role IN ('buyer','seller','licensor','licensee',
                                                         'employer','employee','lessor','lessee',
                                                         'service_provider','client','other')),
    signatory_name  TEXT,
    signed_at       TIMESTAMP,
    signature_valid BOOLEAN,
    UNIQUE (contract_id, party_id, role)
);

CREATE TABLE IF NOT EXISTS contract_clauses (
    clause_id       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id     UUID        NOT NULL REFERENCES contracts(contract_id) ON DELETE CASCADE,
    clause_number   TEXT        NOT NULL,
    clause_type     TEXT,       -- 'payment','termination','liability','ip','confidentiality',...
    title           TEXT,
    body            TEXT        NOT NULL,
    risk_flag       BOOLEAN     DEFAULT FALSE,
    risk_notes      TEXT,
    UNIQUE (contract_id, clause_number)
);

CREATE INDEX IF NOT EXISTS idx_contracts_type       ON contracts(contract_type);
CREATE INDEX IF NOT EXISTS idx_contracts_status     ON contracts(status);
CREATE INDEX IF NOT EXISTS idx_contracts_expiry     ON contracts(expiration_date);
CREATE INDEX IF NOT EXISTS idx_contract_parties_c   ON contract_parties(contract_id);
CREATE INDEX IF NOT EXISTS idx_contract_clauses_c   ON contract_clauses(contract_id);

-- ---------------------------------------------------------------------------
-- Validation log (written by Python validation layer)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS validation_results (
    id              SERIAL      PRIMARY KEY,
    run_id          TEXT        REFERENCES pipeline_runs(run_id),
    document_type   TEXT        NOT NULL,
    external_id     TEXT        NOT NULL,
    rule_name       TEXT        NOT NULL,
    passed          BOOLEAN     NOT NULL,
    message         TEXT,
    severity        TEXT        NOT NULL DEFAULT 'error'
                                CHECK (severity IN ('info','warning','error','critical')),
    checked_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_val_run          ON validation_results(run_id);
CREATE INDEX IF NOT EXISTS idx_val_doc          ON validation_results(document_type, external_id);
CREATE INDEX IF NOT EXISTS idx_val_failed       ON validation_results(passed) WHERE NOT passed;
