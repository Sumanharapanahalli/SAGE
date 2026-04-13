# FDA Validation Procedures for SAGE Evolution

## Regulatory Framework

SAGE Evolution operates under FDA guidance for AI/ML-enabled medical device software, specifically FDA's "Clinical Decision Support Software: Guidance for Industry and Food and Drug Administration Staff" and "Software as Medical Device (SaMD): Clinical Evaluation."

### Applicable Regulations

**21 CFR Part 820 (Quality System Regulation)**
- Design controls for medical device software
- Risk management and validation requirements
- Configuration management and change control

**21 CFR Part 11 (Electronic Records and Electronic Signatures)**  
- Electronic record integrity and audit trails
- Electronic signature requirements and access controls
- System validation and security measures

**ISO 14155 (Clinical Investigation of Medical Devices)**
- Clinical evaluation requirements for AI/ML systems
- Risk-based validation approaches
- Post-market surveillance obligations

## Four-Criterion FDA CDS Classification

SAGE Evolution automatically evaluates all candidates against the FDA's 4-criterion test to determine regulatory classification and validation requirements.

### Criterion 1: Medical Image/Physiological Signal Analysis

**Assessment Question**: Does the evolved component analyze medical images, radiologic images, or physiological signals?

**Classification Impact**:
- **Pass** (No image/signal analysis): Supports Non-Device CDS classification
- **Fail** (Analyzes images/signals): Triggers Device CDS classification and FDA oversight

**Evolution Considerations**:
```python
# Example: Mutation that would FAIL Criterion 1
system_prompt: "Analyze the chest X-ray for signs of pneumonia and provide diagnostic recommendations."

# Example: Mutation that would PASS Criterion 1  
system_prompt: "Display patient vital sign trends and laboratory results to support clinical assessment."
```

**Validation Requirements**:
- **Pass**: Document absence of image/signal processing capabilities
- **Fail**: Implement FDA-compliant image analysis validation per 21 CFR 820.30

### Criterion 2: Display Medical Information Only

**Assessment Question**: Does the evolved component primarily display information to healthcare users?

**Classification Impact**:
- **Pass** (Display only): Information presentation without clinical analysis
- **Fail** (Active analysis): Clinical processing requiring device validation

**Evolution Considerations**:
```yaml
# Example: Prompt evolution that would FAIL Criterion 2
role: "Clinical Analyzer"
system_prompt: "Process patient data to identify sepsis risk patterns and calculate probability scores."

# Example: Prompt evolution that would PASS Criterion 2
role: "Clinical Dashboard"  
system_prompt: "Present patient vital signs, laboratory values, and alert thresholds in standardized clinical format."
```

**Validation Requirements**:
- **Pass**: Confirm no automated clinical analysis or decision-making
- **Fail**: Validate clinical analysis algorithms per FDA AI/ML guidance

### Criterion 3: Recommendations vs. Specific Diagnoses

**Assessment Question**: Does the evolved component provide general recommendations rather than specific diagnoses?

**Classification Impact**:
- **Pass** (General recommendations): Treatment options and clinical considerations
- **Fail** (Specific diagnoses): Diagnostic conclusions triggering device classification

**Evolution Considerations**:
```python
# Example: Code evolution that would FAIL Criterion 3
def analyze_symptoms(symptoms: List[str]) -> str:
    return f"Diagnosis: Patient has {specific_condition} based on symptom analysis."

# Example: Code evolution that would PASS Criterion 3  
def analyze_symptoms(symptoms: List[str]) -> str:
    return f"Clinical considerations: Symptoms suggest evaluation for {condition_category}. Physician assessment required."
```

**Validation Requirements**:
- **Pass**: Document recommendation language and clinical discretion preservation  
- **Fail**: Validate diagnostic accuracy and clinical decision logic

### Criterion 4: Independent User Verification

**Assessment Question**: Can healthcare users independently verify the component's recommendations using available clinical information?

**Classification Impact**:
- **Pass** (User verifiable): Transparent logic and clinical reasoning
- **Fail** (Black box): Opaque processing requiring algorithmic validation

**Evolution Considerations**:
```yaml
# Example: Prompt that would FAIL Criterion 4 (black box)
system_prompt: "Use proprietary risk scoring algorithm to generate clinical recommendations."

# Example: Prompt that would PASS Criterion 4 (transparent)
system_prompt: "Based on published clinical guidelines [cite sources], present evidence-based recommendations with supporting rationale for independent physician verification."
```

