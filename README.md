# Linkat MJ Trader (Production-Safe Execution Engine)

Linkat MJ Trader هو **محرك تنفيذ تداول آمن** مع MT5 + Telegram.

المنظومة الآن تدعم:
- استراتيجيات داخلية متعددة
- تكامل خارجي مع **Dexter** و **TradingAgents** كمصادر تحليل فقط
- **Trade repo** يبقى الجهة الوحيدة المخولة بالتنفيذ الفعلي
- حوكمة مخاطر صارمة + سجل تدقيق (Audit) + إشعارات تشغيلية

> ⚠️ مبدأ أساسي: أي غموض في التقييم/الميتاداتا أو تعارض قرار => **HOLD / NO TRADE**.

---

## 1) Architecture (3 Layers)

### Layer 1 — Market & Risk Gate
قبل أي تنفيذ:
- فحص الوضع (`paper` / `live`)
- فحص حدود المخاطر (max daily loss / max trades / max open positions / balance protection)
- فحص صلاحية الرمز والـ valuation (`point_value`, `point_size`)
- block عند الغموض (خصوصًا live)

### Layer 2 — Intelligence
- **Dexter**: تحليل بحثي مالي فقط (analysis-only)
- **TradingAgents**: قرار لجنة فقط (analysis-only)
- لا يوجد أي تنفيذ مباشر من أي منهما

### Layer 3 — Execution Authority (Trade repo only)
- بناء قرار موحّد deterministic consensus
- تمرير القرار على فلاتر المخاطر
- التنفيذ عبر MT5 Adapter فقط (live)
- أو simulation في paper
- إرسال Telegram + كتابة Audit JSONL

---

## 2) Core Safety Guarantees

- Trade repo هو **الوحيد** الذي ينفّذ الأوامر.
- Dexter/TradingAgents لا يستطيعان إرسال أوامر MT5.
- عند:
  - غياب أحد المصدرين
  - تعارض بينهما
  - do_not_trade من أي طرف
  - confidence أقل من الحد
  - فشل health checks (عند التفعيل)
  => القرار النهائي **HOLD**.
- **Strict point-value validator**:
  - في live: block إجباري عند ambiguity
  - في paper: `warn` أو `block` حسب الإعداد

---

## 3) Fixed USD Risk/Reward Model

منطق المخاطر النقدية ثابت ومربوط باللوت:
- lot `0.01` => SL `$5` / TP `$15`
- lot `0.02` => SL `$10` / TP `$30`
- RR = `1:3`

الصيغة:
- `risk_amount_usd = lot_size * 500`
- `reward_amount_usd = risk_amount_usd * 3`

ثم التحويل لنقاط/أسعار يتم عبر symbol valuation (point/tick).
إذا valuation غير موثوق => **NO TRADE**.

---

## 4) Project Structure

- `app/main.py` — entrypoint
- `app/core/runner.py` — loop orchestration + decision + execution
- `app/core/settings.py` — config/env
- `app/risk/engine.py` — risk guardrails
- `app/brokers/mt5_adapter.py` — MT5 bridge adapter
- `bridge/windows/mt5_bridge.py` — Windows MT5 execution bridge
- `app/storage/audit.py` — JSONL audit logger

### Strategies
- `app/strategies/smc_ict.py`
- `app/strategies/scalper.py`
- `app/strategies/sr_fvg.py`
- `app/strategies/london_ny_session.py`
- `app/strategies/news.py`
- `app/strategies/adaptive_weighting.py`
- `app/strategies/regime_switcher.py`
- `app/strategies/simple_signal.py`
- `app/strategies/ict_signal.py`

### External Agents Integration
- `app/agents/dexter_client.py`
- `app/agents/tradingagents_client.py`
- `app/decision/schemas.py`
- `app/decision/consensus.py`
- `app/services/market_context.py`
- `app/services/external_agent_health.py`
- `docs/DEXTER_TRADINGAGENTS_INTEGRATION.md`

---

## 5) Telegram Commands

أوامر التحكم (authorized chat only):

- `/status`
- `/pause`, `/resume`
- `/paper`, `/live CONFIRM`
- `/positions`, `/balance`, `/pnl`
- `/today`, `/report`
- `/auto_on`, `/auto_off`
- `/buy SYMBOL LOT`, `/sell SYMBOL LOT`
- `/close TICKET`, `/close_all CONFIRM`
- `/sl_tp TICKET SL TP`
- `/symbols`, `/set_symbols A,B,C`
- `/risk`
- `/set_mode safe|normal|aggressive`
- `/strategies`
- `/enable <strategy>`
- `/disable <strategy>`
- `/strict_point_value on|off`

---

## 6) Environment Variables (Important)

### Core / Runtime
- `MODE=paper|live`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `BRIDGE_API_BASE`
- `BRIDGE_TOKEN`

### Risk / Execution
- `STRICT_POINT_VALUE_VALIDATION=true|false`
- `PAPER_VALUATION_POLICY=warn|block`
- `RISK_MODE=safe|normal|aggressive`
- `MAX_DAILY_LOSS`
- `MAX_TRADES_PER_DAY`
- `MAX_CONCURRENT_POSITIONS`
- `MIN_BALANCE_PROTECTION`
- `COOLDOWN_AFTER_LOSSES`

### External Agents
- `DEXTER_ENABLED=true|false`
- `DEXTER_BASE_URL=http://dexter-service:8081`
- `DEXTER_TIMEOUT_SECONDS=45`
- `TRADING_AGENTS_ENABLED=true|false`
- `TRADING_AGENTS_BASE_URL=http://tradingagents-service:8082`
- `TRADING_AGENTS_TIMEOUT_SECONDS=60`
- `CONSENSUS_MIN_CONFIDENCE=0.75`

---

## 7) Setup

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 8) Run

Paper:
```bash
python -m app.main --mode paper
```

Live:
```bash
python -m app.main --mode live --confirm-live YES_I_ACCEPT_LIVE_TRADING
```

---

## 9) Tests

```bash
./.venv/bin/python -m pytest -q tests
```

يشمل اختبارات consensus + حالات HOLD safety + valuation/context.

---

## 10) Deployment Notes

- تأكد تحديث Windows bridge عند أي تعديل متعلق بالتقييم/التنفيذ.
- راقب `logs/audit.jsonl` لأي سبب رفض.
- لا تفعّل live قبل التحقق في paper.

---

## 11) Documentation

مستند التكامل الخارجي الكامل:
- `docs/DEXTER_TRADINGAGENTS_INTEGRATION.md`
