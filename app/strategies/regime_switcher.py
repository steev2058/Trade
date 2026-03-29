from dataclasses import dataclass

from app.strategies.base import Strategy


@dataclass
class RegimeDecision:
    active_strategy_names: list[str]
    weights: dict[str, float]


class RegimeSwitcher:
    """Selects strategy set by session, volatility, structure and recent performance."""

    def select(self, market: dict, candidates: list[Strategy]) -> RegimeDecision:
        name_to_strategy = {s.name: s for s in candidates}
        session = market.get("session", "off_hours")
        volatility = float(market.get("atr_pct", 0.0) or 0.0)
        trend_strength = abs(float(market.get("ema9", 0.0) - market.get("ema21", 0.0) or 0.0))
        noisy = bool(market.get("is_noisy", False))
        perf = market.get("strategy_performance", {}) or {}

        weights: dict[str, float] = {}

        for name in name_to_strategy:
            base = 0.35
            if name == "smc_ict":
                base = 0.9 if session in {"london", "new_york", "london_ny_overlap"} else 0.2
                if noisy:
                    base -= 0.2
            elif name == "scalper":
                base = 0.75 if session in {"london", "london_ny_overlap", "new_york"} and volatility < 0.012 else 0.25
                if noisy:
                    base -= 0.15
            elif name == "london_ny_session":
                base = 0.9 if session in {"london", "london_ny_overlap", "new_york"} else 0.1
            elif name == "news":
                base = 0.15 if market.get("news_high_impact", False) else 0.0
            elif name == "adaptive_weighting":
                base = 0.6

            # favor trending regimes for structure strategies
            if name in {"smc_ict", "london_ny_session"}:
                base += 0.1 if trend_strength > 0 else 0

            p = perf.get(name, {})
            wr = float(p.get("win_rate", 0.5) or 0.5)
            n = int(p.get("n", 0) or 0)
            if n >= 5:
                base *= 0.8 + min(max((wr - 0.5) * 1.2, -0.3), 0.3)

            weights[name] = max(0.0, min(base, 1.2))

        active = [name for name, w in weights.items() if w >= 0.3]
        if not active:
            active = [s.name for s in candidates]
            weights = {s.name: 1.0 for s in candidates}

        return RegimeDecision(active_strategy_names=active, weights=weights)
