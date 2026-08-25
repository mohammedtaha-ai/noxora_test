# Nexora VPE — الحالة الحالية

## المرحلة الحالية

**المرحلة:** اكتملت Gate A ونواة S0 headless وPulseAdapter وحدود العميل، ثم Laravel Control Plane Foundation، ثم **دفعة Pre-Go Hardening** على الفرع `manus/pre-go-hardening`. لا توجد خدمة Go أو Unity أو cloud deployment أو broker/queue production.

> لا يثبت نجاح هندسي محلي أو Laravel/PostgreSQL foundation أو Pre-Go hardening صلاحية سريرية أو فعالية تعليمية أو readiness إنتاجي أو سعة مليون مستخدم.

## الأحكام المنفصلة الحالية

| البعد | الحكم | التفسير الدقيق |
|---|---|---|
| **POLYGLOT PLATFORM ARCHITECTURE** | **ACCEPT** | Laravel/PHP للـControl Plane، Go للـPlatform/Realtime لاحقًا، Python/C++ للمحاكاة/Pulse، وC#/Unity عميل مستقبلي. |
| **CURRENT S0 IMPLEMENTATION** | **KEEP / HARDENED** | Python VPE وC++ Pulse وFacade/host/local transport بقيت بلا rewrite؛ client reads لا تصل إلى Pulse وزمن غموض الأثر يوقف النظام. |
| **LARAVEL CONTROL PLANE** | **PASS** | Laravel 13 + PostgreSQL حقيقي مع tenants/start intent/audit/outbox/REST/OpenAPI وcontracts تنفيذية. |
| **POSTGRESQL CONTROL PLANE** | **PASS** | `control_plane.*`، composite tenant FKs، scenario lifecycle/manifest constraint، وoutbox lease constraints. |
| **TENANT ISOLATION** | **VERIFIED** | membership/policy/Sanctum abilities وscoped queries ورفض cross-tenant FKs المباشر؛ RLS spike فقط. |
| **TRANSACTIONAL OUTBOX** | **VERIFIED** | intent+outbox+audit atomically، at-least-once lease/reclaim/fencing، وconsumer dedupe مطلوب. |
| **SIMULATION START CONTRACT** | **READY_FOR_GO_CONSUMER** | generic + event-specific JSON Schema، immutable execution manifest، ولا Go consumer منفذ. |
| **READY TO IMPLEMENT GO PLATFORM PLANE** | **YES — دفعة مستقلة محدودة** | لا يعني Go service قائمًا أو broker/cloud أو production readiness. |
| **READY TO START UNITY** | **NO** | Gate 0 والمراجعة الطبية/التعليمية وقرار مستقل ما زالت مطلوبة. |
| **MEDICAL REVIEW** | **UNVALIDATED** | لا مراجعة خارجية موثقة أو توقيع. |

## IMPLEMENTED AND VERIFIED

| البند | الحالة | الدليل |
|---|---|---|
| Pulse single-owner + cached client state | **VERIFIED** | `VpeRuntime` يملك الوقت cached؛ اختبارات HTTP GET تثبت غياب adapter calls. |
| Ambiguous side-effect safety | **VERIFIED** | `AMBIGUOUS → PAUSED_BY_SYSTEM`، بلا advance أو retry تلقائي. |
| Tenant graph and lifecycle | **VERIFIED** | composite FKs واختبار إدخالات cross-tenant؛ `published → retired` فقط مع immutable execution content. |
| Published execution manifest | **VERIFIED** | published/retired versions تطلب artifact reference/hash/content metadata وscenario/runtime contract metadata. |
| Executable portable events | **VERIFIED** | `opis/json-schema` ينفذ generic envelope وpayload schema specific مع recursive allowlist. |
| Identifier/ability contract | **VERIFIED** | UUID headers، `Idempotency-Key` منفصل، structured 400، وSanctum abilities مفروضة. |
| Outbox relay contract | **VERIFIED** | `claimed_by` وexpiry وclaim token fencing واختبار crash/reclaim بالـduplicate event ID. |
| Destructive local tool guard | **VERIFIED** | local/testing + loopback + `_test` أو override محلي صريح. |
| PulseAdapter bounded close | **VERIFIED** | fake process يثبت لا blocking `readline` ثم terminate/kill bounded. |

