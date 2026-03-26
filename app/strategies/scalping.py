from app.strategies.base import Strategy


class ScalpingStrategy(Strategy):
    name = "scalping"

    async def generate(self, market: dict):
        return []
