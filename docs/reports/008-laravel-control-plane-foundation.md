# تقرير 008 — Laravel Control Plane Foundation

**التاريخ:** 2026-08-25  
**الفرع:** `manus/control-plane-foundation`  
**الأساس المقبول:** `b5054e5deba1ad3fdac2664cad8a2720038c6777` من `manus/s0-foundation`  
**النطاق:** Laravel/PHP + PostgreSQL للـControl Plane فقط. لا Go Platform Plane، لا Unity، لا cloud، ولا تعديل لمسارات Python VPE/Pulse المعتمدة.

## الحكم التنفيذي

> **LARAVEL CONTROL PLANE: PASS**
>
> **POSTGRESQL CONTROL PLANE: PASS**
>
> **TENANT ISOLATION: VERIFIED** على حدود التطبيق والقيود والفحوص PostgreSQL؛ RLS منفذ كـspike فقط وليس baseline.
>
> **TRANSACTIONAL OUTBOX: VERIFIED** للذرية وإعادة المحاولة at-least-once في PostgreSQL المحلي.
>
> **SIMULATION START CONTRACT: READY_FOR_GO_CONSUMER** كعقد outbox محمول ومحدد، لا كخدمة Go منفذة.
>
> **READY TO IMPLEMENT GO PLATFORM PLANE: YES** في دفعة مستقلة ومحدودة فقط.
>
> **READY TO START UNITY: NO**؛ Gate 0 ما زال UNTESTED والمراجعة الطبية/التعليمية UNVALIDATED.

هذا الحكم هندسي محلي. لا يثبت صلاحية سريرية أو تعليمية أو readiness إنتاجي أو SLA أو سعة نهائية.

## Stack وملكية المعمارية

| العنصر | المنفذ/المختار في الدفعة | الحدود الصريحة |
|---|---|---|
| Framework | Laravel 13.26.1، PHP 8.3.6، Sanctum 4 | Sanctum هو أساس API development/testing؛ لا SSO/SAML/OIDC federation. |
| Database | PostgreSQL 16.15 محلي لاختبارات التكامل | البحث يسجل وثائق PostgreSQL الحالية؛ لا RDS/Aurora/cloud. |
| Logical schema | `control_plane.*` و`control_plane.migrations` | لا إنشاء أو كتابة في `platform.*` أو `session_registry.*` أو Pulse/VPE state. |
| API | REST/JSON `/api/v1` + OpenAPI 3.1 | لا WebSocket، لا gRPC/Protobuf implementation، لا Go relay. |
| Simulation start | intent + outbox + audit في معاملة PostgreSQL واحدة | لا استدعاء Go مباشر أو dual-write. |
| Object storage | references/metadata فقط في scenario version | لا S3 provision ولا blobs كبيرة في DB. |

المسؤولية اللغوية المقبولة لا تتغير: Laravel/PHP للـControl Plane، Go للـPlatform/Realtime لاحقًا، Python+C++ للمحاكاة/Pulse، وC#/Unity عميل مستقبلي فقط.

## البيانات والنماذج

أنشأ migration واحد مملوك للـControl Plane الجداول التالية داخل `control_plane`: `users`، `tenants`، `tenant_memberships`، `programs`، `courses`، `cohorts`، `cohort_memberships`، `scenarios`، `scenario_versions`، `assignments`، `simulation_start_intents`، `outbox_events`، `audit_logs`، و`personal_access_tokens` التقني لـSanctum.

كل معرف domain عام هو UUIDv7 مولد من Laravel `Str::uuid7()`؛ لم تعد API domain entities إلى integer public IDs. تفرض PostgreSQL foreign keys، not-null، CHECK constraints، tenant-scoped unique constraints، وفهارس للعضويات/العروض/outbox pending. `scenario_versions` يحتفظ بـmetadata JSONB محدود وبمرجع artifact/hash/content type/size/classification فقط؛ لا يملك parser التنفيذي أو physiology. Trigger PostgreSQL يمنع تغيير أو حذف النسخة المنشورة في المكان نفسه.

## المصادقة والصلاحيات والعزل

المصادقة API مبنية على Sanctum. لا يعد `X-Tenant-Id` تفويضًا؛ هو اختيار سياق فقط، ويُقبل بعد إيجاد `tenant_memberships` active للمستخدم المصادق. الأدوار الحالية: `learner`، `instructor`، `tenant_admin`، و`platform_admin`. السياسات Laravel تفصل عمليات tenant عن الصلاحية العالمية؛ لا تمنح عضوية tenant صلاحية منصة عالمية.

