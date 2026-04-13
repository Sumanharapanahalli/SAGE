# SAGE Evolution Getting Started Guide

## Overview

SAGE Evolution combines genetic algorithms with human oversight to systematically optimize prompts, code, and build processes in regulated environments. Built specifically for medical device software and FDA-compliant systems, SAGE Evolution maintains complete audit trails while enabling rapid iteration and improvement.

**Key Capabilities:**
- **Genetic Optimization**: Automated mutation, crossover, and selection of system components
- **Human-in-the-Loop Approval**: All changes require explicit human approval before deployment  
- **Regulatory Compliance**: Full 21 CFR Part 11 electronic records and FDA traceability
- **Multi-Target Evolution**: Simultaneously optimize prompts, code implementations, and build configurations
- **Real-Time Monitoring**: Live fitness tracking, population health, and convergence analysis

Evolution experiments run continuously in the background, generating candidate improvements that appear in your approval queue for review. Each candidate includes fitness metrics, change descriptions, and regulatory documentation.

## Quick Start

### Prerequisites

- SAGE Framework installed and running (`make run PROJECT=<solution_name>`)
- Active solution with project.yaml, prompts.yaml, and tasks.yaml configured
- Web dashboard accessible at http://localhost:5173
- Backend API running on http://localhost:8000

### Step 1: Start Your First Experiment

1. **Navigate to Evolution Dashboard**
   ```
   Open: http://localhost:5173/evolution
   ```

2. **Create New Experiment**
   ```bash
   curl -X POST http://localhost:8000/evolution/experiments \
     -H "Content-Type: application/json" \
     -d '{
       "solution_name": "medtech_team", 
       "target_type": "prompt",
       "population_size": 20,
       "max_generations": 50,
       "mutation_rate": 0.1,
       "crossover_rate": 0.7,
       "evaluator_weights": {
         "test_driven": 0.4,
         "semantic": 0.3,
         "integration": 0.3
       }
     }'
   ```

3. **Experiment Parameters Explained**
   - **solution_name**: Your active SAGE solution (e.g., "medtech_team", "firmware_dev")
   - **target_type**: What to evolve ("prompt", "code", or "build")
   - **population_size**: Number of candidates per generation (recommended: 10-30)
   - **max_generations**: Maximum evolution cycles (recommended: 25-100) 
   - **mutation_rate**: Probability of random changes (0.05-0.2)
   - **crossover_rate**: Probability of combining candidates (0.5-0.8)
   - **evaluator_weights**: Fitness scoring priorities

### Step 2: Monitor Progress  

The Evolution dashboard provides real-time insights:

**Generation Tracking**
- Current generation number and progress toward max_generations
- Population health indicators (healthy/struggling/converging)
- Convergence trend analysis (improving/plateauing/declining)

**Fitness Metrics**
- Best fitness score in current population (0.0-1.0 scale)
- Average fitness across all candidates 
- Fitness history chart showing improvement over time
- Evaluation breakdown by component (test coverage, semantic quality, integration compatibility)

**Population Analysis**
- Candidate diversity metrics
- Convergence risk assessment
- Performance distribution visualization

### Step 3: Review and Approve Promising Candidates

When the evolution system generates high-fitness candidates, they appear in the Approvals queue:

1. **Access Approval Queue**
   ```
   Navigate to: http://localhost:5173/approvals
   Filter by: Evolution proposals
   ```

2. **Candidate Review Process**
   Each evolution candidate includes:
   - **Fitness Score**: Overall quality metric (higher is better)
   - **Change Summary**: Human-readable description of modifications
   - **Technical Diff**: Exact changes to prompts, code, or build files
   - **Test Results**: Automated validation outcomes
   - **Regulatory Metadata**: FDA classification, change risk level, required documentation

3. **Approval Decision**
   ```bash
   # Approve candidate
   curl -X POST http://localhost:8000/evolution/candidates/approve \
     -H "Content-Type: application/json" \
     -d '{
       "experiment_id": "<experiment_id>",
       "candidate_id": "<candidate_id>", 
       "approved": true,
       "feedback": "Approved: Improved test coverage and semantic clarity"
     }'
   
   # Reject with feedback  
   curl -X POST http://localhost:8000/evolution/candidates/approve \
     -H "Content-Type: application/json" \
     -d '{
       "experiment_id": "<experiment_id>",
       "candidate_id": "<candidate_id>",
       "approved": false,
       "feedback": "Rejected: Changes introduce regulatory compliance risk"
     }'
   ```

