# Service-controls qualification — 5 November 2026

This is the follow-up to [the native integration evidence](IMPLEMENTATION_EVIDENCE.md).
The reproducible setup and limits are in [SERVICE_CONTROLS](SERVICE_CONTROLS.md).

## Executed results

| Check | Result | Measurement boundary |
|---|---|---|
| Python application suite | 84/84 passed | Includes shared identities, concurrent requests, separate ledgers, foreign receipts/authorizations, role changes and identity removal, malformed registry, callback scoping and logout |
| UI handler suite | 10/10 passed | Includes explicit recovery revision and refusal to send observer mutations |
| Native IRIS lifecycle | 17/17 passed | Real persistent database, claim tokens, expiry, late/duplicate completion, queue gap, returned active slots and per-operator daily limits |
| Existing native solver faults | 31/31 passed | Real native production with injected provider/evidence responses; no paid inference |
| Container restart | Passed | Injected running lease survived an actual native-container restart, became RECOVERY_REQUIRED, rejected its old token and retained the daily-budget value of 20 |
| Private native HTTP | Passed | Anonymous request 401; foreign-account list/get/replay excluded; mismatched operator 403; eight concurrent requests at exhausted budget all 429; rejected case absent; existing-case replay still 200 |
| Connected review | VERIFIED_MATCH | Real AI Hub over one synthetic management receipt; 16.094 seconds, 3 calls, 2,953 input and 2,670 output tokens; repeated execution/admission keys returned their original records |
| Chromium layout | Passed at 360px and 1440px | Actual HTML/CSS/JS, labeled synthetic API fixture; no horizontal overflow or browser error; phone controls at least 44px high |

The restart test intentionally injected a running lease rather than interrupting
a paid provider request. It establishes durable state recovery and fencing across
a process restart. It does not establish cancellation of inference already in
flight. The eight concurrent HTTP requests establish fail-closed exhaustion;
they are not a throughput or fair-queue benchmark.

The latest shared-identity tests execute the production HTTP middleware through
FastAPI's test client, including concurrent requests. The installed local app
remains in its original single-operator mode; shared mode was not enabled with
invented user accounts on Robin's computer.

## Delivery and evidence

The existing `battery-eap-native` Work folder was updated in place. Both services
were rebuilt; the persistent native code volume was explicitly recompiled and
migrated. A final web-only rebuild included stricter malformed-role validation.
The final readback checks authenticated health/case access and compares installed
runtime and native source SHA-256 values with the release files.

- [Machine-readable controls evidence](../interop/results/service-controls-109.json)
- [Connected native result and raw model history](../interop/results/service-connected-109.json)
- [Phone recovery view](audit/recovery-phone.png) and [desktop recovery view](audit/recovery-desktop.png)

The connected model run preceded the final malformed-registry type check. That
small change was qualified by the 84-test Python suite and final installed
readback; inference was not rerun merely to repeat an unrelated credential test.

The normal shared-workspace SSH test route was attempted again and failed DNS
resolution for `ct200`. This report records the isolated application tests and
actual Windows/IRIS execution, not a passing DevLathe fleet release gate.

## Failures caught during development

1. Migration initially assumed every historical record had a full contract.
   A legacy fixture did not. Migration now handles records without that field.
2. An early lifecycle edit accidentally called its own sweep recursively.
   The native suite failed with FRAMESTACK; the recursion was removed before
   the passing qualification.
3. The qualification wrapper tried to start a production the solver suite had
   already restored. The redundant start was removed.
4. The restart wrapper attempted its readback while IRIS was still initializing.
   The first readback was refused; a later verified readback used the existing
   persisted fixture, without replaying its setup.
5. Shared-operator tests initially reused the old API fixture's mocked singleton
   engine. The test now uses the real engine factory and checks independent
   ledger paths, receipt absence and concurrent identity routing.

These failed attempts are not counted as passes. The resulting checks support
these specific controls, not an assertion that every possible failure is solved.

## Remaining design boundaries

IRIS backend privileges remain shared among permitted operators; this is not
per-target tenant ACL enforcement. Provider calls already in flight may continue
billing after a lease expires. Automatic storage retention/purge, public account
provisioning and dollar-cost enforcement remain future work. Evidence is retained
rather than silently discarded during recovery.
