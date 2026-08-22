# Nexora Polyglot Data Ownership and Deployables v0.1

**الحالة:** target ownership model; no database schemas/services are provisioned.  
**قاعدة غير قابلة للتفاوض:** يمكن أن تتشارك الوحدات PostgreSQL cluster ماديًا في البداية، لكن **لكل table/schema منطقي owner واحد فقط**.

## وحدات النشر الأولية

| unit | language | responsibility | scaling boundary | لا ينشأ كخدمة مستقلة قبل |
|---|---|---|---|---|
| `control-plane` | Laravel/PHP | business API، identity/RBAC policy، tenant/course/assignment/catalog/authoring/admin | stateless replicas by API/business workload | يظل module حتى بداية المنتج؛ لا حاجة لفصل billing/authoring/realtime مبكرًا. |
| `platform-plane` | Go | session coordinator/registry، grant verification، lease/fencing، routing، relay/backpressure، future realtime | connection/RPS، lease partitions، outbox backlog | وجود session concurrency/failure/realtime trigger موثق. |
| `simulation-worker` | Python + C++ Pulse | VPE/Pulse owner لجلسة واحدة، client-safe projection، session-local logic | active sessions/resource profile | لا ينقسم Pulse/VPE داخل session. |
| `unity-client` | C# future | rendering/input/visualization | client distribution | Gate 0 + medical review + separate Unity decision. |

`ai-worker` و`analytics-consumer` و`authoring-service` و`billing-service` و`realtime-gateway` are future candidates, not a default deployable list. A component extraction requires ownership/scale/failure/deployment proof (`PLAT-BOUNDARY-01`).

## PostgreSQL logical ownership

| schema/table domain | logical owner | writes allowed | reads allowed | mutation boundary |
|---|---|---|---|---|
| `control_plane.*` | Laravel | Laravel migrations/repositories only | Go only through a versioned read/grant API; Python none by default | Laravel API / Control Plane command. |
| `platform.*` | Go | Go migrations/repositories only | Laravel through platform query/API; Python only through typed command/context | Go platform contract. |
| `session_registry.*` | Go | Go coordinator only | Laravel sees lifecycle projection/command result; Python sees only own lease/context | Go session command/query contract. |
| `outbox.*` | corresponding transactional domain | owning service inserts/polls its own rows | relay uses explicit contract/role; no generic cross-table writer | owner transaction then relay. |
| artifact references | owner domain (Laravel or Go) | owner records reference/authorization | authorized API only | ObjectStorage + owner metadata. |
| simulation-local state | Python worker contract | Python inside its scoped store/runtime only | Go receives portable session outcome/event | typed internal command/event. |
| analytics/lake | derived consumer owner | consumers write derived data only | reporting/query layer | events/object export, never authoritative mutation. |

The PostgreSQL cluster is not a shared integration bus. Cross-service direct SQL writes are prohibited, including Laravel writing `session_registry`, Go writing billing/course tables, and Python writing users/memberships/assignment tables. Shared reads are minimized, documented, and cannot create a hidden dependency on another service's schema.

## outbox and allocation consistency

A user action that starts or assigns simulation has two independently owned truths: Laravel's assignment/authorization state and Go's session lifecycle. It must never depend on an unsafe `commit Laravel DB; call Go synchronously; hope both succeeded` sequence.

```text
Laravel transaction
  ├─ authorize assignment and write control-plane mutation
  └─ write immutable `simulation.start.requested` outbox record
                    │ same commit
                    ▼
         relay delivers at-least-once command/event
                    │
                    ▼
Go Platform transaction
  ├─ idempotently claim command_id
  ├─ create/update Go-owned session registry record
  └─ write platform outbox response / allocation event
                    │
                    ▼
Python worker receives a trusted Go command after session lease/routing
```

