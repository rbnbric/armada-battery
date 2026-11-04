# Battery interoperability agent preview

Status: compiled and exercised on AI Hub Community build 109 through native
`%AI.Agent` and the IRIS Interoperability production. The existing Battery
management portal and its synthetic proof are separate. Native measurements
and remaining limits are recorded below; compilation alone is not acceptance.

The default production now includes a [receipt solver](RECEIPT_SOLVER.md):
small-agent review, larger-agent investigation, one executed read-only receipt
probe, bounded follow-up review, and deterministic checks of fresh scoped
outcome evidence. Raw model answers remain visible separately from the final
measurement disposition. Cases without an adapter-owned binding are held.
The current demonstration uses synthetic persisted receipts and real AI Hub
calls; it does not issue an external business effect or claim a repair.

Receipt qualification includes **149/149 proof checks and 27/27 workflow fault
checks**. The longer frozen live run produced **230/240 expected dispositions**
and **10 unexpected review holds**, with no incorrect verified disposition in
that fixed corpus. The earlier 24/24 run remains a smaller historical sample.
[Results and limitations](RECEIPT_SOLVER.md#thirty-round-repeatability-audit)
separate raw model accuracy, workflow completion, and deterministic containment.
The [system design audit](../docs/SYSTEM_DESIGN_AUDIT.md) records missing product
integration, operational limitations, and proposed acceptance tests.

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

For the current solver demonstration, compile the test fixture classes in a
disposable instance and run the native suite:

```objectscript
Do $SYSTEM.OBJ.LoadDir("/home/irisowner/dev/interop/tests", "ck", , 1)
Do ##class(Battery.Test.SolverSuite).Run(0,1)
// Real provider calls, eight cases, repeated three times:
Do ##class(Battery.Test.SolverSuite).Run(1,3)
```

See [the receipt contract and reproduction steps](RECEIPT_SOLVER.md) for the
exact states, evidence fields and test expectations. The older `Demo.Run`
free-form cases have no adapter binding and are now held by the default solver;
they cannot silently become verified outcomes.

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
  iris session IRIS -U BATTERY < interop/tests/edge-contracts.script
```

All 50 named checks must print `=1`, with no ObjectScript errors. They cover
the assertion/output split, fabricated evidence, invalid probes, malformed and
truncated JSON, wrong root types, renamed fields, invalid evidence containers,
type/size limits, duplicate citations, and a complete Markdown JSON fence. Only a complete outer fence is removed;
arbitrary prose is never searched for a convenient JSON fragment.

For the current receipt proof matrix and repeated native model run, follow
[the solver checks](RECEIPT_SOLVER.md#run-the-native-checks). Its report is
`results/solver-109.json`.

The older `edge-corpus.script` and `corpus.script` are historical raw-review
fixtures. To reproduce their original measurements, use public commit
`7a5b88e`; the new default production requires adapter-owned evidence. The
historical scripts and results are retained unchanged for comparison.

### Expanded build-109 gauntlet — 4 November 2026

After repairing five reproduced validator defects, native checks passed 50/50
contracts and 26/26 fault/replay/restart checks. The 32-case live corpus matched
31 assertion judgments, 28 output judgments, and 31 routes. Acceptable probes
matched 16/22 expected investigations (14 exact preferred choices). Two output
expectations are ambiguous and remain annotated in the frozen results.

One case incorrectly agreed without outcome evidence and skipped escalation.
Another confused unknown outcome with failure. Reordering facts preserved the
primary decision in four pairs but changed one applicability judgment. These
are remaining defects, not successful qualification. See [findings and next
priorities](GAUNTLET.md#measured-result--4-november-2026).

The run made 53 calls in 585.777 seconds; SDK usage was 24,835 prompt and 39,967
completion tokens. No billed-cost figure has been verified. Full inputs,
outputs, source hashes and native message traces are retained in the result.

### Historical first build-109 run — 4 November 2026

These scores describe `results/native-109.json` against its original oracle.
Reassessment found one incorrect expectation: an unobserved application state
was treated as a successful hold. The expanded gauntlet corrects that to
NO/UNKNOWN. The original 13/13 result is therefore **not a current correctness
claim**. It remains here as a record of what was measured and later challenged.

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
