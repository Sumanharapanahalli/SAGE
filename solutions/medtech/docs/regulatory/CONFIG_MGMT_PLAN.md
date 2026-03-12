# Configuration Management Plan
## SAGE[ai] — Autonomous Manufacturing Intelligence System

**Document ID:** SAGE-CMP-001
**Version:** 2.0.0
**Status:** Approved
**Date:** 2026-03-11

---

## 1. Purpose

This Configuration Management Plan (CMP) defines how SAGE[ai] software, documentation, and data artefacts are identified, controlled, tracked, and maintained throughout the software lifecycle, in accordance with:
- **IEC 62304:2006+AMD1:2015 §8** — Software Configuration Management
- **ISO 13485:2016 §7.5.8** — Traceability

---

## 2. Configuration Items

| CI ID | Item | Location | Controlled By |
|---|---|---|---|
| CI-001 | Source code | `src/`, `mcp_servers/`, `web/src/` | Git |
| CI-002 | Configuration file | `config/config.yaml` | Git (template only; secrets via env vars) |
| CI-003 | DHF documents | `docs/regulatory/` | Git |
| CI-004 | Test suite | `tests/` | Git |
| CI-005 | Requirements (Python) | `requirements.txt` | Git |
| CI-006 | Requirements (Node.js) | `web/package.json` | Git |
| CI-007 | Audit trail database | `data/audit_log.db` | File system backup |
| CI-008 | Vector store | `data/chroma_db/` | File system backup |
| CI-009 | LLM model file (if local) | Configurable path | File system backup |
| CI-010 | Release artefacts | GitLab releases | GitLab |

---

## 3. Version Control

### 3.1 Git Repository

**Repository URL:** Configured in `config/config.yaml` → `gitlab.url`

**Branch Strategy:**

| Branch | Purpose | Merge Restrictions |
|---|---|---|
| `main` | Production-ready code | Protected; requires ≥1 approval + CI pass |
| `develop` | Integration branch | Requires ≥1 approval |
| `sage-ai/{iid}-{slug}` | SAGE[ai] auto-created feature branches | Standard MR process |
| `hotfix/{description}` | Emergency fixes | Fast-track; QA approval required |
| `release/{version}` | Release preparation | QA and Engineering Lead approval |

### 3.2 Commit Standards

All commits to controlled branches shall:
- Reference the GitLab issue or CR number (e.g., `Fixes #42`)
- Include a descriptive commit message following Conventional Commits format
- Pass all CI/CD pipeline checks

### 3.3 Tagging

Each release SHALL be tagged in Git using the format `v{MAJOR}.{MINOR}.{PATCH}` (e.g., `v2.0.0`). Tags are protected and require QA sign-off.

---

## 4. Build and Release Management

### 4.1 Reproducible Builds

Python dependencies are pinned in `requirements.txt` with exact versions. Node.js dependencies are managed via `package.json` with `package-lock.json` committed to the repository.

### 4.2 Release Procedure

1. All tests pass in CI/CD pipeline on `develop`
2. Release branch created: `release/2.0.0`
3. Version bumped in all relevant files
4. Final test execution; Test Report (SAGE-TR-001) completed
5. QA Manager approves release
6. Merge to `main` and tag `v2.0.0`
7. GitLab Release created with:
   - Tag reference
   - Changelog summary
   - Test report artifact
   - SHA256 checksums of release artefacts

### 4.3 Release Artefacts

| Artefact | Description | Storage |
|---|---|---|
| Source archive | Git tag tarball | GitLab releases |
| Test report | HTML report from pytest | GitLab CI artifacts |
| Coverage report | HTML coverage report | GitLab CI artifacts |
| Requirements snapshot | `pip freeze` output | GitLab releases |
| Docker image (future) | Containerised deployment | Container registry |

---

## 5. Database Backup

### 5.1 Audit Log Database (`data/audit_log.db`)

| Parameter | Value |
|---|---|
| Backup frequency | Daily (automated) + before each release |
| Retention period | 15 years (Class III medical device) |
| Backup location | Encrypted network storage (site-specific) |
| Backup verification | Monthly restore test |
| Backup format | SQLite copy + SQL dump |

### 5.2 Vector Store (`data/chroma_db/`)

| Parameter | Value |
|---|---|
| Backup frequency | Weekly |
| Retention period | 2 years (operational data) |
| Recovery procedure | Restore from backup; RAG accuracy validated post-restore |

### 5.3 Database Integrity Verification

Before each backup:
```bash
sqlite3 data/audit_log.db "PRAGMA integrity_check"
```
Expected output: `ok`

If integrity check fails, this constitutes a **Critical** event requiring immediate QA notification.

---

## 6. Environment Configuration

### 6.1 Configuration File (`config/config.yaml`)

The configuration file is version-controlled with placeholder values for all secrets:
```yaml
gitlab:
  token: "${GITLAB_TOKEN}"  # Set via environment variable
```

Real values are NEVER committed to the repository.

### 6.2 Secrets Management

| Secret | Mechanism | Rotation Frequency |
|---|---|---|
| GITLAB_TOKEN | Environment variable / CI/CD secret | On personnel change or annually |
| TEAMS_CLIENT_SECRET | Environment variable | On personnel change or annually |
| METABASE_PASSWORD | Environment variable | Annually |
| SPIRA_API_KEY | Environment variable | Annually |

### 6.3 Environment Tiers

| Tier | Purpose | DB | LLM Provider |
|---|---|---|---|
| Development | Developer workstations | Separate `data/dev_audit.db` | Local Llama or Gemini CLI |
| Test | CI/CD pipeline | In-memory SQLite (mocked) | Mock LLM |
| Production | Manufacturing operations | `data/audit_log.db` | Configured per deployment |

---

## 7. Problem Reporting and Tracking

All software problems are tracked as GitLab issues with the following labels:
- `bug` — Software defects
- `compliance` — Compliance/regulatory concerns
- `sage-ai` — Issues for SAGE[ai] to auto-analyse
- `capa` — Corrective and Preventive Actions

Problem severity classification follows the Risk Management Report (SAGE-RM-001) severity scale.

---

## 8. Configuration Management Audit

A configuration management audit shall be conducted:
- Before each formal software release
- Annually as part of the QMS management review
- Following any significant infrastructure change

The audit verifies:
- All configuration items are under version control
- Release artefacts match the tagged source code
- Secrets are not in version control
- Backup procedures are being followed

---

*Document Owner: Systems Engineering Team*
*Next Review Date: 2026-09-11*
