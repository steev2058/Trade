from datetime import datetime, timezone

from app.decision.consensus import build_unified_decision
from app.decision.schemas import DexterResearchReport, TradingCommitteeReport


def _dexter(bias="bullish", dnt=False, conv=0.9):
    return DexterResearchReport(
        symbol="XAUUSD",
        generated_at=datetime.now(timezone.utc),
        timeframe_bias=bias,
        macro_summary="",
        news_summary="",
        fundamental_summary="",
        technical_summary="",
        conviction_score=conv,
        do_not_trade=dnt,
        invalidation_notes="",
        risk_notes="",
        summary_for_telegram="",
        raw_payload={},
    )


def _committee(action="BUY", dnt=False, conf=0.9):
    return TradingCommitteeReport(
        symbol="XAUUSD",
        generated_at=datetime.now(timezone.utc),
        action=action,
        confidence=conf,
        bullish_thesis="",
        bearish_thesis="",
        technical_vote="",
        sentiment_vote="",
        news_vote="",
        risk_team_verdict="",
        portfolio_team_verdict="",
        do_not_trade=dnt,
        summary_for_telegram="",
        raw_payload={},
    )


def test_consensus_aligned_buy():
    d = build_unified_decision(_dexter("bullish"), _committee("BUY"), "XAUUSD", 0.75)
    assert d.final_action == "BUY"
    assert d.eligible_for_risk_review is True


def test_consensus_aligned_sell():
    d = build_unified_decision(_dexter("bearish"), _committee("SELL"), "XAUUSD", 0.75)
    assert d.final_action == "SELL"
    assert d.source_alignment == "aligned"


def test_consensus_disagreement_hold():
    d = build_unified_decision(_dexter("bullish"), _committee("SELL"), "XAUUSD", 0.75)
    assert d.final_action == "HOLD"
    assert d.source_alignment == "conflicting"


def test_consensus_do_not_trade_hold():
    d = build_unified_decision(_dexter("bullish", dnt=True), _committee("BUY"), "XAUUSD", 0.75)
    assert d.final_action == "HOLD"


def test_consensus_missing_report_hold():
    d = build_unified_decision(None, _committee("BUY"), "XAUUSD", 0.75)
    assert d.final_action == "HOLD"


def test_confidence_below_threshold_hold():
    d = build_unified_decision(_dexter("bullish"), _committee("BUY", conf=0.5), "XAUUSD", 0.75)
    assert d.final_action == "HOLD"


def test_external_service_failure_results_in_hold():
    # unavailable external service -> missing report -> HOLD
    d = build_unified_decision(_dexter("bullish"), None, "XAUUSD", 0.75)
    assert d.final_action == "HOLD"


def test_low_confidence_results_in_hold():
    d = build_unified_decision(_dexter("bullish", conv=0.9), _committee("BUY", conf=0.6), "XAUUSD", 0.75)
    assert d.final_action == "HOLD"
