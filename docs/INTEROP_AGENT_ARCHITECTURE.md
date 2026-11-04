# Interoperability agent: binary review and edge investigation

Status: design plus an uncompiled IRIS production source preview for the AI
Agents in Interoperability Workflows contest. This is not a claim of AI Hub
runtime qualification.

## Purpose

Turn an interoperability incident into an inspectable resolution attempt. A
rules engine proposes the expected result. A small agent reviews that result
with a binary answer on its assertion. Separately, it grades the observed
output against an independent acceptance criterion. If either disagrees, it
sends the case to a larger agent to find out why. A separate deterministic gate decides whether any proposed action
can run.

"Total solver" is a coverage objective: every case receives a disposition,
including **needs evidence**, **needs a person**, and **unknown**. It is not a
claim that every incident can be repaired automatically.

## One case record

Both layers read the same durable case record. It contains the source message
and correlation identifiers; source and destination; the intended effect;
schema and partner-contract versions; delivery attempts and acknowledgements;
observations with source, capture time and expiry; candidate actions; and an
append-only decision history. The record distinguishes **not observed** from
**observed absent**. Secret values and unnecessary message contents are not
agent evidence.

## Rules engine: the expected answer

Each rule declares its applicability predicates, required evidence, expected
result, counterexamples, candidate action, and verification read. Evaluate all
applicable rules against a bounded snapshot; do not stop at the first
attractive match. Rules produce candidates, not permission to act. Examples:

| Case | Required evidence | Rule's expected result |
| --- | --- | --- |
| Missing required field | Schema version and original field set | Reject with precise field error; never invent a value |
| Known field alias | Versioned partner mapping and replay against target schema | Propose mapped copy |
| Transient 429/503 before dispatch | Response and confirmed absence of downstream effect | Schedule a bounded retry |
| Endpoint unavailable | Health and last delivery state | Hold; retry only when the delivery boundary is known |
| Duplicate input | Stable partner key and prior effect receipt | Return prior outcome; no new effect |
| Delivery response lost | Attempt record and correlated downstream readback | Reconcile or hold as unknown; never infer failure from silence |

The rules engine records every matched and defeated rule. Conflicting rules
remain visible to both agents.

## Layer 1: small binary reviewer (greedy)

The first native IRIS AI Hub agent records two primary findings: **Was the
selected rule's assertion accurate for this case?** (`YES`/`NO`) and **Did the
observed output satisfy an independent acceptance criterion?**
(`PASS`/`FAIL`/`UNKNOWN`). Applicability is retained as context. A rule can be
inapplicable and predict a different result while the actual output passes.
Agreement with a rule does not approve a send or declare the case resolved.
Missing output evidence is `UNKNOWN`, never an invented pass.

Keep all four known combinations in qualification: accurate assertion with
passing output, inaccurate assertion with passing output, accurate assertion
with failing output, and inaccurate assertion with failing output. `UNKNOWN`
is a fifth held condition when the output cannot yet be observed.

When either primary finding is negative or unknown,
the reviewer writes a compact handoff: expected result, observed result,
support for the rule, contradiction, missing evidence, and related trace IDs.
That is the **talk to the big man** path. An inapplicable rule and a conflicting
prediction can coexist; rule selection is one possible investigation probe.
A malformed or timed-out review is held visibly rather
than counted as `YES` or `NO`.

## Layer 2: larger investigator (clever)

Invoke the larger native IRIS AI Hub agent for the contradiction handoff,
conflicting rules, incidents spanning messages or contracts, or cases with no
rule candidate. It has read-only tools to inspect the case,
related message traces, partner contract, runbook, recent incidents, and
qualification results. It may pursue a limited number of tangents: for each
one it records a hypothesis, supporting evidence, contradicting evidence, and
the next observation that would decide it. It may request more evidence or
recommend an allow-listed action or a candidate rule amendment. It cannot
send, replay, edit a contract, confirm its own proposal, or manufacture a
missing acknowledgement.

The agent returns a versioned structured decision: case ID, action, target,
evidence references, contradictions, uncertainty, and a concise explanation.
Invalid output, timeout, tool error, or budget exhaustion becomes a visible
**needs review** result. It is not silently recast as a successful rule match.

## Final action gate

