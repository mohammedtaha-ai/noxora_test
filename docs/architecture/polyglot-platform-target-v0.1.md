# Nexora Polyglot Platform Target v0.1

**الحالة:** target architecture — **Scale-ready, not scale-now**.  
**يستبدل:** التوصية اللغوية Python-first فقط في الوثائق السابقة، ولا يلغي S0 Python/C++ المثبت أو عقود المنصة المحمولة.  
**غير منفذ:** لا Laravel app، ولا Go service، ولا gRPC/WebSocket gateway، ولا Unity، ولا database/queue/cloud provisioning.

## المبدأ الحاكم

> **Right language for the right workload، لا Python everywhere ولا microservices everywhere.**

تتبع ملكية اللغة workload وdomain ownership وfailure domain وconcurrency profile وecosystem، لا تفضيلًا عامًا للسرعة. تبقى حدود النشر صغيرة في البداية: Control Plane Laravel، Platform Plane Go عند الحاجة، Simulation Worker Python+Pulse، وclient C#/Unity مستقبلًا. يمكن أن تكون هذه الوحدات modules أو deployables محدودة وفق المرحلة؛ لا يعني الرسم أن جميع الصناديق خدمات مستقلة اليوم.

## المخطط المستهدف

```text
                                    CLIENTS
                         Unity/C# future · Web · Instructor
                                      │
                    HTTPS REST/JSON ─┼─ future WebSocket realtime
                                      ▼
                         Go Edge / Realtime Layer (when justified)
                                      │
                 ┌────────────────────┴────────────────────┐
                 │                                         │
                 ▼                                         ▼
       Laravel/PHP Control Plane                    Go Platform Plane
       auth · RBAC · tenants · courses              session coordinator
       assignments · authoring · admin              registry · lease/fencing
       billing later · business audit                routing · relay/backpressure
                 │                                         │
                 └──────────── command/event grant ────────┘
                                      │
                                      ▼
                         Python Simulation Worker (per session)
                         VPE time/queue/scenario orchestration
                                      │
                                      ▼
                            C++ Pulse / native numerical core

  Async only: transactional outbox → SQS initially / event backbone later
                       ├─ Go operational consumers
                       ├─ Python AI/ML workers
                       └─ analytics / ClickHouse or lake later
```

## ownership matrix

| domain | language/owner | owns | must not own | independent scale unit |
|---|---|---|---|---|
| business Control Plane | Laravel/PHP | identity integration, institutions, tenants, memberships, RBAC policy, programs/courses/cohorts, assignment, scenario catalog metadata/versioning, authoring/instructor/admin workflows, billing later | Pulse, simulation clock, live physiology, session lease, high-rate telemetry, AI/ML execution | stateless control-plane replicas by business HTTP/API load. |
| edge/realtime/platform | Go | future edge/realtime gateway, verifiable session authorization context, session registry/coordinator, lease/heartbeat/fencing, routing, relay, rate-limit/backpressure operations | medical truth, Pulse, scenario semantics, billing/course CRUD just because of performance | gateway by connections/RPS; coordinator by lease/session partitions; relay by backlog. |
| simulation | Python | existing VPE, simulation orchestration/time/action queue, scenario runtime, observation logic, formative algorithms, future AI/ML orchestration | global auth, billing, institution management, generic edge routing, uncontrolled business-table writes | worker pool by active sessions / resource profile. |
| native scientific | C++ | Pulse bridge, physiology/numerical core, future numerical components after requirement/benchmark | tenant/business auth, queue orchestration, client protocol | owned within a simulation worker process, not independently multi-owned per session. |
| interactive client | C#/Unity future | rendering, FAST probe, visualization, input, animation | authoritative business or medical/simulation truth, clock, direct Pulse access | client installations; no server ownership. |
| async AI/analytics | Python/Go/analytics technology later | AI/ML jobs, consumer transforms, derived reporting | live-session gating, canonical truth | worker/consumer partitions by queue/model/query workload. |

Laravel supports authorization gates/policies and migrations, and has queue integration, which supports its fit for conventional business workflows when guarded by explicit tenant policies.[1] [2] Go is chosen only where cancellation/deadline propagation and concurrent request/service coordination are central; its `Context` model is appropriate to pass such values across Go API boundaries, not as evidence that every service needs Go.[3]

## the hot path

The **live-simulation hot path** is deliberately narrow:

```text
Future Unity client
   ↓ HTTPS command / future WebSocket
Go realtime/platform boundary
   ↓ typed internal command with scoped session grant
Python VPE worker
   ↓ native bridge
C++ Pulse
```

Laravel does not sit on physiology progression; analytics and LLM services are not required to advance a session. Existing S0 remains local-only: `VpeClientFacade` + loopback HTTP/JSON + `VpePacedHost` continue to own the present headless boundary and are not replaced by this target.

## the control path

```text
User/instructor/admin
   ↓ HTTPS REST/JSON
Laravel Control Plane
   ↓ authenticate + authorize tenant/membership/assignment
   ↓ commit business mutation + owning outbox event/command request
Reliable relay / Go Platform Plane
   ↓ validate grant and allocate/routable session
Python simulation worker starts/owns session
```

