# مراجعة PostgreSQL القابلة للتوسع

**الحالة:** بحث معماري، لا نشر أو spike قاعدة بيانات.  
**النطاق:** تقييم PostgreSQL كـ**system of record علائقي طويل الأجل** لـControl Plane وmetadata الجلسات، لا كادعاء بسعة إنتاجية أو بديل عن مسار telemetry/analytics المشتق.

## الخلاصة

يوصى بـ**PostgreSQL كمرشح OLTP authoritative** لـNexora، وليس كحل مؤقت. السبب هو توافقه الطبيعي مع علاقات المؤسسة والبرامج والمقررات والتعيينات والعضويات والتدقيق والمعاملات، مع إمكان استخدام `jsonb` بصورة مقيدة للوثائق المتغيرة. لا تعني هذه التوصية أن PostgreSQL ينبغي أن يستقبل كل tick أو كل artifact أو كل استعلام تحليلي؛ بل يتطلب الفصل بين الحقيقة العلائقية، artifacts خارج القاعدة، وtelemetry/analytics القابلة لإعادة البناء.

> لا توجد PostgreSQL أو RLS أو replication أو connection pooler أو migration framework مفعلة في هذه الدفعة. ما يلي هدف تصميم ومجموعة عتبات تحقق، لا إعداد تشغيل.

| البعد | قرار التصميم المستهدف | الحد المقصود |
|---|---|---|
| الحقيقة التجارية | PostgreSQL OLTP | المؤسسات، الهويات، العضويات، السيناريوهات، التعيينات، session metadata، audit references، outbox. |
| الوثائق المرنة | `jsonb` مع schema application-level | metadata وconfig وpayloads محدودة، لا history متزايد أو blobs. |
| عزل tenant | `tenant_id` في كل جدول tenant-owned + قيود وفلاتر تطبيق + RLS candidate | RLS دفاع إضافي، لا بديل عن authorization. |
| الملفات الكبيرة | Object storage + references في OLTP | replay packages، exports، assets، artifacts؛ لا BLOB store افتراضي. |
| التحليلات | Derived store في المستقبل | ClickHouse/lake لا يمتلكان truth أو session control. |
| events | transactional outbox | لا dual-write مباشر إلى broker. |

## الدليل والممارسات المقيدة

توثق PostgreSQL أن `jsonb` يخزن تمثيلًا ثنائيًا محللًا ويدعم الفهرسة، وأنه الخيار المعتاد غالبًا على `json`؛ لكنها تنبه في الوقت نفسه إلى أن تعديل مستند كبير يقفل الصف بكامله، ولذلك ينبغي أن يمثل المستند datum صغيرًا نسبيًا لا سجلًا متناميًا دائمًا.[1] تدعم GIN وexpression indexes استعلامات JSONB مختلفة، لكن المفاضلة بين الفهرس العام والمستهدف مرتبطة بالاستعلام الفعلي وحجم الفهرس، لا بقائمة فهارس افتراضية.[1]

يدعم PostgreSQL RLS لفرض policy على الصفوف المعروضة أو المعدلة، ولكن roles ذات `BYPASSRLS` وsuperusers ومالك الجدول قد يتجاوزونها، كما أن integrity constraints قد تتجاوز RLS. لذلك يكون التصميم الصحيح هو tenant-scoped application authorization أولًا، ثم RLS محكم بأدوار اتصال غير مالكة للجداول كدفاع ثانٍ، مع اختبار صريح لمسارات الإدارة والنسخ الاحتياطي.[2]

التقسيم الجدولي متاح بصيغ range/list/hash، ويعطي فائدة عندما يكون الجدول كبيرًا بما يكفي أو يحتاج حذف/أرشفة أجزاء زمنية بسرعة، لكنه يفرض قيودًا مهمة: unique/primary key على الجدول المقسم يجب أن يتضمن مفتاح التقسيم. لذلك لا يُفعّل partitioning الآن، ولا يُستخدم `tenant_id` مفتاح تقسيم تلقائيًا؛ يبدأ عند table-specific access/lifecycle evidence، وخصوصًا telemetry أو outbox/archive tables الزمنية.[3]

التكرار المنطقي يعمل بنموذج publish/subscribe على replication identity، ويفيد لاحقًا في إرسال subset أو تغذية تحليلية أو migration؛ إلا أن الكتابة المتزامنة على subscriber قد تولد conflicts. لذلك هو مسار migration/derived data مستقبلي، لا عقد events ولا بديل عن outbox.[4]

يوضح توثيق PostgreSQL أن زيادة `max_connections` تزيد تخصيص الموارد، وأن القيمة النموذجية الافتراضية تقارب 100 اتصال. لذلك يعد connection pooling/إدارة الاتصال جزءًا من trigger تشغيل مستقبلي قبل رفع الاتصالات بلا قياس.[5] وتوضح دراسة OpenAI المنشورة أن PostgreSQL يمكن أن يدعم أحمال قراءة كبيرة عبر replicas وcaching وrate limiting وworkload isolation وquery/schema discipline، مع إبقاء كاتب واحد غير مقسم في حالتهم؛ لكنها حالة خاصة لا تقدم baseline throughput أو topology قابلة للنسخ إلى Nexora.[6]

## نموذج البيانات والـJSONB

