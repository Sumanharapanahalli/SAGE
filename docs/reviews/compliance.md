# SAGE Feature Review — `compliance`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/compliance.py`  
**Frontend:** `Compliance.tsx`  
**Review time:** 74s

---

## Verdict
This feature is completely unusable today by a real operator because a severe structural mismatch between the frontend filter and the backend schema filters out 100% of the live checklist items, rendering the UI completely blank and the assessment action non-functional.

**Works:** no
**Score:** 2/10

## What Actually Works
* **Domain Metadata Loading:** The `compliance.domains` RPC successfully retrieves all registered regulatory domains (`medtech`, `automotive`, `railways`, `avionics`, `iot_ics`), returning their associated standards, authorities, and risk levels.
* **Backend Checklist Generation:** The `compliance.checklist` RPC successfully generates a list of 21 required compliance items for the `medtech` domain (such as `DOC-001` to `DOC-021`), as verified by the live RPC output.
* **Dropdown Selection Flow:** The `Compliance.tsx` component correctly populates the "Domain" and "Risk level" dropdowns using data from the domain query and resets selection states when domains are changed.

## System-Level Findings
1. **Zero Audit Trail Logging (Critical Severity):** SAGE's defining rule is *"Agents propose. Humans decide."* However, `compliance.py` implements `gap_assessment` as a pure, stateless query. The operator's completed tasks are posted to the backend, and the assessment is computed and returned to the UI, but **nothing is written to the audit trail (`audit.*`)**. There is no tamper-evident record of who performed the assessment, when it occurred, or what the checked compliance state was.
2. **Missing Risk Level Input Validation (High Severity):** While `compliance.py` uses `_require_domain` to validate domains, it does **not validate the `risk_level` parameter** against the domain's authorized list. For `medtech`, the valid levels are `CLASS_A`, `CLASS_B`, and `CLASS_C`. The live RPC output proves the backend accepted `"HIGH"` as a risk level without raising an error. This can lead to silent fallbacks, blank lists, or corrupted metrics in production.
3. **Initialization RPC Errors (Medium Severity):** On mount, `Compliance.tsx` invokes `useComplianceChecklist` before `domain` and `riskLevel` state variables are initialized. This fires an immediate RPC request to `compliance.checklist` with empty string parameters, triggering `RPC_INVALID_PARAMS` ("missing or invalid 'domain'") on every single page load and rendering a red error banner before the user can interact.
4. **Brittle Case-Sensitivity Validation (Medium Severity):** The backend validator `_require_domain` executes `domain.lower()` to check against valid domains, but returns the unmodified `domain` string. If downstream functions like `generate_compliance_checklist` or `assess_compliance_gap` require strictly lowercase domain keys, this will cause unhandled runtime exceptions.

## Usability Findings
1. **Completely Blank Checklist State (Critical Severity):** The backend returns 21 items of type `"evidence_artifact"`. However, `Compliance.tsx` filters items using `type === "required_task"`. Because `required_tasks` is `0`, the list is completely empty. The operator sees an empty box with no checklist items and cannot interact with the page.
2. **Regulatory Documents Hidden from Operator (High Severity):** The 21 items returned by the backend are actual compliance artifacts (e.g. Software Development Plan, SRS, Architecture Design). By filtering for tasks only, the UI completely hides these essential document deliverables from the compliance operator, making it impossible to audit document readiness.
3. **No Visual Completion Feedback (Low Severity):** Clicking "Assess conformance" fires a mutation, but there is no loading indicator on the button (aside from text changes) and no visual success state indicating that the assessment was processed.

## Top 3 Fixes (optimizer-ready)

