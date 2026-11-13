# Native adapter and Embedded Python qualification

Battery's evidence operation uses a custom `Ens.OutboundAdapter` for authenticated
management reads. An Embedded Python method validates the returned JSON inside
IRIS before the operation accepts it. Both are exercised through the native
production queue.

## Implementation

| Component | Responsibility |
| --- | --- |
| [EvidenceAdapter.cls](../interop/Battery/Interop/EvidenceAdapter.cls) | Reads the deployment-configured management host on port 8080. Supplies the deployment credential and bound operator scope. Admits only the four defined read phases, applies timeouts, checks HTTP status and bounds the response to 64 KiB. |
| [EvidenceEnvelope.cls](../interop/Battery/Interop/EvidenceEnvelope.cls) | Runs through `[ Language = python ]` in IRIS. Rejects duplicate JSON members, malformed envelopes, non-finite numbers, changed contracts and tool results for another phase or attempt. Preserves JSON number equivalence while distinguishing booleans and strings. |
| [EvidenceOperation.cls](../interop/Battery/Interop/EvidenceOperation.cls) | Resolves the persisted case binding, calls its native adapter, invokes the Embedded Python validator and records accepted observations. |
| [OutcomeProof.cls](../interop/Battery/Interop/OutcomeProof.cls) | Separately checks observation scope, freshness, count and result. An accepted JSON envelope alone cannot establish success. |

The host and credentials come from deployment settings. Model output cannot
choose an arbitrary URL. Transport errors remain errors, and an unsuccessful
HTTP response does not trigger another request. The adapter does not change the
business target.

## Executed evidence

On 13 November, **247/247 native checks passed**: 24 envelope cases, 13 HTTP
and queued-operation checks, 32 solver cases, 26 agent fault cases, 3 saved-trace
checks and 149 proof checks. Seven local tests also verified that the report
reader rejects incomplete, duplicated and failed output.

[Native results and source hashes](../interop/results/bonus-qualification-109.json)
record the exact runtime and individual checks. The suite covers valid and
adversarial JSON, real HTTP authentication, response limits, UTF-8 preservation,
native queued execution, connection refusal, solver faults and the existing
deterministic proof matrix. The HTTP fixture is a separate loopback process;
the validator executes inside IRIS. Regression provider failures are injected.
This suite makes no model calls.

While preparing [the Visual Trace example](TRACEABILITY.md), a separate defect
was found in Battery's solver: it reused persisted request objects across
successive probes and review rounds. Each send now creates a new message body.
The trace tests inspect saved rows after completion and require the original
probe phases and distinct review snapshots to survive. This is a Battery bug,
not a claimed vendor defect.

## Reproduce the native checks

Use a disposable test container built from this source. The fixture key below
is public test data. It is not a deployment credential. No model key or public
port is needed.

```sh
docker build -f Dockerfile.interop -t battery-bonus-check .
docker run -d --name battery-bonus-check --network none --cpus 2 --memory 4g --memory-swap 4g --pids-limit 512 --shm-size 256m -e BATTERY_MANAGEMENT_HOST=127.0.0.1 -e BATTERY_ADAPTER_KEY=battery-test-fixture-key-not-a-secret-20261113 battery-bonus-check
```

Wait for IRIS startup to finish. `docker exec battery-bonus-check iris qlist`
must report the instance running. Then, from the repository root:

```sh
docker cp interop/. battery-bonus-check:/home/irisowner/dev/bonus/
docker exec -i battery-bonus-check iris session IRIS < interop/tests/bonus-qualification.script > bonus-qualification.log
docker exec -i battery-bonus-check iris session IRIS < interop/tests/bonus-regression.script > bonus-regression.log
docker exec -i battery-bonus-check iris session IRIS < interop/tests/proof-contracts.script > bonus-proof.log
python interop/tests/verify_bonus_results.py bonus-qualification.log bonus-regression.log bonus-proof.log
docker stop battery-bonus-check
```

Use CMD for redirected commands on Windows. The verifier requires all expected
checks and completion markers; a successful shell exit from `iris session`
alone is insufficient. Keep the logs and container for inspection after a
failure. The test container has its own disposable data and no mounted operator
ledger.

## EAP version

These results use **IRIS Community 2027.1.0AI build 109U, x86-64**. On 13 November
the participant's EAP download screen offered Community build 109, while the
[contest announcement](https://community.intersystems.com/post/intersystems-programming-contest-ai-agents-interoperability-workflows)
still named 2026.3.0AI build 154. No build 154 result is claimed. The available
image and the published contest requirement need organizer reconciliation.

These implementations support requests for Custom Adapter and Embedded Python
bonus review. Awarded points are tracked in [the contest evidence table](CONTEST_49_BONUSES.md).
