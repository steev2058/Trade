class RiskEngine:
    def __init__(
        self,
        max_risk_per_trade: float,
        max_daily_loss: float,
        max_trades_per_day: int,
        max_concurrent_positions: int,
        min_balance: float = 0.0,
        cooldown_after_losses: int = 0,
    ):
        self.max_risk_per_trade = max_risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_trades_per_day = max_trades_per_day
        self.max_concurrent_positions = max_concurrent_positions
        self.min_balance = min_balance
        self.cooldown_after_losses = cooldown_after_losses

    def allow_trade(self, stats: dict) -> tuple[bool, str]:
        if stats.get("daily_loss_pct", 0) >= self.max_daily_loss:
            return False, "daily loss cap reached"
        if stats.get("trades_today", 0) >= self.max_trades_per_day:
            return False, "max trades/day reached"
        if stats.get("open_positions", 0) >= self.max_concurrent_positions:
            return False, "max concurrent positions reached"
        if float(stats.get("balance", 0.0) or 0.0) <= float(self.min_balance):
            return False, "balance protection reached"
        if self.cooldown_after_losses > 0 and int(stats.get("consecutive_losses", 0) or 0) >= self.cooldown_after_losses:
            return False, "loss cooldown active"
        return True, "ok"

    def compute_position_size(self, balance: float, stop_loss_points: float, point_value: float) -> float:
        risk_amount = balance * self.max_risk_per_trade
        denom = max(stop_loss_points * point_value, 1e-9)
        return max(risk_amount / denom, 0.01)
