# Nexora Data Platform v0.1

**الحالة:** target architecture، لا نشر بنية بيانات.  
**المبدأ:** من يملك الحقيقة لا يلزم أن يخزن كل بايت؛ من يخزن مشتقًا لا يملك الحقيقة.

## سجل الملكية

| dataset | owner | canonical store/path | consumers المصرحون | محظورات |
|---|---|---|---|---|
| tenant/org/user membership/course/cohort | Control Plane | PostgreSQL OLTP | authorization، operations، projections | cache/search كـtruth. |
| scenario catalog/version policy | Control Plane | OLTP metadata + authored asset reference | session allocator، authorized clients | mutable scenario head يغير session نشطة. |
| active session execution | Simulation Data Plane | VPE/Pulse memory/runtime | facade/host فقط | direct client/Pulse access، analytics writeback. |
| session registry/lifecycle | Control + worker contract | PostgreSQL OLTP | allocator، audit، operations | ClickHouse أو cache canonical state. |
| platform event handoff | owner transaction | PostgreSQL transactional outbox | relay/authorized consumers | direct DB+broker dual write. |
| raw/derived telemetry | data plane policy | future stream/lake/analytics | operations/product analytics | block tick أو كشف inner state. |
| artifacts (replay/export/assets/checkpoint) | artifact plane | object storage + OLTP reference | authorized viewer/export | BLOB/large JSONB default. |
| analytical aggregates | Analytics Plane | future ClickHouse/lake | dashboards/research under policy | source for command authorization/completion. |
| AI-derived result | async derived plane | future derived store/reference | optional user-facing assist after approval | medical truth / simulator control. |

## canonical records وderived records

الـcanonical record هو السجل الذي يملك القرار والتعديل والتدقيق. يجب أن يستطيع أي derived store أن يعاد بناؤه أو أن يعلن بوضوح عدم اكتماله من canonical sources المرخصة. لا تتحول سرعة query أو سهولة export إلى نقل ownership.

| الخاصية | canonical | derived |
|---|---|---|
| يغير business/session truth | نعم، ضمن owner فقط | لا. |
| يحتاج transaction/constraint | غالبًا | لا بالضرورة. |
| يسمح بالـrebuild | مصدر rebuild | يجب أن يكون rebuildable أو يملك ADR خاص. |
| يتحمل lag/failure | لا بلا policy | نعم، مع lag/quality indicator. |
| مثال | assignment، session status، outbox event | dashboard rollup، search index، AI summary. |

## storage strategy

### PostgreSQL OLTP

PostgreSQL هو target system of record للـControl Plane، مع `jsonb` محدود للـmetadata/structure المتغيرة وtyped columns للعلاقات والمسارات الحرجة. لا يستخدم raw telemetry المتزايد أو artifact blobs. يدعم PostgreSQL `jsonb` وفهارس GIN/expression indexes، لكن تحديث المستند الكبير يقفل الصف بالكامل؛ لذلك يكون الاستخدام document-bounded/query-driven لا append-log.[1]

### Object storage

كل artifact يتعامل معه عقد `ObjectStorage` كالآتي: `object_id` ثابت، content hash (`sha256`)، length/content-type، creator/time، data classification، retention policy، logical artifact type، optional version/provider reference. تحفظ OLTP references فقط ولا تعتمد client على bucket key كصلاحية.

| artifact class | hot use | retention/input policy | ملاحظة S0 |
|---|---|---|---|
| `scenario_asset` | authored content delivery | license/version/hash | لا يعدل S0 schema. |
| `session_checkpoint` | future recovery only | restricted + compatibility review | checkpoints الحالية ليست durable object workflow. |
| `session_replay` | review/research future | immutable/provenance/redaction | لا يوجد replay promise الآن. |
| `session_export` | learner/admin output | scoped access/expiry/audit | no public direct object URL. |
| `research_export` | approved de-identified use | policy/legal review | no re-identification assumption. |

توضح وثائق S3 أن object storage يدعم metadata/versioning/lifecycle/retention features وstrong consistency؛ وهذا يساعد في cloud mapping، لكنه لا يجعل S3 provider ملزمًا للعقد ولا يحدد retention طبيًا أو قانونيًا بنفسه.[2]

### Cache

`Cache` future interface يعزل provider ويقتصر على projections القابلة لإعادة البناء، rate limiting، presence، أو lease optimization بعد تعريف fallback. لا يحمل cache owner للـhistory أو assignment أو evidence أو session state. كل key tenant-namespaced، وكل cache contract يحدد TTL وinvalidation وstale semantics.

