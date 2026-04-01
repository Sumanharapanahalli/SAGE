# DHF SECTION-BY-SECTION CONTENT GUIDE
## CardioGuard™ ICD — 21 CFR 820.30 Complete Coverage
### Document ID: DHF-ICD-000-000-SPC-003-A

---

## DOCUMENT CONTROL

| Field | Value |
|---|---|
| Document ID | DHF-ICD-000-000-SPC-003-A |
| Title | DHF Section-by-Section Content Guide |
| Revision | A |
| Status | APPROVED |
| Effective Date | 2026-03-27 |

---

## SECTION 1 — DESIGN AND DEVELOPMENT PLANNING (21 CFR 820.30(b))

### 1.1 Regulatory Requirement

> "Each manufacturer shall establish and maintain plans that describe or reference the design and development activities and define responsibility for implementation. The plans shall identify and describe the interfaces with different groups or activities that provide, or result in, input to the design and development process. The plans shall be reviewed, updated, and approved as design and development evolves."
> — 21 CFR 820.30(b)

### 1.2 Required Documents

| Document ID | Title | Content Description |
|---|---|---|
| DHF-ICD-001-001-PLN-001-A | Design and Development Plan | Comprehensive development plan covering phase gates, resource allocation, milestone schedule, team structure, and inter-disciplinary interfaces. Must reference all applicable design control procedures. Updated at each phase gate. |
| DHF-ICD-001-002-PLN-001-A | Phase Gate Review Procedure | Defines entry/exit criteria for each development phase. Documents who reviews, what artifacts are required, pass/fail criteria, and how exceptions are handled. References QSP-DES-001. |
| DHF-ICD-001-003-REC-001-A | Team Roles and Responsibilities Matrix | RACI matrix covering all design and development activities. Defines Responsible, Accountable, Consulted, and Informed parties for each task type. |
| DHF-ICD-001-004-LOG-001-A | Project Schedule and Milestone Log | Baseline Gantt chart showing all design activities, dependencies, critical path. Updated each quarter. Deviation from baseline requires documented justification. |
| DHF-ICD-001-005-PLN-001-A | Interface Control and Communication Procedure | Documents all organizational interfaces (software/hardware, clinical/engineering, regulatory/design, manufacturing/design). Defines escalation paths. |

### 1.3 Acceptance Criteria

- All plans are reviewed and approved prior to execution of the phase they govern.
- Plans are updated and re-approved before initiating the subsequent development phase.
- All organizational interfaces are identified and have a designated owner.
- Schedule deviations >10% require formal impact assessment documented in the project log.

### 1.4 Responsible Parties

| Activity | Responsible | Approver |
|---|---|---|
| Authoring Design and Development Plan | Program Manager | VP Engineering |
| Phase Gate Review | QA Manager | Executive Steering Committee |
| RACI Matrix Maintenance | Project Manager | Program Director |
| Interface Control | Systems Engineering Lead | VP Engineering |

### 1.5 Review / Approval Requirements

All Section 1 documents require: Author signature, Peer review by one independent engineer, QA Manager review, and VP Engineering approval. Phase Gate documents additionally require sign-off from Medical Director (clinical relevance).

---

## SECTION 2 — DESIGN INPUT (21 CFR 820.30(c))

### 2.1 Regulatory Requirement

> "Each manufacturer shall establish and maintain procedures to ensure that the design requirements relating to a device are appropriate and address the intended use of the device, including the needs of the user and patient. The procedures shall include a mechanism for addressing incomplete, ambiguous, or conflicting requirements."
> — 21 CFR 820.30(c)

### 2.2 Required Documents

