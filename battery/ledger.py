"""Small append-only evidence ledger with deterministic hash chaining."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Ledger:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.records: list[dict[str, Any]] = []
        if path and path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self.records.append(json.loads(line))

    def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        previous = self.records[-1]["digest"] if self.records else "0" * 64
        base = {
            "sequence": len(self.records) + 1,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "payload": payload,
            "previous_digest": previous,
        }
        encoded = json.dumps(base, sort_keys=True, separators=(",", ":"))
        record = {**base, "digest": hashlib.sha256(encoded.encode()).hexdigest()}
        self.records.append(record)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
                handle.flush()
        return record

    def verify(self) -> bool:
        previous = "0" * 64
        for position, record in enumerate(self.records, 1):
            base = {key: record[key] for key in (
                "sequence", "recorded_at", "event_type", "payload", "previous_digest"
            )}
            encoded = json.dumps(base, sort_keys=True, separators=(",", ":"))
            expected = hashlib.sha256(encoded.encode()).hexdigest()
            if record["sequence"] != position or record["previous_digest"] != previous:
                return False
            if record["digest"] != expected:
                return False
            previous = record["digest"]
        return True
