#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCHIVE_NAME="${1:-frontend-dist.tar.gz}"

cd "${ROOT_DIR}"

pnpm --dir frontend build
tar -C frontend -czf "${ARCHIVE_NAME}" dist

echo "Created frontend build archive: ${ROOT_DIR}/${ARCHIVE_NAME}"
echo "Upload it to your server project root, then run: bash start_local.sh"