| Document ID | Title | Content Description |
|---|---|---|
| DHF-ICD-002-001-REQ-001-B | Design Input Requirements Document (DIRD) | Master requirements document. All device-level requirements with unique IDs, rationale, acceptance criteria, and source (standard, user need, or regulatory requirement). Minimum 150 traceable requirements covering all design input categories listed in Section 2.3 below. |
| DHF-ICD-002-002-REQ-001-A | Software Requirements Specification (SRS) | Software-specific requirements per IEC 62304. Includes functional requirements, performance requirements, interface requirements, and safety-related software requirements (Class C designation). |
| DHF-ICD-002-003-REQ-001-A | Electrical Systems Requirements Specification | Electrical requirements including pacing output specifications, sensing amplifier requirements, HV circuit requirements, battery specifications, and connector specifications per IS-4 standard. |
| DHF-ICD-002-004-REQ-001-A | Mechanical Design Requirements | Mechanical requirements including housing dimensions, connector block dimensions, hermeticity requirements (He leak rate), corrosion resistance, and shock/vibration tolerance. |
| DHF-ICD-002-005-REQ-001-A | Biocompatibility Requirements Summary | Biocompatibility requirements derived from ISO 10993-1 biological evaluation for each material in patient contact. Includes duration of contact classification. |
| DHF-ICD-002-006-REC-001-A | Design Input Approval Review Record | Formal record of design input review meeting. Documents reviewers, open issues, and approval signatures. Must confirm all inputs are complete, unambiguous, and testable. |

### 2.3 ICD-Specific Requirements Categories

Each category must have traceable requirements in the DIRD:

| Category | Key Requirements | Applicable Standard |
|---|---|---|
| Functional — Pacing | Bradycardia backup pacing (VVI/DDD), programmable rates 30–200 ppm, pulse width 0.06–2.0 ms, programmable amplitude 0.1–7.5 V | IEC 60601-2-31 |
| Functional — Defibrillation | Capacitor charge time ≤15 s, maximum shock energy ≥35 J, programmable therapy zones (VT, FVT, VF), ATP capability | ANSI/AAMI DF-2 |
| Functional — Sensing | Ventricular sensitivity programmable 0.15–12 mV, automatic gain control, far-field rejection, T-wave oversensing prevention | — |
| Performance — Detection | VF detection sensitivity ≥99%, VT detection specificity ≥95% in clinical simulation, detection time <2.5 s for VF NID 18/24 | Clinical evidence |
| Safety — Patient | No inappropriate shock from oversensing, defibrillation protection circuit, lead impedance monitoring with alert | ISO 14971 |
| Safety — EMI | Functional in 3 V/m E-field per IEC 60601-1-2 Table 4; reversion to asynchronous mode at higher fields; recovery within 10 s | IEC 60601-1-2 |
| Biocompatibility | All patient-contacting materials: ISO 10993-1 cytotoxicity, sensitization, pyrogenicity, implantation; titanium housing | ISO 10993-1 |
| Electrical Safety | Leakage current ≤10 µA (NC), dielectric strength test per IEC 60601-1 | IEC 60601-1 |
| Software | IEC 62304 Class C; SOUP list; software unit testing >85% branch coverage | IEC 62304 |
| Sterilization | SAL 10⁻⁶ via EO sterilization; sterility maintained through 24-month shelf life | ISO 11135 |
| Packaging | Maintains sterile barrier through distribution; ASTM D4169 Climate Category II | ASTM F2097 |
| Labeling | Complies with 21 CFR 801; includes: model number, serial number, lot, sterility symbol (ISO 7000-1051), MR conditional label | 21 CFR 801 |
| Regulatory Compliance | CE Mark, Health Canada, TGA (Australia) requirements documented as additional inputs | EU MDR 2017/745 |

### 2.4 Requirements Traceability Instructions

All requirements in the DIRD must be traced bidirectionally using the Requirements Traceability Matrix (RTM):
- Forward trace: Requirement ID → Design Output (drawing/specification) → Verification/Validation activity
- Backward trace: Test result → Test ID → Requirement ID

The RTM is maintained in the Jama Connect requirements management tool. A static export is included in this DHF section as DHF-ICD-002-001-REQ-001-B-ATT-01 (RTM Export).

### 2.5 Acceptance Criteria

- All requirements have unique IDs (format: REQ-[CAT]-[NNN])
- All requirements are verifiable (measurable acceptance criteria exist)
- No conflicting requirements exist without documented resolution
- Design Input Review Record signed by QA Manager and Medical Director

