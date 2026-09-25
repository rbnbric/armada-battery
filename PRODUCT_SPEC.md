# Armada Battery product specification

Status: version 0.1, implementation baseline  
Product: Armada Battery  
Target: InterSystems Programming Contest — Build Your Own Management Portal  
Implementation posture: public, open-source, clean-room

## Product statement

Armada Battery is an InterSystems IRIS management portal organized around
operational decisions. It converts current management API observations into
plain-language conditions, identifies the safest applicable next action, and
verifies whether an executed action produced its intended result.

The primary user should not need prior knowledge of the IRIS Management Portal
to handle routine conditions safely. An experienced administrator must still be
able to inspect every source observation, rule, threshold, privilege, request,
and response behind a conclusion.

Battery's distinguishing contract is:

> Declare the operation, prove its prerequisites, execute within bounds, and
> accept completion only when the outcome is independently observed.

## Intended outcome

An operator opening Battery must be able to answer:

1. Can this IRIS instance continue serving work safely?
2. What current evidence supports that conclusion?
3. Which conditions require attention now or preparation soon?
4. What is the safest authorized action available?
5. Did an attempted action actually correct the condition?

Battery is successful when a first-time operator can complete a documented
fault-and-recovery scenario without interpreting raw telemetry, while an expert
can reproduce and audit every conclusion.

## Product principles

### Outcomes over controls

The product reports resolved or unresolved conditions. Presenting a button or
receiving a successful HTTP status is not an outcome.

### Positive proof before change

The absence of an error does not establish safety. Every state-changing action
requires current affirmative evidence for all mandatory prerequisites.

### Deterministic judgment

The same applicable policy and the same ordered observations must produce the
same findings, recommendations, and eligibility result. Operational decisions
must not depend on an LLM.

### Unknown remains unknown

Missing privileges, stale observations, unsupported endpoints, malformed
responses, and contradictory evidence produce `UNKNOWN`. They never silently
become healthy or false.

### Plain language with inspectable depth

The first layer states the condition, consequence, and next step. Successive
layers expose the rule, observations, thresholds, endpoint, privilege, and raw
sanitized response.

### Least authority

Read-only collection runs independently of mutation authority. An installation
may operate permanently in observation-only mode.

### Limits stated on the surface

Battery identifies unsupported versions, unavailable evidence, incomplete
coverage, and actions it cannot verify. It does not imply certainty beyond the
available observations.

## Scope

The contest release covers the requested management areas through a consistent
decision interface.

| Management area | Required Battery capability |
|---|---|
| Web applications | Inventory, inspect configuration, identify availability or access problems, and expose bounded configuration actions |
| REST APIs | Discover and inspect APIs, construct requests, display sanitized responses, and retain test evidence |
| Permissions | Show effective capabilities, explain denied actions, and expose applicable user, role, and resource management |
| Security and secrets | Manage supported security objects while never returning or recording secret values |
| Tasks | Inspect schedules and history; explain failures; run, resume, suspend, or edit when eligible |
| Operating system | Interpret processes, disks, CPU, memory, devices, locks, and other exposed resources |
| Logs | Search and correlate relevant records with findings, actions, and verification |
| Battery layer | Evaluate readiness, maintain assurance obligations, recommend actions, and verify outcomes |

Breadth across these areas is required. The Battery layer organizes the portal;
it does not replace the requested management surfaces with a single score.

## System model

Battery uses five public domain objects:

```text
Intent or obligation -> Observation -> Finding -> Action Contract -> Receipt
```

### Intent

An intent records an outcome the operator deliberately requests. This is how
Battery handles ordinary administration such as creating an application,
granting access, or scheduling a task without pretending that an incident
already exists.

```yaml
id: unique identifier
kind: INSPECT | CREATE | CHANGE | RUN | SUSPEND | RESUME | DELETE
target: canonical resource identifier
desired_outcome: deterministic predicate
constraints: operator-supplied limits
requested_by: authenticated operator identifier
requested_at: UTC timestamp
expires_at: UTC timestamp or null
```

An intent does not authorize execution. It causes the planner to identify
candidate action contracts, collect the evidence each one requires, and present
the lowest-impact eligible route to the desired outcome. When several routes
remain valid, Battery explains the tradeoff and leaves the choice to the
operator.

