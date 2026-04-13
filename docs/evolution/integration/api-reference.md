# SAGE Evolution API Reference

## Base URL and Authentication

**Base URL**: `http://localhost:8000`

**Authentication**: Currently no authentication required for local development. Production deployments should implement appropriate authentication mechanisms (API keys, OAuth 2.0, or JWT tokens).

**Content-Type**: All requests expect `application/json` content type.

**Error Handling**: Standard HTTP status codes with JSON error responses.

## Experiment Management

### List Experiments

Retrieve all evolution experiments with their current status and metadata.

**Endpoint**: `GET /evolution/experiments`

**Request**: No parameters required

**Response**:
```json
{
  "experiments": [
    {
      "experiment_id": "exp-12345678",
      "status": "running",
      "solution_name": "medtech_team",
      "target_type": "prompt", 
      "current_generation": 15,
      "max_generations": 50,
      "population_size": 20,
      "best_fitness": 0.847,
      "created_at": "2026-04-13T10:00:00Z",
      "parameters": {
        "mutation_rate": 0.1,
        "crossover_rate": 0.7,
        "evaluator_weights": {
          "test_driven": 0.4,
          "semantic": 0.3,
          "integration": 0.3
        }
      }
    }
  ]
}
```

**Status Values**:
- `running`: Active evolution in progress
- `paused`: Temporarily suspended
- `stopped`: Terminated by user
- `complete`: Reached max generations or convergence
- `failed`: Error occurred during execution

### Start Experiment

Create and start a new evolution experiment.

**Endpoint**: `POST /evolution/experiments`

**Request**:
```json
{
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
}
```

**Request Parameters**:
- **solution_name** (string, required): Name of SAGE solution to evolve
- **target_type** (string, required): Evolution target - `"prompt"`, `"code"`, or `"build"`
- **population_size** (integer, optional): Candidates per generation (default: 20, range: 5-50)
- **max_generations** (integer, optional): Maximum evolution cycles (default: 50, range: 10-200)
- **mutation_rate** (float, optional): Probability of mutations (default: 0.1, range: 0.01-0.5)
- **crossover_rate** (float, optional): Probability of crossover (default: 0.7, range: 0.1-0.95)
- **evaluator_weights** (object, optional): Fitness evaluation weights (must sum to 1.0)

**Response**:
```json
{
  "experiment_id": "exp-87654321"
}
```

**Error Responses**:
```json
// Solution not found
{
  "detail": "Solution name required",
  "status_code": 400
}

// Invalid parameters
{
  "detail": "mutation_rate must be between 0.01 and 0.5",
  "status_code": 400
}
```

### Get Experiment Details

Retrieve detailed information about a specific experiment.

**Endpoint**: `GET /evolution/experiments/{experiment_id}`

**Path Parameters**:
- **experiment_id** (string, required): Unique experiment identifier

**Response**:
```json
{
  "experiment_id": "exp-12345678",
  "status": "running",
  "solution_name": "medtech_team", 
  "target_type": "prompt",
  "current_generation": 15,
  "max_generations": 50,
  "population_size": 20,
  "best_fitness": 0.847,
  "created_at": "2026-04-13T10:00:00Z",
  "parameters": {
    "mutation_rate": 0.1,
    "crossover_rate": 0.7,
    "evaluator_weights": {
      "test_driven": 0.4,
      "semantic": 0.3, 
      "integration": 0.3
    }
  }
}
```

**Error Response**:
```json
{
  "detail": "Experiment not found",
  "status_code": 404
}
```

### Get Experiment Status

Retrieve real-time status and health metrics for an active experiment.

**Endpoint**: `GET /evolution/experiments/{experiment_id}/status`

**Path Parameters**:
- **experiment_id** (string, required): Unique experiment identifier

**Response**:
```json
{
  "status": "running",
  "current_generation": 15,
  "best_fitness": 0.847,
  "population_health": "healthy",
  "convergence_trend": "improving"
}
```

**Population Health Values**:
- `healthy`: Normal evolution progress with good fitness diversity
- `struggling`: Low fitness scores or poor convergence after significant generations
- `converging`: Population fitness plateauing, indicating potential completion

