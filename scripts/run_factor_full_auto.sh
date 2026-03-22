#!/usr/bin/env bash
set -euo pipefail

# One-click full-profile runner:
# - starts docker services
# - creates paper/live accounts
# - writes full-profile compose override
# - applies override and triggers factor research run
# - polls until run finishes (success or error)

BASE_URL="${BASE_URL:-http://127.0.0.1:8802}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-21600}"
TOP_N_SYMBOLS="${TOP_N_SYMBOLS:-20}"
LOOKBACK_DAYS="${LOOKBACK_DAYS:-180}"
PRESCREEN_LIMIT="${PRESCREEN_LIMIT:-10}"
WAIT_TIMEOUT_SECONDS="${WAIT_TIMEOUT_SECONDS:-1800}"
POLL_SECONDS="${POLL_SECONDS:-5}"
READY_TIMEOUT_SECONDS="${READY_TIMEOUT_SECONDS:-600}"
OVERRIDE_FILE="${OVERRIDE_FILE:-docker-compose.factor-full.yml}"
BOOTSTRAP_OVERRIDE_FILE="${BOOTSTRAP_OVERRIDE_FILE:-docker-compose.factor-bootstrap.yml}"
TIMESTAMP="$(date +%s)"
NO_BUILD="${NO_BUILD:-true}"
USE_EXISTING_POSTGRES="${USE_EXISTING_POSTGRES:-true}"
DATABASE_URL="${DATABASE_URL:-postgresql://postgres:mysecretpassword@192.168.31.119:5432/alpha_arena}"
SNAPSHOT_DATABASE_URL="${SNAPSHOT_DATABASE_URL:-postgresql://postgres:mysecretpassword@192.168.31.119:5432/alpha_snapshots}"

LIVE_MIN_OBSERVATION_HOURS="${LIVE_MIN_OBSERVATION_HOURS:-24}"
LIVE_MIN_TRADES="${LIVE_MIN_TRADES:-10}"
LIVE_MIN_NET_PNL="${LIVE_MIN_NET_PNL:-0}"
LIVE_MIN_WIN_RATE="${LIVE_MIN_WIN_RATE:-50}"
LIVE_MAX_DRAWDOWN_PERCENT="${LIVE_MAX_DRAWDOWN_PERCENT:-20}"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[error] missing command: $1" >&2
    exit 1
  }
}

require_cmd docker
require_cmd curl
require_cmd python

LOCAL_PROXY_PATTERN='(127\.0\.0\.1|localhost):[0-9]+'
PROXY_VARS=(http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy)

disable_localhost_proxy_if_needed() {
  local found_local_proxy="false"
  local var_name=""
  local var_value=""
  for var_name in "${PROXY_VARS[@]}"; do
    var_value="${!var_name:-}"
    if [[ -n "${var_value}" ]] && [[ "${var_value}" =~ ${LOCAL_PROXY_PATTERN} ]]; then
      found_local_proxy="true"
      break
    fi
  done

  if [[ "${found_local_proxy}" == "true" ]]; then
    echo "[warn] detected localhost proxy in environment (e.g. 127.0.0.1:7890)."
    echo "[warn] disabling proxy env for docker build/run to avoid container network failure."
    unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
  fi
}

disable_localhost_proxy_if_needed

build_arg() {
  if [[ "${NO_BUILD}" == "true" ]]; then
    echo "--no-build"
  else
    echo "--build"
  fi
}

validate_external_pg_config() {
  if [[ "${USE_EXISTING_POSTGRES}" != "true" ]]; then
    return 0
  fi
  if [[ -z "${DATABASE_URL}" ]]; then
    echo "[error] DATABASE_URL is required when USE_EXISTING_POSTGRES=true" >&2
    exit 1
  fi
  if [[ -z "${SNAPSHOT_DATABASE_URL}" ]]; then
    echo "[error] SNAPSHOT_DATABASE_URL is required when USE_EXISTING_POSTGRES=true" >&2
    exit 1
  fi
}

validate_external_pg_config

