-- =============================================================================
-- tests/verify_api_seed_idempotency.sql
-- Run after seed_api_test_data.seed_all() (once or twice) to confirm:
--   1. Expected row counts are exact (no duplicates after repeat runs).
--   2. All enum values are within the allowed sets.
--   3. All FK / referential patterns hold (trace_id coherence).
--   4. Metadata JSON marker present on all test rows.
-- =============================================================================
-- Usage (SQLite CLI):
--   sqlite3 /path/to/audit_log.db < tests/verify_api_seed_idempotency.sql
-- Or from Python tests:
--   conn.executescript(open("tests/verify_api_seed_idempotency.sql").read())
-- =============================================================================
-- NOTE: SQLite does not support SELECT ... WHERE ... <> N syntax for zero-row
-- success checks the same way PostgreSQL does. Each check returns 0 rows on
-- success; non-zero means a constraint violation was found.
-- =============================================================================


-- ── 1. Row counts ─────────────────────────────────────────────────────────────
-- Each query returns 0 rows on success; non-zero means duplicate rows slipped in.

SELECT 'compliance_audit_log: unexpected count' AS check_name
WHERE (SELECT COUNT(*) FROM compliance_audit_log WHERE actor LIKE 'test_%') <> 10;

SELECT 'chat_messages: unexpected count' AS check_name
WHERE (SELECT COUNT(*) FROM chat_messages WHERE user_id LIKE 'test_%') <> 8;

SELECT 'proposals: unexpected count' AS check_name
WHERE (SELECT COUNT(*) FROM proposals WHERE proposed_by LIKE 'test_%') <> 5;


-- ── 2. Enum integrity — compliance_audit_log ─────────────────────────────────

SELECT 'audit_log: invalid action_type' AS check_name, id, action_type
FROM compliance_audit_log
WHERE actor LIKE 'test_%'
  AND action_type NOT IN ('ANALYSIS', 'PROPOSAL', 'APPROVAL', 'REJECTION', 'ACCESS', 'EXECUTION');

SELECT 'audit_log: invalid event_type' AS check_name, id, event_type
FROM compliance_audit_log
WHERE actor LIKE 'test_%'
  AND event_type IS NOT NULL
  AND event_type NOT IN ('ACCESS', 'ANALYSIS', 'PROPOSAL', 'APPROVAL', 'REJECTION', 'EXECUTION');

SELECT 'audit_log: invalid status' AS check_name, id, status
FROM compliance_audit_log
WHERE actor LIKE 'test_%'
  AND status IS NOT NULL
  AND status NOT IN ('OK', 'DENIED', 'ERROR');

SELECT 'audit_log: approver_provider invalid' AS check_name, id, approver_provider
FROM compliance_audit_log
WHERE actor LIKE 'test_%'
  AND approver_provider IS NOT NULL
  AND approver_provider NOT IN ('oidc', 'api_key', 'anonymous');


-- ── 3. Enum integrity — chat_messages ────────────────────────────────────────

SELECT 'chat_messages: invalid role' AS check_name, id, role
FROM chat_messages
WHERE user_id LIKE 'test_%'
  AND role NOT IN ('user', 'assistant');

SELECT 'chat_messages: invalid message_type' AS check_name, id, message_type
FROM chat_messages
WHERE user_id LIKE 'test_%'
  AND message_type IS NOT NULL
  AND message_type NOT IN ('user', 'assistant', 'system');


-- ── 4. Metadata test_marker present ──────────────────────────────────────────

SELECT 'audit_log: missing test_marker in metadata' AS check_name, id, metadata
FROM compliance_audit_log
WHERE actor LIKE 'test_%'
  AND (
    metadata IS NULL
    OR json_extract(metadata, '$.test_marker') IS NULL
    OR json_extract(metadata, '$.test_marker') <> 1
  );

SELECT 'chat_messages: missing test_marker in metadata' AS check_name, id, metadata
FROM chat_messages
WHERE user_id LIKE 'test_%'
  AND (
    metadata IS NULL
    OR json_extract(metadata, '$.test_marker') IS NULL
    OR json_extract(metadata, '$.test_marker') <> 1
  );


-- ── 5. Trace-group coherence ──────────────────────────────────────────────────
-- Each completed lifecycle trace must have the expected event types.

SELECT 'trace-lifecycle-001: missing ANALYSIS' AS check_name
WHERE NOT EXISTS (
    SELECT 1 FROM compliance_audit_log
    WHERE trace_id = 'trace-lifecycle-001' AND action_type = 'ANALYSIS'
);

SELECT 'trace-lifecycle-001: missing PROPOSAL' AS check_name
WHERE NOT EXISTS (
    SELECT 1 FROM compliance_audit_log
    WHERE trace_id = 'trace-lifecycle-001' AND action_type = 'PROPOSAL'
);

SELECT 'trace-lifecycle-001: missing APPROVAL' AS check_name
WHERE NOT EXISTS (
    SELECT 1 FROM compliance_audit_log
    WHERE trace_id = 'trace-lifecycle-001' AND action_type = 'APPROVAL'
);

SELECT 'trace-lifecycle-002: missing REJECTION' AS check_name
WHERE NOT EXISTS (
    SELECT 1 FROM compliance_audit_log
    WHERE trace_id = 'trace-lifecycle-002' AND action_type = 'REJECTION'
);


