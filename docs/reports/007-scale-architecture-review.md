# تقرير 007: مراجعة معمارية Nexora Scale-Ready

**التاريخ:** 2026-08-23.  
**الحالة:** مكتمل للمراجعة المعمارية؛ يتوقف العمل بعدها.  
**النطاق:** تصميم قابل للنمو إلى ملايين المتعلمين، لا نشر scale-now ولا Unity ولا proof سريري أو SLA.

## الحكم التنفيذي

**النتيجة: YES — يحافظ التصميم على مسار واقعي من S0 إلى مليون مستخدم دون ground-up rewrite.**

السبب هو أن S0 يبقى محميًا عند حدوده الصحيحة: VPE يملك simulation time، Pulse يظل single-owner لكل session، وواجهة العميل تظل projection آمنة. في المقابل يضيف التصميم control/data plane boundaries وtenant-aware contracts وevent/outbox/object-storage abstractions مستقلة لا تتطلب تعديل `runtime.py`. يمكن إدخال PostgreSQL وworker pool وqueue وevent backbone وanalytics تدريجيًا عند evidence محدد، بدل استبدال نواة Python/Pulse أو نشر بنية مبكرة. لا يعني الحكم أن مليون مستخدم تحقق أو أن Pulse/PostgreSQL أثبتا سعة production؛ النموذج السعوي افتراضي والعقود تحتاج مراحل تنفيذ وتشغيل لاحقة.

> لا يتغير الحكم السريري أو التعليمي: **Gate 0 = UNTESTED** و**Medical Review = UNVALIDATED**. كما لا يبدأ Unity في هذه الدفعة رغم بقاء TECHNICAL M3 READINESS محصورًا في scaffold محدود ومراجع.

## ما تم تسليمه

| المجال | التسليم | الأثر |
|---|---|---|
| البحث | مراجعات PostgreSQL، event platform، analytics/lake، NoSQL/cache/vector مع مصادر وtriggers | اختيارات قابلة للمراجعة لا شعارات تقنية. |
| المعمارية | Control Plane مقابل Simulation Data Plane، model tenant، data platform، session scaling، capacity model، roadmap | ownership/failure domains واضحة. |
| القرارات | ADR-003 إلى ADR-006 | لغة وخدمات، OLTP/JSONB، outbox/analytics، object storage. |
| الأحداث | Platform Event Envelope v0.1 منفصل عن S0 envelope | immutable/versioned/tenant-aware/payload minimized. |
| artifacts | Object Storage Contract v0.1 | hash/reference/classification/retention intent بلا provider lock-in. |
| code | `nexora_vpe.platform` | UUIDv7-style IDs، tenant contracts، event publisher، SQLite outbox spike، local filesystem storage. |
| validation | outbox spike report و52-test suite | failure/retry/duplicate semantics دون تعديل S0. |

## المعمارية المستهدفة

تفصل Nexora بين **Control Plane** و**Simulation Data Plane**. يملك الأول tenants والمؤسسات والعضويات والبرامج والمقررات والتعيينات وscenario catalog وaudit وOLTP truth. ويملك الثاني registry/lease مستقبلية وVPE/Pulse execution وclient-safe projections وartifacts references وأحداث session المسموح بها. analytics وAI consumers مشتقات asynchronous؛ لا تملك simulation truth ولا توقف worker الحي.

| plane | source of truth | فشل لا يجب أن يوقف | الحدود غير القابلة للتغيير |
|---|---|---|---|
| Control Plane | PostgreSQL OLTP target | dashboard/search/cache | authorization وtenant ownership. |
| Simulation Data Plane | VPE/Pulse أثناء الجلسة، registry metadata في OLTP future | relay/analytics/AI | clock وPulse single ownership. |
| Artifact plane | object bytes + metadata reference | analytics ingestion | DB references only؛ object key ليس authorization. |
| Event/async plane | outbox committed by owner | live tick/client projection | at-least-once، idempotent consumers. |
| Analytics/AI | derived/rebuildable | session completion | لا writeback truth ولا LLM-owned truth. |

وثقت PostgreSQL أن `jsonb` مفيد ومفهرس لكنه يقفل الصف عند update كبير، ولذلك يبقى للـdocuments المحددة لا history/telemetry المتنامية.[1] RLS طبقة defense-in-depth محتملة وليست بديلًا عن authorization، لأن أدوارًا عالية الصلاحية قد تتجاوزها.[2]

## التخزين والبيانات

| class | canonical owner/path | derived path | قرار الآن |
|---|---|---|---|
| tenant/course/assignment/session metadata | PostgreSQL OLTP target | cache/read models | design only. |
| active simulation state | VPE/Pulse single owner | client-safe projection | S0 unchanged. |
| platform event | outbox row | queue/bus/analytics later | local SQLite semantics spike. |
| artifact/export/replay/checkpoint future | ObjectStorage + OLTP reference | lake/analytics references | local filesystem dev adapter. |
| telemetry | policy-controlled data plane | rollups/ClickHouse/lake later | no raw telemetry in OLTP default. |

