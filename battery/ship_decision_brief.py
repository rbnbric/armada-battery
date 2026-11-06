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
import re
from datetime import datetime, timezone
from .ledger import sanitize


# Reasoning patterns are review prompts, never proof that a premise is false.
# There is no agreed exhaustive taxonomy of fallacies; these stable IDs cover
# formal inference mistakes and common informal moves relevant to case reasons.
REASONING_PATTERNS = {
    "affirming_consequent", "denying_antecedent", "invalid_disjunction",
    "equivocation", "circular_reasoning", "false_dilemma", "hasty_generalization",
    "false_cause", "authority_override", "appeal_to_popularity",
    "appeal_to_emotion", "ad_hominem", "straw_man", "red_herring",
    "slippery_slope", "false_analogy", "composition_division",
    "appeal_to_ignorance", "burden_shift", "special_pleading",
    "cherry_picking", "scope_transfer", "time_transfer", "authority_transfer",
    "acknowledgement_as_effect", "responsibility_transfer", "missing_as_false",
}


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
            "responses": [{"decision_id": d.get("decision_id"), "choice": d.get("choice"), "reason": _short(d.get("reason"), 300), "recorded_at": d.get("recorded_at"), "revision": d.get("revision")}
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


def claim_review_packet(full_packet):
    """Project one bounded case packet into exact human words and cited facts."""
    facts = [source for source in full_packet["sources"] if source["id"] != "human"]
    human_source = next((source for source in full_packet["sources"] if source["id"] == "human"), None)
    responses = (human_source or {}).get("value", {}).get("responses") or []
    selected = responses[-1] if responses else None
    reason = selected.get("reason", "") if selected else ""
    truncated = reason.endswith("… [truncated]")
    if truncated:
        reason = reason.removesuffix("… [truncated]")
    packet = {
        "schema": 1, "case_id": full_packet["case_id"], "revision": full_packet["revision"],
        "scope": full_packet["scope"], "question": full_packet["question"],
        "coverage": full_packet["coverage"], "allowed_choices": full_packet["allowed_choices"],
        "facts": facts,
        "human_record": ({"event_id": selected.get("decision_id") or "selected-response",
                          "selected_choice": selected.get("choice"), "reason_exact": reason,
                          "truncated": truncated, "revision": selected.get("revision")}
                         if selected else None),
    }
    if len(json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()) > 6144:
        raise ValueError("Claim review exceeds the bounded AI input budget")
    return packet


def validate_claim_review(value, packet):
    """Reject invented quotes, sources, actions and oversized model text."""
    required = {"human_event_id", "selected_choice", "choice_assessment", "reason_assessment", "claims"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("Claim review returned an invalid response structure")
    human = packet["human_record"]
    if value["human_event_id"] != (human["event_id"] if human else None):
        raise ValueError("Claim review changed the human event")
    if value["selected_choice"] != (human["selected_choice"] if human else None):
        raise ValueError("Claim review changed the selected choice")
    grades = {"SUPPORTED", "UNSUPPORTED", "CONTRADICTED", "UNCERTAIN", "NO_DECISION"}
    for key in ("choice_assessment", "reason_assessment"):
        if value[key] not in grades:
            raise ValueError("Claim review returned an invalid assessment")
    if human:
        if "NO_DECISION" in (value["choice_assessment"], value["reason_assessment"]):
            raise ValueError("Claim review erased a recorded decision")
        allowed = {item["id"] for item in packet["allowed_choices"]}
        if human["selected_choice"] not in allowed and value["choice_assessment"] != "UNSUPPORTED":
            raise ValueError("Claim review endorsed an unavailable action")
    elif (value["choice_assessment"], value["reason_assessment"]) != ("NO_DECISION", "NO_DECISION"):
        raise ValueError("Claim review invented a human decision")
    claims = value["claims"]
    if not isinstance(claims, list) or len(claims) > 3 or bool(claims) != bool(human):
        raise ValueError("Claim review returned invalid claim count")
    fact_ids = {item["id"] for item in packet["facts"]}
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {"quote", "kind", "assessment", "evidence_ids"}:
            raise ValueError("Claim review returned an invalid claim")
        if not isinstance(claim["quote"], str) or not claim["quote"].strip() or claim["quote"] not in human["reason_exact"]:
            raise ValueError("Claim review invented human words")
        if claim["kind"] not in {"effect", "scope", "approval", "intent", "responsibility", "other"}:
            raise ValueError("Claim review returned an invalid claim kind")
        if claim["assessment"] not in {"SUPPORTED", "CONTRADICTED", "UNVERIFIED", "UNCERTAIN"}:
            raise ValueError("Claim review returned an invalid claim assessment")
        ids = claim["evidence_ids"]
        if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids) or len(ids) != len(set(ids)) or not set(ids) <= fact_ids:
            raise ValueError("Claim review cited unsupported evidence")
    if human and value["reason_assessment"] == "SUPPORTED":
        fact_words = set(re.findall(r"[a-z]{4,}", json.dumps(packet["facts"], sort_keys=True).lower()))
        stop = {"this", "that", "there", "these", "those", "with", "from", "because", "should", "could", "would", "about", "another", "maybe", "which", "their", "have", "been", "were", "what", "when", "where", "then", "than", "some", "case", "review", "evidence"}
        grounded = any(
            claim["assessment"] == "SUPPORTED" and len((set(re.findall(r"[a-z]{4,}", claim["quote"].lower())) - stop) & fact_words) >= 2
            for claim in claims
        )
        if not grounded:
            raise ValueError("Claim review endorsed a reason without words grounded in the selected facts")
    return value


def validate_reasoning_frontload(value, packet):
    """A bounded diagnostic scan; its labels never change the official case."""
    if not isinstance(value, dict) or set(value) != {"human_event_id", "issues"}:
        raise ValueError("Reasoning frontload returned an invalid response structure")
    human = packet["human_record"]
    if value["human_event_id"] != (human["event_id"] if human else None):
        raise ValueError("Reasoning frontload changed the human event")
    issues = value["issues"]
    if not isinstance(issues, list) or len(issues) > 1 or (not human and issues):
        raise ValueError("Reasoning frontload returned invalid issue count")
    for issue in issues:
        if not isinstance(issue, dict) or set(issue) != {"quote", "pattern", "missing_link"}:
            raise ValueError("Reasoning frontload returned an invalid issue")
        if not human or not isinstance(issue["quote"], str) or not issue["quote"].strip() or issue["quote"] not in human["reason_exact"]:
            raise ValueError("Reasoning frontload invented human words")
        if issue["pattern"] not in REASONING_PATTERNS:
            raise ValueError("Reasoning frontload returned an unknown pattern")
        if not isinstance(issue["missing_link"], str) or not issue["missing_link"].strip() or len(issue["missing_link"]) > 180:
            raise ValueError("Reasoning frontload returned an invalid explanation")
        quote = issue["quote"].lower()
        if issue["pattern"] == "authority_override" and not re.search(
            r"\b(so|therefore|ignore|override|bypass|instead|record success|close the question|no need)\b", quote
        ):
            raise ValueError("Reasoning frontload labelled authority without an override")
        if issue["pattern"] in {"affirming_consequent", "denying_antecedent"} and not re.search(r"\bif\b.*\bthen\b", quote):
            raise ValueError("Reasoning frontload labelled formal inference without its conditional form")
    return value


def claim_review_with_frontload(packet, scan):
    """Attach bounded, explicitly unverified reasoning hints to a review packet."""
    validate_reasoning_frontload(scan, packet)
    staged = {**packet, "reasoning_hypotheses": scan["issues"]}
    if len(json.dumps(staged, sort_keys=True, separators=(",", ":")).encode()) > 6144:
        raise ValueError("Reasoning frontload exceeds the bounded AI input budget")
    return staged
