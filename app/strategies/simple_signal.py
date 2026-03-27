class SimpleSignalStrategy:
    name = "simple_signal"

    async def generate(self, market: dict):
        symbol = market.get('symbol', 'XAUUSD.m')
        ema9 = float(market.get('ema9', 0.0))
        ema21 = float(market.get('ema21', 0.0))
        rsi7 = float(market.get('rsi7', 50.0))
        session = market.get('session', '')

        # session filter
        if session not in ('london', 'london_ny_overlap', 'new_york'):
            return []

        if ema9 > ema21 and rsi7 > 52:
            return [{"side": "buy", "symbol": symbol, "confidence": 0.62, "meta": {"ema9": ema9, "ema21": ema21, "rsi7": rsi7}}]
        if ema9 < ema21 and rsi7 < 48:
            return [{"side": "sell", "symbol": symbol, "confidence": 0.62, "meta": {"ema9": ema9, "ema21": ema21, "rsi7": rsi7}}]

        return []