4. **Feedback Integration**
   Your approval/rejection decisions automatically train the evolution system:
   - Approved candidates influence future generation selection
   - Rejection feedback guides mutation strategies away from problematic patterns
   - Human preferences compound over time, improving candidate quality

## Regulatory Compliance

### FDA CDS Classification

SAGE Evolution automatically classifies all code changes using the FDA 4-criterion test:

1. **Medical Images/Physiological Signals**: Does the change analyze medical imaging or physiological data?
2. **Display vs. Analysis**: Does the change only display information or perform clinical analysis?
3. **Recommendations vs. Diagnosis**: Does the change provide recommendations or specific diagnoses?
4. **Independent Verification**: Can healthcare users independently verify the change outcomes?

Based on these criteria, changes are classified as:
- **Non-Device CDS**: Meets all criteria, exempt from FDA device regulations
- **Device CDS**: Fails any criteria, requires FDA oversight and validation

### Audit Trail Requirements

Every evolution experiment maintains complete 21 CFR Part 11 compliance:

**Electronic Records**
- Experiment parameters and start/stop timestamps
- Generation-by-generation candidate fitness scores  
- Human approval/rejection decisions with reasoning
- User identity and timestamp for all actions
- Source code and configuration change history

**Electronic Signatures**
- Digital signatures on all human approval decisions
- Authorized user access controls and role verification
- Non-repudiation through cryptographic audit logs

**Access Controls**
- Role-based permissions for experiment creation/approval
- User session tracking and automatic timeouts
- Administrative oversight and emergency stop capabilities

## Evolution Targets

### Prompt Evolution

**Target Files**: `solutions/<name>/prompts.yaml` system prompts and role definitions

**Optimization Goals**:
- Improve task completion accuracy
- Reduce hallucination and off-topic responses  
- Enhance regulatory compliance language
- Optimize token usage and response time

**Example Mutations**:
```yaml
# Original
system_prompt: "You are a clinical decision support agent. Analyze patient data and provide recommendations."

# Evolved Candidate  
system_prompt: "You are a clinical decision support agent that ONLY provides evidence-based recommendations. Never provide specific diagnoses. Always include the instruction: 'This recommendation requires physician verification per FDA guidelines.'"
```

**Fitness Evaluation**:
- **Test-Driven**: Passes comprehensive prompt test suite
- **Semantic**: Maintains medical accuracy and appropriateness
- **Regulatory**: Meets FDA CDS Non-Device classification criteria

### Code Evolution

**Target Files**: Python modules in `src/agents/`, `src/core/`, solution-specific code

**Optimization Goals**:
- Improve test coverage and code quality
- Reduce cyclomatic complexity  
- Enhance error handling and edge cases
- Optimize performance and memory usage

**Example Mutations**:
```python
# Original
def analyze_symptoms(symptoms: List[str]) -> str:
    if not symptoms:
        return "No analysis possible"
    return f"Based on {len(symptoms)} symptoms: likely diagnosis"

# Evolved Candidate
def analyze_symptoms(symptoms: List[str]) -> str:
    """Analyze symptoms with FDA-compliant recommendations only."""
    if not symptoms:
        raise ValueError("Symptom list cannot be empty")
    
    if len(symptoms) > 10:
        logger.warning("Unusual symptom count may indicate data quality issues")
    
    return f"Based on {len(symptoms)} symptoms: recommend physician evaluation. This is not a diagnosis."
```

**Fitness Evaluation**:
- **Test Coverage**: Increased unit/integration test pass rate
- **Code Quality**: Improved maintainability metrics (complexity, duplication)
- **Performance**: Reduced execution time and resource usage

### Build Plan Evolution

**Target Files**: `Dockerfile`, `requirements.txt`, CI/CD configurations, deployment scripts

**Optimization Goals**:
- Reduce build time and artifact size
- Improve security scanning and vulnerability management
- Enhance reproducibility and environment consistency
- Optimize resource allocation and scaling

**Example Mutations**:
```dockerfile
# Original
FROM python:3.12
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# Evolved Candidate  
FROM python:3.12-slim
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip check \
    && rm -rf ~/.cache/pip
COPY . .
RUN python -m compileall . \
    && python -m pytest --co -q > /dev/null
```

**Fitness Evaluation**:
- **Build Performance**: Reduced build time and image size
- **Security**: Improved vulnerability scan results  
- **Reliability**: Higher deployment success rate

## Best Practices

### Parameter Tuning

