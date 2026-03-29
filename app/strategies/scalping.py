from app.strategies.base import Signal, Strategy


class ScalpingStrategy(Strategy):
    name = "scalping"

    async def generate(self, market: dict) -> list[Signal]:
        return []
