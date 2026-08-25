# Nexora VPE — الحالة الحالية

## المرحلة الحالية

**المرحلة:** اكتملت Gate A ونواة S0 headless وPulseAdapter وحدود العميل، ثم Scale-ready architecture وتصحيح Polyglot Target، ثم **Laravel Control Plane Foundation** على فرع مستقل. لا توجد خدمة Go أو Unity أو cloud deployment أو broker/queue production.

**فرع Control Plane:** `manus/control-plane-foundation` من الأساس المقبول `b5054e5deba1ad3fdac2664cad8a2720038c6777`.

> لا يثبت نجاح هندسي محلي أو Laravel/PostgreSQL foundation صلاحية سريرية أو فعالية تعليمية أو readiness إنتاجي أو سعة مليون مستخدم.

## الأحكام المنفصلة الحالية

| البعد | الحكم | التفسير الدقيق |
|---|---|---|
| **POLYGLOT PLATFORM ARCHITECTURE** | **ACCEPT** | Laravel/PHP للـControl Plane، Go للـPlatform/Realtime لاحقًا، Python/C++ للمحاكاة/Pulse، وC#/Unity عميل مستقبلي. |
| **CURRENT S0 IMPLEMENTATION** | **KEEP** | Python VPE وC++ Pulse وFacade/host/local transport بقيت بلا rewrite أو نقل. |
| **LARAVEL CONTROL PLANE** | **PASS** | Laravel 13 + PostgreSQL حقيقي: tenant/membership/RBAC narrow domain/scenario catalog/assignments/start intent/audit/outbox/REST/OpenAPI/CI. |
| **POSTGRESQL CONTROL PLANE** | **PASS** | migration وقيود وفهارس ومعاملة outbox واختبارات PostgreSQL حقيقية في `control_plane.*`. |
| **TENANT ISOLATION** | **VERIFIED** | membership-derived authorization، scoped queries، constraints، cross-tenant/policy tests؛ RLS spike فقط. |
| **TRANSACTIONAL OUTBOX** | **VERIFIED** | intent+outbox+audit atomically، retry at-least-once، وidempotency/concurrency evidence. |
| **SIMULATION START CONTRACT** | **READY_FOR_GO_CONSUMER** | portable event envelope وOpenAPI والعقد موثقة؛ لا Go consumer منفذ. |
| **READY TO IMPLEMENT GO PLATFORM PLANE** | **YES — دفعة مستقلة محدودة** | لا يعني Go service قائمًا أو production readiness. |
| **TECHNICAL M3 READINESS** | **READY** لscaffold Unity محدود ومراجع فقط | مستقل عن نجاح Laravel. |
| **GATE 0** | **UNTESTED** | لا جلسات/مشاركون/قرار مكتمل. |
| **MEDICAL REVIEW** | **UNVALIDATED** | لا مراجعة خارجية موثقة أو توقيع. |
| **READY TO START UNITY** | **NO** | Control Plane لا يغير Gate 0 أو المراجعة الطبية/التعليمية. |

## IMPLEMENTED

| البند | الحالة | الدليل |
|---|---|---|
| S0 VPE يملك simulation time/queue وPulse single-owner وحدود client-safe headless. | **VERIFIED** للمسارات السابقة | تقارير runtime/Pulse وPulse integration tests. |
| Laravel Control Plane في `apps/control-plane/`. | **IMPLEMENTED** | Laravel 13.26.1، PHP 8.3.6، Sanctum 4، REST v1، Compose/Dockerfile محليين. |
| ملكية PostgreSQL. | **IMPLEMENTED** | `control_plane.*` و`control_plane.migrations` فقط؛ اختبار يمنع schemas platform/session_registry. |
| tenants/users/memberships/roles/programs/courses/cohorts/scenarios/immutable versions/assignments. | **IMPLEMENTED** | migration وEloquent models وconstraints PostgreSQL. |
| API auth + tenant policy boundary. | **IMPLEMENTED** | Sanctum development/testing؛ tenant context يتحقق من active membership. |
| simulation start intent + audit + outbox. | **IMPLEMENTED** | معاملة PostgreSQL واحدة؛ لا direct Go call. |
| portable event contract. | **IMPLEMENTED / TESTED** | Laravel validator وoutbox output موافقان لـ`schemas/platform-event-envelope.schema.json`. |
| local outbox relay semantics. | **IMPLEMENTED / TESTED** | claim/publish/mark/retry؛ at-least-once فقط. |
| UUIDv7 domain identifiers. | **IMPLEMENTED** | Laravel `Str::uuid7()` للـdomain IDs؛ لا public integers. |
| RLS. | **SPIKE ONLY** | `SET LOCAL app.tenant_id` + FORCE RLS جدول مؤقت؛ لا enable للجداول الفعلية. |

## VERIFIED

