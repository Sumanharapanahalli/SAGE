"""System test configuration — SLA thresholds, staging endpoints, chaos settings."""
import os
from dataclasses import dataclass

BASE_URL: str = os.environ.get("STAGING_BASE_URL", "https://api-staging.example.com")
API_ADMIN_KEY: str = os.environ.get("STAGING_ADMIN_KEY", "")
REQUEST_TIMEOUT: float = 30.0


@dataclass(frozen=True)
class SLAThresholds:
    api_p99_ms: int = 500
    transfer_settlement_s: int = 5
    kyc_decision_s: int = 60
    db_failover_s: int = 30
    card_auth_s: float = 1.0
    brokerage_order_s: float = 5.0
    baas_response_ms: int = 200
    duplicate_tx_window_s: int = 60


@dataclass(frozen=True)
class LoadTargets:
    concurrent_users: int = 10_000
    transfers_per_second: int = 500
    ramp_up_s: int = 120
    sustained_s: int = 300
    error_rate_max: float = 0.01


@dataclass(frozen=True)
class ThirdPartyEndpoints:
    baas: str = os.environ.get("BAAS_URL", "https://baas-staging.example.com")
    card_processor: str = os.environ.get("CARD_URL", "https://cards-staging.example.com")
    kyc_vendor: str = os.environ.get("KYC_URL", "https://kyc-staging.example.com")
    brokerage: str = os.environ.get("BROKERAGE_URL", "https://brokerage-staging.example.com")


@dataclass(frozen=True)
class ChaosSettings:
    db_primary_container: str = os.environ.get("DB_PRIMARY_CONTAINER", "postgres-primary")
    db_replica_container: str = os.environ.get("DB_REPLICA_CONTAINER", "postgres-replica")
    toxiproxy_host: str = os.environ.get("TOXIPROXY_HOST", "localhost")
    toxiproxy_port: int = int(os.environ.get("TOXIPROXY_PORT", "8474"))
    kyc_proxy_name: str = "kyc_vendor"
    kyc_upstream_host: str = os.environ.get("KYC_UPSTREAM_HOST", "kyc-staging.example.com")
    kyc_upstream_port: int = int(os.environ.get("KYC_UPSTREAM_PORT", "443"))


SLA = SLAThresholds()
LOAD = LoadTargets()
THIRD_PARTY = ThirdPartyEndpoints()
CHAOS = ChaosSettings()