write_bootstrap_override() {
  if [[ "${USE_EXISTING_POSTGRES}" == "true" ]]; then
    cat > "${BOOTSTRAP_OVERRIDE_FILE}" <<EOF
services:
  app:
    depends_on: []
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      DATABASE_URL: "${DATABASE_URL}"
      SNAPSHOT_DATABASE_URL: "${SNAPSHOT_DATABASE_URL}"
EOF
  else
    cat > "${BOOTSTRAP_OVERRIDE_FILE}" <<EOF
services:
  app:
    environment: {}
EOF
  fi
}

create_account() {
  local account_name="$1"
  local account_id
  account_id="$(curl -sS -X POST "${BASE_URL}/api/account/" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"${account_name}\",\"account_type\":\"AI\",\"initial_capital\":10000,\"auto_trading_enabled\":false}" \
    | python -c 'import json,sys; d=json.load(sys.stdin); i=d.get("id"); assert i is not None, d; print(i)')"
  echo "${account_id}"
}

UP_ARG="$(build_arg)"
write_bootstrap_override

if [[ "${USE_EXISTING_POSTGRES}" == "true" ]]; then
  echo "[step] starting app with existing postgres (${UP_ARG}, --no-deps app)"
  docker compose -f docker-compose.yml -f "${BOOTSTRAP_OVERRIDE_FILE}" up -d "${UP_ARG}" --no-deps app
else
  echo "[step] docker compose up -d ${UP_ARG}"
  docker compose -f docker-compose.yml -f "${BOOTSTRAP_OVERRIDE_FILE}" up -d "${UP_ARG}"
fi

echo "[step] waiting for API readiness"
READY_DEADLINE=$(( $(date +%s) + READY_TIMEOUT_SECONDS ))
while true; do
  if curl -fsS "${BASE_URL}/api/health" >/dev/null 2>&1; then
    break
  fi
  if [[ "$(date +%s)" -ge "${READY_DEADLINE}" ]]; then
    echo "[error] API not ready within ${READY_TIMEOUT_SECONDS}s at ${BASE_URL}" >&2
    echo "[hint] recent app logs:" >&2
    docker compose logs --tail=120 app >&2 || true
    exit 3
  fi
  sleep 2
done

echo "[step] creating accounts"
PAPER_ACCOUNT_ID="$(create_account "paper-auto-${TIMESTAMP}")"
LIVE_ACCOUNT_ID="$(create_account "live-auto-${TIMESTAMP}")"
echo "[ok] PAPER_ACCOUNT_ID=${PAPER_ACCOUNT_ID}"
echo "[ok] LIVE_ACCOUNT_ID=${LIVE_ACCOUNT_ID}"

echo "[step] writing ${OVERRIDE_FILE}"
cat > "${OVERRIDE_FILE}" <<EOF
services:
  app:
$(if [[ "${USE_EXISTING_POSTGRES}" == "true" ]]; then cat <<EOI
    depends_on: []
    extra_hosts:
      - "host.docker.internal:host-gateway"
EOI
fi)
    environment:
$(if [[ "${USE_EXISTING_POSTGRES}" == "true" ]]; then cat <<EOI
      DATABASE_URL: "${DATABASE_URL}"
      SNAPSHOT_DATABASE_URL: "${SNAPSHOT_DATABASE_URL}"
EOI
fi)
      FACTOR_ENGINE_ENABLED: "true"
      FACTOR_RESEARCH_ENABLED: "true"
      FACTOR_RESEARCH_RUN_ON_STARTUP: "true"
      FACTOR_RESEARCH_INTERVAL_SECONDS: "${INTERVAL_SECONDS}"
      FACTOR_RESEARCH_EXCHANGE: "hyperliquid"
      FACTOR_RESEARCH_TOP_N_SYMBOLS: "${TOP_N_SYMBOLS}"
      FACTOR_RESEARCH_LOOKBACK_DAYS: "${LOOKBACK_DAYS}"
      FACTOR_RESEARCH_PRESCREEN_LIMIT: "${PRESCREEN_LIMIT}"
      FACTOR_RESEARCH_AUTO_PROMOTE_PAPER: "true"
      FACTOR_RESEARCH_PAPER_ACCOUNT_ID: "${PAPER_ACCOUNT_ID}"
      FACTOR_RESEARCH_AUTO_PROMOTE_LIVE: "true"
      FACTOR_RESEARCH_LIVE_ACCOUNT_ID: "${LIVE_ACCOUNT_ID}"
      FACTOR_RESEARCH_LIVE_MIN_OBSERVATION_HOURS: "${LIVE_MIN_OBSERVATION_HOURS}"
      FACTOR_RESEARCH_LIVE_MIN_TRADES: "${LIVE_MIN_TRADES}"
      FACTOR_RESEARCH_LIVE_MIN_NET_PNL: "${LIVE_MIN_NET_PNL}"
      FACTOR_RESEARCH_LIVE_MIN_WIN_RATE: "${LIVE_MIN_WIN_RATE}"
      FACTOR_RESEARCH_LIVE_MAX_DRAWDOWN_PERCENT: "${LIVE_MAX_DRAWDOWN_PERCENT}"
      FACTOR_RESEARCH_REQUIRE_LIVE_CONFIRM: "true"