**Convergence Trend Values**:
- `improving`: Fitness increasing over recent generations  
- `plateauing`: Fitness stable over recent generations
- `declining`: Fitness decreasing (may indicate overfitting)

### Update Experiment

Modify experiment parameters or control execution (pause/resume).

**Endpoint**: `PUT /evolution/experiments/{experiment_id}`

**Path Parameters**:
- **experiment_id** (string, required): Unique experiment identifier

**Request**:
```json
{
  "status": "paused",
  "parameters": {
    "mutation_rate": 0.15,
    "evaluator_weights": {
      "test_driven": 0.5,
      "semantic": 0.3,
      "integration": 0.2
    }
  }
}
```

**Request Parameters**:
- **status** (string, optional): New status - `"running"`, `"paused"`, or `"stopped"`
- **parameters** (object, optional): Updated evolution parameters (partial update supported)

**Response**:
```json
{
  "message": "Experiment updated successfully"
}
```

**Error Responses**:
```json
// Invalid status
{
  "detail": "Invalid status",
  "status_code": 400
}

// Experiment not found
{
  "detail": "Experiment not found", 
  "status_code": 404
}
```

### Stop Experiment

Terminate an evolution experiment and clean up resources.

**Endpoint**: `DELETE /evolution/experiments/{experiment_id}`

**Path Parameters**:
- **experiment_id** (string, required): Unique experiment identifier

**Response**:
```json
{
  "message": "Experiment stopped"
}
```

## Candidate Management

### List Candidates

Retrieve all candidates generated for a specific experiment.

**Endpoint**: `GET /evolution/experiments/{experiment_id}/candidates`

**Path Parameters**:
- **experiment_id** (string, required): Unique experiment identifier

**Query Parameters**:
- **generation** (integer, optional): Filter by specific generation number
- **status** (string, optional): Filter by status - `"pending"`, `"approved"`, or `"rejected"`
- **min_fitness** (float, optional): Filter by minimum fitness score
- **limit** (integer, optional): Maximum candidates to return (default: 50)

**Response**:
```json
{
  "candidates": [
    {
      "candidate_id": "cand-789abc",
      "experiment_id": "exp-12345678",
      "generation": 15,
      "fitness_score": 0.847,
      "status": "pending",
      "content": {
        "type": "prompt_evolution",
        "target_file": "solutions/medtech_team/prompts.yaml",
        "changes": {
          "analyst_prompt": {
            "original": "You are a clinical analyst...",
            "evolved": "You are a clinical analyst that provides evidence-based recommendations following FDA CDS guidelines..."
          }
        },
        "fitness_breakdown": {
          "test_driven": 0.92,
          "semantic": 0.78,
          "integration": 0.85
        }
      },
      "feedback": null,
      "created_at": "2026-04-13T12:15:00Z",
      "fda_classification": {
        "classification": "Non-Device CDS",
        "confidence": "HIGH",
        "criteria_met": [true, true, true, true],
        "reasoning": "Candidate maintains compliance with all FDA 4-criterion requirements"
      }
    }
  ]
}
```

**Candidate Content Types**:
- **prompt_evolution**: Changes to system prompts in prompts.yaml
- **code_evolution**: Modifications to Python source code
- **build_evolution**: Updates to build configurations and dependencies

### Approve Candidate

Approve or reject a candidate with feedback for learning improvement.

**Endpoint**: `POST /evolution/candidates/approve`

**Request**:
```json
{
  "experiment_id": "exp-12345678", 
  "candidate_id": "cand-789abc",
  "approved": true,
  "feedback": "Approved: Improved clinical clarity while maintaining Non-Device CDS classification. Fitness improvement acceptable."
}
```

**Request Parameters**:
- **experiment_id** (string, required): Unique experiment identifier
- **candidate_id** (string, required): Unique candidate identifier
- **approved** (boolean, required): Approval decision
- **feedback** (string, optional): Human reasoning for approval/rejection (recommended for learning)

**Response**:
```json
{
  "candidate_id": "cand-789abc",
  "status": "approved",
  "message": "Candidate approved"
}
```

