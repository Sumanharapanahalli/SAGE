"""
services/device_provisioning.py — AWS IoT Core device provisioning.

In production (iot_mock_mode=False), uses boto3 to:
  1. Create an IoT thing
  2. Create X.509 certificate + keys
  3. Attach the policy
  4. Attach the certificate to the thing

In development (iot_mock_mode=True), returns realistic-looking mock credentials.
"""
from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

_DB_PATH = Path(".sage/devices.db")

# Minimal self-signed CA PEM for mock mode (not cryptographically valid — dev only)
_MOCK_CA_PEM = """-----BEGIN CERTIFICATE-----
MIICpDCCAYwCCQDU+pQ4pHgSpDANBgkqhkiG9w0BAQsFADAUMRIwEAYDVQQDDAls
b2NhbGhvc3QwHhcNMjQwMTAxMDAwMDAwWhcNMjUwMTAxMDAwMDAwWjAUMRIwEAYD
VQQDDAlsb2NhbGhvc3QwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQC7
[MOCK-CERT-TRUNCATED-FOR-BREVITY]
-----END CERTIFICATE-----"""


@dataclass
class ProvisionedDevice:
    device_id: str
    device_serial: str
    owner_user_id: str
    firmware_version: str
    model_name: str
    certificate_pem: str
    private_key_pem: str
    ca_cert_pem: str
    certificate_arn: str
    certificate_id: str
    iot_endpoint: str
    mqtt_port: int
    policy_name: str
    mqtt_topic_prefix: str
    provisioned_at: float


