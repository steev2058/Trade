from dataclasses import dataclass

from app.decision.schemas import ExecutionIntent


@dataclass
class RiskIntentResult:
    ok: bool
    reason: str
    intent: ExecutionIntent | None = None


class RiskEngine:
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
    ):
        self.max_risk_per_trade = max_risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_trades_per_day = max_trades_per_day
        self.max_concurrent_positions = max_concurrent_positions
        self.min_balance = min_balance
        self.cooldown_after_losses = cooldown_after_losses
        self.min_lot = min_lot
        self.max_lot = max_lot

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

    def _validate_symbol_valuation(self, symbol_state: dict) -> tuple[bool, str]:
        pv = float(symbol_state.get("point_value", 0.0) or 0.0)
        ps = float(symbol_state.get("point_size", 0.0) or 0.0)
        if pv <= 0 or ps <= 0:
            return False, f"ambiguous valuation (point_value={pv}, point_size={ps})"
        return True, "ok"

    def _mode_multiplier(self, risk_mode: str) -> float:
        m = (risk_mode or "balanced").lower().strip()
        if m in {"safe", "conservative"}:
            return 0.5
        if m in {"aggressive"}:
            return 2.0
        return 1.0  # balanced/normal

    def _round_lot(self, lot: float) -> float:
        # common FX/CFD step safety
        return round(lot, 2)

    def _compute_lot(self, account_state: dict, risk_mode: str) -> float:
        equity = float(account_state.get("equity", account_state.get("balance", 0.0)) or 0.0)
        balance = float(account_state.get("balance", equity) or equity)
        base = min(max(equity, 0.0), max(balance, 0.0))
        # 0.01 lot roughly each $1000 of account at balanced mode, with hard caps
        raw = (base / 1000.0) * 0.01 * self._mode_multiplier(risk_mode)
        lot = self._round_lot(max(self.min_lot, min(raw, self.max_lot)))
        return max(self.min_lot, min(lot, self.max_lot))

    def build_execution_intent(
        self,
        *,
        account_state: dict,
        symbol_state: dict,
        unified_decision,
        mode: str,
        risk_mode: str,
        strict_point_value_validation: bool = True,
    ) -> RiskIntentResult:
        action = str(getattr(unified_decision, "final_action", "HOLD") or "HOLD").upper().strip()
        symbol = str(getattr(unified_decision, "symbol", symbol_state.get("symbol", "")) or "")
        if action not in {"BUY", "SELL"}:
            return RiskIntentResult(ok=False, reason="non-actionable decision")

        if strict_point_value_validation:
            ok, reason = self._validate_symbol_valuation(symbol_state)
            if not ok:
                return RiskIntentResult(ok=False, reason=reason)

        lot = self._compute_lot(account_state, risk_mode)
        # preserve user linear USD scaling example while generalizing to dynamic lot
        stop_loss_usd = float(lot * 500.0)
        take_profit_usd = float(stop_loss_usd * 3.0)

        intent = ExecutionIntent(
            symbol=symbol,
            action=action,
            mode=mode,
            risk_percent=float(self.max_risk_per_trade),
            stop_loss_usd=stop_loss_usd,
            take_profit_usd=take_profit_usd,
            lot_size=float(lot),
            rationale="risk_engine_intent",
        )
        return RiskIntentResult(ok=True, reason="ok", intent=intent)

    def usd_to_points(self, usd: float, lot: float, point_value: float) -> float:
        denom = max(float(lot) * float(point_value), 1e-9)
        return float(usd) / denom
