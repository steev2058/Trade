from app.strategies.base import Signal, Strategy


class SimpleSignalStrategy(Strategy):
    name = "simple_signal"

    async def generate(self, market: dict) -> list[Signal]:
        symbol = market.get("symbol", "XAUUSD.m")
        ema9 = float(market.get("ema9", 0.0))
        ema21 = float(market.get("ema21", 0.0))
        rsi7 = float(market.get("rsi7", 50.0))
        session = market.get("session", "")

        if session not in ("asia", "london", "london_ny_overlap", "new_york"):
            return []

        # softened but still safe thresholds
        side = ""
        ema_gap = abs(ema9 - ema21)
        if ema9 == 0.0 and ema21 == 0.0:
            return []

        if (ema9 >= ema21 or ema_gap <= 0.05) and rsi7 >= 50.5:
            side = "buy"
        elif (ema9 <= ema21 or ema_gap <= 0.05) and rsi7 <= 49.5:
            side = "sell"

        if not side:
            return []

        volume, risk_usd, reward_usd, sl_points, tp_points = self._risk_pack(market)
        return [
            Signal(
                symbol=symbol,
                side=side,
                confidence=0.58,
                stop_loss_points=sl_points,
                take_profit_points=tp_points,
                volume=volume,
                reason="simple_ema_rsi_signal",
                risk_amount_usd=risk_usd,
                reward_amount_usd=reward_usd,
                meta={"ema9": ema9, "ema21": ema21, "rsi7": rsi7},
            )
        ]
