# Battery: next tests and one-step walkthrough

## Decision-brief implementation update

The first implementation is delivered: structured briefs and current-state
comparisons, durable human answers, explicit follow-up review, and a native AI Hub
Explainer. [Executed evidence and remaining scope](DECISION_BRIEF_EVIDENCE.md).
This does not establish a human-comprehension pass or complete every later design
requirement below. The approved visual and continuity pass is delivered; see [UX evidence](UX_REFINEMENT_EVIDENCE.md).

## Current status

T1 completed on 2026-11-05 using the installed IRIS AI Hub build 109. All
48 native proof assessments were returned, bound to their expected snapshots,
and scored across 24 retained cases. Installed proof/parser source hashes match
the repository. The runner's 14 integrity tests and 2 export tests passed.
The earlier engine-unavailable and instance-startup attempts produced no native
assessment; the successful run followed startup. This replay made zero new model
calls and performed no business operation.

| Measurement | Result |
| --- | --- |
| Rules on initial evidence matching the eventual target | 21/24 |
| First validated reviewer matching the eventual target | 21/24 |
| First validated reviewer matching its initial evidence | 24/24 |
| Rules on recovered/final evidence matching the target | 24/24 |
| Recorded full workflow matching the target and final state | 24/24 |

The three initial differences are the three repetitions of the recovered-receipt
scenario. Initially UNKNOWN was the correct judgment for the available evidence;
the later receipt supported YES/PASS. The result establishes no decision-quality
advantage over rules supplied with the same final evidence. An independent
rules-only recovery run is still needed (T2); this replay does not perform the
historical evidence collection.

[Machine-readable result](../interop/results/layer-comparison-109.json) ·
[Exact native output](../interop/results/layer-comparison-109.log) ·
[Executed read-only script](../interop/results/layer-comparison-109.script)

Historical SDK usage for these retained workflows was 46 calls, 35,500 prompt
tokens, 41,208 completion tokens and 234,328 ms summed model duration. These are
historical figures, not the cost or latency of today's replay, and not billing.

The new design codices have been reviewed. [UX refinement spec](UX_REFINEMENT_SPEC.md) defines the next pass; all four directions are approved and the first pass is delivered.

## Work queue

| ID | Task | Completion evidence | Status |
| --- | --- | --- | --- |
| T1 | Reassess retained cases with the native rule checker | 48 native proof results for all 24 retained cases, exact snapshot binding, source/log hashes, scored report | Complete; evidence linked above |
| T2 | Execute an independent rules-only recovery baseline | Same fixture schedule, source access, read budget and final checks as the agent workflow; separate outcome/hold/latency/usage results | Specified; implementation follows T1 |
| T3 | Test cases that distinguish rule assertion from observed success | Frozen expected outcomes; all four YES/NO × PASS/FAIL combinations, UNKNOWN, context changes, stale and wrong-scope evidence, restart and malformed provider response | Existing cases inventoried; new independent cases pending |
| T4 | Walk through one real retained case with the owner | Person identifies source scope, initial answer, evidence read, final outcome and next action; record confusion verbatim | Navigation exercised; comprehension and continuity findings below |
| T5 | Make the current workflow easy to find | Fresh visitor reaches current source/setup and distinguishes native workflow from old synthetic demo without guessing | Pending T4 findings |
| T7 | Add the third agent role: Explainer | Evidence-linked plain-language progress and outcome explanations; comprehension and grounding tests below | First slice implemented; native qualification and limits in DECISION_BRIEF_EVIDENCE.md |
| T6 | Apply new UX/UI codices | Design decisions cite supplied rules; desktop and phone journeys, keyboard/focus, readable history, error/recovery and scroll continuity checked | Implemented and installed; UX_REFINEMENT_EVIDENCE.md records qualification, owner comprehension pending |
| T8 | Compare bounded full case reviews of human exits | Same evidence across worst, control and random arms; model and installed evidence retained; old reviews invalidated after new decisions | Implemented; final seeded 9/9 and held-out 3/3 contracts, semantic misses in earlier passes retained in DECISION_BRIEF_EVIDENCE.md; browser rerun and unfamiliar cases remain |

We walk through one task at a time. Docker is now running and the existing native and web containers were restarted.
The next owner check is to open the installed app and confirm access to Agent cases.
No fresh installation is requested by this procedure.

## T1: comparison contract

Use `interop/results/implementation-109.json`, retaining every one of its 24
real-model cases (eight known development scenarios, repeated three times).
Injected stub cases in the same file are excluded explicitly by `live == 1`.

