# SAGE Framework Technical Decisions

## Architecture Decisions

### Human-in-the-Loop (HITL) Gates

**Decision**: All solution-level agent proposals require human approval before execution.

**Rationale**: 
- SAGE amplifies human judgment, never replaces it
- Compliance requirements in regulated industries mandate human oversight
- Builds trust through transparent decision-making

**Alternatives Considered**: 
- Full automation with confidence scoring
- Optional approval based on risk assessment

**Implications**:
- Requires approval UI and workflow infrastructure
- May slow down development velocity
- Ensures regulatory compliance out-of-box

### YAML-First Agent Configuration

**Decision**: Agent roles, prompts, and tasks defined in YAML files, not Python code.

**Rationale**:
- Domain experts can modify agent behavior without coding
- Versioned, declarative configuration
- Hot-reload capability for rapid iteration

**Alternatives Considered**:
- Python-based configuration classes
- Database-driven configuration

**Implications**:
- Requires YAML validation and parsing infrastructure
- Enables non-technical domain customization
- Configuration becomes portable across environments

### .sage/ Runtime Isolation

**Decision**: Each solution gets its own `.sage/` directory for runtime data.

**Rationale**:
- Complete data isolation between solutions
- Portable solution histories
- Never pollutes the framework repository

**Alternatives Considered**:
- Global SAGE database
- User home directory storage
- Cloud-based storage

**Implications**:
- Audit trails move with solutions
- No central analytics across solutions
- Simplified multi-tenant deployment

## LLM Provider Strategy

### Multi-Provider Support

**Decision**: Support multiple LLM providers with runtime switching.

**Rationale**:
- Avoid vendor lock-in
- Different providers excel at different tasks
- Cost optimization based on use case

**Alternatives Considered**:
- Single provider (OpenAI/Anthropic only)
- Provider abstraction layer

**Implications**:
- More complex provider management
- Consistent API abstraction required
- Enables cost and performance optimization

### No API Keys for Open Models

**Decision**: Prioritize providers that don't require API keys (Gemini CLI, Ollama, local).

**Rationale**:
- Reduces setup friction for new users
- Enables air-gapped deployments
- Cost-effective for development and testing

## Data Architecture Decisions

### SQLite for Audit Logs

**Decision**: Use SQLite for audit logging and compliance records.

**Rationale**:
- File-based, no external dependencies
- ACID compliance for regulatory requirements
- Portable across environments

**Alternatives Considered**:
- PostgreSQL for structured data
- MongoDB for flexible schema
- Cloud-based logging services

**Implications**:
- Limited concurrent write performance
- Simple deployment and backup
- Regulatory compliance built-in

### Vector Store for Memory

**Decision**: Use ChromaDB for vector storage and semantic search.

**Rationale**:
- Enables semantic similarity search
- Local deployment option
- Python-native integration

**Alternatives Considered**:
- Pinecone for cloud vector storage
- PostgreSQL with pgvector
- Elasticsearch for full-text search

## Integration Strategy

### Graceful Degradation

**Decision**: All integrations must fail gracefully without breaking core functionality.

**Rationale**:
- SAGE should work even with partial infrastructure
- Reduces deployment complexity
- Improves reliability in production

**Examples**:
- OpenShell unavailable → fallback to SandboxRunner
- Vector store down → in-memory search
- Slack unavailable → local notifications

### Three-Tier Execution Cascade

**Decision**: OpenShell → SandboxRunner → Direct execution fallback chain.

**Rationale**:
- Maximum isolation when available
- Graceful degradation when containers unavailable
- Consistent interface regardless of execution tier

**Implications**:
- Complex execution path management
- Robust fallback mechanisms required
- Enables deployment flexibility

## Testing and Quality

### Test-Driven Development (TDD)

**Decision**: Implement TDD for all new features and critical bug fixes.

**Rationale**:
- Ensures code quality and design
- Provides regression protection
- Documents expected behavior

**Implementation**:
- Write tests first, then implementation
- Comprehensive test coverage for core functionality
- Integration tests for complete workflows

### Experimental Verification in Gym

**Decision**: Agent training uses real toolchain execution, not just LLM feedback.

**Rationale**:
- Agents learn from actual results, not hallucinations
- Builds real-world competence
- Reduces gap between training and production

**Implementation**:
- 3-tier grading: experimental 40% + LLM 30% + structural 30%
- Domain-specific experimental commands
- Critics refine acceptance criteria based on evidence

## Security and Compliance

### 21 CFR Part 11 Electronic Signatures

**Decision**: Implement full electronic signature compliance for regulated industries.

**Rationale**:
- Required for FDA-regulated software
- Competitive advantage in medtech markets
- Demonstrates enterprise readiness

**Implementation**:
- Complete signature workflows with integrity verification
- Audit trails for all signature activities
- Role-based signature requirements

### Change Control Processes

**Decision**: Formal change control for all requirement modifications.

**Rationale**:
- Regulatory compliance requirement
- Maintains traceability for safety-critical systems
- Prevents uncontrolled system changes

**Implementation**:
- Change request → impact assessment → approval → execution
- Complete audit trail for all changes
- Bidirectional traceability matrices

## Performance and Scalability

### Single-Threaded LLM Gateway

**Decision**: LLM Gateway uses threading.Lock for single-lane inference.

**Rationale**:
- Prevents LLM resource contention
- Predictable response times
- Simplified rate limiting

**Trade-offs**:
- Limits concurrent LLM requests
- May create bottlenecks under high load
- Ensures stable inference performance

**Future Considerations**:
- Queue-based request handling
- Multiple LLM instance pools
- Provider-specific concurrency limits