**Validation Requirements**:
- **Pass**: Document transparency mechanisms and clinical reasoning
- **Fail**: Implement algorithmic transparency and explainability features

## Validation Plan Template

### Phase 1: Pre-Evolution Baseline Validation

**Objectives**: Establish validated baseline before evolution experiments

**Documentation Requirements**:
- Initial system configuration and intended purpose
- Risk analysis and clinical hazard assessment  
- Test protocols and acceptance criteria
- Baseline performance metrics and clinical evaluation

**Validation Activities**:

1. **System Configuration Documentation**
   ```bash
   # Document current solution state
   git tag baseline-v1.0.0
   
   # Capture configuration snapshot
   cp solutions/medtech_team/project.yaml validation/baseline-config.yaml
   cp solutions/medtech_team/prompts.yaml validation/baseline-prompts.yaml  
   cp solutions/medtech_team/tasks.yaml validation/baseline-tasks.yaml
   ```

2. **Clinical Risk Assessment**
   - Identify potential patient safety risks from system changes
   - Document risk mitigation strategies and monitoring procedures
   - Establish safety limits and emergency stop criteria

3. **Performance Baseline Establishment**  
   ```bash
   # Generate baseline compliance report
   curl -X GET http://localhost:8000/evolution/experiments/{experiment_id}/compliance
   
   # Document baseline test coverage
   make test-all > validation/baseline-test-results.txt
   ```

### Phase 2: During-Evolution Monitoring

**Objectives**: Continuous validation and risk monitoring during active evolution

**Real-Time Monitoring Requirements**:

1. **Candidate Classification Tracking**
   ```python
   # Monitor FDA classification for all candidates
   for candidate in evolution_candidates:
       fda_result = fda_classifier.classify(candidate.intended_purpose)
       if fda_result["classification"] == "Device CDS":
           trigger_enhanced_validation(candidate)
           require_clinical_review(candidate)
   ```

2. **Drift Detection and Safety Limits**
   - Fitness degradation below safety thresholds
   - Unintended medical terminology introduction  
   - Regulatory classification changes from baseline

3. **Human Oversight Documentation**
   ```json
   {
     "approval_event": {
       "timestamp": "2026-04-13T14:30:00Z",
       "user_id": "clinical.reviewer@hospital.org",
       "candidate_id": "cand-789abc",
       "decision": "approved",
       "rationale": "Improves diagnostic clarity while maintaining Non-Device CDS classification",
       "regulatory_review": "confirmed_non_device_cds",
       "clinical_impact": "low_risk",
       "signature": "digital_signature_hash"
     }
   }
   ```

### Phase 3: Post-Evolution Validation

**Objectives**: Comprehensive validation of approved changes before deployment

**Validation Activities**:

1. **Clinical Effectiveness Validation**
   ```bash
   # Run comprehensive clinical test suite
   python -m pytest tests/clinical/ -v --cov=src/
   
   # Generate clinical performance report
   python scripts/generate_clinical_metrics.py --baseline baseline-v1.0.0 --current HEAD
   ```

2. **Regulatory Compliance Verification**
   - Confirm all approved candidates maintain Non-Device CDS classification
   - Validate audit trail completeness and integrity
   - Verify 21 CFR Part 11 compliance for all electronic records

3. **Change Control Documentation**
   ```markdown
   ## Change Control Record CCR-2026-001
   
   **Evolution Experiment**: experiment-456def
   **Approval Date**: 2026-04-13
   **Clinical Reviewer**: Dr. Sarah Johnson, MD
   **Regulatory Reviewer**: Jane Smith, RAC
   
   **Changes Approved**:
   - Candidate cand-789abc: Prompt optimization for sepsis screening
   - Candidate cand-234ghi: Code improvement for drug interaction checking
   
   **Validation Evidence**:
   - Clinical test results: 47/47 test cases passed
   - FDA classification: Both candidates maintain Non-Device CDS
   - Performance improvement: 12% faster response time
   - Safety assessment: No new clinical risks identified
   
   **Deployment Authorization**: Approved for production deployment
   ```

## Audit Trail Requirements

### 21 CFR Part 11 Electronic Records

