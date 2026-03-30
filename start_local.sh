#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ENV_FILE="${ROOT_DIR}/backend/.env"

# Load backend/.env first so it can control runtime profile/watcher defaults.
# Preserve explicitly provided shell env values as highest priority.
if [[ -f "${BACKEND_ENV_FILE}" ]]; then
  APP_RUNTIME_PROFILE_WAS_SET="${APP_RUNTIME_PROFILE+x}"
  FRONTEND_WATCHER_ENABLED_WAS_SET="${FRONTEND_WATCHER_ENABLED+x}"
  APP_RUNTIME_PROFILE_ORIG="${APP_RUNTIME_PROFILE-}"
  FRONTEND_WATCHER_ENABLED_ORIG="${FRONTEND_WATCHER_ENABLED-}"

  set -a
  # shellcheck disable=SC1090
  source "${BACKEND_ENV_FILE}"
  set +a

  if [[ -n "${APP_RUNTIME_PROFILE_WAS_SET}" ]]; then
    APP_RUNTIME_PROFILE="${APP_RUNTIME_PROFILE_ORIG}"
  fi
  if [[ -n "${FRONTEND_WATCHER_ENABLED_WAS_SET}" ]]; then
    FRONTEND_WATCHER_ENABLED="${FRONTEND_WATCHER_ENABLED_ORIG}"
  fi
fi

APP_PORT="${PORT:-8000}" \
APP_RUNTIME_PROFILE="${APP_RUNTIME_PROFILE:-factor}" \
FRONTEND_WATCHER_ENABLED="${FRONTEND_WATCHER_ENABLED:-false}" \
exec bash "${ROOT_DIR}/scripts/deploy_prod.sh"
