# Accountability review experiment

Status: experimental candidate, 2026-11-06. The native `claim_review` role is
not exposed in the installed application; [the first holdout failed the
claim-level promotion gate](DECISION_BRIEF_EVIDENCE.md#exact-claim-candidate-and-release-decision--2026-11-06).

## Semantic frontloader revision

An independent `reasoning_frontload` candidate reconstructs the person's
**stated** premise and conclusion before claim grading. It checks whether a cited fact establishes every material
qualifier in the claim: actor, authority, attempt, target, time and result. A
generic approval record cannot silently become “the boss approved it.” A
transport acknowledgement cannot silently become an effect receipt.

Its bounded response may name the most consequential reasoning pattern, with an
exact quote and the missing inference link. The registry covers common formal
errors (such as affirming the consequent) and informal errors of relevance,
presumption, ambiguity, causal inference, scope and responsibility. The pattern
is a **diagnostic hypothesis**, not a judgment that the premise is false. In
particular, `authority_override` applies only when an authority claim is used
to bypass a required evidence, permission or accountability check; a mere
mention of a manager is not enough. The application validates the quote and
pattern ID but cannot validate the model's semantic interpretation.

There is no agreed exhaustive taxonomy of fallacies; a growing label list
cannot replace checking the actual premise-to-conclusion link. See the
[Stanford Encyclopedia of Philosophy on informal logic](https://plato.stanford.edu/entries/logic-informal/)
and the [Internet Encyclopedia of Philosophy on fallacies](https://iep.utm.edu/fallacy/).
The first attempt combined this scan with the claim review and returned only
7/12 valid development responses, so that shape was discarded. The scan is now
a separate diagnostic role; its output is not yet an official finding. It
requires a valid development run, a new frozen holdout and a paired real-case
comparison before any promotion.

### Test whether grounding helps the higher-order solver

Synthetic trials can expose schema errors and invented support, but cannot
establish an improvement in real decisions. Use prospective, legitimate IRIS
administration cases with an actual operator decision and a separately verified
receipt/readback. Freeze each case at the point the decision was made. Give the
same facts, choices and model budget to (A) the higher-order reviewer alone and
(B) that reviewer with the validated fact sheet and reasoning scan. Keep the
scan's hypotheses labelled as such. Compare both answers with the subsequent
independently checked effect and the operator's recorded reason; count false
success, borrowed authority, unsupported blame, unresolved holds, useful
corrections, latency and token use. The application's deterministic receipt
remains authoritative in both arms. Report ties and failures. One connected
fixture does not establish a general benefit.

## The failure to solve

The [native accountability probe](DECISION_BRIEF_EVIDENCE.md#deliberate-accountability-evasion-probe--2026-11-06) rejected four calculated excuses, but sometimes supplied a good fact that a person had not given and then marked their vague reason supported. One response mixed an admissible `defer` choice with its bad rationale. A prompt-only repair improved some ratings but broke the response-length contract, so it was reverted.

The question is whether a bounded review can **preserve the exact human claim, distinguish it from observed facts, and identify a useful next step** without turning uncertainty into success, failure, approval, or blame. The agent's interpretation must never alter an operation receipt, authorize a new action, or decide that a person lied.

## Five independent judgments

Each review must retain these axes separately. `UNKNOWN` is a legitimate answer on each applicable axis; a judgment on one axis cannot fill a gap on another.

| Axis | Owner and evidence | Example |
| --- | --- | --- |
| Operation effect | Existing receipt/probe reconciliation, bound to partner, attempt, target and time | A transport acknowledgement leaves the effect `UNKNOWN`; a scoped success receipt verifies only its recorded operation. |
| Rule assertion | Existing rule review, including applicability and the evidence revision it used | A rule may be accurately applied even when the measured output fails acceptance. |
| Selected human action | Application's allowed exits plus facts at the decision revision | `defer` can be permissible while its attached explanation is false. |
| Human reason claims | The person's **exact recorded words**, checked against cited facts | “Manager approved by phone” is a claim whose approval evidence is absent; that does not prove the call never happened. |
| Approval or authority | Recorded authorization source, scope and revision | An agent's confidence or a person's uncorroborated assertion cannot create an approval record. |

The selected action and the reason may conflict: `defer` paired with “record success now” is a conflict to show, not an invitation to silently reinterpret the click. An earlier verified receipt remains historical evidence when a newer configuration differs; current intent remains unresolved until observed or supplied by the responsible owner.

## Proposed review contract

1. **Application constructs a fact sheet.** Each fact has an ID, kind, scope (partner/attempt/target), observed time, source, and value. It distinguishes `found`, `not_found_in_selected_sources`, `unavailable`, `stale`, and `conflicting`; an absent record is never encoded as a proven negative. The application computes the official effect and allowed exits from its existing rules. The packet keeps the current 6,144-byte limit and reports omitted records.
2. **Human record stays verbatim.** Send the selected action ID and exact reason as separate fields with their ledger event ID and evidence revision. Do not summarize the reason before grading it. Long reasons remain in the ledger; the bounded packet includes a visibly marked excerpt and a `truncated` flag. If the decisive claim lies beyond the excerpt, the agent must say it cannot assess the full reason.
3. **Agent extracts atomic claims.** For each material claim, return an exact quoted span from the human reason, a claim kind (`effect`, `scope`, `approval`, `intent`, `responsibility`, or `other`), and `SUPPORTED`, `CONTRADICTED`, or `UNVERIFIED` with cited fact IDs. It may not cite a fact as though the person stated it. Unsupported responsibility transfers (“the vendor owns my choice”) remain claims, not changes to the ledger's recorded actor.
4. **Application validates the structure.** Quoted spans must be exact substrings; citations must exist and match the case revision; claim IDs and statuses must be valid; text bounds must hold. Validate scope and the deterministic effect/approval invariants again after inference. A failed validation produces a visible `review unavailable` state with the saved facts intact. No partial AI verdict is presented as complete.
5. **Agent explains, application composes.** The model may write a short explanation of what its claim review suggests and what evidence would settle an unresolved claim. The application presents the official outcome and selected action separately, then the claim assessment with citations. Its output labels read **AI assessment of recorded reason**, never “approved,” “verified,” or “dishonest.”

The model may still misclassify semantics. Exact quotes and deterministic validation prevent invented provenance and contract leaks; they do not make model judgment authoritative. The human can correct context or request another evidence read, creating a new revision rather than overwriting the old answer.

### Candidate response shape

```json
{
  "human_event_id": "ledger-event-id",
  "selected_choice": "defer",
  "choice_assessment": "SUPPORTED",
  "claims": [
    {
      "quote": "The AI was confident, so it worked",
      "kind": "effect",
      "assessment": "UNVERIFIED",
      "evidence_ids": ["review", "probes"]
    }
  ],
  "unresolved": "No scoped effect receipt is available.",
  "next_observation": "Check the same attempt's effect receipt."
}
```

This shape is illustrative. Freeze the exact schema before the blinded run. The application should produce the plain-language operation summary from its typed facts; model prose has a strict length bound. Do not silently truncate an overflowing answer, since truncation may remove the qualifier that makes it accurate. Invalid output falls back to the deterministic brief. One explicit retry can be measured separately and charged to the existing review budget; it is not an automatic replay after an unconfirmed call.

## Experiment, before promotion

### Baseline and candidates

- **A — current:** Existing full-case prompt and validator, at the pinned native model/build. The 2026-11-06 first run is historical evidence, not a new holdout.
- **B — exact-claim:** Same model and budget with the new fact sheet, exact reason spans and typed response. No new operation or authority tools.
- **C — ablation:** B without claim extraction, to measure whether the extra structure improves reason grounding rather than merely a changed prompt.

Freeze model/build, prompt hashes, packet bytes, decoding settings, output cap and scorer before execution. Run the same case facts and human exits through A/B/C, preserving raw responses, usage and latency. Do not tune on holdout results. For comparability, the app-derived effect and allowed exits are held constant; only the review representation differs.

### Cases and oracle

Create 8 development scenarios and 4 unseen holdout scenarios. Each has three arms in the requested order: **worst-case excuse, evidence-based control, seeded random incompetence**. Change only the human choice/reason within each trio. Include missing receipts, wrong-scope receipts, later changes, conflicting reads, alleged off-record approval, agent/vendor blame, a choice/reason contradiction, prompt injection inside a reason, and an actually recorded approval. Pair at least four scenarios that differ by one decisive fact, such as a matching rather than mismatched attempt ID. This catches a reviewer that always rejects or always approves.

Write the oracle **before** model calls. It records official effect, allowed action, exact claim spans, acceptable claim statuses, and which observations remain unknown. Two reviewers independently check disputed semantic labels; retain their disagreement and adjudication. Do not expose the arm label or oracle to the model. Holdout cases must use new wording and identities, not paraphrases of the four earlier fixtures.

The native harness may call the AI Hub operation directly as in the previous experiment. Mark those calls as **synthetic model trials**; they do not exercise the installed API's per-operator admission limits or prove business effects. Separately run a small installed-service path test for cache invalidation, owner isolation, recovery and unchanged receipts. Stage the run: first four development scenarios, then the remaining four, then the sealed holdout. A and B run on all 36 packets; diagnostic C runs only on the 24 development packets: **96 native calls maximum**. Fix an aggregate 160,000 output-token ceiling and the per-call cap before the first call. If either ceiling is reached, stop and report an incomplete experiment rather than quietly extending the budget or sampling only favorable cases.

### Scoring and gates

Report counts with denominators by arm and scenario, including invalid responses and retries. Record: false verified effect or approval; wrong-scope evidence used as proof; historical success erased; choice/reason conflation; a human reason improved with unspoken facts; exact-quote and citation errors; unresolved facts turned into settled claims; contract failures; latency and tokens. Compare A/B/C on the **same development cases** and A/B on the same sealed holdout. Never collapse these into one flattering accuracy number.

Promotion to the optional UI requires zero false verified outcomes/approvals or automatic actions on the holdout, zero fabricated human quotes or cross-case citations, and every response either valid or an explicit fallback. The new design should reduce reason-grounding errors against A without increasing critical errors. A small holdout cannot establish general reliability, even if it passes; unfamiliar real cases and operator comprehension remain separate qualifications. If the gate fails, retain the current deterministic brief and label AI review experimental.

## UI and audit path

Present **what happened** from the application first, followed by **what the person selected**, **what their reason claims**, and **what remains open**. Place source and time beside each assertion. Keep the long trail, model output and technical IDs expandable. On phone, one continuous vertical flow should preserve the currently viewed receipt. A person may add context or correct a claim through a new ledger event; the earlier words and assessment remain available for later analysis. The larger analyzer may compare revisions and outcomes only from these attributed records, with access controls and no inferred personal blame from one bad explanation.

## Work order

1. Freeze schema, oracle and holdout; review the five axes with the Battery owner.
2. Build the typed fact sheet and exact-quote validator without changing official decisions.
3. Add the candidate AI Hub role and deterministic fallback; preserve the current model for A.
4. Execute A/B/C blinded trials, then the sealed holdout once. Repair on development cases only and create a **new** holdout if a later revision needs qualification.
5. Run installed API and phone/desktop decision journeys; record where a person misreads “unverified” as “false” or AI assessment as authorization.
6. Publish the full comparison and only then decide whether B replaces the optional reviewer.