### Intent planning

The planner compares desired state with observed state and returns one of:

- `SATISFIED`: the desired outcome is already affirmatively established;
- `NEEDS_EVIDENCE`: a safe plan cannot yet be selected;
- `PLAN_READY`: one or more bounded plans have complete preparation paths;
- `UNSUPPORTED`: Battery has no validated contract for the requested outcome.

A plan is an ordered set of observations, preparations, changes, and
postconditions. Every alternative must reach the same desired outcome while
honoring the intent's constraints. The planner cannot manufacture a warning or
incident merely to justify an administrative request.

The first required intent families are:

| Intent | Planning questions | Verified outcome |
|---|---|---|
| Create an application | Is the name free; which namespace and dispatch class apply; which authentication and resource rules are required? | Application readback matches the requested configuration and its declared availability probe succeeds |
| Give a person access | Does the user exist; what exact resource use is needed; is an existing role sufficient; could the change broaden unrelated access or remove the operator's own access? | Effective access is independently recalculated for the target user and resource |
| Schedule a task | Does the task class exist; which namespace and run-as identity apply; is the schedule valid; can runs overlap; what side effects occur? | Task readback matches the schedule and appears in upcoming work as expected |
| Run an existing task | Is the intended definition selected; is it suspended or already running; did the prior run fail; can a new run be verified? | A new terminal history row is observed for this attempt |

Planning exposes the current-state facts, proposed delta, assumptions, and
postconditions before it offers execution. An unsafe or poorly understood
delta becomes `NEEDS_EVIDENCE`, not a best guess.

### Observation

An observation is an immutable, timestamped fact obtained from IRIS or produced
by a Battery probe.

Required fields:

```yaml
id: unique identifier
source: API operation or Battery probe identifier
target: canonical resource identifier
captured_at: UTC timestamp
expires_at: UTC timestamp or null
value: normalized typed value
quality: VALID | STALE | MALFORMED | FORBIDDEN | UNSUPPORTED | CONFLICTED
sensitivity: PUBLIC | OPERATIONAL | SECRET
provenance:
  request_id: correlation identifier
  iris_version: observed product version
  response_digest: digest of the sanitized source response
```

Truth belongs to a predicate evaluated over observations, rather than to a raw
measurement. For example, `12 GB free` is an observation; `free space exceeds
the configured reserve` is a predicate with a three-valued result.

`SECRET` observations may record only existence, identifiers safe for display,
and non-secret metadata. Secret material is never placed in the observation
ledger.

### Finding

A finding is a deterministic conclusion derived from observations and a
versioned rule.

Required fields:

```yaml
id: stable finding identifier
rule_id: stable rule identifier
rule_version: immutable version
target: canonical resource identifier
state: SAFE | WATCH | ACT | BLOCKED | VERIFY
summary: plain-language condition
consequence: plain-language operational effect
evidence_ids: ordered observation identifiers
missing_evidence: required observations not established
recommended_action_ids: ordered eligible or preparatory actions
evaluated_at: UTC timestamp
```

### Action contract

An action contract defines when an operation applies, what must be true before
execution, what it changes, and how success is proved.

Required fields:

```yaml
id: stable action identifier
version: immutable version
kind: OBSERVE | PREPARE | CHANGE | VERIFY
impact: NONE | LOW | MODERATE | HIGH
applies_when: deterministic predicate
requires:
  privileges: []
  evidence: []
  maximum_evidence_age: duration
  no_conflicts: []
preview:
  affected_resources: []
  expected_effect: text
  reversible: boolean
  rollback_action_id: identifier or null
execute:
  operation: normalized API operation identifier
  parameters: explicitly allowed parameter schema
verify:
  deadline: duration
  success_when: deterministic predicate
  failure_when: deterministic predicate
failure:
  recommendation: text
  escalation_packet: boolean
```

### Receipt

A receipt is the immutable account of an attempted action.

It records the action contract and rule versions, operator, target, preflight
certificate, sanitized request, start and end times, transport result,
before-and-after evidence identifiers, verification result, and any remaining
unknowns. A receipt reports one of:

- `VERIFIED_SUCCESS`
- `VERIFIED_FAILURE`
- `EXECUTED_UNVERIFIED`
- `OUTCOME_UNKNOWN`
- `BLOCKED_BEFORE_EXECUTION`
- `CANCELLED`

