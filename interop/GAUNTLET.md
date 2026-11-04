# Interoperability edge gauntlet

Status: reassessed native review pipeline. The deterministic contract and
fault-injection runs are complete: 50/50 and 26/26 checks passed. The expanded
live-model corpus and its exact scores are in `results/edge-109.json`.
The full downstream execution gauntlet remains a separate pending boundary.

The next increment adds the [receipt solver](RECEIPT_SOLVER.md). Its 149 native
proof cases, 27 workflow fault cases and repeated live-model run are recorded
separately in `results/solver-109.json`. The 32-case report below measures the
older broad prose-only review task, not this narrower typed receipt profile.
Historical reproduction below requires commit `7a5b88e`.

For every fixture retain the original input, selected rule and defeated rules,
independent acceptance criterion, expected assertion accuracy, expected output
result, reviewer JSON, investigator handoff and probe, IRIS message trace,
gate disposition, downstream receipt, and external effect count. A model's
fluent explanation is not a substitute for any of these observations.


## Reassessment before the expanded run

Five native repros demonstrated accepted invalid values: numeric, object, and
whitespace-only summaries, duplicate citations, and object-valued facts. The
repaired process validates exact field shapes, string types, lengths, unique
citations, and evidence containers. Invalid cases are rejected before a model
call. Case JSON is bounded to 65,536 characters, IDs to 120, case text and fact
values to 4,096, facts to 64, and citations to 16.

The original `missing_observation` fixture also had an incorrect oracle. No
application state was observed, yet its gold answer was YES/PASS. The expanded
fixture expects NO/UNKNOWN: NO means the assertion is unverified, and UNKNOWN
means the actual output cannot be established. The original report is retained
as history; its 13/13 score was relative to that flawed original oracle.

Before the live run, 32 fixtures and acceptable probe sets were frozen in
`tests/edge-fixtures.json`. These include the corrected baseline, absence vs
observed zero, currency units, exact expiry, timezone equivalence, clock skew,
conflicting contracts, HTTP 202 without a business receipt, wrong-attempt
acknowledgements, stale readback, revoked authority, alias ambiguity, two
injection variants, and four fact-order metamorphic pairs. Answer keys and
acceptable probe lists never enter model requests.

## Measured result — 4 November 2026

| Measurement | Result against frozen expectations |
| --- | --- |
| Native contract checks | 50/50 |
| Native fault/replay/restart checks | 26/26 |
| Assertion judgments | 31/32 |
| Independent output judgments | 28/32 |
| Review/escalation routes | 31/32 |
| Acceptable next probes | 16/22 expected investigations |
| Exact preferred next probes | 14/22 expected investigations |

There were 53 actual model calls: 32 reviewers and 21 investigators. One
expected investigation was skipped after premature agreement. The SDK reported
24,835 prompt tokens and 39,967 completion tokens, with 581.351 seconds of
summed model time. The live corpus job took 585.777 seconds. Billing has not
been independently verified.

The four fact-order pairs preserved verdict, output, route and probe. One
changed applicability from INAPPLICABLE to APPLICABLE despite unchanged facts.
Thus 3/4 pairs preserved every measured semantic field.

### What failed, and what the test itself needs

- **Missing observation:** the reviewer returned YES/PASS despite unavailable
  application state and no receipt. It skipped investigation. This is a clear
  premature-agreement defect; valid JSON and valid citations did not catch it.
- **HTTP 202:** the reviewer returned FAIL for an unobserved business outcome.
  The expected grade was UNKNOWN. The investigator did select receipt inspection.
- **Clock conflict and conflicting contracts:** both returned FAIL rather than
  the frozen UNKNOWN. These two oracles are ambiguous: the criterion itself
  demands reliable ordering or a uniquely identified contract. Failing that
  prerequisite can reasonably fail the stated criterion while leaving the
  business outcome unknown. Scores remain unchanged; the next corpus must
  separate criterion validity from observed outcome more precisely.
- **Probe selection:** receipt gaps sometimes led to rule-selection probes.
  The report distinguishes acceptable alternatives from preferred probes and
  retains every disagreement, including the missed escalation.
- **Applicability:** the partner-scope pair changed applicability when facts
  were reordered. The primary verdict stayed NO, but the explanation contract
  is not invariant to harmless ordering.

### Next implementation priorities

1. Represent outcome availability, receipt identity, freshness and scope as
   typed evidence. Deterministic checks must prevent agreement when required
   proof is missing; a model's PASS cannot supply that proof.
2. Execute bounded read-only probes, retain the new evidence, and run a bounded
   follow-up review. Selecting a probe name alone does not solve the mystery.
3. Connect the existing action gate and correlated readback only after the
   review boundary is qualified. Then test actual effect counts, concurrent
   replay, crashes and late replies across that complete path.

