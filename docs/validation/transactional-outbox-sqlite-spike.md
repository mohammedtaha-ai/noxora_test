# Transactional Outbox SQLite Spike

**الحالة:** ناجح كـlocal semantics spike فقط.  
**ليس:** PostgreSQL production implementation، ولا queue/broker deployment، ولا proof throughput أو HA أو CDC.

## السؤال

هل يمكن إثبات contract صغير يربط domain mutation وplatform event في transaction واحدة، ثم ينشر خارجها مع retry/duplicate semantics صريحة، من دون ربط VPE أو Pulse ببنية streaming؟

**النتيجة:** نعم، لحدود الـcontract المحلية. يوفر `SQLiteTransactionalOutbox` في `nexora_vpe.platform` معاملة واحدة لـ`domain_state` و`platform_outbox`، ثم relay claim مستقل. يبقى event بعد publisher failure قابلًا لإعادة المحاولة، ويقبل التصميم أن crash بعد publish وقبل mark يسبب delivery مكررة تتطلب idempotent consumer.

## التصميم المنفذ

```text
BEGIN IMMEDIATE
  UPSERT local domain value
  INSERT immutable platform_outbox event
COMMIT

claim pending event ─► publish outside DB transaction ─► mark published
                         │ failure                   │ crash before mark
                         ▼                           ▼
                   release/retry                lease expiry/retry
                                                  (possible duplicate)
```

| الجانب | ما أثبته spike | ما لم يثبته |
|---|---|---|
| atomicity | duplicate `event_id` يفشل ويعيد domain value إلى الحالة السابقة transactionally | PostgreSQL isolation/WAL/load behavior. |
| failure | publisher exception يترك event pending ويزيد attempt على retry | broker outage/backoff/DLQ production policy. |
| duplicate | publish ثم crash-before-mark يعيد نفس `event_id` بعد lease expiry | exactly-once delivery أو consumer implementation. |
| ordering | query pending ترتب بـcreated time/event ID محليًا | distributed order/partition semantics. |
| ownership | claim token + worker ID يمنع mark لclaim قديم | production fencing across durable distributed workers. |
| payload | PlatformEvent JSON/versioned/tenant-aware | PII/medical semantic classification engine. |

## الاختبارات المنفذة

اختبارات `tests/test_platform_boundaries.py` غطت التسع حالات التالية في Python stdlib:

| الاختبار | النتيجة | المعنى |
|---|---:|---|
| UUIDv7 parse/monotonic generator | PASS | IDs قابلة للفرز داخل generator؛ لا total order عالمي. |
| tenant scope validation | PASS | tenant boundary صريحة في contracts. |
| event envelope JSON/versioning | PASS | event مستقل عن S0 runtime. |
| invalid event payload/name rejection | PASS | contract boundaries لا تقبل nonportable payload. |
| atomic domain + outbox rollback | PASS | لا domain update بلا event عند duplicate event insert failure. |
| publisher failure → pending retry | PASS | failure لا يضيع event ولا يدعي success. |
| crash-after-publish duplicate | PASS | duplicate delivery موثقة وevent ID ثابت. |
| content-addressed artifact storage | PASS | bytes/hash/metadata immutable محليًا. |
| tamper detection | PASS | mismatch لا يعامل كartifact صالح. |

الأمر المنفذ:

```bash
PYTHONPATH=src python3 -W error::ResourceWarning -m unittest tests/test_platform_boundaries.py -v
```

والنتيجة الفعلية: **9 tests passed في 0.021s**. هذا زمن local unit test وليس benchmark أو capacity figure.

## failure semantics المعتمدة

> **معاملة domain/outbox تضمن commit معًا؛ relay لا يضمن exactly-once. يجب على المستهلك إزالة التكرار بالـ`event_id`.**

يتفق هذا مع نمط transactional outbox الموثق، الذي يعزل database mutation عن broker publication ويشير إلى إمكان relay delivery المكرر بعد crash.[1] كما ينسجم مع تصميم Debezium outbox الذي يحتفظ بـevent ID وaggregate key للـdedupe/partition ordering مستقبلًا.[2]

## القيود الصريحة

1. SQLite هنا أداة semantics محلية؛ لا يدعم هذا الملف PostgreSQL schema أو `SKIP LOCKED` أو CDC أو logical replication أو connection pooling.
2. لا توجد queue أو Kafka أو Redpanda أو MSK أو Kinesis أو SQS. `EventPublisher` Protocol يمنع coupling المبكر فقط.
3. لا ينشر Relay داخل `VpeRuntime` ولا يغير clock أو Pulse ownership؛ من واجب adapter مستقبلي اختيار events المصرح بها على boundary.
4. claim lease ليس production session-worker lease؛ لا يعالج network partitions أو clock skew أو distributed fencing proof.
5. لا ينفذ consumer dedup store؛ الاختبار يثبت سبب وجوبه لا كفايته.
6. لا تحتوي test payloads على PII أو clinical truth؛ privacy classification policy تحتاج حوكمة منفصلة.

## مسار الترقية

| من | إلى | trigger |
|---|---|---|
| SQLite local spike | PostgreSQL repository/outbox table | بداية Control Plane persistence المعتمدة. |
| direct `EventPublisher` | managed queue | `EVT-QUEUE-01`: work بطيء/retry/DLQ مستقل. |
| polling relay | CDC/stream | `EVT-BUS-02`: multiple replay consumers أو backlog SLO evidence. |
| manual dedup logic | consumer ledger/schema governance | `EVT-SCHEMA-04`: official multi-consumer compatibility. |

## المراجع

[1]: https://microservices.io/patterns/data/transactional-outbox.html "Transactional outbox pattern"
[2]: https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html "Debezium Outbox Event Router"
[3]: ../contracts/platform-event-envelope-v0.1.md "Nexora Platform Event Envelope"
