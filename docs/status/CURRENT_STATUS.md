# Nexora VPE — الحالة الحالية

## المرحلة الحالية

**المرحلة:** اكتملت Gate A ونواة S0 headless وPulseAdapter وحدود العميل، ثم Laravel Control Plane Foundation وPre-Go Hardening، ثم **Go Platform Plane Foundation — Phase 1** على الفرع `manus/go-platform-foundation`.

> لا يثبت نجاح هندسي محلي أو Laravel/PostgreSQL أو Go Platform Foundation صلاحية سريرية أو فعالية تعليمية أو readiness إنتاجي أو سعة مليون مستخدم.

## الأحكام المنفصلة الحالية

| البعد | الحكم | التفسير الدقيق |
|---|---|---|
| **POLYGLOT PLATFORM ARCHITECTURE** | **ACCEPT** | Laravel/PHP للـControl Plane، Go للـPlatform، Python/C++ للمحاكاة/Pulse، وC#/Unity عميل مستقبلي فقط. |
| **CURRENT S0 IMPLEMENTATION** | **KEEP / HARDENED** | Python VPE وC++ Pulse وFacade/host/local transport بقيت بلا rewrite؛ client reads لا تصل إلى Pulse وambiguous side effects توقف الزمن. |
| **LARAVEL CONTROL PLANE** | **PASS** | Laravel 13 + PostgreSQL مع tenants/start intent/audit/outbox/REST/OpenAPI وcontracts تنفيذية. |
| **POSTGRESQL CONTROL PLANE** | **PASS** | `control_plane.*` مع composite tenant FKs وscenario lifecycle/manifest constraints وoutbox lease/fencing. |
| **GO PLATFORM PLANE — PHASE 1** | **PASS، ضيق** | Go process واحد validates canonical events ويخصص receipts/sessions/leases في `platform.*` فقط؛ لا worker ولا VPE/Pulse. |
| **POSTGRESQL PLATFORM REGISTRY** | **VERIFIED** | `platform.command_receipts`, `platform.sessions`, `platform.session_leases` وGoose version table مع integration/race tests حقيقية. |
| **SIMULATION START CONTRACT** | **CONSUMABLE BY GO** | generic + event-specific JSON Schema وimmutable execution manifest؛ Laravel وGo يستهلكان fixtures مشتركة. |
| **PLATFORM TRANSPORT** | **LOCAL/TEST ONLY** | adapter HTTP loopback bounded فقط؛ لا broker أو service identity أو public API. |
| **READY FOR WORKER-TRANSPORT MILESTONE** | **YES — قرار مستقل محدود** | لا يعني deployment أو VPE launch أو broker/cloud أو production/clinical readiness. |
| **READY TO START UNITY** | **NO** | Gate 0 والمراجعة الطبية/التعليمية وقرار مستقل ما زالت مطلوبة. |
| **MEDICAL REVIEW** | **UNVALIDATED** | لا مراجعة خارجية موثقة أو توقيع. |

## IMPLEMENTED AND VERIFIED

| البند | الحالة | الدليل |
|---|---|---|
| Pulse single-owner + cached client state | **VERIFIED** | `VpeRuntime` يملك الزمن cached؛ HTTP GET لا يستدعي adapter. |
| Ambiguous side-effect safety | **VERIFIED** | `AMBIGUOUS → PAUSED_BY_SYSTEM`، بلا advance أو retry تلقائي. |
| Tenant graph and lifecycle | **VERIFIED** | composite FKs واختبار إدخالات cross-tenant؛ `published → retired` فقط مع immutable execution content. |
| Executable portable events | **VERIFIED** | Laravel Opis وGo `jsonschema/v6` ينفذان envelope ثم payload-specific schema. |
| Shared contract fixtures | **VERIFIED** | valid وثلاثة invalid fixtures في `contracts/fixtures/` تختبرها اللغتان. |
| Platform command receipt | **VERIFIED** | `event_id` و`command_id` unique؛ replay يعيد session نفسه، والـmismatch يرفض integrity conflict. |
| Platform session registry | **VERIFIED** | lifecycle محدد: `REQUESTED`, `PENDING_WORKER`, `FAILED`, `CANCELLED`؛ لا `RUNNING` بلا worker. |
| Platform lease/fencing | **VERIFIED** | PostgreSQL lock/expiry/reclaim/token/generation؛ stale owner لا يجدد ولا يكتب route. |
| Bounded local ingress | **VERIFIED** | loopback-only config، timeouts/body limits، health/readiness، sanitized errors؛ لا public auth. |
| Go CI and vulnerability scan | **VERIFIED محليًا / workflow مضاف** | `gofmt`, PostgreSQL `-race`, `go vet`, `govulncheck`; workflow ينتظر run remote للـSHA النهائي. |

## VERIFIED COMMANDS

