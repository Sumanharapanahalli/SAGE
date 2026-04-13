# Phase 7 Evolution UI + Documentation Design

## Overview

**Goal:** Integrate genetic algorithm evolution monitoring and controls into SAGE's existing React dashboard with comprehensive documentation for regulated industry compliance.

**Architecture:** Enhance existing approval queue with evolution-specific proposal cards, add dedicated Evolution Control Center page, and extend REST API with evolution endpoints. Evolution candidates flow seamlessly into existing approval workflow maintaining HITL compliance.

**Tech Stack:** React 18 + TypeScript + Vite (frontend), FastAPI + Python (backend), existing SQLite audit trail integration

---

## Core Components

### 1. Evolution-Integrated Approval Queue

**Enhancement:** Extend existing `web/src/pages/Approvals.tsx` with specialized evolution proposal cards.

**Evolution Proposal Card Features:**
- **Evolution Metadata Panel**: Generation number, fitness score (0.0-1.0), mutation type (crossover/mutation), parent candidate IDs
- **Risk Assessment Badge**: Evolution-specific risk levels (EXPERIMENTAL, VALIDATED, REGRESSION) with regulatory color coding
- **Mutation Details**: Specific changes with diff highlighting (prompt segment, code function, build step)
- **Fitness Context**: Evaluator breakdown showing individual scores (TestDriven: 0.85, Semantic: 0.72, Integration: 0.91)
- **Evolution Timeline**: Mini-timeline showing candidate lineage within current generation
- **Regulatory Context**: FDA classification, intended purpose validation status, automation bias controls

**Approval Flow Integration:**
- New proposal type: `evolution_candidate` alongside existing `yaml_edit`, `code_diff`, etc.
- Same approve/reject buttons with evolution-enhanced feedback
- Reject categories: Poor Fitness, Risky Mutation, Premature Convergence, Regulatory Concern
- Feedback automatically feeds evolution algorithm for continuous improvement

**Audit Trail Compliance:**
- All evolution decisions logged with full context (generation ID, mutation type, fitness scores)
- Regulatory metadata captured for FDA/IEC 62304 submissions
- Traceability matrix integration for medical device compliance

### 2. Evolution Control Center

**New Page:** `web/src/pages/Evolution.tsx` - Dedicated dashboard for evolution experiment management.

**Live Experiment Dashboard:**
- Real-time generation progress with population health metrics
- Fitness trend charts showing convergence patterns
- Population diversity indicators and early warning alerts
- Active experiment list with status (Running, Paused, Complete, Failed)

**Parameter Configuration Panel:**
- Population size, mutation rate, crossover probability sliders
- Evaluator weight configuration (test-driven vs semantic vs integration)
- Evolution strategy selection (tournament, roulette, rank-based)
- Termination criteria (max generations, fitness threshold, stagnation limit)

**Experiment Controls:**
- Start new experiment with solution validation
- Pause/resume with state preservation
- Emergency stop with safety confirmations
- Clone experiment with modified parameters

**Compliance Reporting:**
- Downloadable PDF reports for regulatory submissions
- Evolution audit trails with human approval decisions
- Performance metrics and safety validation results
- Integration with existing SAGE compliance framework

### 3. API Extensions

**New REST Endpoints in `src/interface/api.py`:**

**Experiment Management:**
- `POST /evolution/experiments` - Start new evolution experiment
- `GET /evolution/experiments` - List all experiments with status
- `GET /evolution/experiments/{id}` - Get experiment details and history
- `PUT /evolution/experiments/{id}` - Update experiment parameters
- `DELETE /evolution/experiments/{id}` - Stop and cleanup experiment

**Real-time Monitoring:**
- `GET /evolution/experiments/{id}/status` - Live experiment status and metrics
- `GET /evolution/experiments/{id}/candidates` - Current generation candidates
- `GET /evolution/experiments/{id}/history` - Generation-by-generation history
- `GET /evolution/experiments/{id}/fitness` - Fitness trends and convergence data

**Proposal Integration:**
- `GET /evolution/candidates/pending` - Evolution proposals in approval queue
- `POST /evolution/candidates/{id}/approve` - Approve evolution candidate
- `POST /evolution/candidates/{id}/reject` - Reject with structured feedback

**Compliance & Reporting:**
- `GET /evolution/experiments/{id}/report` - Generate compliance report
- `GET /evolution/audit` - Evolution audit trail for regulatory submissions
- `GET /evolution/metrics` - System-wide evolution performance analytics

### 4. Documentation Hub

**Comprehensive Documentation Structure:**

