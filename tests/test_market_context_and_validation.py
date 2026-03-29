from app.services.market_context import build_market_context
from app.core.runner import TradingRunner


def test_market_context_missing_metadata_flag():
    ctx = build_market_context(
        symbol="XAUUSD",
        mode="paper",
        session="london",
        risk_params={},
        balance={"balance": 1000, "equity": 1000, "currency": "USD"},
        positions=[],
        ticks={"XAUUSD": {"bid": 0, "ask": 0, "point_value": 0, "point_size": 0}},
        candles_m5=[],
        candles_m15=[],
    )
    assert ctx["missing_price_data"] is True
    assert ctx["missing_symbol_metadata"] is True


def test_strict_point_value_ambiguity_blocked():
    r = TradingRunner.__new__(TradingRunner)
    ok, reason = TradingRunner._validate_symbol_valuation(r, {"point_value": 0.0, "point_size": 0.0}, "XAUUSD")
    assert ok is False
    assert "ambiguous valuation" in reason
