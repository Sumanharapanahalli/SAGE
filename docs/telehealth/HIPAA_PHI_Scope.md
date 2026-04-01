# HIPAA PHI Scope Document — Telehealth Platform
**Version:** 1.0
**Classification:** Confidential — HIPAA Compliance Documentation
**Date:** 2026-03-28
**Regulatory Basis:** 45 CFR Parts 160, 162, 164 (HIPAA Privacy, Security, Breach Notification Rules); HITECH Act (Pub.L. 111-5, Title XIII)

---

## 1. PHI Identifier Inventory

HIPAA identifies 18 categories of Protected Health Information (PHI) under the Safe Harbor de-identification standard (45 CFR §164.514(b)(2)). The table below maps each identifier to the platform modules that collect, process, or transmit it.

| # | PHI Identifier | Video | E-Rx | EHR | AI Triage | Billing | Licensing | Infrastructure |
|---|---------------|-------|------|-----|-----------|---------|-----------|----------------|
| 1 | Names | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (tenant metadata) |
| 2 | Geographic subdivisions smaller than state | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ (IP geo) |
| 3 | Dates (except year) directly related to individual | ✓ (visit dates) | ✓ (Rx date) | ✓ | ✓ | ✓ (claim dates) | — | ✓ (session timestamps) |
| 4 | Phone numbers | ✓ | ✓ | ✓ | ✓ | ✓ | — | — |
| 5 | Fax numbers | — | ✓ (pharmacy fax) | ✓ | — | ✓ | — | — |
| 6 | Email addresses | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ (account mgmt) |
| 7 | Social Security Numbers | — | — | ✓ (imported) | — | ✓ (payer ID) | — | — |
| 8 | Medical record numbers | ✓ | ✓ | ✓ | ✓ | ✓ | — | — |
| 9 | Health plan beneficiary numbers | — | ✓ | ✓ | — | ✓ | — | — |
| 10 | Account numbers | — | — | — | — | ✓ | — | — |
| 11 | Certificate/license numbers | — | — | — | — | — | ✓ (provider licenses) | — |
| 12 | Vehicle identifiers | — | — | — | — | — | — | — |
| 13 | Device identifiers / serial numbers | ✓ (device ID for connection) | — | — | — | — | — | — |
| 14 | Web URLs | — | — | — | — | — | — | ✓ (session URLs) |
| 15 | IP addresses | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ |
| 16 | Biometric identifiers | — | — | — | — | — | — | — |
| 17 | Full-face photographs | ✓ (video frames) | — | ✓ (profile photo) | — | — | — | — |
| 18 | Any other unique identifying number | ✓ (session ID) | ✓ (Surescripts ID) | ✓ (FHIR IDs) | ✓ (triage session ID) | ✓ (claim ID) | ✓ (NPI, DEA) | ✓ (tenant UUID) |

**Note:** Provider NPI, DEA registration numbers, and state license numbers are not PHI by themselves (they are provider identifiers), but become PHI when associated with patient care records.

---

## 2. PHI Data Flow Diagrams

### 2.1 Video Consultation PHI Flow

```
Patient Browser/App
    │ PHI: Name, DOB, session context
    │ Transport: TLS 1.3
    ▼
API Gateway (tenant-routed)
    │ PHI: Session metadata, participant IDs
    │ Validation: X-SAGE-Tenant header → tenant registry
    ▼
Video Session Service (WebRTC)
    │ PHI: Audio/video stream (DTLS-SRTP encrypted E2E)
    │ Metadata: start_time, end_time, session_id, participant_ids
    ▼
Session Metadata Store (tenant schema)          Audit Log (tenant schema)
    │ AES-256, KMS key per tenant               │ Append-only, immutable
    │ Retained: visit metadata only             │ All access events logged
    ▼                                           ▼
EHR Sync (post-session)              Compliance Reporting
    │ FHIR DocumentReference
    └─→ Provider EHR System (TLS 1.3)

NOTE: Raw audio/video NOT stored unless recording consent captured.
      If recorded: stored in s3://platform-phi/<tenant-uuid>/recordings/
      with tenant KMS key, immutable object lock (WORM) for 6 years.
```

