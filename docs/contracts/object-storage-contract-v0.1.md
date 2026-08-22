# Object Storage Contract v0.1

**الحالة:** contract + local filesystem development implementation فقط.  
**غير منفذ:** لا S3 bucket ولا retention policy production ولا durable checkpoint workflow إلى cloud.

## الغرض

يفصل هذا العقد bytes الكبيرة عن OLTP وعن event payload. يضمن أن كل artifact يملك reference ثابتًا وintegrity metadata وclassification وretention intent قبل أن يظهر لمستهلك. لا يمثل object key أو filesystem path صلاحية وصول، ولا يجعل storage provider جزءًا من domain contract.

## object record

| الحقل | الدلالة | متطلبات |
|---|---|---|
| `object_id` | ID عام opaque/time-sortable | immutable وprovider-neutral. |
| `storage_key` | key داخلي provider-specific | لا يخرج إلى client كـauthorization. |
| `sha256` | content integrity identifier | 64 hexadecimal lowercase؛ يحسب على bytes المخزنة. |
| `byte_length` | حجم bytes | non-negative؛ يطابق read. |
| `content_type` | media/serialization type | required، policy validates allow-list future. |
| `artifact_type` | semantic class | one of registered artifact classes. |
| `classification` | security/data handling class | required. |
| `tenant_id` | ownership إذا كان tenant-owned | required في tenant artifact. |
| `created_at` | UTC audit time | immutable. |
| `retention_class` | lifecycle intent لا provider setting | required. |
| `metadata` | bounded JSON-safe non-sensitive attrs | لا PII/secrets/raw Pulse truth. |

## classes والـretention intent

| artifact type | owner | typical content | retention class | ملاحظات |
|---|---|---|---|---|
| `scenario_asset` | catalog | authored static media/config asset | `PRODUCT_ASSET` | hash/version/license required future. |
| `session_checkpoint` | simulation data plane | checkpoint bytes إذا اعتمدت | `RESTRICTED_SESSION` | لا تدعي S0 support الآن. |
| `session_replay` | simulation/review | replay trace/package إذا اعتمد | `RESTRICTED_SESSION` | compatibility/provenance before restore. |
| `session_export` | control/export | authorized export bytes | `USER_EXPORT` | scoped access/expiry/audit policy. |
| `research_export` | research owner | approved de-identified extract | `RESEARCH_GOVERNED` | separate approval + data contract. |
| `telemetry_bundle` | operations | compressed derived diagnostic data | `OPERATIONS_BOUNDED` | no raw unbounded PII. |

`retention_class` لا يعين عدد أيام أو storage tier في code. تتطلب القيم product/legal/privacy policy منفصلة قبل production. يمكن mapping هذه النوايا لاحقًا إلى S3 lifecycle/Object Lock/versioning أو provider مكافئ؛ توثق S3 هذه capabilities لكنها لا تعرف semantic retention لـNexora.[1]

## العملية

```text
writer bytes + semantic metadata
       │
       ├─ validate classification / type / tenant rules
       ├─ compute SHA-256 and size
       ├─ persist bytes atomically to provider-local staging/final key
       └─ return immutable ObjectRecord
                         │
                         └─ control-plane stores reference in its own transaction policy
```

التنفيذ المحلي يكتب bytes تحت root development محدود ويمنع directory traversal. لا يعطي signed URLs، ولا encryption-at-rest claim، ولا lifecycle daemon. cloud adapter مستقبلي مسئول عن encryption/KMS/access policy/versioning وoperational evidence، فيما يبقى contract ثابتًا.

## ownership/access policy

| العملية | يتطلب | لا يسمح |
|---|---|---|
| `put` | artifact metadata صحيح + writer authorized context future | caller-supplied arbitrary key/path. |
| `get` | reference authorization خارج storage provider | read by raw object ID وحده في public endpoint. |
| `verify` | SHA-256 + length check | treat mismatch as usable data. |
| `delete` | retention/legal/tenant policy future | immediate delete كخيار implementation convenience. |
| `export` | audit + recipient/classification policy | copy to untracked storage. |

قاعدة database هي **store references only**: entity أو event يحمل `object_id` وmetadata reference صغيرة، لا bytes. لا تصبح object storage system of record للـtenant authorization؛ يحتفظ Control Plane بالـpolicy/association/revocation/audit.

## checkpoint clarification

S0 يميز snapshots خفيفة من checkpoints، ولا يملك في هذه الدفعة durable object-storage workflow أو replay/handoff promise. لذلك توفر classes `session_checkpoint` و`session_replay` فقط vocabulary آمنًا لعقد مستقبلي؛ لا توصل `runtime.py` ولا `VpePacedHost` إلى ObjectStorage الآن من دون ADR واختبارات compatibility/recovery.

## security/classification invariants

1. لا secrets/tokens في metadata أو storage key.
2. لا PII أو physiology internals غير المعتمدة في filename أو event payload يشير إلى object.
3. لا توكل client side path أو MIME type وحده؛ future adapter validates policy.
4. hash mismatch أو size mismatch يجعل object غير صالح للاستعمال وينتج failure evidence، لا silent overwrite.
5. `object_id` immutable؛ أي محتوى مختلف يحصل على ID/hash جديدين.
6. classes لا تمنح retention/authorization تلقائيًا؛ policy owner هو من يفعل ذلك.

## AWS mapping الإيضاحي

يمكن أن يربط adapter مستقبلي `ObjectStorage` إلى S3: bytes إلى object، metadata محددة إلى object metadata/tags أو OLTP record، lifecycle إلى class policy، encryption إلى KMS/provider policy، access إلى IAM/presigned URL صادر من authorization layer. لا يوجد SDK أو bucket أو IAM role في المستودع.

## acceptance tests للتنفيذ المحلي

| الاختبار | الغرض |
|---|---|
| put/get يعيد bytes نفسها | correctness. |
| hash/length صحيحان | integrity. |
| tenant/classification/type مطلوبة | metadata validation. |
| traversal أو key غير آمن مرفوض | filesystem boundary. |
| tamper محلي يكشفه `verify` | corruption detection. |
| duplicate content لا يغير object ID القائم | immutability semantics. |

## المراجع

[1]: https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html "Amazon S3: What is S3?"
[2]: ../architecture/data-platform-v0.1.md "Nexora Data Platform"
[3]: ../architecture/simulation-session-scaling-v0.1.md "Nexora Simulation Session Scaling"
