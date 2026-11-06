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


def _short(value, limit=320):
    text = str(value if value is not None else "")
    return text if len(text) <= limit else text[:limit] + "… [truncated]"


def _bookends(rows, limit=4):
    if not isinstance(rows, list):
        return [], 0
    if len(rows) <= limit:
        return rows, 0
    return rows[:1] + rows[-(limit - 1):], len(rows) - limit


def full_case_review_input(case, receipt):
    """Build a bounded, cited case trail; never send raw model transcripts."""
    result, brief = case.get("result") or {}, case["brief"]
    reviews, reviews_omitted = _bookends(result.get("ReviewHistoryJSON"))
    probes, probes_omitted = _bookends(result.get("ProbeHistoryJSON"))
    decisions, decisions_omitted = _bookends(case.get("decisions"))
    sources = [
        {"id": "receipt", "label": "Saved operation receipt", "value": {
            "id": receipt.get("id"), "target": receipt.get("target"), "action": receipt.get("action_id"),
            "status": receipt.get("status"), "explanation": _short(receipt.get("explanation")),
            "finished_at": receipt.get("finished_at")}},
        {"id": "review", "label": "Recorded review", "value": {
            "state": case.get("state"), "assertion": result.get("assertion"), "output": result.get("output"),
            "reason": _short(result.get("explanation")), "proof": {
                key: _short((result.get("ProofJSON") or {}).get(key), 160)
                for key in ("verdict", "output", "reason")},
            "rounds": [{key: _short(row.get(key), 240) for key in ("state", "verdict", "output", "applicability", "probe", "explanation")}
                       for row in reviews if isinstance(row, dict)],
            "rounds_omitted": reviews_omitted}},
        {"id": "probes", "label": "Evidence checks", "value": {
            "proposed": result.get("proposed_probe"), "executed": result.get("executed_probe"),
            "reads": [{key: _short(row.get(key), 180) for key in ("phase", "found", "reason")}
                      for row in probes if isinstance(row, dict)], "reads_omitted": probes_omitted}},
        {"id": "configuration", "label": "Current settings comparison", "value": {
            "comparison": next((f.get("value") for f in brief["facts"] if f.get("id") == "configuration"), {}),
            "differences": [{"field": _short(d.get("field"), 80), "retained": _short(d.get("retained"), 160), "current": _short(d.get("current"), 160)}
                            for d in brief.get("differences", [])[:4]],
            "differences_omitted": brief.get("differences_omitted", 0) + max(0, len(brief.get("differences", [])) - 4)}},
    ]
    if decisions:
        sources.append({"id": "human", "label": "Recorded human decisions", "value": {
            "responses": [{"choice": d.get("choice"), "reason": _short(d.get("reason"), 300), "recorded_at": d.get("recorded_at"), "revision": d.get("revision")}
                          for d in decisions if isinstance(d, dict)],
            "responses_omitted": case.get("decisions_omitted", 0) + decisions_omitted}})
    packet = sanitize({"case_id": case["id"], "revision": brief["revision"], "scope": brief["scope"],
                       "parent_id": case.get("parent_id"), "successor_id": brief.get("successor"),
                       "question": brief["question"], "allowed_choices": [{"id": c["id"], "label": _short(c.get("label"), 100), "consequence": _short(c.get("consequence"), 180)} for c in brief.get("choices", [])], "sources": sources,
                       "coverage": "Selected first/latest review rounds, evidence checks, saved receipt, current comparison and latest human responses. Counts report omitted records. No raw model transcripts, unrelated cases, or hidden reasoning."})
    if len(json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()) > 6144:
        raise ValueError("Case exceeds the bounded AI review input budget")
    return packet


def validate_full_case_review(value, packet):
    required = {"what_happened", "where_judgment_changed", "human_path", "unresolved", "human_choice_assessment", "human_reason_assessment", "evidence_ids"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("Full case review returned an invalid response structure")
    for key in required - {"evidence_ids", "human_choice_assessment", "human_reason_assessment"}:
        if not isinstance(value[key], str) or not value[key].strip() or len(value[key]) > 320:
            raise ValueError("Full case review returned an invalid text field")
    for key in ("human_choice_assessment", "human_reason_assessment"):
        if not isinstance(value[key], str) or value[key] not in {"SUPPORTED", "UNSUPPORTED", "CONTRADICTED", "UNCERTAIN", "NO_DECISION"}:
            raise ValueError("Full case review returned an invalid human assessment")
    ids = value["evidence_ids"]
    allowed = {source["id"] for source in packet["sources"]}
    if not isinstance(ids, list) or not ids or any(not isinstance(x, str) for x in ids) or len(ids) != len(set(ids)) or not set(ids) <= allowed:
        raise ValueError("Full case review cited unsupported evidence")
    has_human = "human" in allowed
    grades = (value["human_choice_assessment"], value["human_reason_assessment"])
    if has_human and ("NO_DECISION" in grades or "human" not in ids or len(ids) < 2):
        raise ValueError("Full case review did not ground the human assessment")
    if not has_human and grades != ("NO_DECISION", "NO_DECISION"):
        raise ValueError("Full case review invented a human decision")
    return value
