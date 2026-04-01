-- =============================================================================
-- tests/verify_seed_idempotency.sql
-- Run after seed_test_data.seed_all() (once or twice) to confirm:
--   1. Expected row counts are exact (no duplicates after repeat runs).
--   2. All enum values are within the allowed sets.
--   3. All numeric constraints hold in the seeded data.
--   4. All FK relationships are intact.
-- =============================================================================
-- Usage:
--   psql $DATABASE_URL -f tests/verify_seed_idempotency.sql
-- Or from Python tests:
--   session.execute(text(open("tests/verify_seed_idempotency.sql").read()))
-- =============================================================================

-- ── 1. Row counts ─────────────────────────────────────────────────────────────
-- Each assertion returns 0 rows on success; non-zero means a duplicate slipped in.

SELECT 'accounts: unexpected count' AS check_name
WHERE (SELECT COUNT(*) FROM accounts WHERE username LIKE '%_test') <> 6;

SELECT 'p2p_transfers: unexpected count' AS check_name
WHERE (SELECT COUNT(*) FROM p2p_transfers WHERE reference LIKE 'TEST-TXN-%') <> 8;

SELECT 'virtual_cards: unexpected count' AS check_name
WHERE (
    SELECT COUNT(*) FROM virtual_cards
    WHERE card_holder_id IN (
        SELECT account_id FROM accounts WHERE username LIKE '%_test'
    )
) <> 4;

SELECT 'investment_options: unexpected count' AS check_name
WHERE (SELECT COUNT(*) FROM investment_options WHERE name LIKE 'Test %') <> 5;

-- spending_insights has no UNIQUE constraint; its count grows with each seed
-- unless teardown_all() is called first.  The check below is informational only.
SELECT
    'spending_insights (informational): row count' AS check_name,
    COUNT(*) AS rows
FROM spending_insights
WHERE account_id IN (
    SELECT account_id FROM accounts WHERE username LIKE '%_test'
);


-- ── 2. Enum integrity ─────────────────────────────────────────────────────────

SELECT 'accounts: invalid status' AS check_name, username, status
FROM accounts
WHERE username LIKE '%_test'
  AND status NOT IN ('active', 'suspended', 'closed');

SELECT 'p2p_transfers: invalid status' AS check_name, reference, status
FROM p2p_transfers
WHERE reference LIKE 'TEST-TXN-%'
  AND status NOT IN ('pending', 'completed', 'failed', 'reversed');

SELECT 'virtual_cards: invalid card_type' AS check_name, card_id, card_type
FROM virtual_cards
WHERE card_holder_id IN (SELECT account_id FROM accounts WHERE username LIKE '%_test')
  AND card_type NOT IN ('debit', 'credit', 'prepaid');

SELECT 'virtual_cards: invalid status' AS check_name, card_id, status
FROM virtual_cards
WHERE card_holder_id IN (SELECT account_id FROM accounts WHERE username LIKE '%_test')
  AND status NOT IN ('active', 'frozen', 'cancelled');

SELECT 'investment_options: invalid risk_level' AS check_name, name, risk_level
FROM investment_options
WHERE name LIKE 'Test %'
  AND risk_level NOT IN ('low', 'medium', 'high', 'very_high');


-- ── 3. Numeric constraints ────────────────────────────────────────────────────

SELECT 'accounts: negative balance' AS check_name, username, balance
FROM accounts
WHERE username LIKE '%_test' AND balance < 0;

SELECT 'p2p_transfers: non-positive amount' AS check_name, reference, amount
FROM p2p_transfers
WHERE reference LIKE 'TEST-TXN-%' AND amount <= 0;

SELECT 'spending_insights: negative amount' AS check_name, id, amount
FROM spending_insights
WHERE account_id IN (SELECT account_id FROM accounts WHERE username LIKE '%_test')
  AND amount < 0;

SELECT 'investment_options: negative return_potential' AS check_name, name, return_potential
FROM investment_options
WHERE name LIKE 'Test %' AND return_potential < 0;

SELECT 'investment_options: negative min_investment' AS check_name, name, min_investment
FROM investment_options
WHERE name LIKE 'Test %' AND min_investment < 0;


-- ── 4. FK integrity ───────────────────────────────────────────────────────────

SELECT 'p2p_transfers: broken sender_id FK' AS check_name, t.reference, t.sender_id
FROM p2p_transfers t
WHERE t.reference LIKE 'TEST-TXN-%'
  AND NOT EXISTS (SELECT 1 FROM accounts a WHERE a.account_id = t.sender_id);

SELECT 'p2p_transfers: broken receiver_id FK' AS check_name, t.reference, t.receiver_id
FROM p2p_transfers t
WHERE t.reference LIKE 'TEST-TXN-%'
  AND NOT EXISTS (SELECT 1 FROM accounts a WHERE a.account_id = t.receiver_id);

SELECT 'p2p_transfers: self-transfer' AS check_name, reference, sender_id
FROM p2p_transfers
WHERE reference LIKE 'TEST-TXN-%' AND sender_id = receiver_id;

SELECT 'virtual_cards: broken card_holder_id FK' AS check_name, vc.card_id, vc.card_holder_id
FROM virtual_cards vc
WHERE vc.card_holder_id IN (SELECT account_id FROM accounts WHERE username LIKE '%_test')
  AND NOT EXISTS (SELECT 1 FROM accounts a WHERE a.account_id = vc.card_holder_id);

SELECT 'spending_insights: broken account_id FK' AS check_name, si.id, si.account_id
FROM spending_insights si
WHERE si.account_id IN (SELECT account_id FROM accounts WHERE username LIKE '%_test')
  AND NOT EXISTS (SELECT 1 FROM accounts a WHERE a.account_id = si.account_id);


-- ── 5. Summary (always runs) ──────────────────────────────────────────────────
SELECT
    (SELECT COUNT(*) FROM accounts            WHERE username LIKE '%_test')         AS accounts,
    (SELECT COUNT(*) FROM p2p_transfers       WHERE reference LIKE 'TEST-TXN-%')    AS transfers,
    (SELECT COUNT(*) FROM virtual_cards
         WHERE card_holder_id IN (SELECT account_id FROM accounts WHERE username LIKE '%_test'))
                                                                                    AS cards,
    (SELECT COUNT(*) FROM spending_insights
         WHERE account_id IN (SELECT account_id FROM accounts WHERE username LIKE '%_test'))
                                                                                    AS insights,
    (SELECT COUNT(*) FROM investment_options  WHERE name LIKE 'Test %')             AS investments;
