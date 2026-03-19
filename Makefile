# ==============================================================================
# Sage Framework — Makefile
# All Python commands use the project's virtual environment (.venv).
#
# First-time setup:
#   make venv          Create .venv and install all dependencies
#   make venv-minimal  Create .venv with minimal deps (low-RAM machines)
#
# Daily usage:
#   make run [PROJECT=iot_medical]   Start FastAPI backend
#   make ui                      Start React web UI (:5173)
#   make test                    Framework unit tests (venv)
#   make test-all                Framework + all solution tests
# ==============================================================================

PROJECT       ?= iot_medical
SOLUTIONS_DIR ?= solutions
PORT          ?= 8000
HOST          ?= 0.0.0.0

# Detect venv Python (works on Windows bash / Linux / macOS)
VENV_DIR      := .venv
ifeq ($(OS),Windows_NT)
  PYTHON      := $(VENV_DIR)/Scripts/python
  PIP         := $(VENV_DIR)/Scripts/pip
  PYTEST      := $(VENV_DIR)/Scripts/pytest
  ACTIVATE    := $(VENV_DIR)/Scripts/activate
else
  PYTHON      := $(VENV_DIR)/bin/python
  PIP         := $(VENV_DIR)/bin/pip
  PYTEST      := $(VENV_DIR)/bin/pytest
  ACTIVATE    := $(VENV_DIR)/bin/activate
endif

.PHONY: venv venv-minimal install install-dev install-ui install-minimal \
        run api cli monitor demo ui \
        test test-unit test-solution test-medtech test-medtech-team \
        test-meditation-app test-four-in-a-line \
        test-compliance test-all test-api \
        docker-up docker-down docker-up-d \
        list-solutions list-projects clean help doctor

# ------------------------------------------------------------------------------
# Virtual environment setup
# ------------------------------------------------------------------------------
venv:
	@echo "Creating virtual environment in $(VENV_DIR)..."
	python -m venv $(VENV_DIR)
	$(PIP) install --upgrade pip -q
	$(PIP) install -r requirements.txt
	$(PIP) install pytest pytest-asyncio pytest-cov httpx
	@echo ""
	@echo "  Virtual environment ready."
	@echo "  Activate with:  source $(ACTIVATE)  (Linux/macOS)"
	@echo "                  .\\$(ACTIVATE)        (Windows PowerShell)"

venv-minimal:
	@echo "Creating minimal virtual environment (no ChromaDB/embeddings)..."
	python -m venv $(VENV_DIR)
	$(PIP) install --upgrade pip -q
	$(PIP) install -r requirements-minimal.txt
	$(PIP) install pytest pytest-asyncio httpx
	@echo "Minimal virtual environment ready. Run with SAGE_MINIMAL=1"

# Legacy install targets (installs into current active env)
install:
	$(PIP) install -r requirements.txt

install-dev:
	$(PIP) install -r requirements.txt
	$(PIP) install pytest pytest-asyncio pytest-cov httpx

install-minimal:
	$(PIP) install pyyaml pydantic fastapi uvicorn python-dotenv requests httpx

install-ui:
	cd web && npm install

# ------------------------------------------------------------------------------
# Run backend (always uses venv Python)
# ------------------------------------------------------------------------------
run:
	@echo "Starting Sage Framework — project: $(PROJECT)"
	SAGE_PROJECT=$(PROJECT) SAGE_SOLUTIONS_DIR=$(SOLUTIONS_DIR) $(PYTHON) src/main.py api --host $(HOST) --port $(PORT)

api: run

cli:
	@echo "Starting Sage CLI — project: $(PROJECT)"
	SAGE_PROJECT=$(PROJECT) SAGE_SOLUTIONS_DIR=$(SOLUTIONS_DIR) $(PYTHON) src/main.py cli

monitor:
	@echo "Starting Sage Monitor — project: $(PROJECT)"
	SAGE_PROJECT=$(PROJECT) SAGE_SOLUTIONS_DIR=$(SOLUTIONS_DIR) $(PYTHON) src/main.py monitor

demo:
	SAGE_PROJECT=$(PROJECT) SAGE_SOLUTIONS_DIR=$(SOLUTIONS_DIR) $(PYTHON) src/main.py demo

# ------------------------------------------------------------------------------
# Web UI
# ------------------------------------------------------------------------------
ui:
	@echo "Starting web UI at http://localhost:5173"
	cd web && npm run dev

# ------------------------------------------------------------------------------
# Tests (always use venv pytest)
# ------------------------------------------------------------------------------