An HTTP success alone can produce only `EXECUTED_UNVERIFIED` until the declared
postcondition is observed.

## Observation ledger and replay

The observation ledger is Battery's machine-readable memory. New observations,
rule evaluations, action attempts, and verification outcomes are appended; they
are not rewritten to make the current state appear cleaner.

The current dashboard is a projection derived from the ledger. Given the same
ledger prefix, evaluation time, policy configuration, policy versions, and
adapter versions, replay must reconstruct the same findings and action
eligibility.

Every ledger record contains:

- monotonically ordered sequence number;
- UTC event time and ingestion time;
- event type and schema version;
- target and correlation identifiers;
- sanitized payload;
- digest of the preceding record and the current record.

The digest chain is evidence of accidental alteration, not a claim of external
attestation. Exported receipts include the relevant chain segment and policy
versions.

Retention is configurable. Deletion or compaction produces an explicit
administrative event and preserves receipt-level summaries required for the
demo and audit trail.

## Truth and evidence semantics

Every predicate evaluates in three-valued logic:

- `TRUE`: current valid evidence establishes the predicate;
- `FALSE`: current valid evidence disproves the predicate;
- `UNKNOWN`: the predicate cannot be established.

Mandatory action prerequisites must all be `TRUE`. `FALSE` or `UNKNOWN` blocks
the action.

Evidence is current only when:

```text
captured_at <= evaluation_time <= expires_at
```

where the rule defines the applicable lifetime. Evidence without an expiry may
support historical explanation but cannot authorize a change unless the action
contract explicitly permits it.

When current observations disagree, Battery records both, marks the derived
fact `CONFLICTED`, and blocks dependent changes. A later observation does not
automatically erase a conflict unless the policy defines the earlier source as
superseded.

Collectors distinguish a complete empty collection from a truncated, filtered,
forbidden, or failed collection. Source and ingestion timestamps remain
separate. Freshness uses the Battery server clock and records detected clock
skew. Stable source identity or response digest prevents duplicate source
events from being counted as corroboration.

## Findings and recommendation paths

A finding may be established in four ways:

1. **Direct:** one authoritative observation satisfies the rule.
2. **Corroborated:** a declared quorum of independent observations satisfies the
   rule.
3. **Trend:** a deterministic calculation over ordered observations crosses a
   declared forecast boundary.
4. **Exclusion:** required alternatives are affirmatively disproved before the
   remaining explanation is selected.

Battery displays which path established the finding. A numerical confidence
score is not substituted for missing proof. Trend findings state their window,
sample count, formula, and prediction horizon.

Determinism establishes reproducibility, not correctness. Every rule is a
testable operational claim and declares:

- the source or rationale for the rule;
- assumptions required for it to apply;
- supported IRIS versions and configurations;
- observations that would contradict it;
- known counterexamples and unsafe cases;
- synthetic tests and live validations performed;
- validation state: `DRAFT`, `SIMULATED`, `LIVE_OBSERVED`, or `APPROVED`.

The interface labels observations, configured policy, and inferred explanation
separately. A rule below its required validation state may explain a condition
or request more evidence, but cannot enable a state-changing action. Observing
the desired postcondition proves that the state followed the attempt; it does
not by itself prove that the action caused the change.

Recommendation ordering is deterministic:

1. establish missing evidence;
2. perform harmless preparation;
3. prefer the lowest-impact action that can satisfy the postcondition;
4. prefer reversible actions when impact is otherwise equal;
5. escalate when no action has complete prerequisites or verification.

## Rule governance

A finding rule and an action-recommendation rule are separate. A symptom may be
proven while its cause remains unknown, and a likely cause does not establish
that a proposed remedy is safe. Rules therefore produce one of four authorities:

- `EXPLAIN`: describe an established condition;
- `INVESTIGATE`: request a discriminating observation;
- `PREPARE`: test an action's prerequisites and impact;
- `EXECUTE`: permit a declared action after affirmative preflight.

Promotion is monotonic and evidence-based:

```text
DRAFT -> SIMULATED -> LIVE_OBSERVED -> APPROVED
```