## VERIFIED COMMANDS

| مجموعة | النتيجة |
|---|---|
| Laravel PHPUnit/PostgreSQL | **28 tests، 90 assertions، PASS** بعد `migrate:fresh` ضد PostgreSQL محلي حقيقي. |
| Composer/Pint/security | `composer validate --strict` PASS، Pint PASS، `composer audit` بلا advisories. |
| Python/Pulse | **56 tests، 51.612s، PASS**؛ 8 Pulse SDK integrations حقيقية و0 skipped. |
| PulseAdapter shutdown | **1 regression test، PASS**. |

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

## DEFERRED OR UNVALIDATED

| البند | الحالة/trigger |
|---|---|
| Go Platform/Realtime implementation | دفعة مستقلة: registry/consumer/lease/fencing/WebSocket/relay/load/failure/runbook. |
| Go consumer deployment | **NOT IMPLEMENTED**؛ العقد فقط ready. |
| Unity | محظور حتى Gate 0 والمراجعة الطبية/التعليمية وقرار مستقل. |
| Hemorrhage stop/reduce/control | **NOT IMPLEMENTED**؛ يحتاج scenario-authorized action وbridge contract وتحقيق منفصل. |
| Branch replay | **NOT IMPLEMENTED**؛ checkpoint restore لا يوفّر branch lineage أو deterministic replay. |
| RLS rollout | spike فقط؛ يتطلب governance للـroles/pooling/workers/migrations واختبارات negative. |
| Redis/SQS/Kafka/ClickHouse/Iceberg/NoSQL/cloud | لا provision؛ evidence trigger فقط. |
| Durable object-storage workflow | contract فقط؛ لا adapter/runbook/deployment. |
| Enterprise SSO/SAML/OIDC/service identity | threat/rotation/revocation design وproduct requirement. |
| Gate 0 / medical / educational validation | **UNTESTED / UNVALIDATED**. |
| Production HA/capacity/SLA | **UNMEASURED**. |

## القرارات السارية

1. S0 VPE/Pulse ownership لا يتغير؛ Python لا يعاد كتابته وPulse لا يصل إليه client مباشرة.
2. Laravel يملك Control Plane و`control_plane.*` فقط؛ Go مستقبلًا لا يكتب جداول Laravel، وLaravel لا يكتب platform/session/Pulse/VPE state.
3. Authentication منفصلة عن tenant authorization؛ لا ثقة في tenant ID من العميل قبل membership verification، وSanctum ability طبقة إضافية واضحة.
4. owner mutation + outbox atomically؛ لا Laravel DB commit + unreliable direct Go call؛ consumers idempotent.
5. REST/JSON public؛ WebSocket realtime future via Go؛ S0 loopback HTTP/JSON unchanged.
6. execution manifest immutable داخل event يعرّف artifact/runtime reference؛ لا artifact bytes ولا direct Go DB access.
7. لا يبدأ Unity حتى Gate 0 والمراجعة الطبية/التعليمية وقرار مستقل.

## أحدث الأدلة

- [تقرير 009: Pre-Go Hardening](../reports/009-pre-go-hardening-review.md).
- [ADR-009](../decisions/ADR-009-laravel-outbox-and-platform-command-contract.md)، [ADR-010](../decisions/ADR-010-simulation-start-execution-manifest.md)، و[حدود VPE S0](../contracts/vpe-s0-runtime-boundaries-v0.1.md).
- [OpenAPI](../../contracts/control-plane.openapi.yaml)، [portable event schema](../../schemas/platform-event-envelope.schema.json)، و[event-specific payload schema](../../contracts/events/control.simulation_start.requested.v1.schema.json).

## الخطوة التالية

**تتوقف دفعة Pre-Go Hardening للمراجعة.** إذا قبل المراجع الحكم، تكون الخطوة التالية المحتملة دفعة Go Platform Plane منفصلة ومحدودة. لا تبدأ Unity أو Kafka/ClickHouse/Kubernetes/cloud provisioning في القرار نفسه.