---

## SECTION 3 — DESIGN OUTPUT (21 CFR 820.30(d))

### 3.1 Regulatory Requirement

> "Each manufacturer shall establish and maintain procedures for defining and documenting design output in terms that allow an adequate evaluation of conformance to design input requirements. Design output procedures shall contain or make reference to acceptance criteria and shall ensure that those design outputs that are essential for the proper functioning of the device are identified."
> — 21 CFR 820.30(d)

### 3.2 Required Documents

| Document ID | Title | Content Description |
|---|---|---|
| DHF-ICD-003-001-SPC-001-C | Device Master Record (DMR) Index | Top-level index of all DMR documents including all drawings, BOMs, SOPs, and acceptance criteria. Must reference DHF for design evidence. |
| DHF-ICD-003-002-DWG-001-C | Assembly Drawing Package | Engineering drawings (GD&T per ASME Y14.5): can assembly, header block, connector block, lead connector. Includes critical dimensions for hermeticity, feedthrough, and connector alignment. |
| DHF-ICD-003-003-SPC-001-B | Component Specifications Package | Individual component specifications including titanium can material spec, feedthrough specification (titanium nitride coating), capacitor spec (WE series), and battery spec (SL-840 lithium/carbon monofluoride). |
| DHF-ICD-003-004-SPC-001-B | Software Architecture Document | Top-level software architecture per IEC 62304. Includes SOUP list, software unit decomposition, detection algorithm description, therapy state machine, and communication protocol with programmer. |
| DHF-ICD-003-005-LBL-001-B | Device Labeling Package | All labeling per 21 CFR 801 and ISO 15223-1: device label (can), header label, programmer screen displays, IFU (Instructions for Use), patient ID card, and shipping label. |
| DHF-ICD-003-006-SPC-001-A | Sterile Barrier System Specification | Specification for sterile packaging: Tyvek/foil pouch dimensions, seal width specifications, peel force requirements, and pouch-within-box configuration. |

### 3.3 Responsible Parties

| Output Type | Responsible | Approver |
|---|---|---|
| Mechanical Drawings | Sr. Mechanical Engineer | Chief Engineer |
| Software Architecture | Sr. Software Engineer | Software Manager + QA |
| Labeling | Regulatory Affairs Specialist | VP Regulatory Affairs |
| Component Specifications | Systems Engineer | Engineering Manager |

---

## SECTION 4 — DESIGN REVIEW (21 CFR 820.30(e))

### 4.1 Regulatory Requirement

> "Each manufacturer shall establish and maintain procedures to ensure that formal documented reviews of the design results are planned and conducted at appropriate stages of the device's design development... The results of a design review, including identification of the design, the date, and the individual(s) performing the review, shall be documented in the DHF."
> — 21 CFR 820.30(e)

### 4.2 Design Review Schedule

| Review # | Phase | Key Agenda Items | Required Attendees |
|---|---|---|---|
| DR-1 | End of Concept Phase | User needs confirmed, preliminary requirements, market analysis, regulatory strategy | Program Manager, Medical Director, Marketing, Regulatory, QA |
| DR-2 | End of Feasibility Phase | Feasibility study results, design concept selection, updated risk assessment, V&V strategy | All of DR-1 + Systems Eng., Software Lead, Hardware Lead |
| DR-3 | End of Design Phase | Design freeze, drawing package review, requirements coverage, risk control integration | Full cross-functional team, independent reviewer |
| DR-4 | End of Verification Phase | All verification protocols executed, open actions addressed, residual risks acceptable | QA Director, VP Eng., Medical Director, Regulatory, Manufacturing |
| DR-5 | End of Validation Phase | Clinical data review, human factors results, benefit-risk assessment, labeling sign-off | All of DR-4 + Clinical Affairs, independent statistician |
| DR-6 | Transfer Readiness | DMR completeness, manufacturing process validation, post-market plan | Executive team, QA Director, Manufacturing Director |

### 4.3 Required Documents Per Review

