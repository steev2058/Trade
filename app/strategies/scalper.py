from app.strategies.base import Signal, Strategy


class ScalperStrategy(Strategy):
    name = "scalper"

    async def generate(self, market: dict) -> list[Signal]:
        if market.get("volatility") not in {"low", "medium"}:
            return []
        if market.get("news_high_impact", False):
            return []

        momentum = market.get("micro_momentum", "flat")
        side = "buy" if momentum == "up" else "sell" if momentum == "down" else ""
        if not side:
            return []

        volume, risk_usd, reward_usd, sl_points, tp_points = self._risk_pack(market)
        return [
            Signal(
                symbol=market.get("symbol", "EURUSD"),
                side=side,
                confidence=0.52,
                stop_loss_points=sl_points,
                take_profit_points=tp_points,
                volume=volume,
                reason="scalper_micro_momentum",
                risk_amount_usd=risk_usd,
                reward_amount_usd=reward_usd,
            )
        ]
