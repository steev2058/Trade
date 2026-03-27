class SimpleSignalStrategy:
    name = "simple_signal"

    async def generate(self, market: dict):
        # very light real-time heuristic on open positions PnL + session bias placeholder
        # output: [{'side': 'buy'|'sell', 'symbol': 'XAUUSD.m', 'confidence': 0.55}]
        symbol = market.get('symbol', 'XAUUSD.m')
        bias = market.get('bias', 'neutral')
        momentum = market.get('micro_momentum', 'flat')

        if bias == 'bullish' or momentum == 'up':
            return [{"side": "buy", "symbol": symbol, "confidence": 0.55}]
        if bias == 'bearish' or momentum == 'down':
            return [{"side": "sell", "symbol": symbol, "confidence": 0.55}]

        # session-based fallback
        session = market.get('session', '')
        if session in ('london', 'london_ny_overlap'):
            return [{"side": "buy", "symbol": symbol, "confidence": 0.51}]
        return [{"side": "sell", "symbol": symbol, "confidence": 0.51}]
