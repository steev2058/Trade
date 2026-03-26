from app.strategies.base import Strategy


class NewsStrategy(Strategy):
    name = "news"

    async def generate(self, market: dict):
        return []
