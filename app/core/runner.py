import asyncio
import logging
from datetime import datetime, timezone
from collections import defaultdict, deque

from app.core.settings import settings
from app.core.logging import setup_logging
from app.brokers.mt5_adapter import MT5Adapter
from app.notifiers.telegram_notifier import TelegramNotifier
from app.notifiers.telegram_controller import TelegramController
from app.storage.audit import AuditStore
from app.storage.trade_journal import TradeJournal
from app.risk.engine import RiskEngine
from app.strategies.news import NewsStrategy
from app.strategies.scalper import ScalperStrategy
from app.strategies.smc_ict import SmcIctStrategy
from app.strategies.adaptive_weighting import AdaptiveWeightingStrategy
from app.strategies.london_ny_session import LondonNySessionStrategy
from app.strategies.regime_switcher import RegimeSwitcher
from app.strategies.simple_signal import SimpleSignalStrategy
from app.strategies.sr_fvg import SrFvgStrategy
from app.strategies.ict_signal import IctSignalStrategy
from app.agents.dexter_client import analyze_with_dexter
from app.agents.tradingagents_client import analyze_with_tradingagents
from app.decision.consensus import build_unified_decision
from app.services.external_agent_health import check_dexter_health, check_tradingagents_health
from app.services.market_context import build_market_context
from app.execution.protected_executor import execute_protected_trade


