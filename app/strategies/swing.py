from app.strategies.base import Strategy


class SwingStrategy(Strategy):
    name = "swing"

    async def generate(self, market: dict):
        return []