**User Guides (`docs/evolution/`):**
- `getting-started.md` - Quick start guide for first evolution experiment
- `approval-workflow.md` - How to review and approve evolution candidates
- `parameter-tuning.md` - Optimization strategies for different domains
- `troubleshooting.md` - Common issues and diagnostic procedures

**Regulatory Compliance (`docs/evolution/compliance/`):**
- `fda-validation.md` - FDA clinical decision support validation procedures
- `iec-62304-integration.md` - Medical device software compliance patterns
- `audit-trail-guide.md` - Maintaining traceable evolution decisions
- `risk-assessment.md` - Evolution-specific risk classification procedures

**Technical Integration (`docs/evolution/integration/`):**
- `api-reference.md` - Complete REST API documentation
- `custom-evaluators.md` - Building domain-specific fitness functions
- `mutation-strategies.md` - Customizing genetic operators for specific domains
- `monitoring-setup.md` - Configuring evolution health monitoring

**Regulatory Templates (`docs/evolution/templates/`):**
- `validation-plan-template.md` - FDA validation plan for evolutionary AI
- `risk-analysis-template.md` - Risk analysis for genetic algorithm deployment
- `traceability-matrix-template.md` - Requirement traceability for evolved systems

---

## Data Flow Architecture

### Evolution Candidate Pipeline

1. **Generation:** Evolution algorithms create candidate solutions (prompts, code, builds)
2. **Evaluation:** Ensemble evaluators score candidates with fitness metrics
3. **Proposal Creation:** High-fitness candidates automatically become approval proposals
4. **Queue Integration:** Proposals appear in existing approval queue with evolution metadata
5. **Human Decision:** Regulatory-trained users approve/reject with structured feedback
6. **Algorithm Feedback:** Rejection reasons feed back to evolution parameters
7. **Audit Capture:** All decisions logged for regulatory compliance

### Real-time Monitoring Flow

1. **Evolution Engine:** Orchestrator runs generation cycles with population management
2. **Metrics Collection:** Fitness scores, diversity metrics, convergence indicators collected
3. **WebSocket Updates:** Real-time metrics streamed to Evolution Control Center
4. **Alert System:** Early warnings for stuck evolution, poor fitness, regulatory violations
5. **Compliance Logging:** Continuous audit trail for regulatory oversight

---

## Regulatory Integration

### FDA Clinical Decision Support (CDS) Compliance

- **Four-Criterion Classification:** Automatic FDA class determination for evolved clinical tools
- **Intended Purpose Validation:** Evolved systems maintain validated intended purpose constraints
- **Transparency Reporting:** Evolution decisions captured in regulatory-compliant audit format
- **Automation Bias Controls:** Time-critical tasks require enhanced human oversight during evolution

### IEC 62304 Medical Device Software

- **Traceability Matrix:** Evolution decisions linked to original software requirements
- **Risk Classification:** Evolution candidates automatically assessed for safety classification
- **Change Control:** All evolutionary changes follow medical device change control procedures
- **Verification Evidence:** Automated test results provide verification evidence for evolved code

### 21 CFR Part 11 Electronic Records

- **Electronic Signatures:** Evolution approvals support electronic signature compliance
- **Audit Trails:** Immutable audit trail for all evolution decisions and system changes
- **Access Controls:** Role-based access to evolution experiments and approval decisions
- **Data Integrity:** Cryptographic hashes ensure evolution data integrity

---

## User Experience Design

### Evolution Proposal Card Layout

```
┌─────────────────────────────────────────────────────────────┐
│ EVOLUTION CANDIDATE                            [EXPERIMENTAL] │
│ Generation 15 • Fitness: 0.87 • Crossover Mutation          │
├─────────────────────────────────────────────────────────────┤
│ Evaluator Scores:                                           │
│ ● Test-Driven: 0.91  ● Semantic: 0.85  ● Integration: 0.84  │
│                                                             │
│ Changes:                                                    │
│ + Enhanced error handling in user authentication           │
│ ~ Modified database connection retry logic                 │
│ - Removed deprecated API endpoint validation               │
│                                                             │
│ Parent: Candidate #247 (Gen 14) → Mutation → This          │
│                                                             │
│ [APPROVE] [REJECT ▼]                                        │
└─────────────────────────────────────────────────────────────┘
```

### Evolution Control Center Dashboard

