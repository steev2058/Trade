from app.strategies.base import Signal, Strategy


class ScalperStrategy(Strategy):
    """One-candle momentum scalper using EMA 8/13/21 + RSI + micro-FVG."""

    name = "scalper"

    def _ema(self, values, period: int):
        if not values:
            return 0.0
        alpha = 2 / (period + 1)
        e = values[0]
        for v in values[1:]:
            e = alpha * v + (1 - alpha) * e
        return float(e)

    def _rsi(self, values, period=7):
        if len(values) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, len(values)):
            d = values[i] - values[i - 1]
            gains.append(max(d, 0))
            losses.append(max(-d, 0))
        ag = sum(gains[-period:]) / period
        al = sum(losses[-period:]) / period
        if al == 0:
            return 100.0
        rs = ag / al
        return float(100 - 100 / (1 + rs))

    async def generate(self, market: dict) -> list[Signal]:
        if market.get("session") not in {"asia", "london", "new_york", "london_ny_overlap"}:
            return []
        if market.get("news_high_impact", False):
            return []

        m5 = market.get("candles_m5", []) or []
        if len(m5) < 30:
            return []

        closes = [float(c.get("close", 0.0)) for c in m5]
        ema8 = self._ema(closes, 8)
        ema13 = self._ema(closes, 13)
        ema21 = self._ema(closes, 21)
        rsi = self._rsi(closes, 7)

        c0, c2 = m5[-3], m5[-1]
        micro_fvg_bull = float(c0.get("high", 0.0)) < float(c2.get("low", 0.0))
        micro_fvg_bear = float(c0.get("low", 0.0)) > float(c2.get("high", 0.0))

        side = ""
        if ema8 > ema13 > ema21 and rsi > 53 and micro_fvg_bull:
            side = "buy"
        elif ema8 < ema13 < ema21 and rsi < 47 and micro_fvg_bear:
            side = "sell"

        if not side:
            return []

        volume, risk_usd, reward_usd, sl_points, tp_points = self._risk_pack(market)
        return [
            Signal(
                symbol=market.get("symbol", "EURUSD"),
                side=side,
                confidence=0.64,
                stop_loss_points=sl_points,
                take_profit_points=tp_points,
                volume=volume,
                reason="scalper_ema_rsi_microfvg",
                risk_amount_usd=risk_usd,
                reward_amount_usd=reward_usd,
                meta={"ema8": ema8, "ema13": ema13, "ema21": ema21, "rsi": rsi},
            )
        ]
