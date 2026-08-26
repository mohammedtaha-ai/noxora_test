# تقرير 011: Go Platform Plane Foundation Phase 1 — Review Rework

**التاريخ:** 2026-08-26.  
**الفرع:** `manus/go-platform-foundation`.  
**Starting SHA:** `f7615f65a9aa6d805fc0a122e09be0c10f33d1a3`.  
**Final implementation SHA:** `adbfe6a7b4cfc48ee4a433dd50c910e855f6642a`.  
**Implementation CI head SHA:** `adbfe6a7b4cfc48ee4a433dd50c910e855f6642a`.  
**GitHub Actions:** Platform Plane run [`33006772086`](https://github.com/mohammedtaha-ai/noxora_test/actions/runs/33006772086), **success**, 2m05s.  
**Scope:** خمسة إصلاحات rework محصورة فقط. لم يبدأ broker أو production transport أو Python worker/VPE/Pulse integration أو RPC أو Redis/Kafka/SQS أو WebSocket/public API أو Unity أو cloud أو توسعة S0.

## القرار

> **GO_PLATFORM_FOUNDATION=PASS — Phase 1 hardened فقط.**
>
> هذا الحكم مبني على PostgreSQL integration/race tests وLaravel contract verification وPython/Pulse regression وGitHub Actions الناجح على implementation SHA. لا يساوي production readiness أو worker lifecycle أو clinical/educational validation أو تفويض Unity.

## نتائج findings المراجعة

| # | finding | النتيجة | التغيير والدليل |
|---|---|---|---|
| 1 | destructive test database safety | **FIXED** | `internal/testsupport.ResetPlatformSchema` fail-closed: يتطلب `PLATFORM_DESTRUCTIVE_TESTS=1`، URL PostgreSQL، اسم DB ينتهي `_test`، وhost loopback أو CI `postgres`. لا ينفذ `DROP SCHEMA` قبل التحقق. Regression يمرر DB غير اختبارية إلى executor مسجل ويثبت أن `Exec` لم يستدعَ. |
| 2 | unified lease time authority | **FIXED** | PostgreSQL `clock_timestamp()` ينشئ expiry ويقارن active/expired في claim/reclaim/renew/route/lease-miss. Go يمرر duration validated بالـmicroseconds فقط ولا يولد expiry أو يستعمل `time.Now()` للحكم. اختبار reclaim يضع expiry مباشرة بـPostgreSQL clock، بلا `Sleep` أو افتراض تطابق ساعة node وDB.[1] |
| 3 | state-gated lease/route ownership | **FIXED** | `PENDING_WORKER` فقط lease-eligible. `REQUESTED` و`FAILED` و`CANCELLED` ترفض claim/renew/route. Migration `00002` تضيف check وtriggers تمنع direct lease insert على terminal session؛ integration يغطي FAILED وCANCELLED وbypass attempt. |
| 4 | frozen duplicate event integrity | **FIXED** | Migration `00003` تضيف `immutable_envelope_hash`; hash canonical يشمل event/command/tenant/type/version/producer/aggregate/routing/classification/payload. تغيير أي حقل semantic مختبر ينتج `EVENT_INTEGRITY_CONFLICT`. `occurred_at`, correlation, causation, trace مستبعدة كـtransport/observability metadata واختبار replay يثبت قبولها. Legacy receipt بلا hash لا تُقبل كـduplicate آمنة. |
| 5 | schema-aware readiness | **FIXED** | `/readyz` لا تكتفي بـPing: تتحقق من `platform.goose_db_version >= 3` والعلاقات الثلاثة المطلوبة. DB reachable بلا schema تعطي `503 PLATFORM_SCHEMA_UNAVAILABLE`؛ بعد Goose migrations تعطي 200. Goose يبقى أداة migrations المعاد استخدامها.[2] |

## دلالة redelivery المجمدة

اختيرت استراتيجية **A: canonical immutable-event hash** بدلاً من مقارنة حقلية متفرقة. يحدد [ADR-015](../decisions/ADR-015-platform-redelivery-integrity-and-schema-readiness.md) الإسقاط exact. لا يدخل timestamp النقل أو trace/correlation/causation في hash كي لا يصبح retry صحيح conflict بسبب observability metadata، بينما يدخل كل metadata المطلوب مراجعته: producer وaggregate/routing/classification وevent/schema وtenant وpayload.

| مسار | النتيجة |
|---|---|
| نفس event/command وimmutable projection نفسها | duplicate accepted ويُعاد session الأصلي. |
| نفس identity مع producer/aggregate/routing/classification/payload مختلف | `EVENT_INTEGRITY_CONFLICT`. |
| نفس identity مع `occurred_at`/correlation/causation/trace فقط مختلف | duplicate accepted؛ metadata غير semantic. |
| receipt legacy بلا immutable hash | لا تُعامل duplicate آمنة؛ conflict fail-closed. |

## نطاق diff

| المجموعة | الملفات الجوهرية |
|---|---|
| Test safety | `internal/testsupport/postgres.go` و`postgres_test.go`؛ harnesses persistence/transport؛ CI env وREADME. |
| Lease/state | `internal/persistence/repository.go`, `internal/session/types.go`, migration `00002_platform_session_lease_state_fencing.sql`. |
| Event/readiness | `internal/contracts/contracts.go`, migration `00003_platform_receipt_immutable_envelope_hash.sql`, `internal/transport/http.go`. |
| Evidence | PostgreSQL persistence/HTTP integration tests، ADR-015، وهذا التقرير. |

لا تمس الدفعة Laravel logic أو JSON Schema canonical أو Python VPE/Pulse runtime؛ Laravel أعاد التحقق من fixtures المشتركة كما هي.

## التحقق المنفذ

| الأمر | النتيجة الدقيقة |
|---|---|
| `test -z "$(gofmt -l ./cmd ./internal)"` | PASS. |
| `PLATFORM_DESTRUCTIVE_TESTS=1 PLATFORM_TEST_DATABASE_URL=… go test -count=1 -p 1 ./... -v` | **PASS** على PostgreSQL حقيقي؛ **18 top-level tests و42 named invocations بما فيها subtests**؛ يشمل guard، immutable metadata conflicts، transport-only replay، DB-clock reclaim، terminal trigger، readiness missing/migrated، وHTTP bounded ingress. |
| `PLATFORM_DESTRUCTIVE_TESTS=1 PLATFORM_TEST_DATABASE_URL=… go test -race -count=1 -p 1 ./...` | PASS؛ لا race detector findings. |
| `go vet ./... && go mod verify` | PASS؛ all modules verified. |
| `govulncheck ./...` | PASS؛ **No vulnerabilities found**. |
| `composer validate --strict && composer audit && ./vendor/bin/pint --test && php artisan migrate:fresh --force && APP_ENV=testing ./vendor/bin/phpunit` | **29 tests، 102 assertions، PASS** على PostgreSQL؛ no Composer advisories. |
| `PULSE_ROOT=/home/ubuntu/pulse-build/install PYTHONPATH=src python3 -W error::ResourceWarning -m unittest discover -s tests -v` | **56 tests، 52.339s، PASS**؛ 8 Pulse SDK integrations حقيقية و0 skipped. |
| GitHub Actions Platform Plane `33006772086` | **PASS** على implementation SHA؛ يتضمن PostgreSQL `-race`, vet, وgovulncheck. |

## Migrations

| Migration | الغرض |
|---|---|
| `00002_platform_session_lease_state_fencing.sql` | حصر lease/route في `PENDING_WORKER` وإضافة trigger يمنع terminal ownership. |
| `00003_platform_receipt_immutable_envelope_hash.sql` | إضافة hash canonical للـsemantic duplicate identity. |

## DEFERRED — لم يبدأ

| الموضوع | الحالة |
|---|---|
| trusted service identity وproduction command transport | **DEFERRED**؛ HTTP الحالي local/test فقط. |
| broker/DLQ/ack/retry policy | **DEFERRED**؛ لا Redis/Kafka/SQS/NATS/RabbitMQ. |
| Go↔Python worker launch/heartbeat/reconciliation | **DEFERRED**؛ لا subprocess ولا RPC ولا Pulse access. |
| artifact fetch/verification credentials | **DEFERRED**؛ manifest reference فقط. |
| public realtime/WebSocket/auth | **DEFERRED**. |
| gRPC/Protobuf وOTel exporter/backend | **DEFERRED**. |
| Unity/cloud/HA/load/SLO/medical-educational validation | **NOT STARTED / UNMEASURED**. |

## ملاحظات CI

GitHub Actions نجح على SHA التنفيذ `adbfe6a`. ظهرت annotation غير حاجبة عن deprecation لـNode 20 في `actions/checkout@v4` وannotation cache restore لأن `go.mod` داخل `apps/platform-plane` وليس root؛ لا توجد خطوة CI فاشلة. لا تُغيّر هذه الدفعة action runtime أو cache layout لأنها خارج findings الخمسة.

## References

[1] [PostgreSQL Date/Time Functions — `clock_timestamp()` وcurrent-time semantics](https://www.postgresql.org/docs/current/functions-datetime.html).  
[2] [Pressly Goose — SQL migrations overview](https://pressly.github.io/goose/).  
[3] [ADR-015: Platform Redelivery Integrity and Schema Readiness](../decisions/ADR-015-platform-redelivery-integrity-and-schema-readiness.md).