Each design review produces: (1) Meeting minutes (DHF-ICD-004-00N-REC-001-A), (2) Attendee sign-in sheet, (3) Open issues log with owners and due dates, (4) Phase gate checklist with pass/fail determination.

---

## SECTION 5 — DESIGN VERIFICATION (21 CFR 820.30(f))

### 5.1 Regulatory Requirement

> "Each manufacturer shall establish and maintain procedures for verifying the device design. Design verification shall confirm that the design output meets the design input requirements."
> — 21 CFR 820.30(f)

### 5.2 Required Documents (Summary)

Full detail: see `docs/DHF/DHF-ICD-SECTION-005-006-VERVAL.md`

| Document ID | Title |
|---|---|
| DHF-ICD-005-001-PLN-001-A | V&V Master Plan |
| DHF-ICD-005-002-PRT/RPT | Electrical Characterization |
| DHF-ICD-005-004-PRT/RPT | Defibrillation Waveform |
| DHF-ICD-005-006-PRT/RPT | EMI/EMC (IEC 60601-1-2) |
| DHF-ICD-005-008-PRT/RPT | Mechanical Integrity |
| DHF-ICD-005-010-PRT/RPT | Software Verification (IEC 62304) |
| DHF-ICD-005-012-PRT/RPT | Battery/Longevity |

---

## SECTION 6 — DESIGN VALIDATION (21 CFR 820.30(g))

### 6.1 Regulatory Requirement

> "Each manufacturer shall establish and maintain procedures for validating the device design. Design validation shall be performed under defined operating conditions on initial production units, lots, or their equivalents. Design validation shall ensure that devices conform to defined user needs and intended uses..."
> — 21 CFR 820.30(g)

### 6.2 Required Documents (Summary)

Full detail: see `docs/DHF/DHF-ICD-SECTION-005-006-VERVAL.md`

Key requirement: Validation must be performed on **initial production units** (not prototypes), under **actual or simulated use conditions**. Clinical investigation results (from IDE-approved study) constitute the primary clinical validation evidence.

---

## SECTION 7 — DESIGN TRANSFER (21 CFR 820.30(h))

### 7.1 Regulatory Requirement

> "Each manufacturer shall establish and maintain procedures to ensure that the device design is correctly translated into production specifications."
> — 21 CFR 820.30(h)

### 7.2 Required Documents

| Document ID | Title | Content Description |
|---|---|---|
| DHF-ICD-007-001-PLN-001-A | Design Transfer Plan | Procedure for translating design outputs into the Device Master Record. Defines responsibilities, checklist items, and acceptance criteria for transfer readiness. |
| DHF-ICD-007-002-REC-001-A | DMR Approval Record | Formal sign-off that the Device Master Record is complete, approved, and sufficient to produce the device consistently. |
| DHF-ICD-007-003-REC-001-A | First Article Inspection Report | Dimensional and functional inspection of the first production unit against all drawing specifications. 100% inspection at initial production run. |
| DHF-ICD-007-004-REC-001-A | Manufacturing Process Validation Summary | Summary of IQ/OQ/PQ for critical manufacturing processes: hermetic welding, EO sterilization, final test equipment calibration. |
| DHF-ICD-007-005-SOP-001-A | Design Transfer Checklist and Sign-Off | Line-by-line checklist confirming each design output has been incorporated into the DMR, personnel are trained, and quality controls are in place. |

### 7.3 Acceptance Criteria

- DMR contains all documents needed to produce, inspect, and test the device.
- First Article Inspection Report shows 100% conformance to drawings.
- All critical manufacturing processes have validated procedures (IQ/OQ/PQ complete).
- Manufacturing personnel training records are current.

---

## SECTION 8 — DESIGN CHANGES (21 CFR 820.30(i))

### 8.1 Regulatory Requirement

> "Each manufacturer shall establish and maintain procedures for the identification, documentation, validation or where appropriate verification, review, and approval of design changes before their implementation."
> — 21 CFR 820.30(i)

### 8.2 Required Documents

