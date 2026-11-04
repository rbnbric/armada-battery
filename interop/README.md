# Battery interoperability agent preview

Status: source prepared for the AI Agents in Interoperability Workflows contest.
The classes have **not yet been compiled or run on an AI Hub EAP image**. The
existing Battery management portal and its synthetic proof are separate.

This small IRIS production accepts a bounded evidence case through
`Battery.Intake`, routes it through `Battery.CaseProcess`, and calls native
`%AI.Agent` from `Battery.Agent`. Nemotron 3 Nano checks two separate facts:
whether the rule assertion is accurate and whether the observed output meets
an independent acceptance criterion. A false assertion or a failed/unknown
output sends the case to Nemotron 3 Super to choose the next evidence probe. The process
validates each model's JSON shape and evidence IDs. Its states are review
states; **it sends no external business effect and does not claim a repair**.

## Run on the contest AI Hub image

The [contest announcement](https://community.intersystems.com/post/intersystems-programming-contest-ai-agents-interoperability-workflows)
now accepts build 109 as well as the earlier build 154. Download the Community
image for your architecture from the [AI Hub EAP portal](https://evaluation.intersystems.com/Eval/early-access/AIHub)
using your InterSystems account. The EAP image is not included in this repository.

```bash
docker image load -i /path/to/iris-community-2027.1.0AI.109.0-docker.tar.gz
docker images
docker tag <loaded-image-name> iris-community:2027.1.0AI.109.0
export NEBIUS_API_KEY='<your Token Factory key>'
docker compose -f compose.interop.yaml up --build -d
docker compose -f compose.interop.yaml exec battery-interop iris session IRIS -U BATTERY
```

In the IRIS terminal:

```objectscript
Do ##class(Battery.Interop.Demo).Start()
Do ##class(Battery.Interop.Demo).Run("match")
Do ##class(Battery.Interop.Demo).Run("drift")
Do ##class(Battery.Interop.Demo).Run("wrongrule")
Do ##class(Battery.Interop.Demo).Run("badoutput")
```

The first case should return `AGREED_PENDING_GATE` with one reviewer call. The
second should return `INVESTIGATION_PENDING_GATE` with a reviewer `NO` and an
investigator probe. The third and fourth cases show an inaccurate rule with a
passing output, and an accurate rule with a failing output. Both should reach
investigation. Check the IRIS Interoperability Message Viewer for the
Service → Process → Agent Operation trace and compare the printed response
with its messages. If provider setup or model output fails, the case is held
for review and no external effect is sent. These are expected outcomes to
verify on the actual image, not results already measured.

The AI Hub operation uses its documented `openai` provider with a custom
OpenAI-compatible Nebius Token Factory base URL. It reads `NEBIUS_API_KEY` only
inside IRIS. No provider credential enters a case message. The model IDs are
`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` and
`nvidia/nemotron-3-super-120b-a12b`.

## Direct model baseline

`scripts/eval_interop_agents.py` runs fixed synthetic cases against Token
Factory directly. It checks output shape, evidence references, binary verdicts,
and investigator probes. It does **not** qualify the native IRIS agent or
production. Run `python3 scripts/eval_interop_agents.py` to see the case count,
then `NEBIUS_API_KEY=... python3 scripts/eval_interop_agents.py --live --output
eval.json` for billable calls. Keep that receipt private if it contains
provider metadata you do not want to publish.

An initial 12-case direct-model run of the separate assertion/output contract
returned 10/12 correct assertion judgments, 11/12 correct output grades, and
4/6 exact investigator probes. That is a failure-finding baseline, not an
acceptance result. It exposed partner-scope confusion and a case where the
model graded output from the rule's prediction instead of the independent
criterion. The revised 13-case direct-model run correctly classified all 13
assertion judgments and all 13 output grades. The investigator selected the
preferred next probe in 5 of 7 cases; two alternate probes remain for review.
Those numbers use fixed synthetic evidence and direct provider calls, not
native AI Hub execution or a reliability estimate. The two-by-two cases
include a bad rule with a good output and a good rule with a bad output.

The existing Battery action gate is not wired into this preview. The next
iteration must add a durable case record, rule selection, deterministic gate,
and verified readback before any external effect is enabled. The full intended
contract is in `docs/INTEROP_AGENT_ARCHITECTURE.md`. The
[edge gauntlet](GAUNTLET.md) defines the next native qualification cases
and the effect-count evidence each one must retain.