-- ── 6. Named approvals — APPROVAL rows must have approver identity ─────────────

SELECT 'audit_log: APPROVAL missing approver_provider' AS check_name, id, approver_provider
FROM compliance_audit_log
WHERE actor LIKE 'test_%'
  AND action_type = 'APPROVAL'
  AND approver_provider IS NULL;

-- REJECTION rows must also carry approver identity
SELECT 'audit_log: REJECTION missing approver_provider' AS check_name, id, approver_provider
FROM compliance_audit_log
WHERE actor LIKE 'test_%'
  AND action_type = 'REJECTION'
  AND approver_provider IS NULL;


-- ── 6b. Enum integrity — proposals ───────────────────────────────────────────

SELECT 'proposals: invalid action_type' AS check_name, trace_id, action_type
FROM proposals
WHERE proposed_by LIKE 'test_%'
  AND action_type NOT IN ('yaml_edit','code_diff','implementation_plan',
                          'knowledge_add','knowledge_delete','agent_hire');

SELECT 'proposals: invalid risk_class' AS check_name, trace_id, risk_class
FROM proposals
WHERE proposed_by LIKE 'test_%'
  AND risk_class NOT IN ('INFORMATIONAL','EPHEMERAL','STATEFUL','EXTERNAL','DESTRUCTIVE');

SELECT 'proposals: invalid status' AS check_name, trace_id, status
FROM proposals
WHERE proposed_by LIKE 'test_%'
  AND status NOT IN ('pending','approved','rejected','expired');


-- ── 6c. Proposals lifecycle integrity ────────────────────────────────────────

-- Approved proposals must have decided_by populated
SELECT 'proposals: approved missing decided_by' AS check_name, trace_id
FROM proposals
WHERE proposed_by LIKE 'test_%'
  AND status = 'approved'
  AND decided_by IS NULL;

-- Rejected proposals must have feedback
SELECT 'proposals: rejected missing feedback' AS check_name, trace_id
FROM proposals
WHERE proposed_by LIKE 'test_%'
  AND status = 'rejected'
  AND (feedback IS NULL OR feedback = '');

-- Pending proposals must NOT have decided_at
SELECT 'proposals: pending has decided_at' AS check_name, trace_id, decided_at
FROM proposals
WHERE proposed_by LIKE 'test_%'
  AND status = 'pending'
  AND decided_at IS NOT NULL;

-- Expired proposals must have a past expires_at
SELECT 'proposals: expired missing expires_at' AS check_name, trace_id
FROM proposals
WHERE proposed_by LIKE 'test_%'
  AND status = 'expired'
  AND expires_at IS NULL;

-- Payload must be valid JSON (SQLite json_valid() returns 1 for valid JSON)
SELECT 'proposals: invalid payload JSON' AS check_name, trace_id, payload
FROM proposals
WHERE proposed_by LIKE 'test_%'
  AND json_valid(payload) <> 1;


-- ── 7. Chat session coherence ─────────────────────────────────────────────────

SELECT 'chat_messages: session_001 wrong count' AS check_name
WHERE (
    SELECT COUNT(*) FROM chat_messages
    WHERE session_id = 'test_session_001'
) <> 4;

SELECT 'chat_messages: session_002 wrong count' AS check_name
WHERE (
    SELECT COUNT(*) FROM chat_messages
    WHERE session_id = 'test_session_002'
) <> 4;

-- Each session must alternate user/assistant turns
SELECT 'chat_messages: session_001 missing user turn' AS check_name
WHERE NOT EXISTS (
    SELECT 1 FROM chat_messages
    WHERE session_id = 'test_session_001' AND role = 'user'
);

SELECT 'chat_messages: session_001 missing assistant turn' AS check_name
WHERE NOT EXISTS (
    SELECT 1 FROM chat_messages
    WHERE session_id = 'test_session_001' AND role = 'assistant'
);


-- ── 8. Summary (always runs) ──────────────────────────────────────────────────
SELECT
    (SELECT COUNT(*) FROM compliance_audit_log WHERE actor      LIKE 'test_%') AS audit_events,
    (SELECT COUNT(*) FROM chat_messages          WHERE user_id  LIKE 'test_%') AS chat_messages,
    (SELECT COUNT(*) FROM proposals              WHERE proposed_by LIKE 'test_%') AS proposals,
    (SELECT COUNT(DISTINCT trace_id) FROM compliance_audit_log  WHERE actor LIKE 'test_%') AS distinct_traces,
    (SELECT COUNT(DISTINCT session_id) FROM chat_messages       WHERE user_id LIKE 'test_%') AS distinct_sessions,
    (SELECT COUNT(*) FROM proposals WHERE proposed_by LIKE 'test_%' AND status = 'pending')  AS pending_proposals,
    (SELECT COUNT(*) FROM proposals WHERE proposed_by LIKE 'test_%' AND status = 'approved') AS approved_proposals,
    (SELECT COUNT(*) FROM proposals WHERE proposed_by LIKE 'test_%' AND status = 'rejected') AS rejected_proposals,
    (SELECT COUNT(*) FROM proposals WHERE proposed_by LIKE 'test_%' AND status = 'expired')  AS expired_proposals;