### 2.2 E-Prescription PHI Flow

```
Provider (post-consultation)
    │ PHI: Patient name, DOB, address, medication, diagnosis
    │ Auth: MFA-authenticated provider session
    ▼
E-Prescribing Service
    │ Validation: DEA registration check, PDMP query
    │ Drug interaction check (FDB API — BAA in place)
    ▼
PDMP Query (state-specific)          Surescripts Network
    │ PHI: Name, DOB, address         │ PHI: Full Rx data
    │ TLS 1.3 mutual auth             │ NCPDP SCRIPT 2017071
    │ Response logged to tenant DB    │ TLS 1.3 + cert pinning
    ▼                                 ▼
Tenant DB (schema: tenant_<uuid>)   Pharmacy System
    │ AES-256, KMS-encrypted          │ PHI held by pharmacy (separate HIPAA entity)
    │ Rx record retained per state    └─→ Rx fill status back via Surescripts
    ▼
Patient Portal (fill status display)
    │ PHI: Medication name, status
    │ TLS 1.3
    ▼
Patient Device
```

### 2.3 EHR Integration PHI Flow

```
External EHR System (Epic/Cerner)
    │ PHI: Demographics, medications, labs, prior encounters
    │ Protocol: HL7 FHIR R4 / SMART on FHIR 2.0
    │ Transport: TLS 1.3 mutual auth
    ▼
FHIR Integration Service
    │ Validation: FHIR R4 schema validation
    │ Transformation: EHR format → tenant FHIR store
    ▼
Tenant FHIR Repository (schema: tenant_<uuid>)
    │ AES-256, KMS-encrypted
    │ RLS enforced (no cross-tenant access)
    │ FHIR resource audit events → audit log
    ▼
Provider Session View                          Break-The-Glass Override
    │ PHI displayed: demographics,             │ PHI: Full patient record
    │ medications, labs, history               │ Requires: dual admin approval
    │ Access: Provider role only              │ Logged: immediate audit event
    │ Session-scoped access token             │ Post-access: mandatory justification
    ▼
Post-Visit Note Sync
    │ PHI: Encounter note, diagnoses, orders
    │ Protocol: FHIR DocumentReference POST
    │ Delivery: ≤5 min from provider signature
    └─→ External EHR System (TLS 1.3)
```

### 2.4 AI Symptom Checker PHI Flow

```
Patient Browser/App
    │ PHI: Symptoms, duration, severity, age, sex, limited history
    │ Transport: TLS 1.3
    ▼
AI Triage Service
    │ PHI: Structured triage session data
    │ Processing: LLM inference (isolated compute, no cross-tenant model state)
    │ Output: urgency class, differential, recommended pathway
    ▼
Triage Result Display (Patient)             Audit Log (tenant schema)
    │ PHI: Urgency, top 3 conditions        │ Triage session ID, inputs hash,
    │ Disclaimer: Not a medical diagnosis   │ output classification, timestamp
    ▼
If visit initiated:
    │ Triage session ID → linked to encounter ID
    ▼
Provider Session View
    │ Triage summary displayed as context (read-only)
    │ Provider can accept or override triage classification
    ▼
Quality Analytics (de-identified only)
    │ Safe Harbor de-identification applied
    │ 18 identifiers removed per 45 CFR §164.514(b)(2)
    └─→ Accuracy reporting dashboard (no PHI)
```

### 2.5 Medical Billing PHI Flow

