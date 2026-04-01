# SAGE FallGuard Wearable — Clinical Administrator Training
**Document ID:** TRN-ADM-001 v1.0
**Device:** SAGE FallGuard Wearable v1.0
**Applicable Standards:** ISO 13485:2016 §4.2, 21 CFR Part 803 (MDR), 21 CFR Part 820 (QSR)
**Classification:** Clinical Training Material — Controlled Document
**Estimated Training Time:** 60 minutes
**Prerequisites:** Basic IT systems familiarity; familiarity with FDA regulatory framework

> **⚠️ CLINICAL SPECIALIST REVIEW REQUIRED**
> This document must be reviewed and approved by a qualified clinical specialist or regulatory affairs professional before distribution. Review status: **PENDING — [Reviewer Name / Date]**

---

## Module Overview

This module certifies clinical administrators to:
1. Manage and monitor the FallGuard device fleet across a care facility
2. Administer user accounts, roles, and training completion records
3. Generate and submit FDA Medical Device Reports (MDR) for serious adverse events
4. Produce regulatory-compliant incident summaries and maintenance records
5. Configure facility-wide alert routing and escalation rules

**Upon successful completion** (competency quiz score ≥80%), your training record is updated in the Care Dashboard and an administrator certification is issued.

---

## Learning Objectives

- **LO-1:** Navigate all sections of the Fleet Management Dashboard
- **LO-2:** Add, remove, and reassign devices to patients
- **LO-3:** Generate and export regulatory incident reports
- **LO-4:** Submit an FDA MDR (21 CFR Part 803) for a serious injury event within the mandatory 30-day window
- **LO-5:** Configure facility-wide alert routing rules and escalation contacts
- **LO-6:** Monitor training completion per user and issue compliance reports

---

## Section 1: Fleet Management Dashboard (Minutes 0–20)

### 1.1 Dashboard Overview

The Fleet Management Dashboard is accessed at: **Care Dashboard → Admin → Fleet Management**

The dashboard is organized into five panels:

| Panel | Purpose |
|---|---|
| **Device Inventory** | All devices registered to this facility — status, battery, last seen |
| **Patient Assignments** | Which device is paired to which patient |
| **Alert History** | All alerts from the past 30 days with response timestamps |
| **Maintenance Queue** | Devices requiring cleaning, calibration, or repair |
| **Training Registry** | Per-user training completion and certification status |

### 1.2 Device Inventory Management

**Viewing device status:**

Navigate to **Fleet Management → Devices**. Each device row shows:
- Device ID (6-digit alphanumeric)
- Patient assignment (or "Unassigned")
- Connection status: `Connected` / `Offline` / `Charging` / `Decommissioned`
- Battery percentage and estimated hours remaining
- Firmware version (flag devices on versions older than the current release)
- Last calibration date

**Adding a new device to the facility inventory:**

1. Unbox the device and locate the Device ID on the back label
2. Navigate to **Fleet → Add Device**
3. Enter the Device ID and scan the QR code on the packaging
4. Select the device location (ward, room, or "Supply Cabinet")
5. Run the initial self-test: **Fleet → Devices → [Device ID] → Run Diagnostics**
6. Confirm all diagnostics pass (green checkmarks) before assigning to a patient

**Decommissioning a device:**

1. Navigate to **Fleet → Devices → [Device ID] → Decommission**
2. Select a reason: `End of Life` / `Irreparable Fault` / `Patient Discharge`
3. Confirm the device is removed from the patient's assignment
4. Export the device history log (required for regulatory file) before decommissioning
5. Follow your facility's medical device disposal procedure for the physical unit

### 1.3 Patient Assignment Management

**Assigning a device to a patient:**
- Navigate to **Fleet → Patient Assignments → Assign**
- Select patient from the EMR-linked patient list
- Select an available (unassigned, connected) device
- Confirm alert recipients (minimum 2 caregivers required)
- Save — caregiver app notifications are activated immediately

