# تقرير 009: مراجعة Pre-Go Hardening

**التاريخ:** 2026-08-26.  
**الفرع:** `manus/pre-go-hardening`.  
**Implementation verification SHA:** `0849dd8` قبل commit هذا التقرير.  
**النطاق:** Hardening قبل بدء Go Platform Plane فقط. لم يُنفذ Go أو Unity أو Redis أو Kafka أو SQS أو cloud أو توسعة S0 سريرية.

## القرار

> **READY_FOR_GO=YES (دفعة Go مستقلة ومحدودة فقط).**
>
> هذا الحكم يعني أن عقد بدء المحاكاة، حدود Pulse، tenant integrity، وoutbox delivery contract صارت محددة ومختبرة بما يكفي لبدء **تصميم وتنفيذ منفصل** لـGo Platform Plane. لا يعني وجود خدمة Go، أو broker إنتاجي، أو readiness سريري/تعليمي/إنتاجي، أو تفويض بدء Unity.

## ملخص القضايا

| المحور | الحالة | الدليل/الأثر |
|---|---|---|
| ملكية Pulse ووقت العميل | **FIXED** | `VpeRuntime` يملك زمنًا cached؛ HTTP `/state` و`/snapshot` و`/events` لا تستدعي adapter. |
| outcome غامض لأثر learner جانبي | **FIXED** | `AMBIGUOUS` يوقف runtime في `PAUSED_BY_SYSTEM`، ولا host tick يرسل `ADVANCE_TIME` أو يعيد المحاولة تلقائيًا. |
| tenant graph في PostgreSQL | **FIXED** | Composite unique/FK على course/cohort/membership/version/assignment/start intent مع رفض إدخال cross-tenant مباشر. |
| lifecycle scenario version | **FIXED** | `published → retired` فقط؛ published/retired immutable؛ لا نشر/retire بلا artifact/runtime manifest كامل. |
| event contracts | **FIXED** | `opis/json-schema` ينفذ envelope Draft 2020-12 ثم schema payload specific؛ allowlist recursive عبر `additionalProperties: false`. |
| execution manifest للـGo المستقبلي | **FIXED** | Option A: outbox يحمل artifact reference/hash/content metadata وscenario/runtime contracts؛ لا direct Go DB access ولا internal API runtime dependency. |
| transport/business IDs | **FIXED** | `X-Request-Id` و`X-Correlation-Id` UUID للنقل؛ `Idempotency-Key` UUID business retry؛ malformed headers ترجع 400 قبل business writes. |
| Sanctum abilities | **FIXED** | read يحتاج `control-plane:read` وstart يحتاج `control-plane:simulation-start` فوق tenant membership/policy. |
| outbox crash recovery | **FIXED** | lease، `claimed_by`، expiry، token fencing، reclaim؛ duplicate delivery متوقع وconsumer dedupe بـ`event_id`. |
| destructive fixture tool | **FIXED** | guard يطلب local/testing + loopback DB + `_test` أو override محلي صريح. |
| PulseAdapter close timeout | **FIXED** | لا `readline()` عند QUIT غير الجاهز؛ terminate ثم kill بانتظار bounded؛ fake-process regression. |
| hemorrhage-control | **DEFERRED** | لا أمر stop/reduce/control؛ موثق كفجوة، ولا أُدخل arbitrary Pulse actions. |
| branch replay | **DEFERRED** | checkpoint restore ليس branch replay؛ لا lineage أو deterministic replay runner. |

## العقود والقرارات

عقد الحدث العام هو [`schemas/platform-event-envelope.schema.json`](../../schemas/platform-event-envelope.schema.json)، وpayload `control.simulation_start.requested` مقيّد في [`contracts/events/control.simulation_start.requested.v1.schema.json`](../../contracts/events/control.simulation_start.requested.v1.schema.json). اختير `Opis JSON Schema` لأنه منفذ PHP متوافق مع Draft 2020-12، و`CompliantValidator` يقتصر على خيارات معيار JSON Schema.[1]

