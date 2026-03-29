from app.strategies.base import Signal, Strategy


class LondonNySessionStrategy(Strategy):
    """Session breakout/continuation strategy for London, NY and overlap only."""

    name = "london_ny_session"

    async def generate(self, market: dict) -> list[Signal]:
        session = market.get("session")
        if session not in {"london", "new_york", "london_ny_overlap"}:
            return []
        if market.get("volatility") == "extreme":
            return []

        m5 = market.get("candles_m5", []) or []
        if len(m5) < 24:
            return []

        recent = m5[-12:]
        range_high = max(float(c.get("high", 0.0)) for c in recent)
        range_low = min(float(c.get("low", 0.0)) for c in recent)
        last = m5[-1]
        close = float(last.get("close", 0.0))

        side = ""
        if close > range_high:
            side = "buy"
        elif close < range_low:
            side = "sell"
        else:
            # continuation bias
            if market.get("bias") == "bullish" and close > float(m5[-2].get("high", 0.0)):
                side = "buy"
            elif market.get("bias") == "bearish" and close < float(m5[-2].get("low", 0.0)):
                side = "sell"

        if not side:
            return []

        volume, risk_usd, reward_usd, sl_points, tp_points = self._risk_pack(market)
        return [
            Signal(
                symbol=market.get("symbol", "EURUSD"),
                side=side,
                confidence=0.63,
                stop_loss_points=sl_points,
                take_profit_points=tp_points,
                volume=volume,
                reason="session_breakout_continuation",
                risk_amount_usd=risk_usd,
                reward_amount_usd=reward_usd,
                meta={"range_high": range_high, "range_low": range_low},
            )
        ]
