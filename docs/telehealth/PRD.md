# Product Requirements Document — HIPAA-Compliant Telehealth Platform
**Version:** 1.0
**Status:** Draft for Review
**Author:** Product Strategy, SAGE Framework
**Date:** 2026-03-28
**Classification:** Confidential — Internal Use Only

---

## Executive Summary

This document defines the product requirements for a HIPAA-compliant, multi-tenant telehealth platform designed to connect patients with licensed healthcare providers across 50 US states and territories. The platform delivers seven core clinical and operational modules: Video Consultations, E-Prescriptions, EHR Integration, AI Symptom Checker, Medical Billing, Provider Licensing Enforcement, and Multi-Tenant Infrastructure.

The platform is built on a schema-per-tenant PostgreSQL isolation model with tenant identification via X-SAGE-Tenant header and subdomain routing. Every tenant operates in full PHI isolation with dedicated audit logs, provider rosters, billing accounts, S3 prefixes, and KMS encryption keys. Cross-tenant data federation requires explicit grants with Human-in-the-Loop (HITL) approval, ensuring HIPAA's minimum necessary standard is enforced architecturally.

Target market: health systems, insurance carriers, employer health plans, and direct-to-consumer telehealth operators seeking a compliant, white-label-capable platform.

**Strategic outcome:** Enable any healthcare organization to deploy a fully operational telehealth program within 30 days, with HIPAA compliance inherited from the platform rather than built per customer.

---

## Problem Statement

Healthcare access in the United States is constrained by geography, provider availability, and administrative complexity. Over 100 million Americans live in Health Professional Shortage Areas (HPSAs). Telehealth adoption accelerated during COVID-19 under relaxed CMS waivers (PHE flexibilities), but permanent legislative clarity on state licensure and parity payment has arrived inconsistently. Existing telehealth platforms either compromise on compliance (consumer apps) or charge enterprise premiums that exclude mid-market health systems.

**Primary problems this platform solves:**

1. **Provider geographic bottleneck** — Patients cannot access specialists in their state. Providers licensed under IMLC, PSYPACT, or NLC compacts can see patients across participating states, but existing platforms do not enforce licensing at the session level.

2. **Administrative fragmentation** — Scheduling, prescribing, billing, and documentation exist in siloed tools. Providers spend 35-40% of clinical time on administrative tasks (AMA Physician Survey 2024).

3. **HIPAA compliance as a build burden** — Every organization building on third-party APIs must independently implement BAA chains, audit logging, encryption, and breach notification. This creates inconsistent compliance postures across the market.

4. **Multi-tenant scalability** — Health systems running employer programs, Medicaid panels, and commercial panels simultaneously require data isolation between populations that most platforms do not provide.

**Goals:**

| # | Goal | Metric | Target |
|---|------|--------|--------|
| G-1 | Patient engagement | 30-day return rate | ≥70% |
| G-2 | Consultation completion | Completed / Initiated ratio | ≥85% |
| G-3 | Platform availability | Uptime SLA | 99.9% |
| G-4 | E-prescription adoption | Fill rate within 24h | ≥90% |
| G-5 | AI triage accuracy | Agreement with provider diagnosis | ≥80% |
| G-6 | Time-to-first-consultation | From registration to first visit | ≤15 minutes |
| G-7 | Licensing enforcement | Zero cross-state prescribing violations | 100% |

---

## User Personas

### Persona 1: Patient — "Maria, 42, Suburban Working Parent"
- **Needs:** Book same-day appointments, access prescriptions, view visit summaries
- **Pain points:** Long wait times for specialist appointments, fragmented care records, lack of after-hours coverage
- **Tech comfort:** High smartphone literacy, uses health apps but unfamiliar with EHR portals
- **HIPAA concern:** Wants to know who sees her records; prefers not to share data beyond her care team

### Persona 2: Provider — "Dr. James, MD, Licensed in CA + IMLC"
- **Needs:** Efficient documentation, integrated prescribing, license compliance automation, billing transparency
- **Pain points:** Manual PDMP lookups before prescribing controlled substances, state board verification delays, EHR context-switching
- **Tech comfort:** Moderate; prefers streamlined workflow over feature richness
- **Regulatory concern:** Wants platform to enforce licensing rules so he is never inadvertently out of compliance

