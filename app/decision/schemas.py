from datetime import datetime
from pydantic import BaseModel, Field


class DexterResearchReport(BaseModel):
    symbol: str
    generated_at: datetime
    timeframe_bias: str  # bullish | bearish | neutral
    macro_summary: str = ""
    news_summary: str = ""
    fundamental_summary: str = ""
    technical_summary: str = ""
    conviction_score: float = Field(ge=0.0, le=1.0)
    do_not_trade: bool = False
    invalidation_notes: str = ""
    risk_notes: str = ""
    summary_for_telegram: str = ""
    raw_payload: dict = Field(default_factory=dict)


class TradingCommitteeReport(BaseModel):
    symbol: str
    generated_at: datetime
    action: str  # BUY | SELL | HOLD
    confidence: float = Field(ge=0.0, le=1.0)
    bullish_thesis: str = ""
    bearish_thesis: str = ""
    technical_vote: str = ""
    sentiment_vote: str = ""
    news_vote: str = ""
    risk_team_verdict: str = ""
    portfolio_team_verdict: str = ""
    do_not_trade: bool = False
    summary_for_telegram: str = ""
    raw_payload: dict = Field(default_factory=dict)


class UnifiedDecision(BaseModel):
    symbol: str
    final_action: str  # BUY | SELL | HOLD
    confidence: float
    source_alignment: str  # aligned | conflicting | blocked
    dexter_bias: str
    committee_action: str
    do_not_trade: bool
    reason: str
    eligible_for_risk_review: bool
    summary_for_telegram: str


class ExecutionIntent(BaseModel):
    symbol: str
    action: str  # BUY | SELL
    mode: str  # paper | live
    risk_percent: float
    stop_loss_usd: float
    take_profit_usd: float
    lot_size: float
    rationale: str
