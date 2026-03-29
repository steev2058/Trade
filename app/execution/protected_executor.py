from dataclasses import dataclass, asdict


@dataclass
class ProtectedExecutionResult:
    success: bool
    mode: str
    symbol: str
    action: str
    lot_size: float
    stop_loss_usd: float
    take_profit_usd: float
    stop_loss_points: float | None
    take_profit_points: float | None
    ticket_id: int | None
    protection_attached: bool
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def execute_protected_trade(
    *,
    broker,
    risk_engine,
    intent,
    market_context: dict,
    strict_point_value_validation: bool,
    require_protected_execution: bool,
    mode: str,
) -> ProtectedExecutionResult:
    symbol = intent.symbol
    action = intent.action

    if strict_point_value_validation:
        ok_val, val_reason = risk_engine.validate_symbol_valuation(
            {
                "symbol": symbol,
                "point_value": market_context.get("point_value", 0.0),
                "point_size": market_context.get("point_size", 0.0),
            }
        )
        if not ok_val:
            return ProtectedExecutionResult(
                success=False,
                mode=mode,
                symbol=symbol,
                action=action,
                lot_size=float(intent.lot_size),
                stop_loss_usd=float(intent.stop_loss_usd),
                take_profit_usd=float(intent.take_profit_usd),
                stop_loss_points=None,
                take_profit_points=None,
                ticket_id=None,
                protection_attached=False,
                reason=val_reason,
            )

    pv = float(market_context.get("point_value", 0.0) or 0.0)
    if pv <= 0:
        return ProtectedExecutionResult(
            success=False,
            mode=mode,
            symbol=symbol,
            action=action,
            lot_size=float(intent.lot_size),
            stop_loss_usd=float(intent.stop_loss_usd),
            take_profit_usd=float(intent.take_profit_usd),
            stop_loss_points=None,
            take_profit_points=None,
            ticket_id=None,
            protection_attached=False,
            reason="invalid point_value",
        )

    sl_points = risk_engine.convert_usd_risk_to_points(intent.stop_loss_usd, intent.lot_size, pv)
    tp_points = risk_engine.convert_usd_risk_to_points(intent.take_profit_usd, intent.lot_size, pv)
    if sl_points <= 0 or tp_points <= 0:
        return ProtectedExecutionResult(
            success=False,
            mode=mode,
            symbol=symbol,
            action=action,
            lot_size=float(intent.lot_size),
            stop_loss_usd=float(intent.stop_loss_usd),
            take_profit_usd=float(intent.take_profit_usd),
            stop_loss_points=float(sl_points),
            take_profit_points=float(tp_points),
            ticket_id=None,
            protection_attached=False,
            reason="invalid sl/tp points",
        )

    side = "buy" if action == "BUY" else "sell"
    if mode == "paper":
        return ProtectedExecutionResult(
            success=True,
            mode=mode,
            symbol=symbol,
            action=action,
            lot_size=float(intent.lot_size),
            stop_loss_usd=float(intent.stop_loss_usd),
            take_profit_usd=float(intent.take_profit_usd),
            stop_loss_points=float(sl_points),
            take_profit_points=float(tp_points),
            ticket_id=None,
            protection_attached=True,
            reason="paper simulation",
        )

    open_res = broker.open_order(symbol, side, float(intent.lot_size))
    if not open_res.get("ok") or not open_res.get("order"):
        return ProtectedExecutionResult(
            success=False,
            mode=mode,
            symbol=symbol,
            action=action,
            lot_size=float(intent.lot_size),
            stop_loss_usd=float(intent.stop_loss_usd),
            take_profit_usd=float(intent.take_profit_usd),
            stop_loss_points=float(sl_points),
            take_profit_points=float(tp_points),
            ticket_id=None,
            protection_attached=False,
            reason=f"open failed: {open_res}",
        )

    ticket = int(open_res.get("order"))
    sltp_res = broker.set_sl_tp_by_points(
        ticket=ticket,
        symbol=symbol,
        side=side,
        sl_points=float(sl_points),
        tp_points=float(tp_points),
    )
    if not sltp_res.get("ok"):
        # safe containment: close immediately
        close_res = broker.close_ticket(ticket)
        reason = f"failed to attach SL/TP; safe containment close attempted: sltp={sltp_res} close={close_res}"
        if not require_protected_execution:
            reason = f"protection attach failed but REQUIRE_PROTECTED_EXECUTION=false: sltp={sltp_res}"
        return ProtectedExecutionResult(
            success=False,
            mode=mode,
            symbol=symbol,
            action=action,
            lot_size=float(intent.lot_size),
            stop_loss_usd=float(intent.stop_loss_usd),
            take_profit_usd=float(intent.take_profit_usd),
            stop_loss_points=float(sl_points),
            take_profit_points=float(tp_points),
            ticket_id=ticket,
            protection_attached=False,
            reason=reason,
        )

    return ProtectedExecutionResult(
        success=True,
        mode=mode,
        symbol=symbol,
        action=action,
        lot_size=float(intent.lot_size),
        stop_loss_usd=float(intent.stop_loss_usd),
        take_profit_usd=float(intent.take_profit_usd),
        stop_loss_points=float(sl_points),
        take_profit_points=float(tp_points),
        ticket_id=ticket,
        protection_attached=True,
        reason="protected execution success",
    )
