-- =============================================================================
-- Elder Fall Detection — HIPAA-Compliant PostgreSQL 15 Schema
-- =============================================================================
-- Run as a superuser / migration role (bypasses RLS).
-- Application connections use the 'app_user' role (subject to RLS).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 0. Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pgcrypto;        -- pgp_sym_encrypt / decrypt, gen_random_uuid
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";     -- uuid_generate_v4 (fallback)


-- ---------------------------------------------------------------------------
-- 1. Roles
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_readonly') THEN
        CREATE ROLE app_readonly NOLOGIN;
    END IF;
END
$$;


-- ---------------------------------------------------------------------------
-- 2. Enum types
-- ---------------------------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE user_role_enum AS ENUM ('wearer', 'caregiver', 'admin');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE device_status_enum AS ENUM (
        'active', 'inactive', 'maintenance', 'decommissioned'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE severity_level_enum AS ENUM ('low', 'medium', 'high', 'critical');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE alert_status_enum AS ENUM (
        'pending', 'sent', 'acknowledged', 'resolved', 'false_positive'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ---------------------------------------------------------------------------
-- 3. Tables
-- ---------------------------------------------------------------------------

-- 3a. users ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id                       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    role                          user_role_enum NOT NULL,

    -- PII — encrypted with pgcrypto
    encrypted_name                BYTEA       NOT NULL,
    encrypted_email               BYTEA       NOT NULL,
    encrypted_phone               BYTEA,
    -- SHA-256 of plaintext email (hex) — used for UNIQUE lookups without decrypting
    email_hash                    TEXT        NOT NULL UNIQUE,
    -- JSON array: [{"name":"...","phone":"...","relationship":"..."}]
    encrypted_emergency_contacts  BYTEA,

    is_active                     BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_email_hash_format CHECK (email_hash ~ '^[0-9a-f]{64}$')
);

COMMENT ON TABLE  users IS 'System users: wearers, caregivers, and admins.';
COMMENT ON COLUMN users.encrypted_name  IS 'pgp_sym_encrypt(full_name, current_setting(app.encryption_key))';
COMMENT ON COLUMN users.encrypted_email IS 'pgp_sym_encrypt(email, current_setting(app.encryption_key))';
COMMENT ON COLUMN users.email_hash      IS 'encode(digest(email, sha256), hex) — not PII, used for uniqueness.';


-- 3b. devices ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS devices (
    device_id         UUID               PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id          UUID               NOT NULL
                                         REFERENCES users(user_id) ON DELETE RESTRICT,
    firmware_version  TEXT               NOT NULL,
    status            device_status_enum NOT NULL DEFAULT 'active',
    created_at        TIMESTAMPTZ        NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ        NOT NULL DEFAULT now(),

    CONSTRAINT chk_firmware_version CHECK (firmware_version ~ '^\d+\.\d+\.\d+$')
);

COMMENT ON TABLE  devices  IS 'Physical fall-detection wearables.';
COMMENT ON COLUMN devices.owner_id IS 'FK to the wearer (users.role = wearer).';


-- 3c. user_device_assignments  (M:N junction) --------------------------------
CREATE TABLE IF NOT EXISTS user_device_assignments (
    assignment_id  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID        NOT NULL REFERENCES users(user_id)   ON DELETE CASCADE,
    device_id      UUID        NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    assigned_by    UUID        REFERENCES users(user_id) ON DELETE SET NULL,
    assigned_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_user_device UNIQUE (user_id, device_id)
);

COMMENT ON TABLE user_device_assignments IS
    'Caregivers and admins assigned to monitor specific devices (M:N).';


-- 3d. fall_events -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS fall_events (
    event_id               UUID               PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id              UUID               NOT NULL
                                              REFERENCES devices(device_id) ON DELETE RESTRICT,
    timestamp              TIMESTAMPTZ        NOT NULL,
    -- Encrypted JSON: {"lat": 37.7749, "lon": -122.4194}
    encrypted_gps_coords   BYTEA,
    severity               severity_level_enum NOT NULL,
    alert_status           alert_status_enum   NOT NULL DEFAULT 'pending',
    -- Raw sensor snapshot — not PII, unencrypted for analytics
    accelerometer_data     JSONB,
    created_at             TIMESTAMPTZ        NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ        NOT NULL DEFAULT now()
);

COMMENT ON TABLE  fall_events IS 'Detected fall incidents. Cardinality: devices 1:N fall_events.';
COMMENT ON COLUMN fall_events.encrypted_gps_coords IS
    'pgp_sym_encrypt({"lat":...,"lon":...}::text, key) — PII, encrypted at rest.';


-- 3e. gps_history -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS gps_history (
    id          BIGSERIAL   PRIMARY KEY,
    device_id   UUID        NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    timestamp   TIMESTAMPTZ NOT NULL,
    -- PII — encrypted
    encrypted_lat  BYTEA   NOT NULL,
    encrypted_lon  BYTEA   NOT NULL,
    -- Accuracy in metres — not PII, kept plaintext for geofence queries
    accuracy    NUMERIC(8,3)
);

COMMENT ON TABLE  gps_history IS 'Continuous GPS telemetry. encrypted_lat/lon are PII.';
COMMENT ON COLUMN gps_history.encrypted_lat IS 'pgp_sym_encrypt(latitude::text, key)';
COMMENT ON COLUMN gps_history.encrypted_lon IS 'pgp_sym_encrypt(longitude::text, key)';


-- 3f. audit_log -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    log_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Free-form: user UUID string or "system:<subsystem>"
    actor       TEXT        NOT NULL,
    action      TEXT        NOT NULL,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Structured payload: changes, IP address, request ID, etc.
    details     JSONB,
    -- Polymorphic reference to the affected record
    target_id   UUID,
    target_type TEXT,

    -- Immutability guard: no UPDATE or DELETE via app_user
    CONSTRAINT audit_log_immutable CHECK (TRUE)  -- enforced via GRANT / RLS
);