EOF

echo "[step] applying override config"
if [[ "${USE_EXISTING_POSTGRES}" == "true" ]]; then
  docker compose -f docker-compose.yml -f "${OVERRIDE_FILE}" up -d "${UP_ARG}" --no-deps app
else
  docker compose -f docker-compose.yml -f "${OVERRIDE_FILE}" up -d "${UP_ARG}"
fi

echo "[step] triggering one research run"
TRIGGER_PAYLOAD="$(
python - <<PY
import json
print(json.dumps({
  "exchange": "hyperliquid",
  "top_n_symbols": int("${TOP_N_SYMBOLS}"),
  "lookback_days": int("${LOOKBACK_DAYS}"),
  "objective": "return_over_drawdown",
  "factor_scope": "builtin_only",
  "period": "1h",
  "prescreen_limit": int("${PRESCREEN_LIMIT}"),
  "auto_promote_paper": True,
  "paper_account_id": int("${PAPER_ACCOUNT_ID}"),
  "auto_promote_live": True,
  "live_account_id": int("${LIVE_ACCOUNT_ID}"),
  "live_min_observation_hours": float("${LIVE_MIN_OBSERVATION_HOURS}"),
  "live_min_trades": int("${LIVE_MIN_TRADES}"),
  "live_min_net_pnl": float("${LIVE_MIN_NET_PNL}"),
  "live_min_win_rate": float("${LIVE_MIN_WIN_RATE}"),
  "live_max_drawdown_percent": float("${LIVE_MAX_DRAWDOWN_PERCENT}")
}))
PY
)"

curl -sS -X POST "${BASE_URL}/api/factor-research/run" \
  -H "Content-Type: application/json" \
  -d "${TRIGGER_PAYLOAD}" >/dev/null

echo "[step] polling run status"
DEADLINE=$(( $(date +%s) + WAIT_TIMEOUT_SECONDS ))
FINAL_STATUS=""
LAST_RUN_STATUS=""
while true; do
  STATUS_JSON="$(curl -sS "${BASE_URL}/api/factor-research/status")"
  PARSED="$(
    printf '%s' "${STATUS_JSON}" | python -c 'import json,sys; d=json.load(sys.stdin); print(f"{d.get(\"status\",\"\")}|{d.get(\"last_run_status\",\"\")}")'
  )"
  FINAL_STATUS="${PARSED%%|*}"
  LAST_RUN_STATUS="${PARSED##*|}"
  echo "[status] status=${FINAL_STATUS} last_run_status=${LAST_RUN_STATUS}"
  if [[ "${FINAL_STATUS}" == "idle" && ( "${LAST_RUN_STATUS}" == "success" || "${LAST_RUN_STATUS}" == "error" ) ]]; then
    break
  fi
  if [[ "$(date +%s)" -ge "${DEADLINE}" ]]; then
    echo "[error] timeout waiting for run completion (${WAIT_TIMEOUT_SECONDS}s)" >&2
    exit 2
  fi
  sleep "${POLL_SECONDS}"
done

echo "[done] final status payload:"
curl -sS "${BASE_URL}/api/factor-research/status" | python -m json.tool

echo "[hint] tail logs with: docker compose logs -f app"
