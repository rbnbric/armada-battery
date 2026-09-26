"""Fsynced event store, serialized across threads and local worker processes.

An interrupted/invalid record fails closed. A dispatched attempt is recovered as
unresolved; recovery never sends another mutation. Files must be on local disk.
"""

from __future__ import annotations
import hashlib
import json
import os
import re
import threading
import fcntl
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from functools import wraps

_SENSITIVE = re.compile(
    r"password|authorization|secret|private.?key|access.?token|refresh.?token|bearer|^token$",
    re.I,
)


def sanitize(value: Any) -> Any:
    """Remove secret-bearing fields and common inline credential representations."""
    if isinstance(value, dict):
        return {
            str(k): "[REDACTED]" if _SENSITIVE.search(str(k)) else sanitize(v)
            for k, v in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        value = re.sub(
            r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
            "[REDACTED KEY]",
            value,
            flags=re.S,
        )
        value = re.sub(
            r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9+/_.=-]+", r"\1 [REDACTED]", value
        )
        return re.sub(
            r"(?i)(password|secret|token)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", value
        )
    return value


class Ledger:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.records: list[dict[str, Any]] = []
        self._mutex = threading.RLock()
        self._depth = 0
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
        with self.locked():
            pass

    @contextmanager
    def locked(self):
        with self._mutex:
            outer = self._depth == 0
            handle = None
            try:
                if outer and self.path:
                    fd = os.open(
                        str(self.path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600
                    )
                    handle = os.fdopen(fd, "a+")
                    fcntl.flock(handle, fcntl.LOCK_EX)
                    self.records = (
                        [
                            json.loads(line)
                            for line in self.path.read_text().splitlines()
                            if line.strip()
                        ]
                        if self.path.exists()
                        else []
                    )
                self._depth += 1
                try:
                    yield self
                finally:
                    self._depth -= 1
            finally:
                if handle:
                    fcntl.flock(handle, fcntl.LOCK_UN)
                    handle.close()

    def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.locked():
            if not self.verify():
                raise ValueError("Ledger integrity failure; changes blocked")
            previous = self.records[-1]["digest"] if self.records else "0" * 64
            base = {
                "sequence": len(self.records) + 1,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "payload": sanitize(payload),
                "previous_digest": previous,
            }
            encoded = json.dumps(base, sort_keys=True, separators=(",", ":"))
            record = {**base, "digest": hashlib.sha256(encoded.encode()).hexdigest()}
            if self.path:
                fd = os.open(self.path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
                with os.fdopen(fd, "a") as handle:
                    handle.write(json.dumps(record, sort_keys=True) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                directory = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            self.records.append(record)
            return record

    def verify(self) -> bool:
        previous = "0" * 64
        for position, record in enumerate(self.records, 1):
            base = {
                key: record[key]
                for key in (
                    "sequence",
                    "recorded_at",
                    "event_type",
                    "payload",
                    "previous_digest",
                )
            }
            encoded = json.dumps(base, sort_keys=True, separators=(",", ":"))
            if record["sequence"] != position or record["previous_digest"] != previous:
                return False
            if record["digest"] != hashlib.sha256(encoded.encode()).hexdigest():
                return False
            previous = record["digest"]
        return True


def serialized(method):
    """Hold the local event-store lock across validation, dispatch and recording."""

    @wraps(method)
    def call(self, *args, **kwargs):
        with self.ledger.locked():
            if not self.ledger.verify():
                raise ValueError("Ledger integrity failure; changes blocked")
            self._restore_runtime()
            return method(self, *args, **kwargs)

    return call
