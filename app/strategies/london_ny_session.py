from app.strategies.base import Signal, Strategy


class LondonNySessionStrategy(Strategy):
    name = "london_ny_session"

    async def generate(self, market: dict) -> list[Signal]:
        if market.get("session") != "london_ny_overlap":
            return []
        if market.get("volatility") == "extreme":
            return []

        breakout = market.get("session_breakout", "none")
        side = "buy" if breakout == "up" else "sell" if breakout == "down" else ""
        if not side:
            return []

        volume, risk_usd, reward_usd, sl_points, tp_points = self._risk_pack(market)
        return [
            Signal(
                symbol=market.get("symbol", "EURUSD"),
                side=side,
                confidence=0.6,
                stop_loss_points=sl_points,
                take_profit_points=tp_points,
                volume=volume,
                reason="london_ny_overlap_breakout",
                risk_amount_usd=risk_usd,
                reward_amount_usd=reward_usd,
            )
        ]
