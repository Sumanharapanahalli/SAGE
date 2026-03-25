"""Initial HIPAA-compliant schema for elder_fall_detection.

Creates all 5 tables, enum types, indexes, RLS policies, updated_at triggers,
and role grants.  Runs pgcrypto + uuid-ossp extensions as prerequisites.

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-03-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Extensions
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ------------------------------------------------------------------
    # Roles (idempotent)
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                CREATE ROLE app_user NOLOGIN;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_readonly') THEN
                CREATE ROLE app_readonly NOLOGIN;
            END IF;
        END
        $$
        """
    )

    # ------------------------------------------------------------------
    # Enum types
    # ------------------------------------------------------------------
    user_role_enum = postgresql.ENUM(
        "wearer", "caregiver", "admin", name="user_role_enum", create_type=False
    )
    device_status_enum = postgresql.ENUM(
        "active", "inactive", "maintenance", "decommissioned",
        name="device_status_enum", create_type=False,
    )
    severity_level_enum = postgresql.ENUM(
        "low", "medium", "high", "critical",
        name="severity_level_enum", create_type=False,
    )
    alert_status_enum = postgresql.ENUM(
        "pending", "sent", "acknowledged", "resolved", "false_positive",
        name="alert_status_enum", create_type=False,
    )

    op.execute("CREATE TYPE user_role_enum AS ENUM ('wearer', 'caregiver', 'admin')")
    op.execute(
        "CREATE TYPE device_status_enum AS ENUM "
        "('active', 'inactive', 'maintenance', 'decommissioned')"
    )
    op.execute(
        "CREATE TYPE severity_level_enum AS ENUM ('low', 'medium', 'high', 'critical')"
    )
    op.execute(
        "CREATE TYPE alert_status_enum AS ENUM "
        "('pending', 'sent', 'acknowledged', 'resolved', 'false_positive')"
    )

    # ------------------------------------------------------------------
    # Table: users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("role", user_role_enum, nullable=False),
        sa.Column("encrypted_name", sa.LargeBinary, nullable=False),
        sa.Column("encrypted_email", sa.LargeBinary, nullable=False),
        sa.Column("encrypted_phone", sa.LargeBinary, nullable=True),
        sa.Column("email_hash", sa.Text, nullable=False, unique=True),
        sa.Column("encrypted_emergency_contacts", sa.LargeBinary, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "email_hash ~ '^[0-9a-f]{64}$'", name="chk_email_hash_format"
        ),
    )

    # ------------------------------------------------------------------
    # Table: devices
    # ------------------------------------------------------------------
    op.create_table(
        "devices",
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("firmware_version", sa.Text, nullable=False),
        sa.Column(
            "status",
            device_status_enum,
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            r"firmware_version ~ '^\d+\.\d+\.\d+$'",
            name="chk_firmware_version",
        ),
    )

    # ------------------------------------------------------------------
    # Table: user_device_assignments  (M:N junction)
    # ------------------------------------------------------------------
    op.create_table(
        "user_device_assignments",
        sa.Column(
            "assignment_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("devices.device_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assigned_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "device_id", name="uq_user_device"),
    )

    # ------------------------------------------------------------------
    # Table: fall_events
    # ------------------------------------------------------------------
    op.create_table(
        "fall_events",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("devices.device_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("encrypted_gps_coords", sa.LargeBinary, nullable=True),
        sa.Column("severity", severity_level_enum, nullable=False),
        sa.Column(
            "alert_status",
            alert_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "accelerometer_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ------------------------------------------------------------------
    # Table: gps_history
    # ------------------------------------------------------------------
    op.create_table(
        "gps_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("devices.device_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("encrypted_lat", sa.LargeBinary, nullable=False),
        sa.Column("encrypted_lon", sa.LargeBinary, nullable=False),
        sa.Column("accuracy", sa.Numeric(precision=8, scale=3), nullable=True),
    )

    # ------------------------------------------------------------------
    # Table: audit_log
    # ------------------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column(
            "log_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("actor", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_type", sa.Text, nullable=True),
    )

    # ------------------------------------------------------------------
    # Indexes — acceptance criteria
    # ------------------------------------------------------------------
    op.create_index(
        "ix_fall_events_device_timestamp",
        "fall_events",
        ["device_id", "timestamp"],
    )
    op.create_index(
        "ix_gps_history_device_timestamp",
        "gps_history",
        ["device_id", "timestamp"],
    )

    # Supporting indexes
    op.create_index("ix_devices_owner",  "devices", ["owner_id"])
    op.create_index("ix_uda_device",     "user_device_assignments", ["device_id"])
    op.create_index("ix_uda_user",       "user_device_assignments", ["user_id"])
    op.create_index(
        "ix_fall_events_alert_status",
        "fall_events",
        ["alert_status"],
        postgresql_where=sa.text("alert_status IN ('pending', 'sent')"),
    )
    op.create_index(
        "ix_audit_log_actor_timestamp",
        "audit_log",
        ["actor", "timestamp"],
    )
    op.create_index(
        "ix_audit_log_target",
        "audit_log",
        ["target_type", "target_id"],
    )

    # ------------------------------------------------------------------
    # updated_at trigger
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER LANGUAGE plpgsql AS
        $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$
        """
    )
    for table in ("users", "devices", "fall_events"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_updated_at
                BEFORE UPDATE ON {table}
                FOR EACH ROW EXECUTE FUNCTION set_updated_at()
            """
        )

    # ------------------------------------------------------------------
    # Row-Level Security
    # ------------------------------------------------------------------
    _apply_rls()

    # ------------------------------------------------------------------
    # Grants
    # ------------------------------------------------------------------
    _apply_grants()


