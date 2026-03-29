from app.strategies.base import Signal, Strategy


class AdaptiveWeightingStrategy(Strategy):
    """Combines upstream strategy hints into a single weighted suggestion."""

    name = "adaptive_weighting"

    async def generate(self, market: dict) -> list[Signal]:
        weighted_votes = market.get("weighted_votes", {})
        if not weighted_votes:
            return []

        buy_score = float(weighted_votes.get("buy", 0.0))
        sell_score = float(weighted_votes.get("sell", 0.0))
        if abs(buy_score - sell_score) < 0.1:
            return []

        side = "buy" if buy_score > sell_score else "sell"
        confidence = min(max(abs(buy_score - sell_score), 0.5), 0.8)
        volume, risk_usd, reward_usd, sl_points, tp_points = self._risk_pack(market)
        return [
            Signal(
                symbol=market.get("symbol", "EURUSD"),
                side=side,
                confidence=confidence,
                stop_loss_points=sl_points,
                take_profit_points=tp_points,
                volume=volume,
                reason="adaptive_weighting_consensus",
                risk_amount_usd=risk_usd,
                reward_amount_usd=reward_usd,
            )
        ]
