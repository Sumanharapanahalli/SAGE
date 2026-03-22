# NG911 Emergency Dispatch — CAP 1.2 Webhook Integration

> **Standard**: OASIS Common Alerting Protocol v1.2 (CAP-v1.2-os)
> **Transport**: HTTPS POST with JSON-serialized CAP payload
> **Authentication**: HMAC-SHA256 shared-secret signatures
> **Direction**: EFDS → PSAP Gateway (outbound alerts), PSAP Gateway → EFDS (status callbacks)

---

## Overview

The Elder Fall Detection System (EFDS) integrates with Next Generation 911 (NG911) Public Safety Answering Points (PSAPs) via the Common Alerting Protocol (CAP) 1.2 standard. When a fall event requires emergency dispatch — either automatically (critical severity) or manually (caregiver-triggered) — EFDS generates a CAP 1.2 alert and POSTs it to the configured NG911 gateway.

### Flow

```
1. Fall detected → Device publishes to MQTT fall channel (QoS 2)
2. Cloud classifies severity using device ML result + server-side validation
3. If severity=critical OR caregiver dispatches manually:
   a. Generate CAP 1.2 alert payload
   b. POST to NG911 PSAP gateway endpoint
   c. Log dispatch to audit trail
4. PSAP receives alert → dispatches EMS
5. PSAP sends status callbacks → EFDS updates incident record
6. Caregiver app shows real-time dispatch status
```

---

## Outbound: EFDS → PSAP Gateway

### Endpoint (configured per deployment)

```
POST https://{psap-gateway-host}/api/v1/alerts
Content-Type: application/json
X-EFDS-Signature: {hmac_sha256_hex}
X-EFDS-Timestamp: {unix_epoch_seconds}
X-EFDS-Sender-Id: {efds_deployment_id}
```

### Authentication

- **HMAC-SHA256** computed over the raw request body using a pre-shared secret.
- `X-EFDS-Signature` = `hex(HMAC-SHA256(shared_secret, request_body))`
- `X-EFDS-Timestamp` = Unix epoch seconds. PSAP gateway SHOULD reject if timestamp is > 5 minutes old.
- Shared secret is exchanged out-of-band during PSAP onboarding and rotated quarterly.

### CAP 1.2 Alert Payload

Full JSON-serialized CAP 1.2 alert per OASIS specification. All field names match the CAP 1.2 XML element names for interoperability.

```json
{
  "identifier": "efds-fall-550e8400-e29b-41d4-a716-446655440000",
  "sender": "efds@efds.example.com",
  "sent": "2026-03-22T14:33:00-05:00",
  "status": "Actual",
  "msgType": "Alert",
  "scope": "Private",
  "addresses": "psap-nyc-manh-01",
  "code": ["IPAWSv1.0"],
  "note": "Automated fall detection alert from EFDS monitoring platform",
  "info": [
    {
      "language": "en-US",
      "category": ["Safety", "Health"],
      "event": "Fall Detected — Elderly Person",
      "responseType": ["Execute"],
      "urgency": "Immediate",
      "severity": "Severe",
      "certainty": "Observed",
      "audience": "Emergency Medical Services",
      "eventCode": [
        {
          "valueName": "SAME",
          "value": "CEM"
        },
        {
          "valueName": "EFDS-EventType",
          "value": "FALL_CRITICAL"
        }
      ],
      "effective": "2026-03-22T14:32:45-05:00",
      "onset": "2026-03-22T14:32:45-05:00",
      "expires": "2026-03-22T15:32:45-05:00",
      "senderName": "EFDS Emergency Monitoring Platform",
      "headline": "FALL ALERT: Jane Doe, 78F — 42 Maple St, New York, NY",
      "description": "Automated fall detection system has detected a high-severity fall event. Patient: Jane Doe, Age: 78, Female. Device reports 4.7g impact force followed by 45 seconds of post-fall stillness. Patient has not manually acknowledged the alert or pressed the SOS button. GPS coordinates indicate indoor location at registered home address.",
      "instruction": "Dispatch EMS to 42 Maple St, Apt 3B, New York, NY 10001. Patient is 78-year-old female with history of osteoporosis (per caregiver profile). High-severity fall detected at 14:32 UTC. No patient response after 45 seconds. Primary caregiver (Mary Doe) has been notified via push notification.",
      "web": "https://app.efds.example.com/incidents/550e8400-e29b-41d4-a716-446655440000",
      "contact": "Primary caregiver: Mary Doe, +1-555-0199. EFDS Support: +1-800-EFDS-911",
      "parameter": [
        {
          "valueName": "EFDSDeviceId",
          "value": "d1e2f3a4-b5c6-7890-abcd-ef1234567890"
        },
        {
          "valueName": "EFDSFallId",
          "value": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        },
        {
          "valueName": "EFDSSeverity",
          "value": "critical"
        },
        {
          "valueName": "EFDSPatientName",
          "value": "Jane Doe"
        },
        {
          "valueName": "EFDSPatientAge",
          "value": "78"
        },
        {
          "valueName": "EFDSGForce",
          "value": "4.7"
        },
        {
          "valueName": "EFDSStillnessSeconds",
          "value": "45"
        }
      ],
      "area": [
        {
          "areaDesc": "42 Maple St, Apt 3B, New York, NY 10001",
          "circle": "40.7128,-74.006 0.05",
          "geocode": [
            {
              "valueName": "FIPS6",
              "value": "036061"
            },
            {
              "valueName": "UGC",
              "value": "NYZ072"
            }
          ]
        }
      ]
    }
  ]
}
```

