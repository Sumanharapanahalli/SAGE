#!/usr/bin/env bash
# Master system test runner.
# Executes E2E, SLA, chaos, load, and performance regression checks in sequence.
# Exit code: 0 = all pass, 1 = any failure.
#
# Usage:
#   ./run_system_tests.sh                        # all suites
#   ./run_system_tests.sh --suite e2e            # single suite
#   ./run_system_tests.sh --suite load           # k6 load tests only
#   ./run_system_tests.sh --suite chaos          # chaos tests only
#   STAGING_BASE_URL=https://... ./run_system_tests.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
REPORT_DIR="${SCRIPT_DIR}/reports"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

SUITE="${1:-all}"
for arg in "$@"; do
  case $arg in
    --suite=*) SUITE="${arg#--suite=}" ;;
    --suite)   shift; SUITE="${1}" ;;
  esac
done

# Defaults
STAGING_BASE_URL="${STAGING_BASE_URL:-https://api-staging.example.com}"
TOXIPROXY_HOST="${TOXIPROXY_HOST:-localhost}"
TOXIPROXY_PORT="${TOXIPROXY_PORT:-8474}"
K6_BINARY="${K6_BINARY:-k6}"
PYTEST_WORKERS="${PYTEST_WORKERS:-4}"

mkdir -p "${REPORT_DIR}"

log() { echo "[$(date -u +%H:%M:%S)] $*"; }
fail() { echo "[FAIL] $*" >&2; EXIT_CODE=1; }

EXIT_CODE=0

# ---- Verify prerequisites ----
log "Verifying prerequisites..."
command -v python3 >/dev/null 2>&1 || { echo "python3 required"; exit 1; }
if [[ "${SUITE}" == "all" || "${SUITE}" == "load" ]]; then
  command -v "${K6_BINARY}" >/dev/null 2>&1 || {
    log "WARNING: k6 not found at '${K6_BINARY}' — skipping load tests"
    SKIP_LOAD=1
  }
fi

# ---- Health check staging ----
log "Checking staging health: ${STAGING_BASE_URL}/health"
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${STAGING_BASE_URL}/health" || echo "000")
if [[ "${HTTP_STATUS}" != "200" ]]; then
  echo "ERROR: Staging not healthy (HTTP ${HTTP_STATUS}). Aborting." >&2
  exit 1
fi
log "Staging healthy."

# ---- Helper: run pytest suite ----
run_pytest() {
  local suite_name="$1"
  local test_path="$2"
  local extra_args="${3:-}"
  local report_file="${REPORT_DIR}/${suite_name}_${TIMESTAMP}.xml"

  log "Running ${suite_name} tests..."
  if python3 -m pytest \
      "${test_path}" \
      -v \
      -m "${suite_name}" \
      --tb=short \
      --junitxml="${report_file}" \
      -n "${PYTEST_WORKERS}" \
      ${extra_args} \
      --base-url="${STAGING_BASE_URL}" \
      2>&1 | tee "${REPORT_DIR}/${suite_name}_${TIMESTAMP}.log"; then
    log "[PASS] ${suite_name}"
  else
    fail "${suite_name} tests failed — see ${report_file}"
  fi
}

# ---- E2E tests ----
if [[ "${SUITE}" == "all" || "${SUITE}" == "e2e" ]]; then
  run_pytest "e2e" "${SCRIPT_DIR}/e2e/"
fi

# ---- SLA validation ----
if [[ "${SUITE}" == "all" || "${SUITE}" == "sla" ]]; then
  run_pytest "sla" "${SCRIPT_DIR}/sla/"
fi

# ---- Chaos tests ----
if [[ "${SUITE}" == "all" || "${SUITE}" == "chaos" ]]; then
  # Chaos tests need Docker and toxiproxy — skip gracefully if unavailable
  if ! command -v docker >/dev/null 2>&1; then
    log "WARNING: docker not available — skipping chaos tests"
  elif ! curl -s "http://${TOXIPROXY_HOST}:${TOXIPROXY_PORT}/proxies" >/dev/null 2>&1; then
    log "WARNING: toxiproxy not reachable at ${TOXIPROXY_HOST}:${TOXIPROXY_PORT} — skipping chaos tests"
  else
    run_pytest "chaos" "${SCRIPT_DIR}/chaos/" "-n 1"  # chaos tests must run serially
  fi
fi

# ---- Load tests (k6) ----
if [[ "${SUITE}" == "all" || "${SUITE}" == "load" ]] && [[ -z "${SKIP_LOAD:-}" ]]; then
  log "Running k6 load tests (10,000 VUs)..."
  K6_RESULT=0
  "${K6_BINARY}" run \
    --env BASE_URL="${STAGING_BASE_URL}" \
    --out json="${REPORT_DIR}/k6_scenarios_${TIMESTAMP}.json" \
    "${SCRIPT_DIR}/load/k6_scenarios.js" 2>&1 | tee "${REPORT_DIR}/k6_scenarios_${TIMESTAMP}.log" \
    || K6_RESULT=$?

  if [[ ${K6_RESULT} -ne 0 ]]; then
    fail "k6 scenario load test failed (exit ${K6_RESULT})"
  else
    log "[PASS] k6 scenario load test"
  fi

  log "Running k6 transfer TPS test (500 TPS)..."
  TPS_RESULT=0
  "${K6_BINARY}" run \
    --env BASE_URL="${STAGING_BASE_URL}" \
    --out json="${REPORT_DIR}/k6_tps_${TIMESTAMP}.json" \
    "${SCRIPT_DIR}/load/k6_transfer_tps.js" 2>&1 | tee "${REPORT_DIR}/k6_tps_${TIMESTAMP}.log" \
    || TPS_RESULT=$?

  if [[ ${TPS_RESULT} -ne 0 ]]; then
    fail "k6 TPS test failed (exit ${TPS_RESULT})"
  else
    log "[PASS] k6 transfer TPS test"
  fi
fi

# ---- Performance regression check ----
if [[ "${SUITE}" == "all" || "${SUITE}" == "perf" ]]; then
  BASELINE_DIR="${SCRIPT_DIR}/performance/baselines"
  if [[ -d "${BASELINE_DIR}" && -n "$(ls "${BASELINE_DIR}"/*.json 2>/dev/null)" ]]; then
    log "Running performance regression detection..."
    if STAGING_BASE_URL="${STAGING_BASE_URL}" \
       python3 -m tests.system.performance.regression_detector \
       2>&1 | tee "${REPORT_DIR}/perf_regression_${TIMESTAMP}.log"; then
      log "[PASS] Performance regression check"
    else
      fail "Performance regression detected — see ${REPORT_DIR}/perf_regression_${TIMESTAMP}.log"
    fi
  else
    log "No baselines found — collecting initial baselines..."
    STAGING_BASE_URL="${STAGING_BASE_URL}" \
      python3 -m tests.system.performance.baseline_collector \
      2>&1 | tee "${REPORT_DIR}/perf_baseline_${TIMESTAMP}.log"
    log "Baselines collected. Commit ${BASELINE_DIR}/ to track regressions."
  fi
fi

# ---- Summary ----
echo ""
echo "========================================"
echo "SYSTEM TEST SUITE COMPLETE"
echo "Timestamp:  ${TIMESTAMP}"
echo "Suite:      ${SUITE}"
echo "Reports:    ${REPORT_DIR}/"
echo "Result:     $([ ${EXIT_CODE} -eq 0 ] && echo 'ALL PASS' || echo 'FAILURES DETECTED')"
echo "========================================"

exit ${EXIT_CODE}
