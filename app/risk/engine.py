from dataclasses import dataclass

from app.decision.schemas import ExecutionIntent


@dataclass
class RiskIntentResult:
    ok: bool
    reason: str
    intent: ExecutionIntent | None = None


class RiskEngine:
    """Single source of truth for trade-construction and risk sizing policy."""

    def __init__(
        self,
        max_risk_per_trade: float,
        max_daily_loss: float,
        max_trades_per_day: int,
        max_concurrent_positions: int,
        min_balance: float = 0.0,
        cooldown_after_losses: int = 0,
        min_lot: float = 0.01,
        max_lot: float = 1.0,
        usd_stop_per_0_01_lot: float = 5.0,
        rr_ratio: float = 3.0,
    ):
        self.max_risk_per_trade = max_risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_trades_per_day = max_trades_per_day
        self.max_concurrent_positions = max_concurrent_positions
        self.min_balance = min_balance
        self.cooldown_after_losses = cooldown_after_losses
        self.min_lot = min_lot
        self.max_lot = max_lot
        self.usd_stop_per_0_01_lot = usd_stop_per_0_01_lot
        self.rr_ratio = rr_ratio

    def allow_trade(self, stats: dict) -> tuple[bool, str]:
        if stats.get("daily_loss_pct", 0) >= self.max_daily_loss:
            return False, "daily loss cap reached"
        if stats.get("trades_today", 0) >= self.max_trades_per_day:
            return False, "max trades/day reached"
        if stats.get("open_positions", 0) >= self.max_concurrent_positions:
            return False, "max concurrent positions reached"
        min_balance = float(self.min_balance or 0.0)
        if min_balance > 0 and float(stats.get("balance", 0.0) or 0.0) <= min_balance:
            return False, "balance protection reached"
        if self.cooldown_after_losses > 0 and int(stats.get("consecutive_losses", 0) or 0) >= self.cooldown_after_losses:
            return False, "loss cooldown active"
        return True, "ok"

    def validate_symbol_valuation(self, symbol_state: dict) -> tuple[bool, str]:
        pv = float(symbol_state.get("point_value", 0.0) or 0.0)
        ps = float(symbol_state.get("point_size", 0.0) or 0.0)
        symbol = symbol_state.get("symbol", "?")
        if pv <= 0 or ps <= 0:
            return False, f"ambiguous valuation for {symbol} (point_value={pv}, point_size={ps})"
        return True, "ok"

    def validate_trade_bounds(self, lot: float) -> tuple[bool, str]:
        if float(lot) < float(self.min_lot):
            return False, f"lot below minimum ({lot} < {self.min_lot})"
        if float(lot) > float(self.max_lot):
            return False, f"lot above maximum ({lot} > {self.max_lot})"
        return True, "ok"

    def _mode_multiplier(self, risk_mode: str) -> float:
        m = (risk_mode or "balanced").lower().strip()
        if m in {"safe", "conservative"}:
            return 0.5
        if m in {"aggressive"}:
            return 2.0
        return 1.0  # balanced/normal

    def _round_lot(self, lot: float) -> float:
        return round(lot, 2)

    def compute_lot_size(self, account_state: dict, risk_mode: str) -> float:
        equity = float(account_state.get("equity", account_state.get("balance", 0.0)) or 0.0)
        balance = float(account_state.get("balance", equity) or equity)
        base = min(max(equity, 0.0), max(balance, 0.0))
        raw = (base / 1000.0) * 0.01 * self._mode_multiplier(risk_mode)
        lot = self._round_lot(max(self.min_lot, min(raw, self.max_lot)))
        return max(self.min_lot, min(lot, self.max_lot))

    def compute_usd_stop_loss(self, lot_size: float) -> float:
        return float((float(lot_size) / 0.01) * float(self.usd_stop_per_0_01_lot))

    def compute_usd_take_profit(self, stop_loss_usd: float) -> float:
        return float(stop_loss_usd) * float(self.rr_ratio)

    def convert_usd_risk_to_points(self, usd: float, lot: float, point_value: float) -> float:
        denom = max(float(lot) * float(point_value), 1e-9)
        return float(usd) / denom

    def build_execution_intent(
        self,
        *,
        account_state: dict,
        symbol_state: dict,
        unified_decision,
        mode: str,
        risk_mode: str,
        strict_point_value_validation: bool = True,
        risk_percent_override: float | None = None,
    ) -> RiskIntentResult:
        action = str(getattr(unified_decision, "final_action", "HOLD") or "HOLD").upper().strip()
        symbol = str(getattr(unified_decision, "symbol", symbol_state.get("symbol", "")) or "")
        if action not in {"BUY", "SELL"}:
            return RiskIntentResult(ok=False, reason="non-actionable decision")

        if strict_point_value_validation:
            ok, reason = self.validate_symbol_valuation(symbol_state)
            if not ok:
                return RiskIntentResult(ok=False, reason=reason)

        lot = self.compute_lot_size(account_state, risk_mode)
        ok_lot, lot_reason = self.validate_trade_bounds(lot)
        if not ok_lot:
            return RiskIntentResult(ok=False, reason=lot_reason)

        stop_loss_usd = self.compute_usd_stop_loss(lot)
        take_profit_usd = self.compute_usd_take_profit(stop_loss_usd)

        intent = ExecutionIntent(
            symbol=symbol,
            action=action,
            mode=mode,
            risk_percent=float(risk_percent_override if risk_percent_override is not None else self.max_risk_per_trade),
            stop_loss_usd=stop_loss_usd,
            take_profit_usd=take_profit_usd,
            lot_size=float(lot),
            rationale="risk_engine_intent",
        )
        return RiskIntentResult(ok=True, reason="ok", intent=intent)
