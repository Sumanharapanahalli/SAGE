# Regulatory Compliance — Medical Imaging Ai

**Domain:** medtech
**Solution ID:** 008
**Generated:** 2026-03-22T11:53:39.308878
**HITL Level:** strict

---

## 1. Applicable Standards

- **FDA 510(k)**
- **IEC 62304**
- **ISO 13485**
- **ISO 14971**
- **DICOM**

## 2. Domain Detection Results

- medtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 4 | SAFETY | Perform ISO 14971 hazard analysis and risk assessment for the AI SaMD. Identify  | Risk management, FMEA, hazard analysis |
| Step 12 | COMPLIANCE | Produce IEC 62304 software lifecycle artifacts: Software Development Plan, Softw | Standards mapping, DHF, traceability |
| Step 15 | SECURITY | Conduct security threat modeling (STRIDE), PHI data flow analysis, HIPAA Technic | Threat modeling, penetration testing |
| Step 17 | EMBEDDED_TEST | Build ML model validation harness: clinical performance evaluation on independen | Hardware-in-the-loop verification |
| Step 18 | SYSTEM_TEST | Execute end-to-end system test plan: DICOM upload to finding approval workflow,  | End-to-end validation, performance |
| Step 19 | QA | Execute Design History File (DHF) review, software quality audit per ISO 13485,  | Verification & validation |
| Step 20 | COMPLIANCE | Compile complete Design History File (DHF) per 21 CFR Part 820.30: design inputs | Standards mapping, DHF, traceability |
| Step 21 | REGULATORY | Prepare FDA 510(k) premarket notification submission package and De Novo classif | Submission preparation, audit readiness |
| Step 22 | LEGAL | Review software licensing for all ML dependencies, DICOM libraries, and open-sou | Privacy, licensing, contracts |

**Total tasks:** 24 | **Compliance tasks:** 9 | **Coverage:** 38%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | FDA 510(k) compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | IEC 62304 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | ISO 13485 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 4 | ISO 14971 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 5 | DICOM compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

## 5. Risk Assessment Summary

**Risk Level:** HIGH — Safety-critical domain requiring strict HITL gates

| Risk Category | Mitigation in Plan |
|--------------|-------------------|
| Patient/User Safety | SAFETY tasks with FMEA and hazard analysis |
| Data Integrity | DATABASE tasks with audit trail requirements |
| Cybersecurity | SECURITY tasks with threat modeling |
| Regulatory Non-compliance | REGULATORY + COMPLIANCE tasks |
| Software Defects | QA + SYSTEM_TEST + EMBEDDED_TEST tasks |

## 6. Agent Team Assignment

| Agent Role | Tasks Assigned | Team |
|-----------|---------------|------|
| developer | 5 | Engineering |
| regulatory_specialist | 4 | Compliance |
| data_scientist | 3 | Analysis |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| product_manager | 1 | Design |
| business_analyst | 1 | Analysis |
| ux_designer | 1 | Design |
| safety_engineer | 1 | Compliance |
| system_tester | 1 | Engineering |
| legal_advisor | 1 | Compliance |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 61/100 (FAIL) — 1 iteration(s)

**Summary:** This plan demonstrates sophisticated domain knowledge across medical AI, regulatory affairs, and clinical workflow — it is clearly not a naive first attempt. The IEC 62304 Class C framing, ISO 14971 hazard analysis, SMART on FHIR auth, and HITL proposal gate are all correctly scoped. However, it has one critical technical error that invalidates a third of the ML work (LUNA16/LIDC-IDRI are CT datasets, not chest X-ray), a fundamental regulatory pathway contradiction (simultaneous 510(k) + De Novo without resolution), and three compliance gaps that would block FDA clearance outright (no PMS plan, no UDI, no MDR procedures). The load test target inconsistency (500/day vs 500 concurrent) will cause a costly misunderstanding. For a regulated Class II SaMD requiring 85+ to ship, this plan scores 61 — the architecture is solid but the regulatory and ML data gaps require dedicated rework before implementation begins, not post-hoc patching. Priority fixes in order: (1) resolve the CT/CXR dataset error and recalibrate nodule performance targets, (2) schedule FDA pre-submission meeting before any 510(k) documents are written, (3) add IRB submission to the critical path immediately, (4) add PMS/MDR/UDI steps before Step 21.

### Flaws Identified

