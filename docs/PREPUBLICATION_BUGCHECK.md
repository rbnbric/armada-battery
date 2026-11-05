# Pre-publication bug check — 5 November 2026

Tested the Battery update on top of `1f30e6899bba5139394528e75e5bbfbbfcdcc409`.

## Reproduced defects and fixes

1. A non-ASCII single-operator access key raised a server exception. Key comparisons now use encoded bytes; an incorrect Unicode key returns HTTP 401.
2. An expired session left the previous operator's case evidence in the page. Authentication loss now clears case details, receipts, forms, authorization and pending state. A session epoch rejects late responses from the old session. Successful sign-in and sign-out reload the page; blocked browser storage cannot prevent clearing and logout.
3. An invalid Origin URL could raise a parser exception. Invalid or foreign origins now return HTTP 403. API responses also explicitly prohibit caching.

The Unicode and stale-session regression tests failed against the baseline before the fixes. The request-header failure was reproduced during inspection and is covered by the new API regression test.

## Executed verification

| Check | Result |
|---|---|
| Python application suite | 86 passed, 0 failed |
| Node UI handler suite | 13 passed, 0 failed; includes late-response rejection, blocked-storage logout, and identity-switch cleanup |
| Chromium, 360px and 1440px | Opened a synthetic private case, triggered HTTP 401 via Refresh, confirmed sign-in shown, case text removed, Prepare/Execute disabled, and no horizontal overflow |
| Installed Windows web container | Unicode-key 401, malformed-Origin 403, anonymous state 401, health 200; all four responses carry `Cache-Control: no-store` |
| Installed runtime readback | All 13 Python/static source hashes match this release; authenticated native case listing remains available |

Commands for the application regressions:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/ui_state.test.js
```

The existing Work installation was updated in place and its web container rebuilt.
The native IRIS/AI Hub code did not change in this patch. Its lifecycle, restart,
solver-fault and connected-inference results remain the earlier measurements in
[SERVICE_EVIDENCE](SERVICE_EVIDENCE.md); no paid inference was repeated for these
web/session changes. Shared-identity tests run through the real application
middleware in the test client; the installed app remains single-operator.

The first browser probe incorrectly tried to invoke a page function from an
isolated browser world. It did not induce the intended 401 and is not counted as
a qualification run. The corrected probe injected expiry in the main world and
used the actual Refresh control. The passing browser runs use synthetic API
fixtures, separately from the installed HTTP checks.

## Page wording

The supplied “Groundwork Beneath Total Augmentation” editorial describes a wider
OurSpace/OS.IV vision. This check establishes Battery behavior within the above
measurement boundary; it does not qualify every OurSpace app or OS.IV release.
Keep the editorial's distinction between implemented evidence and future goals.
The app is a tested prototype with explicit remaining limits, not proof of
universal correctness. Existing limits are recorded in [SERVICE_CONTROLS](SERVICE_CONTROLS.md).

## Evidence

- [Machine-readable results and source hashes](../interop/results/bugcheck-109.json)
- [Phone after expiry](audit/expired-session-phone.png)
- [Desktop after expiry](audit/expired-session-desktop.png)

The shared-workspace SSH test route was unavailable in the preceding release
qualification. This report establishes isolated application tests and installed
Windows behavior, not a passing fleet-wide DevLathe gate.
