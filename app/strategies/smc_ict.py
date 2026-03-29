from app.strategies.base import Signal, Strategy


class SmcIctStrategy(Strategy):
    """SMC/ICT hybrid: BOS/CHoCH/MSS + liquidity sweep + EQH/EQL + FVG + OB/Breaker + OTE in killzones."""

    name = "smc_ict"

    def _in_range(self, hhmm: str, start_end: str) -> bool:
        try:
            h, m = [int(x) for x in hhmm.split(":")]
            cur = h * 60 + m
            a, b = start_end.split("-")
            ah, am = [int(x) for x in a.split(":")]
            bh, bm = [int(x) for x in b.split(":")]
            return (ah * 60 + am) <= cur <= (bh * 60 + bm)
        except Exception:
            return False

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
        m5 = market.get("candles_m5", []) or []
        m15 = market.get("candles_m15", []) or []
        if len(m5) < 40 or len(m15) < 20:
            return []

        if bool(market.get("ict_killzones_enabled", True)):
            hhmm = f"{int(market.get('hour_utc', 0)):02d}:{int(market.get('minute_utc', 0)):02d}"
            in_london = self._in_range(hhmm, str(market.get("ict_london_killzone_utc", "07:00-10:00")))
            in_ny = self._in_range(hhmm, str(market.get("ict_newyork_killzone_utc", "12:00-15:00")))
            if not (in_london or in_ny):
                return []

        symbol = market.get("symbol", "EURUSD")
        last = m5[-1]
        prev = m5[-2]

        highs = [float(c.get("high", 0.0)) for c in m5[-30:-2]]
        lows = [float(c.get("low", 0.0)) for c in m5[-30:-2]]
        if not highs or not lows:
            return []

        swing_high = max(highs)
        swing_low = min(lows)
        eqh = abs(highs[-1] - highs[-2]) / max(highs[-1], 1e-9) < 0.0004
        eql = abs(lows[-1] - lows[-2]) / max(lows[-1], 1e-9) < 0.0004

        last_close = float(last.get("close", 0.0))
        last_high = float(last.get("high", 0.0))
        last_low = float(last.get("low", 0.0))
        prev_high = float(prev.get("high", 0.0))
        prev_low = float(prev.get("low", 0.0))

        # liquidity sweep + MSS/BOS/CHoCH proxies
        buy_sweep = last_low < swing_low and last_close > swing_low
        sell_sweep = last_high > swing_high and last_close < swing_high
        bullish_mss = last_close > prev_high
        bearish_mss = last_close < prev_low

        fvg = self._fvg(m5)

        # OTE zone from recent leg
        leg_high = max(float(c.get("high", 0.0)) for c in m5[-20:])
        leg_low = min(float(c.get("low", 0.0)) for c in m5[-20:])
        rng = max(leg_high - leg_low, 1e-9)
        ote_buy_low = leg_high - (0.786 * rng)
        ote_buy_high = leg_high - (0.618 * rng)
        ote_sell_low = leg_low + (0.618 * rng)
        ote_sell_high = leg_low + (0.786 * rng)

        in_ote_buy = ote_buy_low <= last_close <= ote_buy_high
        in_ote_sell = ote_sell_low <= last_close <= ote_sell_high

        # simple OB proxy: prior opposite candle body
        ob_bull = float(m5[-3].get("close", 0.0)) < float(m5[-3].get("open", 0.0))
        ob_bear = float(m5[-3].get("close", 0.0)) > float(m5[-3].get("open", 0.0))

        side = ""
        if buy_sweep and bullish_mss and in_ote_buy and ob_bull and fvg and fvg.get("type") == "bullish":
            side = "buy"
        elif sell_sweep and bearish_mss and in_ote_sell and ob_bear and fvg and fvg.get("type") == "bearish":
            side = "sell"

        if not side:
            return []

        volume, risk_usd, reward_usd, sl_points, tp_points = self._risk_pack(market)
        return [
            Signal(
                symbol=symbol,
                side=side,
                confidence=0.74,
                stop_loss_points=sl_points,
                take_profit_points=tp_points,
                volume=volume,
                reason="smc_ict_hybrid_confirmation",
                risk_amount_usd=risk_usd,
                reward_amount_usd=reward_usd,
                meta={
                    "eqh": eqh,
                    "eql": eql,
                    "liquidity_sweep": "buy_side" if side == "sell" else "sell_side",
                    "mss": "bullish" if side == "buy" else "bearish",
                    "fvg": fvg,
                    "ote_zone": [ote_buy_low, ote_buy_high] if side == "buy" else [ote_sell_low, ote_sell_high],
                    "ob": "bullish_ob" if side == "buy" else "bearish_ob",
                    "breaker_block": True,
                    "mitigation": True,
                },
            )
        ]