No direct `Laravel database commit + synchronous Go call` is treated as reliable state transfer. A Control Plane transaction commits its owning mutation and immutable outbox record together. The relay retries idempotently; a platform command carries a stable command/request ID. Laravel must not write Go-owned session registry tables, and Go must not write Laravel-owned course/billing tables.

## async path

```text
Simulation worker or Control Plane owner
   ↓ canonical portable event in owner outbox
Go relay / future SQS or event backbone
   ├─ Python AI/ML worker (derived)
   ├─ analytics consumer (derived)
   └─ reporting/notifications (derived)
```

Slow AI, reporting, ClickHouse, or queue consumers never decide the next physiology tick. A queue/broker outage produces pending outbox/backlog under policy, not a claim that the live worker can run indefinitely without durable policy. The transactional-outbox contract retains at-least-once semantics; consumer idempotency remains required.[4]

## authorization boundary

Laravel owns business authorization policy and emits a short-lived, scoped session grant only after validating identity, membership, role, tenant, assignment, and scenario entitlement. Go verifies issuer/audience/expiry/signature and binds the grant to `principal_id`, `tenant_id`, `session_id`, allowed command scope, and correlation ID. Python receives only a trusted internal command/context, not a browser identity claim.

`tenant_id` supplied by Unity/web is never trusted as authorization. No JWT/OIDC/SSO stack is implemented in this batch. The future token design requires key rotation, revocation/expiry policy, service identities, audience isolation, replay controls, threat model, and negative cross-tenant tests.

## scaling and failure isolation

| unit | scale signal | target behavior on dependent failure | not yet promised |
|---|---|---|---|
| Laravel Control Plane | API/CRUD latency, DB/pool pressure, job backlog | no new authorized allocation/mutation while unavailable; existing live session behavior follows durable policy | continued operation of every live session through all control-plane failure modes. |
| Go gateway | active connections, RPS, reconnect rate | reconnect/reroute client to valid session route | concurrent worker ownership or transparent session handoff. |
| Go coordinator | active leases, heartbeat latency, registry contention | stop stale claims with fencing; pause/recover policy | production distributed lease implementation. |
| Python simulation worker | active sessions, tick time, queue age, memory/Pulse health | isolate failure to its owned session; `PAUSED_BY_SYSTEM`/recovery-required policy | seamless resume or active-active worker. |
| AI worker | model queue age/inference resources | derived result delayed/absent | AI required for live simulation or assessment truth. |
| analytics consumer | partition/backlog/query lag | dashboards stale/rebuildable | analytics as command source. |

## evidence before a new deployable

A module becomes a separate deployable only if it has at least one distinct lifecycle, failure, scaling, trust, or deployment cadence need and passes `PLAT-BOUNDARY-01`: documented owner, contract, SLO/baseline, observability, failure/rollback behavior, tenant review, and load/failure test. The initial target is at most four ownership units, not dozens of microservices.

## repository target — design only

| option | initial recommendation | rationale |
|---|---|---|
| monorepo | preferred for the early cross-language team | one contract source, atomic API/schema changes, shared docs/CI, simpler coordinated S0 preservation. |
| multi-repo | defer until access/release/cadence ownership requires it | independent repos add version coordination and contract publication overhead. |

A future monorepo may contain `/apps/control-plane-laravel`, `/services/platform-go`, `/services/simulation-python`, `/native/pulse-bridge`, `/clients/unity`, `/contracts/{protobuf,events,schemas}`, `/data`, and `/docs`. This repository is **not physically restructured**; verified S0 code stays where it is until a migration ADR and acceptance plan approve a move.

## AWS mapping — illustrative only

| ownership unit | initial AWS candidate | later scaling choice | not in this batch |
|---|---|---|---|
| Laravel control-plane | ECS/Fargate + RDS PostgreSQL | replicas/autoscaling after measurements | provision/deploy. |
| Go platform | ECS/Fargate | gateway/coordinator separation after trigger | service build/deploy. |
| simulation worker | ECS/Fargate/custom worker compute | session pool by measured resource profile | containerization/fleet. |
| artifacts | S3 | lifecycle/replication by policy | bucket/KMS/IAM. |
| async | SQS | MSK/Kinesis after event trigger | queue/broker. |
| cache | ElastiCache | policy-bound cache/lease only | Redis/Valkey. |
| telemetry/analytics | CloudWatch/OTel then ClickHouse/S3+Parquet | lake/Iceberg after evidence | analytics stack. |

## explicit non-decisions

This document does not authorize Laravel, Go, gRPC, WebSocket, SQS, Kafka, Redis, ClickHouse, Kubernetes, multi-region, SSO, AI Patient, or Unity implementation. It does not change technical M3/Gate 0/medical-review judgments. It corrects ownership targets so future implementation does not accidentally turn Python reference helpers into the default platform runtime.

## references

[1]: ../research/polyglot-platform-source-notes.md "Laravel authorization and migrations evidence"
[2]: https://laravel.com/docs/13.x/queues "Laravel 13.x: Queues"
[3]: https://go.dev/blog/context "Go Concurrency Patterns: Context"
[4]: ../validation/transactional-outbox-sqlite-spike.md "Transactional Outbox SQLite Spike"