| failure case | accepted behavior | recovery requirement |
|---|---|---|
| Laravel transaction rolls back | no committed start request | caller receives failure; no platform allocation. |
| commit succeeds, relay unavailable | request remains pending in Laravel outbox | retry/alert; no unsafe direct call. |
| relay redelivers | Go deduplicates stable command/event ID | idempotency ledger/state transition guard. |
| Go registry write fails | no worker allocation signal | retry or terminal command result; audit. |
| Go allocates then response relay fails | Laravel projection may be stale | platform event/outbox retries; user query reconciles by command ID. |
| Python worker unavailable | session stays allocatable/pending or is paused by policy | Go controls retry/admission; no duplicate owner. |
| stale worker attempts write | rejected by lease generation/fencing | evidence/audit + recovery-needed transition. |

This extends—not replaces—the existing transactional outbox semantics spike. The current Python SQLite class is a **reference/test implementation of portable semantics**; it is not a mandate for Python to own the production Go outbox relay or Platform Plane.

## object storage and cache

| capability | owner/rule | exclusion |
|---|---|---|
| object storage | `ObjectStorage` contract portable; object bytes have hash/classification/retention intent; Control/Platform owner stores authorization reference | object key/public URL is not authorization; current S0 checkpoints do not claim durable replay. |
| Redis/Valkey | future cache/rate-limit/ephemeral route/lease optimization only, scoped by owner | no authoritative history, assignment, tenant policy, or physiology truth. |
| ClickHouse | future derived analytics owner | not a command source or source of truth. |
| S3+Parquet/Iceberg | future governed export/lake path | no lake before data ownership, lineage, use case, and lifecycle evidence. |
| DynamoDB/Cassandra | candidate only after `KV-02` proves key-pattern/consistency/ops need | no adoption because of user-count labels. |

## contracts at boundaries

| boundary | primary target | data allowed | data prohibited |
|---|---|---|---|
| public product API | HTTPS REST/JSON, Laravel | business resources, submitted commands, product errors | internal lease/Pulse truth. |
| future realtime client | WebSocket through Go boundary | client-safe projection/allowed commands | direct Pulse/VPE/tenant authority. |
| Laravel ↔ Go | gRPC/Protobuf candidate for high-value internal commands or REST initially if simpler | scoped session grant, command ID, tenant/session IDs, allowed scope | raw browser token as trust, cross-schema write. |
| Go ↔ Python | gRPC/Protobuf candidate when worker process/network boundary exists | trusted session command, route/lease generation, client-safe projection/events | business-table mutation or Pulse internals. |
| event stream | portable JSON Schema event envelope now; evaluate Protobuf/Avro only with broker/schema registry trigger | immutable minimized events/artifact refs | PII/secrets/raw artifact bytes. |

Protocol Buffers can generate bindings across C++, C#, PHP, Python and Go, but require compatibility governance; field numbers are never reused and API messages are separate from storage messages.[1] [2] This makes it a candidate for internal command contracts, not a reason to rewrite S0 loopback HTTP/JSON or force every event into Protobuf.

## migration from current repository

1. Keep `src/nexora_vpe` and Pulse integration intact.
2. Reclassify `src/nexora_vpe/platform/*` as portable **reference contracts/test semantics**: IDs, tenant scope, event envelope, outbox behavior, object metadata.
3. When a Go Platform Plane is authorized, reproduce approved semantics in Go and validate cross-language fixtures/contract tests; do not import Python implementation as the production platform runtime.
4. When Laravel Control Plane is authorized, create a Laravel-owned schema/migration/authorization package without moving S0 code.
5. Add `/contracts` only after selecting codegen/versioning CI; do not physically restructure this repository under the architecture decision alone.

## references

[1]: https://protobuf.dev/overview/ "Protocol Buffers: Overview"
[2]: https://protobuf.dev/best-practices/dos-donts/ "Protocol Buffers: Best Practices"
[3]: ../contracts/platform-event-envelope-v0.1.md "Nexora Platform Event Envelope"
[4]: ../contracts/object-storage-contract-v0.1.md "Nexora Object Storage Contract"
