# Threat Model — Elder Fall Detection System
**Document ID:** SEC-TM-001
**Version:** 1.0
**Date:** 2026-03-22
**Methodology:** STRIDE
**Standard:** IEC 62443 / HIPAA Security Rule
**Classification:** Confidential — Medical Device DHF

---

## 1. System Overview

The elder fall detection system consists of four interconnected components:

| Component | Description |
|---|---|
| **Wearable Device** | IMU + GPS sensor node worn by elder; runs embedded firmware; communicates via LTE/Wi-Fi |
| **Cloud Backend** | MQTT broker, REST API, time-series DB, alert engine; hosted in HIPAA-eligible cloud region |
| **Caregiver App** | iOS/Android/Web portal; receives real-time alerts, views history, manages account |
| **Emergency Dispatch API** | Integration with 911/CAD (Computer-Aided Dispatch) systems via authenticated REST webhook |

### 1.1 Trust Boundaries

```
[Wearable Device]  ─── mTLS (MQTT) ───►  [MQTT Broker / Cloud Backend]
                                                    │
                                           JWT+MFA Bearer
                                                    │
                                         [Caregiver App]
                                                    │
                                           API Key + mTLS
                                                    │
                                     [Emergency Dispatch API]
```

Trust boundaries cross at:
- TB-1: Device ↔ MQTT Broker (Internet)
- TB-2: Cloud Backend ↔ Caregiver App (Internet)
- TB-3: Cloud Backend ↔ Emergency Dispatch (Internet)
- TB-4: Physical device boundary (attacker with physical access)

---

## 2. Data Flow Diagram (DFD Level 1)

```
 ┌───────────────────────────────────────────────────────────────┐
 │                    WEARABLE DEVICE (TB-4)                     │
 │  [IMU Sensor] ──► [Fall Detection Algorithm] ──► [MQTT Client]│
 │  [GPS Module] ──► [Location Buffer (AES-256)]                 │
 │  [Firmware]   ──► [Secure Boot Verification]                  │
 └─────────────────────────────┬─────────────────────────────────┘
                               │ mTLS 1.3 (TB-1)
                               ▼
 ┌───────────────────────────────────────────────────────────────┐
 │                    CLOUD BACKEND                              │
 │  [MQTT Broker] ──► [Event Processor] ──► [Alert Engine]      │
 │  [REST API]    ──► [Auth Service]     ──► [Audit Log]         │
 │  [Time-Series DB (AES-256)] ◄── PHI Data Store               │
 │  [Key Management Service]                                     │
 └──────┬──────────────────────────────┬────────────────────────┘
        │ HTTPS/TLS 1.3 + JWT (TB-2)   │ HTTPS/mTLS + API Key (TB-3)
        ▼                              ▼
 ┌─────────────┐              ┌────────────────────┐
 │ CAREGIVER   │              │ EMERGENCY DISPATCH │
 │ APP         │              │ API (CAD System)   │
 │ (iOS/Android│              │                    │
 │  /Web)      │              └────────────────────┘
 └─────────────┘
```

### 2.1 PHI Data Elements

| Data Element | PHI? | Classification | Storage Location |
|---|---|---|---|
| Elder name | Yes | PHI | Cloud DB (AES-256) |
| Elder DOB | Yes | PHI | Cloud DB (AES-256) |
| GPS location history | Yes | PHI | Cloud DB (AES-256) |
| Fall event timestamps | Yes | PHI | Cloud DB (AES-256) |
| Heart rate (if sensor present) | Yes | PHI | Cloud DB (AES-256) |
| Caregiver contact info | Yes | PHI | Cloud DB (AES-256) |
| Device ID (serial) | No | PII-adjacent | Cloud DB (AES-256) |
| Firmware version | No | Internal | Cloud DB (plaintext) |

---

## 3. STRIDE Threat Analysis

### Surface 1: Device Firmware (TB-4 — Physical)

