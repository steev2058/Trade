from tenacity import retry, stop_after_attempt, wait_fixed

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None


class MT5Adapter:
    def __init__(self, login: int | None, password: str, server: str, path: str = ""):
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self.connected = False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def connect(self):
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package not available")
        ok = mt5.initialize(path=self.path or None, login=self.login, password=self.password, server=self.server)
        if not ok:
            raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")
        self.connected = True
        return True

    def account_info(self):
        if mt5 is None:
            return {}
        info = mt5.account_info()
        if info is None:
            return {}
        return info._asdict()

    def shutdown(self):
        if mt5:
            mt5.shutdown()
        self.connected = False
