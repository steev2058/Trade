import logging
import requests
from tenacity import retry, stop_after_attempt, wait_fixed

from app.core.settings import settings
from app.decision.schemas import DexterResearchReport

log = logging.getLogger("dexter_client")


@retry(stop=stop_after_attempt(2), wait=wait_fixed(1), reraise=True)
def _post(url: str, payload: dict, timeout: int):
    return requests.post(url, json=payload, timeout=timeout)


def analyze_with_dexter(symbol: str, market_context: dict) -> DexterResearchReport | None:
    if not settings.dexter_enabled:
        return None
    try:
        r = _post(
            f"{settings.dexter_base_url.rstrip('/')}/analyze",
            {"symbol": symbol, "market_context": market_context},
            int(settings.dexter_timeout_seconds),
        )
        if not r.ok:
            log.warning("dexter non-200: %s", r.status_code)
            return None
        data = r.json()
        if "raw_payload" not in data:
            data["raw_payload"] = data.copy()
        return DexterResearchReport(**data)
    except Exception as e:
        log.warning("dexter call failed: %s", e)
        return None
