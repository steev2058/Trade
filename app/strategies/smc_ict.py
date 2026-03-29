from app.strategies.base import Signal, Strategy


class SmcIctStrategy(Strategy):
    """Smart Money Concepts / ICT directional bias strategy."""

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

        volume, risk_usd, reward_usd, sl_points, tp_points = self._risk_pack(market)
        return [
            Signal(
                symbol=market.get("symbol", "EURUSD"),
                side=side,
                confidence=0.58,
                stop_loss_points=sl_points,
                take_profit_points=tp_points,
                volume=volume,
                reason="smc_ict_liquidity_structure",
                risk_amount_usd=risk_usd,
                reward_amount_usd=reward_usd,
            )
        ]