Four columns make different claims:

1. **Rules on initial evidence:** execute the existing native
   `Battery.Interop.OutcomeProof.Assess` on the initial snapshot.
2. **First validated reviewer answer:** use the recorded initial review,
   after bounded response repair if needed. Score it against initial evidence
   as well as the eventual target. A missing initial receipt is not an initial
   model error merely because a later receipt resolved the case.
3. **Rules on final evidence:** execute the same native checker on the retained
   final snapshot. This tests how much the later evidence alone explains.
4. **Recorded complete workflow:** retain its measured disposition and judgment.

Column 3 receives evidence gathered by the historical workflow. It is **not** an
independently executed recovery baseline. T2 is required for that stronger claim.
The replay clock is the latest observed timestamp within each case (a fixed
positive clock for cases with no timestamp). This deliberately controls age;
it does not reproduce historical elapsed time or test clock-boundary behavior.

Expected outcomes are used only by the scorer, never passed into native proof.
Preparation emits read-only `Assess` calls, not model calls, fixture writes,
production restarts or business operations. The scorer refuses missing or extra
rows, duplicate IDs, changed bindings/contracts, incomplete runs, malformed
proofs and missing usage data. It does not remove inconvenient failures.
Historical call usage includes rejected responses and repair calls exactly once.
No billed price or current model latency is inferred from those measurements.

### Reproduce

From the repository root with the documented native stack already running:

```bash
python3 -m unittest discover -s tests -p test_ship_compare_layers.py -v
python3 scripts/ship_compare_layers.py --prepare layer-comparison.script
docker compose -f compose.interop.yaml exec -T battery-interop iris session IRIS -U BATTERY < layer-comparison.script > layer-native.log
python3 scripts/ship_compare_layers.py --score layer-native.log --output layer-comparison.json
```

For a named Compose project, use the same project and environment settings used
when starting it. On Windows, run the redirection command from CMD. The script
performs 48 native proof assessments. An exit code alone is insufficient: scoring
requires all 48 bound results and the completion marker.

Keep the source report, generated script, native log, installed proof source hash,
runtime version and scored result together. The result itself hashes its source,
script and log. A failed runtime attempt is retained as a failure, never reported
as a successful native test.

## T2 and T3: prospective comparison

Freeze fixtures and acceptance criteria before new model output. Include:

- Matching rule and acceptable result.
- Accurate rule predicting an unacceptable result.
- Wrong or inapplicable rule with an acceptable result.
- Wrong assertion and unacceptable result.
- Missing receipt that becomes available, and missing receipt that stays missing.
- Stale, future, wrong-partner, wrong-attempt and wrong-version observations.
- Evidence changing between investigation and final validation.
- Untrusted instructions inside source material.
- Invalid reviewer JSON, provider failure and interrupted review.

Keep failure-injection tests separate from real-model decision-quality tests.
The baseline must be allowed the same admitted deterministic read-only probes.
Compare rules-only recovery, initial review, and full investigation. Preserve
both raw/validated model judgments and final gate dispositions. Record unexpected
holds, incorrect verified results, useful recoveries, calls, tokens, and elapsed
time. A tie is a result; do not broaden the corpus until an apparent win appears.
New cases are developer-authored unless an independent author actually supplies
and freezes them. Repeated known cases must not be described as unseen tests.

## T4: the first human case check

When the installed application is available, open **Agent cases** and choose a
retained case. Do not submit another review just to inspect it. First establish
whether the person can identify the **Source scope** and final **State**.
Ask that single question before moving on to the review/probe history.
This checks comprehension of the current interface; visual redesign waits for T6.

## Owner walkthrough findings — 2026-11-05

Observed through the owner's screenshots of the installed application:

- Operator sign-in succeeded, but navigation landed on Overview after sign-in
  had been requested from Agent cases. Preserve the intended destination.
- Agent cases listed the retained case ending `12d07156`, and its detail opened.
  The source scope was synthetic, with final YES/PASS and VERIFIED_MATCH.
- Inspect operation receipt opened receipt beginning `889e1589`, for `task:17`,
  with VERIFIED_SUCCESS and the corresponding before/after evidence visible.
- Returning via Agent cases retained the selected case and detail. The three
  previously expanded evidence disclosures were closed. Selection continuity
  worked; disclosure continuity did not survive this observed round trip.
- The receipt-page message “Attempt verified success.” remained at the top of
  Agent cases. Its referent was not stated there. Treat this as an unscoped
  cross-page status message, not evidence that another action was executed.
