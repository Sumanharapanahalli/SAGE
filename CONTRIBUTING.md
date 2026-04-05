# Contributing to SAGE

Thank you for your interest in contributing to SAGE (Smart Agentic-Guided Empowerment).

## Getting Started

1. **Fork** the repository
2. **Clone** your fork: `git clone https://github.com/<your-username>/SAGE.git`
3. **Set up** the development environment:
   ```bash
   make venv          # Create virtualenv and install Python deps
   cd web && npm install  # Install frontend deps
   ```
4. **Run tests** to verify everything works:
   ```bash
   make test           # Backend tests (pytest)
   cd web && npm test   # Frontend unit tests (vitest)
   cd web && npx playwright test  # Browser e2e tests
   ```

## Development Workflow

1. Create a feature branch from `main`: `git checkout -b feat/my-feature`
2. Write tests **first** (TDD is required for all new features)
3. Implement your changes
4. Run the full test suite and ensure all tests pass
5. Commit with a descriptive message
6. Push and open a Pull Request against `main`

## Pull Request Guidelines

- **One PR per feature/fix** — keep changes focused
- **Tests required** — PRs without tests for new behavior will not be merged
- **No breaking changes** without discussion in an issue first
- **Run `make test`** before submitting — CI will catch failures, but save everyone time
- **TypeScript**: Run `npx tsc --noEmit` to ensure zero type errors
- **Description**: Explain what and why, not just what you changed

## Code Standards

- **Python**: Follow existing patterns in `src/`. Use `logging.getLogger()`, never `print()`
- **TypeScript/React**: Follow existing patterns in `web/src/`
- **Tests**: Use pytest for Python, vitest for frontend unit tests, Playwright for e2e
- **No hardcoded solution names** in `src/` — the framework is domain-blind
- **No secrets** in code — use environment variables

## Architecture Rules

- **Framework vs Solutions**: `src/` knows nothing about specific industries. Solutions plug in via YAML in `solutions/`
- **API boundary**: Everything goes through `src/interface/api.py`. No direct agent calls from UI
- **Data flow**: UI -> API -> Agents -> LLM -> Agents -> Audit Log
- **Approval gate**: Agent proposals require human approval. Framework control executes immediately

## Project Structure

```
src/core/           # LLM gateway, build orchestrator, compliance modules
src/agents/         # Universal, Analyst, Developer, Monitor, Planner, Critic
src/interface/      # FastAPI routes (the only public interface)
src/memory/         # Audit log, vector memory
web/src/            # React dashboard
solutions/          # Solution configs (YAML-driven)
tests/              # pytest test suite
web/e2e/            # Playwright browser tests
```

## Reporting Issues

- Use GitHub Issues with the provided templates
- Include steps to reproduce, expected vs actual behavior
- For security vulnerabilities, see [SECURITY.md](SECURITY.md)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
