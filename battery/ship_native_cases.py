"""Join operator receipts to native AI Hub reviews without trusting browser evidence.

The ledger supplies receipt identity; the configured management adapter supplies
current target state. Neither agent nor browser can choose a callback URL.

SHIP_MANIFEST:
META:
  name: native_cases
  author: robin
  kind: type
  capabilities: [ANALYZE]
  domains: [armada-battery]
  description: Durable receipt-to-native-case bridge and scoped evidence tools
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlsplit, quote

from .ledger import sanitize
from .errors import AdapterError

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class NativeCases:
    def __init__(self, engine, url=None, username=None, password=None, operator=None):
        self.operator = operator
        self.engine = engine
        self.url = (url if url is not None else os.getenv("BATTERY_NATIVE_URL", "")).rstrip("/")
        self.username = username if username is not None else os.getenv("BATTERY_NATIVE_USER", "")
        self.password = password if password is not None else os.getenv("BATTERY_NATIVE_PASSWORD", "")
        if self.url:
            parsed = urlsplit(self.url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
                raise ValueError("Invalid configured native API URL")
            if not self.username or not self.password:
                raise ValueError("Native API credentials are required")

    def request(self, path, body=None):
        if not self.url:
            raise AdapterError("Native AI Hub is not connected to this installation")
        headers = {"Accept": "application/json", "Authorization": "Basic " + base64.b64encode(f"{self.username}:{self.password}".encode()).decode()}
        if self.operator:
            headers["X-Battery-Operator"] = self.operator
        data = None if body is None else json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.url + path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=6) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise AdapterError("Native response exceeds the response budget")
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise AdapterError("Native active or daily review budget exhausted; try later with the same request key" if exc.code == 429 else f"Native API returned HTTP {exc.code}; the request was not confirmed", http_status=exc.code if exc.code in {403, 404, 409, 429, 503} else 502) from exc
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            # Do not print credential-bearing request objects or retry POST.
            raise AdapterError("Native request did not establish an outcome; refresh the same case ID") from exc

    def _contexts(self):
        with self.engine.ledger.locked():
            if not self.engine.ledger.verify():
                raise ValueError("Ledger integrity failure")
            return {r["payload"]["id"]: r["payload"] for r in self.engine.ledger.records if r["event_type"] == "native_case_admitted"}

    def list(self, operator):
        if not self.url:
            return {"available": False, "items": [], "detail": "Connect the native AI Hub service to review operation receipts."}
        contexts = self._contexts()
        result = self.request("/cases")
        result["items"] = [r for r in result["items"] if contexts.get(r["id"], {}).get("operator") == operator]
        for row in result["items"]:
            row["target"] = contexts[row["id"]]["target"]
            row["source_scope"] = contexts[row["id"]]["source_scope"]
        result["available"] = True
        return result

    def get(self, case_id, operator):
        context = self._contexts().get(case_id)
        if not context or context["operator"] != operator:
            raise KeyError(case_id)
        result = self.request("/cases/" + quote(case_id, safe=""))
        result["receipt_id"] = context["receipt_id"]
        result["source_scope"] = context["source_scope"]
        result["target"] = context["target"]
        return result

    def target(self, target):
        kind, identifier = target.split(":", 1)
        if kind == "task":
            return self.engine.adapter.get_task(int(identifier))
        if kind == "web-app":
            return self.engine.adapter.get_web_app(identifier)
        if kind == "user":
            return self.engine.adapter.get_user(identifier)
        raise ValueError("Unsupported target for native evidence review")

    def submit(self, receipt_id, key, operator, parent_id=""):
        if not self.url:
            raise AdapterError("Native AI Hub is not connected")
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,120}", key):
            raise ValueError("A stable request key of 16–120 letters, digits, hyphens or underscores is required")
        case_id = "case-" + digest([operator, key])[:32]
        with self.engine.ledger.locked():
            contexts = self._contexts()
            existing = contexts.get(case_id)
            if existing:
                if existing["receipt_id"] != receipt_id or existing["parent_id"] != parent_id:
                    raise ValueError("Request key is already bound to another case")
                envelope = existing["envelope"]
            else:
                if parent_id:
                    prior = contexts.get(parent_id)
                    if not prior or prior["operator"] != operator or prior["receipt_id"] != receipt_id:
                        raise ValueError("Resume must retain its operator and receipt")
                receipt = self.engine.get_receipt(receipt_id, operator=operator)
                source_ids = set(receipt.get("after_evidence", []) + receipt.get("before_evidence", []))
                candidates = [r["payload"] for r in self.engine.ledger.records if r["event_type"] == "observation" and r["payload"].get("id") in source_ids and r["payload"].get("target") == receipt["target"] and isinstance(r["payload"].get("value"), dict)]
                if not candidates:
                    raise ValueError("Receipt has no retained target snapshot for a version-bound review")
                snapshot = candidates[-1]["value"]
                version = digest(snapshot)
                contract = {"profile": "receipt-v1", "partner": operator, "attempt": receipt_id, "target": receipt["target"], "version": version, "rule_version": version, "expected_count": 1, "expected_result": "COMPLETE", "accepted_count": 1, "accepted_result": "COMPLETE", "max_age": 300}
                case = {"id": case_id, "rule": "One correlated management receipt establishes the requested measured outcome for this target revision.", "expected": "One verified completed receipt", "acceptance": "One verified completed receipt and unchanged target revision", "observed": "Receipt lookup is pending", "facts": {"source": "Evidence comes from the installation ledger and configured management adapter; count means correlated verified receipt records, not the number of physical effects."}}
                envelope = {"case": case, "contract": contract, "initial": {"available": False}, "parent_id": parent_id}
                self.engine.ledger.append("native_case_admitted", {"id": case_id, "operator": operator, "receipt_id": receipt_id, "target": receipt["target"], "source_scope": "synthetic" if self.engine.adapter.synthetic else "iris", "parent_id": parent_id, "target_snapshot": snapshot, "envelope": envelope})
        # The admission key is persisted before the network request. A repeated
        # explicit submission reuses the identical envelope, not a fresh snapshot.
        return self.request("/cases", envelope)

    def evidence(self, case_id, phase):
        if phase not in {"CHECK_EFFECT_RECEIPT", "CHECK_TARGET_VERSION", "CHECK_FRESH_READBACK", "FINAL"}:
            raise ValueError("Unsupported native evidence tool")
        context = self._contexts().get(case_id)
        if not context:
            raise KeyError(case_id)
        contract = context["envelope"]["contract"]
        receipt = self.engine.get_receipt(context["receipt_id"], operator=context["operator"])
        if receipt["target"] != context["target"]:
            raise ValueError("Receipt target changed")
        details = {"tool": phase, "receipt_id": receipt["id"], "receipt_status": receipt["status"], "source_scope": context["source_scope"], "complete": True}
        version = contract["version"]
        if phase in {"CHECK_TARGET_VERSION", "CHECK_FRESH_READBACK", "FINAL"}:
            snapshot = sanitize(self.target(context["target"]))
            version = digest(snapshot)
            details["target_version"] = version
            details["source"] = "configured management adapter target readback"
        else:
            details["source"] = "durable operator-scoped receipt ledger"
        # Unknown transport or unverified task attribution remains UNKNOWN.
        if receipt["status"] not in {"VERIFIED_SUCCESS", "VERIFIED_FAILURE"}:
            observation = {"available": False}
        else:
            stamp = datetime.fromisoformat(receipt["finished_at"] or receipt["started_at"])
            # IRIS $HOROLOG epoch is 1840-12-31; timestamps remain source times.
            observed_at = int((stamp.astimezone(timezone.utc) - datetime(1840, 12, 31, tzinfo=timezone.utc)).total_seconds())
            observation = {"available": True, "partner": context["operator"], "attempt": receipt["id"], "target": context["target"], "version": version, "count": 1, "result": "COMPLETE" if receipt["status"] == "VERIFIED_SUCCESS" else "FAILED", "source": "management-adapter:" + context["source_scope"], "observed_at": observed_at}
        return {"contract": contract, "observation": observation, "tool": details}
