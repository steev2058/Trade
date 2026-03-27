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
        self.price_history = defaultdict(lambda: deque(maxlen=200))
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
            },
        )
        self.risk = RiskEngine(
            settings.max_risk_per_trade,
            settings.max_daily_loss,
            settings.max_trades_per_day,
            settings.max_concurrent_positions,
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

    def _status_text(self) -> str:
        return f"mode={self.mode} | paused={self.paused} | auto={self.auto_enabled} | strategies={len(self.strategies)}"

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
        return (
            f"Report\n"
            f"balance={bal.get('balance')} {bal.get('currency')}\n"
            f"equity={bal.get('equity')}\n"
            f"positions={pnl.get('positions')}\n"
            f"open_pnl={pnl.get('open_pnl')}\n"
            f"auto={self.auto_enabled}"
        )

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

    def _build_market_context(self) -> dict:
        now_utc = datetime.now(timezone.utc)
        hour = now_utc.hour

        if 7 <= hour < 12:
            session = "london"
        elif 12 <= hour < 16:
            session = "london_ny_overlap"
        elif 16 <= hour < 21:
            session = "new_york"
        else:
            session = "off_hours"

        symbol = settings.auto_default_symbol or settings.default_symbol
        series = list(self.price_history.get(symbol, []))
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

        return {
            "symbol": symbol,
            "session": session,
            "volatility": "medium",
            "news_high_impact": False,
            "bias": bias,
            "micro_momentum": micro,
            "session_breakout": "none",
            "weighted_votes": {"buy": 0.0, "sell": 0.0},
            "ema9": ema9,
            "ema21": ema21,
            "rsi7": rsi7,
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
                positions = self.broker.get_positions()
                stats = {
                    "daily_loss_pct": 0,
                    "trades_today": 0,
                    "open_positions": len(positions),
                }
                if self.paused:
                    pass
                else:
                    allowed, reason = self.risk.allow_trade(stats)
                    if not allowed:
                        self.audit.log("risk_block", {"reason": reason})
                    else:
                        market = self._build_market_context()
                        regime = self.regime.select(market, self.strategies)
                        self.audit.log("regime", {"active": regime.active_strategy_names, "weights": regime.weights})

                        active = [s for s in self.strategies if s.name in regime.active_strategy_names]
                        for st in active:
                            signals = await st.generate(market)
                            if signals:
                                self.audit.log(
                                    "signals",
                                    {
                                        "strategy": st.name,
                                        "count": len(signals),
                                        "weight": regime.weights.get(st.name, 1.0),
                                    },
                                )

                        # simple auto execution gate (phase 4 baseline)
                        if self.auto_enabled and self.mode == "live":
                            if len(positions) == 0 and (now - self.last_auto_ts) >= settings.auto_cooldown_seconds:
                                signals = await self.signal_strategy.generate(market)
                                if signals:
                                    sig = signals[0]
                                    side = sig.get('side', 'buy')
                                    symbol = sig.get('symbol', settings.auto_default_symbol)
                                    res = self.broker.open_order(symbol, side, settings.auto_default_lot)
                                    self.audit.log("auto_open", {"symbol": symbol, "side": side, "lot": settings.auto_default_lot, "signal": sig, "result": res})
                                    self.journal.append("auto_open", res, symbol=symbol, side=side, lot=settings.auto_default_lot, ticket=res.get("order") or "")
                                    self.last_auto_ts = now
                                    await self.notifier.send(f"🤖 auto_open ({side} {symbol}): {res}")

                if now - last_hb >= settings.heartbeat_seconds:
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