`DRAFT` rules can explain or investigate. `SIMULATED` rules may execute only in
the synthetic harness. `LIVE_OBSERVED` rules may unlock their specifically
validated action and IRIS version. `APPROVED` means the rule owner reviewed its
live evidence, counterexamples, and rollback behavior; it is not a guarantee
that every future case is safe.

Each promotion requires its declared positive cases, negative cases,
counterexamples, ambiguous cases, version bounds, and expected postconditions
to pass. Any newly observed counterexample demotes the rule and blocks dependent
changes until review. Rule changes create a new immutable version rather than
rewriting the evidence attached to the previous one.

For example, `latest task run failed` establishes a failure finding. It does not
authorize `run task again`. Battery must first identify and validate a
cause-specific retry rule or restrict itself to investigation and escalation.

## Reactive and assurance work

Battery distinguishes four sources of operator work:

| Work type | Trigger | Example |
|---|---|---|
| Incident | A failure is affirmatively observed | Scheduled backup task failed |
| Risk | Current evidence predicts a declared boundary violation | Journal capacity is declining toward its minimum reserve |
| Assurance due | Positive evidence has expired or has never been established | Recovery destination has not been tested within policy |
| Preparation required | A requested change lacks a proven prerequisite | No current proof that a conflicting task is absent |

Assurance work is non-reactionary. It renews evidence before a failure or action
requires it. Typical assurance tasks include checking backup recency, testing a
destination, refreshing capacity and license headroom, checking certificate
expiry, confirming scheduled maintenance, detecting configuration drift, and
validating effective privileges.

An assurance obligation contains:

```yaml
id: stable obligation identifier
target: canonical resource identifier
predicate: fact that must remain affirmatively TRUE
renew_before: duration before evidence expiry
probe_action_id: harmless observation or preparation action
overdue_state: WATCH | ACT | BLOCKED
```

The scheduler creates work when an obligation approaches expiry. No error event
is required.

## Action lifecycle

Every state-changing operation follows:

```text
PREPARE -> AUTHORIZE -> EXECUTE -> VERIFY
```

### Prepare

Battery resolves the target, refreshes required observations, checks effective
privileges, checks version support, detects conflicting work, calculates impact,
and constructs a preview.

Preparation may execute only `OBSERVE` and explicitly harmless `PREPARE`
contracts. It cannot silently perform the requested state change.

### Authorize

Successful preparation creates a short-lived preflight certificate bound to:

```text
action contract + target + operator + effective privileges + evidence snapshot
```

The certificate includes an expiry and single-use nonce. Any target change,
expired evidence, privilege change, detected conflict, contract-version change,
or prior use invalidates it.

Preflight reduces concurrency risk but cannot eliminate changes made by another
administrator between observation and execution. When IRIS exposes a revision
or conditional update, Battery binds the operation to it. Otherwise the action
contract states the remaining race and refreshes the narrowest possible evidence
immediately before execution.

Authorization by impact:

| Impact | Required interaction |
|---|---|
| None | May run automatically |
| Low | One explicit execution action |
| Moderate | Review affected resources and confirm |
| High | Type the target identifier and confirm the stated consequence |

### Execute

The server validates the certificate again immediately before calling IRIS.
The client cannot elevate impact, alter the target, or add undeclared parameters.
Repeated submission with the same execution key returns the original attempt
rather than starting another operation.

Battery creates a durable attempt before sending the IRIS request. If the
connection fails after transmission and the outcome cannot be established, the
attempt becomes `OUTCOME_UNKNOWN`. Battery reconciles it through fresh
observation and never automatically retries an ambiguous non-idempotent change.

### Verify

Battery polls or observes the declared postcondition until it becomes true,
becomes false under the failure predicate, or reaches its deadline. Verification
uses a new observation rather than trusting the mutation response.

If verification is impossible, the interface reports `EXECUTED_UNVERIFIED`,
preserves the receipt, and gives an escalation or manual verification path.

## Interface specification

### Global header

The header displays:

- connected instance identity and product version;
- authenticated user;
- connection freshness;
- observation-only or change-enabled mode;
- overall charge and evidence coverage;
- count of `ACT`, `WATCH`, `BLOCKED`, and `VERIFY` findings.

### Charge rail

The instance is represented by six operational cells:

| Cell | Primary evidence |
|---|---|
| Continuity | Backup, journal, and write-daemon state |
| Capacity | Database, journal, disk, and shared-memory headroom |
| Flow | Locks, busy processes, sessions, and contention |
| Automation | Tasks, task history, monitor freshness, and scheduled work |
| Security | Audit state, exposed services, credentials metadata, and effective privileges |
| License | Usage and remaining licensed headroom |

Charge is the weighted proportion of applicable, observed checks currently
passing. Coverage is the weighted proportion of applicable checks with current,
valid evidence.

```text
charge   = passing observed weight / observed applicable weight
coverage = observed applicable weight / total applicable weight
```

The two values are always displayed together. If coverage is zero, charge is
shown as `UNKNOWN`, not `0%` or `100%`. A critical rule may cap a cell's state,
but every cap must be declared in the policy and visible in the explanation.

### Warning and instruction panel

The primary panel displays one selected finding with:

- condition;
- operational consequence;
- urgency and evidence freshness;
- supporting observations;
- missing or conflicting evidence;
- the rule in plain language;
- other symptoms that would change the recommendation.

The first layer contains no endpoint names or raw records. An evidence drawer
provides those details.

### Action panel

The adjacent action panel displays:

- recommended action and alternatives;
- reason for recommendation order;
- current prerequisite checklist;
- affected resources and expected effect;
- reversibility and rollback path;
- authorization requirement;
- expected verification and deadline;
- preparation, preview, execution, and escalation controls.

Only one primary action is emphasized. Alternatives remain visible for expert
review. A disabled action explains its exact blocker.

### Management surfaces

Each contest-required management area remains directly navigable. Selecting a
finding opens the relevant resource in context rather than making the operator
search for it again.

### Language

Messages follow this order:

```text
What happened -> Why it matters -> What proves it -> What to do -> How success is proved
```

Labels describe outcomes: `Run and verify`, `Refresh evidence`, `Prepare
change`, and `Export escalation packet`. Battery does not use unexplained IRIS
terminology in the first layer.

## Example policy

```yaml
id: continuity.backup.failed
version: 1
applies_to: scheduled_backup_task
when:
  all:
    - latest_task_result == FAILED
    - newer_successful_run == FALSE
    - task_observation_age < 60s
finding:
  state: ACT
  summary: The scheduled backup did not complete.
  consequence: Recent data may not have the expected recovery point.
recommend:
  - action: task.rerun_and_verify
    when:
      all:
        - effective_task_privilege == TRUE
        - backup_destination_available == TRUE
        - conflicting_backup_running == FALSE
  - action: continuity.export_escalation
    otherwise: true
```

Its corresponding action must verify both a successful task result and a new
backup completion time after the execution began.

## Architecture

The contest implementation consists of:

1. **Same-origin gateway:** authenticates to IRIS, normalizes API behavior, and
   prevents credentials from entering browser storage.
2. **Capability discovery:** calls `/info`, records product version and effective
   privileges, and marks supported operations.
3. **Intent planner:** converts requested outcomes into candidate actions and
   evidence requirements.
4. **Collectors:** small read-only adapters that convert API responses into
   observations.
5. **Ledger:** append-only sanitized event storage and deterministic projection.
6. **Policy evaluator:** pure rule evaluation over observations.
7. **Rule registry:** provenance, assumptions, counterexamples, validation
   evidence, and minimum execution state for every rule.
8. **Action registry:** declared preparation, mutation, and verification
   contracts.
9. **Execution service:** certificate validation, idempotency, bounded IRIS
   calls, and receipt creation.
10. **Web interface:** decision panels and direct management surfaces.
11. **Scenario harness:** synthetic observations and a controlled IRIS demo
   environment for repeatable judging.

Collectors and policy evaluation remain separately testable from IRIS and the
web interface. The OpenAPI client is normalized for missing operation IDs,
undeclared per-operation authentication, and known schema inconsistencies.

## Security and privacy

- IRIS credentials remain server-side and are never persisted in browser
  storage.
- Mutation endpoints reject requests without a valid preflight certificate.
- Every parameter is validated against its action contract.
- API and application logs redact authorization headers, passwords, tokens,
  private keys, wallet values, and configured sensitive fields.