### CAP 1.2 Field Mapping — EFDS to CAP

| CAP Field | EFDS Source | Notes |
|---|---|---|
| `identifier` | `efds-fall-{fall_id}` | Globally unique. Prefix ensures no collision with other CAP senders. |
| `sender` | Deployment config | Registered sender ID with PSAP gateway |
| `sent` | Server UTC time | ISO 8601 with timezone offset |
| `status` | Always `Actual` | Use `Test` only in staging environments |
| `msgType` | `Alert` / `Update` / `Cancel` | `Update` for severity re-classification. `Cancel` if false positive confirmed. |
| `scope` | `Private` | Directed to specific PSAP(s) only |
| `addresses` | PSAP routing table | Space-separated PSAP identifiers from geo-routing |
| `info.category` | `["Safety", "Health"]` | Fixed for fall events |
| `info.event` | `"Fall Detected — Elderly Person"` | Fixed event string |
| `info.urgency` | Severity-mapped | critical/high → `Immediate`, medium → `Expected`, low → `Future` |
| `info.severity` | Severity-mapped | critical → `Extreme`, high → `Severe`, medium → `Moderate`, low → `Minor` |
| `info.certainty` | `Observed` | On-device ML + accelerometer data = direct observation |
| `info.headline` | Generated | `"FALL ALERT: {name}, {age}{sex} — {address}"` (max 160 chars) |
| `info.description` | Generated | Full incident summary with device data |
| `info.instruction` | Generated | Dispatch instructions with patient medical context |
| `info.area.circle` | GPS fix | `lat,lon radius_km` — radius = max(GPS accuracy, 0.05km) |
| `info.area.geocode` | Reverse geocode | FIPS and UGC codes from GPS coordinates |

### Severity → CAP Urgency/Severity Mapping

| EFDS Severity | CAP `urgency` | CAP `severity` | Auto-Dispatch? |
|---|---|---|---|
| `critical` | `Immediate` | `Extreme` | Yes — automatic |
| `high` | `Immediate` | `Severe` | No — caregiver must trigger |
| `medium` | `Expected` | `Moderate` | No — caregiver must trigger |
| `low` | `Future` | `Minor` | No — caregiver must trigger |

Only `critical` severity triggers automatic NG911 dispatch. All other severities require the caregiver to explicitly request dispatch via `POST /alerts/{alertId}/dispatch-911`.

---

## Inbound: PSAP Gateway → EFDS (Status Callbacks)

### Endpoint

```
POST https://api.efds.example.com/v1/webhooks/ng911/status
Content-Type: application/json
X-NG911-Signature: {hmac_sha256_hex}
X-NG911-Timestamp: {unix_epoch_seconds}
```

### Authentication

- `X-NG911-Signature` = `hex(HMAC-SHA256(shared_secret, request_body))`
- `X-NG911-Timestamp` = Unix epoch seconds. EFDS rejects if > 5 minutes old (replay protection).
- Different shared secret from the outbound direction (separate key per direction).

### Status Callback Payload

```json
{
  "cap_identifier": "efds-fall-550e8400-e29b-41d4-a716-446655440000",
  "status": "dispatched",
  "unit_id": "FDNY-EMS-42",
  "updated_at": "2026-03-22T14:36:00-05:00",
  "notes": "EMS Unit 42 dispatched. ETA 8 minutes."
}
```

### Status Lifecycle

```
received → dispatched → on_scene → closed
                                  → cancelled
```

| Status | Description | EFDS Action |
|---|---|---|
| `received` | PSAP acknowledged receipt of CAP alert | Update incident record. Notify caregiver: "911 received your alert." |
| `dispatched` | EMS unit assigned and en route | Update incident. Notify caregiver with unit_id and ETA if available. |
| `on_scene` | EMS arrived at location | Update incident. Notify caregiver: "EMS has arrived." |
| `closed` | Incident resolved | Close incident record. Final audit log entry. |
| `cancelled` | PSAP cancelled response (e.g., false alarm confirmed) | Update incident. Notify caregiver. |

### Idempotency

EFDS handles duplicate status callbacks gracefully. If the same `cap_identifier` + `status` combination is received more than once, the duplicate is logged but does not trigger duplicate notifications or state changes.

---

## Error Handling and Retry

### Outbound (EFDS → PSAP)