القاعدة هي: **العلاقات والحقول التي تقود authorization أو uniqueness أو lifecycle أو joins أو predicates المتكررة تكون أعمدة typed**. يشمل ذلك على الأقل `id` و`tenant_id` و`created_at` و`updated_at` وstatus وforeign keys وrevision/optimistic-concurrency حيث يلزم. يخصص `jsonb` للـconfiguration أو attributes المتغيرة ذات structure محدد، ويخضع لحد حجم وثيقة وسياسة schema version.

| نمط البيانات | التخزين المستهدف | سبب الاختيار | anti-pattern محظور |
|---|---|---|---|
| institution, program, course, cohort, learner membership | جداول typed | joins وtenant uniqueness وaudit | document واحد ضخم للمؤسسة. |
| scenario manifest/config | typed core + `jsonb` محدد | مرونة مؤلفة مع حقول قابلة للفهرسة | وضع state المتغير للجلسة في manifest. |
| session registry/lease metadata | typed OLTP | ownership، status، optimistic control | تخزين simulation ticks داخل JSONB. |
| platform event/outbox | typed envelope + JSON payload محدد | routing وidempotency وversioning | payload يحمل PII أو internal Pulse truth. |
| checkpoint/replay/export/assets | object storage reference | الحجم والـretention والـhash | BLOBs أو JSONB كبير في OLTP. |

## الحوكمة متعددة المستأجرين

كل جدول يملك بيانات تخص مؤسسة يحمل `tenant_id NOT NULL`، وكل primary/future foreign path يعيد تأكيد انتماء الكائن للـtenant. تكون uniqueness ذات المعنى التجاري tenant-scoped، مثالًا `UNIQUE (tenant_id, external_slug)` حيث ينطبق. تضاف حقول audit موحدة مثل `created_at` و`created_by` و`updated_at` و`updated_by` و`source_request_id`، ولا تُستخدم IDs المتسلسلة المحلية كـexternal identifiers.

الـRLS candidate لا يُفعل قبل توفر contract اتصال وcontext موثقين؛ حينها تكون السياسة مبنية على tenant context مضبوط في المعاملة، ويجب أن تشمل اختبارات negative cross-tenant، وحالات owner/BYPASSRLS، ووظائف worker/admin، ومراجعة backup/export. لا يعالج RLS وحده authorization على مستوى course/cohort/role.

## خارطة التدرج التشغيلي

| المرحلة | ما يبقى في PostgreSQL | ما يخرج منه | ما يقاس قبل التغيير |
|---|---|---|---|
| البداية | Control Plane، session metadata، canonical outbox، audit refs | artifacts الكبيرة، raw telemetry المستمر | query plans، lock waits، pool saturation، outbox age. |
| نمو منضبط | read replicas/priority isolation عند الحاجة | read-heavy derived views إلى replicas/cache | primary write headroom، replica lag، cache miss impact. |
| جداول زمنية كبيرة | metadata والـrollups المهمة | event/telemetry partitions ثم object/analytics exports | حجم الجدول، retention lifecycle، delete/vacuum cost، access windows. |
| عزل workload | truth لكل domain ما زال مضبوطًا | analytics/search/vector derived paths | SLO per workload، noisy-neighbor evidence، rebuild proof. |

## عتبات قرار مسماة

| المعرّف | الدليل المطلوب | القرار الممكن |
|---|---|---|
| `PG-POOL-01` | saturation أو connection storms مثبتة بالقياس | إضافة pooler/ضبط limits، لا رفع connections فقط. |
| `PG-QUERY-02` | خطة `EXPLAIN (ANALYZE, BUFFERS)` أو slow-query telemetry تثبت cost متكررًا | index مستهدف، query reshape، أو isolation. |
| `PG-PART-03` | جدول زمني كبير مع lifecycle/delete أو windowed queries مثبتة | تصميم partitioning زمني وقيوده واختبار detach/restore. |
| `PG-REPL-04` | read workload يفصل عن write truth وreplica lag مقبول موثق | read replica أو logical replication scoped. |
| `PG-SHARD-05` | write bottleneck متكرر لا يعالجه query/schema/rate-limiting/isolation، مع ownership plan | دراسة shard/NoSQL خاصة بالـaccess pattern؛ ليست ترقية تلقائية. |
| `PG-RLS-06` | contract tenant context وأدوار DB واختبارات cross-tenant جاهزة | تفعيل RLS تدريجيًا كـdefense-in-depth. |

## ما لا نستنتجه

لا يُستنتج من دراسة OpenAI معدل throughput لـNexora أو ضرورة replicas/regions أو Sharding أو cache الآن. لا يُستنتج أن JSONB بديل للنموذج العلائقي، أو أن RLS يغني عن authorization، أو أن logical replication يساوي event platform. لا توجد ادعاءات SLA أو forecast في هذا المستند.

## المراجع

[1]: https://www.postgresql.org/docs/current/datatype-json.html "PostgreSQL: JSON Types"
[2]: https://www.postgresql.org/docs/current/ddl-rowsecurity.html "PostgreSQL: Row Security Policies"
[3]: https://www.postgresql.org/docs/current/ddl-partitioning.html "PostgreSQL: Table Partitioning"
[4]: https://www.postgresql.org/docs/current/logical-replication.html "PostgreSQL: Logical Replication"
[5]: https://www.postgresql.org/docs/current/runtime-config-connection.html "PostgreSQL: Connection Settings"
[6]: https://openai.com/index/scaling-postgresql/ "OpenAI: Scaling PostgreSQL to power 800 million ChatGPT users"
