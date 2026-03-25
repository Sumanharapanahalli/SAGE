# Design Verification Plan

**Clause:** FDA 21 CFR 820.30(f), IEC 62304 §5.6
**Document ID:** DHF-VER-001
**Revision:** A
**Status:** DRAFT

---

## 1. Purpose

This plan establishes the strategy, scope, methods, and acceptance criteria for verification that design outputs meet design inputs for [PRODUCT NAME]. Verification answers: **"Did we build the product right?"**

## 2. Scope

All software items classified as IEC 62304 Class B or C are in scope. Hardware verification is under a separate plan.

## 3. Verification Methods

| Method | Description | Class C Required |
|---|---|---|
| Unit Testing | Individual module / function testing with >=85% branch coverage | YES |
| Integration Testing | Subsystem interface testing (firmware to cloud, cloud to dashboard) | YES |
| System Testing | End-to-end functional, performance, and safety requirement testing | YES |
| Code Review | Peer review of all Class C source code | YES |
| Static Analysis | MISRA-C/C++ for firmware; SonarQube for backend | YES |
| Regression Testing | Full test suite re-run on every change to Class C items | YES |
| SOUP Verification | Functional testing of each SOUP in integrated context | YES |

## 4. Entry Criteria (begin verification)

- [ ] Software implementation phase (P4) exit criteria met
- [ ] Build is reproducible from CM-controlled source
- [ ] All unit tests passing
- [ ] Static analysis baseline established
- [ ] Verification environment qualified (IQ complete)

## 5. Exit Criteria (verification complete)

- [ ] 100% of SRS SHALL requirements have passing test records
- [ ] Branch coverage >=85% for all Class C software items
- [ ] Zero open Critical or High defects
- [ ] All SOUP items verified in integrated context
- [ ] Traceability matrix complete: every SRS-FR-xxx, SRS-SR-xxx, SRS-RR-xxx linked to at least one passing test
- [ ] Verification report reviewed and signed by QA

## 6. Test Environment

| Component | Description | Version / Config |
|---|---|---|
| Hardware Target | [BOARD NAME] | [HW Rev] |
| OS / RTOS | [OS NAME] | [Version] |
| Test Framework | pytest / Unity / GTest | [Version] |
| Static Analyzer | [Tool] | [Version, rule set] |
| Coverage Tool | [Tool] | [Version] |

## 7. Defect Classification

| Severity | Definition | Resolution Before Release |
|---|---|---|
| Critical | Could cause patient harm or data loss | MUST fix |
| High | Major functional failure; workaround exists | MUST fix or risk-accepted |
| Medium | Moderate functional impact | Fix planned or risk-accepted |
| Low | Minor cosmetic or UX issue | Fix at discretion |

## 8. Approval

| Role | Name | Signature | Date |
|---|---|---|---|
| Verification Lead | | | |
| QA Manager | | | |
