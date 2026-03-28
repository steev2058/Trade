from app.core.settings import settings


class IctSignalStrategy:
    name = "ict_signal"

    def _in_range(self, hhmm: str, start_end: str) -> bool:
        try:
            h, m = [int(x) for x in hhmm.split(':')]
            cur = h * 60 + m
            start, end = start_end.split('-')
            sh, sm = [int(x) for x in start.split(':')]
            eh, em = [int(x) for x in end.split(':')]
            a = sh * 60 + sm
            b = eh * 60 + em
            return a <= cur <= b
        except Exception:
            return False

    def _fvg(self, candles):
        if len(candles) < 3:
            return None
        c0, c1, c2 = candles[-3], candles[-2], candles[-1]
        # bullish imbalance
        if c0.get("high", 0.0) < c2.get("low", 0.0):
            return {"type": "bullish", "low": float(c0.get("high", 0.0)), "high": float(c2.get("low", 0.0))}
        # bearish imbalance
        if c0.get("low", 0.0) > c2.get("high", 0.0):
            return {"type": "bearish", "low": float(c2.get("high", 0.0)), "high": float(c0.get("low", 0.0))}
        return None

    async def generate(self, market: dict):
        symbol = market.get("symbol", "XAUUSD.m")
        candles = market.get("candles_m5", []) or []
        if len(candles) < 25:
            return []

        if bool(settings.ict_killzones_enabled):
            hh = int(market.get("hour_utc", 0))
            mm = int(market.get("minute_utc", 0))
            hhmm = f"{hh:02d}:{mm:02d}"
            in_london = self._in_range(hhmm, settings.ict_london_killzone_utc)
            in_ny = self._in_range(hhmm, settings.ict_newyork_killzone_utc)
            if not (in_london or in_ny):
                return []

        last = candles[-1]
        prev = candles[-2]
        prev20 = candles[-22:-2]
        if not prev20:
            return []

        prev_high = max(float(c.get("high", 0.0)) for c in prev20)
        prev_low = min(float(c.get("low", 0.0)) for c in prev20)

        # ICT proxies:
        # 1) liquidity sweep
        bullish_sweep = float(last.get("low", 0.0)) < prev_low and float(last.get("close", 0.0)) > prev_low
        bearish_sweep = float(last.get("high", 0.0)) > prev_high and float(last.get("close", 0.0)) < prev_high

        # 2) market structure shift (MSS) proxy against previous candle
        bullish_mss = float(last.get("close", 0.0)) > float(prev.get("high", 0.0))
        bearish_mss = float(last.get("close", 0.0)) < float(prev.get("low", 0.0))

        # 3) fair value gap
        fvg = self._fvg(candles)

        if bullish_sweep and bullish_mss and fvg and fvg.get("type") == "bullish":
            return [{
                "side": "buy",
                "symbol": symbol,
                "confidence": 0.71,
                "meta": {
                    "model": "ICT",
                    "liquidity": "sell-side sweep",
                    "mss": "bullish",
                    "fvg": fvg,
                    "range_low": prev_low,
                    "range_high": prev_high,
                },
            }]

        if bearish_sweep and bearish_mss and fvg and fvg.get("type") == "bearish":
            return [{
                "side": "sell",
                "symbol": symbol,
                "confidence": 0.71,
                "meta": {
                    "model": "ICT",
                    "liquidity": "buy-side sweep",
                    "mss": "bearish",
                    "fvg": fvg,
                    "range_low": prev_low,
                    "range_high": prev_high,
                },
            }]

        return []