The current review pipeline is an inspectable WIP, not a qualified total solver.

## What the checks actually exercise

| Layer | Native exercise | Measurement boundary |
| --- | --- | --- |
| Contracts | 50 parser, shape, type, size, citation and matrix checks | No model calls |
| Fault injection | 26 cases through Service → Process → Operation | Test operation replaces the provider; injected errors are not real provider outages |
| Timeout | One-second test deadline and a three-second delayed reply for each agent | Saved held response checked again after the late reply |
| Replay/restart | Repeated review and review after production restart | Reviews run again; this does not prove business-effect deduplication |
| Live models | 32 frozen inputs through native `%AI.Agent` | Real provider calls over synthetic business evidence |
| Action/readback | Not connected to this production | No claim of downstream execution, repair, or concurrent effect safety |

Fault tests inspect the resulting state, exact reviewer/investigator call
counts, case ID and verdict in the escalation handoff, and a nonempty outcome
explanation. Invalid cases produce zero provider-boundary invocations. The
suite restores `Battery.Interop.Production` after running. Test-only classes
are outside `interop/Battery` and are not compiled by the standard image build.

## Reproduce

Use a disposable test instance because the fault suite temporarily replaces
the running production. In the BATTERY terminal, compile the test-only classes:

```objectscript
Do $SYSTEM.OBJ.LoadDir("/home/irisowner/dev/interop/tests", "ck", , 1)
Do ##class(Battery.Test.FaultSuite).Run()
```

Require 26 `FAULT_CASE` JSON records with `passed: 1`, no `FAULT_SUITE_ERROR`,
and the `FAULT_PRODUCTION_RESTORED` marker. Then run from the repository root:

```bash
docker compose -f compose.interop.yaml exec -T battery-interop \
  iris session IRIS -U BATTERY < interop/tests/edge-contracts.script
# Every one of the 50 named checks must equal 1.
docker compose -f compose.interop.yaml exec -T battery-interop \
  iris session IRIS -U BATTERY < interop/tests/edge-corpus.script
# Billable: requires 32 EDGE_CASE records and EDGE_CORPUS_END.
docker compose -f compose.interop.yaml exec -T battery-interop \
  iris session IRIS -U BATTERY < interop/tests/edge-evidence.script
```

Retain all model misses, parse/shape rejections and alternative probes.
Classify a permitted alternative separately from an exact preferred probe.
For transformed pairs, compare verdict, output grade, applicability, route and
probe independently. No shell exit code or final marker alone proves a pass.

## Required invariant matrix

| Assertion | Output | Example | Required route |
| --- | --- | --- | --- |
| accurate | pass | applicable alias accepted once | gate may inspect; no automatic effect |
| inaccurate | pass | missing-field rule selected for valid input | investigate rule selection; preserve good output |
| accurate | fail | target accepts but duplicate send occurs | investigate effect receipts; do not call this success |
| inaccurate | fail | wrong partner receipt reused | investigate scope; hold effects |
| unknown | unknown | response lost and no correlated readback | hold `OUTCOME_UNKNOWN`; no resend |

## Fault families

1. **Rule and context:** no match, multiple matches, conflicting rules,
   false precondition, old contract, old target version, ambiguous alias,
   missing required field, case-insensitive collision, unknown field, and
   apparently correct output under the wrong rule.
2. **Evidence:** absent versus observed absent, stale readback, clock skew,
   mixed snapshots, forged fact ID, contradictory sources, truncated message,
   malformed model JSON, invented citation, and unsupported confidence.
3. **Delivery:** duplicate input, same key across partners, transport failure
   before dispatch, response lost after effect, late acknowledgement, repeated
   acknowledgement, concurrent replay, process restart, and readback racing
   an external change. Count effects independently of model prose.
4. **Agent boundary:** prompt injection in message content, tool output that
   impersonates instructions, provider timeout, rate limit, empty content,
   truncated reasoning, invalid probe, budget exhaustion, and a small reviewer
   whose two judgments disagree. All become visible held states.
5. **Gate and operator:** revoked authority, changed target, expired evidence,
   changed case version, stale permit, unauthorized action, human refusal,
   operator correction, and manual replay after an unknown outcome.

Generate combinations at the boundaries of partner, schema, time, and effect
identity, then shrink each failure to a reproducible fixture. The same fixture
must replay after restart without a second business effect. Random cases add
coverage; the fixed corpus preserves regressions.

The release gate is native EAP compilation plus traced end-to-end execution of
the fixed corpus. Every unsafe effect count is a hard failure. A correct hold is
a valid disposition, while a wrong assertion or wrong output grade remains a
failure even when the final gate prevents damage. Publish model scores together
with the exact image build, model IDs, prompts, inputs, and measurement method.
