# مقارنة مخازن التحليلات ومسار lakehouse

**الحالة:** هدف بيانات مستقبلي.  
**غير منفذ:** لا ClickHouse ولا Parquet pipeline ولا Iceberg catalog ولا data lake منشأ في هذه الدفعة.

## الحكم

التحليلات ليست مصدر الحقيقة لـNexora. تبدأ المنصة بـ**canonical records** في OLTP، وartifacts في object storage، وevents مرخصة عبر outbox. يمكن لاحقًا إنشاء طبقة analytics مشتقة قابلة لإعادة البناء: ClickHouse للتحليلات منخفضة الكمون عند ثبوت workload، وobject storage + Parquet للـbulk/history، ثم Iceberg عندما يصبح table management متعدد المحركات وschema evolution/time-travel متطلبًا مثبتًا.

> يجب ألا يوقف فشل analytics ingestion أو dashboard أو AI feature simulation session. الحقيقة التي تعتمدها واجهة المتعلم أو قرار أمان لا تسترجع من derived analytics store.

## المقارنة

| الطبقة | owner | أفضل استخدام | ليست مناسبة لـ | حالة Nexora |
|---|---|---|---|---|
| PostgreSQL OLTP | Control Plane | entity truth، assignments، session registry، audit/outbox | raw telemetry عالي الحجم أو aggregations الواسعة | target authoritative. |
| Object storage | Artifact/data plane | replay/export/assets/checkpoint artifacts، ملفات Parquet | relational transactions أو query-by-row authorization | interface منفذ محليًا فقط لاحقًا في الدفعة. |
| ClickHouse | Analytics plane | aggregates، cohort/product analytics، استعلامات columnar واسعة | source of truth، معاملات كاملة، point lookup individual | deferred حتى trigger. |
| Parquet on object storage | Lake landing/archive | batch exports، immutable history، interchange | table governance متعدد المحركات وحده | deferred policy/path. |
| Iceberg over object storage | Lakehouse table management | schema evolution، hidden partitioning، time travel، multi-engine table management | أول storage layer بلا consumer/maintenance owner | deferred حتى trigger. |
| Redis/Valkey cache | Ephemeral plane | cached projections، rate limits، leases/presence | history أو evidence أو canonical state | deferred، interface فقط. |

تصف ClickHouse نفسها كنظام column-oriented، وتذكر غياب full-fledged transactions وعدم كفاءتها في point queries الفردية؛ وهذا ينسجم مع كونها وجهة derived analytics لا OLTP truth.[1] يصف Iceberg نفسه كـopen table format لجداول تحليلية كبيرة مع schema evolution وhidden partitioning وtime travel وcompaction، لكنه يضيف catalog/maintenance/execution concerns لا حاجة لها قبل consumers حقيقيين.[2]

## canonical مقابل derived

| نوع السجل | canonical source | derived consumers المسموحون | إعادة البناء | قاعدة الوصول |
|---|---|---|---|---|
| institution/course/cohort/assignment | OLTP | dashboards/read models | من OLTP وoutbox | tenant authorization. |
| simulation session registry/status | OLTP + session worker contract | operations dashboard | من OLTP/session event summary | لا يملك analytics تغييرها. |
| platform event envelope | OLTP outbox ثم backbone عند trigger | analytics، audit projection، exporters | من outbox/bus retention حسب policy | payload classified/minimized. |
| telemetry/rollup | event/telemetry ingestion policy | ClickHouse/lake | من raw authorized events أو aggregates | sampling/retention موثقين. |
| replay/export/artifact | object storage + metadata reference | viewers/export pipeline | hash + metadata؛ لا overwrite صامت | scoped reference authorization. |
| AI insight | async derived output | debrief/search assist عند scope مستقبلًا | يمكن invalidation/regenerate | ليس truth ولا patient/clinical advice. |

## hot / warm / cold lifecycle

| الطبقة الزمنية | بيانات نموذجية | store/path | خصائص الاسترجاع | سياسة التغيير |
|---|---|---|---|---|
| Hot | active session registry، current metadata، outbox pending، short-lived cache | OLTP + worker memory + future cache | fast operational | transactional/canonical حيث يلزم. |
| Warm | completed summaries، dashboards، replay artifacts، recent Parquet exports | OLTP summaries + object storage + future analytics | derived/queryable | immutable artifacts أو rebuildable projections. |
| Cold | long retention exports، compliance archive عند تعريف policy | object storage archive / future lake | slower asynchronous | retention/legal hold/deletion policy، لا convenience. |

توثق S3 أن object store يحتفظ بالبيانات والـmetadata، ويدعم lifecycle transitions وversioning وObject Lock/replication، وأن reads بعد PUT/DELETE strong consistent. هذه خصائص cloud mapping مفيدة، لكن Nexora لا تربط contract بـS3 أو storage class محدد؛ يحتفظ العقد بـobject ID وcontent hash وmetadata وclassification وretention، بينما يبقى provider pluggable.[3]

## مسار البيانات المستقبلي

```text
Control-plane OLTP transaction
        │
        ├─► canonical entity + outbox row
        │                  │
        │                  └─► relay / future bus ─► derived analytics
        │                                           ├─► ClickHouse (interactive aggregates)
        │                                           └─► Parquet object storage ─► Iceberg (when justified)
        │
Simulation worker ─► session-safe events / artifact references ─► same derived path
```

الـobject storage لا يعكس snapshot الداخلية مباشرة ولا يعيد تعريف checkpoint semantics الحالية: checkpoints في S0 تظل artifacts محلية داخل session ما لم يعتمد workflow منفصل durability/authorization/replay contract. أي نقل لاحق يمر عبر metadata/reference policy لا عبر كتابة filesystem ad hoc.

## عتبات قرار مسماة

| المعرّف | evidence المطلوب | التغيير المحتمل |
|---|---|---|
| `ANL-CH-01` | cohort/product queries واسعة متكررة تثبت أنها تضر OLTP أو لا تحقق query SLO رغم rollups/indexing | ClickHouse derived store spike مع rebuild/retention/tenant filtering. |
| `ANL-LAKE-02` | batch exports/reprocessing/history تتجاوز DB lifecycle أو تحتاج تنسيقًا columnar portable | Parquet landing في object storage مع catalog-free manifest أولًا. |
| `ANL-ICE-03` | أكثر من engine يحتاج table semantics مشتركة وschema evolution/time-travel/partition maintenance | Iceberg evaluation/catalog owner، لا مجرد إنشاء tables. |
| `ANL-RAW-04` | raw telemetry retention أو ingestion يهدد hot OLTP/outbox | فصل ingest وsampling/rollup policy وobject/lake path. |
| `ANL-PRIV-05` | سياسة retention/delete/export لا تزال غير محددة | توقف نشر analytic payload جديد حتى اعتماد classification/owner. |

## AWS mapping الإيضاحي

في خريطة AWS محايدة العقد، تكون artifacts وParquet على S3، وRDS/Aurora للـOLTP، وClickHouse managed/self-operated قرارًا مستقلًا، ويمكن أن يستقبل Firehose مستقبلًا streams إلى S3. لا يوجد provision ولا vendor lock-in هنا.

## المراجع

[1]: https://clickhouse.com/docs/about-us/distinctive-features "ClickHouse: Distinctive Features"
[2]: https://iceberg.apache.org/ "Apache Iceberg"
[3]: https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html "Amazon S3 User Guide: What is S3?"
[4]: https://docs.aws.amazon.com/whitepapers/latest/build-modern-data-streaming-analytics-architectures/key-considerations-while-building-streaming-analytics.html "AWS streaming analytics considerations (historical reference)"
