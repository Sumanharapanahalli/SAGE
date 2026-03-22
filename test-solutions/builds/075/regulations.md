# Regulatory Compliance — Exam Proctoring

**Domain:** edtech
**Solution ID:** 075
**Generated:** 2026-03-22T11:53:39.329673
**HITL Level:** standard

---

## 1. Applicable Standards

- **FERPA**
- **GDPR**
- **Biometric Privacy Laws**
- **ADA**

## 2. Domain Detection Results

- edtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 4 | COMPLIANCE | Produce compliance artifacts for COPPA, FERPA, and WCAG 2.1. Document data reten | Standards mapping, DHF, traceability |
| Step 5 | SECURITY | Threat model the platform covering webcam/screen data streams, identity document | Threat modeling, penetration testing |
| Step 20 | QA | Produce the QA test plan, test case suite, and execute test runs for all platfor | Verification & validation |
| Step 21 | SYSTEM_TEST | End-to-end system test suite: full exam lifecycle from scheduling through identi | End-to-end validation, performance |
| Step 24 | COMPLIANCE | Final compliance package: compile COPPA verifiable parental consent records, FER | Standards mapping, DHF, traceability |

**Total tasks:** 24 | **Compliance tasks:** 5 | **Coverage:** 21%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | FERPA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 3 | Biometric Privacy Laws compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 4 | ADA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

## 5. Risk Assessment Summary

**Risk Level:** STANDARD — Compliance focus on data protection and quality

| Risk Category | Mitigation in Plan |
|--------------|-------------------|
| Data Privacy | SECURITY + LEGAL tasks |
| Service Quality | QA + SYSTEM_TEST tasks |
| Compliance Gap | REGULATORY tasks (if applicable) |

## 6. Agent Team Assignment

| Agent Role | Tasks Assigned | Team |
|-----------|---------------|------|
| developer | 9 | Engineering |
| regulatory_specialist | 3 | Compliance |
| devops_engineer | 2 | Engineering |
| data_scientist | 2 | Analysis |
| qa_engineer | 2 | Engineering |
| business_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| localization_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 58/100 (FAIL) — 1 iteration(s)

**Summary:** This is a well-structured plan that correctly identifies FERPA/COPPA compliance as a first-class concern and sequences dependencies logically. However, it has several production-blocking gaps that prevent a score above 60. The most critical: GDPR is entirely absent (blocking EU market entry), the WebRTC media architecture is insufficient for 30-stream proctor views and 500-session scale (a media server is required, not just TURN), and the AI model training plan is aspirational rather than grounded in real datasets and timelines. The identity verification layer has an unaddressed demographic bias risk by relying solely on AWS Rekognition without independent audit. The exam content itself has no leak protection despite screen recording being central to the product. For a regulated EdTech platform handling student biometric data and academic records, these aren't polish issues — they are fundamental architectural and compliance failures that will surface within the first institutional pilot. The plan needs a GDPR step, a media server architecture decision, realistic ML scope reduction, and a screen-content security model before it's production-ready.

### Flaws Identified