| Scenario | Behavior |
|---|---|
| PSAP returns 2xx | Success. Log dispatch. |
| PSAP returns 4xx | Do not retry. Log error. Alert operations team. |
| PSAP returns 5xx | Retry with exponential backoff: 5s, 15s, 45s, 135s, 300s (max 5 retries over ~8 min). |
| Network timeout (30s) | Treat as 5xx — enter retry loop. |
| All retries exhausted | Log critical alert. Notify operations team via PagerDuty. Caregiver app shows "911 dispatch failed — call 911 manually" with one-tap dialer. |

### Inbound (PSAP → EFDS)

| Scenario | Behavior |
|---|---|
| Valid signature + payload | Return 200 `{"acknowledged": true}` |
| Invalid HMAC signature | Return 401. Log security event. |
| Timestamp > 5 min old | Return 401 (replay). Log security event. |
| Unknown cap_identifier | Return 200 (do not reject — PSAP may have routing delays). Log warning. |
| Malformed JSON | Return 400 with error detail. |

---

## CAP 1.2 Update and Cancel Messages

### Update (Severity Re-classification)

If the cloud-side ML model re-classifies a fall (e.g., after reviewing the raw accelerometer buffer), EFDS sends a CAP Update:

```json
{
  "identifier": "efds-fall-550e8400-e29b-41d4-a716-446655440000-update-1",
  "sender": "efds@efds.example.com",
  "sent": "2026-03-22T14:38:00-05:00",
  "status": "Actual",
  "msgType": "Update",
  "scope": "Private",
  "addresses": "psap-nyc-manh-01",
  "references": "efds@efds.example.com,efds-fall-550e8400-e29b-41d4-a716-446655440000,2026-03-22T14:33:00-05:00",
  "info": [
    {
      "language": "en-US",
      "category": ["Safety", "Health"],
      "event": "Fall Detected — Severity Update",
      "urgency": "Immediate",
      "severity": "Extreme",
      "certainty": "Observed",
      "headline": "UPDATE: Fall severity upgraded to CRITICAL for Jane Doe, 78F",
      "description": "Server-side ML re-analysis of raw accelerometer data confirms critical-severity fall. Patient vitals show elevated heart rate (108 bpm) and declining SpO2 (91%). Recommend priority dispatch.",
      "area": [
        {
          "areaDesc": "42 Maple St, Apt 3B, New York, NY 10001",
          "circle": "40.7128,-74.006 0.05"
        }
      ]
    }
  ]
}
```

### Cancel (False Positive)

If the caregiver confirms the alert was a false positive (e.g., patient dropped the device):

```json
{
  "identifier": "efds-fall-550e8400-e29b-41d4-a716-446655440000-cancel-1",
  "sender": "efds@efds.example.com",
  "sent": "2026-03-22T14:40:00-05:00",
  "status": "Actual",
  "msgType": "Cancel",
  "scope": "Private",
  "addresses": "psap-nyc-manh-01",
  "references": "efds@efds.example.com,efds-fall-550e8400-e29b-41d4-a716-446655440000,2026-03-22T14:33:00-05:00",
  "note": "Alert cancelled by caregiver. Patient confirmed safe. Device was dropped, not a fall.",
  "info": [
    {
      "language": "en-US",
      "category": ["Safety"],
      "event": "Fall Alert Cancelled — False Positive",
      "urgency": "Past",
      "severity": "Minor",
      "certainty": "Unlikely",
      "headline": "CANCEL: Fall alert for Jane Doe was false positive",
      "description": "Caregiver Mary Doe confirmed patient is safe. The device was dropped during normal activity. No medical assistance required.",
      "area": [
        {
          "areaDesc": "42 Maple St, Apt 3B, New York, NY 10001",
          "circle": "40.7128,-74.006 0.05"
        }
      ]
    }
  ]
}
```

---

## PSAP Onboarding Checklist

1. Exchange HMAC shared secrets (one per direction) via secure channel
2. Configure PSAP gateway endpoint URL in EFDS deployment config
3. Register EFDS sender ID (`efds@{deployment}.example.com`) with PSAP
4. Configure geographic routing rules (which PSAP serves which area codes/FIPS regions)
5. Send `status: Test` CAP alert to verify end-to-end connectivity
6. Verify status callback flow (PSAP → EFDS webhook)
7. Conduct tabletop exercise with live test alerts (status=Exercise)
8. Sign off on production readiness — switch to `status: Actual`

---

## Compliance Notes

- **FCC NG911 requirements**: EFDS CAP alerts include location (GPS), callback number (caregiver contact), and caller identity (patient name/age) per FCC Third Report and Order on NG911.
- **NENA i3 standard**: CAP payloads are compatible with NENA i3 Additional Data for NG911 conveyance.
- **HIPAA**: Patient name and age are included in CAP alerts under the HIPAA emergency treatment exception (45 CFR 164.512(f) — disclosures for law enforcement purposes, and 164.510(b) — notification for emergency circumstances). The minimum necessary information is disclosed.
- **Audit trail**: Every CAP alert sent/received is logged in the solution's `.sage/audit_log.db` with full payload, timestamp, PSAP identifiers, and outcome status.
- **Data retention**: CAP alert records and PSAP status callbacks are retained for 7 years per state EMS records retention requirements (varies by jurisdiction — 7 years is the maximum).
