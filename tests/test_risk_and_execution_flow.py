from types import SimpleNamespace

from app.risk.engine import RiskEngine
from app.decision.schemas import UnifiedDecision
from app.core.runner import TradingRunner


class FakeBroker:
    def __init__(self, open_ok=True, protect_ok=True):
        self.open_ok = open_ok
        self.protect_ok = protect_ok
        self.open_called = False
        self.protect_called = False
        self.close_called = False

    def open_order(self, symbol, side, lot):
        self.open_called = True
        if not self.open_ok:
            return {"ok": False, "note": "open failed"}
        return {"ok": True, "order": 12345, "symbol": symbol, "side": side, "lot": lot}

    def set_sl_tp_by_points(self, ticket, symbol, side, sl_points, tp_points):
        self.protect_called = True
        if not self.protect_ok:
            return {"ok": False, "note": "protect failed"}
        return {"ok": True, "ticket": ticket}

    def close_ticket(self, ticket):
        self.close_called = True
        return {"ok": True, "ticket": ticket}


def _decision(action="BUY"):
    return UnifiedDecision(
        symbol="XAUUSD",
        final_action=action,
        confidence=0.9,
        source_alignment="aligned",
        dexter_bias="bullish",
        committee_action=action,
        do_not_trade=False,
        reason="ok",
        eligible_for_risk_review=True,
        summary_for_telegram="",
    )


def test_build_execution_intent_conservative():
    eng = RiskEngine(0.02, 0.05, 20, 5, min_lot=0.01, max_lot=1.0)
    rr = eng.build_execution_intent(
        account_state={"balance": 1000, "equity": 1000},
        symbol_state={"symbol": "XAUUSD", "point_value": 1.0, "point_size": 0.01},
        unified_decision=_decision("BUY"),
        mode="paper",
        risk_mode="conservative",
        strict_point_value_validation=True,
    )
    assert rr.ok is True
    assert rr.intent is not None
    assert rr.intent.lot_size == 0.01


def test_build_execution_intent_aggressive():
    eng = RiskEngine(0.02, 0.05, 20, 5, min_lot=0.01, max_lot=1.0)
    rr = eng.build_execution_intent(
        account_state={"balance": 2000, "equity": 2000},
        symbol_state={"symbol": "XAUUSD", "point_value": 1.0, "point_size": 0.01},
        unified_decision=_decision("BUY"),
        mode="live",
        risk_mode="aggressive",
        strict_point_value_validation=True,
    )
    assert rr.ok is True
    assert rr.intent is not None
    assert rr.intent.lot_size >= 0.02


def test_build_execution_intent_blocks_ambiguous_valuation():
    eng = RiskEngine(0.02, 0.05, 20, 5)
    rr = eng.build_execution_intent(
        account_state={"balance": 1000, "equity": 1000},
        symbol_state={"symbol": "XAUUSD", "point_value": 0.0, "point_size": 0.0},
        unified_decision=_decision("BUY"),
        mode="live",
        risk_mode="balanced",
        strict_point_value_validation=True,
    )
    assert rr.ok is False


def _runner_for_exec(mode="live", open_ok=True, protect_ok=True):
    r = TradingRunner.__new__(TradingRunner)
    r.mode = mode
    r.broker = FakeBroker(open_ok=open_ok, protect_ok=protect_ok)
    r.risk = RiskEngine(0.02, 0.05, 20, 5)
    r._validate_symbol_valuation = TradingRunner._validate_symbol_valuation.__get__(r, TradingRunner)
    return r


def test_protected_execution_attaches_sltp_after_open():
    r = _runner_for_exec(mode="live", open_ok=True, protect_ok=True)
    intent = SimpleNamespace(symbol="XAUUSD", action="BUY", lot_size=0.01, stop_loss_usd=5.0, take_profit_usd=15.0)
    res = TradingRunner._execute_protected_trade(r, intent, {"point_value": 1.0, "point_size": 0.01}, 0.8)
    assert res["ok"] is True
    assert r.broker.open_called is True
    assert r.broker.protect_called is True


def test_protected_execution_fails_safe_when_sltp_attach_fails():
    r = _runner_for_exec(mode="live", open_ok=True, protect_ok=False)
    intent = SimpleNamespace(symbol="XAUUSD", action="BUY", lot_size=0.01, stop_loss_usd=5.0, take_profit_usd=15.0)
    res = TradingRunner._execute_protected_trade(r, intent, {"point_value": 1.0, "point_size": 0.01}, 0.8)
    assert res["ok"] is False
    assert res["stage"] == "protect"
    assert r.broker.close_called is True


def test_paper_mode_records_simulated_trade():
    r = _runner_for_exec(mode="paper", open_ok=True, protect_ok=True)
    intent = SimpleNamespace(symbol="XAUUSD", action="SELL", lot_size=0.02, stop_loss_usd=10.0, take_profit_usd=30.0)
    res = TradingRunner._execute_protected_trade(r, intent, {"point_value": 1.0, "point_size": 0.01}, 0.7)
    assert res["ok"] is True
    assert res["simulated"] is True


def test_live_mode_refuses_unsafe_execution_on_valuation_ambiguity():
    r = _runner_for_exec(mode="live", open_ok=True, protect_ok=True)
    intent = SimpleNamespace(symbol="XAUUSD", action="BUY", lot_size=0.01, stop_loss_usd=5.0, take_profit_usd=15.0)
    res = TradingRunner._execute_protected_trade(r, intent, {"point_value": 0.0, "point_size": 0.0}, 0.9)
    assert res["ok"] is False
    assert res["stage"] == "valuation"
