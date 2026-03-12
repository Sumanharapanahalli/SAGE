# Security Plan
## SAGE[ai] — Autonomous Manufacturing Intelligence System

**Document ID:** SAGE-SEC-001
**Version:** 2.0.0
**Status:** Approved
**Date:** 2026-03-11

---

## 1. Purpose

This Security Plan documents the cybersecurity controls implemented in SAGE[ai] and the residual risks, in accordance with:
- **FDA Guidance: Cybersecurity in Medical Devices (2023)**
- **ISO/IEC 27001** — Information Security Management
- **NIST SP 800-218** — Secure Software Development Framework (SSDF)
- **IEC 81001-5-1** — Health Software Security Activities in the Product Lifecycle

---

## 2. Threat Model

### 2.1 System Boundary

```
[Internet / Cloud LLM]
         │
    [Firewall]
         │
[Internal Network]
    │         │
[FastAPI]   [SQLite DB]
 REST API    Audit Log
    │
[Web UI]  [CLI]  [Teams Bot]
```

### 2.2 Assets

| Asset | Classification | Sensitivity |
|---|---|---|
| Audit trail database | Compliance record | High |
| GitLab API token | Credential | High |
| Teams/Azure credentials | Credential | High |
| LLM prompts and responses | Operational | Medium |
| Manufacturing error log entries | Operational | Medium |
| Web UI | Interface | Low |

### 2.3 Threat Actors

| Actor | Motivation | Capability |
|---|---|---|
| Malicious insider | Sabotage, data manipulation | High |
| External attacker (network) | Intellectual property theft | Medium |
| Accidental misuse | Human error | N/A |
| Supply chain compromise | SOUP tampering | Low (mitigated by version pinning) |

---

## 3. Security Controls

### 3.1 Authentication and Authorization

| Control | Implementation | Status |
|---|---|---|
| API Authentication | Deploy behind VPN; add API key middleware before production | Planned |
| GitLab Access | Personal Access Token (PAT) with minimal scope | Implemented |
| Teams Authentication | OAuth 2.0 via MSAL (app registration) | Implemented |
| Web UI Authentication | None (development); OAuth/SSO required for production | Planned |
| Database Access | Local file system permissions; no network-exposed DB | Implemented |

**SEC-CTRL-001:** The FastAPI REST API SHALL be deployed behind a network perimeter (VPN or firewall) for production use. Direct internet exposure is prohibited.

**SEC-CTRL-002:** In production deployments, API key authentication SHALL be added to all non-health endpoints via FastAPI middleware.

### 3.2 Data Protection

| Control | Implementation | Status |
|---|---|---|
| Credentials in env vars | No secrets in source code or config.yaml | Implemented |
| Audit log encryption | Encrypted at rest via OS/filesystem encryption | Site-specific |
| TLS for external APIs | HTTPS enforced via `requests` (verify=True default) | Implemented |
| No PHI processing | Policy and training; Local Llama for sensitive sites | Documented |
| CORS restriction | Restrict `allow_origins` to known hosts in production | Partially (open in dev) |

**SEC-CTRL-003:** All external API calls SHALL use HTTPS with SSL certificate verification enabled.

**SEC-CTRL-004:** Production CORS configuration SHALL restrict `allow_origins` to the specific frontend domain.

### 3.3 Input Validation

| Control | Implementation | Status |
|---|---|---|
| Request validation | Pydantic models on all API endpoints | Implemented |
| SQL injection prevention | Parameterised SQLite queries throughout | Implemented |
| Log entry length limits | 4 KB soft limit in documentation | Documented |
| Prompt injection mitigation | LLM outputs treated as untrusted; JSON parsing with fallback | Implemented |

**SEC-CTRL-005:** All SQL queries in the codebase SHALL use parameterised statements. No string concatenation for SQL.

**SEC-CTRL-006:** LLM outputs SHALL be parsed and validated before use. Raw LLM output SHALL NOT be executed as code.

### 3.4 Audit and Monitoring

| Control | Implementation | Status |
|---|---|---|
| Immutable audit trail | Append-only SQLite; no DELETE methods | Implemented |
| Trace ID for every AI action | UUID v4 on all decisions | Implemented |
| Failed action logging | All errors logged with actor and trace_id | Implemented |
| Teams webhook validation | Webhook payloads logged and audited | Implemented |

**SEC-CTRL-007:** The audit log SHALL be monitored for anomalies (unexpected actors, action types) as part of the weekly operations review.

### 3.5 Software Supply Chain Security

| Control | Implementation | Status |
|---|---|---|
| SOUP version pinning | requirements.txt + package.json with exact versions | Implemented |
| Vulnerability scanning | GitHub Dependabot alerts | Implemented |
| CVE monitoring | Quarterly manual CVE check | Documented |
| Integrity verification | SHA256 checksums of release artefacts | Planned |

**SEC-CTRL-008:** Any SOUP item with a CVE score ≥7.0 SHALL be patched or mitigated within 30 days.

---

## 4. Security Testing

| Test | Frequency | Method |
|---|---|---|
| Dependency vulnerability scan | Every release + monthly | `pip audit`, Dependabot |
| OWASP Top 10 review | Every major release | Code review |
| Input validation testing | Every release | Automated pytest fuzzing |
| SQL injection testing | Every release | Automated (parameterised query audit) |
| Authentication bypass testing | Before production deployment | Manual penetration test |
| Network exposure audit | Before production deployment | Port scan + firewall review |

---

## 5. Incident Response

### 5.1 Security Incident Classification

| Class | Description | Response Time |
|---|---|---|
| P1 — Critical | Audit trail compromise; credential exposure; HITL bypass | Immediate (< 1 hour) |
| P2 — High | Unauthorised API access; data exfiltration | < 4 hours |
| P3 — Medium | Failed authentication attempts; anomalous audit entries | < 24 hours |
| P4 — Low | Non-critical vulnerability discovered | < 7 days |

### 5.2 Incident Response Steps

1. **Detect** — Alert from monitoring, user report, or automated scan
2. **Contain** — Isolate affected system; revoke compromised credentials
3. **Assess** — Determine scope; classify severity
4. **Notify** — QA Manager + Engineering Lead; regulatory body if required (FDA MedWatch if patient harm involved)
5. **Eradicate** — Remove vulnerability; patch and re-deploy
6. **Recover** — Restore from clean backup; verify audit trail integrity
7. **Post-Incident Review** — Root cause analysis; update RISK_MANAGEMENT.md; CAPA if needed

---

## 6. Production Deployment Hardening Checklist

Before any production deployment:

- [ ] API deployed behind VPN or internal network only
- [ ] API key authentication middleware enabled
- [ ] CORS `allow_origins` restricted to specific frontend domain
- [ ] All credentials set via environment variables (not config files)
- [ ] Audit database encrypted at rest (OS-level or filesystem encryption)
- [ ] Backup procedure verified (test restore from backup)
- [ ] GitLab PAT scoped to minimum required permissions
- [ ] Network firewall rules reviewed (ports 8000 and 5173 not exposed externally)
- [ ] Dependency vulnerability scan completed — no critical/high CVEs open
- [ ] Security incident response contacts documented

---

## 7. Security Review Schedule

| Review | Frequency | Owner |
|---|---|---|
| Dependency vulnerability scan | Monthly | Engineering Lead |
| Security control effectiveness review | Quarterly | QA Manager |
| Penetration testing | Annually or before major release | External or internal security team |
| Security plan review | Annually | QA Manager + Engineering Lead |

---

*Document Owner: Quality Assurance Manager*
*Next Review Date: 2026-09-11*
