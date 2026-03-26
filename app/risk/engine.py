class RiskEngine:
    def __init__(self, max_risk_per_trade: float, max_daily_loss: float, max_trades_per_day: int, max_concurrent_positions: int):
        self.max_risk_per_trade = max_risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_trades_per_day = max_trades_per_day
        self.max_concurrent_positions = max_concurrent_positions

    def allow_trade(self, stats: dict) -> tuple[bool, str]:
        if stats.get("daily_loss_pct", 0) >= self.max_daily_loss:
            return False, "daily loss cap reached"
        if stats.get("trades_today", 0) >= self.max_trades_per_day:
            return False, "max trades/day reached"
        if stats.get("open_positions", 0) >= self.max_concurrent_positions:
            return False, "max concurrent positions reached"
        return True, "ok"

    def compute_position_size(self, balance: float, stop_loss_points: float, point_value: float) -> float:
        risk_amount = balance * self.max_risk_per_trade
        denom = max(stop_loss_points * point_value, 1e-9)
        return max(risk_amount / denom, 0.01)
