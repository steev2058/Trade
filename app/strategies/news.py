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

        return [
            Signal(
                symbol=market.get("symbol", "EURUSD"),
                side=side,
                confidence=0.55,
                stop_loss_points=130,
                take_profit_points=180,
                reason="news_impact_sentiment_scaffold",
            )
        ]
