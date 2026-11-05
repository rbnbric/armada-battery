# Battery: next tests and one-step walkthrough

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

The UI/UX pass is deliberately waiting for the owner's new design codices.

## Work queue

| ID | Task | Completion evidence | Status |
| --- | --- | --- | --- |
| T1 | Reassess retained cases with the native rule checker | 48 native proof results for all 24 retained cases, exact snapshot binding, source/log hashes, scored report | Complete; evidence linked above |
| T2 | Execute an independent rules-only recovery baseline | Same fixture schedule, source access, read budget and final checks as the agent workflow; separate outcome/hold/latency/usage results | Specified; implementation follows T1 |
| T3 | Test cases that distinguish rule assertion from observed success | Frozen expected outcomes; all four YES/NO × PASS/FAIL combinations, UNKNOWN, context changes, stale and wrong-scope evidence, restart and malformed provider response | Existing cases inventoried; new independent cases pending |
| T4 | Walk through one real retained case with the owner | Person identifies source scope, initial answer, evidence read, final outcome and next action; record confusion verbatim | After runtime is available |
| T5 | Make the current workflow easy to find | Fresh visitor reaches current source/setup and distinguishes native workflow from old synthetic demo without guessing | Pending T4 findings |
| T6 | Apply new UX/UI codices | Design decisions cite supplied rules; desktop and phone journeys, keyboard/focus, readable history, error/recovery and scroll continuity checked | Waiting for codices; no redesign now |

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