يسجل [ADR-010](../decisions/ADR-010-simulation-start-execution-manifest.md) قرار Option A للـexecution manifest. يحمل event reference metadata فقط، لا bytes ولا credentials، بما يتسق مع عقد object storage.[2] يحدّث [ADR-009](../decisions/ADR-009-laravel-outbox-and-platform-command-contract.md) مصطلحات idempotency: المفتاح التجاري ليس X-Request-Id.

| العقد | المصدر التنفيذي | اختبار التحقق |
|---|---|---|
| UUID transport/business identity | `RequestContext.php` و`ControlPlaneController.php` و`control-plane.openapi.yaml` | malformed IDs وability rejection في `SimulationStartTest`. |
| Generic + event payload schema | `PortableEventEnvelope.php` + JSON Schema | `PortableEventContractTest`: UUID/date/type/missing/nested secret/extra property. |
| Immutable execution manifest | `RequestSimulationStart.php` + PostgreSQL constraint | `SimulationStartTest` و`TenantRelationalIntegrityTest`. |
| At-least-once relay | `DevelopmentOutboxRelay.php` | `DevelopmentOutboxRelayTest`: failure/retry وcrash/reclaim/dedupe. |

## الملفات الجوهرية المتغيرة

| مجموعة | ملفات |
|---|---|
| VPE/Pulse | `src/nexora_vpe/runtime.py`, `client_facade.py`, `host.py`, `pulse_adapter.py`, `tests/test_host.py`, `tests/test_local_transport.py`, `tests/test_pulse_adapter_shutdown.py`. |
| PostgreSQL/Laravel | migrations `2026_08_26_000000` إلى `000002`، `RequestSimulationStart.php`, `PortableEventEnvelope.php`, `DevelopmentOutboxRelay.php`, `RequestContext.php`, `LocalDestructiveOperationGuard.php`, routes وOpenAPI وfeature/unit tests. |
| عقود وقرارات | envelope schema، event-specific schema، ADR-009، ADR-010، و`vpe-s0-runtime-boundaries-v0.1.md`. |

## أوامر التحقق ونتائجها

| الأمر | النتيجة |
|---|---|
| `composer validate --strict` | PASS. |
| `composer audit` | PASS؛ لا advisories. |
| `./vendor/bin/pint --test` | PASS بعد تطبيق تنسيق ملفين. |
| `php artisan migrate:fresh --force && APP_ENV=testing ./vendor/bin/phpunit` | **28 tests، 90 assertions، PASS** على PostgreSQL محلي حقيقي. |
| `PYTHONPATH=src python3 -m unittest tests.test_pulse_adapter_shutdown -v` | **1 test، PASS**. |
| `PULSE_ROOT=/home/ubuntu/pulse-build/install PYTHONPATH=src python3 -W error::ResourceWarning -m unittest discover -s tests -v` | **56 tests، PASS، 51.612s**؛ تضم 8 Pulse SDK integration tests حقيقية، و0 skipped. |

## المخاطر المتبقية وحدود القرار

الـoutbox هنا ليس broker إنتاجي ولا يدّعي exactly-once؛ transport الإنتاجي وconsumer deployment وmonitoring/runbooks يجب أن تكون جزءًا من دفعة Go مستقلة. artifact storage durable، RLS rollout، SSO/service identity، HA/scale/latency tests، Gate 0، والمراجعة الطبية/التعليمية تظل غير مكتملة. حدود S0 المتعلقة بالـhemorrhage-control وbranch replay موثقة صراحة في [`vpe-s0-runtime-boundaries-v0.1.md`](../contracts/vpe-s0-runtime-boundaries-v0.1.md).

## References

[1] [Opis JSON Schema: Validator documentation](https://opis.io/json-schema/2.x/php-validator.html).  
[2] [Nexora object storage contract v0.1](../contracts/object-storage-contract-v0.1.md).