```
Encounter Close (Provider signs note)
    │ PHI: Patient demographics, diagnosis codes, procedure codes
    │ Auto-generated: CPT codes, POS code, provider NPI
    ▼
Billing Service
    │ Eligibility Check: ANSI X12 270/271 (PHI: Name, DOB, Member ID)
    │ Transport: TLS 1.3 to clearinghouse
    ▼
Clearinghouse (BAA required)
    │ PHI: Full CMS-1500 / 837P claim data
    │ Transmission: ANSI X12 5010 EDI
    ▼
Payer System                              Payment Processor (PCI DSS Level 1)
    │ PHI: Claim adjudication data         │ PHI: Name, amount (NOT full card)
    │ ERA: ANSI X12 835 response           │ Tokenized card data only
    │ Response → tenant billing ledger     │ PCI scope isolated from PHI scope
    ▼
Tenant Billing Ledger (schema: tenant_<uuid>)
    │ AES-256, KMS-encrypted
    │ Retained: 7 years (CMS requirement)
    │ Access: Billing role only
    ▼
Patient Statement / Portal Balance Display
    │ PHI: Visit date, provider, amount owed
    │ TLS 1.3
    └─→ Patient Device
```

### 2.6 Provider Licensing PHI Flow

```
Provider Credentialing (Admin-initiated)
    │ Provider data: Name, NPI, license #, DEA, state(s)
    │ Note: Provider identifiers, not patient PHI
    ▼
License Verification Service
    │ NPDB Query (weekly automated + on-demand)
    │ DEA Registration Lookup API
    │ State Medical Board APIs (where available)
    ▼
Tenant Provider Registry (schema: tenant_<uuid>)
    │ AES-256, KMS-encrypted
    │ Credential data NOT PHI but stored with PHI-grade controls
    │ Audit: All verification events logged
    ▼
Session Geo-Fence Enforcement
    │ At session initiation: patient state vs. provider license states
    │ Block condition: no valid license match → HTTP 403 + audit event
    ▼
License Expiration Alerts
    │ 90/60/30 day automated email to provider + tenant admin
    │ Auto-suspend if expired (no patient PHI access during suspension)
    └─→ Admin Credentialing Dashboard (no patient PHI)
```

### 2.7 Multi-Tenant Infrastructure PHI Flow

```
Incoming Request
    │ X-SAGE-Tenant header + subdomain
    ▼
API Gateway
    │ Tenant resolution: header → tenant registry → schema name
    │ JWT validation: tenant-scoped access token
    │ Invalid tenant → HTTP 403 + audit event
    ▼
Application Layer (tenant-scoped context)
    │ All DB queries: SET search_path = tenant_<uuid>
    │ All S3 operations: prefix s3://platform-phi/<tenant-uuid>/
    │ All KMS operations: tenant-specific key ARN
    ▼
PostgreSQL (schema-per-tenant)          S3 (prefix-per-tenant)
    │ RLS policies enforced              │ Bucket policy: prefix isolation
    │ No cross-schema queries possible   │ KMS key: tenant-specific
    ▼
Audit Log (per-tenant table)
    │ Append-only, immutable
    │ Fields: actor, action, resource_type, resource_id,
    │         timestamp_utc, source_ip, tenant_id, session_id
    └─→ SIEM Integration (tenant-scoped export only)
```

---

## 3. Encryption Requirements

### 3.1 Encryption at Rest
| Data Type | Encryption Standard | Key Management | Notes |
|-----------|--------------------|-----------------|----- |
| PostgreSQL PHI schemas | AES-256 (RDS encryption) | AWS KMS, tenant-specific CMK | Key rotation: annual |
| S3 PHI objects | AES-256 (SSE-KMS) | AWS KMS, tenant-specific CMK | Object lock (WORM) for recordings |
| Audit log DB | AES-256 (RDS encryption) | AWS KMS, tenant-specific CMK | Immutable after write |
| Provider credential store | AES-256 | AWS KMS, tenant-specific CMK | Same controls as PHI |
| Application secrets (API keys, DB passwords) | AES-256 | AWS Secrets Manager | Auto-rotation 90 days |
| Mobile client local cache | AES-256 (iOS Data Protection, Android Keystore) | Device keychain | Auto-cleared on session expiry |
| Backup snapshots | AES-256 | AWS KMS | Backup CMK separate from data CMK |