1. GDPR is entirely absent. Any institution with EU students — or processing data of EU residents — triggers GDPR obligations (lawful basis for processing biometric data, data subject rights, DPAs with AWS). Biometric data (face matching) is 'special category' under Article 9 and requires explicit consent + DPA. This is not a minor gap; it blocks EU market entry entirely.
2. WebRTC at 500 concurrent sessions is severely underestimated. Each exam generates 2 streams (webcam + screen share) at ~1-2 Mbps each. That's 1-2 Gbps of media throughput minimum. A single Coturn TURN server will saturate and become the single point of failure. Coturn horizontal scaling, bandwidth limits, and TURN server cost are never addressed.
3. The proctor dashboard requirement of 30 simultaneous live WebRTC streams in a single browser tab is not achievable with standard WebRTC. Browsers cap concurrent RTCPeerConnection instances (practical limit ~10-15 before degradation). This requires a media server (Janus, mediasoup, LiveKit) to transcode/fan-out streams — none of which appear in the infra step.
4. Step 11 AI model acceptance criteria are aspirational, not engineered. Training YOLOv8 from scratch on 'synthetic + licensed proctoring datasets' to achieve >=95% precision is months of ML work. No dataset is named, no licensing is verified, and no baseline model is specified. In practice, teams fine-tune a pre-trained YOLO checkpoint — but that's not what's described.
5. AWS Rekognition has documented demographic bias in face recognition, particularly for darker skin tones (MIT Media Lab, NIST FRVT data). Using it as the identity verification backbone without independent bias validation creates disparate impact liability — especially for a FERPA-regulated product. Step 20 audits the cheating model for bias but not the identity verification service.
6. TimescaleDB in step 13 conflicts with the RDS PostgreSQL in step 7. TimescaleDB is not available as a managed RDS extension — you need a self-managed EC2 instance or Timescale Cloud. This is an architectural inconsistency that will break the infra plan.
7. HLS chunk merge failure on session end has no recovery path. Step 10 says 'async merge of HLS chunks into single MP4' but doesn't address: what if FFmpeg OOM-kills during merge? What if chunks are partially uploaded? These recordings are legal evidence in academic integrity cases. Data loss here is catastrophic.
8. No browser lockdown mechanism. A student can trivially have a second device, a phone propped up beside the monitor, or use a VM. The entire plan assumes the threat model is 'detected via webcam analysis' but doesn't address physical second-device cheating or VM/virtual webcam spoofing (e.g., OBS virtual camera defeating liveness checks).
9. Exam content leakage via screen recording is unaddressed. The platform records the student's screen — which contains exam questions. Step 5 lists 'exam_content_leakage' as a threat vector but the encryption spec only covers recordings at rest. There's no watermarking, no mechanism to prevent a recording from being extracted and exam questions distributed.
10. SAML SSO tested against 'mock IdP' only. Real institutional IdPs (Shibboleth, ADFS, Okta, Azure AD) have attribute mapping differences, certificate rotation schedules, and session timeout behaviors that mock IdPs never replicate. This will cause SSO integration failures with institutions post-launch.
11. Data residency is never addressed. Many EU institutions require data stored in EU regions. HIPAA-adjacent institutions (nursing programs, medical schools) may have additional requirements. The plan hardcodes AWS without region strategy.
12. Step 12 requires '< 1 second end-to-end latency (frame to proctor alert)' through a chain of: frame extraction → SageMaker endpoint → threshold filter → incident store → WebSocket push. SageMaker real-time endpoint warm inference is ~50-200ms, but the full pipeline under load has never been benchmarked. The acceptance criterion has no load qualification.
13. Audio recording in student homes creates untested legal exposure. Recording ambient audio may capture family members (including minors under COPPA), medical conversations, or legally protected communications. The compliance step covers COPPA for the student but not for third-party audio capture.

### Suggestions

1. Add a GDPR/CCPA compliance step parallel to step 4. Specifically: Article 9 explicit consent for biometric processing, DPIA (Data Protection Impact Assessment) for webcam/face data, DPA templates for EU institutions, and right-to-erasure workflow for recordings.
2. Replace the single Coturn server with a media server architecture (LiveKit, mediasoup, or Janus). This solves both the TURN scale problem and the 30-stream proctor dashboard problem — the media server handles fan-out, thumbnail generation, and recording, which simplifies steps 10 and 16 significantly.
3. Replace 'train from scratch' in step 11 with 'fine-tune pre-trained models.' Specify exact base models (YOLOv8n pretrained on COCO for object detection, MediaPipe FaceMesh for gaze — both are already production-quality). Reduce timeline expectation accordingly. Training data sourcing should be a separate step with IRB/licensing verification.
4. Add an independent bias audit of AWS Rekognition for the specific identity document types and demographic distribution of your target student population, using NIST FRVT as the benchmark reference. If Rekognition fails the audit, specify a fallback vendor (e.g., FaceIO, Veriff, Onfido).
5. Add exam content watermarking to step 5/10. Each student session should receive a unique steganographic watermark embedded in exam content delivery so that leaked questions can be traced to the source session.
6. Clarify the TimescaleDB deployment model in step 7's Terraform: either use Aurora PostgreSQL with pg_timeseries extension (RDS-compatible) or add a separate TimescaleDB EC2 instance to the infra architecture. Don't leave this as an implicit assumption.
7. Add chunk recovery and integrity verification to step 10. HLS segments should be checksummed on upload; a session-end reconciliation job should verify all expected chunks are present before triggering merge, with an alert to proctor if gaps are detected.
8. Separate the 'TURN server scale' concern from signaling in step 7: deploy Coturn behind an NLB with auto-scaling group, and add bandwidth cost estimate to the ROI analysis in step 1. TURN relay at scale is expensive (~$0.03/GB) and will surprise institutions.
9. Add virtual camera / VM detection to step 11's threat model. AWS Rekognition liveness detection does not catch OBS virtual camera. Add a WebRTC media fingerprinting check (codec negotiation, timing analysis) or a dedicated anti-spoofing vendor.
10. Add geographic data routing in step 7: EU traffic should stay in eu-west-1 or eu-central-1. Implement CloudFront origin routing by geography and RDS read replicas in relevant regions.

