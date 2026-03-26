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

        return [
            Signal(
                symbol=market.get("symbol", "EURUSD"),
                side=side,
                confidence=0.6,
                stop_loss_points=100,
                take_profit_points=140,
                reason="london_ny_overlap_breakout_scaffold",
            )
        ]