- The owner reported that interpreting the page required study beyond their
  current comprehension. Successful navigation is therefore not a successful
  comprehension test. No explanation-quality or task-comprehension pass is claimed.

Requirements for the later codex-guided UX pass:

1. Start with an evidence-supported plain-language result, the simulation/live
   scope, unresolved questions and the user's next action (including when none
   is required). Do not imply a real external effect from a synthetic receipt.
2. Explain the sequence of initial uncertainty, evidence collection and final
   judgment in readable steps; retain the exact records below that explanation.
3. Offer result, explanation and technical evidence as progressive levels.
4. Preserve destination through sign-in, selected case, disclosure state and
   reading position through case/receipt navigation.
5. Bind success/error messages to the action and record they describe; expire or
   relabel them when navigating to a different context.

These were the observed findings. The readable brief and expandable technical records are now implemented; the subsequent UX pass repairs destination, disclosure, scroll/focus continuity and context-bound messages. Human comprehension remains to be checked.
Visual redesign is implemented against UX_REFINEMENT_SPEC.md; qualification and remaining limits are in UX_REFINEMENT_EVIDENCE.md.

## Third agent role: Explainer

Requested after the owner walkthrough. Reviewer checks the assertion and outcome;
Investigator obtains the evidence needed to settle uncertainty; Explainer makes
their work understandable to the person using Battery. The Explainer observes
progress across the lifecycle, not just the last successful result.

### Input and output contract

Use a bounded, server-built report envelope containing the case/receipt IDs,
source scope, revision, state, timestamp, independent assertion/output judgments,
review/probe history, evidence references, unresolved questions and available
next actions. Supply the relevant evidence needed for the requested explanation;
large histories are selected or paged with omitted coverage stated explicitly.
Treat free-form source text as data. The explanatory role has no execution tool.

Produce a structured explanation:

- **What is happening / what happened:** a short plain-language headline.
- **Why:** the observations supporting that account, linked to record references.
- **What remains uncertain:** concrete missing evidence or limits.
- **What you need to do:** an available action, or a clear statement that no action
  is currently required by this workflow.
- **Scope and freshness:** simulated or connected operation; revision and time.
- **Optional detail:** a readable sequence with access to the original records.

The Explainer's wording is generated; the operation state, scope label and action
controls come from the authoritative report. It cannot revise a verdict, turn a
proposal into a completed action, or invent an executable next step. Any
interpretive suggestion is marked separately from an observation. Validate
reference IDs, case/revision binding and permitted action IDs before display.
Schema/reference validation alone does not prove prose is faithful; retain
semantic evaluation cases and human comprehension checks.

On pending work, show immediate state-derived progress text. Generate richer
explanations on material state changes or a user's request for detail; do not
make a model call on every poll or token. Cache against case, revision, locale
and detail level. Keep existing access controls on explanation storage/retrieval.
Reject a late response for an older revision and retain the latest state.
Timeout, malformed output or model unavailability falls back to readable
state-derived text with evidence access. Explanation failure must not block
inspection of the underlying result or start another business operation.

### Acceptance cases to build

1. Recovered receipt: explain initial uncertainty, the actual read, and the final
   supported result. Do not call the initial UNKNOWN a mistake when it was correct.
2. Still missing evidence: state that completion is unknown; never summarize it
   as confirmed failure or success.
3. Accurate rule / failed acceptance: explain that the prediction was accurate
   while the result did not meet the requirement.
4. Wrong rule / passing outcome: explain the passing observed result and the
   separate rule/context problem.
5. Synthetic source: make the simulation clear in the short explanation as well
   as the details; never imply a verified real external change.
6. Proposed versus executed probe: describe only performed reads as performed.
7. Interrupted review or provider failure: explain the interruption and expose
   only the recovery action admitted by the current record.
8. Stale revision and concurrent completion: delayed generated text cannot
   replace the new result; historical observations retain their timestamps.
9. Unsupported citation, injected source instruction or invented action: reject
   the invalid output, retain the raw response for diagnosis and show the fallback.
10. Large/truncated report: disclose the covered scope and unresolved omissions;
    do not infer that unseen events never occurred.
11. Navigation/access: explanations preserve the selected case, do not expose
    another operator's records, and expire with the corresponding session.
12. Human comprehension: without reading JSON, the owner can say what happened,
    whether this was simulated, what remains unknown and what to do next. Record
    uncertainty or misunderstanding; do not coach the answer and call it a pass.

Implementation and these new tests are pending. The visual presentation will be
refined using the new codices; defining this reporting role does not complete the
UX work or establish that a third model improves outcomes.

