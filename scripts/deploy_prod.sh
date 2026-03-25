#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_ARCHIVE="${FRONTEND_ARCHIVE:-frontend-dist.tar.gz}"
APP_MODULE="${APP_MODULE:-main:app}"
APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-8000}"
LOG_FILE="${LOG_FILE:-app.log}"
PID_FILE="${PID_FILE:-.run/uvicorn.pid}"
WAIT_SECONDS="${WAIT_SECONDS:-45}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:${APP_PORT}/api/health}"
NO_PULL="${NO_PULL:-false}"
NO_FRONTEND="${NO_FRONTEND:-false}"

cd "${ROOT_DIR}"
mkdir -p "$(dirname "${PID_FILE}")"

if [[ "${NO_PULL}" != "true" ]]; then
  git pull --ff-only
fi

if [[ "${NO_FRONTEND}" != "true" ]]; then
  if [[ -f "${FRONTEND_ARCHIVE}" ]]; then
    echo "[deploy] Using prebuilt frontend archive: ${FRONTEND_ARCHIVE}"
    rm -rf backend/static
    mkdir -p backend/static
    tar -xzf "${FRONTEND_ARCHIVE}" -C backend/static --strip-components=1
  else
    echo "[deploy] No ${FRONTEND_ARCHIVE} found, building frontend on server..."
    pnpm --dir frontend build
    rm -rf backend/static
    cp -r frontend/dist backend/static
  fi
fi

if [[ -f "${PID_FILE}" ]]; then
  OLD_PID="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${OLD_PID}" ]] && kill -0 "${OLD_PID}" >/dev/null 2>&1; then
    echo "[deploy] Stopping existing backend pid=${OLD_PID}"
    kill "${OLD_PID}" || true
    for _ in $(seq 1 10); do
      if ! kill -0 "${OLD_PID}" >/dev/null 2>&1; then
        break
      fi
      sleep 1
    done
    if kill -0 "${OLD_PID}" >/dev/null 2>&1; then
      kill -9 "${OLD_PID}" || true
    fi
  fi
fi

cd backend
nohup uv run uvicorn "${APP_MODULE}" --host "${APP_HOST}" --port "${APP_PORT}" > "${ROOT_DIR}/${LOG_FILE}" 2>&1 &
NEW_PID="$!"
cd "${ROOT_DIR}"

echo "${NEW_PID}" > "${PID_FILE}"
echo "[deploy] Started backend pid=${NEW_PID}, log=${ROOT_DIR}/${LOG_FILE}"

for _ in $(seq 1 "${WAIT_SECONDS}"); do
  if curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; then
    echo "[deploy] Health check passed: ${HEALTH_URL}"
    exit 0
  fi
  if ! kill -0 "${NEW_PID}" >/dev/null 2>&1; then
    echo "[deploy] Backend exited unexpectedly. Last logs:"
    tail -n 120 "${LOG_FILE}" || true
    exit 1
  fi
  sleep 1
done

echo "[deploy] Health check timeout after ${WAIT_SECONDS}s: ${HEALTH_URL}"
tail -n 120 "${LOG_FILE}" || true
exit 1
