# SAGE Framework Setup Guide

## Initial Setup

### Virtual Environment Setup

```bash
make venv               # Create .venv and install all deps (first time)
make venv-minimal       # Low-RAM machine — skips ChromaDB/embeddings
```

### LLM Provider Setup (No API Keys Required)

All providers except `claude` work without API keys. Pick the one that fits.

| Provider | Setup | Best for |
|---|---|---|
| `gemini` (default) | `npm install -g @google/gemini-cli` → `gemini` (login once) | Cloud, latest models |
| `claude-code` | `npm install -g @anthropic-ai/claude-code` → `claude` (login once) | Claude models |
| `ollama` | Install from ollama.com → `ollama serve` → `ollama pull llama3.2` | Fully offline, no login |
| `local` | `pip install llama-cpp-python` + download GGUF model | GPU-direct, air-gapped |
| `generic-cli` | Set `generic_cli_path` in config.yaml | Any CLI tool |
| `claude` | Set `ANTHROPIC_API_KEY` | Only option requiring a key |

Change provider in `config/config.yaml`:
```yaml
llm:
  provider: "ollama"        # switch here
  ollama_model: "llama3.2"  # any model you've pulled
```

Or switch at runtime (executes immediately, no approval): `POST /llm/switch {"provider": "ollama", "model": "llama3.2"}`

### gstack Integration — Browser Testing Setup

```bash
# Install gstack (one-time)
git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
cd ~/.claude/skills/gstack && ./setup
```

Once installed, OpenBrowser auto-detects gstack and uses real Chromium for testing. Without gstack, it falls back to LLM-simulated testing.

## sage-desktop (optional — no-sockets Tauri app)

Only needed for operators in port-restricted corporate environments.
Everyone else can use the web UI and skip this section.

### Prerequisites

- **Rust toolchain** (stable) — install from https://rustup.rs
- **Node.js 18+** — the web UI already needs this
- **Edge WebView2 runtime** — ships with Windows 10/11; manual install
  only for offline Server SKUs
- **Python interpreter + SAGE deps on PATH** — during `dev`, the sidecar
  uses your system Python; the release build will bundle its own via
  Tauri `externalBin` (Phase 4)

### One-time install

```bash
make desktop-install          # cd sage-desktop && npm install
```

### Run in dev mode

```bash
make desktop-dev              # Tauri dev — Rust core + Vite + sidecar
```

Environment knobs read by the sidecar spawner (all optional):

| Variable | Default | Purpose |
|---|---|---|
| `SAGE_ROOT` | inferred from `current_exe()` | Repo root; sidecar adds it to `sys.path` |
| `SAGE_PYTHON` | `python` | Which interpreter to spawn |
| `SAGE_SOLUTION_NAME` | — | Pin sidecar to a named solution under `SAGE_SOLUTIONS_DIR` |
| `SAGE_SOLUTION_PATH` | — | Absolute path to a solution dir (overrides name) |

### Tests

```bash
make test-desktop             # Sidecar (pytest) + Rust (cargo) + React (vitest)
make test-desktop-e2e         # Spawn real sidecar, round-trip NDJSON
```

None of these tests need a running FastAPI server, network access, or
admin privileges.

### Release build (Phase 4 — not yet wired)

```bash
make desktop-build            # Produces .exe bundle (deferred)
```

See [interfaces/desktop-gui.md](interfaces/desktop-gui.md) for
architecture details, the RPC method list, and the failure model.

## Development Environment

### Environment Variables

Set these for private solutions and skills:

```bash
export SAGE_SOLUTIONS_DIR=/path/to/your-private-solutions-repo
export SAGE_SKILLS_DIR=/path/to/private/skills
```

### Integration Phase Configuration

| Phase | Feature | Config |
|---|---|---|---|
| 0 | Langfuse observability | `observability.langfuse_enabled: true` |
| 1 | LlamaIndex + LangChain + mem0 | `memory.backend: llamaindex` |
| 1.5 | MCP tool registry | `solutions/<name>/mcp_servers/` |
| 2 | n8n webhook receiver | `N8N_WEBHOOK_SECRET` env var |
| 8 | Slack two-way approval | `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET` |
| 11 | Temporal durable workflows | `TEMPORAL_HOST` env var |

## New Solution Setup

### Method 1: Onboarding Wizard (recommended)

```bash
curl -X POST http://localhost:8000/onboarding/generate \
  -H "Content-Type: application/json" \
  -d '{"description": "We build surgical robots for minimally invasive procedures",
       "solution_name": "surgical_robotics",
       "compliance_standards": ["ISO 13485", "IEC 62304"],
       "integrations": ["gitlab", "slack"]}'
```

### Method 2: Manual (from starter template)

```bash
cp -r solutions/starter solutions/my_domain
# Edit the 3 YAML files, then:
make run PROJECT=my_domain
```

### Private Solutions Setup

```bash
export SAGE_SOLUTIONS_DIR=/path/to/your-private-solutions-repo
make run PROJECT=board_games   # .sage/ auto-created on first start
```

Add `.sage/` to your private solutions repo's root `.gitignore`.

## Multi-Tenant Configuration

All endpoints accept `X-SAGE-Tenant: <team_name>` header. This scopes:
- Vector store collection: `<tenant>_knowledge`
- Audit log metadata: `tenant_id` field
- Task queue submissions: tagged with tenant

Default (no header): active solution name is used as tenant.

## Docker Configuration

For domain-specific toolchains:

- `sage/firmware-toolchain` - ARM cross-compilation, OpenOCD, HAL drivers
- `sage/pcb-toolchain` - KiCad, Gerber generation, DRC/ERC
- `sage/hw-simulation` - SPICE, Verilog simulation, waveform analysis
- `sage/ml-toolchain` - GPU-accelerated training, model deployment
- `sage/doc-toolchain` - LaTeX, regulatory document generation

## Troubleshooting

### Common Issues

**Python not found**: Activate virtual environment with `source .venv/bin/activate`

**LLM provider fails**: Check provider installation and authentication

**Solution not loading**: Verify YAML syntax and required fields

**Tests failing**: Run `make test` to identify specific failures

### Performance Tuning

**Low RAM machines**: Use `make venv-minimal` to skip ChromaDB

**GPU workloads**: Configure OpenShell with NVIDIA container runtime

**High concurrency**: Consider multiple SAGE instances with load balancing