# ADR-004: PostgreSQL كـOLTP authoritative وJSONB مقيد

**الحالة:** Accepted as target architecture; deployment deferred.  
**التاريخ:** 2026-08-23.

## السياق

تحتاج Nexora إلى حقيقة علائقية متعددة المستأجرين للمؤسسات والعضويات والبرامج والمقررات والتعيينات والسيناريوهات وsession registry والتدقيق. يلزم دعم documents متغيرة بصورة محدودة، ومخرج event موثوق، دون افتراض Mongo/NoSQL أو sharding من البداية.

## القرار

يختار التصميم المستهدف **PostgreSQL** كـtransactional system of record للـControl Plane وsession metadata وtransactional outbox. تستخدم `jsonb` للـmetadata/config/payloads المحدودة ذات structure معروف، بينما تكون العلاقات وtenant fields وlifecycle/status والـforeign keys والحقول المتكرر الاستعلام عنها typed columns. لا يوجد PostgreSQL provision أو migration framework أو RLS مفعّل في هذه الدفعة.

| المسألة | القرار | الحد |
|---|---|---|
| multi-tenant ownership | `tenant_id NOT NULL` + tenant constraints + auth | RLS defense-in-depth لاحقًا فقط. |
| JSON documents | `jsonb` bounded/schema-versioned | لا log/history كبير في row واحد. |
| artifacts | object reference في OLTP | لا BLOB default. |
| events | outbox في transaction نفسها | لا DB+broker dual write. |
| read growth | optimize/query/cache/replica بعد evidence | لا sharding initial. |
| analytics | derived system | لا ClickHouse source of truth. |

توضح وثائق PostgreSQL أن `jsonb` قابل للفهرسة وعملي غالبًا، مع تحذير أن تحديث الوثائق الكبيرة يقفل الصف بكامله؛ ولذلك يتوافق القرار مع documents صغيرة ومعزولة، لا rows متنامية بلا حد.[1] كما يمكن لـRLS تقييد الصفوف، لكن لا توجد policies افتراضيًا ويمكن للأدوار ذات الصلاحية تجاوزها؛ لهذا لا يستبدل RLS authorization وrole design.[2]

## البدائل المرفوضة

| البديل | سبب الرفض الآن |
|---|---|
| MongoDB لمجرد JSON | لا يلغي علاقات/constraints/transactions المطلوبة. |
| DynamoDB/Cassandra كـprimary truth | access pattern والـconsistency/operations غير مثبتة. |
| تقسيم/sharding مبكر | لم يظهر write bottleneck أو partition plan. |
| ClickHouse للـOLTP | ليس full-transaction store ولا point lookup owner. |
| Redis للـhistory | ephemeral/cache boundary فقط. |

## العواقب

تحتاج أي PostgreSQL adoption إلى migrations آمنة، pool/connection model، query plan monitoring، outbox relay، backup/restore، وtenant/RLS test package. يضاف partitioning عندما يثبت table-specific lifecycle/query benefit، مع مراعاة أن unique/primary key في partitioned table تتضمن partition key وفق القيود الرسمية.[3] ويقارن أي انتقال NoSQL أو shard مع triggers `KV-02` و`PG-SHARD-05` لا مع عدد learners وحده.

## المراجع

[1]: https://www.postgresql.org/docs/current/datatype-json.html "PostgreSQL: JSON Types"
[2]: https://www.postgresql.org/docs/current/ddl-rowsecurity.html "PostgreSQL: Row Security Policies"
[3]: https://www.postgresql.org/docs/current/ddl-partitioning.html "PostgreSQL: Table Partitioning"
[4]: ../research/postgres-scale-review.md "Nexora: مراجعة PostgreSQL القابلة للتوسع"
