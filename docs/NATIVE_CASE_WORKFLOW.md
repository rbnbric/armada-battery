# Native case workflow

The management app can send an existing operation receipt into the native IRIS
AI Hub production. The browser supplies a receipt ID and a stable request key;
the server constructs the evidence contract from retained observations. It does
not accept browser-authored proof.

## Run locally

Start from the branch containing the agent implementation:

```sh
git clone --branch contest-49-wip https://github.com/rbnbric/armada-battery.git
cd armada-battery
```

The default branch and hosted walkthrough contain the earlier management release.
For the fixed 1.0.3 code snapshot, use commit
`f3f438a177b27f834aa022ebb7fc810acd8a4b15`.

Load the AI Hub EAP build 109 image using the vendor's
[AI Hub EAP instructions](https://github.com/intersystems-community/ai-hub-eap).
After loading, use `docker image ls` to check the image name. Compose defaults to
`iris-community:2027.1.0AI.109.0`. If the imported image has a registry-qualified
name, set `AIHUB_IMAGE` to that exact name in `.env`. The EAP image is obtained
from the vendor; the repository does not redistribute it. Other EAP builds and
CPU architectures need their own compatibility check.

Prepare a private, git-ignored `.env` with `NEBIUS_API_KEY`,
`BATTERY_NATIVE_PASSWORD`, `BATTERY_ADAPTER_KEY`, and `BATTERY_ACCESS_KEY`.
Use independently generated values of at least 32 characters for the last three.
Do not commit this file or include it in an evidence export.

```sh
docker compose -f compose.interop.yaml up --build -d
# Once IRIS is running, provision the private API account and start the production:
docker compose -f compose.interop.yaml exec -T battery-interop iris session IRIS < interop/configure.script
```

Require the `BATTERY_SETUP_OK` marker. On Windows, run the redirected command
from CMD. A PowerShell invocation should explicitly run it through `cmd /d /c`.
If IRIS is still starting, wait until it is running before provisioning; inspect
`docker compose -f compose.interop.yaml logs --tail=80 battery-interop` for startup
failures. The setup command's exit status alone does not establish success: check
the marker. Re-running provisioning does not rotate an existing adapter account's
password; keep its original private password or deliberately update the native
account and web-service configuration together.
The browser app is at `http://localhost:8080`; sign in with this installation's
`BATTERY_ACCESS_KEY`. On Windows, `powershell -File scripts/open_local.ps1` opens this local URL and
copies the operator key to your clipboard for the sign-in field. Pass
`-EnvironmentFile .integration.env` when using that private filename.
The private native API uses a separate account and never
sends its password to the browser. Ports are bound to localhost.

The default management target is **synthetic**. AI Hub inference, HTTP transport,
IRIS queues, records and message traces are real. These are distinct claims.
The existing IRIS management adapter remains separately configurable; simply
connecting AI Hub does not convert a synthetic operation into a live one.

1. Prepare and execute a demonstration task through the existing UI.
2. Open its receipt and select **Review this receipt with AI Hub**.
3. Open **Agent cases** and refresh to follow admission, execution and completion.
4. Inspect rule assertion and measured output separately. Expand the reviews for
   raw responses, rejected answers and usage; expand tool reads for the source.
5. If held, correct or reconcile the underlying evidence before requesting a new
   revision. The old revision and its failure remain visible.

An `ADMISSION_UNCERTAIN` case requires inspection of the native trace. It is not
an instruction to resend an operation. Expired queued, running or uncertain
admissions become `RECOVERY_REQUIRED` on the next maintenance sweep. The operator
can inspect the original case and request a new review revision. Recovery never
replays the business operation; see [service controls](SERVICE_CONTROLS.md).

## What the tools measure

| Tool | Source and meaning |
| --- | --- |
| `CHECK_EFFECT_RECEIPT` | Authenticated callback to the operator-scoped durable operation ledger. Establishes receipt status and identity. |
| `CHECK_TARGET_VERSION` | The configured management adapter reads current target configuration; its hash is compared with the retained receipt snapshot. |
| `CHECK_FRESH_READBACK` | Reads the receipt and target configuration together. It does not change the original receipt timestamp. |
| Final check | Reads both again and rejects evidence that changed after reasoning. |

For this management bridge, count means the number of correlated verified
**receipt records**, not a claim about physical effect count. A configuration
readback does not establish downstream service behavior. An unverified or
uncertain operation remains UNKNOWN. Expired receipts remain expired; another
model call cannot refresh their source timestamp.

The investigator's admitted tool choice is executed on native cases. Unknown
tools and `HOLD_FOR_HUMAN` stop explicitly. Legacy synthetic gauntlet cases retain
their original deterministic probe policy so historical results remain comparable.

## Recovery and limits

One malformed reviewer response may receive one contract-repair request. The
original response, validation reason and usage remain in the review history.
Transport failures do not trigger an inference retry. The same validator applies
to the repaired response. Each review has a 180-second budget; a repair call is
limited to 45 seconds. The solver has at most two review rounds, so at most six
agent calls, plus bounded evidence reads. This is not an inference cancellation
guarantee or a dollar billing system. Durable admission budgets and lease recovery
are now described in [service controls](SERVICE_CONTROLS.md).

Case admission and its evidence context are written to the management ledger
before HTTP submission. Native cases claim QUEUED -> RUNNING once. Identical
admission keys reuse the immutable envelope and existing result; canonical JSON
serialization preserves request bytes across process restart. A new revision
retains its parent and receipt. Native case IDs are separate from action
idempotency keys.

The default is a single-operator installation. An optional shared-identity overlay
adds signed sessions, read-only roles and separate operator ledgers; see
[SERVICE_CONTROLS](SERVICE_CONTROLS.md). The native
adapter identity can read/write the Battery data namespace. It is not a
multi-tenant database ACL. Provisioning creates the adapter identity; it does
not replace vendor-account/password management or network hardening. Qualification
used localhost-bound services on a single-operator host. Do not expose the private API or shared callback key
as a public browser credential.

## Persistence and upgrades

Compose mounts separate named volumes for durable `%SYS`, Battery data,
Battery code and the management ledger. The initializer sets ownership of the
system volume before IRIS starts. This follows the vendor's
[durable container data arrangement](https://docs.intersystems.com/irislatest/csp/docbook/DocBook.UI.Page.cls?KEY=ADOCK),
with explicit mounts for the custom Battery databases.

`docker compose down` retains these volumes. `down -v` deletes them and is not an
upgrade procedure. Existing pre-volume demo containers require a deliberate
migration; changing Compose alone does not preserve an old writable layer.

Code is also persisted. A rebuilt image alone does not update a populated code
volume. Stop the production, copy/load the new `interop/Battery` sources and
check the compile status before restarting. Keep a stopped-instance snapshot
of all three native volumes and the management ledger before a schema change;
restore the matched set with its original qualified image if migration fails.
Do not copy open database files as a backup.

## Qualification

The integration runner is:

```sh
docker compose -f compose.interop.yaml exec -T battery-web python scripts/verify_native_integration.py
```

It explicitly requires the synthetic management adapter, performs one bounded
demonstration operation, repeats its execution key, submits/repeats the native
admission key and follows the real AI Hub workflow. It writes the result under
`/app/var/native-integration-result.json`. A runner exit code alone is insufficient:
check the result state, probe history, native response ID and final marker.

See [the implementation evidence report](IMPLEMENTATION_EVIDENCE.md) for the actually executed checks,
source hashes and remaining unqualified boundaries. The earlier
[SYSTEM_DESIGN_AUDIT](SYSTEM_DESIGN_AUDIT.md) remains the historical baseline.
