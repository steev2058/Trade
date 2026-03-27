class SrFvgStrategy:
    name = "sr_fvg"

    def _swing_levels(self, candles):
        highs = [c.get('high', 0.0) for c in candles]
        lows = [c.get('low', 0.0) for c in candles]
        if not highs or not lows:
            return None, None
        resistance = max(highs[-20:])
        support = min(lows[-20:])
        return support, resistance

    def _detect_fvg(self, candles):
        # bullish FVG if candle[i-2].high < candle[i].low
        # bearish FVG if candle[i-2].low > candle[i].high
        if len(candles) < 3:
            return None
        c0, c1, c2 = candles[-3], candles[-2], candles[-1]
        if c0.get('high', 0) < c2.get('low', 0):
            return {"type": "bullish", "low": c0.get('high'), "high": c2.get('low')}
        if c0.get('low', 0) > c2.get('high', 0):
            return {"type": "bearish", "low": c2.get('high'), "high": c0.get('low')}
        return None

    async def generate(self, market: dict):
        symbol = market.get('symbol', 'XAUUSD.m')
        m5 = market.get('candles_m5', []) or []
        m15 = market.get('candles_m15', []) or []
        last_price = float(market.get('last_price', 0.0))
        if not m5 or not m15 or last_price <= 0:
            return []

        s5, r5 = self._swing_levels(m5)
        s15, r15 = self._swing_levels(m15)
        if s5 is None or s15 is None:
            return []

        support = (s5 + s15) / 2.0
        resistance = (r5 + r15) / 2.0
        fvg = self._detect_fvg(m5)

        near_support = abs(last_price - support) / max(last_price, 1e-9) < 0.0025
        near_resistance = abs(last_price - resistance) / max(last_price, 1e-9) < 0.0025

        if fvg and fvg['type'] == 'bullish' and near_support:
            return [{
                "side": "buy",
                "symbol": symbol,
                "confidence": 0.68,
                "meta": {
                    "support": support,
                    "resistance": resistance,
                    "fvg": fvg,
                    "tf": "M5+M15"
                }
            }]

        if fvg and fvg['type'] == 'bearish' and near_resistance:
            return [{
                "side": "sell",
                "symbol": symbol,
                "confidence": 0.68,
                "meta": {
                    "support": support,
                    "resistance": resistance,
                    "fvg": fvg,
                    "tf": "M5+M15"
                }
            }]

        return []
