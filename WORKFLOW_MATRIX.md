# Armada Battery workflow coverage

The matrix is the release boundary. `slice` means the first end-to-end workflow
exists. `planned` means the public API route is known. `research` means live
IRIS behavior must be observed before Battery may promise or automate it.

| Area | Operator outcome | SysAdmin API operations | Required privilege | Verification | Status |
|---|---|---|---|---|---|
| Capability | Establish product, version, namespaces, and effective access | `GET /info` | Any supported `%Admin` privilege | Current identity and capability snapshot | slice |
| Tasks | List scheduled tasks | `GET /v1/task/` | `%Admin_Operate:U` or `%Admin_Task:U` | Complete response or explicit truncation/denial | slice |
| Tasks | Inspect one task and recent results | `GET /v1/task/info?id=`, `GET /v1/task/history/` | Operate or Task; history requires Operate | Target and history are tied to the requested ID | slice |
| Tasks | Run an existing task now | `POST /v1/task/run` | `%Admin_Task:U` | New terminal history row after the attempt | slice |
| Tasks | Resume or suspend a task | `PUT /v1/task` with the `Suspended` field | `%Admin_Task:U` | Fresh task detail reports expected state | planned |
| Tasks | Schedule an existing task | `PUT /v1/task` | Operate or Task | Readback matches normalized schedule fields | slice |
| Tasks | Create or edit task definition | `POST /v1/task`, `PUT /v1/task` | Operate or Task | Readback matches normalized requested fields | planned |
| Tasks | Delete a task | `DELETE /v1/task` | Operate or Task | Subsequent read returns not found | planned |
| Web applications | Create a bounded REST application | `PUT /v1/web-app` | `%Admin_Secure:U` | Configuration readback matches requested fields | slice |
| Web applications | Change an existing application | `/v1/web-app` operations | `%Admin_Secure:U` | Configuration readback and availability probe | planned |
| REST APIs | Discover and exercise a bounded request | Web-app inventory and selected API route | Target-specific | Sanitized response satisfies declared assertion | planned |
| Permissions | Grant an existing reviewed role to an existing user | `GET/PUT /v1/security/user`, `GET /v1/security/role` | `%Admin_Secure:U` | Direct role membership readback preserves prior roles | slice |
| Permissions | Calculate effective inherited access | `/v1/security/role`, `/v1/security/resource` operations | `%Admin_Secure:U` | Effective access independently recalculated | planned |
| Security metadata | Inventory TLS configurations and wallet collections | `GET /v1/security/ssl-configuration/`, `GET /v1/wallet/` | Corresponding security privilege | Current metadata count; secret values are never requested | slice |
| Secrets | Change wallet, certificate, or OAuth material | Wallet, X509, SSL, and OAuth operations | Corresponding security privilege | Metadata and functional probe without secret readback | research |
| Processes | Inspect current processes | `GET /v1/process/` | `%Admin_Operate:U` | Bounded current process count or explicit denial | slice |
| Processes | Control a process | Process mutation operations | `%Admin_Operate:U` | Fresh process state or expected disappearance | planned |
| Capacity | Inspect system resources and databases | `GET /v1/monitor/dashboard/system-resources`; databases have no v1 endpoint and are reported `UNAVAILABLE` | Endpoint-specific | Current aggregate; database inventory is unavailable in v1 | slice |
| Database | Mount, compact, defragment, or check integrity | Database and async operations | Endpoint-specific | Readback or terminal asynchronous result | research |
| Journals | Inspect journal settings and recent files | No IRIS v1 endpoint; reported `UNAVAILABLE` | `%Admin_Journal:U` or specified privilege | Explicit unavailability instead of fabricated data | slice |
| Audit | Inspect auditing state and event definitions | `GET /v1/security/audit/enabled`, `GET /v1/security/audit/event/` | `%Admin_Secure:U` | Current setting and bounded event count | slice |
| Logs | Find records relevant to a condition | Audit and subsystem record operations | Endpoint-specific | Bounded query with explicit coverage | planned |
| License | Inspect licensed headroom | `GET /v1/monitor/license-usage` | Endpoint-specific | Current aggregate with capture timestamp | slice |
| Locks and sessions | Inspect contention and sessions | Lock and web-session operations | Endpoint-specific | Current complete or explicitly bounded list | planned |

## Task-slice release gate

The first slice is complete when the synthetic adapter and then a supported IRIS
container demonstrate:

1. capability discovery;
2. task and history collection;
3. an operator intent to run a task even when no incident exists;
4. a fresh privilege and conflict preflight;
5. a rule whose rationale, assumptions, contradictions, counterexamples, and
   validation state are visible;
6. a blocked change when the rule has not reached its required validation state;
7. single-use execution authorization and idempotent submission;
8. a durable attempt recorded before the request;
9. verification from a new history observation;
10. `OUTCOME_UNKNOWN` after an ambiguous transport result and reconciliation
    without automatically repeating the task.

No row advances from `research` based only on the OpenAPI description.
