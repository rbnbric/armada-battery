# Recovery and shared-service controls

This extends the [native case workflow](NATIVE_CASE_WORKFLOW.md). It is an
application boundary for collaborators using one configured IRIS management
account. It is not database tenant isolation: the backend account's IRIS
permissions still determine which configuration any permitted operator can inspect
or change.

## Abandoned work

Native admission saves the immutable case, evidence binding, active index and
usage reservation in one IRIS transaction under one service lock. An identical
request returns the existing case before checking capacity; it spends no second
reservation. Conflicting content with that identity is rejected.

A queued case has 120 seconds to acquire a worker. The worker receives a unique
lease and a 600-second deadline. Duplicate delivery cannot acquire that lease.
The solver checks it before further evidence/review dispatch, and the real agent
operation checks it before contacting its provider. Completion requires the same
unexpired lease and RUNNING state under the service lock.

Expired QUEUED, RUNNING or ADMISSION_UNCERTAIN records become
`RECOVERY_REQUIRED`. Their explanation remains visible and their active slot is
released. The UI offers **Review refreshed evidence as a new revision**. That
creates a new, budgeted review of the same receipt; it never resends the original
business operation. Old workers cannot overwrite the recovered state.

The web service requests a maintenance sweep every 30 seconds. Native case
reads, admission and worker checks also sweep expired leases. If both services
are offline, recovery occurs on the next sweep after they return. A provider
request already in flight cannot necessarily be cancelled; its late answer
cannot establish an accepted case result.

Upgrade existing code volumes by loading the new classes and running
`##class(Battery.Interop.CaseRecord).Migrate()` with the production stopped.
Legacy active records without a lease become recovery-required. Migration assigns
legacy records to the original `BatteryAdapterUser` deployment identity; change
that migration mapping before use on an installation with a different original
adapter identity. Historical terminal results are retained.

## Admission budgets

| Environment setting | Default | Permitted range |
|---|---:|---:|
| `BATTERY_ACTIVE_LIMIT` | 4 | 1–32 |
| `BATTERY_OPERATOR_ACTIVE_LIMIT` | 2 | 1–16 |
| `BATTERY_DAILY_LIMIT` | 100 | 1–10,000 |
| `BATTERY_OPERATOR_DAILY_LIMIT` | 20 | 1–1,000 |
| `BATTERY_QUEUE_SECONDS` | 120 | 10–600 |
| `BATTERY_RUN_SECONDS` | 600 | 60–900 |

The operator budget is scoped by authenticated native account and operator name.
Daily reservations live in the durable IRIS database and use its calendar day;
restart does not reset them. Failed or abandoned admitted reviews still consume
their daily reservation. Exhaustion returns HTTP 429, which the web API preserves.
A held or recovered review may be revisited without cost; a new revision consumes
a new reservation. The UI shows daily admissions and the operator active limit.

The existing solver permits at most six agent calls per review, with a configured
2,200 maximum output tokens per call. These are admission/work limits, not dollar
billing or a guarantee that a provider honours cancellation. Input-token usage,
provider charges and persistent evidence storage need separate accounting.

## Optional shared identities

The default local installation still uses `BATTERY_ACCESS_KEY` and its existing
ledger. To enable shared identities, use the additional Compose overlay:

```sh
docker compose -f compose.interop.yaml -f compose.shared.yaml up -d --build
```

Set `BATTERY_OPERATORS_FILE` to an absolute path to a private JSON registry and
`BATTERY_SESSION_KEY` to a new random signing key of at least 32 characters. The
registry maps stable names (letters, digits, underscore, hyphen; maximum 64) to:

```json
{
  "alice": {"key_sha256": "SHA256_OF_ALICES_RANDOM_ACCESS_KEY", "role": "operator"},
  "reviewer": {"key_sha256": "SHA256_OF_REVIEWERS_RANDOM_ACCESS_KEY", "role": "observer"}
}
```

Replace each placeholder with a lowercase 64-character SHA-256 digest. Generate
independent high-entropy access keys, for example with `secrets.token_urlsafe(32)`,
and deliver each key privately. The registry supports 1–32 identities and rejects
duplicate hashes, malformed entries and unknown roles. It is mounted read-only
and excluded from the image/repository. Protect it and the session key as service
configuration. For a bind-mounted file replaced atomically, recreate the web
container so the mount follows the new inode.

Operators sign in with their own key. Signed one-hour cookies bind identity,
credential version and role. Every authenticated request checks the current
registry; removing an identity, changing its hash or changing its role revokes
its existing cookies. Sign out clears the browser cookie and local Battery UI
state. It does not revoke a previously copied cookie; rotate that identity's key
for revocation. Use TLS and `BATTERY_SECURE_COOKIE=true` when serving beyond
localhost.

Each identity has a separate hash-addressed ledger under
`BATTERY_OPERATOR_LEDGER_ROOT` (the Compose overlay uses `/app/var/operators`).
Receipts, authorizations, retained observations and native contexts are routed to
that ledger. An observer can read its identity's records and shared target
configuration, but cannot prepare or execute mutations, reconcile receipts, or
submit model reviews. Change an existing operator to observer to preserve its
historical ledger for read-only review.

The native adapter checks its authenticated account on case reads, replay and
parent references. The web backend supplies the signed-in operator's scope;
browsers cannot select that header. Evidence callbacks require the separate
adapter secret and route to the registry-approved operator ledger. These service
credentials remain privileged: do not distribute them as user credentials.

Enabling shared mode does not silently import the original local ledger. Preserve
that ledger and use local mode to inspect its history until an explicit,
identity-checked migration is performed.

## Qualification and remaining scope

See [service evidence](SERVICE_EVIDENCE.md) for executed checks and failure history.
Native lifecycle fixtures do not dispatch business effects or model calls.
The connected run uses real AI Hub inference over a synthetic management receipt.

This release does not implement per-target IRIS permission delegation, public
account enrollment, storage quotas or automatic retention/purge of IRIS message
traces and evidence. Retention needs an explicit deployment policy; case-state
recovery does not erase records. Do not describe this as a completed public
multi-tenant service or a proof of flawless model reasoning.
