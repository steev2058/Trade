from app.strategies.base import Signal, Strategy


class SwingStrategy(Strategy):
    name = "swing"

    async def generate(self, market: dict) -> list[Signal]:
        return []
