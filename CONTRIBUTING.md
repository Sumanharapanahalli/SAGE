# Contributing to SAGE

Thank you for your interest in contributing to **SAGE (Smart Agentic-Guided Empowerment)**. This document covers everything you need to get started.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Commit Message Convention](#commit-message-convention)
- [Code Style](#code-style)
- [Solution vs Framework Scope](#solution-vs-framework-scope)
- [Reporting Issues](#reporting-issues)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior as described in that document.

---

## Getting Started

SAGE is a modular autonomous AI agent framework built on lean development methodology. Before contributing, familiarize yourself with:

- **[CLAUDE.md](CLAUDE.md)** — Full project layout, architecture, and engineering rules
- **[.claude/SOUL.md](.claude/SOUL.md)** — Core philosophy and design principles
- **[LICENSE](LICENSE)** — Apache 2.0

---

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- Git
- At least one LLM provider (Ollama recommended for offline development)

### Clone and Install

```bash
git clone https://github.com/Sumanharapanahalli/SAGE.git
cd SAGE

# Create virtual environment and install all dependencies
make venv

# For low-RAM machines (skips ChromaDB/embeddings)
make venv-minimal
```

### Start the Backend

```bash
# Start FastAPI on :8000
make run PROJECT=starter
```

### Start the Frontend

```bash
# Start Vite dev server on :5173
make ui
```

### LLM Provider

No API keys are required for most providers. The quickest setup for local development:

```bash
# Option A: Ollama (fully offline)
# Install from https://ollama.com, then:
ollama serve
ollama pull llama3.2

# Option B: Gemini CLI (cloud, default provider)
npm install -g @google/gemini-cli
gemini  # login once
```

Set your provider in `config/config.yaml`:
```yaml
llm:
  provider: "ollama"
  ollama_model: "llama3.2"
```

---

## Running Tests

Always run tests before and after making changes to `src/`.

```bash
make test           # Framework unit tests
make test-all       # Framework + all solution tests
make test-api       # API endpoint tests only
make test-compliance # IQ/OQ/PQ validation suite

# Test a specific solution
make test-solution PROJECT=starter
```

All tests must pass before submitting a PR. If you add new functionality, add corresponding tests.

---

## Making Changes

### Before You Start

1. **Search first.** Check existing issues and PRs to avoid duplicate work.
2. **Read the file first.** Understand the existing pattern before modifying.
3. **Make the minimum change.** Don't refactor while fixing bugs. Don't add "while I'm here" improvements.

### Branch Naming

Use descriptive branch names with a type prefix:

```
feature/multi-llm-pool
fix/queue-deadlock
docs/api-examples
test/eval-runner-coverage
chore/update-dependencies
```

### Key Rules

- **Never commit proprietary solutions** to this repository. Mount them via `SAGE_SOLUTIONS_DIR` from a separate private repo.
- **Never add solution-specific logic to `src/`**. Solutions plug in via YAML only.
- **Never bypass the HITL approval gate** for solution-level agent proposals.
- **Never remove the `threading.Lock` from `LLMGateway`**.
- **Use `self.logger` or `logging.getLogger()`**, never `print()`.
- **Run `make test` before and after** any change to `src/`.

---

## Pull Request Process

1. **Fork** the repository and create your branch from `main`.
2. **Make your changes** following the guidelines above.
3. **Add or update tests** for any new or changed functionality.
4. **Run the full test suite** (`make test-all`) and ensure everything passes.
5. **Update documentation** if your change affects the public API, CLI, or user-facing behavior.
6. **Submit a PR** against `main` using the [PR template](.github/PULL_REQUEST_TEMPLATE.md).
7. **Respond to review feedback** promptly. PRs that go stale for 30+ days may be closed.

### PR Requirements

- All CI checks must pass.
- At least one maintainer approval is required.
- The PR description must explain *why*, not just *what*.
- Breaking changes must be clearly flagged in the PR title with a `BREAKING:` prefix.

---

## Commit Message Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]

[optional footer(s)]
```

### Types

| Type | When to use |
|---|---|
| `feat` | A new feature or capability |
| `fix` | A bug fix |
| `docs` | Documentation only changes |
| `test` | Adding or updating tests |
| `chore` | Build process, dependencies, CI config |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | Performance improvement |
| `ci` | CI/CD pipeline changes |

### Scope Examples

- `feat(api)` — new API endpoint
- `fix(llm)` — LLM gateway fix
- `test(eval)` — eval runner tests
- `docs(contributing)` — contribution guidelines

### Examples

```
feat(api): add bulk knowledge import endpoint
fix(queue): prevent deadlock when task queue is full
test(system): add end-to-end system tests for full API lifecycle
docs(readme): update LLM provider setup instructions
chore(deps): bump FastAPI to 0.115
```

---

## Code Style

### Python

- **Formatter/Linter:** [Ruff](https://docs.astral.sh/ruff/)
- **Line length:** 120 characters
- **Type hints:** Required for all public function signatures
- **Docstrings:** Required for public classes and functions
- **Imports:** Sorted by ruff (isort-compatible)

### TypeScript (frontend)

- **Framework:** React 18 + TypeScript
- **Linting:** ESLint (configuration in progress)
- **Formatting:** Prettier (configuration in progress)

### General

- No unused imports or dead code.
- No `TODO` comments without a linked issue number.
- Prefer explicit over implicit. Name variables clearly.

---

## Solution vs Framework Scope

SAGE maintains a hard boundary between the **framework** and **solutions**. Understanding this distinction is critical:

| Scope | What it covers | Where it lives | Who owns it |
|---|---|---|---|
| **Framework** (`scope: "sage"`) | Agent capabilities, API, UI modules, integrations | `src/`, `web/`, `config/` | SAGE open-source community |
| **Solution** (`scope: "solution"`) | Domain-specific YAML, workflows, MCP tools, tests | `solutions/<name>/` | The solution team |

### Rules

- **Framework improvements** (new agent capabilities, better UI, new integrations) go through GitHub Issues/PRs on this repo.
- **Solution improvements** (domain-specific tasks, prompts, workflows) belong in the solution's own backlog, not here.
- **Never hardcode a solution name in `src/`.** The framework is domain-blind.
- **Example solutions** in `solutions/` (starter, meditation_app, etc.) are open and welcome contributions. Proprietary solutions must never be committed here.

---

## Reporting Issues

- **Bugs:** Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md).
- **Feature requests:** Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md).
- **Security vulnerabilities:** Do **not** open a public issue. See [SECURITY.md](SECURITY.md) for responsible disclosure instructions.

---

## Questions?

If you have questions about contributing, open a [Discussion](https://github.com/Sumanharapanahalli/SAGE/discussions) on GitHub. We are happy to help new contributors get oriented.

Thank you for helping make SAGE better.
