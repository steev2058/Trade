import asyncio
import logging
from datetime import datetime, timezone

from app.core.settings import settings
from app.core.logging import setup_logging
from app.brokers.mt5_adapter import MT5Adapter
from app.notifiers.telegram_notifier import TelegramNotifier
from app.storage.audit import AuditStore
from app.risk.engine import RiskEngine
from app.strategies.scalping import ScalpingStrategy
from app.strategies.swing import SwingStrategy
from app.strategies.news import NewsStrategy


class TradingRunner:
    def __init__(self, mode: str = "paper"):
        setup_logging(settings.log_level)
        self.log = logging.getLogger("runner")
        self.mode = mode
        self.audit = AuditStore()
        self.notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
        self.risk = RiskEngine(
            settings.max_risk_per_trade,
            settings.max_daily_loss,
            settings.max_trades_per_day,
            settings.max_concurrent_positions,
        )
        self.broker = MT5Adapter(settings.mt5_login, settings.mt5_password, settings.mt5_server, settings.mt5_path)
        self.strategies = []
        if settings.enable_scalping:
            self.strategies.append(ScalpingStrategy())
        if settings.enable_swing:
            self.strategies.append(SwingStrategy())
        if settings.enable_news:
            self.strategies.append(NewsStrategy())

    async def start(self):
        self.log.info("Starting Linkat MJ Trader | mode=%s", self.mode)
        self.audit.log("startup", {"mode": self.mode})
        await self.notifier.send(f"🚀 Linkat MJ Trader started | mode={self.mode}")

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
                    "open_positions": 0,
                }
                allowed, reason = self.risk.allow_trade(stats)
                if not allowed:
                    self.audit.log("risk_block", {"reason": reason})
                else:
                    for st in self.strategies:
                        signals = await st.generate({})
                        if signals:
                            self.audit.log("signals", {"strategy": st.name, "count": len(signals)})

                if now - last_hb >= settings.heartbeat_seconds:
                    last_hb = now
                    self.audit.log("heartbeat", {"mode": self.mode})
                    await self.notifier.send(f"💓 heartbeat | mode={self.mode}")

            except Exception as e:
                self.log.exception("loop error")
                self.audit.log("error", {"error": str(e)})
                await self.notifier.send(f"⚠️ error: {e}")

            await asyncio.sleep(settings.tick_interval_seconds)