### Persona 3: Admin — "Sarah, Health System Operations Manager"
- **Needs:** Provider credentialing management, tenant configuration, reporting, payer setup
- **Pain points:** Manual credentialing spreadsheets, inability to see real-time license status, inconsistent billing reconciliation
- **Tech comfort:** High; comfortable with dashboards and bulk operations
- **Compliance concern:** Needs audit logs exportable for HIPAA compliance reviews and state audits

### Persona 4: Payer — "TechHealthCo, Self-Insured Employer with 8,000 Members"
- **Needs:** Tenant-level reporting, utilization analytics, cost-per-visit benchmarks, formulary enforcement
- **Pain points:** Lack of visibility into telehealth ROI, no per-member cost attribution, manual invoice reconciliation
- **Tech concern:** API access for claims integration with internal benefits platform

---

## Functional Requirements

### Module 1: Video Consultations

**FR-001** The system SHALL support WebRTC-based encrypted video sessions between one provider and one patient with end-to-end encryption (DTLS-SRTP).

**FR-002** The system SHALL support group video sessions with up to 5 participants (patient + family members + provider + specialist) for complex care coordination.

**FR-003** The system SHALL provide audio-only fallback when video bandwidth is insufficient (<500 kbps), with automatic degradation and patient notification.

**FR-004** The system SHALL enforce session recording consent per applicable state law prior to initiating recording, storing consent in the tenant's audit log.

**FR-005** The system SHALL display real-time connection quality indicators (packet loss, latency, jitter) to both provider and patient.

**FR-006** The system SHALL support virtual waiting rooms with configurable estimated wait time display and provider availability indicators.

**FR-007** The system SHALL allow providers to share screens during consultation for review of imaging results, lab reports, or educational materials.

**FR-008** The system SHALL terminate sessions automatically if the provider's license is not valid for the patient's state of presence at session initiation.

**FR-009** The system SHALL support interpreter integration via third-party Language Line or equivalent, launched from within the session interface.

**FR-010** The system SHALL log session metadata (start time, end time, participant IDs, session ID, connection quality metrics) to the tenant-isolated audit log without storing audio/video content unless recording is explicitly consented.

### Module 2: E-Prescriptions

**FR-011** The system SHALL integrate with Surescripts for electronic prescribing, supporting NCPDP SCRIPT standard 2017071 for new prescriptions, refill requests, and cancellations.

**FR-012** The system SHALL enforce PDMP (Prescription Drug Monitoring Program) consultation before prescribing Schedule II–V controlled substances, per DEA 21 CFR Part 1306 and applicable state PDMP mandates.

**FR-013** The system SHALL block e-prescriptions for controlled substances if the provider does not have a valid DEA registration number with the appropriate schedule authorization for the patient's state.

**FR-014** The system SHALL support e-prescribing of controlled substances via DEA-compliant EPCS (Electronic Prescriptions for Controlled Substances) with two-factor authentication per 21 CFR 1311.

**FR-015** The system SHALL display drug-drug interaction alerts, allergy contraindications, and formulary coverage status at the time of prescribing, sourced from a certified First Databank (FDB) or Multum drug knowledge base.

**FR-016** The system SHALL support medication favorites, prior prescriptions by the provider, and patient medication history imported from the EHR for prescribing efficiency.