COMMENT ON TABLE audit_log IS
    'Immutable HIPAA audit trail. Never UPDATE or DELETE rows from application code.';


-- ---------------------------------------------------------------------------
-- 4. Indexes
-- ---------------------------------------------------------------------------

-- Required by acceptance criteria
CREATE INDEX IF NOT EXISTS ix_fall_events_device_timestamp
    ON fall_events (device_id, timestamp);

CREATE INDEX IF NOT EXISTS ix_gps_history_device_timestamp
    ON gps_history (device_id, timestamp);

-- Supporting indexes
CREATE INDEX IF NOT EXISTS ix_devices_owner
    ON devices (owner_id);

CREATE INDEX IF NOT EXISTS ix_uda_device
    ON user_device_assignments (device_id);

CREATE INDEX IF NOT EXISTS ix_uda_user
    ON user_device_assignments (user_id);

CREATE INDEX IF NOT EXISTS ix_fall_events_alert_status
    ON fall_events (alert_status) WHERE alert_status IN ('pending', 'sent');

CREATE INDEX IF NOT EXISTS ix_audit_log_actor_timestamp
    ON audit_log (actor, timestamp);

CREATE INDEX IF NOT EXISTS ix_audit_log_target
    ON audit_log (target_type, target_id);


-- ---------------------------------------------------------------------------
-- 5. updated_at trigger
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
    RETURNS TRIGGER LANGUAGE plpgsql AS
$$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_users_updated_at     ON users;
DROP TRIGGER IF EXISTS trg_devices_updated_at   ON devices;
DROP TRIGGER IF EXISTS trg_fall_events_updated_at ON fall_events;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_devices_updated_at
    BEFORE UPDATE ON devices
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_fall_events_updated_at
    BEFORE UPDATE ON fall_events
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ---------------------------------------------------------------------------
-- 6. Row-Level Security
-- ---------------------------------------------------------------------------
-- Each protected table has FORCE ROW LEVEL SECURITY so even the table owner
-- cannot bypass policies unless connecting as a superuser.
--
-- Session variables (set per-transaction by the application):
--   app.user_id    — UUID of the authenticated user
--   app.user_role  — 'wearer' | 'caregiver' | 'admin'
-- ---------------------------------------------------------------------------

-- 6a. users table -----------------------------------------------------------
ALTER TABLE users ENABLE  ROW LEVEL SECURITY;
ALTER TABLE users FORCE   ROW LEVEL SECURITY;

