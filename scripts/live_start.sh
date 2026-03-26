#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
python -m app.main --mode live --confirm-live YES_I_ACCEPT_LIVE_TRADING