**FR-017** The system SHALL enforce state-specific prescribing restrictions (e.g., Florida's CS prescribing restrictions requiring in-person exam for initial opioid prescriptions, Texas telemedicine prescribing rules under Tex. Occ. Code §111.005).

**FR-018** The system SHALL transmit prescriptions to the patient's preferred pharmacy within 2 seconds of provider signature.

**FR-019** The system SHALL track prescription fill status (dispensed, partially dispensed, not dispensed) via Surescripts real-time benefit check and surface 24-hour fill rate to administrators.

**FR-020** The system SHALL support formulary management per tenant, allowing payer tenants to enforce preferred drug lists and flag non-formulary prescriptions with prior authorization requirements.

### Module 3: EHR Integration

**FR-021** The system SHALL support bi-directional HL7 FHIR R4 integration with Epic, Cerner (Oracle Health), Athenahealth, and Allscripts EHR systems for patient demographics, encounter notes, lab results, and medication lists.

**FR-022** The system SHALL support SMART on FHIR 2.0 for EHR-launched application contexts, enabling single sign-on from provider EHR portals into the telehealth platform without credential re-entry.

**FR-023** The system SHALL create a structured SOAP note template post-consultation with fields for chief complaint, history of present illness, review of systems, assessment, and plan, auto-populated with vitals from connected devices where available.

**FR-024** The system SHALL transmit completed encounter notes back to the source EHR within 5 minutes of provider signature, using the HL7 FHIR DocumentReference resource.

**FR-025** The system SHALL support CDA (Clinical Document Architecture) R2 import and export for interoperability with legacy systems not yet FHIR-compliant.

**FR-026** The system SHALL display a longitudinal patient timeline showing prior telehealth encounters, imported EHR encounters, lab trends, and medication changes in a single provider-facing view.

**FR-027** The system SHALL support patient-initiated health data import from Apple Health, Google Fit, and FHIR-enabled patient portals per ONC 21st Century Cures Act information blocking requirements (45 CFR Part 171).

**FR-028** The system SHALL validate all FHIR resources against the HL7 FHIR R4 specification before import, logging validation errors without silently discarding data.

**FR-029** The system SHALL support break-the-glass emergency access overrides for providers needing out-of-normal access to patient records, with immediate audit log entry and mandatory post-access justification.

**FR-030** The system SHALL maintain tenant-isolated FHIR resource repositories, ensuring that cross-tenant patient record access is impossible without an explicit federation grant approved via HITL workflow.

### Module 4: AI Symptom Checker

**FR-031** The system SHALL provide a conversational AI symptom triage interface that collects chief complaint, symptom duration, severity, and relevant medical history through a structured dialogue.

**FR-032** The system SHALL produce a triage output with urgency classification (Emergency/Urgent/Non-urgent/Self-care), provisional differential diagnosis (top 3 conditions by probability), and recommended care pathway (ER, urgent care, telehealth, self-care).

**FR-033** The system SHALL achieve ≥80% agreement with provider post-visit diagnosis across a validated test set of 10,000+ clinical scenarios before production deployment, with ongoing monitoring of accuracy metrics.

**FR-034** The system SHALL display FDA-required disclaimers that AI output is not a medical diagnosis and does not replace professional clinical judgment, on every triage result screen.

**FR-035** The system SHALL log all AI triage interactions as PHI-associated audit events, linking triage session ID to the subsequent consultation encounter if one is initiated.

**FR-036** The system SHALL support clinician review and override of AI triage classification with mandatory documentation of rationale, contributing to model accuracy audit trails.

**FR-037** The system SHALL flag high-risk triage results (chest pain, stroke symptoms per FAST criteria, suicidal ideation) with immediate provider escalation pathways and, for imminent danger indicators, prompt the patient with 911 guidance per platform policy.

**FR-038** The system SHALL support pediatric triage protocols adapted for age-specific normal ranges and presenting complaint patterns for patients under 18 years.

**FR-039** The system SHALL not use triage session data for model retraining without explicit patient consent documented in the tenant audit log, per applicable FDA AI/ML guidance (FDA Action Plan for AI/ML-Based SaMD, 2021).

**FR-040** The system SHALL expose triage accuracy analytics per tenant, showing agreement rate by specialty, chief complaint category, and demographic cohort, for quality assurance review.

### Module 5: Medical Billing

**FR-041** The system SHALL generate CMS-1500 (professional) claim forms and 837P electronic transactions compliant with ANSI X12 5010 standards for submission to Medicare, Medicaid, and commercial payers.

**FR-042** The system SHALL auto-assign CPT codes for telehealth encounters based on visit type, provider specialty, and consultation duration, using current AMA CPT code set including telehealth-specific codes (99441–99443, 99421–99423, G2012, G2010).

**FR-043** The system SHALL apply Place of Service (POS) code 02 (Telehealth Provided Other than in Patient's Home) or POS 10 (Telehealth Provided in Patient's Home) per CMS guidelines (MLN Matters SE1605), per patient location collected at session initiation.

**FR-044** The system SHALL support ICD-10-CM diagnosis coding with ICD-10 lookup integrated into the encounter note, auto-suggesting codes based on provider-entered assessment text.

**FR-045** The system SHALL enforce payer-specific telehealth billing rules per tenant payer configuration, including modifier usage (GT, 95, GQ) as required by specific payers.

**FR-046** The system SHALL support real-time eligibility verification (ANSI X12 270/271) at appointment booking to confirm active coverage, telehealth benefit availability, and applicable copay/deductible.

**FR-047** The system SHALL process ERA (Electronic Remittance Advice) files (ANSI X12 835) from payers, auto-posting payments to the tenant's billing ledger with reconciliation reporting.

**FR-048** The system SHALL support patient responsibility calculation and credit card capture at time of service via PCI DSS-compliant payment processing (Stripe or equivalent Level 1 PCI-DSS processor).

**FR-049** The system SHALL track and report denied claims with denial reason codes (CARC/RARC), supporting appeals workflow with one-click claim resubmission.

**FR-050** The system SHALL generate tenant-level billing reports including: gross charges, net collections, denial rate, days in AR, cost-per-visit by visit type, and payer mix — exportable as CSV and PDF.

### Module 6: Provider Licensing Enforcement

**FR-051** The system SHALL maintain a real-time provider license registry per tenant, storing NPI, license number, issuing state, license type, expiration date, and status for each licensed provider.

**FR-052** The system SHALL verify provider licenses against the National Practitioner Data Bank (NPDB) HIPDB integrated query service at credentialing and on a weekly automated basis.

**FR-053** The system SHALL verify DEA registration status via the DEA Registration Lookup API for any provider granted controlled substance prescribing privileges.

**FR-054** The system SHALL enforce geo-fencing at session initiation: if the patient's verified location state does not match any state in which the provider holds a valid, active license, the session SHALL be blocked with a reason code and provider notification.

**FR-055** The system SHALL support Interstate Medical Licensure Compact (IMLC) member state relationships, recognizing that a provider holding an IMLC Letter of Qualification (LOQ) may practice in all IMLC member states without individual state licenses.

**FR-056** The system SHALL support PSYPACT participation for psychologists, authorizing practice in PSYPACT member states for providers holding an Authority to Practice Interjurisdictional Telepsychology (APIT) or Temporary Authorization to Practice (TAP).

**FR-057** The system SHALL support the Nurse Licensure Compact (NLC) for RNs and LPNs, recognizing a multistate license issued by the provider's home state as valid for practice in all NLC compact states.

**FR-058** The system SHALL send automated license expiration alerts to the provider and their administrator at 90, 60, and 30 days before expiration, and daily from 14 days through expiration date.

**FR-059** The system SHALL automatically suspend a provider's ability to initiate new sessions if their license has expired in any state, pending renewal verification by an administrator.

**FR-060** The system SHALL maintain a full credentialing audit trail per provider: verification events, status changes, manual overrides, and administrator approvals, stored in the tenant's isolated audit log.

### Module 7: Multi-Tenant Infrastructure

**FR-061** The system SHALL implement schema-per-tenant data isolation in PostgreSQL, where each tenant's PHI data, audit logs, provider rosters, billing accounts, and configuration are stored in a dedicated named schema (e.g., `tenant_<uuid>.`).

**FR-062** The system SHALL identify tenants via the `X-SAGE-Tenant` HTTP header and subdomain routing (e.g., `acme.telehealth.platform`), with tenant resolution validated against the tenant registry at every request.

**FR-063** The system SHALL provision new tenants with: isolated DB schema, dedicated S3 prefix (`s3://platform-phi/<tenant-uuid>/`), tenant-specific KMS key for S3 and RDS encryption, and admin user account — all completed within 60 seconds of onboarding API call.

**FR-064** The system SHALL enforce row-level security (RLS) policies in PostgreSQL as a defense-in-depth measure, ensuring queries from one tenant's application context cannot return rows belonging to another tenant's schema even if application-layer isolation fails.

**FR-065** The system SHALL require explicit federation grants (approved via HITL workflow with dual admin sign-off) for any cross-tenant data access, such as a health system sharing referral data across its multiple clinic tenants.

**FR-066** The system SHALL support tenant-level configuration of: branding (logo, colors), active modules, payer configurations, AI symptom checker enable/disable, and data retention policies.

**FR-067** The system SHALL provide a tenant admin dashboard with real-time utilization metrics: active sessions, provider count, patient count, consultation volume (daily/weekly/monthly), and billing summary.

**FR-068** The system SHALL support tenant offboarding with full data export in FHIR R4 bulk export format, PHI destruction with audit trail, and KMS key revocation — completing within 24 hours of offboarding request.

**FR-069** The system SHALL implement rate limiting per tenant to prevent one tenant's workload from degrading service for others, using token bucket algorithm with configurable limits per tenant tier.

**FR-070** The system SHALL support horizontal scaling of tenant compute isolation via Kubernetes namespace-per-tenant for workloads requiring dedicated compute (e.g., AI inference for large tenants).

---

## Non-Functional Requirements

**NFR-001** The system SHALL achieve 99.9% uptime (≤8.77 hours/year downtime) measured as a 30-day rolling average, excluding scheduled maintenance windows not exceeding 4 hours/month communicated with 72-hour advance notice.

**NFR-002** The system SHALL encrypt all PHI at rest using AES-256 with AWS KMS-managed tenant-specific keys (per FR-063).

**NFR-003** The system SHALL encrypt all data in transit using TLS 1.3 minimum (TLS 1.2 acceptable for legacy EHR integration partners with documented risk acceptance), with certificate pinning for mobile clients.

**NFR-004** Video session latency SHALL not exceed 150ms end-to-end (one-way) under normal network conditions (≥5 Mbps symmetric bandwidth).

**NFR-005** API response time for non-video endpoints SHALL not exceed 200ms at p95 under normal load, 500ms at p99.

**NFR-006** The system SHALL comply with HIPAA Privacy Rule (45 CFR Parts 160 and 164 Subpart E) and Security Rule (45 CFR Part 164 Subparts A and C).

**NFR-007** The system SHALL comply with HITECH Act (Pub.L. 111-5, Title XIII) breach notification requirements, supporting 60-day notification to individuals and 72-hour HHS notification for breaches affecting ≥500 individuals in a state.

**NFR-008** The system SHALL achieve and maintain SOC 2 Type II certification (Security, Availability, Confidentiality trust service criteria) with annual audits.

**NFR-009** The system SHALL comply with ONC 21st Century Cures Act (Pub.L. 116-136) information blocking prohibitions (45 CFR Part 171).

**NFR-010** All PHI access SHALL be logged in the tenant audit log with: actor identity, action type, resource type, resource ID, timestamp (UTC), source IP, and session ID — logs immutable after write (append-only).

**NFR-011** The system SHALL support FIPS 140-2 Level 1 compliant cryptographic modules for all PHI encryption operations.

**NFR-012** The system SHALL implement role-based access control (RBAC) with least-privilege principle: Patient, Provider, Admin, Billing, AI System roles with defined permission matrices.

**NFR-013** The system SHALL enforce multi-factor authentication (MFA) for all Provider and Admin accounts using TOTP (RFC 6238) or hardware security keys (FIDO2/WebAuthn).

**NFR-014** The system SHALL support automated PHI de-identification per HIPAA Safe Harbor standard (45 CFR §164.514(b)(2)) and Expert Determination standard (45 CFR §164.514(b)(1)) for analytics workloads.

**NFR-015** The system SHALL maintain audit log retention for a minimum of 6 years per HIPAA record retention requirements, with tenant-specific retention policies up to 10 years.

**NFR-016** The system SHALL implement automated vulnerability scanning (SAST, DAST, dependency scanning) in CI/CD pipeline with no critical/high CVEs permitted in production deployments.

**NFR-017** The system SHALL support penetration testing by qualified third parties on an annual basis, with findings remediation tracked through documented risk management process.

**NFR-018** The system SHALL implement session timeout for provider and admin sessions at 15 minutes of inactivity, with re-authentication required, per CMS EHR incentive program security requirements.

**NFR-019** The system SHALL comply with ADA Section 508 accessibility standards for all patient-facing interfaces, including WCAG 2.1 Level AA compliance for web and mobile.

**NFR-020** The system SHALL support disaster recovery with RPO (Recovery Point Objective) ≤1 hour and RTO (Recovery Time Objective) ≤4 hours, with automated failover to secondary region for the video infrastructure.

**NFR-021** The system SHALL implement privacy-by-design: data minimization (collect only what is clinically necessary), purpose limitation (use data only for stated care purposes), and storage limitation (automated retention policy enforcement).

**NFR-022** Mobile clients (iOS, Android) SHALL comply with Apple App Store and Google Play healthcare app privacy policies and shall not transmit PHI to third-party analytics SDKs without explicit BAA coverage.

---

## Multi-Tenancy Data Isolation Requirements

**MT-001** Tenant data isolation SHALL be enforced at the database schema layer (PostgreSQL schema-per-tenant), not solely at the application layer, to prevent cross-tenant data leakage in the event of application bugs.

**MT-002** Each tenant's PHI schema SHALL be identified by a UUID-based schema name (`tenant_<uuid>`) to prevent enumeration attacks.

**MT-003** Tenant onboarding SHALL atomically provision: DB schema with RLS policies, S3 prefix, KMS key, IAM role with minimum necessary S3/KMS permissions, audit log table, and admin user record — or roll back entirely on any failure.

**MT-004** Cross-tenant federation (e.g., health system with multiple clinic tenants sharing a provider roster) SHALL require: (a) administrator request from both tenant admins, (b) HITL approval by platform compliance officer, (c) federated access grant with explicit resource scope and time limit stored in the federation grants table.

**MT-005** Tenant-specific KMS keys SHALL be rotated annually with zero-downtime re-encryption, auditable in the platform key management log.

**MT-006** The `X-SAGE-Tenant` header SHALL be validated against a signed tenant registry entry per request; forged or unknown tenant headers SHALL result in HTTP 403 with audit event.

**MT-007** Tenant offboarding SHALL include: export of all PHI as FHIR R4 bulk data, cryptographic deletion of S3 objects, schema DROP with WAL-confirmed deletion, KMS key scheduled deletion (AWS KMS 7-day mandatory waiting period), and post-deletion verification audit.

---

## Out of Scope

- In-person appointment scheduling and on-site clinic management
- Inpatient clinical documentation (ICU, surgical notes)
- FDA-regulated medical device software (SaMD/SiMD) — the AI symptom checker is clinical decision support, not a diagnostic device
- Pharmacy dispensing operations
- Insurance underwriting and actuarial modeling
- International (non-US) operations in v1.0 (GDPR, PIPEDA compliance is Phase 4+)
- Direct integration with specialty laboratory instruments (LIS/LIMS)
- On-premise deployment (cloud-native only in v1.0)

---

## RICE-Scored Feature Prioritization

| Feature | Reach (pts) | Impact (1-3) | Confidence (%) | Effort (weeks) | RICE Score |
|---------|------------|--------------|----------------|----------------|------------|
| Video Consultations (core WebRTC) | 10,000 | 3 | 90% | 8 | 3,375 |
| Provider Scheduling | 10,000 | 3 | 95% | 4 | 7,125 |
| HIPAA Audit Logging | 10,000 | 3 | 95% | 3 | 9,500 |
| Multi-Tenant Isolation | 10,000 | 3 | 90% | 6 | 4,500 |
| Provider License Enforcement | 8,000 | 3 | 85% | 5 | 4,080 |
| E-Prescriptions (non-controlled) | 7,000 | 3 | 90% | 6 | 3,150 |
| EHR Integration (Epic/Cerner FHIR) | 6,000 | 3 | 80% | 10 | 1,440 |
| Medical Billing (837P/CMS-1500) | 5,000 | 3 | 85% | 8 | 1,594 |
| AI Symptom Checker | 8,000 | 2 | 70% | 12 | 933 |
| EPCS Controlled Substances | 4,000 | 3 | 80% | 8 | 1,200 |
| Payer Eligibility Verification | 5,000 | 2 | 85% | 4 | 2,125 |
| Patient Mobile App (iOS/Android) | 9,000 | 3 | 85% | 12 | 1,913 |
| Group Video Sessions | 3,000 | 2 | 80% | 4 | 1,200 |
| Interpreter Integration | 2,000 | 2 | 90% | 3 | 1,200 |
| Analytics Dashboard (admin) | 4,000 | 2 | 90% | 5 | 1,440 |
| Tenant White-Label Branding | 3,000 | 1 | 95% | 2 | 1,425 |
| PSYPACT/NLC Compact Support | 2,000 | 3 | 90% | 3 | 1,800 |
| Cross-Tenant Federation | 500 | 3 | 70% | 5 | 210 |

---

## MoSCoW Prioritization

### Must Have (MVP — Months 1–4)
- WebRTC video consultations with waiting room
- Provider scheduling and calendar management
- HIPAA audit logging (append-only, per-tenant)
- Schema-per-tenant PostgreSQL isolation
- Provider license enforcement (geo-fence at session)
- NPDB license verification
- Patient registration and identity verification
- TLS 1.3 + AES-256 PHI encryption
- MFA for provider/admin accounts
- Basic encounter notes (structured SOAP)
- Non-controlled substance e-prescribing via Surescripts
- Payer eligibility verification (270/271)
- CMS-1500 claim generation
- 99.9% uptime SLA with monitoring

### Should Have (Phase 2 — Months 5–8)
- EPCS for controlled substances (DEA 21 CFR 1311)
- PDMP integration (controlled substance prescribing)
- FHIR R4 EHR integration (Epic, Cerner)
- AI symptom checker (non-diagnostic, decision support)
- 837P electronic claim submission + ERA processing
- Patient mobile app (iOS + Android)
- IMLC / PSYPACT / NLC compact enforcement
- Automated license expiration alerting
- Group video sessions (up to 5 participants)
- Drug interaction checking (FDB/Multum)

### Could Have (Phase 3 — Months 9–12)
- SMART on FHIR 2.0 EHR-launched context
- Full billing analytics (denial management, AR aging)
- AI triage model retraining pipeline (with consent)
- Interpreter integration (Language Line)
- Payer-specific billing rule engine
- Patient-generated health data import (Apple Health)
- Tenant white-label branding configurator
- Advanced AI care coordination recommendations

### Won't Have (v1.0 — Future Phases)
- International compliance (GDPR, PIPEDA)
- On-premise deployment
- Inpatient clinical documentation
- Specialty laboratory instrument integration
- Insurance underwriting
- SaMD classification AI features (requires 510(k) pathway)

---

## Success Metrics

| Metric | Definition | Target | Measurement Frequency |
|--------|-----------|--------|-----------------------|
| Patient 30-day Return Rate | % patients with ≥2 visits within 30 days of first | ≥70% | Weekly |
| Consultation Completion Rate | Completed sessions / Initiated sessions | ≥85% | Daily |
| Platform Uptime | (Total minutes - downtime minutes) / Total minutes | ≥99.9% | Real-time |
| E-Prescription Fill Rate | Prescriptions dispensed within 24h / Prescriptions sent | ≥90% | Daily |
| AI Triage Accuracy | AI triage agreement with provider post-visit diagnosis | ≥80% | Monthly |
| Time to First Consultation | Registration timestamp to first session start | ≤15 minutes (median) | Weekly |
| Licensing Violation Rate | Sessions initiated without valid provider license | 0% | Real-time |
| Claim Clean Rate | Claims accepted first-pass by payer / Claims submitted | ≥92% | Weekly |
| EHR Note Sync Rate | Notes successfully delivered to EHR / Notes signed | ≥99% | Daily |
| Audit Log Completeness | PHI access events with complete metadata / Total events | 100% | Continuous |
