"""
api/models.py — Pydantic request/response schemas for all API routes.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ── Auth ─────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class LoginRequest(BaseModel):
    username: str
    password: str


# ── Device ───────────────────────────────────────────────────────────────────

class DeviceRegisterRequest(BaseModel):
    owner_user_id: str = Field(..., description="UUID of the wearer/owner user")
    firmware_version: str = Field(..., example="2.3.1")
    device_serial: str = Field(..., description="Physical serial number from manufacturer")
    model_name: str = Field(default="FallGuard-1", example="FallGuard-Pro")


class AwsIotCredentials(BaseModel):
    certificate_pem: str = Field(..., description="X.509 certificate PEM")
    private_key_pem: str = Field(..., description="RSA private key PEM")
    ca_cert_pem: str = Field(..., description="Amazon Root CA PEM")
    certificate_arn: str
    certificate_id: str
    iot_endpoint: str
    mqtt_port: int = 8883
    policy_name: str


class DeviceRegisterResponse(BaseModel):
    device_id: str
    device_serial: str
    owner_user_id: str
    firmware_version: str
    status: str
    iot_credentials: AwsIotCredentials
    mqtt_topic_prefix: str = Field(
        ..., description="Base topic: devices/{device_id}"
    )
    provisioned_at: datetime


class DeviceStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    maintenance = "maintenance"
    decommissioned = "decommissioned"


class DeviceInfo(BaseModel):
    device_id: str
    device_serial: str
    owner_user_id: str
    firmware_version: str
    status: DeviceStatus
    model_name: str
    last_seen: Optional[datetime] = None
    created_at: datetime


class DeviceUpdateRequest(BaseModel):
    firmware_version: Optional[str] = None
    status: Optional[DeviceStatus] = None


# ── Location ─────────────────────────────────────────────────────────────────

class GpsPoint(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_meters: Optional[float] = Field(None, ge=0)
    altitude_meters: Optional[float] = None
    timestamp: datetime
    source: str = "device"  # device | manual | last_known


class GpsHistoryResponse(BaseModel):
    device_id: str
    total_points: int
    from_ts: Optional[datetime]
    to_ts: Optional[datetime]
    points: list[GpsPoint]


# ── Alerts ───────────────────────────────────────────────────────────────────

class AlertSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AlertStatusEnum(str, Enum):
    pending = "pending"
    active = "active"
    acknowledged = "acknowledged"
    escalated = "escalated"
    dismissed = "dismissed"
    resolved = "resolved"
    false_positive = "false_positive"


class AlertInfo(BaseModel):
    alert_id: str
    event_id: str
    device_id: str
    user_id: str
    severity: str
    status: str
    confidence: float
    grace_period_seconds: int
    remaining_seconds: Optional[float]
    location: Optional[GpsPoint]
    created_at: datetime
    updated_at: datetime
    dispatch_id: Optional[str] = None  # RapidSOS dispatch_id if dispatched


class AlertAcknowledgeRequest(BaseModel):
    acknowledged_by: str
    note: Optional[str] = None


class AlertDismissRequest(BaseModel):
    dismissed_by: str
    reason: str = Field(..., description="false_positive | resolved | other")


class AlertEscalateRequest(BaseModel):
    escalated_by: str
    reason: str
    notify_emergency: bool = False


class AlertActionResponse(BaseModel):
    alert_id: str
    status: str
    message: str
    dispatch_id: Optional[str] = None


# ── MQTT Ingestion ────────────────────────────────────────────────────────────

class MqttFallPayload(BaseModel):
    """JSON payload expected on topic devices/{device_id}/fall"""
    event_id: str
    device_id: str
    user_id: str
    event_type: str = Field(..., description="fall_detected | sos_button | impact")
    impact_force_g: Optional[float] = None
    button_pressed: bool = False
    accelerometer_data: Optional[dict] = None
    gyroscope_data: Optional[dict] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy_meters: Optional[float] = None
    firmware_version: Optional[str] = None
    battery_pct: Optional[float] = None
    metadata: dict = Field(default_factory=dict)


class MqttGpsPayload(BaseModel):
    """JSON payload expected on topic devices/{device_id}/gps"""
    device_id: str
    latitude: float
    longitude: float
    accuracy_meters: Optional[float] = None
    altitude_meters: Optional[float] = None
    timestamp: Optional[datetime] = None
    battery_pct: Optional[float] = None


class MqttHeartbeatPayload(BaseModel):
    """JSON payload expected on topic devices/{device_id}/heartbeat"""
    device_id: str
    firmware_version: Optional[str] = None
    battery_pct: Optional[float] = None
    signal_strength_dbm: Optional[int] = None
    uptime_seconds: Optional[int] = None
    timestamp: Optional[datetime] = None


# ── Caregivers ────────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    wearer = "wearer"
    caregiver = "caregiver"
    admin = "admin"


class UserCreateRequest(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    role: UserRole
    password: str = Field(..., min_length=8)
    emergency_contacts: list[dict[str, str]] = Field(default_factory=list)


class UserInfo(BaseModel):
    user_id: str
    name: str
    email: str
    phone: Optional[str]
    role: UserRole
    is_active: bool
    created_at: datetime


class CaregiverAssignRequest(BaseModel):
    caregiver_user_id: str
    device_id: str
    assigned_by: str


class CaregiverAssignResponse(BaseModel):
    assignment_id: str
    caregiver_user_id: str
    device_id: str
    assigned_at: datetime


# ── Health / diagnostics ──────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    environment: str
    mqtt_connected: bool = False
    db_connected: bool = False
    timestamp: datetime
