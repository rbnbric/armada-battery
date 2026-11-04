# Battery interoperability agent preview

Status: compiled and exercised on AI Hub Community build 109 through native
`%AI.Agent` and the IRIS Interoperability production. The existing Battery
management portal and its synthetic proof are separate. Native measurements
and remaining limits are recorded below; compilation alone is not acceptance.

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
verify when reproducing the run. Retain both the response and message trace.

The AI Hub operation uses its documented `openai` provider with a custom
OpenAI-compatible Nebius Token Factory base URL. It reads `NEBIUS_API_KEY` only
inside IRIS. No provider credential enters a case message. The model IDs are
`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` and
`nvidia/nemotron-3-super-120b-a12b`.

The sample limits its container to two CPUs and 4 GB RAM. Its startup merge
sets the global buffer cache to 256 MB before the first IRIS start. This avoids
the almost 10 GB shared-memory allocation observed with the image defaults on
the qualification host. The bounded configuration allocated 743 MB of shared
memory; that is a startup observation, not a peak-memory benchmark.

## Native regression checks

With the production image running, execute the parser/validator checks first:

```bash
docker compose -f compose.interop.yaml exec -T battery-interop \
  iris session IRIS -U BATTERY < interop/tests/validators.script
```

All 17 named checks must print `=1`, with no ObjectScript errors. They cover
the assertion/output split, fabricated evidence, invalid probes, malformed and
truncated JSON, wrong root types, renamed fields, invalid evidence containers,
and a complete Markdown JSON fence. Only a complete outer fence is removed;
arbitrary prose is never searched for a convenient JSON fragment.

The following run makes billable provider calls through native AI Hub:

```bash
docker compose -f compose.interop.yaml exec -T battery-interop \
  iris session IRIS -U BATTERY < interop/tests/corpus.script
```

It prints one `NATIVE_CASE=` JSON record per fixture. Compare all 13 records
against `interop/tests/corpus-fixtures.json`, including the independent output
grade, expected route, and preferred investigation probe. The answer keys are
kept outside model inputs. A zero shell exit code alone does not establish a
pass: IRIS terminal sessions can print errors and still exit zero.

Native results are retained in `interop/results/native-109.json`. The tests use
synthetic evidence; they do not send real business effects or prove a complete
repair loop. See the remaining [edge gauntlet](GAUNTLET.md).

### Build 109 result — 4 November 2026

| Measurement | Result |
| --- | --- |
| Native parser and validator checks | 17/17 |
| Rule assertion judgments | 13/13 |
| Independent output grades | 13/13 |
| Expected review/escalation routes | 13/13 |
| Exact preferred investigation probes | 5/7 |

The final corpus made 20 native AI Hub model calls. The SDK reported 7,392
prompt tokens, 14,125 completion tokens, and 90.016 seconds of summed LLM time.
Reloading, validators, the corpus, and trace capture together took 93.321
seconds. These are one run's measurements, with no verified billing total.

Two probe choices remain visible misses. For schema drift the investigator
chose `CHECK_TARGET_VERSION` instead of the fixture's preferred `CHECK_MAPPING`;
that is a plausible alternative investigation. For injected instructions and
a delivery marked complete without a receipt, it chose `CHECK_RULE_SELECTION`
instead of `CHECK_EFFECT_RECEIPT`; receipt investigation should have priority.
Neither case authorized an external effect.

The initial run exposed renamed JSON fields and a Markdown fence that caused
a parsing exception. The repair tightened field instructions, normalized only
a complete outer fence, and preserved malformed responses as held outcomes.
An intermediate array type-check typo was caught by native tests and repaired.
The result file retains this history and per-case message traces rather than
presenting only a successful final score.

The upstream EAP image also logged a missing `SYS.ICM.Sharding` method during
startup. Compilation and the tested production worked despite that message;
the wider image startup is not being described as error-free.

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
preferred next probe in 5 of 7 cases. One miss chose a plausible rule-selection
probe for schema drift; the other chose a receipt probe although the evidence
already showed a partner-scope mismatch. The latter needs correction.
With a clarified probe instruction, a targeted recheck of that same case chose
`CHECK_PARTNER_SCOPE`; this is one case, not a new full-corpus score.
Those numbers use fixed synthetic evidence and direct provider calls, not
native AI Hub execution or a reliability estimate. The two-by-two cases
include a bad rule with a good output and a good rule with a bad output.

The existing Battery action gate is not wired into this preview. The next
iteration must add a durable case record, rule selection, deterministic gate,
and verified readback before any external effect is enabled. The full intended
contract is in `docs/INTEROP_AGENT_ARCHITECTURE.md`. The
[edge gauntlet](GAUNTLET.md) defines the next native qualification cases
and the effect-count evidence each one must retain.
