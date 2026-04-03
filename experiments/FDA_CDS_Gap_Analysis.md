# SAGE Framework vs FDA Clinical Decision Support Software Guidance (2026)
## Deep Compliance Gap Analysis

**FDA Document:** Clinical Decision Support Software — Guidance for Industry and FDA Staff (January 6, 2026)  
**Reference:** [fda.gov/media/109618/download](https://www.fda.gov/media/109618/download)  
**Analysis Date:** 2026-04-03

---

## Executive Summary

The FDA CDS guidance (2026) defines a **four-criterion test** to determine whether clinical decision support software is regulated as a medical device or exempt as "Non-Device CDS." This analysis maps every requirement in the guidance against SAGE Framework's current capabilities, identifying what is covered, partially covered, and missing.

**Overall Score: 68% — Strong foundation, critical gaps in CDS-specific areas**

| Category | Coverage | Score |
|----------|----------|-------|
| Design Controls & Traceability (Criterion 1) | Strong | 90% |
| Labeling & Intended Use (Criterion 2) | Partial | 55% |
| HCP Decision Support & Transparency (Criterion 3) | Weak | 35% |
| Independent Review & Explainability (Criterion 4) | Weak | 30% |
| Documentation & Algorithm Summary | Partial | 65% |
| Risk Management (Automation Bias) | Partial | 60% |
| Validation & Verification | Strong | 85% |
| Post-Market Surveillance | Partial | 55% |
| Quality Management System | Strong | 80% |
| Change Control & Audit Trail | Strong | 90% |
| Electronic Signatures (21 CFR Part 11) | Strong | 85% |

---

## What the FDA CDS Guidance Requires

### The Four Non-Device CDS Criteria

Software must meet **ALL FOUR** to be exempt from device regulation:

| Criterion | Requirement | What FDA Checks |
|-----------|------------|----------------|
| **1. No Image/Signal Processing** | Software must NOT acquire, process, or analyze medical images, IVD signals, or patterns from signal acquisition systems | Input data types; "pattern" = multiple/sequential/repeated measurements (ECG waveforms, CGM readings, NGS sequences). Discrete point-in-time measurements are OK. |
| **2. Medical Information Display** | Software must display, analyze, or print "medical information" — patient data, clinical guidelines, peer-reviewed studies, FDA-approved labeling | Data sources must be identifiable and grounded in "well-understood and accepted sources" |
| **3. HCP Recommendations** | Software must support or provide recommendations to a **healthcare professional** about prevention, diagnosis, or treatment — NOT replace or direct judgment | Must be labeled for HCPs, not patients. Must support, not replace. Single recommendation now OK (2026 update) if clinically appropriate. |
| **4. Independent Review** | Software must enable HCP to independently review the basis for recommendations, so they do NOT rely primarily on the software's output | No "black box" outputs. Must show inputs, logic basis, validation evidence, known limitations. Must not be used for time-critical urgent decisions. |

---

## Detailed Gap Analysis

### Criterion 1: No Image/Signal Processing

**FDA Requirement:** Software must not acquire, process, or analyze medical images or signals.

| Requirement Detail | SAGE Capability | Status | Gap |
|-------------------|----------------|--------|-----|
| Classify all software functions against Criterion 1 | `derive_system_requirements()` creates SystemRequirement objects with type classification (functional, performance, interface, safety, security) | Partial | **No explicit CDS function-level classification tool.** SAGE classifies requirements by engineering type, not by FDA CDS criteria. Need a method that takes each software function and maps it against all 4 criteria. |
| Identify image/signal processing in requirements | DOMAIN_RULES for `medical_device` triggers IEC 62304 compliance but does not check for image/signal processing exclusions | Missing | **Need a CDS Criterion 1 checker** that scans product description and requirements for image/signal processing keywords (CT, MRI, X-ray, ECG waveform, CGM stream, pathology, etc.) and flags them. |
| Distinguish "pattern" (regulated) from "discrete measurement" (exempt) | Not implemented | Missing | **Need pattern vs. discrete classification logic.** FDA defines "pattern" as multiple, sequential, or repeated measurements. SAGE should classify input data types and flag patterns. |
| Document input data types for each function | Product Owner's `_analyze_customer_input()` identifies domain and potential personas but does not classify input data types | Missing | **Need input data taxonomy per CDS function** — what data does the software acquire, and is it image/signal/pattern/discrete? |

**Criterion 1 Score: 25%** — SAGE has requirements engineering but lacks CDS-specific input classification.

---

### Criterion 2: Medical Information Display

**FDA Requirement:** Software must use "medical information" from well-understood and accepted sources.

| Requirement Detail | SAGE Capability | Status | Gap |
|-------------------|----------------|--------|-----|
| Identify all data sources used | Product Owner gathers requirements including technical constraints; Systems Engineer identifies interfaces | Partial | **No explicit data source registry.** Need a structured list of every data source (EHR, guidelines, peer-reviewed studies, FDA labeling) with provenance documentation. |
| Verify data sources are "well-understood and accepted" | Not implemented | Missing | **Need source validation framework.** Each data source must be mapped to: clinical guidelines, peer-reviewed literature, FDA-approved labeling, or government recommendations. Proprietary/novel data sources must be flagged. |
| Document that information qualifies as "medical information" | SRS generation (`_generate_srs()`) includes intended_use and regulatory_classification sections | Partial | **Need explicit "medical information" classification** per software function — what information does it display/analyze, and does it qualify under Criterion 2? |
| Labeling specifies all data sources | `_generate_srs()` includes sections for functional/performance/interface requirements but no explicit data source labeling section | Missing | **Need data source disclosure in SRS labeling.** FDA expects all sources (EHR fields, guideline databases, literature references) enumerated. |

**Criterion 2 Score: 30%** — SAGE generates requirements docs but lacks CDS data source provenance tracking.

---

### Criterion 3: HCP Recommendations (Support, Not Replace)

**FDA Requirement:** Software must support HCP decision-making, not replace or direct it. Intended for HCPs only.

| Requirement Detail | SAGE Capability | Status | Gap |
|-------------------|----------------|--------|-----|
| Intended user is HCP (not patient/caregiver) | Product Owner's `gather_requirements()` creates personas with `technical_comfort` field, but no explicit HCP vs. patient classification | Partial | **Need intended user classification** as HCP/patient/caregiver per software function. FDA requires this in labeling. |
| Software labeled as "decision support" not "decision directing" | Not implemented | Missing | **Need CDS labeling template** with explicit language: "This software supports healthcare professional decision-making. It does not replace clinical judgment." |
| Software does not produce definitive diagnoses | Not implemented | Missing | **Need output classification framework.** Each software output must be classified: recommendation (OK), definitive diagnosis (NOT OK), immediate intervention directive (NOT OK). |
| Workflow is non-urgent (allows time for review) | Not implemented | Missing | **Need workflow urgency classification.** FDA excludes time-critical software from Non-Device CDS. Each function must be assessed: does the HCP have time to review? |
| Single recommendation permitted (2026 update) | Not implemented | N/A | **New enforcement discretion.** If software provides single recommendation, all other criteria must be met. Need to document this in labeling. |

**Criterion 3 Score: 15%** — SAGE has requirements gathering but no CDS-specific output/user classification.

---

### Criterion 4: Independent Review & Transparency

**FDA Requirement:** HCP must be able to independently review the basis for recommendations. No black-box outputs.

| Requirement Detail | SAGE Capability | Status | Gap |
|-------------------|----------------|--------|-----|
| Algorithm approach documented in plain language | `_generate_srs()` and `_generate_sad()` generate technical architecture docs | Partial | **Need plain-language algorithm summary** for HCP consumption. Current docs are engineer-facing (IEC 62304 format), not clinician-facing. |
| Inputs, logic, and validation disclosed | Systems Engineer creates traceability matrices and verification procedures | Partial | **Need HCP-facing transparency layer** showing: what inputs were used, how the recommendation was generated, what clinical evidence supports it. |
| Known limitations documented | `_generate_risk_management_file()` includes residual_risk assessment | Partial | **Need clinical limitations disclosure** — not just engineering risks, but clinical accuracy limits, populations not tested, conditions where recommendations may be wrong. |
| Outputs flag missing/anomalous inputs | Not implemented | Missing | **Need runtime input validation with clinical context.** When patient data is missing or anomalous, the CDS must flag this to the HCP, not silently proceed. |
| Automation bias warnings included | Not implemented | Missing | **Need explicit automation bias warning** in labeling and UI: "This recommendation requires independent clinical review. Do not rely solely on this output." |
| Alternative options visible to HCP | Not implemented | Missing | **Need alternative recommendations display.** Unless using enforcement discretion for single recommendations, software should show alternative treatment/diagnostic options. |
| No black-box outputs | SAGE uses LLM for generation; LLM outputs are inherently opaque | Gap | **Critical gap for AI/ML-based CDS.** SAGE's LLM-generated recommendations are by nature "black box." Need explainability layer showing recommendation provenance. |

**Criterion 4 Score: 20%** — SAGE has documentation capabilities but lacks CDS-specific transparency features.

---

### Documentation Requirements

**FDA Requirement:** Algorithm development summary, validation results, labeling with intended use, known limitations.

| Requirement Detail | SAGE Capability | Status | Gap |
|-------------------|----------------|--------|-----|
| Algorithm development summary (approach, data sources, validation) | `_generate_srs()` includes algorithm approach in requirements; `_generate_sad()` includes architecture decisions | Covered | SRS and SAD provide algorithm documentation. **Gap: need clinical-facing summary separate from engineering docs.** |
| Intended use statement (non-urgent, HCP-focused) | Product Owner captures `vision` and `target_audience` in ProductBacklog | Partial | **Need formal intended use statement template** per FDA format: "This software is intended for use by [HCP type] to [support/provide recommendations] for [clinical purpose] in [non-urgent setting]." |
| Target patient population | Product Owner captures personas with demographics | Partial | **Need explicit patient population inclusion/exclusion criteria** — not just user personas, but the patient population the CDS covers. |
| Validation evidence and known limitations | `generate_vv_protocol()` and `generate_verification_procedures()` create test plans | Covered | V&V protocol covers engineering validation. **Gap: need clinical validation results (sensitivity/specificity, demographic subgroup analysis).** |
| Input specifications (data elements, how obtained, relevance) | Systems Engineer creates interface specifications and data flow diagrams | Partial | **Need CDS-specific input specification** — not just technical interfaces, but which clinical data elements, how they're obtained from EHR, and their clinical relevance. |
| Output context (missing/unusual inputs flagged) | Not implemented | Missing | **Need runtime output context framework** — when inputs are missing or unusual, CDS must document this in the output. |

**Documentation Score: 60%** — Strong engineering documentation, gaps in clinical-facing documentation.

---

### Risk Management (Automation Bias Focus)

**FDA Requirement:** Design against automation bias; HCPs must not over-rely on software output.

| Requirement Detail | SAGE Capability | Status | Gap |
|-------------------|----------------|--------|-----|
| Automation bias risk assessment | `assess_system_risks()` per ISO 31000; `_generate_risk_management_file()` per ISO 14971 | Partial | **Risk frameworks exist but need "automation bias" as explicit risk category.** Currently handles technical/safety/security risks, not cognitive bias risks. |
| Design for non-urgent workflows | DOMAIN_RULES distinguish `hitl_override: "strict"` vs `"standard"` | Partial | **Need urgency classification per CDS function.** SAGE gates actions via HITL but doesn't classify clinical urgency. |
| Test with actual clinician workflows | `generate_validation_procedures()` creates user-focused procedures | Partial | **Need clinical usability testing protocol** — not just software validation, but HCP workflow integration testing. |
| Monitor for reliance patterns post-deployment | Audit logger tracks approvals and rejections with actor identity | Partial | **Need post-deployment analytics** — track how often HCPs override recommendations, time spent reviewing, pattern detection for over-reliance. |

**Risk Management Score: 50%** — Strong technical risk management, missing cognitive/clinical bias dimensions.

---

### Validation & Verification

**FDA Requirement:** Validate algorithm performance on intended population; verify software functions as specified.

| Requirement Detail | SAGE Capability | Status | Gap |
|-------------------|----------------|--------|-----|
| Algorithm performance on intended population | `generate_validation_procedures()` creates user-focused validation with success_metrics | Partial | **Need clinical validation protocol** — accuracy, sensitivity, specificity across demographic subgroups, comparison to gold standard. |
| Accuracy across demographic subgroups | Not implemented | Missing | **Need demographic stratification in validation.** FDA expects proof that CDS works across age, sex, race, comorbidity subgroups. |
| Edge case handling (missing data, outliers) | `_generate_test_steps_for_requirement()` includes requirement-type specific test augmentation | Partial | **Need clinical edge case catalog** — missing labs, concurrent medications, rare conditions, pediatric/geriatric extremes. |
| Comparison to clinical guidelines | Not implemented | Missing | **Need guideline concordance testing** — compare CDS recommendations to published clinical guidelines and measure agreement rate. |
| Software verification (functions as specified) | `create_verification_matrix()` maps requirements to test methods; `_critic_review_code()` provides adversarial review | Covered | Strong verification infrastructure with traceability. |
| Verification of inputs correctly captured | Systems Engineer defines interface specifications with data elements | Covered | Interface specification covers input verification. |

**Validation Score: 65%** — Strong software V&V, missing clinical validation dimensions.

---

### Post-Market Surveillance

**FDA Requirement:** Monitor for over-reliance, track feedback, document algorithm changes, reassess compliance.

| Requirement Detail | SAGE Capability | Status | Gap |
|-------------------|----------------|--------|-----|
| Monitor HCP over-reliance | Audit logger tracks approvals/rejections with trace_id | Partial | **Need over-reliance detection analytics** — alert when acceptance rate exceeds threshold (e.g., >95% might indicate rubber-stamping). |
| Track user feedback | `refine_backlog()` in Product Owner handles stakeholder feedback; vector memory stores corrections | Partial | **Need structured HCP feedback collection** — clinical disagreements, near-misses, wrong recommendations, with root cause tracking. |
| Document algorithm changes | `initiate_change_request()` → `assess_change_impact()` → `execute_approved_change()` with full audit trail | Covered | Complete change control workflow with impact assessment. |
| Reassess CDS criteria after changes | Not implemented | Missing | **Need CDS criterion re-evaluation trigger** — after any algorithm change, re-run the 4-criterion assessment and document. |
| Prepare for device reclassification | Not implemented | Missing | **Need reclassification readiness plan** — if post-market evidence shows software directs rather than supports, what's the pathway to 510(k)/De Novo? |

**Post-Market Score: 50%** — Strong change control, missing clinical monitoring dimensions.

---

## Gap Summary Table

| # | Gap | FDA Requirement | SAGE Today | Priority | Effort |
|---|-----|----------------|-----------|----------|--------|
| G-01 | **CDS Function Classifier** | Map each software function against all 4 CDS criteria | No CDS-specific classification tool | Critical | Medium |
| G-02 | **Input Data Type Taxonomy** | Classify inputs as image/signal/pattern/discrete per function | No input classification | Critical | Medium |
| G-03 | **Data Source Provenance Registry** | Track every data source with clinical evidence classification | No data source registry | High | Medium |
| G-04 | **HCP vs Patient User Classification** | Classify intended user per function as HCP/patient/caregiver | Persona creation exists but no HCP classification | High | Low |
| G-05 | **CDS Output Type Classifier** | Classify outputs as recommendation/diagnosis/directive | No output classification | Critical | Medium |
| G-06 | **Clinical Urgency Assessment** | Classify each function as urgent/non-urgent for Criterion 4 | HITL gates exist but no urgency classification | High | Low |
| G-07 | **Plain-Language Algorithm Summary** | Clinician-readable algorithm explanation (not IEC 62304 format) | Engineering docs only | High | Medium |
| G-08 | **Transparency/Explainability Layer** | Show HCPs: inputs used, logic basis, clinical evidence, alternatives | Not implemented | Critical | High |
| G-09 | **Automation Bias Risk Category** | Add "automation bias" to risk framework with mitigation strategies | Risk framework exists but no cognitive bias category | High | Low |
| G-10 | **Clinical Limitations Disclosure** | Document accuracy limits, untested populations, failure conditions | Engineering risk file exists, not clinical | High | Medium |
| G-11 | **Runtime Input Validation (Clinical)** | Flag missing/anomalous patient data to HCP at runtime | Not implemented | High | Medium |
| G-12 | **Automation Bias Warning Labels** | Explicit warning: "Requires independent clinical review" | Not implemented | Critical | Low |
| G-13 | **Clinical Validation Protocol** | Accuracy, sensitivity/specificity, demographic subgroup analysis | Engineering V&V exists, not clinical | High | High |
| G-14 | **Guideline Concordance Testing** | Compare recommendations to published clinical guidelines | Not implemented | Medium | High |
| G-15 | **Over-Reliance Detection** | Monitor HCP acceptance rates, flag rubber-stamping patterns | Audit trail exists but no analytics | Medium | Medium |
| G-16 | **HCP Feedback Collection** | Structured clinical disagreement tracking with root cause | Vector memory exists but no clinical structure | Medium | Medium |
| G-17 | **CDS Criterion Re-Evaluation Trigger** | Re-assess 4 criteria after every algorithm change | Change control exists but no CDS re-check | High | Low |
| G-18 | **FDA CDS Labeling Template** | Formal intended use statement, data sources, limitations per FDA format | SRS exists but not CDS-formatted | High | Medium |
| G-19 | **Patient Population Criteria** | Inclusion/exclusion criteria for patient populations covered | Personas exist but not patient population specs | Medium | Low |
| G-20 | **Reclassification Readiness Plan** | Pathway to 510(k)/De Novo if post-market evidence warrants | Not implemented | Low | Medium |

---

## What SAGE Does Well (Strengths)

| Strength | FDA Relevance | SAGE Implementation |
|----------|--------------|-------------------|
| **Bidirectional Traceability** | Core requirement for any FDA submission | 4-matrix system: User Needs → Requirements → Design → Verification → Validation |
| **Immutable Audit Trail** | 21 CFR Part 11, post-market surveillance | SQLite audit log with trace_id, actor, timestamp, identity fields |
| **Electronic Signatures** | 21 CFR Part 11 compliance | create/apply/validate signature workflows with SHA-256 hash integrity |
| **Change Control** | FDA requires documented change management | initiate → assess_impact → execute_approved with full audit trail |
| **Risk Management** | ISO 14971, ISO 31000 | Risk register with severity/probability, mitigation, contingency, traceability |
| **Regulatory Document Generation** | IEC 62304 compliance | SRS, SAD, V&V Plan, Risk Management File, SOUP Inventory |
| **Domain-Aware Enforcement** | Medical device gets strict controls automatically | DOMAIN_RULES inject IEC 62304/ISO 13485/HIPAA requirements + strict HITL gates |
| **HITL Approval Gates** | Critical for regulated industries | 5-gate strict mode for medical/healthcare: plan, wave, code, integration, final |
| **Critic Review (Multi-Provider)** | Independent verification/review | N-provider scoring with adversarial review before human approval |
| **Verification Procedures** | FDA expects reproducible test protocols | Auto-generated per requirement with pass/fail criteria, test steps, expected results |

---

## Recommended Implementation Roadmap

### Phase 1: Critical Gaps (Weeks 1-3)
- G-01: CDS Function Classifier — new method `classify_cds_function()` in systems_engineering.py
- G-05: CDS Output Type Classifier — extend SystemRequirement with output_type field
- G-08: Transparency Layer — new module `src/core/cds_transparency.py` for explainability
- G-12: Automation Bias Warning Labels — template additions to regulatory document generation

### Phase 2: High Priority Gaps (Weeks 4-6)
- G-02: Input Data Type Taxonomy — extend requirements derivation with input classification
- G-03: Data Source Provenance Registry — new dataclass and tracking in systems_engineering.py
- G-04: HCP User Classification — extend ProductBacklog personas with regulatory user type
- G-07: Plain-Language Algorithm Summary — add clinician-facing document to regulatory docs
- G-09: Automation Bias Risk Category — extend risk assessment with cognitive bias dimension
- G-18: FDA CDS Labeling Template — new document template in regulatory doc generation

### Phase 3: Medium Priority Gaps (Weeks 7-10)
- G-06, G-10, G-11: Clinical urgency, limitations, runtime validation
- G-13, G-14: Clinical validation protocol and guideline concordance testing
- G-15, G-16, G-17: Post-market monitoring, HCP feedback, criterion re-evaluation

### Phase 4: Lower Priority (Weeks 11-12)
- G-19, G-20: Patient population criteria, reclassification readiness

---

## Conclusion

SAGE Framework has a **strong foundation** for FDA CDS compliance — particularly in:
- Design controls and traceability (90%)
- Change control and audit trail (90%)
- Verification and validation infrastructure (85%)
- Electronic signatures per 21 CFR Part 11 (85%)

The **critical gaps** are CDS-specific requirements that the current framework was not designed for:
- CDS criteria classification (functions, inputs, outputs, urgency)
- Transparency and explainability for healthcare professionals
- Automation bias mitigation
- Clinical-facing documentation (vs. engineering-facing)

These gaps are **addressable** — SAGE's modular architecture (Systems Engineering framework, Product Owner agent, Build Orchestrator) provides clear extension points for CDS-specific capabilities. The existing regulatory document generation, risk management, and audit trail infrastructure can be extended rather than rebuilt.

**Bottom line:** SAGE is 68% compliant today. With the 20 identified gap closures, it can reach full FDA CDS guidance compliance as a development platform for clinical decision support software.

---

Sources:
- [FDA CDS Software Guidance (2026)](https://www.fda.gov/media/109618/download)
- [Covington: 5 Key Takeaways from FDA CDS Guidance](https://www.cov.com/en/news-and-insights/insights/2026/01/5-key-takeaways-from-fdas-revised-clinical-decision-support-cds-software-guidance)
- [CITI Program: FDA 2026 CDS Compliance Expectations](https://about.citiprogram.org/blog/clinical-decision-support-compliance-fdas-2026-expectations/)
- [Faegre Drinker: Key Updates in FDA 2026 CDS Guidance](https://www.faegredrinker.com/en/insights/publications/2026/1/key-updates-in-fdas-2026-general-wellness-and-clinical-decision-support-software-guidance)
- [King & Spalding: FDA Updates CDS Guidance](https://www.kslaw.com/news-and-insights/fda-updates-general-wellness-and-clinical-decision-support-guidance-documents)
- [Arnold & Porter: FDA Cuts Red Tape on CDS](https://www.arnoldporter.com/en/perspectives/advisories/2026/01/fda-cuts-red-tape-on-clinical-decision-support-software)
- [FDA Town Hall: CDS Final Guidance 03/11/2026](https://www.fda.gov/medical-devices/medical-devices-news-and-events/town-hall-clinical-decision-support-software-final-guidance-03112026)
