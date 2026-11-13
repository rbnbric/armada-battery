# Preserve each agent's input in an IRIS AI Hub trace

While preparing a Visual Trace example for Armada Battery, we found a problem
in our own message handling. A case could finish correctly while its earlier
trace entries pointed at request objects that had since changed.

Battery reviews the evidence around an operation receipt. An initial read may
find nothing; an investigator can request another read; a final check decides
what the observations establish. Each of those moments needs to remain
inspectable after the case finishes. Otherwise, someone investigating the first
answer sees information the agent did not have at the time.

## One session with several decisions

The native production has an intake service, a case process, a review process,
an AI Hub operation and an evidence operation. A reviewer examines the current
facts. When they do not settle the result, an investigator proposes a bounded
read. The process obtains the evidence and may ask the reviewer again.

These are request/response messages in one IRIS Interoperability session. An
`AgentRequest` records the role and input. An `AgentResponse` records the raw
answer and AI Hub usage counters. Evidence messages record the requested probe,
its observation and the bound receipt contract. The completed case retains the
intermediate reviews alongside the deterministic proof result.

Our [trace guide](https://github.com/rbnbric/armada-battery/blob/main/docs/TRACEABILITY.md)
maps those messages to the fields visible in Visual Trace and includes a command
for running one synthetic receipt scenario through real AI Hub inference.

## Reusing a request changed the history

The solver originally created one evidence request and changed its `Phase`
before each send. It also reused a review request when new evidence arrived.
That was convenient application code, but these were persisted messages. The
trace headers for several different steps referred to the same body ID.

The fix is small: construct a new message for each send and copy the fields
that belong to that step. The initial request stays `INITIAL`, the probe keeps
its own phase, and the final request says `FINAL`. Initial review and follow-up
review also retain different input snapshots.

For example, the final evidence read now starts with a new request:

```objectscript
Set er=##class(Battery.Interop.EvidenceRequest).%New()
Set er.CaseId=case.id,er.CaseJSON=pRequest.CaseJSON,er.Phase="FINAL"
Set sc=..SendRequestSync("Battery.Evidence",er,.fresh,10)
```

We added native checks that query the saved message bodies after the entire
workflow has completed. They require three distinct evidence bodies, the
original ordered probe phases, and separate review snapshots. A check that only
watched the outgoing arguments would have missed the persistence problem.

The [older recorded trace](https://github.com/rbnbric/armada-battery/blob/main/interop/results/trace-example-109.json)
still contains the old behavior. Keeping it makes the defect and the change
inspectable. This defect was in Battery's solver.

The [fresh 13 November trace](https://github.com/rbnbric/armada-battery/blob/main/interop/results/trace-example-20261113-109.json)
has 18 headers. Evidence requests 17, 25 and 31 retain their original phases;
review requests 19 and 27 hold different inputs. We read those saved bodies
after completion. The full native qualification passed 247 checks.

## Validate the evidence at the transport boundary

The same work added a native outbound adapter for management evidence reads.
Its destination and credential belong to the deployment. The model chooses
from admitted probe names; it cannot supply a destination URL. The adapter
checks the response status and size and does not retry a failed request.

The operation then calls an Embedded Python method inside IRIS. That method
rejects duplicate JSON members, malformed envelopes and non-finite numbers. It
compares the returned contract with the persisted binding, including JSON
types: `true`, `1` and `"1"` are not interchangeable. It also checks that the
tool result belongs to the requested phase and receipt attempt.

An accepted envelope still has to pass the existing observation checks. An
observation can be well-formed and belong to another target, be stale, or show
an unacceptable result. Those judgments remain separate from parsing.

The [native qualification report](https://github.com/rbnbric/armada-battery/blob/main/docs/BONUS_IMPLEMENTATION.md)
includes individual results and source hashes. Its tests use real loopback
HTTP and native queued operations. The validator runs inside IRIS; no model is
needed to test whether a duplicated JSON key is rejected.

## Reading the usage counters

The 13 November run made three model calls:

| Call | Prompt tokens | Completion tokens | SDK LLM duration |
| --- | ---: | ---: | ---: |
| Initial reviewer | 629 | 758 | 3,381 ms |
| Investigator | 765 | 701 | 5,424 ms |
| Follow-up reviewer | 745 | 789 | 4,204 ms |

Those counters measure usage for this run. The receipt scenario is synthetic; IRIS messaging and
inference were real. The model's initial evidence was incomplete, the evidence
read supplied an observation, and the final result was `VERIFIED_MATCH`.

There is an easy counter to misread here: AI Hub reported zero tool calls inside
those agent sessions. Battery's evidence calls occur as separate Interoperability
messages. Reading only the model counter would hide work that is visible in the
production trace.

## Using the trace with the case screen

The case screen begins with a sourced summary and the next decision for the
operator. Someone investigating a disagreement can expand the reviews and
observations, then inspect the corresponding native session. The original
attempt and earlier answers remain part of that account.

This implements the traceability use case in
[Community Idea DPI-I-689](https://ideas.intersystems.com/ideas/DPI-I-689).
It puts the model exchange next to the IRIS processes and evidence reads that
produced the decision. Source version still matters: the model selection and
system prompt are defined in code rather than copied into each saved message.

The recorded runtime is IRIS Community 2027.1.0AI build 109U. The EAP portal
offered that Community image on 13 November; the contest announcement still
named build 154. Our report names the actual tested version and leaves that
eligibility question for the organizers.

[Run the connected workflow](https://github.com/rbnbric/armada-battery/blob/main/docs/NATIVE_CASE_WORKFLOW.md)
or [watch the current interface walkthrough](https://rbnbric.github.io/armada-battery/video/).