DROP POLICY IF EXISTS users_select_policy ON users;
CREATE POLICY users_select_policy ON users
    FOR SELECT USING (
        current_setting('app.user_role', TRUE) = 'admin'
        OR user_id = current_setting('app.user_id', TRUE)::UUID
        -- Caregivers can see the wearers of their assigned devices
        OR (
            current_setting('app.user_role', TRUE) = 'caregiver'
            AND user_id IN (
                SELECT d.owner_id
                FROM   devices d
                JOIN   user_device_assignments uda ON uda.device_id = d.device_id
                WHERE  uda.user_id = current_setting('app.user_id', TRUE)::UUID
            )
        )
    );

DROP POLICY IF EXISTS users_insert_policy ON users;
CREATE POLICY users_insert_policy ON users
    FOR INSERT WITH CHECK (
        current_setting('app.user_role', TRUE) = 'admin'
    );

DROP POLICY IF EXISTS users_update_policy ON users;
CREATE POLICY users_update_policy ON users
    FOR UPDATE USING (
        current_setting('app.user_role', TRUE) = 'admin'
        OR user_id = current_setting('app.user_id', TRUE)::UUID
    );

DROP POLICY IF EXISTS users_delete_policy ON users;
CREATE POLICY users_delete_policy ON users
    FOR DELETE USING (
        current_setting('app.user_role', TRUE) = 'admin'
    );


-- 6b. devices table ---------------------------------------------------------
ALTER TABLE devices ENABLE  ROW LEVEL SECURITY;
ALTER TABLE devices FORCE   ROW LEVEL SECURITY;

DROP POLICY IF EXISTS devices_select_policy ON devices;
CREATE POLICY devices_select_policy ON devices
    FOR SELECT USING (
        -- Admins see all
        current_setting('app.user_role', TRUE) = 'admin'
        -- Wearers see their own device
        OR (
            current_setting('app.user_role', TRUE) = 'wearer'
            AND owner_id = current_setting('app.user_id', TRUE)::UUID
        )
        -- Caregivers see only assigned devices
        OR (
            current_setting('app.user_role', TRUE) = 'caregiver'
            AND device_id IN (
                SELECT device_id
                FROM   user_device_assignments
                WHERE  user_id = current_setting('app.user_id', TRUE)::UUID
            )
        )
    );

DROP POLICY IF EXISTS devices_insert_policy ON devices;
CREATE POLICY devices_insert_policy ON devices
    FOR INSERT WITH CHECK (
        current_setting('app.user_role', TRUE) = 'admin'
    );

DROP POLICY IF EXISTS devices_update_policy ON devices;
CREATE POLICY devices_update_policy ON devices
    FOR UPDATE USING (
        current_setting('app.user_role', TRUE) = 'admin'
    );

DROP POLICY IF EXISTS devices_delete_policy ON devices;
CREATE POLICY devices_delete_policy ON devices
    FOR DELETE USING (
        current_setting('app.user_role', TRUE) = 'admin'
    );


-- 6c. user_device_assignments -----------------------------------------------
ALTER TABLE user_device_assignments ENABLE  ROW LEVEL SECURITY;
ALTER TABLE user_device_assignments FORCE   ROW LEVEL SECURITY;

DROP POLICY IF EXISTS uda_select_policy ON user_device_assignments;
CREATE POLICY uda_select_policy ON user_device_assignments
    FOR SELECT USING (
        current_setting('app.user_role', TRUE) = 'admin'
        OR user_id = current_setting('app.user_id', TRUE)::UUID
        OR device_id IN (
            SELECT device_id FROM user_device_assignments
            WHERE  user_id = current_setting('app.user_id', TRUE)::UUID
        )
    );

DROP POLICY IF EXISTS uda_insert_policy ON user_device_assignments;
CREATE POLICY uda_insert_policy ON user_device_assignments
    FOR INSERT WITH CHECK (
        current_setting('app.user_role', TRUE) = 'admin'
    );

DROP POLICY IF EXISTS uda_delete_policy ON user_device_assignments;
CREATE POLICY uda_delete_policy ON user_device_assignments
    FOR DELETE USING (
        current_setting('app.user_role', TRUE) = 'admin'
    );


-- 6d. fall_events -----------------------------------------------------------
ALTER TABLE fall_events ENABLE  ROW LEVEL SECURITY;
ALTER TABLE fall_events FORCE   ROW LEVEL SECURITY;

