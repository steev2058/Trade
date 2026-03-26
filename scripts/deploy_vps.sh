#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${1:-https://github.com/steev2058/Trade.git}"
APP_DIR="${2:-/opt/linkat-mj-trader}"
APP_USER="${3:-$USER}"

echo "[1/7] Install system deps"
sudo apt-get update -y
sudo apt-get install -y git python3 python3-venv python3-pip

echo "[2/7] Clone/Update repo"
if [ -d "$APP_DIR/.git" ]; then
  sudo git -C "$APP_DIR" pull --rebase
else
  sudo mkdir -p "$APP_DIR"
  sudo git clone "$REPO_URL" "$APP_DIR"
fi
sudo chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

echo "[3/7] Python venv"
cd "$APP_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[4/7] Env file"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created $APP_DIR/.env (edit credentials before live mode)."
fi

echo "[5/7] Prepare logs"
mkdir -p logs

echo "[6/7] Install systemd service"
sudo cp scripts/systemd.service.example /etc/systemd/system/linkat-mj-trader.service
sudo sed -i "s|/opt/linkat-mj-trader|$APP_DIR|g" /etc/systemd/system/linkat-mj-trader.service
sudo sed -i "s|EnvironmentFile=/opt/linkat-mj-trader/.env|EnvironmentFile=$APP_DIR/.env|g" /etc/systemd/system/linkat-mj-trader.service
sudo systemctl daemon-reload
sudo systemctl enable linkat-mj-trader

echo "[7/7] Done"
echo "Edit $APP_DIR/.env then start: sudo systemctl restart linkat-mj-trader"
echo "Check logs: sudo journalctl -u linkat-mj-trader -f"
