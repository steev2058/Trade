from pathlib import Path
from datetime import datetime, timezone
import csv


class TradeJournal:
    def __init__(self, path: str = "logs/trade_journal.csv"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["ts", "action", "symbol", "side", "lot", "ticket", "ok", "retcode", "comment"])

    def append(self, action: str, result: dict, symbol: str = "", side: str = "", lot: float | str = "", ticket: int | str = ""):
        with self.path.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                datetime.now(timezone.utc).isoformat(),
                action,
                symbol,
                side,
                lot,
                ticket,
                result.get("ok"),
                result.get("retcode", ""),
                result.get("comment", result.get("note", "")),
            ])
