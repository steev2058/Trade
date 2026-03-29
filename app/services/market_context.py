def build_market_context(
    *,
    symbol: str,
    mode: str,
    session: str,
    risk_params: dict,
    balance: dict,
    positions: list,
    ticks: dict,
    candles_m5: list,
    candles_m15: list,
) -> dict:
    t = ticks.get(symbol, {}) if isinstance(ticks, dict) else {}
    bid = float(t.get("bid", 0.0) or 0.0)
    ask = float(t.get("ask", 0.0) or 0.0)
    spread = (ask - bid) if ask > 0 and bid > 0 else 0.0

    point_value = float(t.get("point_value", 0.0) or 0.0)
    point_size = float(t.get("point_size", 0.0) or 0.0)

    return {
        "symbol": symbol,
        "mode": mode,
        "session": session,
        "timeframes": ["M5", "M15"],
        "risk_params": risk_params,
        "account": {
            "balance": float(balance.get("balance", 0.0) or 0.0),
            "equity": float(balance.get("equity", 0.0) or 0.0),
            "currency": balance.get("currency", "USD"),
        },
        "open_positions_count": len(positions or []),
        "price": {"bid": bid, "ask": ask, "spread": spread},
        "broker_metadata": {
            "point_value": point_value,
            "point_size": point_size,
        },
        "candles_m5": candles_m5,
        "candles_m15": candles_m15,
        "missing_price_data": bool(bid <= 0 or ask <= 0),
        "missing_symbol_metadata": bool(point_value <= 0 or point_size <= 0),
    }