| ID | Category | Threat | Severity | Likelihood | Mitigation |
|---|---|---|---|---|---|
| TH-FW-01 | **Tampering** | Attacker with physical access replaces firmware via JTAG/UART debug port to inject malicious code that silences fall alerts or exfiltrates GPS data | **Critical** | Medium | Disable JTAG/SWD in production fuses; enforce secure boot with hardware root of trust (ROM-based); firmware signed with RSA-4096/ECDSA-P384; boot ROM verifies signature before execution |
| TH-FW-02 | **Spoofing** | Cloned device with spoofed device certificate impersonates legitimate elder device to inject false fall events or suppress real ones | **Critical** | Low | Per-device X.509 certificate provisioned in factory; certificates stored in hardware secure element (TPM or SE050); certificate pinned in MQTT broker ACL; device serial tied to certificate CN |
| TH-FW-03 | **Information Disclosure** | Debug logs containing GPS coordinates or elder identity written to unprotected flash and extractable via physical access | **High** | Medium | Debug logging disabled in production build via compile-time flag; sensitive data in RAM cleared after transmission; flash storage encrypted with AES-256-XTS; hardware secure element for key storage |
| TH-FW-04 | **Denial of Service** | Firmware update mechanism abused to brick device by pushing invalid firmware, preventing fall detection | **High** | Low | Firmware updates validated against signed manifest before flashing; A/B partition scheme with automatic rollback on boot failure; OTA updates require mutual authentication |
| TH-FW-05 | **Elevation of Privilege** | Exploit in fall-detection application escapes to OS/RTOS level and gains full device control | **High** | Low | RTOS task isolation; stack canaries; MPU memory protection enabled; minimal attack surface (no shell, no unnecessary services); static analysis in CI pipeline |
| TH-FW-06 | **Repudiation** | Device denies sending a fall alert; no integrity proof that event originated from this specific device | **Medium** | Low | Events signed with device private key (stored in secure element) before transmission; cloud backend verifies signature and records in immutable audit log |

---

### Surface 2: Device–Cloud Channel / MQTT (TB-1)

| ID | Category | Threat | Severity | Likelihood | Mitigation |
|---|---|---|---|---|---|
| TH-CH-01 | **Information Disclosure** | MQTT traffic intercepted on cellular/Wi-Fi path exposing PHI (GPS location, fall events, elder identity) | **Critical** | Medium | Mutual TLS 1.3 enforced on all MQTT connections; TLS 1.2 minimum with cipher suite restriction (ECDHE-RSA-AES256-GCM-SHA384+); payload-level AES-256-GCM encryption as defense-in-depth; no plaintext fallback |
| TH-CH-02 | **Spoofing** | Man-in-the-middle substitutes cloud certificate with attacker certificate to intercept or modify MQTT messages | **Critical** | Low | Certificate pinning on device (hash of CA and leaf cert stored in secure element); client rejects any cert not matching pinned chain; certificate transparency monitoring for unexpected issuance |
| TH-CH-03 | **Tampering** | GPS coordinates in MQTT payload modified in transit to report false location during emergency | **Critical** | Low | TLS record integrity (AEAD) prevents undetected modification; device signs payload with private key; broker verifies signature before forwarding to event processor |
| TH-CH-04 | **Spoofing** | GPS signal spoofed at RF level causing device to report false location coordinates | **High** | Medium | Multi-constellation GNSS (GPS+GLONASS+Galileo) reduces single-point spoofing; anomaly detection in cloud (sudden location jumps flagged); Wi-Fi/cell tower cross-validation of reported position |
| TH-CH-05 | **Denial of Service** | MQTT broker flooded with connection attempts or large payloads, preventing legitimate device events from reaching cloud | **High** | Medium | Rate limiting per device certificate; connection throttling on broker; separate broker cluster for device ingestion vs. other traffic; payload size cap enforced |
| TH-CH-06 | **Repudiation** | Carrier denies message was delivered; no proof of transmission for compliance audit | **Medium** | Low | MQTT QoS 1 (at-least-once) with cloud-side deduplication; device logs outbound event with sequence number; cloud acknowledges with signed receipt stored in audit log |

---

### Surface 3: Cloud Backend