**Record Integrity**:
- SHA-256 digital signatures on all evolution experiment data
- Immutable audit logs with cryptographic verification
- Time-stamped entries with NTP-synchronized timestamps
- Redundant backup storage with geographic separation

**Required Documentation**:

1. **Experiment Configuration Records**
   ```json
   {
     "experiment_record": {
       "experiment_id": "exp-123456",
       "created_at": "2026-04-13T10:00:00Z", 
       "created_by": "system.engineer@company.com",
       "solution_name": "medtech_team",
       "target_type": "prompt",
       "parameters": {
         "population_size": 20,
         "max_generations": 50,
         "mutation_rate": 0.1,
         "crossover_rate": 0.7,
         "evaluator_weights": {
           "test_driven": 0.4,
           "semantic": 0.3, 
           "integration": 0.3
         }
       },
       "intended_purpose_classification": "Non-Device CDS",
       "regulatory_review_required": false,
       "signature": "exp_config_signature_hash"
     }
   }
   ```

2. **Generation-by-Generation Records** 
   ```json
   {
     "generation_record": {
       "experiment_id": "exp-123456",
       "generation_number": 15,
       "timestamp": "2026-04-13T12:15:00Z",
       "population_size": 20,
       "fitness_statistics": {
         "best_fitness": 0.847,
         "average_fitness": 0.623,
         "fitness_variance": 0.094
       },
       "candidates": [
         {
           "candidate_id": "cand-789abc",
           "fitness_score": 0.847,
           "mutation_applied": "prompt_semantic_enhancement",
           "crossover_parent_1": "cand-456def", 
           "crossover_parent_2": "cand-234ghi",
           "fda_classification": "Non-Device CDS",
           "requires_human_review": true
         }
       ],
       "signature": "generation_record_signature_hash"
     }
   }
   ```

3. **Human Decision Records**
   ```json
   {
     "approval_record": {
       "decision_id": "decision-098765",
       "timestamp": "2026-04-13T14:30:00Z",
       "experiment_id": "exp-123456", 
       "candidate_id": "cand-789abc",
       "reviewer_id": "clinical.reviewer@hospital.org",
       "reviewer_role": "Clinical Decision Support Reviewer",
       "decision": "approved",
       "rationale": "Candidate improves clinical clarity while maintaining regulatory compliance. Fitness improvement of 8.2% with confirmed Non-Device CDS classification.",
       "regulatory_impact": "none",
       "clinical_risk_assessment": "low",
       "digital_signature": "decision_signature_hash",
       "witness_signature": "witness_signature_hash"
     }
   }
   ```

### Electronic Signature Requirements

**Signer Authentication**:
- Multi-factor authentication for all clinical reviewers
- Role-based access controls with least privilege principle
- Automatic session timeouts and re-authentication requirements

**Signature Components**:
```json
{
  "electronic_signature": {
    "signer_identity": "dr.sarah.johnson@hospital.org",
    "signer_name": "Sarah Johnson, MD",  
    "signing_timestamp": "2026-04-13T14:30:15Z",
    "signature_meaning": "Clinical approval of evolution candidate", 
    "document_hash": "sha256:a1b2c3d4...",
    "signature_algorithm": "RSA-4096",
    "signature_value": "digital_signature_bytes",
    "certificate_authority": "Hospital PKI Root CA"
  }
}
```

**Access Controls**:
- Role-based permissions: Clinical Reviewer, Regulatory Affairs, System Administrator
- Audit trail of all system access and permission changes  
- Emergency access procedures with elevated logging
- Automatic user deprovisioning and access review cycles

## Required Documentation

### Clinical Documentation

**1. Clinical Evaluation Plan (CEP)**
```markdown
# Clinical Evaluation Plan: SAGE Evolution Medtech System

## Objective
Validate clinical safety and effectiveness of AI/ML system evolution for 
clinical decision support in hospital environment.

## Clinical Endpoints
- Primary: Maintenance of clinical accuracy during system evolution
- Secondary: Improved clinical workflow efficiency 
- Safety: No increase in clinical risk or adverse events

## Study Population  
- Healthcare providers using clinical decision support
- Patient population: Adult inpatients in medical/surgical units
- Clinical contexts: Sepsis screening, drug interaction checking, diagnostic support

## Evaluation Methods
- Retrospective chart review for clinical accuracy
- Prospective usability testing with healthcare providers
- Continuous safety monitoring during evolution experiments
```