### 3.2 Encryption in Transit
| Connection | Protocol | Minimum Version | Certificate | Notes |
|-----------|----------|-----------------|-------------|-------|
| Client → API Gateway | TLS | 1.3 (1.2 for legacy EHR) | ACM-issued, auto-renewed | HSTS enforced |
| Video sessions (WebRTC) | DTLS-SRTP | DTLS 1.2 (SRTP AES-128) | Self-signed per session | E2E encrypted |
| API → Surescripts | TLS | 1.3 | Surescripts cert | Mutual TLS |
| API → FHIR EHR | TLS | 1.3 | EHR-provided cert | Mutual TLS where supported |
| API → NPDB | TLS | 1.2 minimum | Federal PKI | Per NPDB integration requirements |
| API → PDMP | TLS | 1.3 | State-issued cert | Per state PDMP spec |
| API → Clearinghouse | TLS | 1.3 | Clearinghouse cert | SFTP alternative for legacy |
| Intra-service (K8s) | mTLS | 1.3 | Istio service mesh cert | Auto-rotated 24h |
| DB connections | TLS | 1.3 | RDS cert | SSL mode: verify-full |

---

## 4. Access Control Matrix

| Resource | Patient | Provider | Admin | Billing | AI System |
|---------|---------|---------|-------|---------|-----------|
| Own demographic data | Read/Write | Read | Read/Write | Read | No Access |
| Own visit history | Read | Read (own visits) | Read | Read | No Access |
| Own prescriptions | Read | Read/Write (own Rx) | Read | No Access | No Access |
| Other patients' records | No Access | No Access (own panel only) | Read (audit only) | No Access | No Access |
| EHR imported records | Read (own) | Read (own patients) | No Access | No Access | Read (triage only, hashed) |
| Triage session data | Read (own) | Read (linked to encounter) | Read | No Access | Write (create), Read |
| Billing records | Read (own statements) | No Access | Read | Read/Write | No Access |
| Audit log | No Access | No Access | Read | No Access | No Access |
| Provider license records | No Access | Read (own) | Read/Write | No Access | No Access |
| Tenant configuration | No Access | No Access | Read/Write | Read | No Access |
| Cross-tenant data | No Access | No Access | No Access (federation required) | No Access | No Access |
| Admin MFA reset | No Access | No Access | No Access (requires platform support + HITL) | No Access | No Access |

**Access control implementation:** OAuth 2.0 + PKCE for patient/provider authentication; SAML 2.0 for enterprise SSO (health system admin accounts); JWT access tokens scoped to tenant and role; access tokens expire in 15 minutes; refresh tokens expire in 8 hours.

---

## 5. Audit Logging Requirements

### 5.1 Events Requiring Audit Log Entry (per module)

**Video Consultations:**
- Session initiated (actor, patient_id, provider_id, session_id, tenant_id, timestamp)
- Session terminated (duration, termination reason)
- Recording consent captured (Y/N, patient_id, timestamp)
- Recording started / stopped
- Session blocked by licensing enforcement (provider_id, patient_state, reason)
- Break-the-glass access (actor, patient_id, justification, timestamp)

**E-Prescriptions:**
- Prescription created (provider_id, patient_id, medication, schedule class, timestamp)
- PDMP queried (provider_id, patient_id, query_id, timestamp)
- DEA validation check result (provider_id, schedule, state, pass/fail)
- Prescription transmitted to pharmacy (Rx_id, pharmacy_id, timestamp)
- Drug interaction alert displayed and accepted/overridden (alert_id, provider decision)
- Controlled substance Rx blocked (provider_id, reason, timestamp)

