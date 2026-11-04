# Receipt solver: evidence before agreement

This increment makes receipt reconciliation a bounded native IRIS workflow.
The agent calls use AI Hub; the read-only probe executes through a separate
Interoperability Business Operation against persisted adapter snapshots.
The demonstration adapter data is synthetic. No external system is queried
and no business mutation is issued by this increment.

## Execution contract

```text
Intake → Solver → initial adapter snapshot → small reviewer
                              ↓ disagreement / unknown
                       larger investigator proposes a probe
                              ↓
                  one receipt/readback probe → follow-up review
                              ↓
                 final adapter read → deterministic disposition
```

`Battery.Interop.Production` routes `Battery.CaseProcess` to `SolverProcess`.
The earlier `CaseProcess` is now the internal `Battery.Review` component. It
retains model-contract validation and calls the larger agent when its reviewer
returns a negative or unknown finding. The solver also detects evidence gaps
when that reviewer wrongly agrees. It selects the required receipt probe even
if the model suggests a different probe; proposed and executed probes remain
separate in the response.

The receipt profile is deliberately specific: an applicable versioned rule
predicts an exact effect count and result, and an independent acceptance
criterion specifies its own exact count and result. These are evaluated
separately. A correct prediction can accompany a failing outcome. A wrong or
inapplicable rule can accompany a passing outcome.

### Adapter ownership

`EvidenceBinding` binds a case ID to its exact original `CaseJSON`, a measurement
contract, and initial/current observations. The intake and agent operation
cannot write this table. A trusted adapter or operator populates it; the demo
suite does so explicitly with synthetic values. Unbound cases and changed case
payloads are held before spending a model call. This is an internal production
contract, not a newly implemented user authentication or database ACL system.

The measurement contract has exactly these fields:

```json
{
  "profile": "receipt-v1",
  "partner": "A",
  "attempt": "attempt-1",
  "target": "target-1",
  "version": "v1",
  "rule_version": "v1",
  "expected_count": 1,
  "expected_result": "COMPLETE",
  "accepted_count": 1,
  "accepted_result": "COMPLETE",
  "max_age": 3600
}
```

A complete observation has exactly `available`, `partner`, `attempt`, `target`,
`version`, `count`, `result`, `source`, and `observed_at`. `available` is a JSON
boolean; count and timestamp are nonnegative integer JSON numbers. Counts are
bounded to one million and maximum age to 1–3600 seconds. `observed_at` uses the
IRIS `$HOROLOG` day/second clock converted to seconds by `OutcomeProof.Now()`;
external timestamp adapters are not yet implemented. Exact expiry is stale;
future observations are rejected. Scope must match on all four fields.
An unavailable observation is represented by `{"available": false}`.

An observed count of zero is real evidence. An absent observation is UNKNOWN.
Neither a transport acknowledgement nor a model statement can establish an
observed effect. Strings, booleans, fractions, negative numbers, extra fields,
and wrong-scope observations cannot masquerade as valid numeric proof.

### Model inputs and bounded investigation

Original inputs remain in native message storage. For this profile, the model
receives a neutral `receipt-review` ID and three adapter-bound facts: `B_CONTRACT`, `B_OBSERVATION` and the
evaluation clock `B_EVALUATED_AT`. Original
free-form claims are not mixed into those facts. This changes the model's task
from judging arbitrary prose to explaining the explicit measurement contract.
It does not solve the original broad prose-only corpus by assertion.

A missing, stale, wrong-scope, or failing receipt leads to one bounded receipt
probe. The production reads `CurrentJSON` through `EvidenceOperation`. A changed,
usable observation triggers one follow-up review. Identical or unusable evidence
stops the loop. There are at most two review rounds, each containing at most one
reviewer and one investigator call, and at most three evidence reads. The
investigator proposes a probe; the supported receipt profile determines which
read can actually execute. Other probe implementations remain future work.

Before returning a verified result, the process reads again and checks that the
original case binding, measurement contract and selected observation are
unchanged and still fresh. Changes produce a visible hold. This establishes a
snapshot disposition; it does not grant a future action permit or solve a
read/write race around an external mutation.

## Results shown to callers

| Field/state | Meaning |
| --- | --- |
| `ReviewerVerdict`, `OutputResult`, `ReviewerApplicability` | Last contract-validated model judgment; invalid responses leave these fields empty |
| `GateVerdict`, `GateOutput`, `ProofJSON` | Deterministic judgment for the bound receipt profile |
| `InvestigatorProbe` | Last proposed model probe |
| `ExecutedProbe` | The bounded read actually executed |
| `ReviewHistoryJSON`, `ProbeHistoryJSON` | All review rounds, usage, reads and snapshots |
| `VERIFIED_MATCH` | Fresh measurement verifies the applicable rule prediction and acceptance criterion |
| `VERIFIED_MISMATCH` | Fresh measurement establishes a rule or outcome mismatch |
| `HELD_FOR_EVIDENCE` | Evidence is missing, malformed, stale or out of scope |
| `HELD_FOR_REVIEW` | Contract/provider/probe failure, or evidence changed during reasoning |

A raw YES/PASS may coexist with a held final disposition. Do not display the raw
model answer as the final result. VERIFIED means this measurement was checked;
it never means a repair was performed or a downstream action was authorized.
The original response text is retained in native `AgentResponse` messages,
including rejected answers; it is scored separately from these validated fields.

