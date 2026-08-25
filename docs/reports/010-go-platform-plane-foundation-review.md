# تقرير 010: مراجعة Go Platform Plane Foundation

**التاريخ:** 2026-08-26.  
**الفرع:** `manus/go-platform-foundation`.  
**Base SHA المتحقق من Pre-Go CI:** `e4dc9b28a365fa3e0f7539a4852421be85af30f3`.  
**Implementation verification SHA:** `30eb9aef56a3804c177a0131575622ab941bf77e` قبل commit هذا التقرير.  
**النطاق:** إغلاق فجوة CI في Pre-Go ثم Go Platform Plane Phase 1 ضيق. لا توجد worker/VPE/Pulse integration أو broker أو Redis/Kafka/SQS أو public API/WebSocket أو Unity أو cloud.

## القرار

> **GO_PLATFORM_FOUNDATION=PASS — لحدود Phase 1 فقط.**
>
> تم تنفيذ Go process واحد يستهلك عقد `control.simulation_start.requested` عبر adapter محلي/اختباري، يتحقق من JSON Schema canonical، ويسجل receipt idempotent ويخصص session وlease/fencing داخل `platform.*`. لا يعني ذلك تشغيل محاكاة أو readiness لإنتاج أو جاهزية سريرية/تعليمية أو تصريح Unity.

## بوابة CI قبل Go

فرع `manus/pre-go-hardening` لم يكن يطلق workflow على SHA السابق بسبب `paths` مقيدًا بفرع/مسارات غير كافية. تم توسيع workflow ليغطي جميع الفروع والمسارات الفعلية للعقود، ثم ظهر فشل حقيقي في RLS spike: مستخدم التطبيق يملك bypass-RLS محليًا. أصلح الاختبار وCI provisioning لفرض role اختبار غير bypass-RLS. النتيجة النهائية كانت **GitHub Actions GREEN على SHA `e4dc9b2`** قبل إنشاء فرع Go؛ لم يُعامل غياب run على SHA قديم كنجاح.

## ما نُفذ

| المحور | الحالة | الدليل التنفيذي |
|---|---|---|
| مسؤولية Go الضيقة | **FIXED** | `apps/platform-plane/` process واحد، بلا Pulse/VPE/clinical time أو artifact bytes أو Unity. ADR-011. |
| ملكية البيانات | **FIXED** | SQL migrations مملوكة لـGo تنشئ `platform.command_receipts`, `platform.sessions`, `platform.session_leases` و`platform.goose_db_version` فقط. ADR-012. |
| العقود المحمولة | **FIXED** | `santhosh-tekuri/jsonschema/v6` يحمّل generic envelope ثم payload schema الخاص من root، مع format assertions؛ لا schema Go-only. |
| fixtures متعددة اللغات | **FIXED** | Laravel وGo يستهلكان fixture valid وثلاثة fixtures invalid مشتركة من `contracts/fixtures/`. |
| receipt/deduplication | **FIXED** | unique `event_id` و`command_id` وحفظ SHA-256 للـpayload؛ replay يعيد session نفسه؛ تغيير tenant/payload مع identity نفسها يرفض integrity conflict. |
| session lifecycle | **FIXED ضمن Phase 1** | السجل يبدأ `REQUESTED`; الحالات المحددة فقط `REQUESTED`, `PENDING_WORKER`, `FAILED`, `CANCELLED`. لا `RUNNING` ولا worker launch. |
| leases/fencing | **FIXED** | claim/reclaim PostgreSQL row lock، UUID token، generation monotonic، expiry؛ stale owner لا يستطيع renew أو تحديث route. ADR-014. |
| ingestion boundary | **FIXED محليًا فقط** | `EventSource`/service boundary و`POST /internal/test-events/simulation-start` loopback-only مع body/time limits، health/readiness، وerrors مُنقحة. ADR-013. |
| observability | **FIXED بالحد الأدنى** | `log/slog` JSON structured diagnostics بلا payload secrets/physiology؛ interface قابل للـOTel لاحقًا، بلا exporter/backend. |
| Go CI | **FIXED** | workflow PostgreSQL حقيقي مع `gofmt`, `go test -race -p 1 ./...`, `go vet`, و`govulncheck`. |