**Approval Effects**:
- **Approved candidates**: Integrated into solution configuration, influence future generations
- **Rejected candidates**: Removed from consideration, rejection feedback trains future mutations

### Reject Candidate

Convenience endpoint for rejecting candidates (equivalent to approve with approved=false).

**Endpoint**: `POST /evolution/candidates/reject`

**Request**:
```json
{
  "experiment_id": "exp-12345678",
  "candidate_id": "cand-234ghi", 
  "feedback": "Rejected: Changes introduce diagnostic language that violates FDA Non-Device CDS criteria. Maintain recommendation-only language."
}
```

**Response**:
```json
{
  "candidate_id": "cand-234ghi",
  "status": "rejected", 
  "message": "Candidate rejected"
}
```

## Metrics and Analytics

### Fitness History

Retrieve fitness progression over generations for visualization and analysis.

**Endpoint**: `GET /evolution/experiments/{experiment_id}/fitness-history`

**Path Parameters**:
- **experiment_id** (string, required): Unique experiment identifier

**Query Parameters**:
- **generations** (integer, optional): Number of recent generations (default: 20)
- **metric_type** (string, optional): Fitness metric - `"best"`, `"average"`, or `"all"` (default: "best")

**Response**:
```json
{
  "experiment_id": "exp-12345678",
  "fitness_history": [
    {
      "generation": 1,
      "timestamp": "2026-04-13T10:05:00Z", 
      "best_fitness": 0.623,
      "average_fitness": 0.445,
      "fitness_variance": 0.089,
      "population_size": 20
    },
    {
      "generation": 2,
      "timestamp": "2026-04-13T10:07:00Z",
      "best_fitness": 0.671,
      "average_fitness": 0.478, 
      "fitness_variance": 0.094,
      "population_size": 20
    }
  ]
}
```

### Population Metrics

Get detailed analytics about population diversity and convergence patterns.

**Endpoint**: `GET /evolution/experiments/{experiment_id}/population-metrics`

**Response**:
```json
{
  "experiment_id": "exp-12345678",
  "current_generation": 15,
  "population_statistics": {
    "size": 20,
    "fitness_distribution": {
      "min": 0.234,
      "max": 0.847,
      "mean": 0.623,
      "median": 0.612,
      "std_dev": 0.145
    },
    "diversity_metrics": {
      "genetic_diversity": 0.73,
      "phenotypic_diversity": 0.68,
      "novelty_score": 0.45
    },
    "convergence_indicators": {
      "generations_since_improvement": 3,
      "improvement_rate": 0.023,
      "plateau_risk": "low",
      "premature_convergence_risk": "medium"
    }
  }
}
```

### Performance Benchmarks

Compare current experiment performance against baseline and historical data.

**Endpoint**: `GET /evolution/experiments/{experiment_id}/benchmarks`

**Response**:
```json
{
  "experiment_id": "exp-12345678",
  "baseline_comparison": {
    "baseline_fitness": 0.675,
    "current_best_fitness": 0.847,
    "improvement_percentage": 25.5,
    "statistical_significance": 0.023
  },
  "performance_metrics": {
    "convergence_speed": {
      "generations_to_90_percent": 12,
      "average_improvement_per_generation": 0.018
    },
    "resource_efficiency": {
      "cpu_time_per_generation": 45.2,
      "memory_usage_mb": 342,
      "storage_usage_mb": 156
    }
  },
  "historical_comparison": {
    "rank_among_experiments": 3,
    "percentile_performance": 78.5,
    "similar_experiments_count": 12
  }
}
```

## Compliance and Reporting

### Compliance Report

Generate comprehensive compliance report for regulatory submission and audit purposes.

**Endpoint**: `GET /evolution/experiments/{experiment_id}/compliance`