class TradingRunner:
    def __init__(self, mode: str = "paper"):
        setup_logging(settings.log_level)
        self.log = logging.getLogger("runner")
        self.mode = mode
        self.audit = AuditStore()
        self.journal = TradeJournal()
        self.notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
        self.paused = False
        self.auto_enabled = bool(settings.auto_trading_enabled)
        self.last_auto_ts = 0.0
        self.last_no_trade_notify_ts = 0.0
        self.watch_symbols = [s.strip() for s in str(settings.watch_symbols or '').split(',') if s.strip()]
        self.risk_mode = (settings.risk_mode or "balanced").lower().strip()
        self.strict_point_value_validation = bool(settings.strict_point_value_validation)
        self.require_protected_execution = bool(settings.require_protected_execution)
        self.price_history = defaultdict(lambda: deque(maxlen=200))
        self.strategy_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "n": 0})
        self.open_trade_ctx = {}  # ticket -> context
        self.day_start_balance = None
        self.day_key = datetime.now(timezone.utc).date().isoformat()
        self.last_dd_alert_ts = 0.0
        self.last_tp_alert_ts = 0.0
        self.controller = TelegramController(
            settings.telegram_bot_token,
            settings.telegram_chat_id,
            callbacks={
                "status": self._status_text,
                "pause": self._pause,
                "resume": self._resume,
                "switch_mode": self._switch_mode,
                "positions": self._positions_text,
                "balance": self._balance_text,
                "pnl": self._pnl_text,
                "close_all": self._close_all,
                "open": self._open_order,
                "close": self._close_ticket,
                "sl_tp": self._set_sl_tp,
                "auto_on": self._auto_on,
                "auto_off": self._auto_off,
                "report": self._report,
                "symbols": self._symbols_text,
                "set_symbols": self._set_symbols,
                "risk": self._risk_text,
                "set_risk_mode": self._set_risk_mode,
                "today": self._today,
                "strategies": self._strategies,
                "enable_strategy": self._enable_strategy,
                "disable_strategy": self._disable_strategy,
                "strict_point_value": self._set_strict_point_value,
                "safe_preset": self._safe_preset,
            },
        )
        self.risk = RiskEngine(
            settings.risk_percent_per_trade if settings.risk_percent_per_trade else settings.max_risk_per_trade,
            settings.max_daily_loss,
            settings.max_trades_per_day,
            settings.max_concurrent_positions,
            settings.min_balance_protection,
            settings.cooldown_after_losses,
            settings.min_lot_size if settings.min_lot_size else settings.min_allowed_lot,
            settings.max_lot_size if settings.max_lot_size else settings.max_allowed_lot,
            settings.usd_stop_per_0_01_lot,
            settings.rr_ratio,
        )
        self.broker = MT5Adapter(
            settings.mt5_login,
            settings.mt5_password,
            settings.mt5_server,
            settings.mt5_path,
            mode=self.mode,
            bridge_api_base=settings.bridge_api_base,
            bridge_token=settings.bridge_token,
        )
        self.regime = RegimeSwitcher()
        self.signal_strategy = SimpleSignalStrategy()
        self.sr_fvg_strategy = SrFvgStrategy()
        self.ict_strategy = IctSignalStrategy()
        self.strategies = []
        if settings.enable_smc_ict:
            self.strategies.append(SmcIctStrategy())
        if settings.enable_scalper:
            self.strategies.append(ScalperStrategy())
        if settings.enable_news:
            self.strategies.append(NewsStrategy())
        if settings.enable_adaptive_weighting:
            self.strategies.append(AdaptiveWeightingStrategy())
        if settings.enable_london_ny_session:
            self.strategies.append(LondonNySessionStrategy())
        if settings.enable_sr_fvg:
            self.strategies.append(self.sr_fvg_strategy)
        self.strategies.append(self.ict_strategy)
        self.strategies.append(self.signal_strategy)
        self.strategy_enabled = {s.name: True for s in self.strategies}

    def _status_text(self) -> str:
        return f"mode={self.mode} | paused={self.paused} | auto={self.auto_enabled} | risk_mode={self.risk_mode} | strategies={len(self.strategies)}"

    def _positions_text(self) -> str:
        positions = self.broker.get_positions()
        if not positions:
            return f"positions=0 | mode={self.mode}"
        head = [f"positions={len(positions)} | mode={self.mode}"]
        for p in positions[:10]:
            head.append(
                f"#{p.get('ticket')} {p.get('symbol')} {p.get('type')} vol={p.get('volume')} pnl={p.get('profit')}"
            )
        return "\n".join(head)

    def _balance_text(self) -> str:
        bal = self.broker.get_balance()
        return (
            f"mode={bal.get('mode')} | balance={bal.get('balance')} {bal.get('currency')} "
            f"| equity={bal.get('equity')}"
        )

    def _pnl_text(self) -> str:
        pnl = self.broker.get_pnl()
        return f"mode={pnl.get('mode')} | positions={pnl.get('positions')} | open_pnl={pnl.get('open_pnl')}"

    def _close_all(self) -> str:
        res = self.broker.close_all_positions()
        self.audit.log("control_close_all", res)
        self.journal.append("close_all", res)
        return f"close_all result: {res}"

    def _open_order(self, symbol: str, side: str, lot: float) -> str:
        res = self.broker.open_order(symbol, side, lot)
        self.audit.log("control_open", {"symbol": symbol, "side": side, "lot": lot, "result": res})
        self.journal.append("open", res, symbol=symbol, side=side, lot=lot, ticket=res.get("order") or "")
        return f"open result: {res}"

    def _close_ticket(self, ticket: int) -> str:
        res = self.broker.close_ticket(ticket)
        self.audit.log("control_close", {"ticket": ticket, "result": res})
        self.journal.append("close", res, ticket=ticket)
        return f"close result: {res}"

    def _set_sl_tp(self, ticket: int, sl: float, tp: float) -> str:
        res = self.broker.set_sl_tp(ticket, sl, tp)
        self.audit.log("control_sl_tp", {"ticket": ticket, "sl": sl, "tp": tp, "result": res})
        return f"sl_tp result: {res}"

    def _auto_on(self) -> str:
        self.auto_enabled = True
        self.audit.log("auto_on", {})
        return "✅ auto trading enabled"

    def _auto_off(self) -> str:
        self.auto_enabled = False
        self.audit.log("auto_off", {})
        return "🛑 auto trading disabled"

    def _report(self) -> str:
        bal = self.broker.get_balance()
        pnl = self.broker.get_pnl()
        today = self._today()
        return (
            f"Daily Summary\n"
            f"balance={bal.get('balance')} {bal.get('currency')}\n"
            f"equity={bal.get('equity')}\n"
            f"positions={pnl.get('positions')}\n"
            f"open_pnl={pnl.get('open_pnl')}\n"
            f"auto={self.auto_enabled} | risk_mode={self.risk_mode}\n"
            f"{today}"
        )

    def _symbols_text(self) -> str:
        return "watch_symbols=" + ",".join(self.watch_symbols or [settings.auto_default_symbol])

    def _set_symbols(self, csv_symbols: str) -> str:
        syms = [s.strip() for s in str(csv_symbols or '').split(',') if s.strip()]
        if not syms:
            return "Use: /set_symbols XAUUSD.m,BRENT.m,BTCUSD.m,ETHUSD.m"
        self.watch_symbols = syms
        self.audit.log("set_symbols", {"watch_symbols": self.watch_symbols})
        return "✅ watch_symbols=" + ",".join(self.watch_symbols)

    def _risk_text(self) -> str:
        if self.risk_mode == "aggressive":
            vol = 0.02
        elif self.risk_mode in {"conservative", "safe"}:
            vol = 0.01
        else:
            vol = 0.01
        risk_usd = vol * 500
        reward_usd = risk_usd * 3
        return f"risk_mode={self.risk_mode} | volume={vol} | risk=${risk_usd:.2f} | reward=${reward_usd:.2f} | RR=1:3 | strict_point_value={self.strict_point_value_validation} | require_protected={self.require_protected_execution} | paper_policy={settings.paper_valuation_policy}"

    def _set_risk_mode(self, mode: str) -> str:
        m = (mode or "").lower().strip()
        if m not in {"safe", "conservative", "normal", "balanced", "aggressive"}:
            return "Use: /set_mode conservative|balanced|aggressive"
        if m in {"safe", "normal"}:
            m = "balanced" if m == "normal" else "conservative"
        self.risk_mode = m
        self.audit.log("set_risk_mode", {"mode": m})
        return f"✅ risk mode set to {m}"

    def _today(self) -> str:
        bal = self.broker.get_balance()
        cur = float(bal.get("balance", 0.0) or 0.0)
        base = float(self.day_start_balance or cur)
        delta = cur - base
        pct = (delta / base * 100.0) if base > 0 else 0.0
        return f"today pnl=${delta:.2f} ({pct:.2f}%) | baseline=${base:.2f} | balance=${cur:.2f}"

    def _strategies(self) -> str:
        lines = ["strategies:"]
        for s in self.strategies:
            st = self.strategy_stats.get(s.name, {"wins": 0, "losses": 0, "n": 0})
            en = self.strategy_enabled.get(s.name, True)
            wr = (st["wins"] / st["n"] * 100.0) if st["n"] else 0.0
            lines.append(f"- {s.name}: {'ON' if en else 'OFF'} | n={st['n']} | wr={wr:.1f}%")
        return "\n".join(lines)

    def _enable_strategy(self, name: str) -> str:
        n = (name or "").strip().lower()
        if n not in self.strategy_enabled:
            return f"unknown strategy: {n}"
        self.strategy_enabled[n] = True
        self.audit.log("enable_strategy", {"strategy": n})
        return f"✅ enabled {n}"

    def _disable_strategy(self, name: str) -> str:
        n = (name or "").strip().lower()
        if n not in self.strategy_enabled:
            return f"unknown strategy: {n}"
        self.strategy_enabled[n] = False
        self.audit.log("disable_strategy", {"strategy": n})
        return f"🛑 disabled {n}"

    def _set_strict_point_value(self, val: str) -> str:
        v = (val or "").strip().lower()
        if v not in {"on", "off"}:
            return "Use: /strict_point_value on|off"
        self.strict_point_value_validation = (v == "on")
        self.audit.log("strict_point_value_toggle", {"enabled": self.strict_point_value_validation})
        return f"✅ strict_point_value={self.strict_point_value_validation}"

    def _safe_preset(self) -> str:
        self.risk_mode = "balanced"
        self.strict_point_value_validation = True
        self.require_protected_execution = True
        self.watch_symbols = ["XAUUSD.m", "BRENT.m"]
        self.audit.log("safe_preset", {
            "risk_mode": self.risk_mode,
            "strict_point_value_validation": self.strict_point_value_validation,
            "require_protected_execution": self.require_protected_execution,
            "watch_symbols": self.watch_symbols,
        })
        return "🛡️ Safe preset applied: balanced | strict ON | protected ON | symbols=XAUUSD.m,BRENT.m"

    def _pause(self):
        self.paused = True
        self.audit.log("control_pause", {})

    def _resume(self):
        self.paused = False
        self.audit.log("control_resume", {})

    def _switch_mode(self, mode: str):
        mode = (mode or "").lower().strip()
        if mode not in {"paper", "live"}:
            return
        if mode == self.mode:
            return
        self.mode = mode
        self.broker.set_mode(mode)
        if mode == "live":
            self.broker.connect()
            self.audit.log("broker_connected", {"server": settings.mt5_server})
        self.audit.log("control_mode_switch", {"mode": self.mode})

    def _in_hhmm_range(self, hh: int, mm: int, start_end: str) -> bool:
        try:
            cur = hh * 60 + mm
            a, b = str(start_end).split('-')
            ah, am = [int(x) for x in a.split(':')]
            bh, bm = [int(x) for x in b.split(':')]
            return (ah * 60 + am) <= cur <= (bh * 60 + bm)
        except Exception:
            return False

    def _ema(self, values, period: int):
        if not values:
            return 0.0
        alpha = 2 / (period + 1)
        ema = values[0]
        for v in values[1:]:
            ema = alpha * v + (1 - alpha) * ema
        return float(ema)

    def _rsi(self, values, period: int = 7):
        if len(values) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, len(values)):
            d = values[i] - values[i - 1]
            gains.append(max(d, 0))
            losses.append(max(-d, 0))
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100 - (100 / (1 + rs)))

    def _update_price_history(self):
        ticks = self.broker.get_ticks() or {}
        for sym, t in ticks.items():
            px = float(t.get('last') or t.get('bid') or 0.0)
            if px > 0:
                self.price_history[sym].append(px)



    def _roll_day_if_needed(self, now_ts: float):
        day_now = datetime.now(timezone.utc).date().isoformat()
        if day_now != self.day_key:
            self.day_key = day_now
            bal = self.broker.get_balance()
            self.day_start_balance = float(bal.get("balance", 0.0) or 0.0)
            self.auto_enabled = bool(settings.auto_trading_enabled)
            self.last_dd_alert_ts = 0.0
            self.last_tp_alert_ts = 0.0
            self.audit.log("day_roll_reset", {"day": self.day_key, "day_start_balance": self.day_start_balance})
            try:
                import asyncio
                asyncio.create_task(self.notifier.send(f"🗓 Day reset: baseline={self.day_start_balance} | auto={self.auto_enabled}"))
            except Exception:
                pass

    def _check_daily_drawdown_stop(self, now_ts: float) -> bool:
        bal = self.broker.get_balance()
        cur = float(bal.get("balance", 0.0) or 0.0)
        if cur <= 0:
            return False
        if self.day_start_balance is None:
            self.day_start_balance = cur
            return False

        dd_pct = ((self.day_start_balance - cur) / self.day_start_balance) * 100.0
        if dd_pct >= float(settings.daily_drawdown_limit_pct):
            if self.auto_enabled:
                self.auto_enabled = False
                self.audit.log("auto_off_drawdown", {"drawdown_pct": dd_pct, "limit_pct": settings.daily_drawdown_limit_pct})
            if now_ts - self.last_dd_alert_ts > 60:
                self.last_dd_alert_ts = now_ts
                try:
                    import asyncio
                    asyncio.create_task(self.notifier.send(f"🛑 Auto OFF: daily drawdown {dd_pct:.2f}% >= {settings.daily_drawdown_limit_pct}%"))
                except Exception:
                    pass
            return True
        return False


    def _check_daily_profit_lock(self, now_ts: float) -> bool:
        bal = self.broker.get_balance()
        cur = float(bal.get("balance", 0.0) or 0.0)
        if cur <= 0:
            return False
        if self.day_start_balance is None:
            self.day_start_balance = cur
            return False

        gain_pct = ((cur - self.day_start_balance) / self.day_start_balance) * 100.0
        if gain_pct >= float(settings.daily_profit_target_pct):
            if self.auto_enabled:
                self.auto_enabled = False
                self.audit.log("auto_off_profit_target", {"gain_pct": gain_pct, "target_pct": settings.daily_profit_target_pct})
            if now_ts - self.last_tp_alert_ts > 60:
                self.last_tp_alert_ts = now_ts
                try:
                    import asyncio
                    asyncio.create_task(self.notifier.send(f"✅ Auto OFF: daily profit target {gain_pct:.2f}% >= {settings.daily_profit_target_pct}%"))
                except Exception:
                    pass
            return True
        return False


    async def _manage_open_positions(self, positions: list[dict]):
        for p in positions:
            ticket = int(p.get("ticket", 0) or 0)
            if ticket <= 0:
                continue
            ctx = self.open_trade_ctx.get(ticket)
            if not ctx:
                continue
            profit = float(p.get("profit", 0.0) or 0.0)
            symbol = str(p.get("symbol", ctx.get("symbol", "")))
            side = "buy" if int(p.get("type", 0)) == 0 else "sell"

            # 1R management
            if (not ctx.get("breakeven_done")) and profit >= float(ctx.get("risk_usd", 0.0)):
                be_res = self.broker.set_sl_tp_by_points(
                    ticket=ticket,
                    symbol=symbol,
                    side=side,
                    sl_points=0.0,
                    tp_points=float(ctx.get("tp_points", 0.0)),
                )
                if be_res.get("ok"):
                    ctx["breakeven_done"] = True
                    await self.notifier.send(f"🔒 breakeven moved | #{ticket} {symbol}")

            if (not ctx.get("partial_done")) and profit >= float(ctx.get("risk_usd", 0.0)):
                close_vol = max(float(ctx.get("volume", 0.01)) * 0.5, 0.01)
                part_res = self.broker.close_partial(ticket, close_vol)
                if part_res.get("ok"):
                    ctx["partial_done"] = True
                    await self.notifier.send(f"✂️ partial close 50% executed | #{ticket} vol={close_vol}")

            if ctx.get("breakeven_done"):
                # lightweight trailing approximation: tighten SL with increasing R multiples
                risk_usd = max(float(ctx.get("risk_usd", 1.0)), 1e-9)
                r_mult = profit / risk_usd
                if r_mult >= 1.5:
                    sl_points = max(float(ctx.get("sl_points", 0.0)) * 0.35, 1.0)
                    tr_res = self.broker.set_sl_tp_by_points(
                        ticket=ticket,
                        symbol=symbol,
                        side=side,
                        sl_points=sl_points,
                        tp_points=float(ctx.get("tp_points", 0.0)),
                    )
                    if tr_res.get("ok") and not ctx.get("trailing_announced"):
                        ctx["trailing_announced"] = True
                        await self.notifier.send(f"📈 trailing stop active | #{ticket} {symbol}")

        # detect closed positions and update strategy stats
        open_tickets = {int(p.get("ticket", 0) or 0) for p in positions}
        for t in list(self.open_trade_ctx.keys()):
            if t not in open_tickets:
                c = self.open_trade_ctx.pop(t)
                st_name = c.get("strategy", "unknown")
                pnl = float(c.get("last_profit", 0.0) or 0.0)
                self.strategy_stats[st_name]["n"] += 1
                if pnl >= 0:
                    self.strategy_stats[st_name]["wins"] += 1
                else:
                    self.strategy_stats[st_name]["losses"] += 1
                await self.notifier.send(f"✅ trade closed | #{t} strategy={st_name} pnl≈{pnl:.2f}")

        for p in positions:
            t = int(p.get("ticket", 0) or 0)
            if t in self.open_trade_ctx:
                self.open_trade_ctx[t]["last_profit"] = float(p.get("profit", 0.0) or 0.0)

    def _build_candles_from_prices(self, prices, chunk=5):
        if len(prices) < chunk:
            return []
        candles=[]
        for i in range(0, len(prices)-chunk+1, chunk):
            c=prices[i:i+chunk]
            candles.append({"open": c[0], "high": max(c), "low": min(c), "close": c[-1]})
        return candles

    def _validate_symbol_valuation(self, market: dict, symbol: str) -> tuple[bool, str]:
        return self.risk.validate_symbol_valuation(
            {
                "symbol": symbol,
                "point_value": market.get("point_value", 0.0),
                "point_size": market.get("point_size", 0.0),
            }
        )

    def _execute_intent_with_protection(self, intent, market_context: dict):
        result = execute_protected_trade(
            broker=self.broker,
            risk_engine=self.risk,
            intent=intent,
            market_context=market_context,
            strict_point_value_validation=self.strict_point_value_validation,
            require_protected_execution=bool(self.require_protected_execution),
            mode=self.mode,
        )
        return result.to_dict()

    def _expected_side_label(self, market: dict) -> str:
        ema9 = float(market.get('ema9', 0.0) or 0.0)
        ema21 = float(market.get('ema21', 0.0) or 0.0)
        rsi7 = float(market.get('rsi7', 50.0) or 50.0)
        if ema9 > ema21 and rsi7 >= 50:
            return "شراء"
        if ema9 < ema21 and rsi7 <= 50:
            return "بيع"
        return "محايد"

    def _build_no_trade_reason(self, market: dict, positions_count: int, now_ts: float) -> str:
        if self.paused:
            return "التداول موقوف حالياً"
        if self.mode != "live":
            return "الوضع ليس حي (Live)"
        if positions_count > 0:
            return f"يوجد صفقات مفتوحة حالياً ({positions_count})"
        if (now_ts - self.last_auto_ts) < settings.auto_cooldown_seconds:
            left = int(settings.auto_cooldown_seconds - (now_ts - self.last_auto_ts))
            return f"فترة التهدئة فعّالة (متبقي {left} ثانية)"
        if market.get('session') == 'off_hours':
            return "خارج جلسة التداول المحددة"
        ema9 = float(market.get('ema9', 0.0))
        ema21 = float(market.get('ema21', 0.0))
        rsi7 = float(market.get('rsi7', 50.0))
        side_lbl = self._expected_side_label(market)
        return f"الإشارة غير مكتملة الشروط | الاتجاه المتوقع: {side_lbl} (EMA9={ema9:.2f}, EMA21={ema21:.2f}, RSI7={rsi7:.2f})"

    def _build_market_context(self, symbol_override: str | None = None) -> dict:
        now_utc = datetime.now(timezone.utc)
        hour = now_utc.hour

        if self._in_hhmm_range(now_utc.hour, now_utc.minute, settings.asia_session_utc):
            session = "asia"
        elif 7 <= hour < 12:
            session = "london"
        elif 12 <= hour < 16:
            session = "london_ny_overlap"
        elif 16 <= hour < 23:
            session = "new_york"
        else:
            session = "off_hours"

        symbol = symbol_override or settings.auto_default_symbol or settings.default_symbol
        series = list(self.price_history.get(symbol, []))
        specs = self.broker.get_symbol_specs(symbol)
        point_value = float(specs.get("point_value", 0.0) or 0.0)
        ema9 = self._ema(series, 9) if series else 0.0
        ema21 = self._ema(series, 21) if series else 0.0
        rsi7 = self._rsi(series, 7) if series else 50.0

        bias = "neutral"
        micro = "flat"
        if ema9 > ema21:
            bias = "bullish"
            micro = "up"
        elif ema9 < ema21:
            bias = "bearish"
            micro = "down"

        candles_m5 = self._build_candles_from_prices(series, chunk=5)
        candles_m15 = self._build_candles_from_prices(series, chunk=15)

        atr_pct = 0.0
        if len(series) >= 20 and series[-1] > 0:
            atr_proxy = sum(abs(series[i] - series[i - 1]) for i in range(len(series) - 14, len(series))) / 14
            atr_pct = atr_proxy / series[-1]

        return {
            "symbol": symbol,
            "session": session,
            "hour_utc": now_utc.hour,
            "minute_utc": now_utc.minute,
            "ict_killzones_enabled": bool(settings.ict_killzones_enabled),
            "ict_london_killzone_utc": settings.ict_london_killzone_utc,
            "ict_newyork_killzone_utc": settings.ict_newyork_killzone_utc,
            "asia_session_utc": settings.asia_session_utc,
            "asia_region_markets": ["Australia", "Japan", "Korea", "China"],
            "volatility": "medium",
            "news_high_impact": bool(settings.asia_news_block_enabled and session == "asia" and settings.asia_news_high_impact),
            "bias": bias,
            "micro_momentum": micro,
            "session_breakout": "none",
            "weighted_votes": {"buy": 0.0, "sell": 0.0},
            "ema9": ema9,
            "ema21": ema21,
            "rsi7": rsi7,
            "last_price": series[-1] if series else 0.0,
            "point_value": point_value,
            "point_size": float(specs.get("point_size", 0.0) or 0.0),
            "atr_pct": atr_pct,
            "is_noisy": atr_pct > 0.02,
            "aggressive_mode": self.risk_mode == "aggressive",
            "allow_point_fallback": not (self.mode == "live" and settings.strict_point_value_validation),
            "strategy_performance": {
                k: {
                    "wins": v.get("wins", 0),
                    "losses": v.get("losses", 0),
                    "n": v.get("n", 0),
                    "win_rate": (v.get("wins", 0) / v.get("n", 1)) if v.get("n", 0) else 0.5,
                }
                for k, v in self.strategy_stats.items()
            },
            "candles_m5": candles_m5,
            "candles_m15": candles_m15,
        }

    async def start(self):
        self.log.info("Starting Linkat MJ Trader | mode=%s", self.mode)
        self.audit.log("startup", {"mode": self.mode})
        await self.notifier.send(f"🚀 Linkat MJ Trader started | mode={self.mode}")

        await self.controller.start()

        if self.mode == "live":
            self.broker.connect()
            self.audit.log("broker_connected", {"server": settings.mt5_server})

        last_hb = 0
        last_report = 0
        while True:
            now = datetime.now(timezone.utc).timestamp()
            try:
                self._update_price_history()
                self._roll_day_if_needed(now)
                self._check_daily_drawdown_stop(now)
                self._check_daily_profit_lock(now)
                positions = self.broker.get_positions()
                await self._manage_open_positions(positions)
                bal = self.broker.get_balance()
                stats = {
                    "daily_loss_pct": 0,
                    "trades_today": 0,
                    "open_positions": len(positions),
                    "balance": float(bal.get("balance", 0.0) or 0.0),
                    "consecutive_losses": 0,
                }
                if self.paused:
                    pass
                else:
                    allowed, reason = self.risk.allow_trade(stats)
                    if not allowed:
                        self.audit.log("risk_block", {"reason": reason})
                        if (now - self.last_no_trade_notify_ts) >= 60:
                            self.last_no_trade_notify_ts = now
                            await self.notifier.send(f"🚫 trade rejected by risk engine: {reason}")
                    else:
                        market = self._build_market_context()
                        regime = self.regime.select(market, self.strategies)
                        self.audit.log("regime", {"active": regime.active_strategy_names, "weights": regime.weights})

                        active = [s for s in self.strategies if s.name in regime.active_strategy_names and self.strategy_enabled.get(s.name, True)]

                        # auto execution with strategy competition by confidence * regime weight
                        if self.auto_enabled:
                            traded = False
                            chosen_market = market
                            if len(positions) == 0 and (now - self.last_auto_ts) >= settings.auto_cooldown_seconds:
                                watch_symbols = self.watch_symbols or [settings.auto_default_symbol]

                                dexter_ok = check_dexter_health()
                                committee_ok = check_tradingagents_health()
                                if settings.dexter_enabled and not dexter_ok:
                                    self.audit.log("hold_external_unavailable", {"source": "dexter"})
                                if settings.trading_agents_enabled and not committee_ok:
                                    self.audit.log("hold_external_unavailable", {"source": "tradingagents"})

                                for sym in watch_symbols:
                                    chosen_market = self._build_market_context(sym)

                                    # backward-compatible local strategy path when external agents disabled
                                    if (not settings.dexter_enabled) and (not settings.trading_agents_enabled):
                                        local_best = None
                                        for st in active:
                                            sigs = await st.generate(chosen_market)
                                            if not sigs:
                                                continue
                                            sig = sigs[0]
                                            score = float(getattr(sig, 'confidence', 0.0) or 0.0) * float(regime.weights.get(st.name, 1.0))
                                            if (local_best is None) or (score > local_best[0]):
                                                local_best = (score, st.name, sig)
                                        if local_best is None:
                                            continue

                                        _, st_name, sig = local_best
                                        symbol = sig.symbol or sym
                                        local_decision = type("D", (), {"final_action": sig.side.upper(), "symbol": symbol})()
                                        risk_result = self.risk.build_execution_intent(
                                            account_state=bal,
                                            symbol_state={
                                                "symbol": symbol,
                                                "point_value": chosen_market.get("point_value", 0.0),
                                                "point_size": chosen_market.get("point_size", 0.0),
                                            },
                                            unified_decision=local_decision,
                                            mode=self.mode,
                                            risk_mode=self.risk_mode,
                                            strict_point_value_validation=self.strict_point_value_validation,
                                            risk_percent_override=float(settings.risk_percent_per_trade),
                                        )
                                        if not risk_result.ok or not risk_result.intent:
                                            self.audit.log("risk_intent_block_local", {"symbol": symbol, "reason": risk_result.reason, "strategy": st_name})
                                            await self.notifier.send(f"🚫 HOLD {symbol}: {risk_result.reason}")
                                            continue

                                        intent = risk_result.intent
                                        res = self._execute_intent_with_protection(intent, chosen_market)
                                        self.audit.log("auto_open_local", {"strategy": st_name, "signal": sig.__dict__, "intent": intent.model_dump(), "result": res})
                                        self.last_auto_ts = now
                                        traded = bool(res.get("success"))
                                        if traded:
                                            await self.notifier.send(
                                                f"✅ {('PAPER TRADE' if self.mode=='paper' else 'EXECUTED')} {symbol} {intent.action} | lot={intent.lot_size} | SL=${intent.stop_loss_usd:.2f} | TP=${intent.take_profit_usd:.2f} | protected={res.get('protection_attached')} | ticket={res.get('ticket_id')} | mode={self.mode}"
                                            )
                                            break
                                        await self.notifier.send(f"🚫 trade rejected by execution/risk path | {res.get('reason')}")
                                        continue

                                    ticks = self.broker.get_ticks() or {}
                                    ext_ctx = build_market_context(
                                        symbol=sym,
                                        mode=self.mode,
                                        session=chosen_market.get("session", "off_hours"),
                                        risk_params={
                                            "max_risk_per_trade": settings.max_risk_per_trade,
                                            "max_daily_loss": settings.max_daily_loss,
                                            "max_open_positions": settings.max_concurrent_positions,
                                            "max_trades_per_day": settings.max_trades_per_day,
                                        },
                                        balance=bal,
                                        positions=positions,
                                        ticks=ticks,
                                        candles_m5=chosen_market.get("candles_m5", []),
                                        candles_m15=chosen_market.get("candles_m15", []),
                                    )

                                    self.audit.log("analysis_cycle", {"symbol": sym, "market_context": ext_ctx, "mode": self.mode})

                                    # hard metadata gate
                                    ok_val, why_val = self._validate_symbol_valuation(chosen_market, sym)
                                    if not ok_val and (self.mode == "live" or str(settings.paper_valuation_policy).lower().strip() == "block"):
                                        self.audit.log("valuation_block", {"symbol": sym, "reason": why_val, "mode": self.mode})
                                        await self.notifier.send(f"🚫 HOLD {sym}: {why_val}")
                                        continue

                                    if (settings.dexter_enabled and not dexter_ok) or (settings.trading_agents_enabled and not committee_ok):
                                        await self.notifier.send(f"⏸ HOLD {sym}: external services unavailable")
                                        continue

                                    dexter_report = analyze_with_dexter(sym, ext_ctx)
                                    committee_report = analyze_with_tradingagents(sym, ext_ctx)
                                    decision = build_unified_decision(
                                        dexter_report,
                                        committee_report,
                                        sym,
                                        min_confidence=float(settings.consensus_min_confidence),
                                    )

                                    self.audit.log(
                                        "external_decision",
                                        {
                                            "symbol": sym,
                                            "dexter": dexter_report.model_dump() if dexter_report else None,
                                            "committee": committee_report.model_dump() if committee_report else None,
                                            "unified": decision.model_dump(),
                                        },
                                    )

                                    if not decision.eligible_for_risk_review or decision.final_action not in {"BUY", "SELL"}:
                                        await self.notifier.send(
                                            f"⏸ HOLD {sym} | reason={decision.reason} | align={decision.source_alignment} | dexter={decision.dexter_bias} | committee={decision.committee_action} | conf={decision.confidence:.2f} | mode={self.mode}"
                                        )
                                        continue

                                    risk_result = self.risk.build_execution_intent(
                                        account_state=bal,
                                        symbol_state={
                                            "symbol": sym,
                                            "point_value": chosen_market.get("point_value", 0.0),
                                            "point_size": chosen_market.get("point_size", 0.0),
                                        },
                                        unified_decision=decision,
                                        mode=self.mode,
                                        risk_mode=self.risk_mode,
                                        strict_point_value_validation=self.strict_point_value_validation,
                                        risk_percent_override=float(settings.risk_percent_per_trade),
                                    )

                                    if not risk_result.ok or not risk_result.intent:
                                        self.audit.log("risk_intent_block", {"symbol": sym, "reason": risk_result.reason})
                                        await self.notifier.send(f"🚫 HOLD {sym}: {risk_result.reason}")
                                        continue

                                    intent = risk_result.intent
                                    res = self._execute_intent_with_protection(intent, chosen_market)

                                    if res.get("success") and res.get("ticket_id") and self.mode == "live":
                                        self.open_trade_ctx[int(res.get("ticket_id"))] = {
                                            "strategy": "external_consensus",
                                            "risk_usd": float(intent.stop_loss_usd),
                                            "reward_usd": float(intent.take_profit_usd),
                                            "sl_points": float(res.get("stop_loss_points", 0.0) or 0.0),
                                            "tp_points": float(res.get("take_profit_points", 0.0) or 0.0),
                                            "volume": float(intent.lot_size),
                                            "symbol": sym,
                                            "breakeven_done": False,
                                            "partial_done": False,
                                            "trailing_announced": False,
                                            "last_profit": 0.0,
                                        }

                                    self.audit.log("execution_intent", {"intent": intent.model_dump(), "result": res})
                                    self.last_auto_ts = now
                                    traded = bool(res.get("success"))

                                    if traded:
                                        await self.notifier.send(
                                            f"✅ {('PAPER TRADE' if self.mode=='paper' else 'EXECUTED')} {sym} {intent.action} | align={decision.source_alignment} | lot={intent.lot_size} | SL=${intent.stop_loss_usd:.2f} | TP=${intent.take_profit_usd:.2f} | protected={res.get('protection_attached')} | ticket={res.get('ticket_id')} | conf={decision.confidence:.2f} | mode={self.mode}"
                                        )
                                        break
                                    else:
                                        await self.notifier.send(f"🚫 trade rejected by execution/risk path | reason={res.get('reason')} | mode={self.mode}")

                            if (not traded) and (now - self.last_no_trade_notify_ts) >= max(settings.auto_cooldown_seconds, 60):
                                why = self._build_no_trade_reason(chosen_market, len(positions), now)
                                self.last_no_trade_notify_ts = now
                                self.audit.log("auto_skip", {"reason": why})
                                await self.notifier.send(f"⏸ تخطي دخول تلقائي: {why}")
                if settings.heartbeat_seconds > 0 and (now - last_hb) >= settings.heartbeat_seconds:
                    last_hb = now
                    self.audit.log("heartbeat", {"mode": self.mode})
                    await self.notifier.send(f"💓 heartbeat | mode={self.mode}")

                if now - last_report >= settings.report_interval_seconds:
                    last_report = now
                    await self.notifier.send("🧾 " + self._report())

            except Exception as e:
                self.log.exception("loop error")
                self.audit.log("error", {"error": str(e)})
                await self.notifier.send(f"⚠️ error: {e}")

            await asyncio.sleep(settings.tick_interval_seconds)
