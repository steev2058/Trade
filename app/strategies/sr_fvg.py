from app.strategies.base import Signal, Strategy


class SrFvgStrategy(Strategy):
    """Multi-timeframe Support/Resistance + FVG confluence strategy."""

    name = "sr_fvg"

    def _swing_levels(self, candles, n=20):
        highs = [float(c.get("high", 0.0)) for c in candles]
        lows = [float(c.get("low", 0.0)) for c in candles]
        if not highs or not lows:
            return None, None
        return min(lows[-n:]), max(highs[-n:])

    def _fvg(self, candles):
        if len(candles) < 3:
            return None
        c0, _, c2 = candles[-3], candles[-2], candles[-1]
        if float(c0.get("high", 0.0)) < float(c2.get("low", 0.0)):
            return {"type": "bullish", "low": float(c0.get("high", 0.0)), "high": float(c2.get("low", 0.0))}
        if float(c0.get("low", 0.0)) > float(c2.get("high", 0.0)):
            return {"type": "bearish", "low": float(c2.get("high", 0.0)), "high": float(c0.get("low", 0.0))}
        return None

    async def generate(self, market: dict) -> list[Signal]:
        symbol = market.get("symbol", "XAUUSD.m")
        m5 = market.get("candles_m5", []) or []
        m15 = market.get("candles_m15", []) or []
        if len(m5) < 30 or len(m15) < 20:
            return []

        last = float(m5[-1].get("close", 0.0))
        if last <= 0:
            return []

        s5, r5 = self._swing_levels(m5, 24)
        s15, r15 = self._swing_levels(m15, 16)
        if s5 is None or s15 is None:
            return []

        support = (s5 + s15) / 2.0
        resistance = (r5 + r15) / 2.0
        fvg = self._fvg(m5)

        near_s = abs(last - support) / max(last, 1e-9) <= 0.0025
        near_r = abs(last - resistance) / max(last, 1e-9) <= 0.0025

        side = ""
        if fvg and fvg["type"] == "bullish" and near_s:
            side = "buy"
        elif fvg and fvg["type"] == "bearish" and near_r:
            side = "sell"

        if not side:
            return []

        volume, risk_usd, reward_usd, sl_points, tp_points = self._risk_pack(market)
        return [
            Signal(
                symbol=symbol,
                side=side,
                confidence=0.69,
                stop_loss_points=sl_points,
                take_profit_points=tp_points,
                volume=volume,
                reason="sr_fvg_mtf_confluence",
                risk_amount_usd=risk_usd,
                reward_amount_usd=reward_usd,
                meta={"support": support, "resistance": resistance, "fvg": fvg, "tf": "M5+M15"},
            )
        ]
