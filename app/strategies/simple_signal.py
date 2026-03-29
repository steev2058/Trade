from app.strategies.base import Signal, Strategy


class SimpleSignalStrategy(Strategy):
    name = "simple_signal"

    async def generate(self, market: dict) -> list[Signal]:
        symbol = market.get("symbol", "XAUUSD.m")
        ema9 = float(market.get("ema9", 0.0))
        ema21 = float(market.get("ema21", 0.0))
        rsi7 = float(market.get("rsi7", 50.0))
        session = market.get("session", "")

        if session not in ("london", "london_ny_overlap", "new_york"):
            return []

        side = ""
        if ema9 > ema21 and rsi7 > 52:
            side = "buy"
        elif ema9 < ema21 and rsi7 < 48:
            side = "sell"

        if not side:
            return []

        volume, risk_usd, reward_usd, sl_points, tp_points = self._risk_pack(market)
        return [
            Signal(
                symbol=symbol,
                side=side,
                confidence=0.62,
                stop_loss_points=sl_points,
                take_profit_points=tp_points,
                volume=volume,
                reason="simple_ema_rsi_signal",
                risk_amount_usd=risk_usd,
                reward_amount_usd=reward_usd,
                meta={"ema9": ema9, "ema21": ema21, "rsi7": rsi7},
            )
        ]
