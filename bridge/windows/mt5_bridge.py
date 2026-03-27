import json
import os
import time
import requests
from datetime import datetime, timezone

try:
    import MetaTrader5 as mt5
except Exception as e:
    raise SystemExit(f"MetaTrader5 package required on Windows: {e}")

API_BASE = os.getenv("BRIDGE_API_BASE", "")
BRIDGE_TOKEN = os.getenv("BRIDGE_TOKEN", "")
POLL_SEC = int(os.getenv("BRIDGE_POLL_SEC", "2"))
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
MT5_PATH = os.getenv("MT5_PATH", "")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def headers():
    return {"Authorization": f"Bearer {BRIDGE_TOKEN}", "Content-Type": "application/json"}


def connect_mt5():
    # Some Windows setups fail when path is empty/invalid. Try without path first.
    if MT5_PATH:
        ok = mt5.initialize(path=MT5_PATH, login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
    else:
        ok = mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
    if not ok:
        raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")


def get_snapshot():
    acc = mt5.account_info()
    positions = mt5.positions_get() or []
    return {
        "ts": now_iso(),
        "connected": acc is not None,
        "balance": float(getattr(acc, "balance", 0.0)) if acc else 0.0,
        "equity": float(getattr(acc, "equity", 0.0)) if acc else 0.0,
        "positions": [
            {
                "ticket": int(p.ticket),
                "symbol": p.symbol,
                "type": int(p.type),
                "volume": float(p.volume),
                "price_open": float(p.price_open),
                "profit": float(p.profit),
            }
            for p in positions
        ],
    }


def close_all():
    # conservative placeholder: only reports tickets. execution logic can be expanded safely.
    positions = mt5.positions_get() or []
    return {"closed": 0, "tickets": [int(p.ticket) for p in positions], "note": "close_all execution stub"}


def main():
    if not API_BASE or not BRIDGE_TOKEN:
        raise SystemExit("Set BRIDGE_API_BASE and BRIDGE_TOKEN")
    connect_mt5()
    print("MT5 Bridge started")
    while True:
        try:
            snap = get_snapshot()
            requests.post(f"{API_BASE}/bridge/snapshot", headers=headers(), data=json.dumps(snap), timeout=8)
            cmd = requests.get(f"{API_BASE}/bridge/command", headers=headers(), timeout=8)
            if cmd.ok:
                data = cmd.json()
                if data.get("command") == "close_all":
                    result = close_all()
                    requests.post(f"{API_BASE}/bridge/result", headers=headers(), data=json.dumps(result), timeout=8)
        except Exception as e:
            try:
                requests.post(f"{API_BASE}/bridge/error", headers=headers(), data=json.dumps({"error": str(e), "ts": now_iso()}), timeout=8)
            except Exception:
                pass
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
