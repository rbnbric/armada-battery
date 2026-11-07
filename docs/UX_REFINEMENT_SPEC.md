# Battery UX refinement: understand, decide, continue

Status: approved by Robin, 2026-11-05; visual direction revised by Robin, 2026-11-07. See [UX evidence](UX_REFINEMENT_EVIDENCE.md).
Routine design and engineering decisions are delegated. This document records the agreed direction; the evidence report identifies delivered behavior and remaining limits.

## Outcome

A person opening a case should be able to explain what happened, whether it
involved a simulated or connected operation, what remains unknown, and what to
do next without decoding record IDs or raw JSON. Human attention belongs where
intent, context or competing outcomes change the decision. Settled results need
a clear conclusion; technical failures need a recovery route.

## Baseline and evidence

The structured brief, native Explainer, evidence-bound decisions and follow-up
reviews already exist. Their executed checks and limits are in
[Decision brief evidence](DECISION_BRIEF_EVIDENCE.md). That qualification does
not establish improved human comprehension.

The owner walkthrough recorded destination loss through sign-in, disclosure
state loss on case/receipt return, an unscoped success message following navigation,
and difficulty understanding the record-heavy presentation. See
[Next tests](NEXT_TESTS.md). Those are concrete starting defects. Older system
audit findings must be reconciled with current source before becoming new work.

## Four approved choices

| ID | Recommended choice | Alternative and tradeoff |
| --- | --- | --- |
| A | Make **Cases** the first-visit home, with a visible Needs your decision filter and all cases available. Restore the last valid location on later visits; explicit links always win. | Keep Overview as first-visit home; preserves the administration emphasis but adds a step to review work. |
| B | Use **Summary → What happened → Technical evidence** within one case. Summary is the default; remember opened detail per case within the signed-in session. | Start with expanded technical detail; faster for regular auditors, heavier reading for everyone else. |
| C | Use a warm paper-and-graphite identity drawn from the black-and-gold Battery mark: clear reading surfaces, an editorial case heading, restrained teal actions and semantic status colors. | The initial dark treatment was functional but felt drab and generic; Robin requested a more distinct, welcoming direction on 2026-11-07. |
| D | Present a focused human decision only when context is unresolved. Put the question, material difference, known facts, unknowns and available choices together. | Use an always-present decision form; consistent placement but creates unnecessary prompts on settled cases. |

Approval selects these product directions. Detailed spacing, copy, components,
responsive behavior, accessibility and test implementation are delegated.
The initial four directions were approved. The visual choice above records Robin's
later correction; routine details remain delegated.

## Screen structure

### Global shell

One compact header shows Battery, the active installation and operation scope.
Use explicit labels such as **Simulated operation** and **Connected IRIS**;
show actual read-only or action capability separately. Native AI inference on a
synthetic receipt must not imply a real management change.

Navigation groups:

- **Cases:** review list and selected case.
- **Manage:** existing Tasks, Web applications, Permissions, Security, Operating
  system and Logs & audit destinations.
- **Evidence:** Receipts, Evidence ledger and Rules.
- **Overview:** retained operational summary and demonstration entry.

Existing destinations remain reachable. A destination with no working feature,
such as the currently labelled unimplemented REST API page, belongs in a clearly
marked capability explanation rather than posing as an available workflow.
No UI relabeling promises newly implemented adapter functionality.

Use a compact header with Cases, Overview and New request immediately available;
put records and settings in one labelled menu. Center the working canvas on
ultrawide screens. The selected case is a three-stage journey with visible
desktop arrows and optional phone swipes; every stage remains reachable without
gestures. Text paragraphs
stay within roughly 60–75 characters per line; comparisons may use wider space.
On phones, use one full-width working view, a labelled menu, and a visible Back
to cases action. Browser Back and Forward work. No mandatory swipe gestures or
nested whole-page scroll areas. Tablet chooses layout by fit, not device name.

### Case list