### Missing Elements

1. GDPR compliance artifacts (DPIA, Article 9 consent mechanism for biometric data, DPA templates, right-to-erasure workflow for recordings, data subject access request handling)
2. Media server architecture for fan-out streaming (LiveKit/mediasoup) — critical for both 30-stream proctor view and TURN scale
3. LMS integration implementation — Canvas and Moodle are mentioned in step 17 UI settings but there's no backend step for LTI 1.3 / OAuth 2.0 integration, which is how institutions actually launch exams from their LMS
4. Exam content watermarking and anti-leakage controls
5. Virtual webcam / VM spoofing detection in threat model and AI pipeline
6. Browser compatibility matrix — which browsers support getDisplayMedia, and what's the fallback for unsupported environments
7. SageMaker endpoint auto-scaling policy — at 500 concurrent sessions extracting 1 frame/sec, that's 500 inference requests/sec, which requires a provisioned concurrency plan
8. Data residency and geographic routing strategy (EU data sovereignty, country-specific storage requirements)
9. Third-party audio consent mechanism for household members captured incidentally
10. Incident appeals workflow — students who believe they were falsely flagged need a formal appeal process, which has FERPA implications
11. Exam content delivery security (how questions are sent to the student browser and protected from extraction)
12. Independent Rekognition bias audit for identity verification demographic fairness
13. FERPA breach notification procedure with timeline (institutions must be notified within specific windows)

### Security Risks

1. Virtual camera injection bypasses liveness detection: OBS Studio and similar tools present as a legitimate webcam device. AWS Rekognition FaceMovementAndLightChallenge detects some spoofing but not all virtual camera attacks. No compensating control is specified.
2. JWT refresh token theft via XSS: 24-hour refresh tokens stored in a browser context are high-value targets. The plan specifies 'session token security' but doesn't specify httpOnly/Secure cookie storage vs localStorage. localStorage refresh tokens are trivially exfiltrated by any XSS.
3. TURN credential exposure: Coturn uses time-limited HMAC credentials. If the TURN secret leaks (e.g., via misconfigured environment variable in ECS), an attacker can relay arbitrary WebRTC traffic through your TURN server at your bandwidth cost. Secrets Manager is specified but TURN credential rotation cadence is not.
4. SageMaker endpoint enumeration: if the SageMaker endpoint URL is embedded in frontend or API responses, an adversary could probe it directly to map model behavior and calibrate cheating techniques to stay below detection thresholds.
5. Insecure direct object reference on recordings: S3 object keys for recordings are stored in the database. If presigned URL generation doesn't enforce institution_id scoping in the IAM condition, a student with a valid JWT could construct requests for another institution's recordings.
6. AI model poisoning via feedback loop: Step 14's threshold auto-adjustment based on proctor decisions could be systematically gamed. A proctor (or compromised proctor account) dismissing all incidents of type X for 50 sessions lowers the threshold for that institution, effectively disabling detection for that incident type.
7. WebRTC signaling server as DoS vector: the WebSocket signaling endpoint (step 10) is unauthenticated at the protocol level until the JWT is validated. A bot that opens thousands of WebSocket connections before authenticating can exhaust connection limits. No connection-level rate limiting is specified for WebSocket upgrade requests.
8. Screen recording captures sensitive non-exam content: the student's screen recording may capture passwords autofilled by a password manager, banking sites in other tabs, or medical portals. This data is stored in S3 indefinitely per the retention policy. The threat model doesn't classify this as a risk.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.329717
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
