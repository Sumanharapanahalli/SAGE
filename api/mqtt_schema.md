# EFDS MQTT Topic Schema — Device-to-Cloud Communication

> **Protocol**: MQTT 5.0 over TLS 1.3
> **Authentication**: X.509 mutual TLS (client certificates provisioned at manufacturing)
> **Broker**: AWS IoT Core / EMQX Enterprise (deployment-dependent)
> **Max message size**: 128 KB
> **Keep-alive**: 60 seconds

---

## Topic Hierarchy

All topics follow the pattern:

```
efds/{tenantId}/device/{deviceId}/{channel}
```

| Segment | Description |
|---|---|
| `efds` | Fixed namespace prefix |
| `{tenantId}` | UUID — tenant/organization identifier |
| `{deviceId}` | UUID — device identifier (matches X.509 CN) |
| `{channel}` | Message type (see below) |

### IAM Policy Constraint

Each device certificate authorizes publish/subscribe **only** to its own subtree:

```
efds/{tenantId}/device/{deviceId}/#
```

A device CANNOT publish to another device's topics. The broker enforces this via X.509 CN-based topic policy.

---

## Channels

### 1. `telemetry` — Sensor Telemetry

**Direction**: Device → Cloud
**QoS**: 1 (at least once)
**Retain**: false
**Publish interval**: Every 30 seconds (configurable via OTA config)
**Topic**: `efds/{tenantId}/device/{deviceId}/telemetry`