**Discharging a patient:**
1. Navigate to **Fleet → Patient Assignments → [Patient Name] → Discharge**
2. Confirm the device is physically retrieved from the patient
3. The device status reverts to "Unassigned" in inventory
4. Patient alert history is archived (accessible for 7 years per 21 CFR Part 820.180)

### 1.4 Fleet Alert Routing Configuration

**Global escalation chain** (applied facility-wide unless overridden per patient):

Navigate to **Admin → Alert Routing → Escalation Chain**:
- **Tier 1 — Immediate Response (0–3 min):** Assigned caregiver(s)
- **Tier 2 — Supervisor Notification (3–5 min, if no acknowledgement):** Charge nurse on duty
- **Tier 3 — Emergency Escalation (5 min, unacknowledged high-confidence alert):** Auto-page on-call physician; consider auto-dial 911 (requires administrative approval to activate)

**Configuring quiet hours:**
- Navigate to **Admin → Alert Routing → Facility Schedule**
- Set overnight quiet hours (e.g., 22:00–06:00)
- During quiet hours: low-confidence alerts (<40%) are suppressed; medium and high confidence alerts are always active
- Quiet hours apply **only** to non-urgent notifications, never to confirmed fall alerts

### 1.5 Maintenance Queue Management

Devices enter the maintenance queue automatically when:
- Battery cycles exceed 300 (≈1 year of daily use)
- Calibration was not performed in the past 30 days
- Diagnostics fail any check
- A post-fall inspection is required (any device involved in a serious injury event)

**Processing a maintenance item:**
1. Open **Fleet → Maintenance Queue**
2. Select the maintenance ticket
3. Assign to a trained biomedical technician or designated staff member
4. Record the maintenance action performed (cleaned / calibrated / repaired / replaced)
5. Close the ticket — device status returns to "Available"

---

## Section 2: FDA Medical Device Reporting (MDR) — 21 CFR Part 803 (Minutes 20–42)

> **Regulatory Requirement:** This section covers a mandatory U.S. federal reporting obligation. Non-compliance may result in enforcement action by the FDA. When in doubt, consult your facility's regulatory affairs officer or legal counsel before submitting or withholding a report.

### 2.1 What Triggers an MDR?

Under 21 CFR Part 803, your facility (as a device user facility) must submit a **MedWatch 3500A report** to the FDA when a medical device is suspected to have caused or contributed to:

| Trigger Condition | MDR Required | Deadline |
|---|---|---|
| Patient death | Yes — must also notify manufacturer | 10 calendar days |
| Serious injury (requires hospitalization, surgery, permanent impairment) | Yes | 30 calendar days |
| Malfunction that would cause serious injury if it recurred | Manufacturer notification required | 30 calendar days |
| Minor injury with no serious outcome | No MDR required | Document in internal incident log |
| False positive alert, no injury | No MDR required | Document in incident log |

**FallGuard-specific triggers to watch for:**
- Device failed to detect a fall that resulted in serious injury (missed alert)
- Device reported a fall alert and patient rushed to respond, causing a caregiver injury
- Device battery failure caused monitoring gap; patient fell during the gap
- Sensor gave erroneous vital sign data that affected clinical decision-making

### 2.2 The FDA MDR Submission Process — Step by Step

**Step 1 — Identify the Event (within 24 hours of becoming aware)**

When a caregiver escalates a "Serious Injury — EMS Activated" incident report:
1. Open the incident in **Fleet → Alert History → [Incident ID]**
2. Review the alert timestamp, confidence score, caregiver response time, and outcome
3. Determine: Was the FallGuard device involved in the causation or failure to prevent the injury?
4. If yes or reasonably suspected: proceed with MDR. *When uncertain, err toward reporting.*

**Step 2 — Notify the Manufacturer (within 24 hours for death; as soon as practicable for serious injury)**