# Framework unit tests
test:
	$(PYTEST) tests/ -m unit -v

test-unit: test

test-api:
	$(PYTEST) tests/test_api.py -v

test-compliance:
	SAGE_SOLUTIONS_DIR=$(SOLUTIONS_DIR) $(PYTEST) solutions/medtech/tests/validation/ -v --tb=long

# Solution-specific tests
test-solution:
	SAGE_SOLUTIONS_DIR=$(SOLUTIONS_DIR) $(PYTEST) solutions/$(PROJECT)/tests/ -v

test-medtech:
	SAGE_SOLUTIONS_DIR=$(SOLUTIONS_DIR) $(PYTEST) solutions/medtech/tests/ \
	  --ignore=solutions/medtech/tests/mcp \
	  --ignore=solutions/medtech/tests/integration \
	  -v

test-medtech-team:
	SAGE_SOLUTIONS_DIR=$(SOLUTIONS_DIR) $(PYTEST) solutions/medtech_team/tests/ -v

test-meditation-app:
	SAGE_SOLUTIONS_DIR=$(SOLUTIONS_DIR) $(PYTEST) solutions/meditation_app/tests/ -v

test-four-in-a-line:
	SAGE_SOLUTIONS_DIR=$(SOLUTIONS_DIR) $(PYTEST) solutions/four_in_a_line/tests/ -v

# Full suite: framework + medtech (excludes mcp/integration which need real services)
test-all:
	@echo "=== Framework unit tests ==="
	$(PYTEST) tests/ -m unit -v
	@echo ""
	@echo "=== medtech solution tests ==="
	SAGE_SOLUTIONS_DIR=$(SOLUTIONS_DIR) $(PYTEST) solutions/medtech/tests/ \
	  --ignore=solutions/medtech/tests/mcp \
	  --ignore=solutions/medtech/tests/integration \
	  -v

# MCP tests (requires fastmcp: pip install fastmcp)
test-mcp:
	SAGE_SOLUTIONS_DIR=$(SOLUTIONS_DIR) $(PYTEST) solutions/medtech/tests/mcp/ -v

# Integration tests (requires configured .env with real service credentials)
test-integration:
	SAGE_SOLUTIONS_DIR=$(SOLUTIONS_DIR) $(PYTEST) solutions/medtech/tests/integration/ -v

# ------------------------------------------------------------------------------
# Docker
# ------------------------------------------------------------------------------
docker-up:
	SAGE_PROJECT=$(PROJECT) docker-compose up --build

docker-down:
	docker-compose down

docker-up-d:
	SAGE_PROJECT=$(PROJECT) docker-compose up -d --build

# ------------------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------------------
list-solutions:
	@ls solutions/

list-projects: list-solutions

doctor:
	$(PYTHON) doctor

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# ------------------------------------------------------------------------------
# Help
# ------------------------------------------------------------------------------
help:
	@echo ""
	@echo "Sage Framework — Available commands:"
	@echo ""
	@echo "Setup:"
	@echo "  make venv                    Create .venv + install all deps"
	@echo "  make venv-minimal            Create .venv + minimal deps (low-RAM)"
	@echo "  make install-ui              Install Node.js deps for web UI"
	@echo ""
	@echo "Run:"
	@echo "  make run [PROJECT=starter]   Start FastAPI backend (:8000)"
	@echo "  make ui                      Start React web UI (:5173)"
	@echo "  make cli [PROJECT=...]       Interactive CLI"
	@echo ""
	@echo "Test:"
	@echo "  make test                    Framework unit tests"
	@echo "  make test-medtech            medtech solution tests"
	@echo "  make test-medtech-team       medtech_team solution tests"
	@echo "  make test-meditation-app     meditation_app solution tests"
	@echo "  make test-four-in-a-line     four_in_a_line solution tests"
	@echo "  make test-solution PROJECT=X Any solution's tests"
	@echo "  make test-all                Framework + medtech (no external deps)"
	@echo "  make test-mcp                MCP tests (needs fastmcp installed)"
	@echo "  make test-integration        Integration tests (needs live services)"
	@echo "  make test-compliance         IQ/OQ/PQ validation protocol"
	@echo ""
	@echo "Deploy:"
	@echo "  make docker-up [PROJECT=...] Start via Docker Compose"
	@echo ""
	@echo "  Solutions: starter | meditation_app | four_in_a_line | medtech_team | <your-solution>"
	@echo ""