```
┌─────────────────┬───────────────────────────────────────────┐
│ Experiment List │ Live Metrics                              │
│                 │                                           │
│ ● Running (2)   │ Generation: 18/50                        │
│ ● Paused (1)    │ Best Fitness: 0.91                       │
│ ● Complete (5)  │ Population Health: Diverse               │
│                 │ Convergence: Improving                   │
│ [START NEW]     │                                           │
├─────────────────┼───────────────────────────────────────────┤
│ Parameters      │ Fitness Trends                           │
│                 │                                           │
│ Population: 50  │    0.9 ┤                                  │
│ Mutation: 0.1   │    0.8 ┤  ∙∙∙∙∙∙∙∙∙∙∙∙∙∙∙∙∙∙             │
│ Crossover: 0.7  │    0.7 ┤     ∙∙∙∙∙∙∙∙                    │
│                 │    0.6 └─────────────────────────         │
│ [CONFIGURE]     │          5   10   15   Generation         │
└─────────────────┴───────────────────────────────────────────┘
```

---

## Implementation Strategy

### Phase 7A: Core UI Components
1. **Evolution proposal cards** - Enhanced approval queue with evolution metadata
2. **Basic evolution controls** - Start/stop experiment functionality  
3. **API integration** - REST endpoints for experiment management
4. **Real-time updates** - WebSocket integration for live metrics

### Phase 7B: Advanced Monitoring
1. **Fitness visualization** - Trend charts and convergence analysis
2. **Population health metrics** - Diversity indicators and early warnings
3. **Experiment history** - Generation-by-generation detailed views
4. **Performance analytics** - Success rate analysis and optimization insights

### Phase 7C: Regulatory Documentation
1. **User guides** - Getting started and workflow documentation
2. **Compliance guides** - FDA, IEC 62304, 21 CFR Part 11 integration
3. **API documentation** - Complete REST API reference
4. **Regulatory templates** - Validation plans and risk analysis templates

### Testing Strategy

**Unit Tests:**
- Evolution proposal card rendering with mock data
- API endpoint validation with comprehensive edge cases
- Evolution metrics calculation accuracy
- Regulatory compliance data capture

**Integration Tests:**
- End-to-end evolution experiment workflow
- Approval queue integration with existing system
- Real-time metric streaming and WebSocket handling
- Cross-browser compatibility and responsive design

**Regulatory Validation Tests:**
- FDA CDS classification accuracy for evolved candidates
- Audit trail completeness and integrity verification
- Electronic signature compliance for evolution approvals
- Traceability matrix integrity across evolution cycles

**User Acceptance Tests:**
- Evolution experiment creation and monitoring workflow
- Approval decision workflow with evolution metadata
- Compliance report generation and regulatory submission format
- Performance under realistic evolution workloads

---

## Success Criteria

### Functional Requirements
- ✅ Evolution candidates appear seamlessly in existing approval queue
- ✅ Real-time monitoring shows experiment progress and health metrics
- ✅ Users can start, pause, and configure evolution experiments safely
- ✅ Comprehensive documentation supports regulated industry deployment

### Regulatory Requirements  
- ✅ All evolution decisions captured in FDA-compliant audit trail
- ✅ Evolution candidates include regulatory risk assessment
- ✅ Compliance reports generate automatically for regulatory submissions
- ✅ Electronic signature support for evolution approvals

### Performance Requirements
- ✅ Evolution monitoring UI responsive under 500ms for live updates
- ✅ Approval queue handles 100+ evolution candidates without degradation
- ✅ Real-time metrics stream without blocking experiment execution
- ✅ Compliance report generation completes within 30 seconds

### Usability Requirements
- ✅ Existing SAGE users can use evolution features without training
- ✅ Evolution metadata clearly explains changes and fitness rationale
- ✅ Error messages provide actionable guidance for failed experiments
- ✅ Documentation enables self-service deployment for new domains

---

## Risk Mitigation

### Technical Risks
- **WebSocket Connection Issues:** Graceful fallback to polling for real-time updates
- **Evolution State Corruption:** Checkpoint system with automatic recovery
- **UI Performance Degradation:** Virtualized lists and pagination for large datasets
- **API Rate Limiting:** Client-side throttling and retry logic with exponential backoff

### Regulatory Risks  
- **Audit Trail Gaps:** Comprehensive logging at every decision point with integrity checks
- **Compliance Documentation Gaps:** Template validation and completeness verification
- **Electronic Signature Issues:** Fallback to paper-based approval with digital audit
- **Evolution Approval Bypass:** Hard-coded HITL gates with no override capability

### User Experience Risks
- **Complex Evolution Terminology:** Plain-language explanations and guided workflows
- **Overwhelming Approval Queue:** Smart filtering and prioritization algorithms
- **Configuration Complexity:** Sensible defaults and guided parameter selection
- **Integration Learning Curve:** Progressive disclosure and contextual help system