import asyncio
import logging
from datetime import datetime, timezone

from app.core.settings import settings
from app.core.logging import setup_logging
from app.brokers.mt5_adapter import MT5Adapter
from app.notifiers.telegram_notifier import TelegramNotifier
from app.notifiers.telegram_controller import TelegramController
from app.storage.audit import AuditStore
from app.risk.engine import RiskEngine
from app.strategies.news import NewsStrategy
from app.strategies.scalper import ScalperStrategy
from app.strategies.smc_ict import SmcIctStrategy
from app.strategies.adaptive_weighting import AdaptiveWeightingStrategy
from app.strategies.london_ny_session import LondonNySessionStrategy
from app.strategies.regime_switcher import RegimeSwitcher


class TradingRunner:
    def __init__(self, mode: str = "paper"):
        setup_logging(settings.log_level)
        self.log = logging.getLogger("runner")
        self.mode = mode
        self.audit = AuditStore()
        self.notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
        self.paused = False
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
        return f"mode={self.mode} | paused={self.paused} | strategies={len(self.strategies)}"

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
        return f"close_all result: {res}"

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

        return {
            "symbol": settings.default_symbol,
            "session": session,
            "volatility": "medium",
            "news_high_impact": False,
            "bias": "neutral",
            "micro_momentum": "flat",
            "session_breakout": "none",
            "weighted_votes": {"buy": 0.0, "sell": 0.0},
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
        while True:
            now = datetime.now(timezone.utc).timestamp()
            try:
                stats = {
                    "daily_loss_pct": 0,
                    "trades_today": 0,
                    "open_positions": len(self.broker.get_positions()),
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

                if now - last_hb >= settings.heartbeat_seconds:
                    last_hb = now
                    self.audit.log("heartbeat", {"mode": self.mode})
                    await self.notifier.send(f"💓 heartbeat | mode={self.mode}")

            except Exception as e:
                self.log.exception("loop error")
                self.audit.log("error", {"error": str(e)})
                await self.notifier.send(f"⚠️ error: {e}")

            await asyncio.sleep(settings.tick_interval_seconds)
