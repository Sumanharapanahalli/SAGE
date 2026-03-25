"""
core/config.py — Application settings via pydantic-settings.

All values can be overridden by environment variables or a .env file.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Auth ─────────────────────────────────────────────────────────────────
    secret_key: str = "CHANGE-ME-IN-PRODUCTION-USE-32+-RANDOM-CHARS"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./fall_detection.db"

    # ── AWS IoT Core ─────────────────────────────────────────────────────────
    aws_region: str = "us-east-1"
    aws_account_id: str = "123456789012"
    aws_iot_endpoint: str = "CHANGEME.iot.us-east-1.amazonaws.com"
    iot_policy_name: str = "FallDetectionDevicePolicy"
    # Set to False to use boto3 real AWS calls; True returns mock certs
    iot_mock_mode: bool = True

    # ── MQTT ─────────────────────────────────────────────────────────────────
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 8883
    mqtt_use_tls: bool = False  # set True in production with IoT Core
    mqtt_client_id: str = "sage-fall-detection-backend"
    mqtt_ca_cert: str = ""
    mqtt_client_cert: str = ""
    mqtt_client_key: str = ""

    # ── Twilio SMS ────────────────────────────────────────────────────────────
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = "+15551234567"

    # ── SendGrid ──────────────────────────────────────────────────────────────
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "alerts@falldetection.ai"

    # ── Firebase / FCM ────────────────────────────────────────────────────────
    firebase_credentials_path: str = ""

    # ── RapidSOS NG911 ────────────────────────────────────────────────────────
    rapidsos_client_id: str = ""
    rapidsos_client_secret: str = ""
    rapidsos_base_url: str = "https://api.rapidsos.com/v2"
    rapidsos_agency_id: str = ""
    rapidsos_mock_mode: bool = True  # set False with real credentials

    # ── App ───────────────────────────────────────────────────────────────────
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
