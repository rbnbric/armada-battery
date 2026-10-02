# Correctness and UI implementation status

Updated 2026-09-26. This records implementation and validation scope; it is not
live-mutation qualification or a contest-result prediction.

## Design reconciliation

The coordinated Robin-4 Codex / Robin-3 Claude UI/UX specification is the design
direction for this pass. Correctness findings take precedence over visual state.

- P0: any intent change, failed preparation, expired certificate, or late response
  invalidates eligibility. Execution failures do not imply success. Lost browser
  responses retain an execution key for receipt lookup; unknown receipts offer
  read-only reconciliation, never automatic redispatch.
- P0: authority mode is independent of synthetic/live context. Evidence quality
  has explicit word/glyph/color mappings. Missing, future-dated and aged evidence
  is unknown, conflicted or stale; it cannot retain success styling. The freshness
  threshold is 60 seconds, visible as policy rather than claimed source cadence.
- P0: an empty ledger says there is nothing to verify. Populated ledgers show count,
  full/copyable digests and retained event timestamps. Receipts show the actual
  fields, before/after observation IDs, sanitized observations and ledger links.
- P1: compact status bar and management navigation replace the hero. Requests live
  in a separate workspace with the four-stage lifecycle and unequal finding/action
  columns. Inventory, receipts, evidence and rule views have explicit empty and
  unavailable states. Observation failures do not disable unrelated areas.
- P1: neutral graphite palette, semantic state colors, visible keyboard focus,
  native 16px checkboxes, one status region and one alert region. At 390px,
  navigation collapses and overview details start closed; tables become records.
- P2 stays deferred: charge/coverage computations, a general condition/finding queue,
  scheduled assurance obligations, impact-scaled confirmation, alternatives,
  sanitized packet export, REST exploration and subsystem-log management. No
  score, graph, coverage percentage, or live metric is invented for this pass.

The 2026-10-02 reviewer follow-up adds one synthetic demonstration finding:
absence of a result for the bundled on-demand task. It opens the existing guarded
request and resolves only against a verified Battery receipt. A failed or
unattributed attempt remains for review. Live mode reports this finding as
unavailable; it is not a live condition engine or general queue.

A configured preflight result is not a claim that every prerequisite has been
independently proven. Missing impact classification and automated rollback are
stated. The console displays the available rule assumptions and counterexamples.
Synthetic fixture values are labeled by adapter context.

## Engine corrections

Task configuration and runtime status are collected separately. Run-now supplies
an explicit request body. The event store fsyncs records before dispatch, restores
receipts/plans/key bindings, and locks local thread/process execution. It fails
closed on broken integrity or storage failure. A crash cannot authorize replay.

Readback failure is separate from mutation failure. Task status matching uses
explicit known results; unknown prior outcomes block a new run. Live v1 history
lacks an attempt identifier, so new rows cannot by themselves prove this request's
success. Synthetic isolation is stated in the receipt. Configuration verification
proves the requested fields, not downstream functional behavior.

Raw certificate tokens and recognized secret fields are not written to new audit
records. Upstream error bodies are withheld. Collector responses are capped at
2 MiB; response completeness is not implied by a successful HTTP response.

Live mutation mode requires a strong Battery access key. The session is an
explicit single-operator boundary, with the backend IRIS authority shown separately.
This does not implement multi-user permissions or prove least-privilege deployment.

## Validation performed

- 48 pytest cases (47 unittest cases plus the sandbox-verifier meta-test) passed,
  including concurrent thread/process submissions,
  restart-after-dispatch, failed readback, secret canaries and API access controls.
- Four Node tests exercise the shipped handlers: input invalidation, late replies,
  expiry/quality classification and lost response without automatic mutation retry.
- The offline tank sandbox full profile passed 39 core tests and eight scenarios
  (run `cb6113bc94d86dee`); it excludes FastAPI and browser integration. Later
  changes to collector limits and documentation are additionally checked locally.
- Courier rendered the actual HTML/CSS/JS with synthetic API fixtures at 1440px
  and 390px. No browser errors or horizontal overflow were observed. The browser
  interaction check confirms task edits and failed preparation disable execution;
  checkbox width is 16px and there is one status region.
- The screenshots are synthetic fixture renders. They do not certify the deployed
  service or a freshly rebuilt application image. Live IRIS mutation qualification,
  keyboard/screen-reader user testing and a complete deployment smoke remain gates.
  Body and state token contrast was calculated at a minimum 6.12:1 on all three
  console surfaces; full assistive-technology qualification is not implied.

The container verifier now includes an unreviewed task preparation. It performs
no IRIS mutation and must not be described as live change qualification.

## Reproduce

```sh
python3 -m unittest discover -s tests -v
node --test tests/ui_state.test.js
python3 scripts/run_scenarios.py
python3 scripts/verify_container.py  # running read-only Compose stack required
```

On the internal fleet, the optional credential-free engine sandbox is:

```sh
devlathe run venture_sandbox --venture armada-battery --profile full
```

Independent replicas/network filesystems, automatic ledger repair, per-rule
validation-artifact enforcement, and effective inherited-access calculation remain
unsupported. The README describes the supported local persistent-store boundary.