1. CRITICAL: Step 8 and Step 7 use LUNA16 and LIDC-IDRI for lung nodule training data — these are CT datasets, not chest X-ray (CR/DX). CXR nodule detection is a fundamentally different task. LUNA16 test set cited in Step 17 acceptance criteria is also CT. The entire nodule detection pipeline is built on the wrong modality. Achieving sensitivity ≥90% on CXR nodules is also an unrealistic target; state-of-the-art CXR nodule detection AUC is typically 0.82–0.87.
2. Regulatory pathway is internally contradictory. 510(k) requires a substantially equivalent predicate; De Novo is for novel devices without a predicate. Running both simultaneously for the same device is not how FDA pathways work. A 3-condition AI algorithm covering pneumonia + TB + lung nodules simultaneously almost certainly has no single 510(k) predicate covering all three — De Novo is the likely correct path, and the substantial equivalence argument in Step 21 may be unbuildable.
3. Step 18 acceptance criteria state '500 concurrent studies processed' — but Step 13 payload targets '500 studies/day' throughput. These are orders of magnitude apart. 500/day ≈ 0.3 studies/minute; 500 concurrent is a crushing GPU load test. This inconsistency will cause the load test to either trivially pass or catastrophically fail depending on which number engineering implements.
4. No dedicated step for Post-Market Surveillance (PMS) plan. FDA 21 CFR 522 and EU MDR Article 83 both require formal PMS for Class II devices. The plan's drift detection in Step 17 is analytical validation tooling, not a PMS plan. Missing: complaint handling, MDR/vigilance reporting timelines, PMSR/PSUR schedules.
5. No step or acceptance criteria addressing FDA Medical Device Reporting (MDR) under 21 CFR Part 803 — adverse event reporting procedures, reportability criteria, and 30-day/5-day reporting timelines. This is a legal requirement for cleared Class II devices.
6. Step 9 HITL configuration depends only on Step 5 (API design) but not Step 8 (ML model). The HITL proposal structure (finding_positive, finding_negative, urgency_escalation) must be defined by what the model actually outputs — confidence scores, bounding box formats, uncertainty estimates. This dependency gap means Step 9 will be built against abstract API contracts, then likely need rework when the actual model outputs differ.
7. Multi-label vs separate classifier inconsistency in Step 8: 'multi-label CNN ensemble' and 'separate calibrated classifiers per condition' are different architectures with different training objectives, loss functions, and calibration approaches. A multi-label model trained with BCE per label is not the same as N independent binary classifiers. The architecture decision is unresolved and will create downstream model card, FMEA, and regulatory documentation conflicts.
8. No dedicated Software Architecture Document (SAD) design step. The SAD is an artifact produced in Step 12 (compliance), but no preceding step actually designs the architecture. Critical architectural decisions — monolith vs microservices, sync vs async inference, DICOM storage strategy — are scattered across Step 10 (backend) and Step 13 (infra) without a preceding design gate. This inverts the design-then-implement sequence that IEC 62304 Class C requires.
9. Step 7 preprocessing resizes all images to 512x512. For CXR with modern DR panels producing 3000x3000+ pixel images, this aggressive downsampling may eliminate sub-centimeter nodules — the very finding the model is supposed to detect. No clinical validation that 512x512 preserves diagnostic quality for all three target conditions.
10. IRB approval process is entirely absent. Using CheXpert, NIH ChestXray14, TBX11K, and Shenzhen datasets requires compliance with each dataset's Data Use Agreement. CheXpert (Stanford) requires registration. Reader study in Step 17 (N=100 cases with radiologists) requires IRB approval before execution. No step accounts for IRB submission, review timeline (typically 4–12 weeks), or DUA execution.

### Suggestions

1. Replace LUNA16/LIDC-IDRI with CXR-specific nodule datasets: VinDr-CXR (18,000 CXRs with nodule annotations), PadChest (subset), or Indiana University Chest X-rays. Accept that CXR nodule sensitivity targets must be calibrated to CXR state-of-the-art (~0.85 AUC), not CT benchmarks.
2. Resolve the 510(k)/De Novo conflict in Step 1 before any other regulatory work. Recommend a pre-submission meeting (Q-Sub) with FDA under the Q-Submission Program to get agency agreement on pathway before committing to the 510(k) predicate strategy. This single meeting could save 12+ months of rework.
3. Add a dedicated Step 0 or Step 1a for IRB submission and DUA execution covering all training datasets and the reader study protocol. This is on the critical path because IRB approval commonly takes 8–12 weeks and blocks Steps 8 and 17.
4. Add a dedicated Post-Market Surveillance step between Steps 21 and 22 covering: PMS plan, complaint handling SOP, MDR reportability matrix, PSUR schedule, and real-world performance monitoring dashboard with clinical KPIs.
5. Add Unique Device Identification (UDI) assignment to Step 20 or 21. FDA requires UDI for Class II devices under 21 CFR Part 830. UDI labeler account registration at GUDID must be completed before market clearance.
6. Separate the Predetermined Change Control Plan (PCCP) into its own dedicated step rather than burying it as a line item in Step 21. The PCCP for an ML/AI SaMD defines what model updates require a new submission vs. can be deployed under the cleared PCCP — this is the document that determines your entire post-market model update strategy.
7. Add explicit GPU autoscaling to Step 13. Chest X-ray studies arrive in bursts (overnight batch, morning rounds), and always-on GPU instances for a hospital deployment are cost-prohibitive. Define horizontal pod autoscaler thresholds and scale-from-zero behavior for inference pods.
8. Step 17 reader study (N=100) is underpowered for demonstrating statistically significant AI-assisted improvement (p<0.05) if the expected effect size is modest. Run a power calculation before committing to N=100. For AUC differences of 0.03–0.05, you likely need N=200–400 cases.
9. Add explicit de-identification verification step for any real patient data used in development. DICOM metadata removal is notoriously incomplete — burnt-in PHI in pixel data, private DICOM tags, and facility-specific extensions are common sources of de-identification failures that constitute HIPAA breaches.