يغطي الاختبار رفض tenant متقاطع، learner لعملية إدارية، instructor خارج tenant، وtenant_admin لمورد platform عالمي. تؤكد assignment access عضوية cohort عندما تكون assignment مرتبطة بفوج.

### RLS

القرار هو **APPLICATION AUTHORIZATION ONLY FOR NOW**. نُفذ `RlsSpikeTest` على جدول مؤقت مع `FORCE ROW LEVEL SECURITY` و`SET LOCAL app.tenant_id`، وأثبت deny بدون context وعرض الصفوف الخاصة بكل tenant داخل معاملته. لم يُفعّل RLS على الجداول الفعلية بسبب متطلبات role/pooling/transaction context/background worker/migration governance. التفاصيل في [`control-plane-rls-spike.md`](../validation/control-plane-rls-spike.md) وADR-008.

## API والعقود

المسارات المنفذة محدودة ومُنسخة:

| المسار | الغرض |
|---|---|
| `GET /api/v1/me` | principal وactive memberships. |
| `GET /api/v1/tenants/current` | tenant context بعد تحقق membership. |
| `GET /api/v1/scenarios` و`/{id}` | scenario catalog metadata فقط. |
| `GET /api/v1/assignments` | assignments في tenant context authorized. |
| `POST /api/v1/simulation-start-requests` | intent idempotent قابل للاستهلاك لاحقًا عبر Go. |

أخطاء domain تعيد الشكل المستقر `error.code` و`message` و`request_id`، ولا تكشف SQL أو paths أو credentials. middleware يمرر `request_id` و`correlation_id` إلى الاستجابة، domain operation، audit، وoutbox. العقد العام موجود في [`contracts/control-plane.openapi.yaml`](../../contracts/control-plane.openapi.yaml).

## Simulation Start وTransactional Outbox

المسار الحقيقي هو:

```text
Authenticated HTTP request
  -> active membership / policy / assignment / cohort / availability validation
  -> PostgreSQL transaction
      -> simulation_start_intents
      -> outbox_events (control.simulation_start.requested)
      -> audit_logs
  -> 202 Accepted
```

يرث outbox semantics من العقد المحمول [`schemas/platform-event-envelope.schema.json`](../../schemas/platform-event-envelope.schema.json)، لا من شكل PHP خاص. Payload صغير ويحتوي command/assignment/scenario version/requester IDs فقط؛ لا password أو token أو secret أو raw profile أو runtime physiology أو artifact bytes. delivery relay محلي يطبق claim → publish → mark أو release+retry. الدلالة **at-least-once**؛ event/command identity ضروريان لdeduplication. لا ادعاء exactly-once ولا SQS/Kafka/Redis.

`request_id` مرتبط بمستخدم واحد ومبصمة intent؛ التكرار المطابق يعيد نفس intent/command من دون outbox ثانٍ، والتكرار المختلف يرفض. قفل PostgreSQL advisory transaction-scoped يسلسل التكرارات المتزامنة لنفس user/request key.

## Evidence واختبارات PostgreSQL

اختبرت الحزمة ضد PostgreSQL محلي حقيقي، لا SQLite. آخر تشغيل نهائي قبل التقرير:

| مجموعة التحقق | النتيجة |
|---|---|
| Laravel PHPUnit integration/unit | **18 tests، 63 assertions، 0.892s، 0 skipped** في آخر تحقق قبل التقرير. |
| Migrations | `php artisan migrate:fresh --force` نجح على PostgreSQL 16.15. |
| PostgreSQL ownership | `control_plane.migrations` وoutbox في `control_plane`، ولا `platform` أو `session_registry` schemas. |
| Outbox atomicity | forced outbox failure يرجع intent/outbox/audit كلها؛ لا dual-write. |
| Outbox delivery | publisher unavailable يترك event غير منشور، ثم retry ينشر نفس `event_id`. |
| Idempotency | sequential repeat يرجع نفس intent؛ reuse مختلف يرفض. |
| Concurrency | 16 HTTP requests متزامنة بنفس request ID: 1×202، 15×200، 0 errors، و`1:1` intents:outbox. |
| Tenant/auth/failure | cross-tenant denial، expired assignment، draft scenario version، RLS spike، PostgreSQL unavailable connection، malformed portable event، وpublished-version immutability مغطاة. |
| Quality/security | `composer validate --strict` PASS، Pint PASS، `composer audit` = لا advisories. |
| Python/Pulse regression | **53 tests، 51.430s، 8 Pulse SDK integrations حقيقية، 0 skipped** بعد إعادة بناء Pulse 4.3.2 revision `e8a36497b8ba78e788dc201a6baf74e1c297c56f` وbridge Nexora. |

