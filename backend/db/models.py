"""
SQLAlchemy 2.0 declarative models for elder_fall_detection.

Encryption strategy
-------------------
PII columns (name, email, phone, GPS coordinates) are stored as PostgreSQL
`bytea` and encrypted/decrypted transparently by the PGPEncryptedString and
PGPEncryptedNumeric TypeDecorators using pgcrypto's pgp_sym_encrypt /
pgp_sym_decrypt with the session-local key `current_setting('app.encryption_key')`.

Row-Level Security
------------------
RLS policies are defined in the Alembic migration (not here) because they are
DDL, not ORM metadata.  The session must SET LOCAL app.user_id and
app.user_role before executing any SELECT/INSERT/UPDATE/DELETE on protected
tables.  See database.py:set_session_context().
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    LargeBinary,
    Numeric,
    Text,
    UniqueConstraint,
    cast,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


# ---------------------------------------------------------------------------
# Custom TypeDecorators for pgcrypto-encrypted columns
# ---------------------------------------------------------------------------


class PGPEncryptedString(TypeDecorator):
    """
    Stores a Python str as pgp_sym_encrypt(value, key) bytea.
    Decrypts transparently on SELECT via pgp_sym_decrypt.

    The encryption key is read from the PostgreSQL session variable
    ``app.encryption_key`` which must be set per-transaction.
    """

    impl = LargeBinary
    cache_ok = True

    def bind_expression(self, bindvalue):
        return func.pgp_sym_encrypt(
            bindvalue,
            func.current_setting(text("'app.encryption_key'")),
        )

    def column_expression(self, col):
        return func.pgp_sym_decrypt(
            col,
            func.current_setting(text("'app.encryption_key'")),
        )


class PGPEncryptedNumeric(TypeDecorator):
    """
    Stores a Python float/Decimal as pgp_sym_encrypt(cast(value, text), key).
    Decrypts and re-casts to NUMERIC(10,7) on SELECT.
    """

    impl = LargeBinary
    cache_ok = True

    def bind_expression(self, bindvalue):
        return func.pgp_sym_encrypt(
            cast(bindvalue, Text),
            func.current_setting(text("'app.encryption_key'")),
        )

    def column_expression(self, col):
        return cast(
            func.pgp_sym_decrypt(
                col,
                func.current_setting(text("'app.encryption_key'")),
            ),
            Numeric(precision=10, scale=7),
        )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class UserRole(str, enum.Enum):
    wearer = "wearer"
    caregiver = "caregiver"
    admin = "admin"


class DeviceStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    maintenance = "maintenance"
    decommissioned = "decommissioned"


class SeverityLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AlertStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    acknowledged = "acknowledged"
    resolved = "resolved"
    false_positive = "false_positive"


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Table: users
# ---------------------------------------------------------------------------


class User(Base):
    """
    Represents a system user.  PII columns (name, email, phone,
    emergency_contacts) are pgcrypto-encrypted at the database level.
    email_hash (SHA-256 of the plaintext email) is stored unencrypted to
    allow uniqueness enforcement and fast lookups without decrypting.
    """

    __tablename__ = "users"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum"),
        nullable=False,
    )

    # PII — pgcrypto encrypted
    encrypted_name: Mapped[bytes] = mapped_column(
        "encrypted_name",
        PGPEncryptedString,
        nullable=False,
        comment="pgp_sym_encrypt(full_name, key)",
    )
    encrypted_email: Mapped[bytes] = mapped_column(
        "encrypted_email",
        PGPEncryptedString,
        nullable=False,
        comment="pgp_sym_encrypt(email, key)",
    )
    encrypted_phone: Mapped[Optional[bytes]] = mapped_column(
        "encrypted_phone",
        PGPEncryptedString,
        nullable=True,
        comment="pgp_sym_encrypt(phone_number, key)",
    )
    # SHA-256 of plaintext email — used for UNIQUE index and lookup
    email_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
        comment="digest(email, 'sha256') hex — not PII",
    )
    # Emergency contacts as encrypted JSON array:
    # [{"name": "...", "phone": "...", "relationship": "..."}]
    encrypted_emergency_contacts: Mapped[Optional[bytes]] = mapped_column(
        "encrypted_emergency_contacts",
        PGPEncryptedString,
        nullable=True,
        comment="pgp_sym_encrypt(JSON array of contacts, key)",
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    owned_devices: Mapped[list["Device"]] = relationship(
        "Device", back_populates="owner", foreign_keys="Device.owner_id"
    )
    device_assignments: Mapped[list["UserDeviceAssignment"]] = relationship(
        "UserDeviceAssignment",
        back_populates="user",
        foreign_keys="UserDeviceAssignment.user_id",
    )

    def __repr__(self) -> str:
        return f"<User user_id={self.user_id} role={self.role}>"


# ---------------------------------------------------------------------------
# Table: devices
# ---------------------------------------------------------------------------


class Device(Base):
    """
    Physical fall-detection wearable device.
    owner_id → users (the wearer who physically wears the device).
    Caregivers and admins are linked via user_device_assignments (M:N).
    """

    __tablename__ = "devices"

    device_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK to the wearer (users.role = wearer)",
    )
    firmware_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus, name="device_status_enum"),
        nullable=False,
        default=DeviceStatus.active,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    owner: Mapped["User"] = relationship(
        "User", back_populates="owned_devices", foreign_keys=[owner_id]
    )
    fall_events: Mapped[list["FallEvent"]] = relationship(
        "FallEvent", back_populates="device"
    )
    gps_history: Mapped[list["GpsHistory"]] = relationship(
        "GpsHistory", back_populates="device"
    )
    assignments: Mapped[list["UserDeviceAssignment"]] = relationship(
        "UserDeviceAssignment", back_populates="device"
    )

    def __repr__(self) -> str:
        return f"<Device device_id={self.device_id} status={self.status}>"


# ---------------------------------------------------------------------------
# Table: user_device_assignments  (M:N junction)
# ---------------------------------------------------------------------------


class UserDeviceAssignment(Base):
    """
    Junction table: caregivers (and admins) assigned to devices.
    Wearers are linked via devices.owner_id — not through this table.
    RLS policies use this table to determine caregiver access to devices.
    """

    __tablename__ = "user_device_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "device_id", name="uq_user_device"),
    )

    assignment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    device_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("devices.device_id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin user who created the assignment",
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User", back_populates="device_assignments", foreign_keys=[user_id]
    )
    device: Mapped["Device"] = relationship(
        "Device", back_populates="assignments", foreign_keys=[device_id]
    )

    def __repr__(self) -> str:
        return (
            f"<UserDeviceAssignment user={self.user_id} device={self.device_id}>"
        )


# ---------------------------------------------------------------------------
# Table: fall_events
# ---------------------------------------------------------------------------


class FallEvent(Base):
    """
    Detected fall incident.  GPS coordinates are PII and are pgcrypto-encrypted.
    Cardinality: devices 1:N fall_events.
    """

    __tablename__ = "fall_events"
    __table_args__ = (
        Index("ix_fall_events_device_timestamp", "device_id", "timestamp"),
    )

    event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    device_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("devices.device_id", ondelete="RESTRICT"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=False
    )

    # GPS coords — stored as encrypted lat/lon JSON: {"lat": 37.7749, "lon": -122.4194}
    encrypted_gps_coords: Mapped[Optional[bytes]] = mapped_column(
        "encrypted_gps_coords",
        PGPEncryptedString,
        nullable=True,
        comment='pgp_sym_encrypt({"lat": ..., "lon": ...}, key)',
    )

    severity: Mapped[SeverityLevel] = mapped_column(
        Enum(SeverityLevel, name="severity_level_enum"),
        nullable=False,
    )
    alert_status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status_enum"),
        nullable=False,
        default=AlertStatus.pending,
    )
    # Raw accelerometer snapshot — not PII, stored unencrypted for analytics
    accelerometer_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Raw sensor snapshot at time of detection",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    device: Mapped["Device"] = relationship("Device", back_populates="fall_events")

    def __repr__(self) -> str:
        return (
            f"<FallEvent event_id={self.event_id} device={self.device_id}"
            f" severity={self.severity}>"
        )


# ---------------------------------------------------------------------------
# Table: gps_history
# ---------------------------------------------------------------------------


class GpsHistory(Base):
    """
    Continuous GPS telemetry stream from devices.
    lat and lon are PII and are pgcrypto-encrypted.
    accuracy is not PII and is stored plaintext for geofence calculations.
    """

    __tablename__ = "gps_history"
    __table_args__ = (
        Index("ix_gps_history_device_timestamp", "device_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    device_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("devices.device_id", ondelete="CASCADE"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=False
    )

    # PII — pgcrypto encrypted
    encrypted_lat: Mapped[bytes] = mapped_column(
        "encrypted_lat",
        PGPEncryptedNumeric,
        nullable=False,
        comment="pgp_sym_encrypt(latitude::text, key)",
    )
    encrypted_lon: Mapped[bytes] = mapped_column(
        "encrypted_lon",
        PGPEncryptedNumeric,
        nullable=False,
        comment="pgp_sym_encrypt(longitude::text, key)",
    )
    # Accuracy in metres — not PII, kept unencrypted
    accuracy: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=8, scale=3), nullable=True
    )

    # Relationships
    device: Mapped["Device"] = relationship("Device", back_populates="gps_history")

    def __repr__(self) -> str:
        return f"<GpsHistory device={self.device_id} ts={self.timestamp}>"


# ---------------------------------------------------------------------------
# Table: audit_log
# ---------------------------------------------------------------------------


class AuditLog(Base):
    """
    Immutable HIPAA audit trail.  Never UPDATE or DELETE rows.
    actor is a free-form string to accommodate both user UUIDs and
    system identifiers (e.g. 'system:mqtt_ingester').
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_actor_timestamp", "actor", "timestamp"),
        Index("ix_audit_log_target", "target_type", "target_id"),
    )

    log_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Free-form: user UUID string or "system:<subsystem>"
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    # Structured payload — what changed, old/new values, IP address, etc.
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Polymorphic reference to the affected record
    target_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    target_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AuditLog log_id={self.log_id} actor={self.actor}"
            f" action={self.action}>"
        )