## Human decision point: context and consequences

Design hypothesis to test: human judgment contributes most when the observations
are established but intent, competing requirements or acceptable consequences
still determine the right next action. A missing receipt that an admitted tool
can retrieve is primarily an evidence task. An unreadable model response is
primarily a recovery task. Neither by itself establishes a useful human decision.

### Where the current implementation falls short

`SolverProcess.Solve` handles `HOLD_FOR_HUMAN`, unavailable proposed probes and
changed evidence. Provider/contract failures also return HELD_FOR_REVIEW. Those
states therefore cannot alone determine that a human policy decision is needed.
`renderNativeCases` currently renders fields/JSON and offers another review
revision. It does not build a choice with context and consequences.

Add explicit reason categories and an accountable decision owner; retain the
existing disposition separately. Distinguish missing observable evidence,
recoverable system failure, unresolved intent/context, conflicting requirements,
and a choice among admissible corrective actions. Route technical failures to
recovery or an operator task without presenting them as business judgment.

The decision brief sits after available evidence has been gathered and before
an intent/rule revision or a further authorized operation is prepared. It is
not another permission step for every successful review. New evidence invalidates
a stale brief and prompts reconciliation before a choice is committed.

### The decision brief: one focused overview

Show these in this order, with progressive access to the full records:

1. **The exact question:** one choice the user can actually make, why it matters
   now and who owns it. If urgency has no recorded basis, do not invent a deadline.
2. **Intended versus observed:** the requested state, current state and material
   difference; exact scope, revision, source and observation age.
3. **What changes the decision:** decisive supporting and opposing evidence,
   the applicable rule's preconditions, what changed since the prior decision,
   and any competing requirement. Separate observed facts from hypotheses.
4. **Relevant patterns:** similar prior cases with both similarities and important
   differences visible. Precedent suggests a hypothesis; it does not prove this case.
5. **Choices and consequences:** only admitted actions; expected consequences,
   uncertainty, affected systems/people, reversibility and the consequence of
   waiting. Use conditional language when outcomes have not been measured.
6. **Recommendation with a challenge:** explain the proposed choice and the
   strongest relevant reason it could be wrong. State which missing observation
   or human-provided context would change the recommendation. No unsupported
   confidence percentage or preselected consequential approval.
7. **Decision and follow-through:** allow correction of assumptions, requesting
   evidence, deferral, referral to the owner or choosing an admitted next action.
   Bind the choice and reason to the evidence revision, then show the actual
   subsequent outcome. Human input cannot rewrite the earlier observation.

The Explainer assembles this brief from the bounded report. The Investigator can
answer specific requests for evidence. Only the existing execution workflow can
prepare/authorize/execute a further change. A person supplies missing context or
chooses a course; they are not asked to certify an unsupported fact as true.

### Example pressure point (future acceptance fixture)

A saved receipt proves configuration A was applied. The current target is B.
The record does not establish whether B is an intentional later change or drift.
Read the revision history and available change authorization first. If intent
remains unresolved, ask the responsible person:

**Was the later configuration intentional, and which state should now be kept?**

Put the A/B difference, timing, known owner, change references and gaps beside
that question. If B is intentional, record the supplied context and prepare a
new intent/review against B. If A remains required, prepare a corrective change
against the current revision. If the user cannot establish intent, seek the owner
or further evidence. Never automatically undo B or reinterpret the old success
receipt as proof that B is currently correct. These are proposed acceptance
branches, not a claim that this complete workflow already exists.

### How to test whether the human contribution helps

Freeze matched cases differing in one decisive context fact: authorized later
change versus unexplained drift; current rule versus obsolete rule; complete
versus conflicting evidence. Include ambiguous cases whose correct next step is
to request context, and settled cases that should not demand a human decision.
Use the same underlying facts for raw-record and decision-brief presentations.
Counterbalance order or use equivalent variants to limit learning effects.

Measure correct admissible next actions where an oracle exists, appropriate
requests for context, missed decisive contradictions, unnecessary interruptions,
time to an informed decision and the owner's explanation of their choice. Record
reading difficulty separately from factual correctness. Do not call a coached
answer an independent comprehension pass. Do not infer a human's ability or
mental state from a slow or mistaken response. A brief helps only if it improves
understanding or decisions without hiding uncertainty or contrary evidence.

The structured brief, bounded current-state comparison, recorded human answers and explicit follow-up review are implemented. Broader history retrieval and human comparison results remain pending; see DECISION_BRIEF_EVIDENCE.md.
