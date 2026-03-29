from app.strategies.base import Signal, Strategy


class AdaptiveWeightingStrategy(Strategy):
    """Adaptive vote generator based on strategy recent performance + market votes."""

    name = "adaptive_weighting"

    async def generate(self, market: dict) -> list[Signal]:
        weighted_votes = market.get("weighted_votes", {}) or {}
        perf = market.get("strategy_performance", {}) or {}
        symbol = market.get("symbol", "EURUSD")

        buy = float(weighted_votes.get("buy", 0.0))
        sell = float(weighted_votes.get("sell", 0.0))

        # boost/deboost with performance bias from core strategies
        for k in ("smc_ict", "scalper", "london_ny_session"):
            p = perf.get(k, {})
            n = int(p.get("n", 0) or 0)
            if n < 3:
                continue
            wr = float(p.get("win_rate", 0.5) or 0.5)
            delta = (wr - 0.5) * 0.8
            if market.get("bias") == "bullish":
                buy += max(delta, 0)
                sell -= max(delta, 0)
            elif market.get("bias") == "bearish":
                sell += max(delta, 0)
                buy -= max(delta, 0)

        if abs(buy - sell) < 0.12:
            return []

        side = "buy" if buy > sell else "sell"
        confidence = min(max(abs(buy - sell), 0.5), 0.85)
        volume, risk_usd, reward_usd, sl_points, tp_points = self._risk_pack(market)
        return [
            Signal(
                symbol=symbol,
                side=side,
                confidence=confidence,
                stop_loss_points=sl_points,
                take_profit_points=tp_points,
                volume=volume,
                reason="adaptive_weighting_performance",
                risk_amount_usd=risk_usd,
                reward_amount_usd=reward_usd,
                meta={"buy_score": round(buy, 4), "sell_score": round(sell, 4)},
            )
        ]
