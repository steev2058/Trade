import logging
import requests

from app.core.settings import settings

log = logging.getLogger("external_health")


def _check(base: str, timeout: int) -> bool:
    try:
        r = requests.get(f"{base.rstrip('/')}/health", timeout=timeout)
        return bool(r.ok)
    except Exception as e:
        log.warning("health check failed for %s: %s", base, e)
        return False


def check_dexter_health() -> bool:
    if not settings.dexter_enabled:
        return True
    return _check(settings.dexter_base_url, int(settings.dexter_timeout_seconds))


def check_tradingagents_health() -> bool:
    if not settings.trading_agents_enabled:
        return True
    return _check(settings.trading_agents_base_url, int(settings.trading_agents_timeout_seconds))