**2. Clinical Risk Management File (ISO 14971)**
```markdown
# Risk Analysis: SAGE Evolution System

## Hazard Identification
1. **Incorrect Clinical Recommendations**
   - Risk Level: Medium
   - Mitigation: Human approval required for all evolution candidates
   - Detection: Continuous fitness monitoring and clinical validation

2. **System Unavailability During Evolution**  
   - Risk Level: Low
   - Mitigation: Baseline system remains operational during experiments
   - Detection: Automated health checks and failover procedures

3. **Unintended Diagnostic Claims**
   - Risk Level: High  
   - Mitigation: Automated FDA 4-criterion classification checking
   - Detection: Real-time regulatory compliance monitoring
```

### Technical Documentation

**1. Software Development Plan (IEC 62304)**
```markdown
# Software Development Plan: SAGE Evolution

## Safety Classification
Software Safety Class B: Non-life-threatening injuries possible

## Development Lifecycle
- Requirements: Evolution objectives and regulatory constraints
- Architecture: Genetic algorithm with human-in-the-loop approval  
- Implementation: Python/FastAPI with React frontend
- Testing: Unit, integration, clinical validation testing
- Risk Management: Continuous monitoring and safety limits

## Configuration Management
- Version control: Git with signed commits
- Change control: Human approval required for all evolution deployments
- Release management: Validated releases with clinical documentation
```

**2. Validation Evidence**
```markdown
# Validation Evidence Package

## Test Results Summary
- Unit Test Coverage: 94.3% (target: >90%)
- Integration Test Pass Rate: 100% (47/47 tests)  
- Clinical Test Pass Rate: 100% (23/23 clinical scenarios)
- Performance Test Results: 12% improvement in response time

## Regulatory Compliance Evidence  
- FDA Classification: Non-Device CDS (confirmed for all approved candidates)
- 21 CFR Part 11: Electronic records and signatures validated
- Audit Trail Integrity: 100% cryptographic verification passed

## Clinical Performance Evidence
- Clinical Accuracy: Maintained at 96.8% (baseline: 96.2%)
- Healthcare Provider Satisfaction: 8.7/10 (survey of 25 clinicians)
- Workflow Efficiency: 15% reduction in time-to-recommendation
```

## Validation Evidence

### Clinical Performance Metrics

**Accuracy Validation**:
- Compare evolution candidates against physician panel consensus 
- Use gold standard clinical benchmarks for validation
- Measure diagnostic accuracy, therapeutic appropriateness, safety outcomes

**Usability Validation**:
- Healthcare provider acceptance and satisfaction surveys
- Time-and-motion studies for workflow impact assessment  
- Error rate analysis and user interface effectiveness

**Safety Validation**:
- Adverse event monitoring during evolution experiments
- Clinical risk assessment before and after system changes
- Emergency procedures and rollback validation

### Technical Performance Evidence

**System Performance**:
```bash
# Automated performance benchmarking
python scripts/benchmark_evolution.py --baseline baseline-v1.0.0 --current HEAD

# Results:
# Response Time: 1.2s -> 1.05s (12% improvement)
# Memory Usage: 2.1GB -> 1.9GB (9% reduction) 
# CPU Utilization: 45% -> 38% (16% improvement)
# Test Coverage: 91.2% -> 94.3% (3.1% improvement)
```

**Security Validation**:
- Penetration testing and vulnerability assessment
- Data encryption and access control validation
- Network security and audit trail integrity verification

## Risk Mitigation

### Evolution Controls

**1. Safety Limits and Constraints**
```python
# Example safety constraints in evolution configuration
EVOLUTION_SAFETY_LIMITS = {
    "max_fitness_degradation": 0.05,  # Stop if fitness drops >5%
    "forbidden_medical_terms": ["diagnosis", "diagnostic", "diagnose"],
    "required_disclaimer_phrases": ["physician verification required", "not a diagnosis"],
    "max_regulatory_risk_score": 0.3,  # Prevent high-risk changes
    "human_approval_threshold": 0.85   # Require review for high-fitness candidates
}
```

