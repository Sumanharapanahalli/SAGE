# Software Requirements Specification (SRS)
## SAGE[ai] — Autonomous Manufacturing Intelligence System

**Document ID:** SAGE-SRS-001
**Version:** 2.0.0
**Status:** Approved
**Classification:** ISO 13485 Design Control Document
**Date:** 2026-03-11

---

## 1. Introduction

### 1.1 Purpose
This Software Requirements Specification (SRS) defines the functional, non-functional, and interface requirements for **SAGE[ai]**, an autonomous AI-powered developer agent for medical device manufacturing operations. This document serves as the primary input to design and verification activities under the Design History File (DHF).

### 1.2 Scope
SAGE[ai] is a software system that:
- Analyzes manufacturing error logs using AI reasoning
- Proposes corrective actions subject to mandatory human approval
- Automates GitLab merge request creation and AI-assisted code review
- Provides continuous monitoring of Teams, Metabase, and GitLab event sources
- Maintains an immutable compliance audit trail compliant with ISO 13485 and FDA 21 CFR Part 11

**Out of Scope:** SAGE[ai] does not autonomously modify production code, flash firmware to production devices, or create regulatory submissions without human approval gates.

### 1.3 Applicable Standards
| Standard | Applicability |
|---|---|
| ISO 13485:2016 | Quality Management System for Medical Devices |
| ISO 14971:2019 | Risk Management for Medical Devices |
| IEC 62304:2006+AMD1:2015 | Medical Device Software Lifecycle |
| FDA 21 CFR Part 11 | Electronic Records and Electronic Signatures |
| ISO/IEC 25010:2011 | Software Quality Characteristics |

### 1.4 Definitions
| Term | Definition |
|---|---|
| Agent | An AI subsystem that autonomously performs a category of tasks |
| Trace ID | A UUID v4 uniquely identifying every AI-generated decision |
| HITL | Human-in-the-Loop — mandatory human approval gate |
| RAG | Retrieval-Augmented Generation — vector-based context retrieval |
| MR | Merge Request — a GitLab code change proposal |
| SOUP | Software of Unknown Provenance (IEC 62304 §8.1.2) |

---

## 2. System Overview

### 2.1 System Context
SAGE[ai] operates within the following external system context:

```
[Manufacturing Operations]
        │
        ▼
[Error Events] ──► [MonitorAgent] ──► [AnalystAgent] ──► [HITL Gate]
                                                               │
[GitLab Issues] ──► [DeveloperAgent] ──────────────────────► [HITL Gate]
                                                               │
[Teams Channel] ──► [MonitorAgent]                           │
[Metabase Dashboard] ──► [MonitorAgent]              [Approved Actions]
                                                               │
                                                     [Audit Log → DHF]
```

### 2.2 User Classes
| User Class | Description | Interaction Mode |
|---|---|---|
| Manufacturing Engineer | Reviews AI proposals, approves/rejects | Web UI, Teams adaptive cards |
| Software Developer | Creates/reviews MRs, manages pipeline | Web UI, API |
| QA Manager | Reviews audit trail, compliance reports | Web UI (Audit Log) |
| System Administrator | Configures integrations, manages LLM | CLI, config.yaml |

---

## 3. Functional Requirements

### 3.1 Log Analysis (FR-ANAL)

**FR-ANAL-001:** The system SHALL accept a text-based manufacturing error log entry as input through the REST API (`POST /analyze`) or CLI.

**FR-ANAL-002:** The system SHALL use the configured LLM provider to classify the error severity as RED, AMBER, or GREEN.

**FR-ANAL-003:** The system SHALL produce a root cause hypothesis and recommended corrective action for each analyzed log entry.

**FR-ANAL-004:** The system SHALL assign a UUID v4 trace_id to every analysis result.

**FR-ANAL-005:** The system SHALL store the complete input/output of every analysis in the compliance audit log before returning the result to the user.

**FR-ANAL-006:** The system SHALL retrieve contextually relevant past analyses from the vector memory (RAG) and include them in the LLM prompt.

**FR-ANAL-007:** The system SHALL NOT automatically execute any corrective action — all proposals SHALL require explicit human approval (HITL gate).

