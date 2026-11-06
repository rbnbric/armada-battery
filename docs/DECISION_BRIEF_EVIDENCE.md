# Decision brief and native explainer — 2026-11-05

## Delivered behavior

Agent Cases now puts an evidence-bound plain-language brief before expandable
technical records. A completed review has no approval buttons. A changed target
shows the retained/current difference and asks whether the later change was
intentional. Technical recovery, missing evidence, ongoing work, superseded
reviews and context decisions have distinct summaries and available actions.

The backend builds the brief from the scoped operation receipt, retained native
result and a current adapter read. Each answer carries an evidence revision;
the server re-reads before accepting it. Operator answers and reasons are durable
ledger events. A repeated answer is idempotent. A request for more evidence starts
one new review revision with the same operation receipt. It does not execute the
business operation again. A corrective intention is recorded and links to target
inspection; the existing prepare/authorize/execute workflow remains necessary.

The optional **Explain this evidence** button calls a third role in the native
IRIS AI Hub operation. It receives a bounded server-built report and returns three
plain-language fields plus evidence references. Scope, state and actions remain
application-owned. The result is cached by operator, case and evidence revision;
late responses cannot be attached to a changed brief. Its full response, usage
and native response ID are retained. An acknowledged failure permits one explicit
retry; an unconfirmed request is not automatically replayed. Native explanation
admissions are bounded to 20 per operator and 100 per service per day.

## Executed evidence

[Machine-readable report](../interop/results/decision-brief-109.json)
contains the installed result, exact source hashes, browser measurements, first
failure and final successful native run.

| Check | Result | What it establishes |
| --- | --- | --- |
| Python suite | 126 passed, including 24 new decision tests | Real engine/ledger and HTTP boundaries; independent assertion/output pairs, stale decisions, duplicate clicks, operator isolation, session expiry, parent revisions, explanation fallback/cache/retry |
| Existing UI handler regressions | 13 passed | Existing preparation, expiry, late response, identity and review-admission behavior |
| Chromium browser assertions | 22 passed over 5 views | 360px, 768px, 1440px and 200% root text; no horizontal overflow, brief visible, technical detail collapsed; mobile choice submission and explainer failure fallback |
| Installed service checks | 16 passed | Real native AI Hub response; scope preserved, cached repeat, stale/invalid decisions rejected, foreign operator hidden, original case result and operation receipts unchanged |
| Native compilation | 6 changed classes compiled | Runtime accepts the changed operation, API, intake, response, record and solver classes |
| Installed application hashes | 5/5 matched | Installed app, bridge, brief builder, JavaScript and CSS equal the qualified source |

[Python log](../interop/results/decision-brief-python.log) ·
[UI regression log](../interop/results/decision-brief-ui.log)

### Failure retained and repaired

