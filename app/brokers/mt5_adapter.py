from tenacity import retry, stop_after_attempt, wait_fixed

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None


class MT5Adapter:
    def __init__(self, login: int | None, password: str, server: str, path: str = "", mode: str = "paper"):
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self.mode = mode
        self.connected = False

    @property
    def is_paper(self) -> bool:
        return self.mode != "live"

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def connect(self):
        if self.is_paper:
            self.connected = True
            return True
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package not available")
        ok = mt5.initialize(path=self.path or None, login=self.login, password=self.password, server=self.server)
        if not ok:
            raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")
        self.connected = True
        return True

    def set_mode(self, mode: str):
        self.mode = mode

    def account_info(self):
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
        return {
            "balance": float(info.get("balance", 0.0)),
            "equity": float(info.get("equity", info.get("balance", 0.0))),
            "currency": info.get("currency", "USD"),
            "mode": "paper" if self.is_paper else "live",
        }

    def get_positions(self) -> list[dict]:
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
        return {
            "open_pnl": open_pnl,
            "positions": len(positions),
            "mode": "paper" if self.is_paper else "live",
        }

    def close_all_positions(self) -> dict:
        if self.is_paper:
            return {"closed": 0, "mode": "paper", "note": "no-op in paper mode"}

        # Safety scaffold only: intentionally no forced autonomous close execution.
        positions = self.get_positions()
        return {
            "closed": 0,
            "mode": "live",
            "requested": len(positions),
            "note": "stub: implement broker-specific close flow with explicit risk approvals",
        }

    def shutdown(self):
        if mt5 and not self.is_paper:
            mt5.shutdown()
        self.connected = False
