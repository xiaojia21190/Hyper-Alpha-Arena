#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APP_PORT="${PORT:-8000}" exec bash "${ROOT_DIR}/scripts/deploy_prod.sh"
