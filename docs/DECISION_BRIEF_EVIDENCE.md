# Decision brief and native explainer — 2026-11-05

## Delivered behavior

Agent Cases now puts an evidence-bound plain-language brief before expandable
technical records. A completed review has no approval buttons. A changed target
shows the retained/current difference and asks whether the later change was
intentional. Technical recovery, missing evidence, ongoing work, superseded
reviews and context decisions have distinct summaries and available actions.

The backend builds the brief from the scoped operation receipt, retained native
result and a current adapter read. Each answer carries an evidence revision;
the server re-reads before accepting it. Operator answers and reasons are durable
ledger events. A repeated answer is idempotent. A request for more evidence starts
one new review revision with the same operation receipt. It does not execute the
business operation again. A corrective intention is recorded and links to target
inspection; the existing prepare/authorize/execute workflow remains necessary.

The optional **Explain this evidence** button calls a third role in the native
IRIS AI Hub operation. It receives a bounded server-built report and returns three
plain-language fields plus evidence references. Scope, state and actions remain
application-owned. The result is cached by operator, case and evidence revision;
late responses cannot be attached to a changed brief. Its full response, usage
and native response ID are retained. An acknowledged failure permits one explicit
retry; an unconfirmed request is not automatically replayed. Native explanation
admissions are bounded to 20 per operator and 100 per service per day.

## Executed evidence

[Machine-readable report](../interop/results/decision-brief-109.json)
contains the installed result, exact source hashes, browser measurements, first
failure and final successful native run.

| Check | Result | What it establishes |
| --- | --- | --- |
| Python suite | 126 passed, including 24 new decision tests | Real engine/ledger and HTTP boundaries; independent assertion/output pairs, stale decisions, duplicate clicks, operator isolation, session expiry, parent revisions, explanation fallback/cache/retry |
| Existing UI handler regressions | 13 passed | Existing preparation, expiry, late response, identity and review-admission behavior |
| Chromium browser assertions | 22 passed over 5 views | 360px, 768px, 1440px and 200% root text; no horizontal overflow, brief visible, technical detail collapsed; mobile choice submission and explainer failure fallback |
| Installed service checks | 16 passed | Real native AI Hub response; scope preserved, cached repeat, stale/invalid decisions rejected, foreign operator hidden, original case result and operation receipts unchanged |
| Native compilation | 6 changed classes compiled | Runtime accepts the changed operation, API, intake, response, record and solver classes |
| Installed application hashes | 5/5 matched | Installed app, bridge, brief builder, JavaScript and CSS equal the qualified source |

[Python log](../interop/results/decision-brief-python.log) ·
[UI regression log](../interop/results/decision-brief-ui.log)

### Failure retained and repaired

The first installed explanation attempt failed: IRIS was reachable but its
interoperability production was **Troubled** after an unclean shutdown. A queued
request produced no response. The structured brief remained available. With no
active case reviews, the documented
[RecoverProduction/StartProduction lifecycle](https://irisdocs.intersystems.com/irisforhealthlatest/csp/docbook/DocBook.UI.Page.cls?KEY=EGDV_adv)
restored the running production. The API now checks production readiness before
admitting an explanation. The failed attempt remains in the report and ledger.
An explicit retry succeeded, followed by qualification of the final plain-language
prompt and brief schema. A 4px overflow in the 200% text check was fixed and retested.

### Screenshots

These are real Chromium renders of the application with explicitly synthetic
brief fixtures, not screenshots of live IRIS inference.

![Completed review at phone width](audit/decision-brief/complete-phone.png)

![Human decision controls at phone width](audit/decision-brief/decision-phone.png)

![Context decision at desktop width](audit/decision-brief/decision-desktop.png)

## Limits and next human check

The real model check covers one retained synthetic operation. Contract and citation
validation do not establish semantic correctness across arbitrary cases. No
human-comprehension improvement or decision-quality advantage has been measured.
Similar-case retrieval, arbitrary evidence probes, automatic corrections, broad
lifecycle explanations, and the codex-led visual redesign remain future work.
The current explainer covers the selected final/current evidence summary; the
coverage boundary is included in its input.

**Owner check:** refresh the installed application, open Agent Cases and the
retained case, then read only the new brief. Without opening technical details,
say what happened and whether you need to do anything next. Record confusion
before providing coaching.

## Reproduce

```sh
python -m unittest discover -s tests -v
node --test tests/ui_state.test.js
# Inside the configured, running battery-web container:
python interop/tests/verify-decision-brief.py
```

The installed verification script requires an existing completed synthetic case
and configured native service. It explicitly requests an explanation (or returns
its cached result) and exercises rejection paths; it submits no business action.
