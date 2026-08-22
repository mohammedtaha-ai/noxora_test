# ملاحظات مصادر معمارية scale-ready

**الغرض:** حفظ حقائق المصدر المستخدمة في قرارات Nexora. لا تمثل هذه الملاحظات توصية بتكرار بنية شركة أخرى أو نشر أي منصة الآن.

| المصدر | الملاحظة ذات الصلة | الدلالة المحدودة على Nexora |
|---|---|---|
| [OpenAI: Scaling PostgreSQL to power 800 million ChatGPT users](https://openai.com/index/scaling-postgresql/) | تصف OpenAI تشغيل primary PostgreSQL واحد غير مجزأ للكتابة مع read replicas، وتحسين الاستعلامات، connection pooling، caching، rate limiting، عزل workload، وتغييرات schema حذرة. كما تصف نقل بعض الأحمال عالية الكتابة القابلة للتجزئة إلى نظم أخرى. | PostgreSQL ليس “قاعدة مؤقتة” بالضرورة؛ يبدأ Nexora بـOLTP مضبوط وقياس فعلي، ثم يعزل/يهاجر workload مبررًا بدل افتراض sharding أو NoSQL من البداية. حجم وتشغيل OpenAI ليسا هدفًا أو baseline لـNexora. |
| [PostgreSQL 18: Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) | RLS يقيد الصفوف المعادة أو المعدلة حسب policy، ولا توجد policies افتراضيًا. يذكر المصدر أن superusers و`BYPASSRLS` ومالكي الجداول قد يتجاوزون RLS، وأن integrity constraints يمكن أن تتجاوزها. | يدعم RLS كـdefense-in-depth محتمل لعزل `tenant_id`، لكنه لا يحل محل authorization في التطبيق أو مراجعة أدوار الاتصال/schema/قيود uniqueness. |

## حدود الأدلة الحالية

لم تُنشأ قاعدة PostgreSQL أو RLS أو replication أو queue في هذا المستودع ضمن هذه الدفعة. كل قرار أدناه هو target architecture أو abstraction headless منخفض الكلفة، ويحتاج benchmark وتهديدات أمنية ومراجعة تشغيلية قبل نشره.

| [Debezium: Outbox Event Router](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html) | يصف outbox كطريقة لتبادل الأحداث بأمان وموثوقية عبر التقاط تغييرات جدول outbox؛ يوضح حقولًا نموذجية مثل event id وaggregate type/id وtype وJSONB payload، وأن event key مهم للحفاظ على ترتيب Kafka partition. | يعتمد Nexora event id وaggregate ordering وpayload versioning من البداية، من دون نشر Debezium أو Kafka الآن؛ يمكن الترقية لاحقًا من outbox ثابت العقد. |
| [Microservices.io: Transactional outbox](https://microservices.io/patterns/data/transactional-outbox.html) | يشرح كتابة business state والرسالة في معاملة قاعدة بيانات واحدة ثم relay منفصل؛ وينبه أن relay قد ينشر الرسالة أكثر من مرة بعد crash، وبالتالي يحتاج المستهلك إلى idempotency. | لا يوعد Nexora بـexactly-once. يجب أن تكون outbox delivery at-least-once ومستهلكو analytics/AI/derived projections idempotent، ولا يتوقف live simulation عند تعطلهم. |

## توضيح failure semantics للـoutbox

`committed domain mutation + committed outbox row` هما الذرية المطلوبة في الـOLTP المستقبلي. النشر إلى queue/bus يقع بعد commit ويمكن أن يتكرر. يجب ألا يدعي relay أن الحذف أو marking published يمنع التكرار بمفرده؛ consumer-side event IDs هي حماية ثانية.

| [PostgreSQL: JSON Types](https://www.postgresql.org/docs/current/datatype-json.html) | `jsonb` يخزن تمثيلًا محللًا ويدعم indexing؛ توصي الوثائق عادةً بـ`jsonb`، لكنها تنبه أن updates تقفل الصف كاملًا وأن الوثائق الكبيرة تزيد contention. تشرح GIN وexpression indexes وtrade-offs بين `jsonb_ops` و`jsonb_path_ops`. | الوثائق المتغيرة والـmetadata المحدودة يمكن أن تبدأ بـ`jsonb` مع typed columns للعلاقات والحقول الحرجة، وحدود حجم وindexes مبنية على query patterns. لا تُخزن telemetry الساخنة أو history المتنامي في JSONB row واحد. |
| [PostgreSQL: Table Partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html) | يقدم range/list/hash partitioning، ويذكر أن المنفعة عادةً تظهر عندما يكبر الجدول؛ يسهل lifecycle بdetach/drop partitions، لكنه يقيد unique/primary key على partitioned table بأن تشمل partition key. | لا تقسيم مبكر للـOLTP. افحص جداول events/telemetry الضخمة زمنيًا بعد قياس. صمم IDs وunique constraints مع فهم قيد partition key، ولا تجعل tenant partitioning افتراضًا ثابتًا. |
| [PostgreSQL: Logical Replication](https://www.postgresql.org/docs/current/logical-replication.html) | logical replication publish/subscribe مبني على replication identity وغالبًا primary key، ويدعم مشاركة subset أو تغذية analytical subscriber، مع مخاطر conflicts عند كتابة subscribers. | مسار مستقبلي لنشر تغييرات مدروسة أو تعزيز migration؛ ليس بديلًا لعقد platform event ولا يُفعّل في هذه الدفعة. |
| [PostgreSQL: Connection Settings](https://www.postgresql.org/docs/current/runtime-config-connection.html) | `max_connections` يحدد اتصالات متزامنة ويزيد تخصيص الموارد؛ default نموذجي 100. | تطبيقات متعددة العمال/المستخدمين تحتاج pooler أو connection management قبل رفع `max_connections` عشوائيًا؛ هذه ملاحظة تشغيلية مستقبلية لا إعداد منفذ. |

## سياسة JSONB المستخلصة

`jsonb` للوثائق محددة الشكل المتغيرة ببطء ولـpayloads محدودة؛ الأعمدة typed للعلاقات، حالة lifecycle، `tenant_id`، timestamps، مفاتيح المسار والاستعلامات المشتركة؛ وobject storage للملفات والمخرجات الكبيرة. الفهارس تأتي بعد ظهور access pattern و`EXPLAIN`، لا كقائمة افتراضية عامة.

| [Apache Kafka: Introduction](https://kafka.apache.org/documentation/) | يعرّف Kafka كمنصة event streaming تنشر/تخزن/تعالج streams؛ events ذات key/value/timestamp/headers، والـtopic مقسم، وتضمن القراءة المرتبة ضمن topic-partition للمفتاح ذاته. | عندما تثبت الحاجة إلى replay متعدد consumers أو streaming مستقل، يكون `session_id` أو aggregate key أساس partition routing. لا يبدأ Nexora بكافكا لمجرد قابلية النمو. |
| [AWS: Key considerations while building streaming analytics](https://docs.aws.amazon.com/whitepapers/latest/build-modern-data-streaming-analytics-architectures/key-considerations-while-building-streaming-analytics.html) | يقدم مقارنة إرشادية بين Kafka وKinesis وMSK: Kafka self-managed overhead أعلى؛ Kinesis managed؛ MSK Serverless منخفض إلى MSK Provisioned متوسط overhead. والوثيقة موسومة historical reference. | خريطة AWS إيضاحية فقط: queue managed مبكرًا، Kinesis إن كان AWS-native stream يلائم consumers/retention، وMSK عند ضرورة Kafka ecosystem بعد قياس. لا نعتمد على أرقام الوثيقة أو نعاملها كإلزام. |
| [Amazon Kinesis Data Streams FAQ](https://aws.amazon.com/kinesis/data-streams/faqs/) | Kinesis يدير البنية والتخزين والشبكة؛ يشرح partition keys وordering داخل shard، وأن تجاوز القدرة يسبب throttling ويتطلب retries، وأن retention محدود حسب الإعداد. | إن اختير مستقبلًا، يحتاج المنتج backpressure، partition keys، واختبارات retry؛ لا يمنح exactly-once للـdomain truth. لا توجد stream منشأة الآن. |

## مبدأ event backbone

الـoutbox والـenvelope يتبنيان مرة واحدة حول event ID ثابت، `tenant_id`، aggregate/session key، schema version، وتصنيف البيانات. queue أو broker مجرد relay قابل للاستبدال، ولا يصبح analytics أو AI أو consumer متأخر سببًا لإيقاف simulation worker.

| [RFC 9562: UUIDs](https://datatracker.ietf.org/doc/rfc9562/) | RFC 9562 هو المعيار الحالي للـUUID ويعرّف UUIDv7 كـUnix-epoch time-based. يبين أن UUIDs لا تحتاج سلطة مركزية، وأن UUIDv4 يفتقر إلى database-index locality بينما الترتيب الزمني يعالج ذلك. | تستخدم Nexora UUIDv7-style opaque IDs قابلة للترتيب زمنيًا وليست sequences محلية، مع تجنب ادعاء total order عالمي أو كشف معناه كـauthorization. |
| [Amazon S3: What is S3?](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html) | يصف S3 object storage للبيانات/metadata، lifecycle transitions وversioning وObject Lock وreplication وstrong read-after-write consistency. | `ObjectStorage` interface يجب أن يحتفظ بالـreference وhash وmetadata وclassification وretention؛ قاعدة البيانات تحفظ المرجع لا الـblob. تعيين S3 سحابي توضيحي فقط، والتنفيذ الحالي local filesystem dev. |
| [ClickHouse: Distinctive Features](https://clickhouse.com/docs/about-us/distinctive-features) | ClickHouse column-oriented ومناسب لتحليلات grouped/range; يذكر صراحة عدم وجود full-fledged transactions وعدم كفاءة point queries الفردية. | ClickHouse وجهة analytics مشتقة مستقبلية، لا system of record ولا owner للـsimulation state، ولا يُنشر الآن. |
| [Apache Iceberg](https://iceberg.apache.org/) | Iceberg open table format للجداول التحليلية الكبيرة، يدعم schema evolution وhidden partitioning وtime travel وcompaction والعمل المتزامن لعدة engines. | يحتفظ المسار المستقبلي بـParquet/object storage أولًا، ويضاف Iceberg فقط عند حاجات جدول تحليلي قابلة للقياس (multi-engine evolution/reproducibility)، لا كتعقيد مبدئي. |

## مبدأ object وanalytics storage

الـartifact يمثله reference immutable مع content hash وmetadata وretention/classification، بينما تكون التحليلات replica أو derived store قابلة لإعادة البناء من أحداث مرخصة أو exports، وليست مصدر الحقيقة. يتدرج lifecycle إلى hot OLTP/session artifacts، warm derived analytics/object، ثم cold archive؛ وتحدد retention سياسة البيانات لا convenience التقني.

| [pgvector](https://github.com/pgvector/pgvector) | يضيف vector similarity search إلى PostgreSQL مع exact وapproximate HNSW/IVFFlat. يوضح trade-offs recall/speed/memory وmultitenancy filtering، ويوصي بقياس `EXPLAIN (ANALYZE, BUFFERS)` ومقارنة recall exact/approximate. | pgvector أول خيار متى ظهرت حاجة knowledge retrieval غير سريرية ومقاسة؛ لا embeddings ولا AI consumer في الدفعة. يضاف OpenSearch فقط بعد إثبات أن capabilities أو operational isolation لا يحققها PostgreSQL/pgvector. |
| [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html) | دليل AWS مهيكل صراحة حول تصميم NoSQL، partition/sort keys، secondary indexes، time series، queries/scans، والعمليات concurrent. | DynamoDB ليس بديلًا افتراضيًا لـOLTP العلائقي؛ يقيّم فقط عند access pattern مثبت بمفتاح/ترتيب مستقرين أو توزيع write لا يلبّيه PostgreSQL بعد قياس. |
| [Redis data-store guide](https://redis.io/docs/latest/develop/get-started/data-store/) | Redis store في الذاكرة بمفاتيح وهياكل بيانات من نوع dictionary/hash. | Cache/lease/rate limit/presence وephemeral coordination فقط؛ لا history أو evidence أو source of truth. لا Redis/Valkey منشأ في الدفعة. |
| [OpenSearch vector search docs](https://docs.opensearch.org/latest/vector-search/) | توثيق OpenSearch يظهر أن vector/search deployment يتضمن installation، cluster formation، security، availability/recovery، backpressure، وindex lifecycle. | لا نضيف OpenSearch لأجل JSON أو vector مبكر. trigger يتطلب benchmark يثبت حاجة full-text/faceted/vector/search isolation وتكلفة تشغيل/حوكمة مقبولة. |

## قاعدة الاستبدال لا الإضافة

لا قاعدة جديدة إلا عندما يثبت access pattern وSLO والـdata volume والـconsistency boundaries أن PostgreSQL أو object storage أو cache المؤقت لا يلبيها. كل derived index قابل لإعادة البناء من canonical records المرخصة، ولا تملك DynamoDB أو OpenSearch أو ClickHouse حقائق تعلم أو simulation state.