تستخدم IDs خارجية UUIDv7-style؛ يعرف RFC 9562 UUIDv7 كـUnix-epoch time-based ويعرض دوافع locality للـdatabase keys الموزعة.[3] لا تعطي IDs صلاحية، ولا تدعي total order عالمي أو simulation chronology.

## events وoutbox

العقد الجديد يحمل `event_id` و`event_type` و`schema_version` و`tenant_id` وaggregate/routing key وclassification وpayload JSON محدود. يبدأ بأسماء مثل `simulation.session.started` و`simulation.intent.recorded` و`simulation.snapshot.available` و`simulation.session.completed`. ولا يخلط هذا العقد مع `schemas/event-envelope.schema.json` الخاص بـS0.

نمط outbox المحلي يثبت أن domain mutation وevent row يلتزمان معًا، ثم ينشر relay خارج transaction. يقبل التصميم تكرار delivery بعد crash، لذلك يتطلب consumer idempotency بالـevent ID. هذا متسق مع نمط outbox المنشور ومع توثيق Debezium لحقول event/aggregate key.[4] [5]

| failure domain | السلوك المعتمد | لا يعد به |
|---|---|---|
| DB transaction failure | لا domain mutation ولا event row | publish external. |
| publisher/queue failure | pending event/retry/lag signal | live simulation blocking. |
| crash after publish before mark | duplicate event ID possible | exactly-once. |
| analytics/AI consumer lag | stale/rebuildable derived output | truth/session ownership. |
| Pulse/worker failure | pause/recovery-required policy future | seamless resume بلا checkpoint proof. |

## outbox spike

نفذ `SQLiteTransactionalOutbox` **فقط** كـlocal semantics spike، وليس PostgreSQL production implementation. تغطي الاختبارات atomicy، publisher failure، retry، duplicate delivery الناتج عن crash window، content-addressed artifacts، وtamper detection. نجحت اختبارات platform التسع في **0.021s**؛ لا يمثل الزمن benchmark.[6]

## السعة والـlifecycle

نموذج 1k/100k/1M معلن الافتراضات: 5% concurrent sessions، 8 canonical events/min/session، 2 telemetry samples/s/session، 1 KiB event، 200 B sample، وcheckpoint افتراضي 2 MiB كل 10 دقائق. في سيناريو مليون متعلم ينتج النموذج **50,000 active sessions** و**400,000 canonical events/min** و**1,609.325 GiB telemetry/day** و**14,062.500 GiB checkpoint/day**؛ هذه نواتج معادلات افتراضية لا forecast.[7]

الدلالة ليست اختيار Kafka أو ClickHouse الآن؛ بل إبقاء raw telemetry/artifact bytes خارج OLTP/event payload، وقياس actual workload قبل الترقية. تقسم البيانات إلى Hot (session/OLTP/outbox)، Warm (summaries/artifacts/derived analytics)، وCold (archive/lake path) وفق policy لا وفق convenience تقني.[8]

## triggers وقرارات مؤجلة

| capability مؤجلة | trigger required | first reversible action |
|---|---|---|
| PostgreSQL pooler/replica | `PG-POOL-01` / `PG-REPL-04` | telemetry/query/pool spike. |
| table partitioning | `PG-PART-03` | schema/lifecycle rehearsal. |
| managed queue | `EVT-QUEUE-01` | one idempotent async consumer + DLQ design. |
| Kafka/Redpanda/MSK/Kinesis | `EVT-BUS-02` | contract/retention/replay benchmark. |
| worker allocator/lease | `SIM-POOL-01`/`SIM-FENCE-02` | registry + fencing/chaos test. |
| durable resume | `SIM-RECOVER-03` | artifact/replay compatibility validation. |
| ClickHouse | `ANL-CH-01` | derived export/rebuild spike. |
| Parquet/Iceberg | `ANL-LAKE-02`/`ANL-ICE-03` | Parquet manifest then catalog study. |
| NoSQL | `KV-02` | proof-of-access-pattern. |
| pgvector/OpenSearch | `VECTOR-04`/`VECTOR-05` | pgvector recall/latency/tenant-filter spike. |
| multi-region/Kubernetes | `PLAT-REGION-03`/`PLAT-K8S-04` | RPO/RTO/residency or deployment operations study. |

Kafka provides ordering at the topic-partition boundary for same keys, not global ordering, which supports routing events by `session_id` if/when a backbone is justified.[9] Redpanda is considered a Kafka-compatible alternative but declares compatibility exceptions, so it stays evaluation-only rather than assumed drop-in.[10]

