from dataclasses import dataclass


@dataclass
class Signal:
    symbol: str
    side: str  # buy/sell
    confidence: float
    stop_loss_points: float
    take_profit_points: float
    reason: str


class Strategy:
    name = "base"

    async def generate(self, market: dict) -> list[Signal]:
        return []