**EHR Integration:**
- Patient record imported from EHR (source_ehr, resource_type, patient_id, timestamp)
- Encounter note exported to EHR (encounter_id, destination_ehr, timestamp, success/fail)
- FHIR validation error (resource_type, error_code, timestamp)
- Break-the-glass override (actor, patient_id, justification, approver, timestamp)
- Cross-tenant federation access (granting_tenant, receiving_tenant, resource_scope, approval_id)

**AI Symptom Checker:**
- Triage session initiated (session_id, patient_id, timestamp — no symptom text in log)
- Triage classification generated (session_id, urgency_class, top_condition_categories — no diagnosis codes)
- Provider override of triage (encounter_id, original_class, new_class, provider_id)
- High-risk flag triggered (session_id, flag_type, escalation_action, timestamp)

**Medical Billing:**
- Claim created (claim_id, patient_id, provider_id, amount, timestamp)
- Eligibility check performed (patient_id, payer_id, result, timestamp)
- Claim submitted (claim_id, clearinghouse_id, submission_timestamp)
- Payment posted (claim_id, amount, payer_id, ERA_id, timestamp)
- Denial received (claim_id, denial_code, timestamp)

**Provider Licensing:**
- License verification performed (provider_id, license_number, state, result, timestamp)
- NPDB query result (provider_id, query_id, adverse_action_flag, timestamp)
- License expiration alert sent (provider_id, license_state, expiry_date, days_remaining)
- Provider auto-suspended (provider_id, reason, timestamp)
- Provider suspension lifted (provider_id, admin_actor, timestamp)
- Geo-fence enforcement triggered (session_id, provider_id, patient_state, blocked_states)

**Infrastructure:**
- Tenant provisioned (tenant_id, admin_actor, timestamp)
- Tenant offboarded (tenant_id, admin_actor, data_export_confirmed, timestamp)
- Cross-tenant federation grant created/modified/revoked (grant_id, tenants, scope, approver, timestamp)
- KMS key rotation (key_id, tenant_id, timestamp)
- Admin MFA reset (actor, target_admin, approver, timestamp)

### 5.2 Audit Log Technical Requirements
- **Immutability:** Append-only; no UPDATE or DELETE operations on audit log tables; WAL archiving enabled
- **Retention:** 6 years minimum; 10 years for tenants under CMS Medicare Conditions of Participation
- **Format:** JSON-structured log entries with mandatory fields: `event_id`, `tenant_id`, `actor_id`, `actor_role`, `action`, `resource_type`, `resource_id`, `timestamp_utc`, `source_ip`, `session_id`, `outcome` (success/failure)
- **Export:** Tenant admins can export audit logs in JSON or CSV format for compliance reviews; export events themselves are logged
- **Integrity:** SHA-256 hash chain on audit log entries; daily integrity verification job alerts on chain breaks
- **SIEM:** Real-time streaming to tenant-scoped SIEM (Splunk/Datadog) via secure webhook

---

## 6. Business Associate Agreement (BAA) Requirements Matrix

| Vendor / Service | PHI Shared | BAA Required | BAA Type | Notes |
|-----------------|-----------|-------------|----------|-------|
| AWS (infrastructure) | All PHI | Yes | AWS HIPAA BAA | Auto-available in AWS console |
| Surescripts | Patient Rx data, demographics | Yes | Direct BAA | Surescripts provides standard BAA |
| First Databank (FDB) | Medication context (linked to patient) | Yes | FDB BAA | Drug knowledge base |
| NPDB (federal) | Provider identifiers (not patient PHI) | No — federal agency | N/A | HHS entity, BAA not applicable |
| State PDMP systems | Patient name, DOB, Rx data | Varies by state | State-specific data sharing agreement | Some states require provider agreement, not BAA |
| Clearinghouse (e.g., Availity, Change Healthcare) | Full claims data | Yes | Clearinghouse BAA | Verify clearinghouse is not downstream covered entity |
| Payment Processor (Stripe) | Name, amount (NOT full PHI) | Yes (if any PHI) | Stripe HIPAA BAA | Stripe offers BAA for healthcare customers |
| Language Line (interpreter) | Session audio during interpretation | Yes | Language Line BAA | Required if interpreter joins clinical session |
| SIEM vendor (Splunk/Datadog) | Audit log data (may contain PHI) | Yes | Vendor BAA | Ensure PHI isolation in SIEM indexes |
| Analytics platform (if used) | De-identified data only | No | N/A | Safe Harbor de-identification must be verified pre-export |
| Twilio (SMS/notifications) | PHI in SMS if included | Yes (if PHI) | Twilio BAA | Prefer non-PHI notification content |
| Email provider (SES/SendGrid) | PHI in email body if included | Yes (if PHI) | Vendor BAA | Prefer notification-only emails without clinical content |
| CDN (CloudFront) | PHI in transit through CDN | Covered under AWS BAA | AWS BAA | CloudFront included in AWS HIPAA eligible services |

