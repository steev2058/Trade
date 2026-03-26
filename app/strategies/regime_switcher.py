from dataclasses import dataclass

from app.strategies.base import Strategy


@dataclass
class RegimeDecision:
    active_strategy_names: list[str]
    weights: dict[str, float]


class RegimeSwitcher:
    """Selects and weights strategies by volatility/session/news context."""

    def select(self, market: dict, candidates: list[Strategy]) -> RegimeDecision:
        name_to_strategy = {s.name: s for s in candidates}
        volatility = market.get("volatility", "medium")
        session = market.get("session", "off_hours")
        news_high_impact = market.get("news_high_impact", False)

        weights: dict[str, float] = {}

        if "news" in name_to_strategy:
            weights["news"] = 1.0 if news_high_impact else 0.2

        if "scalper" in name_to_strategy:
            if news_high_impact:
                weights["scalper"] = 0.0
            elif volatility in {"low", "medium"}:
                weights["scalper"] = 0.8
            else:
                weights["scalper"] = 0.2

        if "smc_ict" in name_to_strategy:
            weights["smc_ict"] = 0.7 if session in {"london", "new_york", "london_ny_overlap"} else 0.3

        if "london_ny_session" in name_to_strategy:
            weights["london_ny_session"] = 0.9 if session == "london_ny_overlap" else 0.1

        if "adaptive_weighting" in name_to_strategy:
            weights["adaptive_weighting"] = 0.6

        active = [name for name, weight in weights.items() if weight >= 0.25]
        if not active:
            active = [s.name for s in candidates]
            weights = {s.name: 1.0 for s in candidates}

        return RegimeDecision(active_strategy_names=active, weights=weights)