- Secret-management receipts record identifiers and outcomes, never values.
- Raw log searches are bounded by time, result count, and privilege.
- Exported evidence is sanitized and states which fields were removed.
- Observation-only mode exposes no state-changing route to the browser.
- Synthetic public fixtures contain no production-derived records.

## Model boundary

No LLM may determine truth, severity, action eligibility, authorization,
execution parameters, or verification success.

An optional model may rewrite an already-established finding into plainer
language or perform an offline adversarial review of policies and tests. Its
output is untrusted, cannot change the underlying decision, and is not required
for normal operation. Astra is reserved for final review after deterministic
validation passes.

## Clean-room boundary

The public repository may contain the concepts specified here, public IRIS API
contracts, original Battery code, synthetic fixtures, tests, and public build
instructions.

It must not contain Armadaforge source, internal terminology required to operate
Armadaforge, infrastructure topology, private hostnames, credentials, prompts,
production records, private transports, or deployment conventions. Battery does
not import Armadaforge packages or require access to Armada infrastructure.

## Acceptance scenarios

The release is accepted only when the scenario harness demonstrates:

1. **Healthy instance:** all available cells explain their state and charge is
   accompanied by coverage.
2. **Insufficient privilege:** the relevant fact becomes `UNKNOWN` or blocked,
   the action is disabled, and the required privilege is explained.
3. **Stale evidence:** a previously eligible action becomes ineligible until
   preparation refreshes its observations.
4. **Failed scheduled task:** Battery correlates task history and logs,
   recommends an eligible response, and verifies the result.
5. **Assurance due:** no incident exists, but an expiring obligation produces a
   preparation task and renews its evidence.
6. **Conflicting observations:** the conclusion becomes conflicted and mutation
   is blocked.
7. **Concurrent operation:** preflight detects the conflict or execution rejects
   a now-invalid certificate.
8. **Successful mutation:** a transport success remains unverified until the
   declared postcondition is newly observed.
9. **Failed verification:** Battery reports `VERIFIED_FAILURE` or
   `EXECUTED_UNVERIFIED` and produces a sanitized escalation receipt.
10. **Repeated submission:** the idempotency key returns the original action
    attempt without repeating the change.
11. **Secret operation:** no secret value appears in the ledger, UI logs,
    receipt, or exported packet.
12. **Replay:** rebuilding projections from the same ledger and policy versions
    produces identical findings and action eligibility.
13. **Intentional administration:** an operator requests an outcome with no
    existing incident, and Battery plans, prepares, executes, and verifies it.
14. **Wrong-rule defense:** a plausible but incomplete recommendation remains
    blocked until its counterexample and live-validation requirements pass.
15. **Ambiguous transport:** a lost response produces `OUTCOME_UNKNOWN`, no
    automatic retry, and later reconciliation from fresh evidence.

## Delivery order

1. Prove a live vertical slice: authenticate, inspect one scheduled task,
   express an intent to run it, prepare, execute, and verify its history result.
2. Normalize the OpenAPI client and implement the same-origin gateway.
3. Implement `/info` capability discovery and observation-only mode.
4. Define the five domain objects, rule registry, and append-only ledger.
5. Implement collectors for monitor, tasks, processes, databases, journals,
   license, locks, audit, web applications, and logs.
6. Implement pure three-valued policy evaluation, counterexample, and replay
   tests.
7. Build the charge rail, warning panel, evidence drawer, and action panel.
8. Add remaining preflight, execution, verification, and receipt contracts.
9. Complete direct management surfaces against the workflow coverage matrix.
10. Add the remaining synthetic scenarios and containerized demonstration.
11. Run security, accessibility, clean-room, and adversarial policy review.

## Non-goals for the contest release

- autonomous execution of state-changing actions without declared policy;
- probabilistic diagnosis presented as fact;
- replacement of a full external observability or incident-management stack;
- ingestion of arbitrary third-party plugins;
- a generic automation framework;
- dependence on Armadaforge or a hosted Armada service;
- decorative battery metaphors that obscure operational meaning.

## Release definition

The contest release is complete when all requested management areas are usable,
the acceptance scenarios pass against synthetic fixtures, the selected live
scenarios pass against a supported IRIS container, every mutation produces a
receipt, and the README lets a judge install and demonstrate the complete
observe-to-verify loop without private infrastructure.
