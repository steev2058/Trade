#!/usr/bin/env bash
set -euo pipefail
SERVICE=linkat-mj-trader
if ! systemctl is-active --quiet "$SERVICE"; then
  systemctl restart "$SERVICE"
  echo "[$(date -Is)] restarted $SERVICE"
else
  echo "[$(date -Is)] $SERVICE healthy"
fi