### قياس محلي تشخيصي فقط

تم قياس المسار الحقيقي: authenticated HTTP request → authorization → assignment lookup → PostgreSQL transaction → outbox insert → response. وليس benchmark hello-world أو SLA.

| السيناريو | Requests / concurrency | RPS | p50 | p95 | p99 | Errors | DB connections قبل/بعد |
|---|---:|---:|---:|---:|---:|---:|---:|
| request IDs مختلفة | 40 / 8 | 27.152 | 210.199 ms | 578.047 ms | 633.413 ms | 0 | 1 / 1 |
| request ID نفسه | 16 / 8 | 29.423 | 193.365 ms | 322.749 ms | 346.836 ms | 0 | 1 / 1 |

النتائج محفوظة في `artifacts/benchmarks/control_plane_simulation_start/`. هي قياسات sandbox محلي وبـPHP development server وPostgreSQL محلي؛ لا تصلح للتنبؤ بسعة production.

## البيئة وCI

أضيف `apps/control-plane/compose.yaml` و`Dockerfile` لتشغيل Laravel+PostgreSQL فقط. Docker غير متاح في sandbox، لذلك Compose موثق ولم يختبر runtime هنا؛ بديل PostgreSQL المحلي اختبر فعليًا. لا توجد كلمة مرور DB ثابتة في Compose؛ يلزم `CONTROL_PLANE_DB_PASSWORD` محلي غير ملتزم.

يوجد workflow `.github/workflows/control-plane.yml` منفصل: Composer validation، PHP syntax، Pint، PostgreSQL service integration tests، JSON schema syntax، وComposer audit. يبقى Python/Pulse CI منطقيًا منفصلًا بسبب runtime الخاص به.

## القرارات والمراجع

* [Stack review](../research/laravel-control-plane-stack-review.md)؛ [ADR-007](../decisions/ADR-007-control-plane-framework-and-runtime.md)؛ [ADR-008](../decisions/ADR-008-control-plane-auth-and-tenant-boundary.md)؛ [ADR-009](../decisions/ADR-009-laravel-outbox-and-platform-command-contract.md).
* Laravel/PHP/PG sources موثقة في stack review. 
* [OpenAPI](../../contracts/control-plane.openapi.yaml)، [portable event schema](../../schemas/platform-event-envelope.schema.json)، و[local setup](../../apps/control-plane/README-NEXORA.md).

## Deferred / remaining gaps

| البند | الحالة ولماذا |
|---|---|
| Go Platform Plane | **DEFERRED**؛ العقد جاهز، لكن لا coordinator/registry/lease/WebSocket/relay production منفذ. |
| Unity | **DEFERRED / NO**؛ Gate 0 UNTESTED وmedical/educational review UNVALIDATED. |
| Production auth | **DEFERRED**؛ لا enterprise SSO/SAML/OIDC federation أو service identity/rotation/revocation runbook. |
| RLS | **SPIKE ONLY**؛ لا rollout قبل role/pool/job/migration governance. |
| Queue/broker/cache/cloud | **DEFERRED**؛ لا Redis/SQS/Kafka/MSK/RDS/ECS/EKS provision. |
| Object storage | **REFERENCE ONLY**؛ لا S3 أو durable artifact workflow. |
| Production load/HA | **UNMEASURED**؛ القياس المحلي تشخيصي فقط، ولا pool/Octane/replicas. |
| Product UI/LMS/high-stakes grading | **OUT OF SCOPE**. |

## Commits

| Commit | المحتوى |
|---|---|
| `367fa69` | stack review وADRs Laravel/tenant/outbox. |
| `59ff726` | Laravel 13 PostgreSQL Control Plane foundation، schema، models، services، API. |
| `9fbbee0` | PostgreSQL tenant/isolation/outbox/RLS/idempotency/failure tests. |
| `69f40e5` | أدوات ونتائج benchmark لمسار simulation start وconcurrent idempotency. |
| `036b2ec` | CI PostgreSQL، Compose/Dockerfile المحلي، وOpenAPI contract. |

يتبع التقرير والحالة في الالتزام التوثيقي النهائي لهذه الدفعة؛ لا توجد hashes متوقعة أو commits غير منشورة في هذا الجدول.

## Stop condition

تتوقف هذه الدفعة للمراجعة. لا تبدأ Go أو Unity أو cloud infrastructure تلقائيًا.