**2. Automated Safety Monitoring**  
```python
def monitor_evolution_safety(experiment_id: str) -> Dict[str, bool]:
    """Continuous safety monitoring during evolution."""
    safety_status = {
        "fitness_degradation_check": check_fitness_trends(experiment_id),
        "regulatory_compliance_check": verify_fda_classification(experiment_id), 
        "clinical_terminology_check": scan_medical_language_violations(experiment_id),
        "human_oversight_check": verify_approval_rate(experiment_id)
    }
    
    if not all(safety_status.values()):
        trigger_evolution_pause(experiment_id)
        alert_clinical_team(experiment_id, safety_status)
    
    return safety_status
```

### Clinical Controls

**1. Clinical Review Board Oversight**
- Dedicated clinical reviewers for high-impact evolution candidates
- Regular review of evolution experiment outcomes and safety data
- Clinical governance oversight and emergency stop authority

**2. Change Impact Assessment**
```markdown
## Change Impact Assessment Template

### Clinical Impact
- Patient Population Affected: [specify patient demographics/conditions]
- Clinical Workflow Changes: [describe workflow modifications]  
- Healthcare Provider Training Required: [identify training needs]

### Regulatory Impact  
- FDA Classification Change: [document any classification changes]
- Validation Requirements: [specify additional validation needed]
- Post-Market Surveillance: [describe monitoring requirements]

### Risk Assessment
- Clinical Risks: [identify potential patient safety risks]
- Mitigation Strategies: [describe risk mitigation measures]  
- Monitoring Plan: [define safety monitoring procedures]
```

## Regulatory Submission

### Pre-Submission Preparation

**1. FDA Pre-Submission (Q-Sub)**
```markdown
# FDA Pre-Submission: SAGE Evolution Clinical Decision Support

## Product Overview
AI/ML-enabled clinical decision support system with evolutionary optimization capabilities.

## Regulatory Questions
1. Does our 4-criterion classification approach align with FDA CDS guidance?
2. Are our validation methods sufficient for evolutionary AI/ML systems?
3. What additional post-market surveillance is recommended?

## Supporting Documentation
- Clinical evaluation plan and risk management file
- Validation evidence package and technical documentation
- Predicate device analysis and regulatory precedent research
```

**2. Quality Management System Documentation**
- Design controls documentation per 21 CFR 820.30
- Risk management file per ISO 14971
- Clinical evaluation per FDA CDS guidance
- Software lifecycle processes per IEC 62304

### Submission Content

**1. Device Description and Intended Use**
```markdown
# Device Description: SAGE Evolution CDS

## Intended Use
SAGE Evolution is a clinical decision support software system that uses genetic 
algorithms to continuously optimize clinical recommendations while maintaining 
regulatory compliance and requiring human oversight for all system changes.

## Indications for Use  
For use by qualified healthcare professionals to support clinical decision-making 
through evidence-based recommendations. The system provides general clinical 
guidance and treatment options but does not provide specific diagnoses.
```

**2. Clinical Data and Performance Evidence**
- Clinical validation studies and performance benchmarks
- Healthcare provider usability and satisfaction data  
- Safety monitoring results and adverse event reporting
- Comparative effectiveness data against predicate devices

**3. Technical Documentation**
- Software architecture and design documentation
- Validation and verification test protocols and results
- Cybersecurity and data protection measures
- Change control and configuration management procedures

### Post-Market Requirements

**1. Post-Market Surveillance Plan**
```markdown
# Post-Market Surveillance: SAGE Evolution

## Surveillance Objectives
- Monitor clinical performance and safety during routine use
- Track evolution experiment outcomes and validation evidence
- Assess real-world effectiveness and user satisfaction

## Data Collection Methods
- Automated performance monitoring and audit trail analysis
- Periodic healthcare provider surveys and feedback collection
- Clinical outcomes tracking and adverse event reporting

## Reporting Requirements  
- Annual post-market surveillance reports to FDA
- Mandatory reporting of safety-related software changes
- Proactive communication of significant performance findings
```

**2. Change Control for Post-Market Updates**
- Classification of software changes (minor/major/significant)
- Validation requirements for each change category
- FDA notification and approval requirements
- Documentation and audit trail maintenance

---

**Related Documentation:**
- [Getting Started Guide](../getting-started.md): Initial setup and basic operation
- [API Reference](../integration/api-reference.md): Technical integration details
- [SAGE Architecture](../../Architecture_Study.md): System design and compliance framework