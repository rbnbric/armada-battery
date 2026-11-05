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
from .ship_decision_brief import build_brief, explanation_input, validate_explanation

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

    def request(self, path, body=None, timeout=6):
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
            with urllib.request.urlopen(request, timeout=timeout) as response:
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
        read_error, current = "", {}
        try:
            current = sanitize(self.target(context["target"]))
        except (AdapterError, ValueError, KeyError) as exc:
            read_error = "Current target could not be read; inspect the adapter connection and access."
            import logging
            logging.getLogger(__name__).error("Decision target read failed for %s: %s", case_id, type(exc).__name__)
        contexts = self._contexts()
        successor = next((k for k, v in reversed(list(contexts.items())) if v.get("parent_id") == case_id and v["operator"] == operator), "")
        result["brief"] = build_brief(result, context, current, read_error, successor)
        with self.engine.ledger.locked():
            history = [r["payload"] for r in self.engine.ledger.records if r["event_type"] == "native_human_decision" and r["payload"].get("case_id") == case_id and r["payload"].get("operator") == operator]
            result["decisions"] = history[-10:]
            result["decisions_omitted"] = max(0, len(history)-10)
            for record in reversed(self.engine.ledger.records):
                value = record["payload"]
                if record["event_type"] == "native_explanation_finished" and value.get("case_id") == case_id and value.get("revision") == result["brief"]["revision"] and value.get("operator") == operator:
                    result["explanation"] = value
                    break
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

    def decide(self, case_id, operator, revision, choice, reason):
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
            raise ValueError("Explain your choice in 1–2000 characters")
        # Serialize duplicate answers and review admission. All facts are re-read before acceptance.
        with self.engine.ledger.locked():
            case = self.get(case_id, operator)
            brief = case["brief"]
            payload = {"case_id": case_id, "operator": operator, "revision": revision, "choice": choice, "reason": sanitize(reason.strip())}
            decision_id = digest(payload)
            for row in self.engine.ledger.records:
                if row["event_type"] == "native_human_decision" and row["payload"].get("decision_id") == decision_id:
                    return row["payload"]
            if revision != brief["revision"]:
                raise ValueError("Evidence changed. Refresh the decision brief before answering.")
            if choice not in {x["id"] for x in brief["choices"]}:
                raise ValueError("This choice is not available for the current evidence")
            payload.update(decision_id=decision_id, recorded_at=datetime.now(timezone.utc).isoformat(), next_step=next(x["consequence"] for x in brief["choices"] if x["id"] == choice))
            if choice == "request_evidence":
                # Persist the decision before dispatch; retry uses the same stable review key.
                child_key = "decision-" + decision_id
                payload["review_key"] = child_key
            self.engine.ledger.append("native_human_decision", payload)
        return payload

    def follow_decision(self, decision, operator):
        if decision["choice"] == "request_evidence":
            context = self._contexts()[decision["case_id"]]
            child = self.submit(context["receipt_id"], decision["review_key"], operator, decision["case_id"])
            return {**decision, "child_id": child["id"]}
        return decision

    def explain(self, case_id, operator, revision, retry=False):
        case = self.get(case_id, operator)
        brief = case["brief"]
        if brief["revision"] != revision:
            raise ValueError("Evidence changed. Refresh before requesting an explanation.")
        if brief["kind"] in {"IN_PROGRESS", "SUPERSEDED"}:
            raise ValueError("Wait for the current review to finish before requesting an explanation")
        with self.engine.ledger.locked():
            attempt = 1
            for row in reversed(self.engine.ledger.records):
                p = row["payload"]
                if p.get("case_id") == case_id and p.get("revision") == revision and p.get("operator") == operator:
                    if row["event_type"] == "native_explanation_finished":
                        prior_attempt = p.get("attempt", 1)
                        if p.get("status") == "ready" or not retry or prior_attempt >= 2:
                            return p
                        attempt = prior_attempt + 1
                        break
                    if row["event_type"] == "native_explanation_started":
                        return {"status": "unconfirmed", "detail": "An explanation was requested. Its result is not confirmed; refresh later. The evidence brief remains available."}
            self.engine.ledger.append("native_explanation_started", {"case_id": case_id, "operator": operator, "revision": revision, "attempt": attempt})
        output = {"case_id": case_id, "operator": operator, "revision": revision, "attempt": attempt}
        try:
            response = self.request("/cases/" + quote(case_id, safe="") + "/explain", {"revision": revision, "attempt": attempt, "brief": explanation_input(brief)}, timeout=100)
            output.update(status="ready", content=validate_explanation(json.loads(response["content"]), brief), usage=response.get("usage"), response_id=response.get("response_id"))
        except (AdapterError, ValueError, KeyError, TypeError) as exc:
            import logging
            logging.getLogger(__name__).error("Explanation unavailable for %s: %s", case_id, type(exc).__name__)
            output.update(status="unavailable", detail="The AI explanation was unavailable or failed its response contract. The evidence brief remains available.")
        self.engine.ledger.append("native_explanation_finished", output)
        # The result is retained for audit, but never presented as current after an intervening change.
        if self.get(case_id, operator)["brief"]["revision"] != revision:
            raise ValueError("Evidence changed while the explanation was being prepared. Refresh the brief.")
        return output
