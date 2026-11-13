# Following Battery agent calls in IRIS Visual Trace

Battery implements [DPI-I-689, using InterSystems Interoperability to trace GenAI
pipelines](https://ideas.intersystems.com/ideas/DPI-I-689). Agent calls and evidence
reads are native request/response messages in the case's Interoperability
session. The saved message bodies expose the supplied evidence, role, model
response and AI Hub usage counters.

## What to inspect

| Message or record | What it establishes |
| --- | --- |
| `CaseRequest` to `Battery.CaseProcess` | Original case and its requested judgment. |
| `EvidenceRequest` and `EvidenceResponse` | Requested phase, bound contract, observation, tool result and rejection reason. Each phase has its own saved request body. |
| `AgentRequest` to `Battery.Agent` | Reviewer or investigator role, evidence input and any bounded response-repair envelope. |
| `AgentResponse` | Raw model output and AI Hub `UsageJSON`, including prompt/completion token counts and SDK-reported LLM duration. |
| `CaseResponse` | Review history, rejected responses, executed probes and deterministic proof result. |
| `Ens.MessageHeader` | Session, source/target production items, body class, body ID and message status. |

The selected model, provider endpoint and system prompt are defined in
[AgentOperation.cls](../interop/Battery/Interop/AgentOperation.cls). This revision
does not copy the system prompt or its version into every message; preserve the
source revision beside an exported trace. API keys remain in the IRIS process
environment and are not message properties.

AI Hub's `total_tool_calls` describes tools inside that AI Hub session. Battery
dispatches evidence tools through separate Interoperability messages, so zero
in that counter does not mean the production performed no evidence reads.
Token counts are measured usage, not a currency cost or billing receipt.

## Current recorded example

The [13 November run](../interop/results/trace-example-20261113-109.json)
contains 18 native message headers and three real model calls. It reached
`VERIFIED_MATCH` using a synthetic receipt fixture. Saved evidence request IDs
17, 25 and 31 retain `INITIAL`, `CHECK_EFFECT_RECEIPT` and `FINAL`; review request
IDs 19 and 27 retain different evidence snapshots. The exported bodies were
read after the case finished.

| Call | Prompt tokens | Completion tokens | SDK LLM duration |
| --- | ---: | ---: | ---: |
| Initial reviewer | 629 | 758 | 3,381 ms |
| Investigator | 765 | 701 | 5,424 ms |
| Follow-up reviewer | 745 | 789 | 4,204 ms |

The case is `solver4-live-recovered-5865449989`, session 21 in the isolated test
container. Those IDs identify this run; a fresh installation will assign its
own IDs. The export includes the implementation hashes for the tested source.

## Historical example

The [retained 4 November example](../interop/results/trace-example-109.json)
contains a real native AI Hub run against a synthetic receipt fixture. Session
3188 contains 18 message headers and three agent calls: reviewer, investigator,
reviewer. The adapter initially reports missing evidence; a subsequent read
finds the receipt and the case reaches `VERIFIED_MATCH`.

| Call | Prompt tokens | Completion tokens | SDK LLM duration |
| --- | ---: | ---: | ---: |
| Initial reviewer | 629 | 1,057 | 5,530 ms |
| Investigator | 756 | 940 | 5,401 ms |
| Follow-up reviewer | 745 | 777 | 4,260 ms |

This historical export also preserves the old request-body reuse defect. The
current solver assigns separate bodies to each read and review round; native
regression checks verify the original phases and snapshots after completion.
The historical record has not been rewritten to resemble the fixed behavior.

## Run a fresh example

Start the connected installation using [the native workflow guide](NATIVE_CASE_WORKFLOW.md).
It needs a separately obtained AI Hub image and configured model access. Run:

```sh
docker compose -f compose.interop.yaml exec -T battery-interop iris session IRIS < interop/tests/trace-example.script
```

On Windows, run that redirected command in CMD. It submits one uniquely named
synthetic receipt scenario through the running production. It makes real model
calls, normally reviewer–investigator–reviewer, with the existing bounded repair
and review limits. The fixture changes no management target.

The output contains the case result, `VISUAL_TRACE_SESSION`, and the saved
headers. In the IRIS Management Portal, select namespace **BATTERY**, open the
production's message viewer and find that session ID. Open **Visual Trace**.
Select the messages to inspect their bodies:

1. The initial evidence request says `INITIAL`; its response reports unavailable evidence.
2. The first reviewer and investigator show the evidence they were actually given.
3. The evidence probe records `CHECK_EFFECT_RECEIPT` and its observation.
4. Follow-up review has a separate case snapshot containing that observation.
5. The final read and deterministic proof appear before the completed response.

Refresh the trace after the case finishes and confirm the earlier request
phases still show their original values. The regression suite checks the same
property by querying saved native messages.

To export saved request bodies, replace `21` below with the printed session ID:

```sh
docker compose -f compose.interop.yaml exec -T -e BATTERY_TRACE_SESSION=21 battery-interop iris session IRIS < interop/tests/trace-inspect.script
```

This reads the existing messages and makes no model call. Its output must show
`TRACE_INSPECTION_FINISHED` and a nonzero `TRACE_BODY_COUNT`, with no native
error. Review the bodies before sharing a trace from a real operation; the
provided example contains synthetic case data.

## Relationship to an LLM observability service

[Langfuse](https://langfuse.com/docs) provides LLM application traces and evaluations. Battery's
implementation keeps the model exchange beside the IRIS service, process and
evidence messages that produced the business decision. A person investigating
one receipt can follow that sequence within the existing Interoperability
session. Battery does not provide a general prompt-management product, a
cross-application evaluation service, or currency-cost analytics.

The [organizer's clarification](https://community.intersystems.com/post/technology-bonuses-intersystems-programming-contest-ai-agents-interoperability-workflows)
accepts Interoperability tracing for DPI-I-689 without requiring Vector Search.
The idea must also be entered in the dedicated Ideas field on Open Exchange.
