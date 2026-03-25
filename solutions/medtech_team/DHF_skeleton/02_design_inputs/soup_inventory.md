# SOUP (Software of Unknown Provenance) Inventory

**Clause:** IEC 62304:2006/AMD1:2015 §8.1.2
**Document ID:** DHF-SOUP-001
**Revision:** A

---

## Purpose

This document lists all third-party software components (SOUP) integrated into [PRODUCT NAME]. Each entry includes version, license, known anomalies, and risk impact per IEC 62304 §7.1.3.

## SOUP Register

| ID | Name | Version | License | Purpose | Safety Class Impact | Known Anomalies | Risk Control |
|---|---|---|---|---|---|---|---|
| SOUP-001 | [Library Name] | [X.Y.Z] | [MIT/Apache/BSD] | [Purpose] | Class C | [CVE / None] | [Mitigation] |
| SOUP-002 | [OS/RTOS Name] | [X.Y.Z] | [License] | Real-time scheduling | Class C | [Errata list URL] | Vendor-qualified build |
| SOUP-003 | [Crypto Library] | [X.Y.Z] | [License] | TLS 1.3 | Class C | None known | Pin to verified hash |

## SOUP Evaluation Criteria (IEC 62304 §7.1.3)

For each SOUP the following must be documented:
1. Functional and performance requirements the SOUP must meet
2. Hardware and software required by the SOUP
3. Known anomalies in the SOUP relevant to safety
4. Where to obtain published SOUP anomaly lists
5. History of use of the SOUP (if applicable)
