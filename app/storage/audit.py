from pathlib import Path
from datetime import datetime, timezone
import orjson


class AuditStore:
    def __init__(self, path: str = "logs/audit.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, payload: dict):
        line = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "payload": payload,
        }
        with self.path.open("ab") as f:
            f.write(orjson.dumps(line) + b"\n")
