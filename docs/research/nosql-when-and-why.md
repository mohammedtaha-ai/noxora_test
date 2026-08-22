# NoSQL وcache وvector/search: متى ولماذا

**الحالة:** قرار عدم الإضافة الآن، مع عتبات قابلة للفحص.  
**غير منفذ:** لا Redis/Valkey ولا DynamoDB/Cassandra ولا pgvector ولا OpenSearch منشأ أو مرتبط بتدفق S0.

## المبدأ

لا تُختار قاعدة بيانات لأن البيانات «JSON» أو لأن شعارها يوحي بالتوسع. يثبت أولًا **access pattern** وconsistency boundary وSLO وحجم/نمو البيانات وhot-key distribution وretention/rebuild plan. PostgreSQL هو baseline العلائقي، object storage للـblobs، وcache ephemeral فقط. تصبح خدمة إضافية مبررة عندما يفشل baseline تحت قياس محدد أو يفتقد capability لازمة بوضوح.

## decision matrix

| Access pattern / الحاجة | PostgreSQL | Redis/Valkey | NoSQL key-value/wide-column | OpenSearch | trigger وتوقع الاتساق |
|---|---|---|---|---|---|
| tenant entities، memberships، assignments، audit | **نعم، canonical** | لا | لا افتراضيًا | لا | معاملات/joins/constraints وRLS candidate؛ strong OLTP. |
| session registry وlease metadata | **نعم، canonical** | lease cache مستقبلًا فقط | تقييم لاحق فقط | لا | fencing/transaction/owner recovery؛ cache لا يملك truth. |
| cached read model أو rate limit أو presence | source + invalidate | **محتمل ephemeral** | لا | لا | evidence أن latency/load يحتاج cache؛ stale/eviction safe. |
| artifact/replay/export كبيرة | metadata/ref فقط | لا | لا | index optional | object storage + hash/retention؛ immutable reference. |
| raw telemetry/time series | metadata/rollup فقط | لا | ربما عند pattern مثبت | لا | ingest/retention يهدد OLTP؛ analytics/lake path غالبًا أولًا. |
| key-addressed ultra-high write/write hotspots | baseline بعد tuning | لا كـtruth | **تقييم Dynamo/Cassandra** | لا | predictable access path وsustained measured write bottleneck؛ explicit consistency model. |
| full-text/faceted search | محدود/PG FTS إن كفى | لا | لا | **تقييم** | relevance/faceting/index isolation لا يكفيها PG بالقياس؛ index derived/rebuildable. |
| semantic/vector search محدود | **pgvector أولًا** | لا | لا | تقييم لاحق | recall/latency/tenant-filter benchmark؛ لا AI clinical truth. |
| vector/search بخصائص مستقلة وscale تشغيلي مبرر | source of metadata | لا | لا | **تقييم OpenSearch** | pgvector benchmark/operational boundary يفشل؛ async derived index. |

## Redis / Valkey

تصف وثائق Redis النظام كـin-memory data structure store بمفاتيح وهياكل بيانات مثل strings وhashes.[1] لذلك دوره المقترح، عند trigger فقط، هو cache أو rate limiting أو presence أو lease/coordination مؤقت. لا يخزن history أو assessment evidence أو control-plane truth أو session snapshot authoritative. يجب أن يكون أي key مصحوبًا بـtenant namespace وTTL/invalidation/observability، وأن تصح الوظيفة عند miss أو eviction.

## DynamoDB / Cassandra

يركز دليل DynamoDB على تصميم NoSQL وpartition/sort keys وsecondary indexes وqueries/scans وtime-series وconcurrent updates؛ وهذه مؤشرات إلى أن النموذج يبدأ من access patterns لا من نقل جداول عشوائيًا.[2] لذلك لا تصبح DynamoDB أو Cassandra خيارًا إلا إذا وُجد مسار قراءة/كتابة ثابت بمفاتيح معروفة، والتوزيع وwrite throughput والـhot partitions موثقة، وتم تحديد consistency وretention وrepair/migration والـtenant isolation.

لا تنقل entities العلائقية أو audit أو assignment semantics إلى NoSQL لمجرد أنها قابلة للتسلسل JSON. تبقى أي NoSQL projection قابلة لإعادة البناء إن لم تكن قد حصلت على ownership/consistency ADR مستقل.

## pgvector ثم OpenSearch

يوفر pgvector exact وapproximate nearest-neighbor search داخل PostgreSQL، ويعرض صراحة مفاضلات recall مقابل السرعة والذاكرة في HNSW/IVFFlat، مع تنبيه خاص إلى تأثير multitenancy filtering وإلى الحاجة لقياس exact مقابل approximate و`EXPLAIN (ANALYZE, BUFFERS)`.[3] لذلك هو أول اختيار مستقبلي إذا ظهر search semantic محدود ومشروع غير عالي الخطورة، لأن metadata والـtenant constraint يمكن أن تبقى قرب OLTP.

توثق OpenSearch جانبًا تشغيليًا واسعًا: cluster formation وsecurity وavailability/recovery وbackpressure وindex lifecycle.[4] لذلك يبرر فقط عندما تثبت benchmark أن PG/pgvector لا يحققان capabilities أو isolation مطلوبين، مع أن index مشتق من canonical source ويمكن rebuildه. لا تستخدم نتيجة vector أو LLM لتعديل simulation truth أو تقديم medical decision.

## عتبات قرار مسماة

| المعرّف | الدليل الأدنى | قرار التحول |
|---|---|---|
| `CACHE-01` | cacheable read path معلوم، hit/miss risk وinvalidation/TTL وfallback SLO مختبرة | إضافة Cache interface/provider، لا نقل truth. |
| `KV-02` | sustained key-based write/read pattern ببيانات load/hot-key وconsistency/repair requirements | DynamoDB/Cassandra proof-of-access-pattern وADR خاص. |
| `SEARCH-03` | full-text/facet/relevance query لا تحققها PostgreSQL بعد plan/index/rollup measurement | OpenSearch evaluation مع rebuild/delete/tenant filter plan. |
| `VECTOR-04` | use case approved non-clinical، corpus وrecall/latency/tenant filtering SLO موثق | pgvector spike أولًا؛ لا embedding deployment في هذه الدفعة. |
| `VECTOR-05` | pgvector benchmark/operations يثبت عدم الكفاية وOpenSearch capability محدد | OpenSearch/vector ADR جديد وderived synchronization. |
| `HOTKEY-06` | top-key skew أو partition/write pressure يسبب فشل SLO بعد تحسين schema/query/rate-limit | redesign key/splitting أو NoSQL evaluation، لا scale-out عشوائي. |

## ما لا نفعله

لا Mongo لمجرد JSON، ولا DynamoDB/Cassandra لمجرد مليون learner، ولا Redis كمخزن سجل/تاريخ، ولا OpenSearch كـsystem of record، ولا pgvector أو LLM لمحتوى سريري أو قرار patient. لا توجد أرقام سعة أو forecast في هذا المستند.

## المراجع

[1]: https://redis.io/docs/latest/develop/get-started/data-store/ "Redis: in-memory data structure store"
[2]: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html "DynamoDB Best Practices"
[3]: https://github.com/pgvector/pgvector "pgvector documentation"
[4]: https://docs.opensearch.org/latest/vector-search/ "OpenSearch Vector Search Documentation"
[5]: https://www.postgresql.org/docs/current/datatype-json.html "PostgreSQL JSON Types"