**Population Size**:
- Small solutions (< 50 files): 10-20 candidates
- Medium solutions (50-200 files): 20-30 candidates  
- Large solutions (200+ files): 30-50 candidates
- Regulatory constraint: Higher populations provide better audit coverage

**Mutation Rate**:
- Conservative (regulated): 0.05-0.1 (5-10% change probability)
- Standard development: 0.1-0.15 (10-15% change probability)
- Aggressive optimization: 0.15-0.25 (15-25% change probability)
- FDA guidance: Lower rates reduce validation burden

**Crossover Rate**:
- Prompt evolution: 0.6-0.8 (favor combination of successful patterns)
- Code evolution: 0.5-0.7 (balance preservation and innovation)
- Build evolution: 0.7-0.9 (infrastructure changes benefit from proven combinations)

### Fitness Evaluation

**Evaluator Weights** (must sum to 1.0):
```json
{
  "test_driven": 0.4,     // Automated test suite results
  "semantic": 0.3,        // Domain knowledge and correctness  
  "integration": 0.3      // System compatibility and performance
}
```

**Regulatory Environments**:
```json
{
  "test_driven": 0.5,     // Higher emphasis on validation
  "semantic": 0.3,        // Medical accuracy critical
  "integration": 0.2      // Stability over optimization
}
```

**Performance Optimization**:
```json
{
  "test_driven": 0.3,     // Maintain functionality
  "semantic": 0.2,        // Preserve core behavior
  "integration": 0.5      // Focus on speed and efficiency
}
```

### Regulatory Guidelines

**Change Classification**:
- **Minor Evolution**: Fitness improvements < 10%, low regulatory risk
- **Major Evolution**: Fitness improvements > 20%, requires additional validation
- **Breakthrough Evolution**: Fundamental architecture changes, full revalidation needed

**Approval Thresholds**:
- Automatically flag candidates with fitness > 0.85 for priority review
- Require additional justification for fitness improvements < 0.05
- Mandate human review for any candidate affecting diagnostic pathways

**Documentation Requirements**:
- Maintain complete generation lineage for all deployed candidates
- Document rejection reasoning for FDA audit preparation
- Preserve baseline configurations for rollback scenarios

## Troubleshooting

### Common Issues

**Low Fitness Scores**
```
Symptom: Best fitness remains < 0.3 after 10+ generations
Cause: Poor baseline quality or restrictive evaluation criteria
Solution: Review test suite coverage, adjust evaluator weights, increase mutation rate
```

**Population Stagnation**
```  
Symptom: Fitness plateau with no improvement for 5+ generations
Cause: Insufficient genetic diversity or local optimization
Solution: Increase population size, adjust crossover rate, introduce fresh candidates
```

**Regulatory Classification Failures**
```
Symptom: Candidates consistently classified as "Device CDS" 
Cause: Evolution introducing diagnostic language or medical analysis
Solution: Add regulatory constraints to mutation operators, update fitness weights
```

**High Rejection Rate**
```
Symptom: >80% of candidates rejected by human reviewers
Cause: Evolution optimizing for wrong objectives or ignoring constraints  
Solution: Incorporate rejection feedback, adjust evaluator priorities, add domain constraints
```

### Performance Optimization

**Memory Usage**: 
- Limit population size on resource-constrained systems
- Use incremental evaluation instead of full re-computation
- Implement candidate caching for repeated fitness calculations

**Compute Time**:
- Parallelize fitness evaluation across candidates
- Use approximation methods for expensive semantic analysis
- Cache evaluation results for unchanged components

**Network I/O**:
- Batch API calls for candidate approval/rejection
- Use WebSocket connections for real-time monitoring
- Implement client-side caching for experiment metadata

## Next Steps

### Advanced Configuration

- **[FDA Validation Guide](compliance/fda-validation.md)**: Complete regulatory compliance procedures
- **[API Reference](integration/api-reference.md)**: Technical integration details and endpoint documentation
- **[Solution Templates](../ADDING_A_PROJECT.md)**: Create custom evolution targets for new domains

### Integration Examples

- **Custom Evaluators**: Build domain-specific fitness functions
- **External Tools**: Integrate evolution with CI/CD pipelines  
- **Multi-Objective Optimization**: Balance competing objectives (speed vs. accuracy)

### Support Resources

- **Architecture Documentation**: [Architecture Study](../Architecture_Study.md)
- **User Guide**: [Complete User Guide](../USER_GUIDE.md)  
- **API Reference**: [Complete API Documentation](../API_REFERENCE.md)

---

**Next**: Continue to [FDA Validation Procedures](compliance/fda-validation.md) for regulatory compliance setup.