### Event/analytics/lake

تكتب canonical event إلى outbox في معاملة owner ثم يخرج relay. ClickHouse، إن ظهر، store تحليلي مشتق لا يقدم full transactions ولا point lookup economic على مستوى OLTP، وفق خصائصه الموثقة.[3] يبدأ lake path بـParquet/object storage عندما تبرر batch export أو archive/reprocessing ذلك؛ يتأخر Iceberg حتى تظهر حاجة multi-engine table semantics وschema evolution/time travel الفعلية.[4]

## JSONB، NoSQL، وvector policy

| التقنية | الوضع الافتراضي | trigger الاستخدام | لا تستخدم لأجل |
|---|---|---|---|
| JSONB PostgreSQL | مسموح ضمن حدود | document metadata محدد/queries مثبتة | استبدال relational integrity أو append telemetry. |
| MongoDB | غير مختار | ADR مستقل/access pattern لا يحققه PG | JSON فقط. |
| DynamoDB/Cassandra | غير مختار | key-based high-write/read pattern مثبت وconsistency model محدد | label «million users». |
| Redis/Valkey | deferred ephemeral | cache/lease/rate limit مع fallback | canonical history. |
| pgvector | first vector option future | approved non-clinical semantic search benchmark | LLM truth/medical advice. |
| OpenSearch | deferred derived index | PG/pgvector لا يحققان search/operational isolation مثبت | JSON storage أو source truth. |

## hot / warm / cold data lifecycle

| tier | latency objective | datasets | system | lifecycle action |
|---|---|---|---|---|
| Hot | operational/session cadence | active registry، outbox pending، current projection | OLTP + VPE memory + future cache | bounded retention/purge per policy. |
| Warm | dashboard/review/recent artifact | completed summaries، rollups، approved artifacts | OLTP summaries/object/derived analytics | compaction/rollup/rebuild support. |
| Cold | archive/research/compliance policy | historical exports/Parquet/raw where approved | object archive/future lake | lifecycle transition/legal hold/deletion proof. |

لا تحدد هذه الوثيقة أيام الاحتفاظ أو درجات storage class؛ فهذه سياسات منتجات/قانون/مراجعة سريرية غير معتمدة. يحدد كل dataset owner الحقول التي لا بد أن تحتفظ بها، والآلية التي تثبت deletion أو hold أو export authorization.

## quality، lineage، والـprivacy

كل event/export/artifact future يحمل على الأقل source ID/version، tenant context عند انطباقه، producer، schema version، classification، creation timestamp، وhash أو integrity evidence متى كان artifact. لا ينقل pipeline قيمة `RESTRICTED` إلى analytics أو research من دون data contract يحدد minimization، recipient، retention، وredaction/de-identification.

| جودة/سياسة | signal | response |
|---|---|---|
| outbox lag | oldest pending age / attempts | retry/alert، لا block simulation. |
| projection lag | source watermark vs consumer watermark | freshness indicator/rebuild. |
| schema mismatch | consumer rejects version | quarantine/DLQ/replay after fix. |
| hash mismatch | artifact integrity check fails | deny use/investigate، لا overwrite. |
| unauthorized tenant reference | validation/RLS test/audit | deny، security incident path. |

## AWS mapping الإيضاحي

| capability | possible AWS service | portability boundary |
|---|---|---|
| OLTP | RDS/Aurora PostgreSQL | repository/transaction interface. |
| object | S3 | ObjectStorage reference/hash contract. |
| cache | ElastiCache | cache interface/fallback semantics. |
| event queue | SQS | publisher/consumer/event envelope. |
| stream | MSK/Kinesis | event routing/partition key/consumer contract. |
| analytics/lake | ClickHouse + S3/Parquet/Iceberg | canonical export schema, not provider API. |

## explicit non-decisions

لا توجد multi-region replication plan أو active-active writes، ولا service deployment، ولا Data Lake implementation، ولا OpenSearch/NoSQL provisioning. يبقى customer medical/assessment validity خارج scope البيانات التقنية. ولا تغّير هذه الوثيقة S0 event envelope الحالي؛ يضاف platform envelope مستقل versioned في المرحلة التالية.

## المراجع

[1]: ../research/postgres-scale-review.md "Nexora: مراجعة PostgreSQL القابلة للتوسع"
[2]: https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html "Amazon S3: What is S3?"
[3]: ../research/analytics-store-comparison.md "Nexora: مقارنة مخازن التحليلات ومسار lakehouse"
[4]: ../research/nosql-when-and-why.md "Nexora: NoSQL وcache وvector/search"
