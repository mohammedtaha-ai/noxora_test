# تقرير 007: مراجعة معمارية Nexora Scale-Ready متعددة اللغات

**التاريخ:** 2026-08-23.  
**الحالة:** محدث للمراجعة المعمارية؛ لا يصرح بتنفيذ خدمات أو Unity.
**النطاق:** تصحيح هدف المنصة من توصية Python-centric إلى ownership polyglot منضبط، مع الحفاظ على كل boundaries القابلة للتوسع التي سبقت التصحيح.

## الحكم التنفيذي

**POLYGLOT PLATFORM ARCHITECTURE: ACCEPT.**

التصميم يقبل Laravel/PHP كـControl Plane، وGo كـPlatform/Realtime Plane عند evidence، وPython+C++ كـSimulation/Native Core، وC#/Unity كعميل مستقبلًا. لا تُختار اللغات كحكم سرعة عام؛ بل لأن business workflows وauthorization والمهاجرات تختلف عن session coordination/high-connection I/O وعن VPE/AI orchestration وعن numerical physiology. يبقى S0 محميًا: VPE يملك simulation time، Pulse single-owner لكل session، والعميل لا يملك truth أو clock.

**CURRENT S0 IMPLEMENTATION: KEEP.** لا توجد إعادة كتابة VPE أو Pulse أو Facade/host/loopback transport. تعاد تسمية Python platform helpers وظيفيًا: هي reference/test semantics لعقود محمولة، وليست التزامًا بأن Python يملك Platform Plane production.

> لا يغير التصحيح الأحكام المستقلة: **Gate 0 = UNTESTED**، و**Medical Review = UNVALIDATED**، وUnity لا يبدأ في هذه الدفعة.

## ما تم تصحيحه وحفظه

| الأصل | القرار بعد التصحيح |
|---|---|
| Control Plane / Simulation Data Plane separation | **محفوظ**؛ Laravel يملك business truth، وGo/Python/C++ يملكون platform/session/simulation boundaries. |
| tenant-aware IDs/events/outbox/object storage | **محفوظ**؛ صار Platform Event Envelope JSON Schema محايدًا للغة، مع Python reference serialization يخرج `tenant_id` top-level. |
| PostgreSQL target | **محفوظ ومقيد**: physical cluster واحد ممكن؛ logical schema/table owner واحد فقط. |
| future queue/analytics/lake/NoSQL triggers | **محفوظ**؛ لا provision مبكر. |
| language strategy السابقة | **مصَححة**: لا Python-first Control Plane؛ Laravel هو المرشح الأساسي للـbusiness backend وGo للمنصة عند trigger. |
| S0 transport | **محفوظ**: HTTP/JSON loopback لا يستبدل بـgRPC في هذه الدفعة. |

## target architecture

```text
                                  CLIENTS
                    Unity/C# future · Web · Instructor
                                   │
                HTTPS REST/JSON ──┼── future WebSocket
                                   ▼
                    Go Edge / Realtime (when justified)
                                   │
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
     Laravel/PHP Control Plane                    Go Platform Plane
     auth/RBAC/tenants/courses                    session registry/lease/fencing
     assignments/catalog/authoring                routing/backpressure/outbox relay
              │                                         │
              └──── reliable command/event grant ───────┘
                                   │
                                   ▼
                     Python Simulation Worker per session
                     VPE time/queue/scenario orchestration
                                   │
                                   ▼
                          C++ Pulse/native numerical core

Async only: owner outbox → SQS later / event backbone later
             → Go operations · Python AI/ML · derived analytics
```

## language and service ownership matrix

| Domain | Language | Why | Data owner | Scale unit |
|---|---|---|---|---|
| Control Plane | Laravel/PHP | business CRUD/workflows, authorization policies, migrations, queues/ecosystem | `control_plane.*` | stateless replicas by business API load. |
| edge/realtime/platform | Go | cancellation/deadline propagation, I/O/service coordination, session lease/routing when evidence exists | `platform.*`, `session_registry.*` | gateway by connections/RPS; coordinator by lease partitions; relay by backlog. |
| simulation | Python | existing VPE, scenario/runtime/observation logic, future AI/ML orchestration | session-local explicit contract only | workers by active session/resource profile. |
| native scientific core | C++ | existing Pulse/native numerical boundary | embedded in worker/session process | session-owned native process boundary. |
| client | C#/Unity future | rendering, input, FAST probe, visualization | none authoritative | client distribution. |
| AI/analytics | Python/Go/analytics technology future | isolated derived workload | derived store/lake only | workers/consumers by queue/model/partitions. |