Rows/cards show a recognizable target name, plain-language status, scope,
updated time, and the reason attention is needed. Short IDs are secondary.
Provide All, Needs your decision, In progress and Finished filters, plus search
by target or case ID. Technical recovery and missing evidence remain distinct
from human context decisions. Counts cover the authorized loaded dataset;
partial results say so. Do not imply a global count from one page.

Default order is stable and explained. New events show an update indicator;
they do not shuffle a focused row. An empty filter offers a clear return to All.
Loading, empty, denied, stale and failed loading states each explain a useful
next action without inventing case outcomes.

### Case detail

The first section shows:

1. Target, scope and understandable status.
2. What happened: one or two evidence-supported sentences.
3. What needs attention now, or **No decision needed for this review**.
4. The important limitation or unknown, beside the conclusion it qualifies.
5. The next available action, with a short consequence.

Example for a settled synthetic case: **The saved result matched the request.**
Supporting text explains that the current readable settings match the saved
settings and that this does not establish downstream service behavior.
Use only claims supported by the actual brief; this example is not universal copy.

The second section, **What happened**, presents a readable ordered account from
available records: initial review, evidence obtained, and final check. Keep an
incorrect initial answer visible as part of the history. If the backend lacks
an event or ordering fact, say it is not recorded; do not fabricate a timeline.

**Technical evidence** retains original verdicts, IDs, revision, probes, usage,
receipts and raw records. Friendly labels accompany exact values; they never
rewrite stored outcomes. Explain rule accuracy separately from accepted result.

### Human decision point

Example: **Was the later configuration intentional?** Show saved A versus
current B, observed times, material changed fields and missing owner/context.
Explain why the available evidence cannot settle intent.

Keep admitted alternatives visible together: keep the current state, record an
intention to restore the requested state, request more evidence, or decide later.
The exact labels follow server capabilities. No consequential choice is
preselected or styled as the presumed correct answer. After selection, show its
consequence, a persistent reason label, and a clear **Record decision** action.

Recording intent is distinct from performing a change. A restoration intention
links to the existing preparation workflow; it does not secretly execute it.
An evidence request shows the linked review and its actual admission state.
A settled case contains no needless approval form. A technical failure offers
recovery with its limits, not a demand for business judgment.

### Explanation and local help

The deterministic summary is immediately usable. **Explain this evidence** is
an optional native model action with visible waiting, failure, cached and retry
states. Keep scope, evidence age, current result and controls application-owned.
Mark generated interpretation and offer evidence references. A model response
cannot replace contradictory facts or create an action.

Brief inline definitions explain receipt, review, rule and evidence when needed.
A skippable five-step guide opens on first sign-in and remains available from a
corner help button. It explains the case stages, rule-versus-outcome judgment,
prepare/authorize/execute/verify, and response-loss recovery, with links into
the relevant working view. Automatic lifecycle narration and similar-case
retrieval are later work.

## Continuity and feedback

- Preserve the requested route through sign-in. Explicit routes take precedence
  over remembered locations. Validate saved routes and discard inaccessible IDs.
- Preserve selected case, filter, expanded disclosures, scroll anchor and focus
  when opening a receipt and returning. Preserve unsent decision text during
  ordinary navigation in the same authenticated session.
- Keep sensitive case content and drafts out of persistent browser storage.
  Session expiry clears them; return to the permitted destination after sign-in
  with an honest notice if a draft could not be retained.
- Bind notices to the case and action they describe. On another page, remove
  them or retain an explicit source label. Never carry a generic success banner
  onto an unrelated action.
- Background refresh cannot steal focus, collapse reading detail, jump scroll
  or overwrite a draft. New evidence marks a draft stale and offers comparison
  before resubmission. Keep the existing server revision check authoritative.
- While pending, prevent duplicate admission and explain the state. Lost replies
  remain unknown until reconciled. Do not introduce automatic operation retries.

## Delegated visual and accessibility details

Use shared semantic tokens for surfaces, text, borders, action, success, warning,
error and focus. System sans-serif carries controls and body text; a restrained
serif display face marks case questions and section headings. Monospace remains
for code and IDs only.
Use a small spacing scale and restrained borders. Target 16px reading text,
14px secondary text, and 44px phone controls. These are product design choices.
Reduce secondary content before shrinking working controls.

