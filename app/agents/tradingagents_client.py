import logging
import requests
from tenacity import retry, stop_after_attempt, wait_fixed

from app.core.settings import settings
from app.decision.schemas import TradingCommitteeReport

log = logging.getLogger("tradingagents_client")


@retry(stop=stop_after_attempt(2), wait=wait_fixed(1), reraise=True)
def _post(url: str, payload: dict, timeout: int):
    return requests.post(url, json=payload, timeout=timeout)


def analyze_with_tradingagents(symbol: str, market_context: dict) -> TradingCommitteeReport | None:
    if not settings.trading_agents_enabled:
        return None
    try:
        r = _post(
            f"{settings.trading_agents_base_url.rstrip('/')}/committee",
            {"symbol": symbol, "market_context": market_context},
            int(settings.trading_agents_timeout_seconds),
        )
        if not r.ok:
            log.warning("tradingagents non-200: %s", r.status_code)
            return None
        data = r.json()
        if "raw_payload" not in data:
            data["raw_payload"] = data.copy()
        return TradingCommitteeReport(**data)
    except Exception as e:
        log.warning("tradingagents call failed: %s", e)
        return None