**BAA Management Requirements:**
- All BAAs stored in the platform's compliance document repository with expiry tracking
- BAA renewal alerts sent 90 days before expiry
- Vendor PHI access suspended upon BAA expiry until renewal confirmed
- BAA inventory reviewed annually by Compliance Officer

---

## 7. Data Retention and Destruction Policies

### 7.1 Retention Schedules

| Data Category | Minimum Retention | Maximum Retention | Legal Basis |
|--------------|------------------|------------------|-------------|
| Patient medical records | 6 years from creation or last use | 10 years (CMS) | 45 CFR §164.530(j); CMS CoPs |
| Audit logs | 6 years | 10 years | 45 CFR §164.312(b) |
| E-Prescription records | 2 years (federal); state law varies (up to 7 years) | 7 years | DEA 21 CFR 1304.04; state law |
| Billing records | 7 years | 10 years | CMS; IRS |
| Video session metadata | 6 years | 10 years | Same as medical records |
| Video recordings (if consented) | 6 years | 10 years | State medical record law |
| PDMP query records | 3 years | 7 years | State PDMP law |
| Provider credential records | 6 years post-termination | 10 years | NPDB requirements |
| AI triage sessions | 6 years (linked to encounter) | 10 years | Same as medical records |

### 7.2 Data Destruction Procedures
1. **Automated retention enforcement:** Platform retention service evaluates records daily against policy; eligible records enter a 30-day deletion queue with admin notification
2. **Tenant offboarding destruction:** Full cryptographic erasure (KMS key scheduled deletion + S3 object deletion) within 24 hours of approved offboarding request; destruction certificate issued
3. **S3 destruction:** AWS S3 Object Versioning + Object Lock (WORM) prevents premature deletion; destruction follows: (a) delete object versions, (b) delete delete-markers, (c) confirm via S3 inventory
4. **Database destruction:** Schema DROP with WAL-confirmed completion; RDS snapshot deletion; KMS CMK scheduled for deletion (7-day AWS mandatory waiting period)
5. **Destruction audit trail:** All destructions logged in platform master audit log (separate from tenant logs, retained 10 years)
6. **Backup purge:** Backup snapshots purged from all backup vaults on destruction schedule; PITR logs deleted at retention boundary

---

## 8. Breach Notification Procedures

### 8.1 HIPAA Breach Notification Requirements (45 CFR §§164.400–414)
- **Individual notification:** ≤60 calendar days from breach discovery; written notice to last known address (email if prior consent)
- **HHS notification (≥500 individuals in a state):** ≤72 hours from discovery (HITECH, Pub.L. 111-5 §13402(e))
- **HHS notification (<500 individuals):** Annual log to HHS no later than 60 days after end of calendar year in which breach occurred
- **Media notification:** ≥500 individuals in a state or jurisdiction → notification to prominent media outlets ≤60 days

### 8.2 Breach Response Workflow