## Run the native checks

Build and start the container using [the setup instructions](README.md). Use a
disposable instance: test suites stop/start productions and populate synthetic
`EvidenceBinding` rows. In a BATTERY terminal:

```objectscript
Do $SYSTEM.OBJ.LoadDir("/home/irisowner/dev/interop/tests", "ck", , 1)
Do ##class(Battery.Test.SolverSuite).Run(0,1)
```

Require 27 `SOLVER_CASE` records with `passed: 1`, no `SOLVER_ERROR`, and
`SOLVER_END`. The stub reviewer deliberately says YES/PASS to every valid input;
tests inject provider errors, malformed model evidence, changing bindings and
failed reads. A valid reviewer followed by a malformed or failed investigator
still permits the predefined read-only probe; it cannot authorize a mutation.
The failed model answer stays in review history. A matching held state caused by an unexpected solver exception
is explicitly a failure.

```bash
docker compose -f compose.interop.yaml exec -T battery-interop \
  iris session IRIS -U BATTERY < interop/tests/proof-contracts.script
# Require all 149 PROOF_CHECK records to pass, without ObjectScript errors.
docker compose -f compose.interop.yaml exec -T battery-interop \
  iris session IRIS -U BATTERY < interop/tests/solver-live.script
# Billable: 8 scenarios × 3 repetitions. Retain all 24 records and native traces.
```

The live cases cover agreement, missing receipt, recovered receipt, wrong
partner, observed zero, wrong rule with good output, duplicate effects, and an
accurate rule with bad output. The recovered case must contain an actual probe
read and two review rounds. Repetition establishes only this corpus's observed
consistency; model judgments are scored separately from deterministic results.

## Measured final run

| Check | Result |
| --- | --- |
| Native receipt proof matrix | 149/149 |
| Native adversarial workflow faults | 27/27 |
| Final dispositions, eight scenarios × three repetitions | 24/24 |
| Recovered receipts with a probe and second review | 3/3 |
| Raw model assertion judgments, including follow-ups | 27/27 |
| Raw model output judgments, including follow-ups | 26/27 |

One raw answer called a wrong-partner receipt FAIL rather than UNKNOWN; the
scope check retained the correct UNKNOWN final outcome. No final false
agreement occurred in these 24 cases. This is the measured consistency of a
bounded receipt profile, not proof that the models or arbitrary workflows are
flawless.

The final live run took 239.719 seconds and made 45 model calls. SDK usage was
34,405 prompt tokens and 38,574 completion tokens, with 236.007 seconds of
summed model time. Billing has not been independently verified. Earlier
iterations are retained: one found a malformed investigator answer blocking
recovery; another exposed scenario names in model inputs; the neutral-ID run
then exposed insufficiently explicit scope and acceptance instructions. The
final run used neutral IDs, explicit predicates, and an evaluation clock.

The earlier raw boundary regression checks also remained green: 50 contract
checks and 26 fault/replay/restart checks. They test the unchanged internal
review component; their scope remains distinct from downstream action safety.
Full fixtures, source hashes, model inputs/outputs and native message traces
are in [the evidence report](results/solver-109.json).

## Remaining boundaries

External adapters must establish trustworthy source identity, timestamp
normalization, scope and completeness of receipt collections. Authentication,
external action execution, effect deduplication, distributed concurrency,
crash recovery and multi-probe investigation remain outside this increment.
The older broad corpus and its misses remain in `results/edge-109.json`.
The current evidence report is `results/solver-109.json`.

## Thirty-round repeatability audit

The frozen follow-up ran **30 serial rounds of eight scenarios**, using the
same production source and model settings throughout. Every requested case
completed. No failing case was retried or removed.

| Measurement | Result |
| --- | --- |
| Expected final dispositions | 230/240 (95.83%) |
| Unexpected review holds | 10 |
| Incorrect verified dispositions | 0 |
| Raw assertion judgments matching the oracle | 258/270 |
| Raw output judgments matching the oracle | 254/270 |
| Raw reviewer responses with valid evidence-ID lists | 260/270 |
| Raw reviewer JSON parse errors | 0 |
| Maximum review rounds / evidence reads per case | 2 / 3 |
| Case latency median / p95 / maximum | 10.005s / 16.912s / 30.846s |

The unexpected holds came from reviewer contract rejection, including citations
to `receipt-review` instead of supplied fact IDs. The validator prevented those
answers from being accepted, but the workflow lacked a bounded recovery route.
This is a completion-reliability defect. Raw model disagreements remain in the
report even when the deterministic gate corrected the final disposition.

Elapsed command time was 2354.815 seconds. SDK usage reports
438 model calls, 334,284 prompt tokens and
378,129 completion tokens. Actual billing has not been
reconciled. The previous 24/24 sample remains historical evidence; the longer
run does not support a claim of flawless operation.

These are repeated development scenarios with fresh synthetic timestamps, not
240 independent unseen workflows. External receipt authenticity, business
mutations, and concurrent production load were not tested by this run.

See the [complete repetition evidence](results/solver-repeat-109.json) for every
case, native trace, raw response, timing, source hash, and retained failure.
The [whole-system design audit](../docs/SYSTEM_DESIGN_AUDIT.md) specifies the
recovery and integration work. No production repair was applied during this
measurement or as part of the documentation audit.
