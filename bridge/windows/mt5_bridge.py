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
    if MT5_LOGIN <= 0 or not MT5_PASSWORD or not MT5_SERVER:
        raise RuntimeError('Missing MT5_LOGIN / MT5_PASSWORD / MT5_SERVER in .env')

    # Some Windows setups fail when path is empty/invalid. Use path only if file exists.
    if MT5_PATH and os.path.exists(MT5_PATH):
        ok = mt5.initialize(path=MT5_PATH, login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
    else:
        ok = mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)

    if not ok:
        raise RuntimeError(f"MT5 init failed: {mt5.last_error()} | login={MT5_LOGIN} server={MT5_SERVER} path={MT5_PATH or 'AUTO'}")


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
    positions = mt5.positions_get() or []
    closed = 0
    failed = []

    for p in positions:
      try:
        symbol = p.symbol
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            failed.append({"ticket": int(p.ticket), "error": "no_tick"})
            continue

        # POSITION_TYPE_BUY=0, POSITION_TYPE_SELL=1
        is_buy = int(p.type) == 0
        order_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
        price = tick.bid if is_buy else tick.ask

        fill_candidates = [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN]
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is not None and hasattr(symbol_info, 'filling_mode'):
            fm = int(symbol_info.filling_mode)
            if fm in fill_candidates:
                fill_candidates = [fm] + [x for x in fill_candidates if x != fm]

        sent_ok = False
        last_ret = None
        for fill_mode in fill_candidates:
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(p.volume),
                "type": order_type,
                "position": int(p.ticket),
                "price": float(price),
                "deviation": 20,
                "magic": 987654,
                "comment": "bridge_close_all",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": fill_mode,
            }
            res = mt5.order_send(req)
            last_ret = res
            if res is not None and int(getattr(res, 'retcode', -1)) == int(mt5.TRADE_RETCODE_DONE):
                closed += 1
                sent_ok = True
                break

        if not sent_ok:
            failed.append({
                "ticket": int(p.ticket),
                "retcode": int(getattr(last_ret, 'retcode', -1)) if last_ret is not None else -1,
                "comment": str(getattr(last_ret, 'comment', 'order_send_failed')) if last_ret is not None else 'order_send_failed'
            })
      except Exception as e:
        failed.append({"ticket": int(getattr(p, 'ticket', 0)), "error": str(e)})

    return {
        "closed": closed,
        "requested": len(positions),
        "failed": failed,
        "mode": "bridge"
    }


def open_order(symbol: str, side: str, lot: float):
    symbol = str(symbol or '').strip()
    if not symbol:
        return {"ok": False, "error": "missing_symbol"}

    # ensure symbol is visible in Market Watch
    mt5.symbol_select(symbol, True)
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"ok": False, "error": "no_tick", "symbol": symbol}

    side = str(side or '').lower().strip()
    if side not in ('buy', 'sell'):
        return {"ok": False, "error": "invalid_side"}

    order_type = mt5.ORDER_TYPE_BUY if side == 'buy' else mt5.ORDER_TYPE_SELL
    price = tick.ask if side == 'buy' else tick.bid

    fill_candidates = [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN]
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is not None and hasattr(symbol_info, 'filling_mode'):
        fm = int(symbol_info.filling_mode)
        if fm in fill_candidates:
            fill_candidates = [fm] + [x for x in fill_candidates if x != fm]

    last_ret = None
    for fill_mode in fill_candidates:
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot),
            "type": order_type,
            "price": float(price),
            "deviation": 20,
            "magic": 987654,
            "comment": "bridge_open",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": fill_mode,
        }
        res = mt5.order_send(req)
        last_ret = res
        if res is not None and int(getattr(res, 'retcode', -1)) == int(mt5.TRADE_RETCODE_DONE):
            return {
                "ok": True,
                "retcode": int(getattr(res, 'retcode', -1)),
                "comment": str(getattr(res, 'comment', 'done')),
                "symbol": symbol,
                "side": side,
                "lot": float(lot),
                "order": int(getattr(res, 'order', 0) or 0),
                "deal": int(getattr(res, 'deal', 0) or 0),
            }

    return {
        "ok": False,
        "retcode": int(getattr(last_ret, 'retcode', -1)) if last_ret is not None else -1,
        "comment": str(getattr(last_ret, 'comment', 'order_send_failed')) if last_ret is not None else 'order_send_failed',
        "symbol": symbol,
        "side": side,
        "lot": float(lot),
    }


def close_ticket(ticket: int):
    positions = mt5.positions_get(ticket=int(ticket)) or []
    if not positions:
        return {"ok": False, "error": "ticket_not_found", "ticket": int(ticket)}
    p = positions[0]
    symbol = p.symbol
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"ok": False, "error": "no_tick", "ticket": int(ticket)}
    is_buy = int(p.type) == 0
    order_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
    price = tick.bid if is_buy else tick.ask
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(p.volume),
        "type": order_type,
        "position": int(p.ticket),
        "price": float(price),
        "deviation": 20,
        "magic": 987654,
        "comment": "bridge_close_ticket",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(req)
    return {
        "ok": bool(res is not None and int(getattr(res, 'retcode', -1)) == int(mt5.TRADE_RETCODE_DONE)),
        "retcode": int(getattr(res, 'retcode', -1)) if res is not None else -1,
        "comment": str(getattr(res, 'comment', 'order_send_failed')) if res is not None else 'order_send_failed',
        "ticket": int(ticket),
    }


def modify_sl_tp(ticket: int, sl: float, tp: float):
    positions = mt5.positions_get(ticket=int(ticket)) or []
    if not positions:
        return {"ok": False, "error": "ticket_not_found", "ticket": int(ticket)}
    p = positions[0]
    req = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": p.symbol,
        "position": int(ticket),
        "sl": float(sl),
        "tp": float(tp),
        "magic": 987654,
        "comment": "bridge_sl_tp",
    }
    res = mt5.order_send(req)
    return {
        "ok": bool(res is not None and int(getattr(res, 'retcode', -1)) == int(mt5.TRADE_RETCODE_DONE)),
        "retcode": int(getattr(res, 'retcode', -1)) if res is not None else -1,
        "comment": str(getattr(res, 'comment', 'order_send_failed')) if res is not None else 'order_send_failed',
        "ticket": int(ticket),
    }


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
                c = data.get("command")
                result = None
                if c == "close_all":
                    result = close_all()
                elif c == "open":
                    result = open_order(str(data.get('symbol','')), str(data.get('side','')), float(data.get('lot', 0.01)))
                elif c == "close":
                    result = close_ticket(int(data.get('ticket', 0)))
                elif c == "sl_tp":
                    result = modify_sl_tp(int(data.get('ticket', 0)), float(data.get('sl', 0)), float(data.get('tp', 0)))
                if result is not None:
                    requests.post(f"{API_BASE}/bridge/result", headers=headers(), data=json.dumps(result), timeout=8)
        except Exception as e:
            try:
                requests.post(f"{API_BASE}/bridge/error", headers=headers(), data=json.dumps({"error": str(e), "ts": now_iso()}), timeout=8)
            except Exception:
                pass
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