```json
{
  "ts": "2026-03-22T14:32:10.123Z",
  "seq": 148823,
  "battery_pct": 82,
  "battery_mv": 3845,
  "accel": {
    "x": 0.02,
    "y": -0.01,
    "z": 9.81,
    "unit": "m/s2"
  },
  "gyro": {
    "x": 0.3,
    "y": -0.1,
    "z": 0.0,
    "unit": "deg/s"
  },
  "heart_rate_bpm": 72,
  "spo2_pct": 97,
  "skin_temp_c": 36.2,
  "step_count_daily": 3421,
  "signal_rssi_dbm": -72,
  "signal_type": "lte",
  "fw_version": "2.4.1",
  "mem_free_kb": 128
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `ts` | string (ISO 8601) | yes | Device-local UTC timestamp |
| `seq` | integer | yes | Monotonic sequence number (wraps at 2^32) |
| `battery_pct` | integer (0–100) | yes | Battery state of charge |
| `battery_mv` | integer | no | Battery voltage in millivolts |
| `accel` | object | yes | 3-axis accelerometer reading |
| `gyro` | object | no | 3-axis gyroscope (EFDS-200/PRO only) |
| `heart_rate_bpm` | integer | no | Heart rate (EFDS-PRO only) |
| `spo2_pct` | integer (0–100) | no | Blood oxygen (EFDS-PRO only) |
| `skin_temp_c` | float | no | Skin temperature Celsius (EFDS-PRO only) |
| `step_count_daily` | integer | no | Steps since midnight local time |
| `signal_rssi_dbm` | integer | yes | Cellular signal strength |
| `signal_type` | string | yes | `lte` / `nb_iot` / `catm1` |
| `fw_version` | string (semver) | yes | Current firmware version |
| `mem_free_kb` | integer | no | Free heap memory in KB |

---

### 2. `fall` — Fall Detection Events

**Direction**: Device → Cloud
**QoS**: 2 (exactly once)
**Retain**: true (last fall event retained per device)
**Topic**: `efds/{tenantId}/device/{deviceId}/fall`

```json
{
  "ts": "2026-03-22T14:32:45.678Z",
  "fall_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "severity": "high",
  "impact_g": 4.7,
  "free_fall_ms": 320,
  "impact_vector": {
    "x": -2.1,
    "y": 0.8,
    "z": -4.2,
    "unit": "g"
  },
  "post_fall_stillness_s": 45,
  "sos_pressed": false,
  "location": {
    "lat": 40.7128,
    "lon": -74.006,
    "accuracy_m": 8.5,
    "alt_m": 12.3,
    "source": "gps",
    "fix_ts": "2026-03-22T14:32:40.000Z"
  },
  "vitals_snapshot": {
    "heart_rate_bpm": 92,
    "spo2_pct": 95
  },
  "accel_window_b64": "base64-encoded-200-sample-buffer",
  "battery_pct": 78,
  "fw_version": "2.4.1"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `ts` | string (ISO 8601) | yes | Detection timestamp |
| `fall_id` | string (UUID v4) | yes | Unique fall event ID (generated on-device) |
| `severity` | string | yes | `low` / `medium` / `high` / `critical` |
| `impact_g` | float | yes | Peak resultant acceleration (g) |
| `free_fall_ms` | integer | yes | Milliseconds of free-fall detected before impact |
| `impact_vector` | object | yes | 3-axis impact force decomposition |
| `post_fall_stillness_s` | integer | yes | Seconds of no-motion after impact |
| `sos_pressed` | boolean | yes | True if SOS button was pressed |
| `location` | object | yes | GPS fix at time of fall |
| `location.lat` | float | yes | WGS84 latitude |
| `location.lon` | float | yes | WGS84 longitude |
| `location.accuracy_m` | float | yes | Horizontal accuracy (meters, 1-sigma) |
| `location.alt_m` | float | no | Altitude (meters above WGS84 ellipsoid) |
| `location.source` | string | yes | `gps` / `cell_tower` / `wifi` |
| `location.fix_ts` | string (ISO 8601) | yes | Timestamp of the position fix |
| `vitals_snapshot` | object | no | Vitals at moment of fall (EFDS-PRO only) |
| `accel_window_b64` | string | no | Base64-encoded raw accelerometer buffer (~200 samples @ 100Hz around impact) for ML re-analysis |
| `battery_pct` | integer | yes | Battery at time of event |
| `fw_version` | string | yes | Firmware version at time of event |

**Severity classification (on-device ML model)**:
- **low**: impact < 2g AND stillness < 10s
- **medium**: impact 2–4g OR stillness 10–30s
- **high**: impact > 4g AND stillness 30–120s
- **critical**: impact > 4g AND (stillness > 120s OR sos_pressed=true OR vitals anomaly)

---

### 3. `gps` — Periodic Location Updates

**Direction**: Device → Cloud
**QoS**: 0 (at most once — best effort)
**Retain**: true (last known position retained per device)
**Publish interval**: Every 5 minutes (configurable via OTA config)
**Topic**: `efds/{tenantId}/device/{deviceId}/gps`

```json
{
  "ts": "2026-03-22T14:35:00.000Z",
  "lat": 40.7128,
  "lon": -74.006,
  "accuracy_m": 5.2,
  "alt_m": 12.3,
  "speed_mps": 1.2,
  "heading_deg": 135.0,
  "source": "gps",
  "satellites": 8,
  "battery_pct": 81
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `ts` | string (ISO 8601) | yes | Fix timestamp |
| `lat` | float | yes | WGS84 latitude |
| `lon` | float | yes | WGS84 longitude |
| `accuracy_m` | float | yes | Horizontal accuracy (meters) |
| `alt_m` | float | no | Altitude |
| `speed_mps` | float | no | Ground speed (meters/second) |
| `heading_deg` | float | no | Heading (0–360 degrees, true north) |
| `source` | string | yes | `gps` / `cell_tower` / `wifi` |
| `satellites` | integer | no | Number of GPS satellites in fix |
| `battery_pct` | integer | yes | Current battery level |

**Power note**: GPS interval increases to 15 min when battery < 30%, and 60 min when < 15%.

---

### 4. `heartbeat` — Device Heartbeat / Keepalive

**Direction**: Device → Cloud
**QoS**: 0 (at most once)
**Retain**: true (last heartbeat retained — used for online/offline detection)
**Publish interval**: Every 60 seconds
**Topic**: `efds/{tenantId}/device/{deviceId}/heartbeat`

```json
{
  "ts": "2026-03-22T14:35:30.000Z",
  "seq": 148850,
  "uptime_s": 259200,
  "battery_pct": 81,
  "charging": false,
  "signal_rssi_dbm": -68,
  "fw_version": "2.4.1",
  "fall_detect_active": true,
  "ota_pending": false,
  "error_flags": []
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `ts` | string (ISO 8601) | yes | Heartbeat timestamp |
| `seq` | integer | yes | Monotonic sequence (shared with telemetry) |
| `uptime_s` | integer | yes | Seconds since last device boot |
| `battery_pct` | integer | yes | Battery level |
| `charging` | boolean | yes | True if on charger |
| `signal_rssi_dbm` | integer | yes | Cellular signal strength |
| `fw_version` | string | yes | Current firmware version |
| `fall_detect_active` | boolean | yes | Fall detection ML model running |
| `ota_pending` | boolean | yes | True if OTA update downloaded but not applied |
| `error_flags` | array of string | yes | Active error conditions (e.g., `["gps_no_fix", "low_memory"]`) |

**Offline detection**: Cloud marks device offline if no heartbeat received for 5 minutes (5x the publish interval).

---

### 5. `ota/command` — OTA Firmware Commands (Cloud → Device)

**Direction**: Cloud → Device
**QoS**: 2 (exactly once)
**Retain**: true (device receives command on next connect if offline)
**Topic**: `efds/{tenantId}/device/{deviceId}/ota/command`

```json
{
  "ts": "2026-03-22T15:00:00.000Z",
  "command": "update_firmware",
  "deployment_id": "d1e2f3a4-b5c6-7890-abcd-ef1234567890",
  "firmware_version": "2.5.0",
  "firmware_url": "https://firmware.efds.example.com/EFDS-200/2.5.0/firmware.bin?X-Amz-Signature=...",
  "firmware_sha256": "a3f19b2c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a",
  "firmware_size_bytes": 524288,
  "min_battery_pct": 30,
  "download_deadline": "2026-03-23T15:00:00.000Z",
  "install_window": {
    "start_hour_utc": 2,
    "end_hour_utc": 5
  },
  "rollback_version": "2.4.1",
  "force": false
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `ts` | string (ISO 8601) | yes | Command timestamp |
| `command` | string | yes | `update_firmware` / `update_config` / `rollback` / `reboot` |
| `deployment_id` | string (UUID) | yes | Links to admin OTA deployment record |
| `firmware_version` | string (semver) | yes | Target firmware version |
| `firmware_url` | string (URL) | yes | Pre-signed download URL (24h validity) |
| `firmware_sha256` | string (hex) | yes | SHA-256 hash — device MUST verify before applying |
| `firmware_size_bytes` | integer | yes | Expected file size |
| `min_battery_pct` | integer | yes | Minimum battery to proceed with update |
| `download_deadline` | string (ISO 8601) | yes | URL expires after this time |
| `install_window` | object | no | Preferred UTC hours for install (avoids active use) |
| `rollback_version` | string | yes | Version to revert to if update fails health check |
| `force` | boolean | yes | If true, skip install_window and battery checks (security patches only) |

---

### 6. `ota/status` — OTA Update Status (Device → Cloud)

**Direction**: Device → Cloud
**QoS**: 1 (at least once)
**Retain**: true (last OTA status retained)
**Topic**: `efds/{tenantId}/device/{deviceId}/ota/status`

```json
{
  "ts": "2026-03-22T15:05:30.000Z",
  "deployment_id": "d1e2f3a4-b5c6-7890-abcd-ef1234567890",
  "status": "downloading",
  "progress_pct": 45,
  "firmware_version": "2.5.0",
  "current_version": "2.4.1",
  "error": null,
  "battery_pct": 76
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `ts` | string (ISO 8601) | yes | Status timestamp |
| `deployment_id` | string (UUID) | yes | Links to the OTA command |
| `status` | string | yes | `acknowledged` / `downloading` / `downloaded` / `verifying` / `installing` / `completed` / `failed` / `rolled_back` |
| `progress_pct` | integer (0–100) | no | Download/install progress |
| `firmware_version` | string | yes | Target version |
| `current_version` | string | yes | Running version |
| `error` | string or null | yes | Error message if status=failed |
| `battery_pct` | integer | yes | Battery at time of report |

---

## QoS Summary Table

| Channel | Direction | QoS | Retain | Interval | Rationale |
|---|---|---|---|---|---|
| `telemetry` | Device→Cloud | 1 | false | 30s | Periodic, occasional loss acceptable |
| `fall` | Device→Cloud | 2 | true | Event-driven | Safety-critical — exactly-once required |
| `gps` | Device→Cloud | 0 | true | 5 min | Best-effort location, retain last known |
| `heartbeat` | Device→Cloud | 0 | true | 60s | Keepalive, retain for online status |
| `ota/command` | Cloud→Device | 2 | true | On-demand | Critical command — exactly-once, retained for offline devices |
| `ota/status` | Device→Cloud | 1 | true | Event-driven | Status tracking — at-least-once sufficient |

---

## MQTT 5.0 Properties Used

| Property | Usage |
|---|---|
| **Content Type** | `application/json` on all messages |
| **Message Expiry Interval** | `ota/command`: 86400s (24h). `fall`: 604800s (7 days). Others: not set. |
| **Response Topic** | `ota/command` sets Response Topic to `efds/{tenantId}/device/{deviceId}/ota/status` |
| **Correlation Data** | `deployment_id` bytes for OTA request/response correlation |
| **User Property** | `fw_version` on all device-originated messages for routing |

---

## Wildcard Subscriptions (Cloud-Side)

The cloud backend subscribes to process incoming device messages:

```
efds/+/device/+/telemetry    → Telemetry ingestion pipeline
efds/+/device/+/fall         → Fall detection alert handler (high priority)
efds/+/device/+/gps          → Location tracking service
efds/+/device/+/heartbeat    → Device presence monitor
efds/+/device/+/ota/status   → OTA deployment tracker
```

All subscriptions use **QoS 1** on the cloud subscriber side.

---

## Security Notes

1. **TLS 1.3 only** — TLS 1.2 and below are rejected at the broker.
2. **Certificate rotation**: New certificates are delivered as an OTA config update. Old cert stays valid for 72h overlap window.
3. **Topic ACL**: Broker enforces per-device topic ACL derived from X.509 CN. No device can publish to another device's subtree.
4. **Payload validation**: Cloud-side JSON schema validation on all channels. Malformed messages are logged and dropped (not NACKed — prevents DoS via PUBACK storms).
5. **Rate limiting**: Per-device publish rate capped at 2 msg/sec aggregate across all channels. Excess messages are silently dropped.