| مجموعة | النتيجة |
|---|---|
| Pre-Go GitHub Actions gate | **GREEN** على `e4dc9b2` بعد إصلاح paths وRLS spike role. |
| Laravel PHPUnit/PostgreSQL | **29 tests، 102 assertions، PASS** بعد `migrate:fresh` ضد PostgreSQL محلي حقيقي. |
| Composer/Pint/security | `composer validate --strict` PASS، Pint PASS، `composer audit` بلا advisories. |
| Go compile/tests | `go test -count=1 -p 1 ./...` PASS؛ integration على PostgreSQL حقيقي. |
| Go race/static/security | `go test -race -count=1 -p 1 ./...` PASS، `go vet` PASS، `go mod verify` PASS، `govulncheck` بلا vulnerabilities. |
| Platform migration/runtime smoke | migration CLI PASS؛ `platform.*` فقط؛ health/ready 200 وfixture replay يعيد session نفسه. |
| Python/Pulse | **56 tests، 52.156s، PASS**؛ 8 Pulse SDK integrations حقيقية و0 skipped. |

## TARGET

| domain | owner/language | owner data | scale boundary |
|---|---|---|---|
| Control Plane | Laravel/PHP | `control_plane.*` | stateless business API replicas by load. |
| Platform | Go | `platform.*` | sessions/leases/receipt rate ثم measured connection/RPS. |
| Simulation | Python + C++ Pulse | scoped session-local/runtime | active simulation sessions/resource profile. |
| Client | C#/Unity future | لا truth authoritative | client distribution. |
| AI/analytics | derived future workers/consumers | derived stores only | queue/model/partition workload. |

**Control path الحالي:** Laravel authorized transaction + outbox contract → Go local/test adapter → `platform.*` allocation/lease proof.

**Control path المؤجل:** trusted production transport → Go consumer → Python worker lifecycle → VPE → C++ Pulse.

## DEFERRED OR UNVALIDATED

| البند | الحالة/trigger |
|---|---|
| trusted service identity / production transport | **NOT IMPLEMENTED**؛ مطلوب قبل أي ingress غير loopback. |
| Broker/queue/DLQ/retry delivery policy | **NOT IMPLEMENTED**؛ لا Kafka/NATS/RabbitMQ/SQS/Redis provision. |
| Go↔Python VPE worker lifecycle | **NOT IMPLEMENTED**؛ لا subprocess launch أو route/heartbeat/reconciliation. |
| Pulse access/time/state/telemetry من Go | **PROHIBITED NOW**؛ تبقى ملكية Python VPE/C++ Pulse. |
| Artifact resolver/storage credentials | contract reference فقط؛ لا object storage adapter أو bytes. |
| Public realtime/WebSocket/API | **NOT IMPLEMENTED**؛ local adapter غير مصادق وغير public. |
| gRPC/Protobuf وOTel exporter/backend | **DEFERRED**؛ يعادان عند worker/backend requirement موثق. |
| Hemorrhage stop/reduce/control | **NOT IMPLEMENTED**؛ يحتاج scenario-authorized action وbridge contract وتحقيق منفصل. |
| Branch replay | **NOT IMPLEMENTED**؛ checkpoint restore لا يوفّر lineage أو deterministic replay runner. |
| RLS/DB grants production governance | **DEFERRED**؛ RLS spike ليس rollout. |
| Unity/cloud/production HA/capacity/SLA | **NOT STARTED / UNMEASURED**. |
| Gate 0 / medical / educational validation | **UNTESTED / UNVALIDATED**. |

## القرارات السارية

1. Python VPE/C++ Pulse يحتفظان بملكية وقت المحاكاة والحقيقة الفسيولوجية؛ Go لا يصل إليهما في Phase 1.
2. Laravel يملك `control_plane.*` وGo يملك `platform.*` فقط؛ لا direct cross-owner database access.
3. owner mutation + outbox atomically؛ delivery at-least-once وconsumers idempotent، لا exactly-once claim.
4. execution manifest immutable داخل event؛ لا artifact bytes ولا direct Go DB access إلى Laravel.
5. Platform lease يعتمد PostgreSQL token + monotonic generation + expiry؛ stale owner fenced.
6. local ingress ليس public API؛ أي trusted production transport يحتاج ADR/milestone مستقل.
7. لا يبدأ Unity حتى Gate 0 والمراجعة الطبية/التعليمية وقرار مستقل.

## أحدث الأدلة

- [تقرير 010: Go Platform Plane Foundation](../reports/010-go-platform-plane-foundation-review.md).
- [ADR-011](../decisions/ADR-011-go-platform-plane-phase-one-responsibility-boundary.md)، [ADR-012](../decisions/ADR-012-platform-postgresql-ownership-and-session-registry.md)، [ADR-013](../decisions/ADR-013-platform-command-ingestion-adapter-and-transport-deferral.md)، و[ADR-014](../decisions/ADR-014-platform-session-lease-and-fencing-model.md).
- [بحث dependencies](../research/go-platform-dependency-research.md)، [portable event schema](../../schemas/platform-event-envelope.schema.json)، و[event-specific payload schema](../../contracts/events/control.simulation_start.requested.v1.schema.json).

## الخطوة التالية

**تتوقف دفعة Go Platform Plane Foundation للمراجعة.** إذا قبل المراجع الحكم، تكون الخطوة التالية المحتملة milestone منفصلًا لـtrusted production command transport وGo↔Python worker lifecycle. لا تبدأ Unity أو broker deployment أو cloud provisioning أو S0 clinical expansion في القرار نفسه.