Laravel's documented gates/policies and migrations support its Control Plane fit; Laravel queues remain an async business-workflow capability, not session coordination ownership.[1] [2] Go `Context` formally carries cancellation, deadlines, and request-scoped values across concurrent API boundaries, supporting its candidate role for platform coordination—not a blanket language claim.[3]

## paths and boundaries

| path | route | invariant |
|---|---|---|
| live hot path | future Unity/Web → Go realtime/platform → Python VPE → C++ Pulse | Laravel, analytics, and LLM are not required for physiology progression. |
| business control path | user → Laravel auth/assignment transaction → Laravel outbox → Go allocator → Python worker | no unsafe `commit + direct call` dual-write; each owner is idempotent. |
| async path | owner outbox → queue/bus at trigger → AI/analytics/reporting consumers | consumer failure never determines a tick or canonical session truth. |
| local S0 | local client → HTTP/JSON loopback → Facade → VPE host | unchanged; no cloud service conclusion. |

## data ownership and consistency

| logical area | owner | allowed write path | forbidden |
|---|---|---|---|
| `control_plane.*` | Laravel | Laravel migrations/repositories | Laravel writes to `session_registry`; Python business-table mutation. |
| `platform.*` / `session_registry.*` | Go | Go coordinator/repositories | Go course/billing/membership writes. |
| outbox | owning transactional domain | owner mutation + immutable outbox in one transaction | generic shared outbox writer/dual-write broker logic. |
| VPE/Pulse/session-local state | Python/C++ worker | scoped session contract | tenant/user/assignment direct mutation. |
| artifacts | owner metadata + ObjectStorage reference | authorized owner request | public object key as authorization. |
| analytics/lake | derived consumer | event/object export projection | command/source-of-truth usage. |

A Laravel start/assignment commits its business mutation and an owner outbox record atomically. Relay delivery may repeat; Go deduplicates stable command IDs before committing the Go-owned registry state/outbox. If relay fails, backlog accumulates and retries; if a worker fails, the failure remains session-scoped and no seamless resume is promised. The local SQLite spike validates this semantics shape, not a PostgreSQL/Go production implementation.[4]

## contract strategy

| interface | target | status |
|---|---|---|
| external product API | HTTPS REST/JSON | target for conventional resources; unimplemented. |
| future realtime | WebSocket through Go | target only; no gateway. |
| Laravel ↔ Go / Go ↔ Python | gRPC/Protobuf candidate when typed command/streaming value is proven | no `.proto`, codegen, or service now. |
| event | portable JSON Schema envelope now; future Protobuf/Avro assessed by broker trigger | `schemas/platform-event-envelope.schema.json` implemented; Python class is reference. |
| local S0 client | existing HTTP/JSON loopback | verified and unchanged. |

Protocol Buffers are language-neutral and generate bindings for target languages; gRPC lists PHP, Go, Python, C#, and C++ support. Compatibility still requires governance: tags are never reused, deleted tags reserved, and RPC messages remain separate from storage messages.[5] [6] This is why gRPC/Protobuf is a candidate, not automatic infrastructure.

## scaling, capacity, and failures

The existing illustrative model remains non-forecast: 5% active sessions, 8 canonical events/min/session, 2 telemetry samples/s/session, and hypothetical 2 MiB checkpoints per 10 minutes. It shows why telemetry and artifacts require isolation from OLTP/event payloads, not why Kafka/ClickHouse must be deployed today.[7]

| unit failure | intended isolation | not yet implemented/promise |
|---|---|---|
| Laravel outage | existing simulation ideally follows previously durable policy; new business allocation halts | full production continuation semantics. |
| Go gateway outage | client reconnect/reroute to a valid route | distributed gateway/service deployment. |
| one Python/Pulse worker crash | only owned session transitions to controlled failure/recovery-required path | seamless handoff/resume. |
| queue/event outage | durable owner outbox pending/retry | deployed outbox relay/broker/DLQ. |
| AI/ClickHouse outage | derived results/dashboards stale or absent | any live-session gating. |

## AWS mapping — illustrative, cloud-neutral contracts first