| ID | Category | Threat | Severity | Likelihood | Mitigation |
|---|---|---|---|---|---|
| TH-CB-01 | **Information Disclosure** | Database breach exposes PHI for all enrolled elders (HIPAA breach event) | **Critical** | Low | AES-256 encryption at rest (managed key in KMS, customer-managed key option); field-level encryption for highest-sensitivity fields (location history, identity); HSM-backed key storage; quarterly penetration testing |
| TH-CB-02 | **Elevation of Privilege** | SQL/NoSQL injection in REST API allows attacker to access records across tenant boundaries | **Critical** | Medium | Parameterized queries enforced (ORM, no raw string concatenation); input validation and schema enforcement; principle of least privilege for DB service accounts; row-level security enforced at DB layer |
| TH-CB-03 | **Tampering** | Attacker modifies historical fall event records in database to alter elder's medical history | **High** | Low | Immutable audit log (append-only table with periodic Merkle hash anchoring); all writes to PHI tables go through API layer (no direct DB write access); change data capture logged with actor identity |
| TH-CB-04 | **Spoofing** | Compromised caregiver JWT reused after logout or token theft to access elder records | **High** | Medium | Short JWT expiry (15 min access token, 8 hr refresh); refresh token rotation; server-side token blacklist on logout; bind token to device fingerprint; re-authentication required for sensitive operations |
| TH-CB-05 | **Denial of Service** | Alert engine overwhelmed by high-volume fall events (real or injected), delaying emergency notifications | **High** | Medium | Priority queue for fall alert processing; rate limiting per device; circuit breaker on downstream emergency dispatch; horizontal auto-scaling on alert processor service |
| TH-CB-06 | **Repudiation** | Cloud service operator or insider accesses PHI without authorization and denies doing so | **High** | Low | All data access logged with IAM identity in immutable SIEM-forwarded audit trail; privileged access requires just-in-time approval and session recording; HIPAA audit controls (§164.312(b)) |
| TH-CB-07 | **Information Disclosure** | API error responses leak internal stack traces, DB schema, or PHI to unauthenticated callers | **Medium** | Medium | Generic error responses in production; detailed errors to structured logs only; secrets scanning in CI; API gateway masks internal error codes |

---

### Surface 4: Caregiver App

| ID | Category | Threat | Severity | Likelihood | Mitigation |
|---|---|---|---|---|---|
| TH-CA-01 | **Spoofing** | Credential stuffing or brute force attack gains unauthorized access to caregiver account, exposing elder PHI and allowing suppression of alerts | **Critical** | High | MFA mandatory for all caregiver accounts (TOTP or hardware key); account lockout after 5 failed attempts; anomalous login detection (new device/location step-up auth); no SMS OTP (SIM swap risk) |
| TH-CA-02 | **Information Disclosure** | Mobile app caches PHI (location history, fall events) insecurely in local storage accessible to other apps or via backup | **High** | Medium | PHI in memory only during active session; no caching to disk; iOS Data Protection class completeUnlessOpen; Android EncryptedSharedPreferences; app transport security enforced; screenshot prevention on sensitive screens |
| TH-CA-03 | **Tampering** | Repackaged/trojanized version of caregiver app distributed via third-party stores to harvest credentials | **High** | Medium | App signing with pinned certificate; certificate transparency; in-app attestation (Play Integrity API / App Attest for iOS); users warned against sideloading; root/jailbreak detection |
| TH-CA-04 | **Elevation of Privilege** | Unauthorized caregiver attempts to access records of elders not assigned to them (horizontal privilege escalation) | **High** | Medium | Backend enforces caregiver-elder assignment; all API responses filtered server-side by caregiver identity; no client-side access control; IDOR prevention via opaque UUIDs |
| TH-CA-05 | **Denial of Service** | Push notification channel (APNs/FCM) disrupted, preventing caregiver from receiving fall alerts on mobile | **High** | Medium | Redundant notification channels (push + SMS fallback + email); notification delivery receipt tracking; caregiver portal polling as tertiary fallback |
| TH-CA-06 | **Repudiation** | Caregiver claims they never received fall alert or took no action; no audit evidence for regulatory review | **Medium** | Low | Server-side alert delivery log with timestamp; push notification delivery receipts; caregiver acknowledgment action logged with identity and timestamp; exportable audit trail for compliance |