Qualification targets draw on [WCAG 2.2](https://www.w3.org/TR/WCAG22/): text
contrast 4.5:1 for ordinary text and 3:1 for qualifying large text; applicable
non-text contrast 3:1; keyboard operation and visible unobscured focus; persistent
labels and programmatic error/status messages; 200% text resizing and reflow at
320 CSS pixels, allowing essential two-dimensional data its own region. Check
24px minimum pointer targets or documented criterion exceptions; the product's
44px phone target is deliberately larger. Respect reduced motion. These checks
do not by themselves establish full WCAG conformance.

## Implementation order after approval

1. Repair route/sign-in return, context-bound messages and case/receipt continuity.
2. Apply the shell, case list, readable hierarchy and shared visual tokens.
3. Refine the decision controls, explanation states and contextual definitions.
4. Exercise complete journeys and repair failures; deliver to the existing
   installed application with source hashes and repeat the owner walkthrough.

Primary files: static/index.html, static/app.js, static/app.css and focused UI
checks. Use existing API contracts. If a required timeline fact or list capability
is absent, add the smallest source-backed projection with tests; do not infer it
from display text. Preserve native review, ledger, operator scope, revision checks
and all existing operation capabilities.

## Acceptance and forensic evidence

Freeze expected outcomes before editing. Record fixture/source revision,
viewport, browser, starting state, actions, expected/actual result, screenshots
and logs. Separate synthetic browser fixtures from installed native checks.

| Journey | Required observation |
| --- | --- |
| Open a protected case while signed out | Sign-in returns to that case; expired or forbidden references have a useful recovery route. |
| Read a settled case | Scope, bounded result and no-decision-needed state are understandable; no approval controls. |
| Inspect and return | Case, filters, disclosure, draft, scroll and focus are restored. |
| Review a context change | A/B difference and unknown intent remain visible; all admitted alternatives are reachable. |
| Submit while evidence changes | Server rejects stale revision; draft survives within session; comparison/review route works. |
| Double click or lose the reply | One recorded decision or linked review; unknown delivery visible; no duplicate business operation. |
| Explanation fails or arrives late | Summary remains usable; bounded retry respected; no cross-case or cross-session stale content. |
| Read while events arrive | No forced reordering, scroll jump, overwritten input or stolen focus. |
| Empty, denied, long and malformed data | Useful state and recovery; safe rendering; no leaking records or clipped essential controls. |
| Phone keyboard and desktop keyboard | Decision input and actions remain reachable; logical focus and Back/Escape behavior. |

Run 320px reflow, 360/390px phones, 768px tablet and 1440px desktop, plus 200%
text, reduced motion and keyboard-only navigation. Include long names/IDs,
large histories, all independent assertion/output combinations and unknowns.
Measure contrast and target geometry rather than judging screenshots alone.

Run relevant Python/API regression and UI handler checks; repeat installed
case/receipt and explanation checks where affected. Capture before/after views
from the same cases. Report executed counts and failures, not planned passes.

Then ask the owner one task at a time, without coaching first:

1. From the summary, what happened and do you need to do anything?
2. In a changed-state case, what fact is missing and which next action fits?
3. Open supporting evidence and return to your place.

Record confusion verbatim, correct choices, missed limits and time to an informed
action. A single owner walkthrough is usability feedback, not population-level
proof or a measure of personal ability. Approval of this spec is not a test pass.

## Design sources

The owner-supplied study notes informed this pass as testable hypotheses.
Practical UI pointers: pp. 61, 66, 179, 213, 216, 244–248, 270–272, 287,
303, 317–318, 331 and 350. The notes and source books are not distributed here.
[Practical UI](https://www.practical-ui.com/) supplies hierarchy, typography,
forms and control vocabulary. [NN/g usability heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/)
inform status, familiar language, control, consistency and recovery.
[Deceptive Patterns](https://deceptive.design/book/contents/chapter-16/) informs
the check for misleading emphasis and hidden alternatives. These sources guide
review; observed task success remains the acceptance evidence.