| capability | possible AWS mapping | deferred condition |
|---|---|---|
| Laravel/Go/Python units | ECS/Fargate | no deployment in this batch. |
| OLTP | RDS/Aurora PostgreSQL | schema/role/migration/ops review. |
| artifacts | S3 | no bucket/KMS/IAM/lifecycle. |
| initial async | SQS | `EVT-QUEUE-01` evidence. |
| backbone | MSK/Kinesis | `EVT-BUS-02` evidence. |
| cache | ElastiCache | explicit ephemeral use/fallback. |
| analytics/lake | ClickHouse plus S3/Parquet/Iceberg | query/lake trigger. |
| observability | CloudWatch/OTel | service implementation. |

## implemented now versus deliberately deferred

| Implemented now | Target architecture | Deliberately deferred |
|---|---|---|
| S0 VPE/Pulse/facade/host/local transport; tenant/UUID/event/outbox/artifact reference contracts; JSON Schema envelope; SQLite semantics spike; architecture/ADR/research docs | Laravel Control Plane; Go Platform Plane; Go realtime; typed internal contracts; owner schemas; session coordinator; ObjectStorage/SQS/PostgreSQL production adapters | Laravel/Go apps; gRPC/WebSocket; PostgreSQL/Redis/SQS/Kafka/ClickHouse/Iceberg; AWS/Kubernetes; SSO/JWT implementation; AI Patient; Unity. |

## migration path from current Python S0

1. Keep the verified Python VPE and C++ Pulse boundary untouched.
2. Freeze portable contract semantics in language-neutral schema/fixtures; regard `nexora_vpe.platform` as reference/test behavior.
3. In a separate approved Control Plane batch, scaffold Laravel only with `control_plane` ownership, migrations, tenant/RBAC policy, and outbox transaction tests.
4. In a separate approved Platform Plane batch, implement Go registry/lease/fencing/relay against contracts and reproduce fixtures; no cross-schema writes.
5. Only after worker and realtime evidence, introduce gRPC/WebSocket boundaries. Unity remains gated independently by Gate 0 and medical review.

## required separate judgments

| judgment | result | reason |
|---|---|---|
| **POLYGLOT PLATFORM ARCHITECTURE** | **ACCEPT** | ownership and contract boundaries are explicit; no language is forced outside its workload. |
| **CURRENT S0 IMPLEMENTATION** | **KEEP** | Python VPE/C++ Pulse remain correct simulation/native owners; no rewrite evidence. |
| **READY TO IMPLEMENT LARAVEL CONTROL PLANE** | **YES, as a separate bounded architecture batch** | target owner/schema/outbox/auth boundary is specified; still needs product scope, migrations, role model, and tests. |
| **READY TO IMPLEMENT GO PLATFORM PLANE** | **YES, as a separate bounded architecture batch** | lease/routing/contract ownership specified; still needs load/failure/observability and no production promise. |
| **READY TO START UNITY** | **NOT YET** | Gate 0 is UNTESTED and Medical Review is UNVALIDATED; this architectural ACCEPT is not clinical/product validation. |

## final validation

نفذ الأمر التالي بعد كل تغييرات العقد polyglot:

```bash
PULSE_ROOT=/home/ubuntu/pulse-build/install PYTHONPATH=src \\
  python3 -W error::ResourceWarning -m unittest discover -s tests -v
```

**النتيجة الفعلية:** **53 اختبارًا نجحت في 25.317s**، منها **8 اختبارات تكامل Pulse SDK حقيقية**، و**0 skipped**. تتضمن الحزمة **10 platform-boundary tests** (منها اختبار توافق Python reference serializer مع JSON Schema المحايد للغة). لا توجد Pulse skips مقبولة كـPASS، ولا يعد هذا benchmark للأداء أو readiness لخدمات Laravel/Go.

## references

[1]: https://laravel.com/docs/13.x/authorization "Laravel 13.x: Authorization"
[2]: https://laravel.com/docs/13.x/queues "Laravel 13.x: Queues"
[3]: https://go.dev/blog/context "Go Concurrency Patterns: Context"
[4]: ../validation/transactional-outbox-sqlite-spike.md "Transactional Outbox SQLite Spike"
[5]: https://protobuf.dev/overview/ "Protocol Buffers: Overview"
[6]: https://protobuf.dev/best-practices/dos-donts/ "Protocol Buffers: Best Practices"
[7]: ../architecture/capacity-model-v0.1.md "Nexora Capacity Model"
[8]: ../architecture/polyglot-platform-target-v0.1.md "Nexora Polyglot Platform Target"
[9]: ../architecture/polyglot-data-and-deployables-v0.1.md "Nexora Polyglot Data Ownership and Deployables"
