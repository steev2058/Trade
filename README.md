# Linkat MJ Trader (Production-Safe Scaffold)

Professional, safety-first trading bot scaffold with MT5 integration, Telegram control plane, audit logging, risk guardrails, and regime-aware strategy routing.

> ⚠️ This repository is intentionally conservative. It does **not** implement unrestricted autonomous execution.

## Architecture

- `app/main.py` - entrypoint (`paper`/`live` mode with explicit live confirmation)
- `app/core/runner.py` - orchestration loop, risk checks, regime switching, command callbacks
- `app/core/settings.py` - environment-based config
- `app/risk/engine.py` - pre-trade risk constraints
- `app/brokers/mt5_adapter.py` - broker adapter (safe paper no-op + live stubs)
- `app/strategies/` - strategy modules and regime switcher:
  - `smc_ict.py`
  - `scalper.py`
  - `news.py`
  - `adaptive_weighting.py`
  - `london_ny_session.py`
  - `regime_switcher.py`
- `app/notifiers/telegram_controller.py` - Telegram command handlers (authorized chat only)
- `app/notifiers/telegram_notifier.py` - outbound Telegram notifications
- `app/storage/audit.py` - append-only JSONL audit logs

## Safety Model

- Runtime modes: `paper` (default) and `live`
- Live start requires: `--confirm-live YES_I_ACCEPT_LIVE_TRADING`
- Telegram control is restricted to configured `TELEGRAM_CHAT_ID`
- `/close_all` requires explicit argument `CONFIRM`
- In paper mode, broker close calls are safe no-ops
- Risk limits enforced before strategy signal processing:
  - max risk per trade
  - max daily loss
  - max trades/day
  - max concurrent positions

## Strategy & Regime Layer

Implemented strategy scaffolds:

1. **SMC/ICT** (`smc_ict`) - session- and structure-aware placeholder logic
2. **Scalper** (`scalper`) - low-latency micro-momentum scaffold
3. **News** (`news`) - high-impact event sentiment scaffold
4. **Adaptive Weighting** (`adaptive_weighting`) - weighted consensus combiner scaffold
5. **London-NY Session** (`london_ny_session`) - overlap breakout scaffold

`RegimeSwitcher` chooses/weights active strategies by:
- volatility regime
- trading session
- high-impact news flag

## Telegram Commands

All commands are authorized-chat only.

- `/status`
- `/pause`
- `/resume`
- `/paper`
- `/live CONFIRM`
- `/positions`
- `/balance`
- `/pnl`
- `/close_all CONFIRM`

## Environment Setup

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Fill `.env` at minimum:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- MT5 credentials (required for live broker connectivity)

## Run

Paper mode:
```bash
python -m app.main --mode paper
```

Live mode:
```bash
python -m app.main --mode live --confirm-live YES_I_ACCEPT_LIVE_TRADING
```

## VPS Deployment

One-command deploy:
```bash
bash scripts/deploy_vps.sh https://github.com/steev2058/Trade.git /opt/linkat-mj-trader
```

Then on VPS:
1. Configure `/opt/linkat-mj-trader/.env`
2. Verify paper mode runtime first
3. Enable service using `scripts/systemd.service.example`
4. Promote to live only after paper verification and operator sign-off

Detailed guide: `QUICKSTART_VPS.md`