## قرارات البحث وإعادة الاستخدام

استخدمت Phase 1 `net/http` و`log/slog` من standard library، و`pgx/v5` للـPostgreSQL، و`santhosh-tekuri/jsonschema/v6` للتحقق Draft 2020-12، وGoose v3 لملفات SQL migrations، و`google/uuid` للـtyped UUID boundaries. لم يُضف router framework أو Redis أو custom JSON Schema/UUID/migration runner. gRPC/Protobuf وOpenTelemetry SDK/exporter مؤجلان لأنهما يضيفان generated/tooling أو backend surface بلا worker route حالي.[1]

| قرار | الحكم | السبب |
|---|---|---|
| `pgx/v5` | **REUSE** | pool/transactions PostgreSQL وnative error model. |
| `jsonschema/v6` | **REUSE** | تنفيذ schema الموجودة كما هي مع format assertions. |
| Goose | **REUSE** | SQL migrations مرئية وversion table مملوك داخل `platform.*`. |
| `google/uuid` | **REUSE** | parsing/generation typed؛ لا UUID custom. |
| HTTP local adapter | **IMPLEMENT** | adapter محدد لـlocal/test فقط، وليس broker أو public endpoint. |
| broker/gRPC/OTel exporter | **DEFER** | لا production transport أو worker/telemetry backend requirement مثبت. |

## مخطط الملكية والتدفق

```text
Laravel authorization + outbox event
              │  canonical JSON Schema
              ▼
Go Platform Plane (Phase 1 only)
  command receipt → session registry → PostgreSQL lease/fence
              │
              └── PENDING_WORKER is defined, but no worker is launched

Python VPE / C++ Pulse remain separate and unchanged runtime owners.
```

Laravel لا يكتب `platform.*`، وGo لا يقرأ أو يكتب `control_plane.*`. لا توجد foreign keys cross-schema إلى Laravel: event المصرح يحمل immutable execution manifest reference وفق ADR-010.[2]

## التحقق المنفذ

| الأمر/الدليل | النتيجة |
|---|---|
| GitHub Actions على SHA `d78af2d` | **PASS**: Control Plane Verification run `32911633890` وPlatform Plane run `32911634019`؛ الأخير أكمل في 2m04s مع PostgreSQL/race/vet/govulncheck. |
| `composer validate --strict` | PASS. |
| `composer audit` | PASS؛ لا security advisories. |
| `./vendor/bin/pint --test` | PASS على 64 ملفًا. |
| `php artisan migrate:fresh --force && APP_ENV=testing ./vendor/bin/phpunit` | **29 tests، 102 assertions، PASS** على PostgreSQL حقيقي؛ يشمل shared fixtures. |
| `go test -count=1 -p 1 ./... -v` | PASS؛ يشمل schema fixtures، PostgreSQL migration، duplicate/crash-style redelivery، 16 concurrent allocators، lease race/reclaim، stale fencing، وHTTP error paths. |
| `go test -race -count=1 -p 1 ./...` | PASS؛ لا race detector findings. |
| `go vet ./... && go mod verify` | PASS؛ كل modules verified. |
| `govulncheck ./...` | PASS؛ **No vulnerabilities found**. |
| migration CLI | PASS؛ `go run ./cmd/platform-plane migrate` أنشأ فقط جدول tracking والجداول الثلاثة داخل `platform.*`. |
| process smoke | PASS؛ `/healthz` و`/readyz` رجعا 200؛ valid fixture أعطى `201`, ثم replay أعطى session نفسه مع `duplicate: true`. |
| `PULSE_ROOT=/home/ubuntu/pulse-build/install PYTHONPATH=src python3 -W error::ResourceWarning -m unittest discover -s tests -v` | **56 tests، 52.156s، PASS**؛ 8 Pulse SDK integrations حقيقية و0 skipped. |

