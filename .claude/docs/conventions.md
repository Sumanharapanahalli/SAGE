# SAGE Framework Conventions

## Coding Standards

### Core Engineering Values

**Separation of concerns is sacred.**
The framework (`src/`, `web/`) and the solutions (`solutions/<name>/`) are fundamentally different things. The framework knows nothing specific about any industry. Solutions know nothing about framework internals. This boundary must never blur.

**The smallest correct change wins.**
This codebase is working production software. Don't refactor while fixing bugs. Don't add "while I'm here" improvements. Do exactly what was asked, test it, stop.

**Human approval is not optional — it's the product.**
The entire point of SAGE is that AI proposes and humans decide. Never design around, bypass, or make optional the approval step. That's the compliance guarantee.

**Solutions are tenants, not children.**
A solution YAML config plugs in to SAGE; SAGE doesn't belong to any solution. Both are equals from the framework's perspective. Never hardcode solution-specific logic into `src/`.

**Tests are the truth.**
If tests pass, the framework works. If tests fail, nothing else matters. When uncertain about a change, run `make test` first and fix failures before moving on.

## File Organization Rules

### Adding New Components

**When adding a new API endpoint:** it goes in `src/interface/api.py` with a lazy import accessor. Update `client.ts` with the typed fetch function at the same time.

**When adding a new UI page:** create `web/src/pages/MyPage.tsx`, wire the route in `App.tsx`, add the sidebar entry in `Sidebar.tsx`, and the title in `Header.tsx`. All four changes together, nothing skipped.

**When touching solution YAMLs:** never hardcode solution names anywhere in `src/`. Always use `project_config.project_name` or `_SOLUTIONS_DIR`.

**When adding a new agent role:** add it to `prompts.yaml` (role definition + system prompt), add a task type to `tasks.yaml` if needed, wire it in `UniversalAgent`. No new Python files for new roles.

### What to Never Do

- Never commit `solutions/dfs/` to the SAGE repository. It is proprietary.
- Never add company-specific logic to `src/`. Solutions absorb domain specifics.
- Never skip the YAML validation in the `/config/yaml/{file}` endpoint.
- Never break the audit log. It is the compliance record and the training signal.
- Never remove the `threading.Lock` from `LLMGateway`. Single-lane inference is intentional.
- Never add `print()` statements — use `self.logger` or `logging.getLogger()`.
- Never bypass the HITL approval gate for solution-level agent proposals. Not for demos. Not for "obvious" cases. Never.
- Never short-circuit Phase 5 (feedback ingestion). Every rejection is a learning opportunity.
- Never hardcode a solution name in `src/`. The framework is domain-blind.

## Code Style Guidelines

### Python Code

- Always use `self.logger` not `print()`
- Use type hints for all public methods
- Follow dataclass patterns for structured data
- Lazy import heavy dependencies to avoid circular imports
- Handle exceptions gracefully with meaningful error messages
- Use descriptive variable names that explain business intent

### Agent Architecture Principles

**Agents are role-based, not function-based.**
Each agent has a defined role (Analyst, Developer, Monitor, Planner, Universal). Roles are declared in `prompts.yaml`, not hardcoded. Adding a new agent role means editing YAML, not Python.

**Non-invasive instrumentation.**
Agent execution is fully traced through the audit log. No separate telemetry system needed. Every `generate()` call, every approval, every rejection is a structured event.

**Behavioral improvement without model retraining.**
SAGE improves agent quality by enriching the retrieval context (vector store) from human feedback — not by fine-tuning the LLM.

**Wave-capable task execution.**
Tasks without dependencies can and should run in parallel. The queue manager is the scheduler.

**Declarative agent manifest (YAML-first).**
The `prompts.yaml` is the agent package manifest. Role definitions, system prompts, tool access, and behavioral constraints all live there.

## UI Development Standards

### React/TypeScript Guidelines

- Use TypeScript strictly — no `any` types
- Components should be functional with hooks
- Keep components small and focused
- Use the established patterns in `web/src/components/`
- Follow the module registry pattern for feature organization
- Maintain the 3-column layout: SolutionRail + Sidebar + Content

### Sidebar Navigation Rules

**Path conflict rule**: every nav item's `to` must be unique across all areas. Two items with the same `to` will cause the first match to be highlighted as active for both routes.

For solution-specific pages, follow the same pattern but put them in `web/src/pages/solutions/<name>/`. Framework-agnostic pages go in `web/src/pages/`.

## Testing Standards

### Test-Driven Development (TDD)

- Write tests first, then implement functionality
- Tests should cover happy path, error cases, and edge cases
- Use descriptive test names that explain what is being tested
- Mock external dependencies appropriately
- Ensure tests are deterministic and can run in any order

### Test Organization

- Unit tests go in `tests/test_*.py`
- Integration tests cover complete workflows
- Use pytest fixtures for common test data
- Follow the AAA pattern: Arrange, Act, Assert