# VPS Quickstart (Ubuntu/Debian)

## 1) Deploy
```bash
bash scripts/deploy_vps.sh https://github.com/steev2058/Trade.git /opt/linkat-mj-trader
```

## 2) Configure credentials
Edit:
```bash
nano /opt/linkat-mj-trader/.env
```
Set at least:
- `MT5_LOGIN`
- `MT5_PASSWORD`
- `MT5_SERVER`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## 3) Test paper mode
```bash
cd /opt/linkat-mj-trader
source .venv/bin/activate
python -m app.main --mode paper
```

## 4) Start service
```bash
sudo systemctl restart linkat-mj-trader
sudo systemctl status linkat-mj-trader
```

## 5) Start live manually (one-click)
```bash
cd /opt/linkat-mj-trader && bash scripts/live_start.sh
```

## 6) Logs
```bash
sudo journalctl -u linkat-mj-trader -f
cat /opt/linkat-mj-trader/logs/audit.jsonl | tail -n 20
```