Contact SAGE Medical Devices (device manufacturer):
- **MDR Hotline:** Listed in your device registration documentation
- **Email:** mdr-reporting@[manufacturer-domain].com
- Provide: Event date, Device ID, Patient ID (anonymized per HIPAA — use facility patient number), description of the event, and the injury outcome
- Request and retain the manufacturer's **Device Complaint Number**

**Step 3 — Gather Documentation**

Collect and retain the following (do NOT alter original records):
- [ ] FallGuard incident report (exported from dashboard as PDF)
- [ ] Alert log extract for the 24 hours surrounding the event
- [ ] Device diagnostic report (downloaded from Fleet → Device → Export Diagnostics)
- [ ] Caregiver shift notes and handoff records
- [ ] Medical records excerpt (injury assessment, treatment provided)
- [ ] Device serial number, firmware version, last calibration date
- [ ] Photographs of device condition if relevant (post-event inspection)

**Step 4 — Complete MedWatch Form 3500A**

Access the form at: **FDA MedWatch Online (FDA.gov/Safety/MedWatch)** — or use your facility's pre-loaded form in the EMR regulatory module.

Key fields for FallGuard events:

| Form Section | FallGuard-Specific Guidance |
|---|---|
| A. Patient Information | Use facility patient number — do NOT include name or DOB on FDA form |
| B. Adverse Event or Product Problem | Check "Adverse Event" if injury occurred; "Product Problem" if device malfunctioned without injury |
| C. Suspect Medical Device | Device name: "SAGE FallGuard Wearable v1.0"; Manufacturer: SAGE Medical Devices; Include device serial number and firmware version |
| D. Suspect Concomitant Products | List any other monitoring devices in use |
| E. Event Narrative | Describe the sequence of events clearly, including what the device did or failed to do, and the patient outcome |
| F. Reporter | Enter your name, facility name, and contact information |

**Step 5 — Submit and Retain**

- Submit the form electronically via FDA MedWatch Online
- Print or save the submission confirmation with the FDA tracking number
- File in your facility's **MDR Log** (required under 21 CFR 803.18)
- Retain all supporting documentation for a minimum of **2 years** from the submission date

**Step 6 — Follow-Up Report (if applicable)**

