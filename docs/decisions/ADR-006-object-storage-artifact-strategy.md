# ADR-006: استراتيجية artifacts في Object Storage

**الحالة:** Accepted for contract/local adapter; cloud object storage deployment deferred.  
**التاريخ:** 2026-08-23.

## السياق

تحتاج Nexora إلى assets وexports وreplay/checkpoint artifacts مستقبلية قد تكون كبيرة أو طويلة العمر. وضع bytes في PostgreSQL rows أو event payloads يخلط lifecycle والحجم والوصول مع OLTP. كما أن checkpoints في S0 لا تساوي snapshots الخفيفة ولا يوجد durable recovery workflow مثبت.

## القرار

تعتمد المنصة `ObjectStorage` provider-neutral contract. يخزن artifact كـimmutable bytes مع `object_id` و`sha256` وlength/content-type وartifact type/classification/retention intent وtenant scope وmetadata محدودة. يخزن OLTP **reference فقط**، ويبقى authorization/association/audit في Control Plane. التنفيذ الحالي local filesystem development adapter؛ لا S3 bucket أو cloud provider.

| الأصل | مكان bytes | مكان metadata المرجعية | مبدأ الوصول |
|---|---|---|---|
| scenario asset | object storage | catalog OLTP | authorized catalog visibility. |
| session export | object storage | session/export OLTP reference | scoped request/audit. |
| checkpoint/replay future | object storage عند contract معتمد | session registry/artifact metadata | no resume promise قبل validation. |
| analytics/research export | object storage/lake path | governed export record | classification/approval/retention. |

توضح S3 أن object storage يدعم lifecycle/versioning/replication/Object Lock وmetadata، وهي capabilities مفيدة للـmapping السحابي؛ لكن العقد لا يربط Nexora بـS3 أو يحدد retention medical/legal policy من تلقاء نفسه.[1]

## البدائل المرفوضة

| البديل | سبب الرفض |
|---|---|
| byte/blob افتراضي في PostgreSQL | يربك OLTP growth، backup، lifecycle، ويحرم provider optimization. |
| artifact bytes داخل platform event | حجم/retention/privacy/replay لا تلائم envelope. |
| direct public object URLs | object key ليس authorization. |
| writable/overwrite artifact key | يضر provenance/integrity؛ content مختلف = object جديد. |
| durable checkpoint claim الآن | S0 لا يثبت workflow/replay compatibility. |

## العواقب

يجب أن يبقى hash mismatch failure قابلًا للتدقيق، وأن يكون metadata JSON-bounded ولا يحمل secrets/PII غير المصرح بها. يحتاج adapter cloud مستقبلي إلى encryption/KMS، IAM/presigned access صادر من authorization layer، lifecycle/retention، monitoring، backup/DR، واختبارات retrieval/integrity. لا ينفذ local adapter هذه الأمور ولا يدعيها.

أي session recovery feature يمر عبر `SIM-RECOVER-03`: format version، checkpoint/replay validation، ownership/fencing، failure behavior، ومراجعة البيانات. لا يتصل `VpeRuntime` أو `VpePacedHost` مباشرة بـObjectStorage في هذه الدفعة.

## المراجع

[1]: https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html "Amazon S3: What is S3?"
[2]: ../contracts/object-storage-contract-v0.1.md "Nexora Object Storage Contract"
[3]: ../architecture/data-platform-v0.1.md "Nexora Data Platform"
[4]: ../architecture/simulation-session-scaling-v0.1.md "Nexora Simulation Session Scaling"