DROP POLICY IF EXISTS fall_events_select_policy ON fall_events;
CREATE POLICY fall_events_select_policy ON fall_events
    FOR SELECT USING (
        current_setting('app.user_role', TRUE) = 'admin'
        OR device_id IN (
            SELECT device_id FROM devices
            WHERE  owner_id = current_setting('app.user_id', TRUE)::UUID
              AND  current_setting('app.user_role', TRUE) = 'wearer'
        )
        OR (
            current_setting('app.user_role', TRUE) = 'caregiver'
            AND device_id IN (
                SELECT device_id FROM user_device_assignments
                WHERE  user_id = current_setting('app.user_id', TRUE)::UUID
            )
        )
    );

DROP POLICY IF EXISTS fall_events_insert_policy ON fall_events;
CREATE POLICY fall_events_insert_policy ON fall_events
    FOR INSERT WITH CHECK (
        -- Only system role (MQTT ingester) and admins insert
        current_setting('app.user_role', TRUE) IN ('admin', 'system')
    );

DROP POLICY IF EXISTS fall_events_update_policy ON fall_events;
CREATE POLICY fall_events_update_policy ON fall_events
    FOR UPDATE USING (
        current_setting('app.user_role', TRUE) IN ('admin', 'caregiver', 'system')
        AND (
            current_setting('app.user_role', TRUE) = 'admin'
            OR device_id IN (
                SELECT device_id FROM user_device_assignments
                WHERE  user_id = current_setting('app.user_id', TRUE)::UUID
            )
        )
    );


-- 6e. gps_history -----------------------------------------------------------
ALTER TABLE gps_history ENABLE  ROW LEVEL SECURITY;
ALTER TABLE gps_history FORCE   ROW LEVEL SECURITY;

DROP POLICY IF EXISTS gps_history_select_policy ON gps_history;
CREATE POLICY gps_history_select_policy ON gps_history
    FOR SELECT USING (
        current_setting('app.user_role', TRUE) = 'admin'
        OR device_id IN (
            SELECT device_id FROM devices
            WHERE  owner_id = current_setting('app.user_id', TRUE)::UUID
              AND  current_setting('app.user_role', TRUE) = 'wearer'
        )
        OR (
            current_setting('app.user_role', TRUE) = 'caregiver'
            AND device_id IN (
                SELECT device_id FROM user_device_assignments
                WHERE  user_id = current_setting('app.user_id', TRUE)::UUID
            )
        )
    );

DROP POLICY IF EXISTS gps_history_insert_policy ON gps_history;
CREATE POLICY gps_history_insert_policy ON gps_history
    FOR INSERT WITH CHECK (
        current_setting('app.user_role', TRUE) IN ('admin', 'system')
    );


-- 6f. audit_log — append-only for app_user ---------------------------------
ALTER TABLE audit_log ENABLE  ROW LEVEL SECURITY;
ALTER TABLE audit_log FORCE   ROW LEVEL SECURITY;

DROP POLICY IF EXISTS audit_log_select_policy ON audit_log;
CREATE POLICY audit_log_select_policy ON audit_log
    FOR SELECT USING (
        current_setting('app.user_role', TRUE) = 'admin'
        OR actor = current_setting('app.user_id', TRUE)
    );

DROP POLICY IF EXISTS audit_log_insert_policy ON audit_log;
CREATE POLICY audit_log_insert_policy ON audit_log
    FOR INSERT WITH CHECK (TRUE);  -- any authenticated session may append

-- No UPDATE / DELETE policy → effectively blocked for app_user


-- ---------------------------------------------------------------------------
-- 7. Grants to app_user
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA public TO app_user;

GRANT SELECT, INSERT, UPDATE ON users                  TO app_user;
GRANT SELECT, INSERT, UPDATE ON devices                TO app_user;
GRANT SELECT, INSERT, DELETE ON user_device_assignments TO app_user;
GRANT SELECT, INSERT, UPDATE ON fall_events            TO app_user;
GRANT SELECT, INSERT         ON gps_history            TO app_user;
GRANT SELECT, INSERT         ON audit_log              TO app_user;
GRANT USAGE, SELECT ON SEQUENCE gps_history_id_seq     TO app_user;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_readonly;


-- ---------------------------------------------------------------------------
-- 8. Database-level encryption_key default (override per session in app)
-- ---------------------------------------------------------------------------
-- In production set this via your secrets manager, not here.
-- ALTER DATABASE elder_fall_detection SET app.encryption_key = '<your-secret>';
-- The application overrides it per-transaction via set_config('app.encryption_key', key, true).