```
Incident Detected
    │
    ▼ (within 1 hour)
Security Incident Response Team (SIRT) notified
    │ Platform security alert → PagerDuty → on-call security engineer
    │
    ▼ (within 4 hours)
Initial Assessment: Is PHI involved?
    │ YES → Treat as potential breach; preserve evidence
    │ NO → Document as non-PHI incident; close
    │
    ▼ (within 24 hours)
Four-Factor Risk Assessment (45 CFR §164.402):
    1. Nature and extent of PHI involved (identifiers, sensitivity)
    2. Identity of person who used or received PHI
    3. Whether PHI was actually acquired or viewed
    4. Extent to which risk has been mitigated
    │
    ▼ (within 48 hours)
Legal + Compliance determination: Breach or Not?
    │ BREACH → Activate notification timeline
    │ NOT BREACH → Document risk assessment; retain 6 years
    │
    ▼ (within 72 hours — HHS if ≥500 in a state)
HHS OCR Breach Portal notification
    │ Required fields: date of breach, date discovered, type of PHI,
    │ cause of breach, number of individuals, safeguards in place
    │
    ▼ (within 60 days — individuals)
Individual notification letters
    │ Content required: description of breach, PHI involved,
    │ steps individuals should take, steps covered entity is taking,
    │ contact information for questions
    │
    ▼ (ongoing)
Remediation + Root Cause Analysis
    │ Corrective action plan
    │ Follow-up testing
    └─→ Post-incident report to tenant admin + board (if applicable)
```

### 8.3 Tenant Breach Notification Support
- Platform provides breach event data export (audit log extract, affected record IDs, timeline) to tenant admin within 4 hours of breach determination
- Platform legal team available as HIPAA Covered Entity support resource
- Breach notification letter template provided; tenant must customize and send
- Platform assists with HHS OCR portal submission data compilation

---

## 9. De-identification Standards

### 9.1 Safe Harbor Method (45 CFR §164.514(b)(2))
All 18 PHI identifiers must be removed or generalized:

| Identifier | Safe Harbor Treatment |
|-----------|----------------------|
| Names | Remove completely |
| Geographic subdivisions | Restrict to first 3 digits of ZIP code; if population <20,000 → replace with 000 |
| Dates (except year) | Remove all dates directly related to individual; keep year only |
| Ages ≥90 | Aggregate to "90 or older" |
| Phone numbers | Remove |
| Fax numbers | Remove |
| Email addresses | Remove |
| SSNs | Remove |
| Medical record numbers | Remove or replace with token |
| Health plan beneficiary numbers | Remove |
| Account numbers | Remove |
| Certificate/license numbers | Remove |
| Vehicle identifiers | Remove |
| Device identifiers | Remove |
| URLs | Remove |
| IP addresses | Remove or truncate to /16 prefix |
| Biometric identifiers | Remove |
| Full-face photographs | Remove or pixelate |
| Other unique identifiers | Remove or replace with token |

### 9.2 Expert Determination Method (45 CFR §164.514(b)(1))
- Requires a qualified statistician to certify that risk of re-identification is very small
- Applies to: population-level analytics, AI model training datasets, published research outputs
- Process: (a) identify quasi-identifiers in dataset, (b) apply k-anonymity (k≥5) and l-diversity analysis, (c) document statistical risk assessment, (d) obtain expert sign-off
- Expert re-certification required if dataset is combined with external data sources

### 9.3 De-identification Use Cases
| Use Case | Method | Approver |
|---------|--------|---------|
| AI model accuracy analytics dashboard | Safe Harbor | Automated (18-identifier check) |
| Quality improvement reporting to tenants | Safe Harbor | Automated + admin review |
| Platform-level aggregate utilization metrics | Safe Harbor | Automated |
| AI model training data preparation | Expert Determination | Compliance Officer + qualified statistician |
| Published outcomes research | Expert Determination | IRB + Compliance Officer |
| Payer population health analytics | Expert Determination | Compliance Officer + tenant admin consent |