### 3.2 Human-in-the-Loop Approval (FR-HITL)

**FR-HITL-001:** The system SHALL provide `POST /approve/{trace_id}` to approve a pending proposal.

**FR-HITL-002:** The system SHALL provide `POST /reject/{trace_id}` to reject a proposal with mandatory human feedback text.

**FR-HITL-003:** On rejection, the system SHALL ingest the human feedback into vector memory to improve future analyses.

**FR-HITL-004:** The system SHALL audit every approval and rejection event with actor, timestamp, and trace_id.

**FR-HITL-005:** The system SHALL NOT execute any proposal that has not received an explicit approval event in the audit log.

### 3.3 Merge Request Automation (FR-MR)

**FR-MR-001:** The system SHALL accept a GitLab project_id and issue_iid and create a corresponding Merge Request using the GitLab REST API v4.

**FR-MR-002:** The system SHALL use the LLM to generate the MR title and description based on the issue content.

**FR-MR-003:** The system SHALL review a GitLab MR diff using a multi-step ReAct reasoning loop that includes pipeline status checking.

**FR-MR-004:** The MR review output SHALL include: summary, issues list, suggestions list, and an approved boolean.

**FR-MR-005:** The system SHALL list open MRs for a given project (`GET /mr/open`).

**FR-MR-006:** The system SHALL return CI/CD pipeline status for a given MR (`GET /mr/pipeline`).

**FR-MR-007:** The system SHALL post the AI code review as a comment on the GitLab MR.

### 3.4 Monitoring (FR-MON)

**FR-MON-001:** The system SHALL poll Microsoft Teams channels for manufacturing error keywords at configurable intervals.

**FR-MON-002:** The system SHALL poll Metabase error dashboards for new error records at configurable intervals.

**FR-MON-003:** The system SHALL poll GitLab for issues labelled `sage-ai` at configurable intervals.

**FR-MON-004:** The system SHALL dispatch detected events to registered callback handlers asynchronously.

**FR-MON-005:** The system SHALL expose monitor thread status via `GET /monitor/status`.

**FR-MON-006:** Each monitor polling thread SHALL be independently configurable and independently restartable.

### 3.5 Audit Trail (FR-AUDIT)

**FR-AUDIT-001:** The system SHALL log every AI decision, human action, and system event to an append-only SQLite database.

**FR-AUDIT-002:** The audit log SHALL record: id (UUID), timestamp (UTC), actor, action_type, input_context, output_content, metadata (JSON), verification_signature.

**FR-AUDIT-003:** The system SHALL NOT delete or modify audit log records.

**FR-AUDIT-004:** The system SHALL expose the audit log via `GET /audit` with pagination support.

**FR-AUDIT-005:** The audit log SHALL be retained for a minimum period consistent with the device classification (see RISK_MANAGEMENT.md §7).

### 3.6 Task Queue (FR-QUEUE)

**FR-QUEUE-001:** The system SHALL serialize all AI agent tasks through a single-lane priority queue.

**FR-QUEUE-002:** The task queue SHALL persist pending and in-progress tasks to SQLite and restore them on process restart.

**FR-QUEUE-003:** The system SHALL track task status: PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED.

**FR-QUEUE-004:** No two AI tasks SHALL execute concurrently (single-lane compliance constraint).

### 3.7 Planner Agent (FR-PLAN)

**FR-PLAN-001:** The system SHALL accept a high-level natural-language task description and decompose it into ordered subtasks using the LLM.

**FR-PLAN-002:** The Planner SHALL only emit subtask types that are in the set of supported task types.

**FR-PLAN-003:** All planning decisions SHALL be recorded in the audit log.

### 3.8 Web Interface (FR-WEB)

**FR-WEB-001:** The system SHALL provide a browser-based UI accessible at `http://localhost:5173` during development.

**FR-WEB-002:** The web UI SHALL display a Dashboard, Analyst, Developer, Audit Log, and Monitor pages.

**FR-WEB-003:** The web UI SHALL auto-refresh live data every 30 seconds using polling.

**FR-WEB-004:** The web UI SHALL allow submission of log entries and display analysis proposals with approve/reject controls.