**Response**:
```json
{
  "experiment_id": "exp-12345678",
  "report_timestamp": "2026-04-13T14:30:00Z",
  "total_candidates": 145,
  "approved_candidates": 23,
  "rejected_candidates": 89,
  "pending_candidates": 33,
  "average_fitness": 0.623,
  "compliance_score": 0.891,
  "regulatory_summary": {
    "fda_classification_distribution": {
      "non_device_cds": 142,
      "device_cds": 3
    },
    "high_risk_candidates": 3,
    "regulatory_review_required": 8
  },
  "risk_metrics": {
    "diversity_risk": "low",
    "convergence_risk": "medium", 
    "human_oversight": "adequate",
    "audit_trail_integrity": "verified"
  },
  "audit_trail_summary": {
    "total_events": 456,
    "signature_verification": "passed",
    "timestamp_integrity": "verified",
    "access_control_violations": 0
  }
}
```

### Evolution Audit Trail

Retrieve detailed audit trail for compliance and traceability.

**Endpoint**: `GET /evolution/experiments/{experiment_id}/audit-trail`

**Query Parameters**:
- **start_date** (string, optional): ISO 8601 date for trail start (default: experiment start)
- **end_date** (string, optional): ISO 8601 date for trail end (default: now)
- **event_type** (string, optional): Filter by event type
- **user_id** (string, optional): Filter by user identity

**Response**:
```json
{
  "experiment_id": "exp-12345678",
  "audit_events": [
    {
      "event_id": "evt-123456",
      "timestamp": "2026-04-13T10:00:00Z",
      "event_type": "experiment_started",
      "user_id": "system.engineer@company.com",
      "details": {
        "solution_name": "medtech_team",
        "target_type": "prompt",
        "parameters": {...}
      },
      "signature": "event_signature_hash",
      "ip_address": "10.0.1.100"
    },
    {
      "event_id": "evt-234567", 
      "timestamp": "2026-04-13T14:30:00Z",
      "event_type": "candidate_approved",
      "user_id": "clinical.reviewer@hospital.org",
      "details": {
        "candidate_id": "cand-789abc",
        "fitness_score": 0.847,
        "approval_rationale": "Improved clinical clarity...",
        "fda_classification": "Non-Device CDS"
      },
      "signature": "approval_signature_hash",
      "witness_signature": "witness_signature_hash",
      "ip_address": "10.0.1.105"
    }
  ]
}
```

**Event Types**:
- `experiment_started`: New evolution experiment created
- `experiment_paused`: Experiment execution suspended
- `experiment_resumed`: Paused experiment restarted
- `experiment_stopped`: Experiment terminated
- `generation_completed`: New generation finished evaluation
- `candidate_generated`: New candidate created by evolution
- `candidate_approved`: Human approval of candidate
- `candidate_rejected`: Human rejection of candidate
- `parameter_updated`: Experiment parameters modified
- `safety_violation`: Safety limit exceeded or constraint violated

### Regulatory Change Impact

Analyze regulatory impact of approved candidates for change control documentation.

**Endpoint**: `GET /evolution/experiments/{experiment_id}/regulatory-impact`

**Response**:
```json
{
  "experiment_id": "exp-12345678",
  "impact_assessment": {
    "classification_changes": {
      "baseline_classification": "Non-Device CDS",
      "current_classification": "Non-Device CDS", 
      "classification_stable": true
    },
    "validation_requirements": {
      "additional_clinical_validation": false,
      "regulatory_submission_required": false,
      "post_market_surveillance_changes": false
    },
    "change_classification": {
      "change_type": "minor_enhancement", 
      "change_risk_level": "low",
      "validation_impact": "routine_testing"
    }
  },
  "approved_changes_summary": [
    {
      "candidate_id": "cand-789abc",
      "change_description": "Enhanced clinical recommendation clarity",
      "regulatory_impact": "maintains_non_device_cds",
      "clinical_impact": "improved_usability",
      "validation_evidence": "passed_clinical_test_suite"
    }
  ]
}
```

## Error Handling

### Standard HTTP Status Codes

**2xx Success**:
- `200 OK`: Request successful with response body
- `201 Created`: New resource created successfully
- `202 Accepted`: Request accepted for processing
- `204 No Content`: Request successful with no response body