| Document ID | Title | Content Description |
|---|---|---|
| DHF-ICD-008-001-SOP-001-A | Design Change Control Procedure | Procedure for initiating, evaluating, verifying/validating, approving, and implementing design changes. Includes significance assessment (does change require new PMA or 30-day PMA Supplement?). |
| DHF-ICD-008-002-LOG-001-A | Engineering Change Order (ECO) Register | Running log of all ECOs with: ECO number, description, affected documents, significance assessment, approval date. |
| DHF-ICD-008-003-REC-001-A | Design Change Impact Assessments | For each significant change: documents rationale, risk impact analysis, V&V activities performed, and regulatory pathway (e.g., 30-day PMA Supplement per 21 CFR 814.39). |

---

## SECTION 9 — RISK MANAGEMENT (ISO 14971:2019)

See `docs/DHF/DHF-ICD-RISK-MANAGEMENT-INDEX.md` for full detail.

### 9.1 Regulatory and Standards Basis

- **ISO 14971:2019** — Primary risk management standard
- **21 CFR 820.30** — Design controls implicitly require risk management throughout
- **FDA Guidance: Factors to Consider When Making Benefit-Risk Determinations in Medical Device Premarket Approval** (2019)
- **IEC 80001-1** — Application of risk management for IT networks incorporating medical devices

---

## SECTION 10 — SUPPORTING DOCUMENTATION (21 CFR 820.30(j))

### 10.1 Regulatory Requirement

> "Each manufacturer shall establish and maintain a DHF for each type of device. The DHF shall contain or reference the records necessary to demonstrate that the design was developed in accordance with the approved design plan and the requirements of this part."
> — 21 CFR 820.30(j)

### 10.2 Required Documents

| Document ID | Title | Content Description |
|---|---|---|
| DHF-ICD-010-001-CER-001-A | Biocompatibility Assessment (ISO 10993-1) | Complete biological evaluation per ISO 10993-1:2018 Table 1 for all patient-contacting materials. Includes test reports for cytotoxicity, sensitization, genotoxicity, implantation (90-day), and pyrogenicity. Summary matrix of material × test × result. |
| DHF-ICD-010-002-CER-001-A | IEC 60601-1 Electrical Safety Certificate | CB Scheme test report and certificate from accredited NRTL confirming compliance with IEC 60601-1:2005+A1:2012. Includes national deviations for US (UL 60601-1) and EU (EN 60601-1). |
| DHF-ICD-010-003-CER-001-A | IEC 62304 Software Safety Classification Record | Documented justification for software safety classification (Class C — software failure can cause death or serious injury). Includes SOUP list and SOUP risk analysis. |
| DHF-ICD-010-004-CER-001-A | Third-Party Audit Certificate (ISO 13485) | Current ISO 13485:2016 QMS certification from accredited registrar. Scope must include design, development, and manufacture of active implantable cardiovascular devices. |
| DHF-ICD-010-005-RPT-001-A | Predicate Device and State-of-Art Review | Literature review supporting intended use, clinical rationale, and comparison to predicate devices (Abbott Ellipse, Medtronic Evita). Documents state-of-art for detection and therapy. |
| DHF-ICD-010-006-SPC-001-A | Regulatory Standards Compliance Checklist | Line-by-line checklist against each applicable standard listed in the Master Index, Section 6. Documents objective evidence for each compliance claim. |

### 10.3 Cybersecurity Documentation (Per FDA 2023 Guidance)

| Document ID | Title |
|---|---|
| DHF-ICD-010-007-PLN-001-A | Cybersecurity Risk Management Plan |
| DHF-ICD-010-008-RPT-001-A | Threat Modeling Report (STRIDE methodology) |
| DHF-ICD-010-009-SPC-001-A | Software Bill of Materials (SBOM) |
| DHF-ICD-010-010-PLN-001-A | Coordinated Vulnerability Disclosure Policy |

Per FDA's 2023 cybersecurity guidance, the ICD's wireless programmer interface (Bluetooth LE, 2.4 GHz) requires documented security controls. The CG-7000 employs AES-128 encryption, device authentication, and a rolling session key for all programmer-to-device communication. Full cybersecurity documentation is maintained as part of the DHF Section 10 supporting file.