**FR-WEB-005:** The web UI SHALL display the paginated audit log with row-level trace detail.

**FR-WEB-006:** The web UI SHALL allow export of audit log entries to CSV.

---

## 4. Non-Functional Requirements

### 4.1 Performance (NFR-PERF)

**NFR-PERF-001:** Log analysis SHALL complete within 60 seconds for entries up to 4 KB.

**NFR-PERF-002:** MR review (ReAct loop, max 5 steps) SHALL complete within 120 seconds.

**NFR-PERF-003:** REST API endpoints SHALL respond within 2 seconds for non-LLM operations (health, audit query, status).

**NFR-PERF-004:** The web UI SHALL load initial page within 3 seconds on a LAN connection.

### 4.2 Reliability (NFR-REL)

**NFR-REL-001:** The task queue SHALL survive process restart without loss of pending tasks.

**NFR-REL-002:** The system SHALL degrade gracefully when external integrations (GitLab, Metabase) are unavailable, returning structured error responses rather than crashing.

**NFR-REL-003:** The LLM gateway SHALL operate with a single active provider at a time; switching providers requires configuration change and process restart.

### 4.3 Security (NFR-SEC)

**NFR-SEC-001:** All API credentials SHALL be stored as environment variables, not in source code or config files committed to version control.

**NFR-SEC-002:** The FastAPI REST API SHALL validate all request payloads using Pydantic models before processing.

**NFR-SEC-003:** The system SHALL NOT expose raw database connection strings or LLM prompts in API responses.

**NFR-SEC-004:** CORS shall be configurable; production deployments SHALL restrict `allow_origins` to known frontend hosts.

### 4.4 Traceability (NFR-TRACE)

**NFR-TRACE-001:** Every AI output SHALL be traceable to its input via trace_id in the audit log.

**NFR-TRACE-002:** Every human approval or rejection SHALL reference the trace_id of the proposal it acts upon.

**NFR-TRACE-003:** The audit log SHALL record the LLM provider name and version for each decision.

### 4.5 Maintainability (NFR-MAINT)

**NFR-MAINT-001:** The system SHALL support pluggable LLM providers via the abstract LLMProvider interface.

**NFR-MAINT-002:** All agent configuration SHALL be centralised in `config/config.yaml` with environment variable overrides.

---

## 5. Interface Requirements

### 5.1 REST API Interface

| Method | Path | Purpose |
|---|---|---|
| GET | /health | System health and provider info |
| POST | /analyze | Analyze log entry |
| POST | /approve/{trace_id} | Approve proposal |
| POST | /reject/{trace_id} | Reject with feedback |
| GET | /audit | Query audit log |
| POST | /mr/create | Create GitLab MR |
| POST | /mr/review | AI review MR (ReAct) |
| GET | /mr/open | List open MRs |
| GET | /mr/pipeline | Pipeline status |
| GET | /monitor/status | Monitor thread status |
| POST | /webhook/teams | Teams webhook receiver |

### 5.2 External System Interfaces

| System | Interface Type | Protocol | Auth |
|---|---|---|---|
| GitLab | REST API v4 | HTTPS | Private-Token header |
| Microsoft Teams | Incoming Webhook | HTTPS POST | Webhook URL |
| Teams Graph API | REST API | HTTPS | OAuth 2.0 (MSAL) |
| Metabase | REST API | HTTPS | Session token |
| SpiraTeam | REST API | HTTPS | API key |
| J-Link Debugger | USB/SWD | Local | N/A |
| Serial Port | UART | Local | N/A |

---

## 6. Constraints

- The system SHALL operate on a single compute node (no distributed processing).
- Maximum concurrent AI tasks: 1 (single-lane queue, by design).
- Supported LLM providers: Gemini CLI (cloud) or Local Llama (air-gapped).
- The system SHALL NOT support automatic production deployments without explicit human approval.

---

## 7. Traceability

See `docs/regulatory/RTM.md` for the full Requirements Traceability Matrix linking each requirement to its design element, test case, and verification record.

---

*Document Owner: Systems Engineering Team*
*Next Review Date: 2026-09-11*
