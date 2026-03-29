from app.strategies.base import Signal, Strategy


class NewsStrategy(Strategy):
    name = "news"

    async def generate(self, market: dict) -> list[Signal]:
        if not market.get("news_high_impact", False):
            return []

        sentiment = market.get("news_sentiment", "neutral")
        side = "buy" if sentiment == "positive" else "sell" if sentiment == "negative" else ""
        if not side:
            return []

        volume, risk_usd, reward_usd, sl_points, tp_points = self._risk_pack(market)
        return [
            Signal(
                symbol=market.get("symbol", "EURUSD"),
                side=side,
                confidence=0.55,
                stop_loss_points=sl_points,
                take_profit_points=tp_points,
                volume=volume,
                reason="news_impact_sentiment",
                risk_amount_usd=risk_usd,
                reward_amount_usd=reward_usd,
            )
        ]
