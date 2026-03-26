# Linkat MJ Trader (Professional Safe Autotrader)

Production-oriented trading agent scaffold with MT5 + Telegram integration, audit logging, risk controls, reconnect/restart patterns, and secure secrets handling.

## Features
- MT5 broker adapter (primary)
- Strategy engine (scalping/swing/news hooks)
- Risk engine (max risk per trade, daily loss cap, circuit breaker)
- Telegram bot notifications + control commands
- Full audit trail (JSONL)
- Runtime modes: `paper` and `live`
- Guardrails for live mode (kill-switch, max trades/day, max concurrent positions)
- Auto-reconnect loop and health heartbeat

## Quick Start
1. `cp .env.example .env`
2. Fill credentials/secrets
3. `python -m venv .venv && source .venv/bin/activate`
4. `pip install -r requirements.txt`
5. `python -m app.main --mode paper`

## VPS One-Command Deploy
```bash
bash scripts/deploy_vps.sh https://github.com/steev2058/Trade.git /opt/linkat-mj-trader
```
Detailed guide: `QUICKSTART_VPS.md`

## Live mode
Use only after verifying in paper mode:

```bash
python -m app.main --mode live --confirm-live YES_I_ACCEPT_LIVE_TRADING
```

## Safety note
This project intentionally includes guardrails and does **not** support unrestricted no-confirmation account takeover.