## validation

الأمر النهائي المنفذ بعد التغييرات:

```bash
PULSE_ROOT=/home/ubuntu/pulse-build/install PYTHONPATH=src \
  python3 -W error::ResourceWarning -m unittest discover -s tests -v
```

**النتيجة:** **52 اختبارًا نجحت في 25.268s**، بما فيها **8 اختبارات تكامل Pulse SDK حقيقية**؛ لم تكن اختبارات Pulse متخطاة. الزيادة من 43 إلى 52 هي 9 اختبارات platform boundaries، ولا تعدل S0 runtime/adapter/host/facade/transport.

## الالتزامات الذرية الرئيسية

| commit | المحتوى |
|---|---|
| `6170396` | مصادر ومراجعات scale architecture. |
| `84a2c83` | target architecture، contracts، data/session/tenant design. |
| `a3226bf` | platform IDs/events/outbox/object storage abstractions. |
| `70237a4` | platform boundary tests. |
| `759b7d5` | capacity model، roadmap، ADR-003..006، وoutbox spike validation. |

## التوصية التنفيذية المطلوبة

| الحقل | التوصية |
|---|---|
| **Backend** | Python modular boundaries؛ احتفظ بـVPE Python، Pulse C++؛ قيّم Go لحد خدمة مبرر فقط؛ Unity/C# future client فقط. |
| **OLTP** | PostgreSQL authoritative transactional system of record عند بدء Control Plane؛ `jsonb` bounded مع typed relational fields. |
| **Cache** | Redis/Valkey interface لاحقًا للـephemeral cache/lease/rate-limit؛ ليس history أو truth. |
| **Object storage** | ObjectStorage reference/hash/classification contract؛ local dev الآن، S3-compatible/provider adapter لاحقًا. |
| **Initial async queue** | transactional outbox الآن؛ managed queue مثل SQS فقط عند `EVT-QUEUE-01`. |
| **Future event backbone** | Kafka/MSK، Redpanda، أو Kinesis بعد `EVT-BUS-02` benchmark؛ routing key=session/aggregate. |
| **Future analytics** | ClickHouse derived فقط عند `ANL-CH-01`؛ لا يملك truth. |
| **Data lake** | object storage + Parquet عند `ANL-LAKE-02`؛ Iceberg فقط عند `ANL-ICE-03`. |
| **NoSQL** | DynamoDB/Cassandra فقط عند `KV-02` access-pattern evidence؛ لا Mongo لمجرد JSON. |
| **Vector** | pgvector أولًا لاستخدام غير سريري approved؛ OpenSearch عند `VECTOR-05`. |
| **Deployment** | cloud-neutral contracts؛ AWS mapping RDS/Aurora, S3, SQS, ECS/Fargate, CloudWatch/OTel؛ EKS فقط trigger. |
| **Implemented now** | docs/research/ADRs، tenant/ID/event/object contracts، SQLite outbox semantics spike، local artifact adapter، tests/model. |
| **Deferred** | PostgreSQL/Redis/queue/broker/ClickHouse/lake/NoSQL/vector/cloud/SSO/multi-region/Kubernetes/Unity/AI patient or clinical function. |

## المطلوب بعد هذه الدفعة

يتوقف التنفيذ للمراجعة المعمارية. أول تنفيذ تالٍ، إذا وافق المراجع والـproduct scope، هو خطة Control Plane PostgreSQL منفصلة تشمل schema/migrations/auth role model/outbox production adapter وload/failure tests؛ وليس Unity أو Kafka أو ClickHouse أو Kubernetes. تظل Gate 0 والمراجعة الطبية/التعليمية prerequisites مستقلة لأي قرار Unity.

## المراجع

[1]: ../research/postgres-scale-review.md "Nexora: مراجعة PostgreSQL القابلة للتوسع"
[2]: https://www.postgresql.org/docs/current/ddl-rowsecurity.html "PostgreSQL: Row Security Policies"
[3]: https://datatracker.ietf.org/doc/rfc9562/ "RFC 9562: UUIDs"
[4]: https://microservices.io/patterns/data/transactional-outbox.html "Transactional outbox pattern"
[5]: https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html "Debezium Outbox Event Router"
[6]: ../validation/transactional-outbox-sqlite-spike.md "Transactional Outbox SQLite Spike"
[7]: ../architecture/capacity-model-v0.1.md "Nexora Capacity Model"
[8]: ../architecture/data-platform-v0.1.md "Nexora Data Platform"
[9]: https://kafka.apache.org/documentation/ "Apache Kafka Documentation"
[10]: https://docs.redpanda.com/streaming/current/develop/kafka-clients/ "Redpanda: Kafka Compatibility"
