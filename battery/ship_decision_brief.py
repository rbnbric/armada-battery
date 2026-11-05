"""Evidence-bound human decisions and plain-language fallbacks.

SHIP_MANIFEST:
META:
  name: decision_brief
  author: robin
  kind: type
  capabilities: [ANALYZE]
  domains: [armada-battery]
  description: Structured decision briefs, explanation contracts and human responses
"""
import hashlib
import json
from datetime import datetime, timezone
from .ledger import sanitize


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_brief(case, context, current, read_error="", successor=""):
    result = case.get("result") or {}
    active = case.get("state") in {"QUEUED", "RUNNING", "ADMISSION_UNCERTAIN"}
    original = sanitize(context["target_snapshot"])
    changed = not read_error and fingerprint(current) != fingerprint(original)
    kind = result.get("reason_code") or "REVIEW_REQUIRED"
    state = case.get("state")
    if active:
        kind = "IN_PROGRESS"
    elif successor:
        kind = "SUPERSEDED"
    elif read_error:
        kind = "EVIDENCE_NEEDED"
    elif changed:
        kind = "CONTEXT_DECISION"
    elif state == "VERIFIED_MATCH":
        kind = "COMPLETE"
    elif state == "VERIFIED_MISMATCH":
        kind = "CONTEXT_DECISION"
    elif state == "RECOVERY_REQUIRED":
        kind = "TECHNICAL_RECOVERY"
    elif state == "HELD_FOR_EVIDENCE":
        kind = "EVIDENCE_NEEDED"
    question, summary, next_step = {
        "IN_PROGRESS": ("The review is still in progress", "Battery has not finished reviewing this receipt.", "Refresh cases to check progress."),
        "SUPERSEDED": ("A newer review exists", "This is an earlier review. Its evidence remains available.", "Open the newer review before deciding."),
        "COMPLETE": ("This review is complete", "The saved evidence passed this review’s checks. The settings we can read now match those saved with the request.", "You do not need to repeat the operation because of this review."),
        "CONTEXT_DECISION": ("Which outcome is intended now?", "The evidence does not settle what you want to happen next.", "Check the difference and record the intended outcome, or request more evidence."),
        "TECHNICAL_RECOVERY": ("The review needs technical recovery", "The review could not complete reliably. This does not establish that the operation failed.", "Review the failure details, then explicitly start a fresh review if appropriate."),
        "EVIDENCE_NEEDED": ("More evidence is needed", "The available evidence cannot establish the outcome.", "Request a fresh evidence review or record what information is missing."),
        "REVIEW_REQUIRED": ("The reason for this hold needs clarification", "This older record does not identify a specific human decision.", "Inspect the recorded reason or request a fresh review."),
    }.get(kind, ("Review needs clarification", "The outcome remains unresolved.", "Inspect the evidence before deciding."))
    if changed and not active and not successor:
        question = "Was the later configuration intentional?"
        summary = "The settings are different from those saved with this request. We do not yet know who changed them or why."
    facts = [
        {"id": "review", "label": "Recorded review", "value": {"state": state, "assertion": result.get("assertion", "UNKNOWN"), "output": result.get("output", "UNKNOWN"), "reason": result.get("explanation", case.get("recovery_reason", ""))}, "observed_at": case.get("updated_at", "Unknown")},
        {"id": "scope", "label": "Source and target", "value": {"scope": context["source_scope"], "target": context["target"], "receipt": context["receipt_id"]}},
        {"id": "configuration", "label": "Current configuration comparison", "value": {"changed": changed if not read_error else None, "read_error": read_error, "retained_digest": fingerprint(original), "current_digest": fingerprint(current) if not read_error else None}},
    ]
    differences = []
    if changed:
        for key in sorted(set(original) | set(current)):
            if original.get(key) != current.get(key) or (key in original) != (key in current):
                differences.append({"field": key, "retained": original.get(key, "[absent]"), "current": current.get(key, "[absent]")})
    options = []
    if kind == "CONTEXT_DECISION":
        options += [
            {"id": "keep_current", "label": "The current configuration is intended", "consequence": "Records your intent. It does not change the earlier measurement or apply a configuration."},
            {"id": "restore_intent", "label": "The earlier outcome is still required", "consequence": "Records the need for a corrective request. Prepare and authorize that request separately against current evidence."},
        ]
    if kind not in {"COMPLETE", "IN_PROGRESS", "SUPERSEDED"}:
        options += [
            {"id": "request_evidence", "label": "Request a fresh evidence review", "consequence": "Creates one new review revision using the current adapter. It can use model calls; it does not repeat the business operation."},
            {"id": "defer", "label": "Wait for more context", "consequence": "Records what is missing and who you need to ask. No review or operation is started."},
        ]
    revision = fingerprint({"brief_schema": 1, "id": case["id"], "state": state, "result": result, "recovery": case.get("recovery_reason"), "facts": facts, "successor": successor})
    return {"revision": revision, "case_id": case["id"], "kind": kind, "question": question, "summary": summary, "next_step": next_step,
            "owner": context["operator"], "scope": context["source_scope"], "facts": facts, "differences": differences[:20],
            "differences_omitted": max(0, len(differences)-20), "choices": options, "successor": successor,
            "read_at": datetime.now(timezone.utc).isoformat(),
            "unknowns": ["Matching settings alone do not prove that the service works in use."] + (["The author, authorization and purpose of the later change are not established by this comparison."] if changed else []),
            "history_note": "No comparison with similar cases has been performed."}


def explanation_input(brief):
    # Bounded selection is explicit. Raw model transcripts and unrelated cases are excluded.
    packet = {k: brief[k] for k in ("case_id", "revision", "kind", "question", "summary", "next_step", "scope", "facts", "unknowns")}
    packet["coverage"] = "Selected review result, source scope and configuration comparison only. Full transcripts and historical analogies are not included."
    return sanitize(packet)


def validate_explanation(value, brief):
    if not isinstance(value, dict) or set(value) != {"summary", "meaning", "missing", "evidence_ids"}:
        raise ValueError("Explainer returned an invalid response structure")
    for key in ("summary", "meaning", "missing"):
        if not isinstance(value[key], str) or not value[key].strip() or len(value[key]) > 700:
            raise ValueError("Explainer returned an invalid text field")
    ids = value["evidence_ids"]
    allowed = {f["id"] for f in brief["facts"]}
    if not isinstance(ids, list) or not ids or any(not isinstance(x, str) for x in ids) or len(set(ids)) != len(ids) or not set(ids) <= allowed:
        raise ValueError("Explainer cited unsupported evidence")
    # Contract validity is not semantic proof: prose stays attributed as model interpretation.
    return value
