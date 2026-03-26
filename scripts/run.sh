#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate || true
python -m app.main --mode "${MODE:-paper}" ${LIVE_CONFIRM:+--confirm-live YES_I_ACCEPT_LIVE_TRADING}