**4xx Client Errors**:
- `400 Bad Request`: Invalid request parameters or format
- `401 Unauthorized`: Authentication required (if auth enabled)
- `403 Forbidden`: Insufficient permissions (if auth enabled)  
- `404 Not Found`: Requested resource not found
- `409 Conflict`: Resource conflict or business logic violation
- `422 Unprocessable Entity`: Valid request format but logical errors

**5xx Server Errors**:
- `500 Internal Server Error`: Unexpected server error
- `502 Bad Gateway`: Upstream service unavailable
- `503 Service Unavailable`: Service temporarily unavailable
- `504 Gateway Timeout`: Request timeout

### Error Response Format

All error responses follow a consistent JSON structure:

```json
{
  "error": {
    "code": "EXPERIMENT_NOT_FOUND",
    "message": "The specified experiment could not be found",
    "details": {
      "experiment_id": "exp-invalid",
      "available_experiments": ["exp-123", "exp-456"]
    },
    "timestamp": "2026-04-13T14:30:00Z",
    "request_id": "req-987654321"
  }
}
```

**Error Response Fields**:
- **code** (string): Machine-readable error identifier
- **message** (string): Human-readable error description
- **details** (object, optional): Additional context and debugging information
- **timestamp** (string): ISO 8601 timestamp when error occurred
- **request_id** (string): Unique identifier for request tracking

### Common Error Codes

**Experiment Management**:
- `EXPERIMENT_NOT_FOUND`: Specified experiment ID does not exist
- `SOLUTION_NOT_FOUND`: Specified solution name is not available
- `INVALID_TARGET_TYPE`: Target type must be 'prompt', 'code', or 'build'
- `INVALID_PARAMETERS`: Evolution parameters outside acceptable ranges
- `EXPERIMENT_ALREADY_STOPPED`: Cannot modify stopped experiment

**Candidate Management**:
- `CANDIDATE_NOT_FOUND`: Specified candidate ID does not exist
- `CANDIDATE_ALREADY_PROCESSED`: Candidate has already been approved/rejected
- `MISSING_APPROVAL_FEEDBACK`: Feedback recommended for learning improvement
- `INVALID_APPROVAL_REQUEST`: Malformed approval request structure

**System Errors**:
- `EVOLUTION_ENGINE_ERROR`: Internal evolution algorithm error
- `DATABASE_CONNECTION_ERROR`: Unable to connect to storage backend
- `EXTERNAL_SERVICE_TIMEOUT`: Dependency service not responding
- `RESOURCE_EXHAUSTION`: Insufficient system resources for operation

## Rate Limiting

**Request Limits**:
- Evolution Management: 100 requests per minute per IP
- Candidate Operations: 500 requests per minute per IP  
- Reporting/Analytics: 200 requests per minute per IP
- Audit Trail Access: 50 requests per minute per IP

**Rate Limit Headers**:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 47
X-RateLimit-Reset: 1681397400
X-RateLimit-Window: 60
```

**Rate Limit Exceeded Response**:
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Request rate limit exceeded",
    "details": {
      "limit": 100,
      "window_seconds": 60,
      "retry_after": 13
    }
  }
}
```

## WebSocket Updates

Real-time monitoring and updates via WebSocket connection for live dashboard integration.

**Connection**: `ws://localhost:8000/ws/evolution/{experiment_id}`

**Authentication**: Include authorization header if authentication is enabled

### Message Types

**Experiment Status Updates**:
```json
{
  "type": "experiment_status",
  "experiment_id": "exp-12345678",
  "timestamp": "2026-04-13T12:15:00Z",
  "data": {
    "status": "running",
    "current_generation": 16,
    "best_fitness": 0.862,
    "population_health": "healthy",
    "convergence_trend": "improving"
  }
}
```

**New Candidate Generated**:
```json
{
  "type": "candidate_generated", 
  "experiment_id": "exp-12345678",
  "timestamp": "2026-04-13T12:16:00Z",
  "data": {
    "candidate_id": "cand-345def",
    "generation": 16,
    "fitness_score": 0.892,
    "requires_approval": true,
    "fda_classification": "Non-Device CDS"
  }
}
```

