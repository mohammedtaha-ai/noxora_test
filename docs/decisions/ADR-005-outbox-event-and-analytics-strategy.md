# ADR-005: Outbox أولًا، analytics مشتقة، وevent backbone عند trigger

**الحالة:** Accepted for contracts/local spike; broker and analytics deployment deferred.  
**التاريخ:** 2026-08-23.

## السياق

يحتاج Control Plane وSimulation Data Plane إلى إخراج أحداث موثوقة للمراقبة وanalytics وexports وميزات AI مستقبلًا، لكن لا يجوز أن يوقف publisher أو consumer بطيء session worker. كما لا يجوز تنفيذ dual-write غير موثوق بين OLTP وbroker أو استعمال ClickHouse/lake كـtruth.

## القرار

تكتب owner domain mutation و**Platform Event Envelope** immutable في transactional outbox واحدة. يقرأ relay خارج المعاملة ويسلم at-least-once. كل consumer idempotent بالـ`event_id`، والترتيب المقصود داخل `routing_key`/aggregate/session فقط. تبدأ التحليلات كـderived/rebuildable، مع ClickHouse وParquet/Iceberg كخيارات مستقبلية بعتبات محددة.

| المرحلة | القرار | مؤجل |
|---|---|---|
| الآن | event envelope versioned، EventPublisher protocol، SQLite semantics spike | queue/broker/CDC. |
| asynchronous work | managed queue عند `EVT-QUEUE-01` | event backbone طويل الاحتفاظ. |
| event stream | Kafka/Redpanda/MSK/Kinesis evaluation عند `EVT-BUS-02` | service/vendor adoption بلا evidence. |
| analytics | derived exports/rollups | ClickHouse عند `ANL-CH-01`. |
| lake | Parquet object storage | Iceberg عند `ANL-ICE-03`. |

يوضح نمط transactional outbox أن relay قد ينشر الرسالة أكثر من مرة بعد crash، لذلك consumer idempotency requirement صريح.[1] وتوضح Kafka أن ordering مضمون ضمن partition للمفتاح نفسه، ما يبرر `routing_key=session_id` لأحداث المحاكاة بدل ادعاء ترتيب عالمي.[2]

## البدائل المرفوضة

| البديل | سبب الرفض |
|---|---|
| publish قبل/بعد OLTP commit مباشرة | ينتج dual-write loss/inconsistency window. |
| exactly-once claim من relay | crash boundary يخلق duplicate حتى مع mark published. |
| Kafka/Redpanda الآن | لا consumers/replay SLO أو تشغيل مبرر. |
| ClickHouse/lake كـcommand source | derived data قد تلحق أو تعاد بناؤها ولا تملك truth. |
| AI synchronous in session path | failure/latency/ownership يخالفان simulation invariant. |

## العواقب

تحتاج adoption الإنتاجي إلى outbox table PostgreSQL، claim/poll أو CDC decision، consumer ledger/DLQ/replay policy، schema governance، observability for lag/attempts, وdata classification contract. لا ينقل هذا القرار S0 internal events تلقائيًا إلى platform events؛ adapter يسمح فقط بالـdata المصنف والمصرح به.

تفصل analytics failure domain عن live simulation: consumer lag يحدّث freshness/alert ولا يوقف clock أو Pulse. توثق ClickHouse غياب full-fledged transactions، مما يدعم كونه derived analytics store لا primary truth.[3]

## المراجع

[1]: https://microservices.io/patterns/data/transactional-outbox.html "Transactional outbox pattern"
[2]: https://kafka.apache.org/documentation/ "Apache Kafka Documentation"
[3]: https://clickhouse.com/docs/about-us/distinctive-features "ClickHouse: Distinctive Features"
[4]: ../contracts/platform-event-envelope-v0.1.md "Nexora Platform Event Envelope"
[5]: ../validation/transactional-outbox-sqlite-spike.md "Transactional Outbox SQLite Spike"
