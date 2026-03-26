from app.strategies.base import Signal, Strategy


class SmcIctStrategy(Strategy):
    """Safety-first scaffold for Smart Money Concepts / ICT style logic."""

    name = "smc_ict"

    async def generate(self, market: dict) -> list[Signal]:
        if market.get("session") not in {"london", "new_york", "london_ny_overlap"}:
            return []
        if market.get("volatility") == "extreme":
            return []

        bias = market.get("bias", "neutral")
        side = "buy" if bias == "bullish" else "sell" if bias == "bearish" else ""
        if not side:
            return []

        return [
            Signal(
                symbol=market.get("symbol", "EURUSD"),
                side=side,
                confidence=0.58,
                stop_loss_points=150,
                take_profit_points=240,
                reason="smc_ict_liquidity_structure_scaffold",
            )
        ]