---

### Surface 5: Emergency Dispatch API

| ID | Category | Threat | Severity | Likelihood | Mitigation |
|---|---|---|---|---|---|
| TH-ED-01 | **Spoofing** | Unauthorized third party calls emergency dispatch webhook to trigger false 911 dispatch to elder's address | **Critical** | Medium | Mutual TLS between cloud backend and dispatch API; static IP allowlisting; per-tenant API key with HMAC request signing; dispatch API validates event signature against registered public key |
| TH-ED-02 | **Tampering** | Fall event payload modified in transit to alter elder address, GPS coordinates, or severity before reaching CAD system | **Critical** | Low | mTLS record integrity; payload signed by cloud backend (ECDSA-P256); CAD integration layer verifies signature before dispatching; any modification invalidates signature |
| TH-ED-03 | **Denial of Service** | Emergency dispatch API endpoint flooded with requests, delaying or blocking real emergency notifications | **Critical** | Low | Dedicated egress path for emergency dispatch; circuit breaker with exponential backoff; out-of-band alerting to dispatch agency if integration fails; fall-back to direct caregiver SMS with instructions to call 911 |
| TH-ED-04 | **Information Disclosure** | Emergency dispatch webhook response leaks CAD event ID or internal dispatch details back to attacker | **High** | Low | API response contains only confirmation token; no PHI in response body; TLS prevents interception; response logged server-side only |
| TH-ED-05 | **Repudiation** | Dispatch agency claims they never received a fall alert; cloud denies sending it | **High** | Low | Cloud backend stores signed request with timestamp and HTTP response code; dispatch API issues signed confirmation receipt; mutual non-repudiation via cryptographic exchange |
| TH-ED-06 | **Elevation of Privilege** | Compromised dispatch API key used to access other cloud backend endpoints beyond emergency notification scope | **High** | Low | Dispatch API key scoped to single endpoint (POST /emergency/dispatch) via API gateway policy; key cannot authenticate to any other endpoint; key rotation every 90 days |

---

## 4. Risk Summary Matrix

| Severity | Count | Threat IDs |
|---|---|---|
| **Critical** | 11 | TH-FW-01, TH-FW-02, TH-CH-01, TH-CH-02, TH-CH-03, TH-CB-01, TH-CB-02, TH-CA-01, TH-ED-01, TH-ED-02, TH-ED-03 |
| **High** | 16 | TH-FW-03, TH-FW-04, TH-FW-05, TH-CH-04, TH-CH-05, TH-CB-03, TH-CB-04, TH-CB-05, TH-CB-06, TH-CA-02, TH-CA-03, TH-CA-04, TH-CA-05, TH-ED-04, TH-ED-05, TH-ED-06 |
| **Medium** | 4 | TH-FW-06, TH-CH-06, TH-CB-07, TH-CA-06 |
| **Low** | 0 | — |

---

## 5. Assumptions and Exclusions

**Assumptions:**
- Cloud provider (AWS/Azure/GCP) HIPAA BAA is in place
- Factory provisioning environment is physically secured
- Cellular carrier network is an untrusted transport (threats mitigated at application layer)

**Out of Scope (this document):**
- Physical security of cloud data centers (delegated to cloud provider SOC 2 Type II)
- Social engineering attacks on caregivers (addressed in user training documentation)
- Denial-of-service at internet/ISP level

---

## 6. Document Control

| Role | Name | Signature | Date |
|---|---|---|---|
| Author | Security Architect | __________ | 2026-03-22 |
| Review | Clinical Safety Officer | __________ | |
| Approval | DHF Owner | __________ | |

**References:**
- IEC 62443-4-1 (Secure Product Development Lifecycle)
- IEC 62443-4-2 (Technical Security Requirements for IACS Components)
- HIPAA Security Rule 45 CFR §164.300-§164.318
- NIST SP 800-30 (Risk Assessment)
- OWASP IoT Attack Surface Areas
