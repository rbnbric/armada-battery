# Battery UX refinement — delivery and evidence

Updated: 2026-11-06. All four product directions were approved. The existing Battery
logo now anchors a warm dark visual system, with readable type, shared spacing,
blue actions and labelled semantic states. The receipt and a plain-language account share the case view; supporting
history, optional explanation and technical records expand beneath each section.

## Delivered

- Cases is the first-visit home and opens the latest returned review directly.
  The explicit `#cases/all` route keeps search and browsing available. Explicit case/receipt links survive sign-in and
  browser reload. A later visit without a route remembers the last destination.
- List search and filters, stable loaded ordering, scope labels and plain statuses.
  The list is limited to up to 50 recent authorized reviews. The decision filter
  explicitly covers inspected cases; it does not claim to inspect every current
  target or count all outstanding decisions.
- Case/receipt navigation preserves the selected case, draft reason, selected
  option, expanded disclosures, scroll and focus within the signed-in page.
  Browser Back/Forward follows the same routes. Background refresh preserves
  input selection. New evidence retains the draft and asks for comparison.
- Human choices display their consequences and require an explicit selection,
  reason and Record decision action. Completed cases require no approval.
- Notices are cleared on a different route. Session expiry clears private case
  content and draft memory. A failed explanation leaves the factual summary usable.
- The header is compact on phones; working forms, menus and evidence reflow.
  Existing management, receipt, ledger and rule destinations remain accessible.

## Executed checks

| Check | Result | Scope |
| --- | --- | --- |
| Python suite | 126 public-checkout tests and both source-tree HTTP asset tests passed; earlier full source-tree qualification passed 128 tests | Engine/API/session/ledger regressions plus exact HTTP logo and asset routes |
| UI handler suite | 13 passed | Existing preparation, expiry, response loss and identity behaviors; recovery fixture updated to select its explicit case route |
| Chromium journeys | 177 passed; no browser exceptions | 320, 360, 390, 768, 1440px, 200% root text, keyboard, browser history, focus/selection/scroll, contrast, stale decisions, double click, expired identity, failed explanation, search, long/hostile data and shuffled navigation across 12 screens |
| Installed HTTP checks | 15 passed | Served source hashes, CSP, logo MIME, sign-in, retained case/brief/history and linked receipt |
| Installed/source comparison | 5 of 5 exact matches | app.py, HTML, CSS, JavaScript and logo |

[Browser assertions and hashes](audit/ux/report.json) ·
[Installed assertions and hashes](audit/ux/installed.json) ·
[Source-tree Python output](audit/ux/python.log) · [Public Python output](audit/ux/public-python.log) · [UI output](audit/ux/ui.log).

The browser journeys use the actual shipped UI with explicit synthetic API
fixtures. Installed checks ran separately against the existing Windows Docker
application, reading its retained case. This pass requested no model inference
and executed no management operation. The existing native integration evidence
remains in [Decision brief evidence](DECISION_BRIEF_EVIDENCE.md).

### Screenshots

These are actual Chromium renders of synthetic fixtures. The walkthrough banner
belongs to the fixture, not the installed service. The completed phone image
includes an intentionally failed explanation, demonstrating the usable fallback.

![Current task and explanation fallback on phone](audit/ux/complete-390.png)

![Context decision on desktop](audit/ux/decision-1440.png)

[Phone decision](audit/ux/decision-390.png) ·
[Desktop completed case](audit/ux/complete-1440.png).

## Findings retained during development

An initial handler check failed because its fixture had not selected the new
explicit case route. The fixture was corrected; all original recovery and
no-replay assertions remain. An early browser test used an ambiguous heading
selector; it now targets the summary heading. A selection check raced an
in-flight return navigation; its refresh stimulus is now applied atomically to
the active textarea. The final browser run passed all listed assertions.

Visual inspection showed that the first phone header delayed the task summary.
Connection controls were grouped into an expandable section. Input outlines were
strengthened and measured against the card surface. The logo needed its own
explicit HTTP route; both asset bytes and MIME were tested before delivery.

## Delivery

The five program files were updated in place in the existing Work folder and web
container. The web service restarted successfully; the native IRIS production
and data volumes were not replaced. Installed verification exited successfully
and all five source hashes matched the qualified source.

## Limits and next owner check

No human-comprehension improvement has yet been measured. This is not a full
WCAG conformance assessment or a screen-reader qualification. The 200% test
changes root text size; it does not substitute for every browser/OS zoom setting.
No new similar-case retrieval is claimed. The visible narrative translates
recorded review fields; it does not infer unrecorded events.

Case content, drafts and disclosure memory live only in the signed-in page;
refreshing the browser preserves the URL destination but not an unsent draft.
A fresh tab remembers the last section, not a private case ID. Session expiry
clears private drafts. Native list ordering stays stable while reading; newly
loaded cases append until a fresh page load.

**One owner task:** refresh Battery and select Cases. The retained review opens
directly. Read the receipt and What happened, then say whether you need to act.
Record any confusion before coaching. Then test another journey one at a time.

## Reproduce

```sh
python -m unittest discover -s tests -v
node --test tests/ui_state.test.js
# Separate browser environment with Playwright and Chromium installed:
python tests/browser_ux.py --out ./ux-evidence
# Inside the running battery-web container, with its existing environment:
python interop/tests/verify-ux.py
```

## Receipt and explanation follow-up — 2026-11-06

The receipt is now visible beside **What happened** on desktop and above it on
phones. The account progresses through the initial review, evidence check and
recorded conclusion, followed by the current task or human decision. Each step
has its supporting detail underneath. Opening Cases reads the latest listed
review without requiring a card click; Back to cases opens the searchable list.

The operation receipt is fetched independently and checked against both the
review's receipt ID and target. Its outcome stays distinct from the review's
conclusion. A failed fetch or mismatched receipt shows an explicit gap and cannot
reuse a previously displayed success. Missing review steps are labelled as
unrecorded. Rendering this view starts no model or management operation.

The 177 browser assertions include direct landing, desktop/phone reading order,
closed detail panels, failed/mismatched receipt responses, uncertain operation
outcomes alongside a matching review, list reload and missing-route recovery.
The existing draft, session, navigation, accessibility and explanation-failure
checks remain. The 13 handler checks and two HTTP asset checks also passed.

JavaScript and CSS were delivered in place for this follow-up. Work mode
briefly disconnected after the file transfers, before command execution. Once
it reconnected, the Docker update completed with exit code 0. All 15 installed
HTTP checks passed and all five served/installed source hashes matched the
qualified source and public checkout. The retained application, IRIS production
and data were reused.
