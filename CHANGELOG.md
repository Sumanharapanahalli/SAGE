# Changelog

All notable changes to the SAGE Framework are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.1.0] - 2026-03-25

### Added
- 79 Playwright browser E2E tests covering all 23 UI routes
- Rate limiting middleware with X-RateLimit headers
- White + green HMI theme (default)
- OpenAPI/Swagger docs at `/docs` and `/openapi.json`
- Open-source community files (CONTRIBUTING.md, SECURITY.md, CHANGELOG.md)
- GitHub issue and PR templates
- Product modules: backend, firmware, hardware, mobile, ML models, infra
- CI/CD workflows for backend, firmware, and mobile
- Medtech DHF templates and security threat model

### Fixed
- `GET /queue/tasks` returns 500 when no tasks exist (now returns `[]`)
- `POST /knowledge/add` now accepts both `text` and `content` fields
- `POST /feedback/feature-request` no longer requires `module_id`/`module_name`

## [2.0.0] - 2026-03-20

### Added
- Multi-LLM provider pool with parallel generation (voting, fastest, quality strategies)
- Build Orchestrator (0-to-N product pipeline) with 13 domains, 19 agents, 32 task types
- Adaptive router with Q-learning for task assignment
- Actor-critic agent for plan/code/integration quality scoring
- Anti-drift checkpoints for build integrity
- 58 system end-to-end API lifecycle tests
- OpenSWE autonomous coding agent with ReAct iteration
- DeerFlow task completion semantics
- Wave-based parallel task execution
- Organization graph and multi-solution management

### Changed
- Upgraded to 136 API endpoints across 22 categories
- Expanded to 27 UI pages across 5 sidebar navigation areas
- 17+ bundled solution templates

## [1.0.0] - 2026-02-01

### Added
- Core agent framework: Analyst, Developer, Monitor, Planner, Universal agents
- HITL (Human-in-the-Loop) approval gate with risk-tiered proposals
- Vector memory with ChromaDB for compounding intelligence
- SQLite audit log for compliance (ISO 13485, IEC 62304)
- FastAPI REST interface with CORS and multi-tenant support
- React 18 + TypeScript dashboard with 5-area sidebar navigation
- Solution configuration via 3 YAML files (project, prompts, tasks)
- LLM gateway supporting Gemini CLI, Claude Code CLI, Ollama, local GGUF
- Onboarding wizard for LLM-powered solution generation
- Eval/benchmarking suite with keyword scoring
- SSE streaming for analysis and agent execution
- Knowledge base CRUD with vector search
- LangGraph workflow orchestration with interrupt-before-approve
- Slack two-way approval via Block Kit
- MCP tool discovery and invocation
- n8n webhook receiver
- Multi-tenant isolation via X-SAGE-Tenant header
