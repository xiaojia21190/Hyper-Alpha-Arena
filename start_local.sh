#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

git pull

pnpm --dir frontend build
rm -rf backend/static
cp -r frontend/dist backend/static

cd backend
nohup uv run uvicorn main:app --host 0.0.0.0 --port 8000 > "${ROOT_DIR}/app.log" 2>&1 &
echo "Started backend in background. PID=$!, log=${ROOT_DIR}/app.log"