The gate is shared by both agent paths. Before any external effect, it re-reads the
target and verifies that the case and partner contract have not changed. It
checks evidence freshness, action allow-list, authorization, delivery boundary,
idempotency key, and whether a prior effect or attempt already exists. It
records a single-use permit and the attempt before dispatch. An ambiguous
transport outcome remains **unknown** until correlated readback establishes
the result; it never grants an automatic second send. Risky mapping or contract
changes require human confirmation and a replay against synthetic fixtures.

Every result has one of these states: `RESOLVED_VERIFIED`, `HELD_FOR_EVIDENCE`,
`HELD_FOR_REVIEW`, `REFUSED`, or `OUTCOME_UNKNOWN`. The UI shows which layer
proposed the action and which gate check accepted or refused it.

## Agent runtime and operator experience

The ordinary path runs the rules engine and one bounded binary review; the
larger investigation is reserved for disagreement and edge cases. Both agent
steps are durable and resumable: receiving the same event again joins the
existing case instead of starting another agent turn. A case version and
evidence fingerprint bind each answer to what it actually saw. If new evidence
arrives while an agent is reasoning, validate against the new state and re-run
only the necessary observation step; never apply a stale answer.

Give the agent a finite tool-call budget, wall-clock deadline, and token cap.
Read-only tools return bounded, source-labeled observations. A provider failure
opens a circuit for that provider while the rules engine can still record its
candidate; the case is held without a reviewer confirmation and remains visible
with its exact reason and a manual resume action. An AI
retry is permitted only for the reasoning call, never as a disguised retry of
an external business effect. A restart resumes from the recorded step rather
than replaying completed effects.

The operator first sees one sentence: what happened, what the system proposes,
and whether anything has already been sent. Expand to see the rule prediction,
binary review, investigator's hypotheses, contradictions, source messages,
freshness, and final gate
checks. Pending cases show the next useful observation or human decision.
The UI must distinguish **working**, **waiting for provider**, **waiting for
evidence**, **waiting for person**, and **outcome unknown**. It should never
display a spinner that hides an uncertain delivery state.

Track small-reviewer calls, investigator escalation rate, time to disposition,
provider errors, case resumptions, human overrides, false recommendations,
and external effect count. Publish measured values from an actual run only;
the target is a fast binary common path and a bounded, explainable investigation.

## Required IRIS proof

Build a real production: inbound Business Service -> Business Process ->
rules engine -> small AI Hub reviewer -> larger AI Hub investigator when needed -> action gate ->
outbound Business Operation and receipt. The AI Hub call must run on a contest
accepted EAP image. InterSystems initially named build 154 and on November 4
also accepted the newer build 109; record the exact tested build. A replay
fixture is only an optional no-key demonstration mode and must be labeled as
such.

The minimum demonstration has three cases:

1. A known field alias has a matching observation; the small reviewer returns
   `YES`, the larger investigator is not called, and the gate verifies the output.
2. A rule remains applicable but its expected result disagrees with the
   observation; the small reviewer returns `NO` with a contradiction packet.
   The larger agent inspects a related trace and recommends an evidence request
   or bounded action.
3. A downstream send succeeds but its response disappears; a second send is
   refused, and later correlated readback reconciles the original attempt.

Qualify at least: missing field, unknown alias, version drift, duplicate input,
late acknowledgement, stale evidence, concurrent target change, conflicting
rules, prompt injection in a message, malformed agent output, model timeout,
and a downstream response lost after effect. For each, retain the IRIS message
trace, decision record, gate result, and observed downstream effect count.

## Build order

1. Acquire and boot a contest accepted AI Hub Community image. Prove one native
   agent call inside a minimal IRIS interoperability production.
2. Implement the case record, rules engine, and gate with synthetic partner
   messages. Prove each rule's evidence and counterexample.
3. Add the small AI Hub binary reviewer, then the larger agent's bounded tools
   and structured decision validation. Prove a contradiction handoff and a
   recommendation without letting either agent own the action.
4. Run the three end-to-end cases on IRIS, publish exact setup steps and
   evidence, then make the reviewer path short and repeatable.

This extends Battery's single-dispatch and readback principles. It does not
convert Battery's earlier synthetic admin demonstration into evidence that the
new interoperability production works.
