#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_ARCHIVE="${FRONTEND_ARCHIVE:-frontend-dist.tar.gz}"
PORT="${PORT:-8000}"

cd "${ROOT_DIR}"

git pull

if [[ -f "${FRONTEND_ARCHIVE}" ]]; then
  echo "Using prebuilt frontend archive: ${FRONTEND_ARCHIVE}"
  rm -rf backend/static
  mkdir -p backend/static
  tar -xzf "${FRONTEND_ARCHIVE}" -C backend/static --strip-components=1
else
  echo "No ${FRONTEND_ARCHIVE} found, building frontend on this machine..."
  pnpm --dir frontend build
  rm -rf backend/static
  cp -r frontend/dist backend/static
fi

cd backend
nohup uv run uvicorn main:app --host 0.0.0.0 --port "${PORT}" > "${ROOT_DIR}/app.log" 2>&1 &
echo "Started backend in background. PID=$!, log=${ROOT_DIR}/app.log"
