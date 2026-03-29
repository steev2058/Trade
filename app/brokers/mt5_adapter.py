from tenacity import retry, stop_after_attempt, wait_fixed
import requests
import time
import uuid

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None


class MT5Adapter:
    def __init__(
        self,
        login: int | None,
        password: str,
        server: str,
        path: str = "",
        mode: str = "paper",
        bridge_api_base: str = "",
        bridge_token: str = "",
    ):
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self.mode = mode
        self.connected = False
        self.bridge_api_base = (bridge_api_base or "").rstrip("/")
        self.bridge_token = bridge_token or ""

    @property
    def is_paper(self) -> bool:
        return self.mode != "live"

    def set_mode(self, mode: str):
        self.mode = mode

    def _bridge_headers(self):
        return {"Authorization": f"Bearer {self.bridge_token}"}

    def _bridge_enabled(self) -> bool:
        return bool(self.bridge_api_base and self.bridge_token)

    def _bridge_state(self) -> dict | None:
        if not self._bridge_enabled():
            return None
        try:
            r = requests.get(f"{self.bridge_api_base}/bridge/state", headers=self._bridge_headers(), timeout=5)
            if r.ok:
                return r.json()
        except Exception:
            return None
        return None

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def connect(self):
        if self.is_paper:
            self.connected = True
            return True
        if mt5 is None:
            # live mode may still be served via windows bridge
            if self._bridge_enabled():
                self.connected = True
                return True
            raise RuntimeError("MetaTrader5 package not available")
        ok = mt5.initialize(path=self.path or None, login=self.login, password=self.password, server=self.server)
        if not ok:
            raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")
        self.connected = True
        return True

    def account_info(self):
        st = self._bridge_state()
        if st and st.get("snapshot"):
            snap = st["snapshot"]
            return {
                "balance": float(snap.get("balance", 0.0)),
                "equity": float(snap.get("equity", snap.get("balance", 0.0))),
                "profit": 0.0,
                "currency": "USD",
                "mode": "bridge",
            }

        if self.is_paper:
            return {
                "balance": 10000.0,
                "equity": 10000.0,
                "profit": 0.0,
                "currency": "USD",
                "mode": "paper",
            }
        if mt5 is None:
            return {}
        info = mt5.account_info()
        if info is None:
            return {}
        return info._asdict()

    def get_balance(self) -> dict:
        info = self.account_info()
        mode = info.get("mode", "paper" if self.is_paper else "live")
        return {
            "balance": float(info.get("balance", 0.0)),
            "equity": float(info.get("equity", info.get("balance", 0.0))),
            "currency": info.get("currency", "USD"),
            "mode": mode,
        }

    def get_ticks(self) -> dict:
        st = self._bridge_state()
        if st and st.get("snapshot"):
            return st["snapshot"].get("ticks", {}) or {}
        return {}

    def get_symbol_specs(self, symbol: str) -> dict:
        ticks = self.get_ticks() or {}
        t = ticks.get(symbol, {})
        return {
            "bid": float(t.get("bid", 0.0) or 0.0),
            "ask": float(t.get("ask", 0.0) or 0.0),
            "point_size": float(t.get("point_size", 0.0) or 0.0),
            "point_value": float(t.get("point_value", 0.0) or 0.0),
        }

    def get_positions(self) -> list[dict]:
        st = self._bridge_state()
        if st and st.get("snapshot"):
            return st["snapshot"].get("positions", []) or []

        if self.is_paper:
            return []
        if mt5 is None:
            return []
        positions = mt5.positions_get() or []
        out = []
        for p in positions:
            d = p._asdict()
            out.append(
                {
                    "ticket": d.get("ticket"),
                    "symbol": d.get("symbol"),
                    "type": "buy" if d.get("type") == 0 else "sell",
                    "volume": d.get("volume"),
                    "price_open": d.get("price_open"),
                    "profit": d.get("profit", 0.0),
                }
            )
        return out

    def get_pnl(self) -> dict:
        positions = self.get_positions()
        open_pnl = sum(float(p.get("profit", 0.0)) for p in positions)
        mode = "paper" if self.is_paper else "live"
        if self._bridge_enabled():
            mode = "bridge"
        return {
            "open_pnl": open_pnl,
            "positions": len(positions),
            "mode": mode,
        }

    def _bridge_send(self, endpoint: str, payload: dict | None = None) -> dict:
        try:
            cmd_id = uuid.uuid4().hex
            body = dict(payload or {})
            body["cmd_id"] = cmd_id
            r = requests.post(
                f"{self.bridge_api_base}{endpoint}",
                headers=self._bridge_headers(),
                json=body,
                timeout=5,
            )
            if not r.ok:
                return {"ok": False, "note": f"bridge command failed: {r.status_code}"}

            # wait briefly for matching result
            for _ in range(10):
                st = self._bridge_state() or {}
                res = st.get("last_result")
                if isinstance(res, dict) and res.get("cmd_id") == cmd_id:
                    out = {"mode": "bridge"}
                    out.update(res)
                    return out
                time.sleep(0.3)

            return {"ok": True, "mode": "bridge", "note": "command sent", "cmd_id": cmd_id}
        except Exception as e:
            return {"ok": False, "mode": "bridge", "note": f"bridge error: {e}"}

    def open_order(self, symbol: str, side: str, lot: float) -> dict:
        if self._bridge_enabled():
            return self._bridge_send('/bridge/command/open', {"symbol": symbol, "side": side, "lot": lot})
        return {"ok": False, "note": "bridge not enabled"}

    def close_ticket(self, ticket: int) -> dict:
        if self._bridge_enabled():
            return self._bridge_send('/bridge/command/close', {"ticket": int(ticket)})
        return {"ok": False, "note": "bridge not enabled"}

    def set_sl_tp(self, ticket: int, sl: float, tp: float) -> dict:
        if self._bridge_enabled():
            return self._bridge_send('/bridge/command/sl_tp', {"ticket": int(ticket), "sl": float(sl), "tp": float(tp)})
        return {"ok": False, "note": "bridge not enabled"}

    def set_sl_tp_by_points(self, ticket: int, symbol: str, side: str, sl_points: float, tp_points: float) -> dict:
        specs = self.get_symbol_specs(symbol)
        point = float(specs.get("point_size", 0.0) or 0.0)
        bid = float(specs.get("bid", 0.0) or 0.0)
        ask = float(specs.get("ask", 0.0) or 0.0)
        if point <= 0 or (bid <= 0 and ask <= 0):
            return {"ok": False, "note": "missing market specs for sl/tp", "symbol": symbol}

        is_buy = str(side).lower() == "buy"
        entry = ask if is_buy else bid
        sl = entry - (sl_points * point) if is_buy else entry + (sl_points * point)
        tp = entry + (tp_points * point) if is_buy else entry - (tp_points * point)
        return self.set_sl_tp(int(ticket), float(sl), float(tp))

    def close_all_positions(self) -> dict:
        if self._bridge_enabled():
            return self._bridge_send('/bridge/command/close_all')

        if self.is_paper:
            return {"closed": 0, "mode": "paper", "note": "no-op in paper mode"}

        positions = self.get_positions()
        return {
            "closed": 0,
            "mode": "live",
            "requested": len(positions),
            "note": "stub: implement broker-specific close flow",
        }

    def shutdown(self):
        if mt5 and not self.is_paper:
            mt5.shutdown()
        self.connected = False