**Fitness Improvement**:
```json
{
  "type": "fitness_improvement",
  "experiment_id": "exp-12345678", 
  "timestamp": "2026-04-13T12:17:00Z",
  "data": {
    "generation": 16,
    "previous_best": 0.862,
    "new_best": 0.892,
    "improvement_percentage": 3.5,
    "candidate_id": "cand-345def"
  }
}
```

**Safety Alert**:
```json
{
  "type": "safety_alert",
  "experiment_id": "exp-12345678",
  "timestamp": "2026-04-13T12:20:00Z", 
  "data": {
    "alert_type": "regulatory_violation",
    "severity": "high",
    "message": "Candidate generated with Device CDS classification",
    "candidate_id": "cand-456ghi",
    "action_required": "immediate_review"
  }
}
```

### Client Connection Example

```javascript
// JavaScript WebSocket client example
const ws = new WebSocket('ws://localhost:8000/ws/evolution/exp-12345678');

ws.onopen = function(event) {
    console.log('Connected to evolution updates');
};

ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    
    switch(message.type) {
        case 'experiment_status':
            updateDashboardStatus(message.data);
            break;
        case 'candidate_generated': 
            addCandidateToQueue(message.data);
            break;
        case 'fitness_improvement':
            updateFitnessChart(message.data);
            break;
        case 'safety_alert':
            displaySafetyAlert(message.data);
            break;
    }
};

ws.onerror = function(error) {
    console.error('WebSocket error:', error);
};
```

## SDK Integration

For programmatic integration with external systems and custom automation.

### Python SDK Example

```python
import asyncio
import aiohttp
from typing import Dict, List

class SAGEEvolutionClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def start_experiment(
        self, 
        solution_name: str,
        target_type: str,
        **kwargs
    ) -> str:
        """Start new evolution experiment."""
        async with self.session.post(
            f"{self.base_url}/evolution/experiments",
            json={
                "solution_name": solution_name,
                "target_type": target_type,
                **kwargs
            }
        ) as response:
            result = await response.json()
            return result["experiment_id"]
    
    async def monitor_experiment(self, experiment_id: str) -> Dict:
        """Get current experiment status."""
        async with self.session.get(
            f"{self.base_url}/evolution/experiments/{experiment_id}/status"
        ) as response:
            return await response.json()
    
    async def approve_candidate(
        self,
        experiment_id: str, 
        candidate_id: str,
        approved: bool,
        feedback: str = None
    ) -> Dict:
        """Approve or reject candidate."""
        async with self.session.post(
            f"{self.base_url}/evolution/candidates/approve",
            json={
                "experiment_id": experiment_id,
                "candidate_id": candidate_id,
                "approved": approved,
                "feedback": feedback
            }
        ) as response:
            return await response.json()

# Usage example
async def main():
    async with SAGEEvolutionClient() as client:
        # Start experiment
        experiment_id = await client.start_experiment(
            solution_name="medtech_team",
            target_type="prompt",
            population_size=20,
            max_generations=50
        )
        
        # Monitor progress
        while True:
            status = await client.monitor_experiment(experiment_id)
            if status["status"] != "running":
                break
            await asyncio.sleep(10)
        
        print(f"Experiment {experiment_id} completed")

# Run the example
asyncio.run(main())
```

### Integration Best Practices

**Connection Management**:
- Use connection pooling for multiple concurrent requests
- Implement retry logic with exponential backoff for transient failures
- Monitor rate limits and implement client-side throttling

**Error Handling**:
- Implement comprehensive error handling for all API calls
- Log API errors with request context for debugging
- Provide graceful degradation for non-critical operations

**Authentication** (when enabled):
- Securely store and rotate API credentials
- Implement token refresh logic for expired credentials
- Use role-based access controls for different operations

**Monitoring Integration**:
- Use WebSocket connections for real-time updates
- Implement health checks for API availability
- Monitor experiment performance and resource usage

---

**Related Documentation:**
- [Getting Started Guide](../getting-started.md): User-friendly introduction and basic setup
- [FDA Validation Guide](../compliance/fda-validation.md): Regulatory compliance procedures  
- [SAGE API Reference](../../API_REFERENCE.md): Complete framework API documentation