### Missing Elements

1. Post-Market Surveillance (PMS) plan and PSUR/PMSR schedule — required for Class II FDA clearance and EU MDR
2. Unique Device Identification (UDI) registration and labeling per 21 CFR Part 830
3. FDA Medical Device Reporting (MDR) / adverse event handling procedures per 21 CFR Part 803
4. Pre-Submission (Q-Sub) meeting with FDA to agree on regulatory pathway before any 510(k)/De Novo work
5. IRB approval process and timeline for reader study (Step 17) and any retrospective clinical data use
6. Data Use Agreement execution steps for CheXpert (Stanford), TBX11K, Shenzhen, and any other licensed dataset
7. Predetermined Change Control Plan (PCCP) as a standalone deliverable with resubmission trigger criteria
8. Production monitoring and observability stack — Grafana/Prometheus dashboards for inference latency, model score distributions, DICOM ingestion rates, and system health
9. Disaster recovery and business continuity plan — RTO/RPO targets for a clinical system that radiologists depend on
10. Model governance policy — who can approve model updates to production, what evidence is required, review board composition
11. DICOM conformance statement — required for PACS integration certification; hospitals' PACS vendors will demand this before allowing C-STORE connections
12. HL7 v2 integration for worklist (HL7 ORM/ORU messages) — most hospital RIS systems still use HL7 v2, not FHIR, for worklist management; FHIR-only assumption will block many hospital integrations
13. EU MDR pathway if any EU market is anticipated — CE marking, Notified Body engagement, EUDAMED registration are entirely absent
14. Software bill of materials (SBOM) process for ongoing maintenance — Step 15 generates initial SBOM but no process for keeping it current as dependencies update
15. Clinical site pilot/beta program plan — structured limited market release (LMR) or controlled deployment before full commercial launch

### Security Risks

1. DICOM C-STORE SCP listener (Step 7) is a network service accepting binary data from untrusted hospital networks. DICOM has a long history of CVEs in parsing libraries (pydicom, dcm4che). The plan has no mention of DICOM input validation beyond 'corrupt file quarantine' — malicious DICOM files (pixel data buffer overflows, tag injection) are a realistic attack vector in a hospital network context. Require fuzz testing of the DICOM ingestion path specifically.
2. ML model adversarial robustness is listed as a security acceptance criterion but the test is superficial ('pixel perturbation attacks'). For a clinical AI, the more realistic adversarial threat is subtle image manipulation that causes false negatives on specific patient populations — not academic FGSM attacks. The adversarial testing plan needs to include clinically-motivated perturbation scenarios (compression artifacts, vendor-specific DICOM rendering differences).
3. OAuth2 SMART on FHIR token validation (Step 10) against a 'test FHIR authorization server' — acceptance criteria don't require testing against a production-grade authorization server. Token replay attacks, JWT algorithm confusion attacks (alg:none), and scope escalation are not explicitly tested. The SMART on FHIR security profile has specific requirements around token binding and audience validation that need explicit test cases.
4. Vault integration (Step 13) with 'no secrets in environment variables' — correct intent, but Kubernetes service account tokens used for Vault authentication are themselves secrets that can be compromised via SSRF attacks on the metadata endpoint. The secret zero problem for Vault in Kubernetes requires explicit mitigation (Vault Agent injector or CSI driver with proper RBAC).
5. DICOM data in S3 encrypted at rest, but DICOM metadata extraction to PostgreSQL (Step 7) copies PHI from encrypted S3 to the database. The database encryption key management and backup encryption are not explicitly addressed. PostgreSQL RDS encryption at rest is enabled by default but backup snapshots and read replicas require separate key management verification.
6. Step 15 SBOM covers production dependencies at a point in time, but the ML training pipeline has its own dependency tree (PyTorch, torchvision, albumentations, etc.) that may include high-CVE packages. Supply chain attacks targeting ML training environments (malicious PyPI packages) are an emerging threat not addressed in the security plan.
7. No mention of network egress controls for the inference service. A compromised inference pod that exfiltrates DICOM studies would be high-severity. Kubernetes NetworkPolicy restricting egress from inference pods to only required services (database, Redis, internal APIs) should be an explicit infrastructure requirement.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.308925
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
