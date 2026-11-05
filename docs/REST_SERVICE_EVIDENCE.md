# Functional REST service qualification — 5 November 2026

Follow-up to the [configuration qualification](IMPLEMENTATION_EVIDENCE.md).
The original run proved that an IRIS REST application configuration existed and
matched its requested state. This follow-up sends actual HTTP requests through a
new application using the same `Battery.Interop.CaseAPI` dispatch class.

## Result

**22/22 functional HTTP checks and 19/19 native lifecycle checks passed.**
Two native defects were reproduced and fixed before the passing run.

| Area | Observed result |
|---|---|
| Creation through Battery | Prepared and executed with the real IRIS management adapter; configuration receipt VERIFIED_SUCCESS |
| Repeated execution key | Same receipt returned |
| Configuration | BATTERY namespace, intended dispatch class and password authentication read back |
| Anonymous / wrong password | HTTP 401 |
| Authenticated list | HTTP 200, JSON, same case IDs as the established native API |
| Authenticated detail | HTTP 200, complete response equal to the established native API |
| Valid POST replay | HTTP 200, existing terminal case returned unchanged |
| Foreign native owner / operator | HTTP 404, case detail withheld |
| Missing case / route | HTTP 404 |
| Invalid case, malformed JSON, array, null, string bodies | HTTP 400 |
| Rejected POST effects | No new cases and no review-budget changes |
| Cleanup | Temporary application absent from configuration; its route returns 404; fixture identity and role removed |

[Machine-readable results and source hashes](../interop/results/rest-service-109.json)
contain the 22 individual checks. Native lifecycle qualification retained the
original 17 checks and added two regressions for unscoped and scoped budgets.

## Bugs found by executing the service

1. **Authenticated unfiltered list returned 500.** The optional operator filter
   was empty, and the budget lookup used it as an IRIS global subscript. Both the
   new application and the established native API failed on that request. The
   same request shape is used by background maintenance. Unscoped responses now
   report `operator_scoped: 0` and `operator_daily_used: null`; they do not
   query an empty subscript or pretend usage is zero. Scoped counters retain
   their measured values.
2. **Malformed/scalar JSON returned 500.** Parsing and root-object validation now
   classify invalid input as HTTP 400 before case admission. Rejected requests
   do not create records or spend review reservations.

The initial run recorded seven passing checks (including cleanup) and one failed
authenticated-list check; it stopped before the later behavior checks.
After the budget fix, 18 of 21 checks passed, exposing the three JSON failures.
After both fixes, the full run passed; a valid existing-case POST replay was
added and the final 22-check run passed. No earlier failure was relabeled.

During harness preparation, a missing qualification directory prevented one
load attempt; no production stop had occurred. An initial new test assertion used
unsupported dot syntax for an underscore-containing JSON key. It was corrected to
`%Get`; the subsequent 19-check native run passed. These were harness defects,
separate from the two service defects above.

## Runtime and measurement boundary

The test used the installed AI Hub EAP build 109 environment. A separate
loopback Battery process and ledger used a disposable privileged fixture identity
to create the temporary application. The normal operator web process retained
its mode and configuration. Native production was briefly stopped for explicit
compilation with no active cases, then restarted. The updated classes are loaded
in the persistent native code database and their installed source hashes match
the repository files.

**No model calls were made.** Positive POST coverage verifies idempotent replay
of an existing case. New case execution and inference are covered separately by
the earlier integration reports; this run does not repeat that paid workflow.
This report qualifies the exercised CaseAPI routes and responses, not arbitrary
REST applications, sustained load or every possible input.

The result belongs to this follow-up code revision. The earlier 1.0.3 snapshot
`f3f438a` does not contain these two native fixes. Historical evidence remains
unchanged; use the current `contest-49-wip` branch for the corrected implementation.

## Reproduce in a disposable installation

First follow [native setup and code-volume upgrade guidance](NATIVE_CASE_WORKFLOW.md).
The native classes must match the source being tested. A retained terminal case
from the normal operator ledger is required for the positive read/replay checks;
the test deliberately does not manufacture a model result.

Run these commands from the repository root using the same Compose project and
private environment file as the installation. Shell input redirection works from
CMD on Windows; use `cmd /d /c` when invoking it from PowerShell.

```sh
docker compose -f compose.interop.yaml exec -T battery-interop iris session IRIS < interop/tests/configure-rest-fixture.script
# Require REST_FIXTURE_READY before continuing.
docker compose -f compose.interop.yaml exec -T battery-web mkdir -p /app/interop/tests
docker compose -f compose.interop.yaml cp interop/tests/verify-rest-service.py battery-web:/app/interop/tests/verify-rest-service.py
docker compose -f compose.interop.yaml exec -T battery-web python interop/tests/verify-rest-service.py
# Run identity cleanup even when the qualification command reports failure:
docker compose -f compose.interop.yaml exec -T battery-interop iris session IRIS < interop/tests/remove-rest-fixture.script
```

The runner saves `/app/var/rest-functional-result.json`, retains its qualification
ledger and attempts application cleanup in `finally`. Require all checks, the
`REST_FUNCTIONAL_OK` marker and the `REST_FIXTURE_USER_REMOVED` cleanup marker.
A fixture-identity collision is refused before setup; inspect that existing
identity instead of deleting it. If configuration cleanup fails, the result names
the unique temporary application for investigation.
