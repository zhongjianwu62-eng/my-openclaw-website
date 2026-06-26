#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASE_DIR="${ROOT_DIR}/release"
PACKAGE_NAME="openclaw-trading-bot-lite.tar.gz"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "Preparing release directory"
rm -rf "${RELEASE_DIR}"
mkdir -p "${RELEASE_DIR}/openclaw-trading-bot"

log "Copying static files"
cp "${ROOT_DIR}/index.html" "${RELEASE_DIR}/openclaw-trading-bot/"
cp "${ROOT_DIR}/status.json" "${RELEASE_DIR}/openclaw-trading-bot/"
cp "${ROOT_DIR}/trades.json" "${RELEASE_DIR}/openclaw-trading-bot/"
cp "${ROOT_DIR}/thinking.json" "${RELEASE_DIR}/openclaw-trading-bot/"
cp "${ROOT_DIR}/strategy_v2.json" "${RELEASE_DIR}/openclaw-trading-bot/"
cp "${ROOT_DIR}/README.md" "${RELEASE_DIR}/openclaw-trading-bot/"
cp "${ROOT_DIR}/deploy.sh" "${RELEASE_DIR}/openclaw-trading-bot/"
cp "${ROOT_DIR}/nginx-openclaw.conf" "${RELEASE_DIR}/openclaw-trading-bot/"

log "Creating compressed package"
tar -czf "${RELEASE_DIR}/${PACKAGE_NAME}" -C "${RELEASE_DIR}" openclaw-trading-bot

log "Release created: ${RELEASE_DIR}/${PACKAGE_NAME}"