1. **Fix Checklist Item Filtering and Display All Artifacts**
   * **Task:** Modify `Compliance.tsx` to display both `"required_task"` and `"evidence_artifact"` item types in the checklist. Update `requiredTaskItems` to include all items, map them to appropriate icons/checkboxes, and ensure that `taskIdToTaskType` correctly formats both `DOC-` and `TASK-` prefixes before submitting them to `assess_compliance_gap`.
   * **Acceptance Criteria:** Selecting "medtech" and "CLASS_A" displays all 21 evidence documents (like `DOC-001` Software Development Plan) in the UI list. Checking them off and clicking "Assess conformance" successfully passes their IDs in the `completed_tasks` list to the backend.

2. **Prevent Initial Load RPC Errors via Query Guarding**
   * **Task:** Guard the `useComplianceChecklist` hook in `Compliance.tsx` (or inside the hook definition in `useCompliance.ts`) to prevent executing the underlying RPC call if `domain` or `riskLevel` is an empty string.
   * **Acceptance Criteria:** On first load of the Compliance page, no RPC call is made to `compliance.checklist` with empty parameters, and no red error banner is rendered. The query only fires once the default domain/risk level has been set by the `useEffect` hook.

3. **Log All Gap Assessments to the Audit Trail**
   * **Task:** Update the `gap_assessment` function in `compliance.py` to import and call SAGE's audit logging module. Write a structured, tamper-evident log entry whenever an assessment is requested.
   * **Acceptance Criteria:** Triggering a gap assessment successfully creates an audit log entry containing the timestamp, active operator, target domain, risk level, the list of completed items, and the calculated compliance percentage.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    compliance.domains
  -> {"domains": [{"domain": "medtech", "standard": "IEC 62304:2015+A1 + ISO 14971:2019 + FDA 21 CFR 820", "description": "Medical device software \u2014 covers embedded firmware, cloud backend, mobile apps", "authority": "FDA (US), EMA/Notified Bodies (EU MDR), Health Canada, PMDA (Japan)", "risk_levels": ["CLASS_A", "CLASS_B", "CLASS_C"], "hil_required_for": ["CLASS_B", "CLASS_C"]}, {"domain": "automotive", "standard": "ISO 26262:2018 + ISO/SAE 21434:2021 + UN ECE WP.29 R155/R156", "description": "Road vehicle functional safety and cybersecurity \u2014 from ASIL A to ASIL D", "authority": "Type approval authorities (KBA Germany, NHTSA US, UNECE WP.29)", "risk_levels": ["QM", "ASIL_A", "ASIL_B", "ASIL_C", "ASIL_D"], "hil_required_for": ["ASIL_B", "ASIL_C", "ASIL_D"]}, {"domain": "railways", "standard": "EN 50128:2011+A2:2020 + EN 50129:2018 + EN 50126-1:2017", "description": "Railway signalling and control software \u2014 SIL 0 to SIL 4", "authority": "National Safety Authorities (NSAs), ERA (European Union Agency for Railways)", "risk_levels": ["SIL_0", "SIL_1", "SIL_2", "SIL_3", "SIL_4"], "hil_required_for": ["SIL_2", "SIL_3", "SIL_4"]}, {"domain": "avionics", "standard": "DO-178C:2011 + DO-254:2000 + ARP4754A:2010", "description": "Airborne software and hardware \u2014 from DAL E (no effect) to DAL A (catastrophic)", "authority": "FAA (US), EASA (EU), Transport Canada, CAAC (China)", "risk_levels": ["DAL_E", "DAL_D", "DAL_C", "DAL_B", "DAL_A"], "hil_required_for": ["DAL_C", "DAL_B", "DAL_A"]}, {"domain": "iot_ics", "standard": "IEC 62443-2-4:2015 + IEC 62443-3-3:2013 + ETSI EN 303 645:2020", "description": "Industrial control systems and consumer IoT cybersecurity \u2014 SL 1 to SL 4", "authority": "CISA (US), ENISA (EU), BSI (Germany), NCSC (UK)", "risk_levels": ["SL_1", "SL_2", "SL_3", "SL_4"], "hil_required_for": ["SL_3", "SL_4"]}]}