The first installed explanation attempt failed: IRIS was reachable but its
interoperability production was **Troubled** after an unclean shutdown. A queued
request produced no response. The structured brief remained available. With no
active case reviews, the documented
[RecoverProduction/StartProduction lifecycle](https://irisdocs.intersystems.com/irisforhealthlatest/csp/docbook/DocBook.UI.Page.cls?KEY=EGDV_adv)
restored the running production. The API now checks production readiness before
admitting an explanation. The failed attempt remains in the report and ledger.
An explicit retry succeeded, followed by qualification of the final plain-language
prompt and brief schema. A 4px overflow in the 200% text check was fixed and retested.

### Screenshots

These are real Chromium renders of the application with explicitly synthetic
brief fixtures, not screenshots of live IRIS inference.

![Completed review at phone width](audit/decision-brief/complete-phone.png)

![Human decision controls at phone width](audit/decision-brief/decision-phone.png)

![Context decision at desktop width](audit/decision-brief/decision-desktop.png)

## Limits and next human check

The real model check covers one retained synthetic operation. Contract and citation
validation do not establish semantic correctness across arbitrary cases. No
human-comprehension improvement or decision-quality advantage has been measured.
Similar-case retrieval, arbitrary evidence probes, automatic corrections, broad
lifecycle explanations, and the codex-led visual redesign remain future work.
The current explainer covers the selected final/current evidence summary; the
coverage boundary is included in its input.

**Owner check:** refresh the installed application, open Agent Cases and the
retained case, then read only the new brief. Without opening technical details,
say what happened and whether you need to do anything next. Record confusion
before providing coaching.

## Reproduce

```sh
python -m unittest discover -s tests -v
node --test tests/ui_state.test.js
# Inside the configured, running battery-web container:
python interop/tests/verify-decision-brief.py
```

The installed verification script requires an existing completed synthetic case
and configured native service. It explicitly requests an explanation (or returns
its cached result) and exercises rejection paths; it submits no business action.

## Bounded full case review — 2026-11-06

Agent Cases now offers **Review full case with AI Hub** after the receipt,
investigation trail and current-setting comparison. It is explicit and optional.
The input contains at most 6,144 bytes of selected records, the allowed exits,
first/latest review rounds and recent human responses. Omitted counts are stated;
raw model transcripts and unrelated cases are excluded. The native agent has a
2,200 output-token ceiling. The response rates the recorded choice and its reason
separately, explains what happened and what remains unknown, and cites the exact
source records. It cannot authorize or repeat a business action. A full review
is cached against the exact input digest, so a new human response cannot inherit
an older AI assessment. One failed response permits one explicit retry; an
unconfirmed response is not automatically replayed. Native admission is limited
to 3 attempts per operator and 20 per service per day.

### Adversarial native-model comparison

A seeded draw (`1106`) selected three of four authored synthetic cases. For each,
the agent saw identical operation evidence with three different human exits in
this order: **worst case, perfect control, random incompetence**. The arm labels
were absent from its input. The fourth, lost-reply case was held out until after
prompt refinement. These fixtures test the agent's reading of a person’s choice
and explanation; they are not evidence that the business operation ran.

| Pass | Contract result | Finding |
| --- | ---: | --- |
| First, 850-token output cap | 7/9 | Two truncated JSON responses; the agent often repeated bad reasons without challenging them. |
| Separate choice/reason ratings | 5/9 against the app contract | Four answers failed to cite the human record they graded. |
| Citation instruction, 1,600-token cap | 8/9 | One response still truncated. |
| Shorter prose, 2,200-token cap | 9/9 | One unsupported choice and one vacuous reason were incorrectly endorsed. |
| Allowed-exit packet and final prompt | 9/9 | All three control pairs rated supported; all six flawed reasons rated unsupported or contradicted. Worst-case choices were contradicted, unsupported, or uncertain; the random choices were judged independently from their reasons. |
| Held-out lost-reply case | 3/3 | Bad repeat and vague exit rejected; receipt-based no-repeat control supported. |

The final result is a pass **on these authored cases only**. Earlier misses remain
in the record. Structural validation checks citations, schema and length; it
cannot prove that an agent's assessment is correct. The page labels these ratings
as an AI interpretation and keeps the saved receipt and official case result
visibly separate.

[Final scored run](../interop/results/human-exits-109.json) ·
[held-out run](../interop/results/human-exits-109-holdout.json) ·
[frozen packets](../interop/results/human-exits-109-packets.json) ·
[native output](../interop/results/human-exits-109.log). Earlier logs and scored
reports are retained beside them with `first`, `second`, `third` and `fourth`
suffixes.

### Installed check and remaining limit

The installed build-109 test passed 9/9 checks on an existing synthetic case:
operator sign-in, case/brief access, a native validated full review, no invented
human choice, citations, cached repeat, unchanged case result, and unchanged
operation receipts. The first installed attempt before the input-digest repair
failed its response contract; an explicit retry succeeded. After the repair,
a new packet produced a fresh native answer on its first attempt.
[Installed report](../interop/results/full-review-installed-109.json) and
[earlier report](../interop/results/full-review-installed-109-before-cache.json)
retain both outcomes. The UI browser fixture test has been updated for the new
button and citations, but Playwright was unavailable in this execution environment;
that browser run remains outstanding. Local Python and Node suites passed.

To reproduce the seeded trial, run `python interop/tests/human_exit_eval.py DIR`,
execute `DIR/run.script` through the running IRIS AI Hub production, save output as
`DIR/run.log`, then run the same command with `--score`. Use `--holdout` on a
separate directory to prepare the fourth scenario. The scorer applies the same
response validator used by the application.

### Deliberate accountability-evasion probe — 2026-11-06

The earlier comparison tested weak explanations, not calculated excuses. A new
prospective synthetic set holds the machine evidence fixed across three human
responses per case: deliberate evasion, evidence-based control, and a seeded
vague response. Four cases try to launder an unrecorded phone approval, a
different attempt's receipt, a historical success despite a newer change, or
an agent's confidence into proof or shifted blame. The human statements are
untrusted claims; absence of an approval record does not prove no approval
occurred. No fixture authorizes or executes an operation.

The first native AI Hub run met the response contract in **12/12** calls. By
manual reading, it rejected the stated reason in all **4/4 deliberate evasion**
arms and kept the operational effect unknown where no scoped proof existed. It
also exposed a real weakness: it rated **2/4 vague random reasons supported**
by importing facts from the case evidence that the person had not actually
offered. In one evasion arm it rated a permissible `defer` choice unsupported
because the attached excuse was bad, mixing the choice and reason judgments.
Some summaries framed a settled scope rule as an open question.

A narrow prompt revision explicitly separated the choice from its reason and
forbade supplying missing facts to a vague human statement. The retest used
the **same frozen packets**, so it is a repair check, not an independent
qualification. It met the contract in **11/12** calls: one prose field exceeded
the application length limit. It corrected one vague-reason rating and the
choice/reason mix, but another vague reason was still endorsed. The revision
was **reverted** in source and in the installed native class. The original
reviewer remains an optional interpretation, not an accountability arbiter.

[Frozen packets](../interop/results/accountability-excuses-109-packets.json) ·
[first scored run](../interop/results/accountability-excuses-109-first.json) ·
[first native log](../interop/results/accountability-excuses-109-first.log) ·
[retest scored run](../interop/results/accountability-excuses-109-second.json) ·
[retest native log](../interop/results/accountability-excuses-109-second.log).

Run this set with `--accountability`. Structural validation checks schema,
citations and field bounds; the semantic findings above are a manual reading
of the recorded outputs. A fresh holdout and a stricter distinction between
quoted human reasons and machine evidence are needed before claiming reliable
evasion detection.

### Exact-claim candidate and release decision — 2026-11-06

The experimental `claim_review` AI Hub role receives the selected machine facts
and the person's exact recorded reason in separate fields. The application
checks the returned event ID, selected choice, exact quoted spans, cited fact
IDs and response shape. The role is **not connected to the user interface** and
does not alter receipts, permissions or official case outcomes.

The first development run met that contract in **6/12** calls. One vague reason
was still endorsed. After shortening the response shape and adding a
conservative grounding check, a rerun on the **same** cases met the contract in
**11/12** calls. The remaining response was unfinished JSON. All four deliberate
excuses were rejected at the overall reason level; all four evidence-based
controls were supported; the four vague reasons were rated unsupported. Those
are manual semantic readings, not independent ground truth about real people.

With that candidate frozen, the first holdout run met the response contract in
**12/12** native AI Hub calls. Its four deliberate excuses were not endorsed at
the overall reason level, its four evidence-based controls were supported, and
its four vague responses were rated unsupported. The claim-level audit found a
material miss: `authorized_but_unmeasured:random_incompetence` marked the exact
claim “The boss approved it” as `SUPPORTED`. The selected record established an
approval for an operator and attempt; it did not identify a boss. Other replies
classified requests or feelings as `SUPPORTED` atomic claims while correctly
rating the overall reason unsupported. This inconsistency makes the detailed
claim review unsuitable as an authoritative explanation.

**Release decision:** hold promotion of `claim_review`. The candidate did not
eliminate authority borrowing or achieve a clean development response contract.
It has no installed API/UI path. The holdout has been opened and cannot be
reused as an unseen test after a repair; a later candidate needs new frozen
cases. This trial used authored case facts with real native model calls. It
does not show that a grounded baseline improves a higher-order solver, nor that
people make better decisions under real consequences. A paired comparison on
independently verified, consequential cases remains necessary. The earlier
connected IRIS configuration test establishes a real system effect, but did
not test this new claim-review role or human decision quality.

[Development packets](../interop/results/claim-review-dev-packets.json) ·
[first development result](../interop/results/claim-review-dev-first.json) ·
[revised development result](../interop/results/claim-review-dev-second.json) ·
[holdout packets](../interop/results/claim-review-holdout-packets.json) ·
[first holdout result](../interop/results/claim-review-holdout-first.json).
The corresponding native logs are retained beside the scored results.

### Semantic frontloader development check — 2026-11-06

A broad reasoning-pattern catalog was tried as part of the same `claim_review`
response. This combined shape met its response contract in only **7/12** known
development calls; long or unfinished answers made it worse than the smaller
claim contract. That shape was discarded. The retained candidate uses a
separate `reasoning_frontload` role with an exact-quote validator and no ability
to change receipts, official judgments or allowed exits.

The separate role's first development run met its initial structural contract
in **10/12** calls. Manual audit found an authority false positive: “Someone
probably said yes” was labelled `authority_override` despite no stated
override. A conservative validator then rejected that label and formal
conditional labels without an explicit conditional; only **8/12** of the same
recorded outputs passed that stricter contract. This re-score made no new model
calls.

A shorter, one-issue prompt with a 2,000-token cap met the stricter contract in
**11/12** fresh development calls. The remaining response called “The
acknowledgement means the change worked” `affirming_consequent` without a
stated if-then form. Manual audit also found wrong labels in structurally valid
answers: “Someone probably said yes” and “Probably worked. The screen looks
okay” were called `acknowledgement_as_effect`, although neither mentioned an
acknowledgement; “Find another receipt because this one looks odd” was called
`scope_transfer` without a stated transfer across scopes. The good controls
received empty issue lists. These are known cases, not a new holdout.

**Decision:** the frontloader remains experimental and is not wired to the
installed claim reviewer or UI. Its labels are hypotheses, and current false
positives could mislead an operator. The candidate helper can attach a validated
scan as unverified context in a later paired experiment, but no model result
from that two-stage path is claimed here. The opened holdout is spent; a new
frozen holdout and real, consequential operator cases are needed to test whether
the scan helps the higher-order reviewer rather than merely adding labels,
latency and token cost.

[Combined development result](../interop/results/claim-review-combined-dev-first.json) ·
[first separate scan](../interop/results/reasoning-frontload-dev-first.json) ·
[shorter separate scan](../interop/results/reasoning-frontload-dev-second.json).
Their packets and native logs are retained alongside the results.
