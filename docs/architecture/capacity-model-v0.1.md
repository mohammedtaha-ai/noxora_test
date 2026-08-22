# Nexora Capacity Model v0.1

**الحالة:** نموذج معماري توضيحي قابل لإعادة الإنتاج، وليس forecast أو benchmark أو SLA.  
**مصدر الحساب:** `tools/calculate_capacity_model.py` و`artifacts/capacity_model/illustrative_capacity_model.csv`.

## الغرض وحدود القراءة

يختبر هذا النموذج الاتجاهات البنيوية عند 1,000 و100,000 و1,000,000 متعلم مسجل، لا قدرة Pulse أو VPE أو PostgreSQL أو أي cloud vendor. الأرقام أدناه **افتراضات محاسبية صريحة** اختيرت لإظهار سبب الفصل بين OLTP وtelemetry/artifacts، وليست ملاحظات من استخدام حقيقي ولا وعدًا بعدد مستخدمين أو معدل أحداث.

> لا يترتب على وصول الخطة إلى سيناريو مليون متعلم أن المنصة أثبتت القدرة على مليون مستخدم. لا تتحول هذه الأرقام إلى procurement sizing إلا بعد load test، product telemetry، SLO، وقياسات component-specific.

## الافتراضات

| الافتراض | القيمة التوضيحية | لماذا موجود | ليس ادعاءً عن |
|---|---:|---|---|
| المتعلمون النشطون في آن واحد | 5% من المسجلين | تحويل registered count إلى active session model واضح | peak usage أو adoption. |
| canonical platform events | 8 لكل active session في الدقيقة | تقدير outbox/event handoff الخفيف | raw Pulse/runtime events. |
| حجم canonical event | 1 KiB | تقدير envelope/payload صغير ومصنف | payload production أو PII allowance. |
| telemetry samples | 2 لكل active session في الثانية | إظهار تضخم signals مقارنة بالأحداث | tick rate أو Unity FPS أو telemetry contract حالي. |
| حجم telemetry sample | 200 B | حساب حجم تقريبي | encoding/provider compression. |
| durable checkpoint interval | كل 10 دقائق | stress-test افتراضي لمسار artifact مستقبلي | feature S0 قائم أو recovery promise. |
| durable checkpoint size | 2 MiB | إظهار أثر bytes/artifacts | Pulse checkpoint size الحقيقي. |
| اليوم | 24 ساعة نشاط مستمر | تحويل rate إلى volume سهل المراجعة | تشغيل حقيقي بلا انقطاع. |

المعادلات هي: `active = learners × 5%`، و`canonical/day = active × 8/min × 1,440`، و`telemetry/day = active × 2/s × 86,400`، و`checkpoint/day = active ÷ 10min × 1,440`. جميع تحويلات الحجم تستعمل GiB (`1024³` bytes).

## النتائج التوضيحية

| المتعلمون المسجلون | active sessions التوضيحية | canonical events/دقيقة | canonical events/يوم | canonical GiB/يوم | telemetry samples/ثانية | telemetry GiB/يوم | checkpoints/دقيقة | checkpoint GiB/يوم |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 50 | 400 | 576,000 | 0.549 | 100 | 1.609 | 5 | 14.062 |
| 100,000 | 5,000 | 40,000 | 57,600,000 | 54.932 | 10,000 | 160.933 | 500 | 1,406.250 |
| 1,000,000 | 50,000 | 400,000 | 576,000,000 | 549.316 | 100,000 | 1,609.325 | 5,000 | 14,062.500 |

توضح المعادلات أن raw telemetry وcheckpoint bytes قد ينموان أسرع بكثير من canonical business events في نموذج معقول من حيث الشكل؛ لذلك لا يوضعان تلقائيًا في OLTP row أو event payload، ولا يبرر ذلك إطلاق Kafka/ClickHouse/Iceberg الآن. إنه سبب لتصميم ingestion/rollup/object storage boundaries مبكرًا وقياسها قبل التنفيذ.

## الاستنتاجات المعمارية المقيدة

| الدلالة | القرار الآن | trigger التوسعة |
|---|---|---|
| canonical events أصغر نسبيًا | PostgreSQL outbox + immutable envelope contract | `EVT-BUS-02` عندما تحتاج replay/consumers/lag SLO فعليًا. |
| telemetry يتضخم مع concurrency | لا raw telemetry في OLTP أو JSONB session row | `EVT-TELEM-05`/`ANL-RAW-04` عند تهديد outbox/OLTP. |
| checkpoint storage يتضخم بسرعة | ObjectStorage reference/hash/classification contract | `SIM-RECOVER-03` حين يطلب product resume مثبتًا. |
| active sessions stateful | worker pool/lease design فقط | `SIM-POOL-01` بعد قياس host capacity/failure blast radius. |
| dashboard/query isolation | rollups/derived data planned | `ANL-CH-01` بعد workload query/SLO evidence. |
| region scaling | لا active-active default | `PLAT-REGION-03`/`TENANT-REGION-03` مع RPO/RTO/residency. |

## budget signals التي يجب قياسها قبل أي migration

| المجال | signals أولية | قرار لم يثبت بعد |
|---|---|---|
| session workers | active sessions/worker، tick active time، queue age، process memory، Pulse failure rate | worker density وallocator sizing. |
| OLTP | transaction latency، lock waits، slow query plans، connection pool saturation، outbox oldest age | replicas/partitioning/pooler/sharding. |
| event path | pending count، publish attempts، duplicate rate، consumer lag، poison/schema errors | queue/bus/CDC/partitioning. |
| artifacts | bytes/day، object count، hash failure، upload retry، restore test result | storage class/lifecycle/checkpoint policy. |
| analytics | ingestion lag، query SLO، rebuild duration، tenant filter test | ClickHouse/lake/Iceberg. |
| security | cross-tenant deny tests، export audit, classification violations | RLS/SSO/search isolation. |

## sensitivity rather than prediction

إذا تغيرت نسبة concurrent learners أو events/min أو sample size أو retention، تتغير النتائج خطيًا في هذا النموذج. لذلك يجب تعديل input constants في script وحفظ result CSV مع كل architecture review، بدل إعادة استخدام الجدول الحالي كحقيقة. ووجود tick benchmark محلي 0.5s في S0 لا يدخل هنا كـcapacity input؛ ذلك benchmark timing محلي وليس SLA أو Unity FPS.

## عدم الاستدلال

لا يثبت الجدول أن PostgreSQL أو Pulse أو Python أو أي broker يمكنه تحقيق القيم. لا يفترض ضغطًا أو batching أو regional distribution أو retention فعليًا. لا يقترح MongoDB/DynamoDB/Cassandra/Kubernetes، ولا يغير Gate 0 أو medical review أو حظر Unity.

## المراجع

[1]: data-platform-v0.1.md "Nexora Data Platform"
[2]: simulation-session-scaling-v0.1.md "Nexora Simulation Session Scaling"
[3]: ../research/event-platform-comparison.md "Nexora: مقارنة منصة الأحداث"
[4]: ../research/analytics-store-comparison.md "Nexora: مقارنة مخازن التحليلات ومسار lakehouse"