def _apply_rls() -> None:
    """Enable RLS and create all access policies."""

    # users
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY users_select_policy ON users FOR SELECT USING (
            current_setting('app.user_role', TRUE) = 'admin'
            OR user_id = current_setting('app.user_id', TRUE)::UUID
            OR (
                current_setting('app.user_role', TRUE) = 'caregiver'
                AND user_id IN (
                    SELECT d.owner_id FROM devices d
                    JOIN user_device_assignments uda ON uda.device_id = d.device_id
                    WHERE uda.user_id = current_setting('app.user_id', TRUE)::UUID
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY users_insert_policy ON users FOR INSERT WITH CHECK (
            current_setting('app.user_role', TRUE) = 'admin'
        )
        """
    )
    op.execute(
        """
        CREATE POLICY users_update_policy ON users FOR UPDATE USING (
            current_setting('app.user_role', TRUE) = 'admin'
            OR user_id = current_setting('app.user_id', TRUE)::UUID
        )
        """
    )
    op.execute(
        """
        CREATE POLICY users_delete_policy ON users FOR DELETE USING (
            current_setting('app.user_role', TRUE) = 'admin'
        )
        """
    )

    # devices
    op.execute("ALTER TABLE devices ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE devices FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY devices_select_policy ON devices FOR SELECT USING (
            current_setting('app.user_role', TRUE) = 'admin'
            OR (
                current_setting('app.user_role', TRUE) = 'wearer'
                AND owner_id = current_setting('app.user_id', TRUE)::UUID
            )
            OR (
                current_setting('app.user_role', TRUE) = 'caregiver'
                AND device_id IN (
                    SELECT device_id FROM user_device_assignments
                    WHERE user_id = current_setting('app.user_id', TRUE)::UUID
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY devices_insert_policy ON devices FOR INSERT WITH CHECK (
            current_setting('app.user_role', TRUE) = 'admin'
        )
        """
    )
    op.execute(
        """
        CREATE POLICY devices_update_policy ON devices FOR UPDATE USING (
            current_setting('app.user_role', TRUE) = 'admin'
        )
        """
    )
    op.execute(
        """
        CREATE POLICY devices_delete_policy ON devices FOR DELETE USING (
            current_setting('app.user_role', TRUE) = 'admin'
        )
        """
    )

    # user_device_assignments
    op.execute(
        "ALTER TABLE user_device_assignments ENABLE ROW LEVEL SECURITY"
    )
    op.execute("ALTER TABLE user_device_assignments FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY uda_select_policy ON user_device_assignments FOR SELECT USING (
            current_setting('app.user_role', TRUE) = 'admin'
            OR user_id = current_setting('app.user_id', TRUE)::UUID
            OR device_id IN (
                SELECT device_id FROM user_device_assignments
                WHERE user_id = current_setting('app.user_id', TRUE)::UUID
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY uda_insert_policy ON user_device_assignments FOR INSERT WITH CHECK (
            current_setting('app.user_role', TRUE) = 'admin'
        )
        """
    )
    op.execute(
        """
        CREATE POLICY uda_delete_policy ON user_device_assignments FOR DELETE USING (
            current_setting('app.user_role', TRUE) = 'admin'
        )
        """
    )

    # fall_events
    op.execute("ALTER TABLE fall_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE fall_events FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY fall_events_select_policy ON fall_events FOR SELECT USING (
            current_setting('app.user_role', TRUE) = 'admin'
            OR device_id IN (
                SELECT device_id FROM devices
                WHERE owner_id = current_setting('app.user_id', TRUE)::UUID
                  AND current_setting('app.user_role', TRUE) = 'wearer'
            )
            OR (
                current_setting('app.user_role', TRUE) = 'caregiver'
                AND device_id IN (
                    SELECT device_id FROM user_device_assignments
                    WHERE user_id = current_setting('app.user_id', TRUE)::UUID
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY fall_events_insert_policy ON fall_events FOR INSERT WITH CHECK (
            current_setting('app.user_role', TRUE) IN ('admin', 'system')
        )
        """
    )
    op.execute(
        """
        CREATE POLICY fall_events_update_policy ON fall_events FOR UPDATE USING (
            current_setting('app.user_role', TRUE) IN ('admin', 'caregiver', 'system')
            AND (
                current_setting('app.user_role', TRUE) = 'admin'
                OR device_id IN (
                    SELECT device_id FROM user_device_assignments
                    WHERE user_id = current_setting('app.user_id', TRUE)::UUID
                )
            )
        )
        """
    )

    # gps_history
    op.execute("ALTER TABLE gps_history ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE gps_history FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY gps_history_select_policy ON gps_history FOR SELECT USING (
            current_setting('app.user_role', TRUE) = 'admin'
            OR device_id IN (
                SELECT device_id FROM devices
                WHERE owner_id = current_setting('app.user_id', TRUE)::UUID
                  AND current_setting('app.user_role', TRUE) = 'wearer'
            )
            OR (
                current_setting('app.user_role', TRUE) = 'caregiver'
                AND device_id IN (
                    SELECT device_id FROM user_device_assignments
                    WHERE user_id = current_setting('app.user_id', TRUE)::UUID
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY gps_history_insert_policy ON gps_history FOR INSERT WITH CHECK (
            current_setting('app.user_role', TRUE) IN ('admin', 'system')
        )
        """
    )

    # audit_log
    op.execute("ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_log FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY audit_log_select_policy ON audit_log FOR SELECT USING (
            current_setting('app.user_role', TRUE) = 'admin'
            OR actor = current_setting('app.user_id', TRUE)
        )
        """
    )
    op.execute(
        """
        CREATE POLICY audit_log_insert_policy ON audit_log FOR INSERT WITH CHECK (TRUE)
        """
    )


def _apply_grants() -> None:
    """Grant minimum-privilege access to app_user."""
    op.execute("GRANT USAGE ON SCHEMA public TO app_user")
    op.execute("GRANT SELECT, INSERT, UPDATE ON users TO app_user")
    op.execute("GRANT SELECT, INSERT, UPDATE ON devices TO app_user")
    op.execute(
        "GRANT SELECT, INSERT, DELETE ON user_device_assignments TO app_user"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON fall_events TO app_user")
    op.execute("GRANT SELECT, INSERT ON gps_history TO app_user")
    op.execute("GRANT SELECT, INSERT ON audit_log TO app_user")
    op.execute(
        "GRANT USAGE, SELECT ON SEQUENCE gps_history_id_seq TO app_user"
    )
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_readonly")


def downgrade() -> None:
    # Reverse order: drop tables, triggers, functions, types

    for table in ("users", "devices", "fall_events"):
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}"
        )
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")

    op.drop_table("audit_log")
    op.drop_table("gps_history")
    op.drop_table("fall_events")
    op.drop_table("user_device_assignments")
    op.drop_table("devices")
    op.drop_table("users")

    for enum_name in (
        "alert_status_enum",
        "severity_level_enum",
        "device_status_enum",
        "user_role_enum",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
