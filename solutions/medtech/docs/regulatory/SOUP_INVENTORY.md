# SOUP Inventory
## SAGE[ai] — Software of Unknown Provenance
### IEC 62304:2006+AMD1:2015 §8.1.2

**Document ID:** SAGE-SOUP-001
**Version:** 2.0.0
**Status:** Approved
**Date:** 2026-03-11

---

## 1. Introduction

This document identifies all Software of Unknown Provenance (SOUP) components used by SAGE[ai] in accordance with **IEC 62304:2006+AMD1:2015 §8.1.2**. SOUP is defined as software items that were not developed with a quality system appropriate for medical device software and are used without modification.

For each SOUP item this inventory records:
- Identification (name, version, source)
- Functional purpose in the system
- Potential anomalies or known risks
- Verification and monitoring approach

---

## 2. SOUP Classification

All SOUP items in this inventory are classified as **Class B** software per IEC 62304 §4.3 (software whose failure can result in unacceptable risk to the patient after mitigation). The SAGE[ai] system as a whole is classified Class B because it supports medical device manufacturing operations indirectly; it does not directly control a medical device.

---

## 3. Python Runtime SOUP

### SOUP-PY-001: Python Interpreter

| Field | Value |
|---|---|
| **Name** | CPython |
| **Version** | 3.11.x |
| **Source** | python.org |
| **License** | PSF License |
| **Purpose** | Runtime environment for all SAGE[ai] Python code |
| **Known Anomalies** | Refer to Python CVE database; actively maintained |
| **Verification** | Version pinned in SETUP.md; `python --version` check in IQ tests |
| **Update Monitoring** | python.org security announcements |

---

## 4. Core Python Packages

### SOUP-PY-002: FastAPI

| Field | Value |
|---|---|
| **Name** | fastapi |
| **Version** | ≥0.109.0 |
| **Source** | PyPI (tiangolo/fastapi) |
| **License** | MIT |
| **Purpose** | REST API framework for all HTTP endpoints |
| **Known Anomalies** | No safety-critical anomalies identified |
| **Verification** | API endpoint tests in test_api.py |
| **Update Monitoring** | GitHub releases; PyPI |

### SOUP-PY-003: Uvicorn

| Field | Value |
|---|---|
| **Name** | uvicorn |
| **Version** | ≥0.27.0 |
| **Source** | PyPI |
| **License** | BSD |
| **Purpose** | ASGI server for FastAPI |
| **Known Anomalies** | None identified |
| **Verification** | Integration tests via HTTP requests |

### SOUP-PY-004: Pydantic

| Field | Value |
|---|---|
| **Name** | pydantic |
| **Version** | ≥2.5.0 |
| **Source** | PyPI |
| **License** | MIT |
| **Purpose** | Request/response model validation for API |
| **Known Anomalies** | None affecting safety |
| **Verification** | Unit tests for model validation |

### SOUP-PY-005: PyYAML

| Field | Value |
|---|---|
| **Name** | pyyaml |
| **Version** | ≥6.0 |
| **Source** | PyPI |
| **License** | MIT |
| **Purpose** | Configuration file parsing (config/config.yaml) |
| **Known Anomalies** | yaml.safe_load() used; yaml.load() not used |
| **Verification** | Config loading tests |

### SOUP-PY-006: Requests

| Field | Value |
|---|---|
| **Name** | requests |
| **Version** | ≥2.31.0 |
| **Source** | PyPI |
| **License** | Apache 2.0 |
| **Purpose** | HTTP client for GitLab, Metabase, SpiraTeam REST APIs |
| **Known Anomalies** | SSL verification enabled by default |
| **Verification** | Integration tests with mock HTTP server |

### SOUP-PY-007: httpx

| Field | Value |
|---|---|
| **Name** | httpx |
| **Version** | ≥0.26.0 |
| **Source** | PyPI |
| **License** | BSD |
| **Purpose** | Async HTTP client (FastAPI test client) |
| **Known Anomalies** | None identified |
| **Verification** | Used in test fixtures |

---

## 5. AI / LLM SOUP

### SOUP-AI-001: LangChain

| Field | Value |
|---|---|
| **Name** | langchain, langchain-community, langchain-chroma |
| **Version** | ≥0.1.0 |
| **Source** | PyPI (langchain-ai/langchain) |
| **License** | MIT |
| **Purpose** | LLM chaining primitives; ChromaDB integration |
| **Known Anomalies** | Rapid release cadence; API breaking changes possible |
| **Verification** | Version pinned in requirements.txt; regression tests after updates |
| **Update Monitoring** | GitHub releases; changelog review before upgrade |

### SOUP-AI-002: ChromaDB

| Field | Value |
|---|---|
| **Name** | chromadb |
| **Version** | ≥0.4.0 |
| **Source** | PyPI (chroma-core/chroma) |
| **License** | Apache 2.0 |
| **Purpose** | Vector database for RAG episodic memory |
| **Known Anomalies** | In-memory fallback implemented if unavailable |
| **Verification** | Vector store tests; fallback path tested |