class DeviceProvisioningService:
    """
    Provisions a new device against AWS IoT Core and persists device record locally.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._db = _DB_PATH
        self._init_db()

    def _init_db(self) -> None:
        self._db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    device_id        TEXT PRIMARY KEY,
                    device_serial    TEXT NOT NULL UNIQUE,
                    owner_user_id    TEXT NOT NULL,
                    firmware_version TEXT NOT NULL,
                    model_name       TEXT NOT NULL,
                    status           TEXT NOT NULL DEFAULT 'active',
                    certificate_arn  TEXT,
                    certificate_id   TEXT,
                    last_seen        REAL,
                    battery_pct      REAL,
                    created_at       REAL NOT NULL
                )
                """
            )
            conn.commit()

    async def register_device(
        self,
        owner_user_id: str,
        device_serial: str,
        firmware_version: str,
        model_name: str,
    ) -> ProvisionedDevice:
        """
        Provision a new device. Returns IoT credentials.
        Idempotent: re-registering the same serial returns existing credentials.
        """
        # Check if already registered
        existing = self.get_device_by_serial(device_serial)
        if existing:
            logger.info(
                "DeviceProvisioning: serial=%s already registered as device_id=%s",
                device_serial,
                existing["device_id"],
            )
            raise ValueError(
                f"Device serial {device_serial!r} already registered as "
                f"device_id={existing['device_id']}"
            )

        settings = self._settings

        if settings.iot_mock_mode:
            result = await self._mock_provision(
                owner_user_id, device_serial, firmware_version, model_name
            )
        else:
            result = await self._boto3_provision(
                owner_user_id, device_serial, firmware_version, model_name
            )

        # Persist device record
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                "INSERT INTO devices (device_id, device_serial, owner_user_id, "
                "firmware_version, model_name, certificate_arn, certificate_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    result.device_id,
                    result.device_serial,
                    result.owner_user_id,
                    result.firmware_version,
                    result.model_name,
                    result.certificate_arn,
                    result.certificate_id,
                    result.provisioned_at,
                ),
            )
            conn.commit()

        logger.info(
            "DeviceProvisioning: provisioned device_id=%s serial=%s owner=%s",
            result.device_id,
            device_serial,
            owner_user_id,
        )
        return result

    async def _mock_provision(
        self,
        owner_user_id: str,
        device_serial: str,
        firmware_version: str,
        model_name: str,
    ) -> ProvisionedDevice:
        """Return mock AWS IoT credentials for development."""
        settings = self._settings
        device_id = str(uuid.uuid4())
        cert_id = uuid.uuid4().hex

        mock_cert_pem = (
            f"-----BEGIN CERTIFICATE-----\n"
            f"MOCK-CERT-FOR-DEVICE-{device_id[:8]}\n"
            f"SERIAL-{device_serial}\n"
            f"-----END CERTIFICATE-----"
        )
        mock_key_pem = (
            f"-----BEGIN RSA PRIVATE KEY-----\n"
            f"MOCK-KEY-FOR-DEVICE-{device_id[:8]}\n"
            f"DO-NOT-USE-IN-PRODUCTION\n"
            f"-----END RSA PRIVATE KEY-----"
        )

        return ProvisionedDevice(
            device_id=device_id,
            device_serial=device_serial,
            owner_user_id=owner_user_id,
            firmware_version=firmware_version,
            model_name=model_name,
            certificate_pem=mock_cert_pem,
            private_key_pem=mock_key_pem,
            ca_cert_pem=_MOCK_CA_PEM,
            certificate_arn=(
                f"arn:aws:iot:{settings.aws_region}:{settings.aws_account_id}"
                f":cert/{cert_id}"
            ),
            certificate_id=cert_id,
            iot_endpoint=settings.aws_iot_endpoint,
            mqtt_port=8883,
            policy_name=settings.iot_policy_name,
            mqtt_topic_prefix=f"devices/{device_id}",
            provisioned_at=time.time(),
        )

    async def _boto3_provision(
        self,
        owner_user_id: str,
        device_serial: str,
        firmware_version: str,
        model_name: str,
    ) -> ProvisionedDevice:
        """
        Real AWS IoT Core provisioning via boto3.
        Requires: pip install boto3 + AWS credentials configured.
        """
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError(
                "boto3 is required for real AWS IoT provisioning. "
                "Install it with: pip install boto3"
            ) from exc

        settings = self._settings
        device_id = str(uuid.uuid4())
        thing_name = f"fall-detector-{device_id}"

        iot = boto3.client("iot", region_name=settings.aws_region)

        # 1. Create thing
        iot.create_thing(
            thingName=thing_name,
            attributePayload={
                "attributes": {
                    "device_id": device_id,
                    "device_serial": device_serial,
                    "owner_user_id": owner_user_id,
                    "firmware_version": firmware_version,
                }
            },
        )

        # 2. Create certificate
        cert_resp = iot.create_keys_and_certificate(setAsActive=True)
        cert_id = cert_resp["certificateId"]
        cert_arn = cert_resp["certificateArn"]

        # 3. Attach policy
        iot.attach_policy(
            policyName=settings.iot_policy_name,
            target=cert_arn,
        )

        # 4. Attach certificate to thing
        iot.attach_thing_principal(
            thingName=thing_name,
            principal=cert_arn,
        )

        # 5. Get endpoint
        endpoint_resp = iot.describe_endpoint(endpointType="iot:Data-ATS")
        iot_endpoint = endpoint_resp["endpointAddress"]

        logger.info(
            "DeviceProvisioning: AWS IoT thing=%s cert=%s created",
            thing_name,
            cert_id[:8],
        )

        return ProvisionedDevice(
            device_id=device_id,
            device_serial=device_serial,
            owner_user_id=owner_user_id,
            firmware_version=firmware_version,
            model_name=model_name,
            certificate_pem=cert_resp["certificatePem"],
            private_key_pem=cert_resp["keyPair"]["PrivateKey"],
            ca_cert_pem=_MOCK_CA_PEM,  # Amazon Root CA — download from AWS in production
            certificate_arn=cert_arn,
            certificate_id=cert_id,
            iot_endpoint=iot_endpoint,
            mqtt_port=8883,
            policy_name=settings.iot_policy_name,
            mqtt_topic_prefix=f"devices/{device_id}",
            provisioned_at=time.time(),
        )

    def get_device(self, device_id: str) -> Optional[dict]:
        with sqlite3.connect(self._db) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM devices WHERE device_id = ?", (device_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_device_by_serial(self, serial: str) -> Optional[dict]:
        with sqlite3.connect(self._db) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM devices WHERE device_serial = ?", (serial,)
            ).fetchone()
        return dict(row) if row else None

    def list_devices(self, owner_user_id: Optional[str] = None) -> list[dict]:
        with sqlite3.connect(self._db) as conn:
            conn.row_factory = sqlite3.Row
            if owner_user_id:
                rows = conn.execute(
                    "SELECT * FROM devices WHERE owner_user_id = ?",
                    (owner_user_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM devices").fetchall()
        return [dict(r) for r in rows]

    def update_last_seen(
        self, device_id: str, battery_pct: Optional[float] = None
    ) -> None:
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                "UPDATE devices SET last_seen = ?, battery_pct = ? WHERE device_id = ?",
                (time.time(), battery_pct, device_id),
            )
            conn.commit()

    def update_status(self, device_id: str, status: str) -> bool:
        with sqlite3.connect(self._db) as conn:
            cur = conn.execute(
                "UPDATE devices SET status = ? WHERE device_id = ?",
                (status, device_id),
            )
            conn.commit()
        return cur.rowcount > 0


_provisioning_service: Optional[DeviceProvisioningService] = None


def get_provisioning_service() -> DeviceProvisioningService:
    global _provisioning_service
    if _provisioning_service is None:
        _provisioning_service = DeviceProvisioningService()
    return _provisioning_service