## الملفات والمigrations والعقود الرئيسية

| المجموعة | الملفات |
|---|---|
| Go process | `apps/platform-plane/cmd/platform-plane/main.go`, `internal/config`, `contracts`, `ingestion`, `persistence`, `session`, `transport`, `observability`. |
| Migration | `apps/platform-plane/migrations/00001_platform_session_registry.sql`. |
| Contracts | `schemas/platform-event-envelope.schema.json`, `contracts/events/control.simulation_start.requested.v1.schema.json`, و`contracts/fixtures/*`. |
| Laravel parity | `apps/control-plane/tests/Unit/ControlPlane/PortableEventContractTest.php`. |
| ADRs | ADR-011 إلى ADR-014. |
| CI | `.github/workflows/control-plane.yml` على Pre-Go و`.github/workflows/platform-plane.yml`. |

## DEFERRED — لا يجوز تفسيره كمنفذ

| الموضوع | الحالة والـtrigger |
|---|---|
| trusted service identity / authenticated Control Plane origin | **DEFERRED**؛ مطلوب قبل أي adapter غير loopback أو production transport. |
| broker / dead-letter / acknowledgements / retry policy | **DEFERRED**؛ يلزم قرار transport إنتاجي وfailure policy مثبتة. |
| Python VPE worker launch، route، heartbeat، lifecycle | **DEFERRED**؛ يلزم milestone مستقل ولا يوجد subprocess أو Pulse access هنا. |
| simulation clock / state / telemetry | **DEFERRED**؛ تبقى ملكية Python VPE/Pulse. |
| artifact retrieval/hash verification | **DEFERRED**؛ manifest reference فقط، لا object storage adapter/credential. |
| realtime/WebSocket/public API | **DEFERRED**؛ لا user/client ingress ولا public auth surface. |
| gRPC/Protobuf | **DEFERRED**؛ يعاد تقييمه عند route Go↔Python موثقة. |
| OTel exporter/collector/backend | **DEFERRED**؛ diagnostics interface فقط. |
| RLS/DB grants deployment governance | **DEFERRED**؛ Phase 1 يثبت schema ownership، لا production role rollout. |
| HA/capacity/scale/SLO/load | **UNMEASURED**؛ لا benchmark أو production operation evidence. |
| Unity/cloud/clinical expansion | **NOT STARTED**؛ خارج النطاق تمامًا. |

## المخاطر المتبقية والقرار التالي

التخصيص دائم ويدعم at-least-once redelivery؛ لكنه لا يحل وصول artifact أو availability للـworker أو exactly-once أو recovery end-to-end. Lease fencing يثبت حماية platform-local ownership، لكنه ليس worker protocol قبل تعريف identity/heartbeat/kill/reconciliation. local HTTP ingress غير مصادق عليه عمدًا، ومن الخطأ كشفه في شبكة عامة.

**الخطوة المسموح بها التالية** هي مراجعة هذا الفرع ثم milestone منفصل ومحدد لـtrusted production command transport وGo↔Python worker lifecycle، مع إبقاء Python VPE/Pulse صاحب الوقت والحقيقة الفسيولوجية. لا تبدأ Unity أو cloud أو broker deployment بهذه الموافقة.

## References

[1] [Go platform dependency research](../research/go-platform-dependency-research.md).  
[2] [ADR-010: Simulation-Start Execution Manifest](../decisions/ADR-010-simulation-start-execution-manifest.md).  
[3] [ADR-011](../decisions/ADR-011-go-platform-plane-phase-one-responsibility-boundary.md)، [ADR-012](../decisions/ADR-012-platform-postgresql-ownership-and-session-registry.md)، [ADR-013](../decisions/ADR-013-platform-command-ingestion-adapter-and-transport-deferral.md)، و[ADR-014](../decisions/ADR-014-platform-session-lease-and-fencing-model.md).