| مجموعة | النتيجة |
|---|---|
| Laravel PHPUnit/PostgreSQL | **18 tests، 63 assertions، 0 skipped**؛ `migrate:fresh` ضد PostgreSQL 16.15 المحلي. |
| Outbox atomicity/failure/retry | **VERIFIED**. |
| Idempotency concurrency HTTP | **VERIFIED**: 16 طلبًا بنفس request ID = 1×202، 15×200، 0 errors، intent:outbox = 1:1. |
| Tenant/policy/failure/immutability/RLS | **VERIFIED** ضمن suite Laravel. |
| Local diagnostic load | **40 requests / concurrency 8**: 27.152 RPS، p50 210.199ms، p95 578.047ms، p99 633.413ms، 0 errors؛ ليس SLA. |
| Composer/Pint/security | `composer validate --strict` PASS، Pint PASS، `composer audit` بلا advisories. |
| Existing Python/Pulse | **VERIFIED**: 53 tests في **51.430s**، منها 8 Pulse SDK integrations حقيقية و0 skipped، بعد إعادة بناء Pulse 4.3.2 revision `e8a36497b8ba78e788dc201a6baf74e1c297c56f`. |

## TARGET

| domain | owner/language | owner data | scale boundary |
|---|---|---|---|
| Control Plane | Laravel/PHP | `control_plane.*` | stateless business API replicas by load. |
| Platform/Realtime | Go future | `platform.*`, `session_registry.*` | connections/RPS، leases، relay backlog. |
| Simulation | Python + C++ Pulse | scoped session-local/runtime | active simulation sessions/resource profile. |
| Client | C#/Unity future | لا truth authoritative | client distribution. |
| AI/analytics | derived future workers/consumers | derived stores only | queue/model/partition workload. |

**Control path target:** Laravel authorized transaction + owner outbox → Go allocation/registry → Python worker.
**Hot path target:** future client → Go realtime/platform → Python VPE → C++ Pulse.

## DEFERRED

| البند | الحد/trigger |
|---|---|
| Go Platform/Realtime implementation | دفعة مستقلة: registry/lease/fencing/WebSocket/relay/load/failure/runbook. |
| Unity | يبقى محظورًا حتى Gate 0 والمراجعة الطبية/التعليمية وقرار مستقل. |
| Enterprise SSO/SAML/OIDC/service identity | threat/rotation/revocation design وproduct requirement. |
| RLS rollout | role/pooling/background worker/migration governance وnegative tests. |
| Redis/SQS/Kafka/ClickHouse/Iceberg/NoSQL/cloud | evidence triggers؛ لا provision. |
| S3/object storage durable workflow | contract/adapter/runbook مستقل. |
| Laravel Octane/PgBouncer | evidence من connection/load profile أولًا. |
| LMS/grading/high-stakes | خارج S0 formative Learning Mode. |

## UNVALIDATED OR UNMEASURED

| البند | الحالة |
|---|---|
| Gate 0 | **UNTESTED**. |
| medical/educational review | **UNVALIDATED**. |
| production Laravel/PostgreSQL capacity/HA | **UNMEASURED**؛ لا SLA من قياس محلي. |
| Compose runtime | **NOT RUN** في sandbox لأن Docker غير متاح؛ PostgreSQL non-Docker اختبر فعليًا. |
| Go/platform leases/recovery/realtime | **NOT IMPLEMENTED**. |
| Unity rendering/network cost | **UNMEASURED**. |

## القرارات السارية

1. S0 VPE/Pulse ownership لا يتغير؛ Python لا يعاد كتابته وPulse لا يصل إليه client مباشرة.
2. Laravel يملك Control Plane و`control_plane.*` فقط؛ Go لا يكتب جداول Laravel، وLaravel لا يكتب platform/session/Pulse/VPE state.
3. Authentication منفصلة عن tenant authorization؛ لا ثقة في tenant ID من العميل قبل membership verification.
4. owner mutation + outbox atomically؛ لا Laravel DB commit + unreliable direct Go call؛ consumers idempotent.
5. REST/JSON public؛ WebSocket realtime future via Go؛ gRPC/Protobuf candidate future؛ S0 loopback HTTP/JSON unchanged.
6. analytics/AI/cache/object store لا تملك simulation truth ولا توقف hot path.
7. لا يبدأ Unity حتى Gate 0 والمراجعة الطبية/التعليمية وقرار مستقل.

## أحدث الأدلة

- [تقرير 008: Laravel Control Plane Foundation](../reports/008-laravel-control-plane-foundation.md).
- [Stack review](../research/laravel-control-plane-stack-review.md)، [ADR-007](../decisions/ADR-007-control-plane-framework-and-runtime.md)، [ADR-008](../decisions/ADR-008-control-plane-auth-and-tenant-boundary.md)، [ADR-009](../decisions/ADR-009-laravel-outbox-and-platform-command-contract.md).
- [OpenAPI](../../contracts/control-plane.openapi.yaml)، [portable event schema](../../schemas/platform-event-envelope.schema.json)، [RLS spike](../validation/control-plane-rls-spike.md).
- [تقرير 007](../reports/007-scale-architecture-review.md)، [Gate 0](../gate0/README.md)، و[medical review packet](../validation/s0-medical-review-packet.md).

## الخطوة التالية

**تتوقف دفعة Laravel Control Plane للمراجعة.** إذا قبل المراجع الحكم، تكون الخطوة التالية المحتملة دفعة Go Platform Plane منفصلة ومحدودة. لا تبدأ Unity أو Kafka/ClickHouse/Kubernetes/cloud provisioning في القرار نفسه.
