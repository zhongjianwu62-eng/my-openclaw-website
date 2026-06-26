#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/var/www/openclaw-trading-bot"
PUBLIC_DIR="/var/www/openclaw-trading-bot"
BRANCH="main"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "Step 1/6: entering app directory: ${APP_DIR}"
cd "${APP_DIR}"

log "Step 2/6: fetching latest code from origin/${BRANCH}"
git fetch origin "${BRANCH}"

log "Step 3/6: resetting local code"
git reset --hard "origin/${BRANCH}"

log "Step 4/6: ensuring static files are present"
test -f index.html
test -f status.json
test -f trades.json
test -f thinking.json
test -f strategy_v2.json

log "Step 5/6: testing nginx configuration"
sudo nginx -t

log "Step 6/6: reloading nginx"
sudo systemctl reload nginx

log "Deployment completed: ${PUBLIC_DIR}"
