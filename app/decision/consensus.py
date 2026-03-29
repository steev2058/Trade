from app.decision.schemas import DexterResearchReport, TradingCommitteeReport, UnifiedDecision


def _dexter_action(bias: str) -> str:
    b = (bias or "").lower().strip()
    if b == "bullish":
        return "BUY"
    if b == "bearish":
        return "SELL"
    return "HOLD"


def build_unified_decision(
    dexter_report: DexterResearchReport | None,
    committee_report: TradingCommitteeReport | None,
    symbol: str,
    min_confidence: float = 0.75,
) -> UnifiedDecision:
    if not dexter_report or not committee_report:
        return UnifiedDecision(
            symbol=symbol,
            final_action="HOLD",
            confidence=0.0,
            source_alignment="blocked",
            dexter_bias=getattr(dexter_report, "timeframe_bias", "unknown"),
            committee_action=getattr(committee_report, "action", "unknown"),
            do_not_trade=True,
            reason="missing external analysis",
            eligible_for_risk_review=False,
            summary_for_telegram=f"{symbol}: HOLD | missing external analysis",
        )

    if dexter_report.do_not_trade or committee_report.do_not_trade:
        return UnifiedDecision(
            symbol=symbol,
            final_action="HOLD",
            confidence=0.0,
            source_alignment="blocked",
            dexter_bias=dexter_report.timeframe_bias,
            committee_action=committee_report.action,
            do_not_trade=True,
            reason="blocked by external do_not_trade",
            eligible_for_risk_review=False,
            summary_for_telegram=f"{symbol}: HOLD | blocked (do_not_trade)",
        )

    dexter_action = _dexter_action(dexter_report.timeframe_bias)
    committee_action = (committee_report.action or "HOLD").upper().strip()

    if dexter_action != committee_action:
        return UnifiedDecision(
            symbol=symbol,
            final_action="HOLD",
            confidence=0.0,
            source_alignment="conflicting",
            dexter_bias=dexter_report.timeframe_bias,
            committee_action=committee_action,
            do_not_trade=False,
            reason="dexter and committee conflict",
            eligible_for_risk_review=False,
            summary_for_telegram=f"{symbol}: HOLD | conflict dexter={dexter_action} committee={committee_action}",
        )

    if committee_action == "HOLD":
        return UnifiedDecision(
            symbol=symbol,
            final_action="HOLD",
            confidence=0.0,
            source_alignment="blocked",
            dexter_bias=dexter_report.timeframe_bias,
            committee_action=committee_action,
            do_not_trade=False,
            reason="committee hold",
            eligible_for_risk_review=False,
            summary_for_telegram=f"{symbol}: HOLD | committee=HOLD",
        )

    if float(committee_report.confidence) < float(min_confidence):
        return UnifiedDecision(
            symbol=symbol,
            final_action="HOLD",
            confidence=float(committee_report.confidence),
            source_alignment="blocked",
            dexter_bias=dexter_report.timeframe_bias,
            committee_action=committee_action,
            do_not_trade=False,
            reason="committee confidence below threshold",
            eligible_for_risk_review=False,
            summary_for_telegram=f"{symbol}: HOLD | low confidence {committee_report.confidence:.2f}",
        )

    conf = min(float(dexter_report.conviction_score), float(committee_report.confidence))
    return UnifiedDecision(
        symbol=symbol,
        final_action=committee_action,
        confidence=conf,
        source_alignment="aligned",
        dexter_bias=dexter_report.timeframe_bias,
        committee_action=committee_action,
        do_not_trade=False,
        reason="aligned external decision",
        eligible_for_risk_review=True,
        summary_for_telegram=f"{symbol}: {committee_action} | aligned | conf={conf:.2f}",
    )