[LIVE OK]    compliance.checklist
  -> {"domain": "medtech", "risk_level": "HIGH", "standard": "IEC 62304:2015+A1 + ISO 14971:2019 + FDA 21 CFR 820", "description": "Medical device software \u2014 covers embedded firmware, cloud backend, mobile apps", "authority": "FDA (US), EMA/Notified Bodies (EU MDR), Health Canada, PMDA (Japan)", "hil_testing_required": false, "total_items": 21, "flags": 0, "required_tasks": 0, "artifacts": 21, "items": [{"id": "DOC-001", "type": "evidence_artifact", "level": "REQUIRED", "description": "Software Development Plan (IEC 62304 \u00a75.1)", "clause": "IEC 62304:2015+A1 + ISO 14971:2019 + FDA 21 CFR 820", "hil_required": false, "status": null, "evidence_ref": null, "notes": ""}, {"id": "DOC-002", "type": "evidence_artifact", "level": "REQUIRED", "description": "Software Requirements Specification (IEC 62304 \u00a75.2)", "clause": "IEC 62304:2015+A1 + ISO 14971:2019 + FDA 21 CFR 820", "hil_required": false, "status": null, "evidence_ref": null, "notes": ""}, {"id": "DOC-003", "type": "evidence_artifact", "level": "REQUIRED", "description": "Software Architecture Design (IEC 62304 \u00a75.3)", "clause": "IEC 62304:2015+A1 + ISO 14971:2019 + FDA 21 CFR 820", "hil_required": false, "status": null, "evidence_ref": null, "notes": ""}, {"id": "DOC-004", "type": "evidence_artifact", "level": "REQUIRED", "description": "Software Detailed Design (IEC 62304 \u00a75.4)", "clause": "IEC 62304:2015+A1 + ISO 14971:2019 + FDA 21 CFR 820", "hil_required": false, "status": null, "evidence_ref": null, "notes": ""}, {"id": "DOC-005", "type": "evidence_artifact", "level": "REQUIRED", "description": "Unit Test Protocol + Results (IEC 62304 \u00a75.5)", "clause": "IEC 62304:2015+A1 + ISO 14971:2019 + FDA 21 CFR 820", "hil_required": false, "status": null, "evidence_ref": null, "notes": ""}, {"id": "DOC-006", "type": "evidence_artifact", "level": "REQUIRED", "description": "Integration Test Protocol + Results (IEC 62304 \u00a75.6)", "clause": "IEC 62304:2015+A1 + ISO 14971:2019 + FDA 21 CFR 820", "hil_required": false, "status": null, "evidence_ref": null, "notes": ""}, {"id": "DOC-007", "type": "evidence_artifact", "level": "REQUIRED", "description": "System Test Protocol + Results (IEC 62304 \u00a75.7)", "clause": "IEC 62304:2015+A1 + ISO 14971:2019 + FDA 21 CFR 820", "hil_required": false, "status": null, "evidence_ref": null, "notes": ""}, {"id": "DOC-008", "type": "evidence_artifact", "level": "REQUIRED", "description": "Software Release (IEC 62304 \u00a75.8)", "clause": "IEC 62304:2015+A1 + ISO 14971:2019 + FDA 21 CFR 820", "hil_required": false, "status": null, "evidence_ref": null, "notes": ""}, {"id": "DOC-009", "type": "evidence_artifact", "level": "REQUIRED", "description": "Problem Resolution Record (IEC 62304 \u00a79)", "clause": "IEC 62304:2015+A1 + ISO 14971:2019 + FDA 21 CFR 820", "hil_required": false, "status": null, "evidence_ref": null, "notes": ""}, {"id": "DOC-010", "type": "evidence_artifact", "level": "REQUIRED", "description": "Risk Management Plan (IS  ...[TRUNCATED BY THE AUDIT HARNESS FOR LENGTH — the real RPC response was complete, valid JSON. Do NOT report this as a defect.]
```