If new information becomes available after the initial report (e.g., patient's condition worsens, root cause identified), submit a follow-up MedWatch 3500A within **30 days of the new information**, referencing the original FDA tracking number.

### 2.3 Internal MDR Log

The Care Dashboard maintains an internal MDR log: **Admin → Regulatory → MDR Log**

For each reportable event:
- Event date and incident ID
- MDR decision (Reportable / Not Reportable + rationale)
- Submission date and FDA tracking number
- Manufacturer complaint number
- Document retention checklist status

**Annual MDR Summary Report:**
Under 21 CFR Part 803.33, user facilities must submit an **Annual Report** to the FDA (Form 3419) by January 1 each year. The dashboard generates a draft annual summary at **Admin → Regulatory → Annual MDR Summary → Export**. Review and submit to FDA by December 31 each year.

### 2.4 Common MDR Errors to Avoid

| Error | Consequence |
|---|---|
| Submitting beyond the deadline | FDA warning letter; potential civil money penalty |
| Including patient name on FDA form | HIPAA violation |
| Failing to notify manufacturer within 24 hours of death | 21 CFR 803.30 violation |
| Altering device logs post-event | Obstruction of regulatory investigation |
| Failing to maintain MDR log | 21 CFR 803.18 non-compliance |

---

## Section 3: Regulatory Reporting Schedule (Minutes 42–52)

### 3.1 Recurring Reporting Obligations

| Report | Frequency | Deadline | Dashboard Location |
|---|---|---|---|
| Internal Incident Log Review | Monthly | Last business day of month | Regulatory → Incident Summary |
| MDR Annual Report (FDA Form 3419) | Annual | January 1 | Regulatory → Annual MDR Summary |
| Device Maintenance Log | Quarterly | End of quarter | Fleet → Maintenance → Export |
| Training Compliance Report | Monthly | 5th of following month | Training Registry → Export |
| ISO 13485 Internal Audit | Annual | Per quality plan | Admin → Audit Records |

### 3.2 Generating Regulatory Reports from the Dashboard

**Incident Summary Report:**
1. Navigate to **Admin → Regulatory → Incident Summary**
2. Set the date range
3. Select report type: `All Incidents` / `Reportable Events Only` / `MDR Filed`
4. Click **Export PDF** or **Export CSV**
5. Sign and date the report as the responsible administrator

**Training Compliance Report:**
1. Navigate to **Admin → Training Registry → Compliance Report**
2. Select the reporting period
3. The report shows: staff member name, role, modules completed, quiz scores, certification status, and expiry date
4. Export and file per your facility's quality records procedure

**Device Maintenance Summary:**
1. Navigate to **Fleet → Maintenance → Summary Report**
2. Confirm all maintenance tickets in the period are closed
3. Export for inclusion in the ISO 13485 Device Master Record

### 3.3 HIPAA Considerations in Regulatory Reporting

When preparing any report that may leave the facility:
- **De-identify patient data** before sending to FDA, manufacturers, or external auditors
- Use facility patient numbers (not names, DOB, SSN, or MRN) in all external reports
- Internal reports may retain identifiable information but must be stored in access-controlled systems
- Retain all regulatory correspondence (including FDA acknowledgements) in the quality management system for the required retention period

---

## Section 4: Training Administration (Minutes 52–58)

### 4.1 Managing Staff Training Records

Navigate to **Admin → Training Registry**:

- View all staff members and their training completion status per module
- Filter by: Role / Department / Training Status / Certification Expiry
- Override a training record (e.g., equivalency recognition) — requires administrator justification note
- Manually enroll staff in specific training modules
- View quiz attempt history and scores

### 4.2 Certification Expiry Management

FallGuard training certifications expire:
- Caregiver certification: **12 months** from completion
- Administrator certification: **12 months** from completion

The dashboard sends automatic reminders at 60, 30, and 7 days before expiry. Administrators receive a weekly report of any certifications expiring within 30 days.

**Staff with expired certifications should not be assigned as primary alert recipients** until recertification is complete. The dashboard flags this condition automatically.

### 4.3 Onboarding New Staff

When a new staff member joins:
1. Create their account in **Admin → Users → Add User**
2. Assign their role: `Caregiver` / `Charge Nurse` / `Administrator`
3. Enroll in required training modules (role-based pre-selection is automatic)
4. Set a training completion deadline (recommended: within 5 business days of start date)
5. Staff cannot be added as active alert recipients until module completion and quiz certification are confirmed

---

## Section 5: Competency Check Reminders

Before taking the quiz, confirm you can answer:
- What are the 3 MDR trigger conditions and their deadlines?
- Which FDA form is used for user facility MDR submissions?
- What information must NOT appear on the FDA MDR form?
- How many years must MDR documentation be retained?
- What is the annual MDR reporting deadline under 21 CFR Part 803.33?

**Proceed to the Competency Assessment Quiz** (TRN-QUIZ-001, Administrator track) in the Care Dashboard → Training → My Assessments. You must score **≥80% to receive certification.**

---

## Document Control

| Field | Value |
|---|---|
| Author | SAGE OpenDoc Agent (AI-assisted draft) |
| Regulatory Reviewer | [Regulatory Affairs Professional — SIGNATURE PENDING] |
| Clinical Reviewer | [Clinical Specialist — SIGNATURE PENDING] |
| Version | 1.0 |
| Effective Date | Pending reviewer sign-off |
| Review Cycle | Annual or upon regulatory guidance change |
| Next Review Due | 2027-03-27 |
| Related Documents | TRN-CG-001, TRN-ONB-001, TRN-QUIZ-001 |
| Regulatory References | 21 CFR Part 803, 21 CFR Part 820, ISO 13485:2016, FDA MedWatch Form 3500A, FDA Form 3419 |
