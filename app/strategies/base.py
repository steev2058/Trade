from dataclasses import dataclass, field


@dataclass
class Signal:
    symbol: str
    side: str  # buy/sell
    confidence: float
    stop_loss_points: float
    take_profit_points: float
    volume: float
    reason: str
    risk_amount_usd: float = 0.0
    reward_amount_usd: float = 0.0
    meta: dict = field(default_factory=dict)


class Strategy:
    name = "base"

    @staticmethod
    def _approx_point_value(symbol: str) -> float:
        s = (symbol or "").upper()
        if "XAU" in s:
            return 1.0
        if "BTC" in s:
            return 1.0
        if "ETH" in s:
            return 0.1
        if any(k in s for k in ["US30", "NAS", "SPX", "DJI", "DAX", "GER"]):
            return 1.0
        if len(s) >= 6 and s[:3].isalpha() and s[3:6].isalpha():
            return 10.0  # major FX rough pip value for 1.0 lot
        return 1.0

    @classmethod
    def _risk_pack(cls, market: dict) -> tuple[float, float, float, float, float]:
        aggressive = bool(market.get("aggressive_mode", False))
        volume = 0.02 if aggressive else 0.01
        risk_amount_usd = volume * 500.0
        reward_amount_usd = risk_amount_usd * 3.0

        symbol = str(market.get("symbol", ""))
        point_value = float(market.get("point_value", 0.0) or 0.0)
        if point_value <= 0:
            point_value = cls._approx_point_value(symbol)

        denom = max(volume * point_value, 1e-9)
        stop_loss_points = risk_amount_usd / denom
        take_profit_points = reward_amount_usd / denom
        return volume, risk_amount_usd, reward_amount_usd, stop_loss_points, take_profit_points

    async def generate(self, market: dict) -> list[Signal]:
        return []
