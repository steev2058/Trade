from app.strategies.base import Signal, Strategy


class NewsStrategy(Strategy):
    """High-impact news safety gate: intentionally avoids entries during risky releases."""

    name = "news"

    async def generate(self, market: dict) -> list[Signal]:
        if market.get("news_high_impact", False):
            return []
        return []