### SOUP-AI-003: Sentence Transformers

| Field | Value |
|---|---|
| **Name** | sentence-transformers |
| **Version** | ≥2.3.0 |
| **Source** | PyPI (UKPLab/sentence-transformers) |
| **License** | Apache 2.0 |
| **Purpose** | Embedding model (all-MiniLM-L6-v2) for vector search |
| **Known Anomalies** | Model files are not audited for safety-critical use; used only for similarity search, not for decision-making |
| **Verification** | Embedding quality validated against known test cases |

### SOUP-AI-004: llama-cpp-python (optional)

| Field | Value |
|---|---|
| **Name** | llama-cpp-python |
| **Version** | ≥0.2.0 |
| **Source** | PyPI (abetlen/llama-cpp-python) |
| **License** | MIT |
| **Purpose** | Local Llama GGUF model inference (air-gapped mode) |
| **Known Anomalies** | GPU/CPU inference results may vary by hardware |
| **Verification** | Output validated against known test prompts; HITL gate mitigates inference errors |
| **Note** | Optional SOUP — only active when `llm.provider: local` |

---

## 6. Hardware Interface SOUP

### SOUP-HW-001: pyserial

| Field | Value |
|---|---|
| **Name** | pyserial |
| **Version** | ≥3.5 |
| **Source** | PyPI |
| **License** | BSD |
| **Purpose** | Serial/COM port communication via MCP server |
| **Known Anomalies** | None identified; read/write operations are explicit |
| **Verification** | Serial port MCP server tests |

### SOUP-HW-002: pylink-square

| Field | Value |
|---|---|
| **Name** | pylink-square |
| **Version** | ≥1.0.0 |
| **Source** | PyPI (square/pylink) |
| **License** | Apache 2.0 |
| **Purpose** | J-Link JTAG/SWD debugger interface for firmware flashing |
| **Known Anomalies** | Hardware-dependent; tested on SEGGER J-Link EDU and Pro |
| **Verification** | J-Link MCP server tests; hardware-in-the-loop tests |
| **Safety Note** | Firmware flash operations require human approval (HITL gate) |

---

## 7. Microsoft Integration SOUP

### SOUP-MS-001: MSAL (Microsoft Authentication Library)

| Field | Value |
|---|---|
| **Name** | msal |
| **Version** | ≥1.26.0 |
| **Source** | PyPI (AzureAD/microsoft-authentication-library-for-python) |
| **License** | MIT |
| **Purpose** | OAuth 2.0 authentication for Teams Graph API |
| **Known Anomalies** | Token caching; credentials in environment variables only |
| **Verification** | Authentication integration tests |

---

## 8. MCP Framework SOUP

### SOUP-MCP-001: FastMCP

| Field | Value |
|---|---|
| **Name** | fastmcp |
| **Version** | ≥0.1.0 |
| **Source** | PyPI |
| **License** | MIT |
| **Purpose** | Model Context Protocol server framework for tool integration |
| **Known Anomalies** | Pre-1.0 release; API may change |
| **Verification** | MCP server tests in tests/mcp/ |

---

## 9. Frontend SOUP (Web UI)

| Package | Version | License | Purpose |
|---|---|---|---|
| React | 18.2.x | MIT | UI component framework |
| React DOM | 18.2.x | MIT | DOM rendering |
| React Router DOM | 6.x | MIT | Client-side routing |
| TanStack Query | 5.x | MIT | Server state management / polling |
| Recharts | 2.x | MIT | Data visualisation (error trend chart) |
| Lucide React | 0.303.x | ISC | Icon library |
| Vite | 5.x | MIT | Build tool and dev server |
| TypeScript | 5.x | Apache 2.0 | Type-safe JavaScript |
| Tailwind CSS | 3.x | MIT | Utility-first CSS framework |
| clsx | 2.x | MIT | Conditional class name utility |
| tailwind-merge | 2.x | MIT | Tailwind class merging |

---

## 10. SOUP Anomaly Monitoring

SOUP items are monitored for reported anomalies through:

1. **GitHub Dependabot** alerts on the repository
2. **CVE database** checks (quarterly) for packages listed above
3. **Changelog review** before any SOUP version upgrade
4. **Regression testing** after any SOUP version change

Any anomaly with a CVSS score ≥7.0 affecting a SOUP item used in a safety-critical path SHALL trigger a risk management review (§3 of RISK_MANAGEMENT.md).

---

## 11. SOUP Version Pinning

All Python SOUP versions are specified in `requirements.txt`. All Node.js SOUP versions are specified in `web/package.json`. Version changes require:
1. Change control record (see CHANGE_CONTROL.md)
2. Re-execution of affected verification tests
3. Update to this SOUP Inventory

---

*Document Owner: Systems Engineering Team*
*Next Review Date: 2026-09-11*
