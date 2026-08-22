# Nexora Scale Roadmap v0.1

**القاعدة:** كل انتقال ينتج من دليل access pattern أو failure/SLO أو compliance، وليس من رقم مسجلين وحده.  
**الحالة الآن:** contracts/documents/local SQLite spike فقط؛ لا infrastructure deployment.

## المسار المرحلي

| المرحلة | يبقى/يُنفذ | لا يُنفذ | proof قبل المرحلة التالية |
|---|---|---|---|
| S0 المثبت | VPE/Pulse single owner، facade محلي، host paced، contract scenario | Unity، cloud API، distributed workers | Gate 0/medical review كما هي. |
| Scale-ready boundaries | platform envelope، UUIDv7-style، tenant contracts، outbox SQLite spike، local object storage | PostgreSQL deployment، queue، cache، broker | contract tests + architecture review. |
| Control Plane persistence | PostgreSQL OLTP + migrations/outbox production adapter عند product scope | analytics store/NoSQL افتراضي | schema/RLS readiness، transactional/load tests، ops owner. |
| async work isolation | managed queue عند evidence | event backbone طويل retention بلا consumer | `EVT-QUEUE-01`, DLQ/idempotency/alert runbook. |
| session worker pool | registry/lease/fencing بعد capacity evidence | transparent resume/active-active sessions | `SIM-POOL-01`, `SIM-FENCE-02`, chaos/recovery tests. |
| streaming/analytics | bus/ClickHouse/Parquet عند workload | Iceberg/Kafka لمجرد scale label | `EVT-BUS-02`, `ANL-CH-01`, `ANL-LAKE-02`. |
| multi-region/search/NoSQL | only bounded services for proven need | blanket database/service migration | region/search/NoSQL ADR + benchmark + security review. |

## trigger register

| trigger | evidence package | reversible first step | irreversible step الممنوع بلا proof |
|---|---|---|---|
| `PG-POOL-01` | connection telemetry/pool saturation/slow request impact | pooler/config spike | globally increasing DB connections. |
| `PG-PART-03` | time-table size, lifecycle delete cost, query windows | partition design migration rehearsal | automatic partitioning every tenant table. |
| `EVT-QUEUE-01` | slow async work, retries, DLQ need | queue-backed one consumer | all events move to queue. |
| `EVT-BUS-02` | multiple independent replay consumers, measurable lag/retention SLO | Kafka/Redpanda/MSK/Kinesis contract spike | broker fleet deployment. |
| `SIM-POOL-01` | active-session load test, host saturation, blast radius | allocator/lease test environment | multi-owner VPE/Pulse. |
| `SIM-RECOVER-03` | product resume requirement + checkpoint/replay compatibility proof | artifact/recovery validation | advertising seamless resume. |
| `ANL-CH-01` | analytical query load harms OLTP or misses SLO | derived export/rebuild spike | ClickHouse as truth. |
| `ANL-ICE-03` | multiple engines need governed table features | Parquet manifest/catalog evaluation | lakehouse platform with no owner. |
| `VECTOR-04` | approved non-clinical use case + recall/latency/tenant benchmark | pgvector experiment | OpenSearch/vector fleet by default. |
| `KV-02` | stable key pattern/hot-key data/consistency model | NoSQL proof-of-pattern | relational data wholesale migration. |
| `PLAT-REGION-03` | written residency/RPO/RTO/write ownership requirement | DR/placement design | active-active multi-region writes. |
| `PLAT-K8S-04` | ECS/Fargate/equivalent limitations measured and team operating model | workload study | Kubernetes adoption as scale signal. |

## deployment mapping, not deployment plan

| capability | initial cloud-neutral posture | AWS illustration | explicit deferment |
|---|---|---|---|
| service/runtime | modular boundaries | ECS/Fargate first | EKS until `PLAT-K8S-04`. |
| OLTP | PostgreSQL target | RDS/Aurora | provision/database migration. |
| async | outbox contract | SQS | queue setup until `EVT-QUEUE-01`. |
| backbone | envelope/partition key | MSK/Kinesis | Kafka/Redpanda/MSK/Kinesis deployment. |
| object | interface/local dev | S3 | bucket/KMS/IAM/lifecycle configuration. |
| cache | interface only | ElastiCache | Redis/Valkey runtime. |
| analytics | derived schemas | ClickHouse + S3/Parquet/Iceberg | analytics/lake deployment. |
| observability | correlation/metrics vocabulary | CloudWatch/OTel | cloud telemetry integration. |

## acceptance rule

ترقية واحدة تملك: owner تشغيلي، schema/API contract، baseline measurement، success/failure SLO، rollback/rebuild plan، tenant/privacy review، load/failure tests، وتقرير قرار. إذا غاب أحدها، تبقى capability deferred حتى لو بدا الخيار تقنيًا شائعًا.

## المراجع

[1]: capacity-model-v0.1.md "Nexora Capacity Model"
[2]: platform-scale-target-v0.1.md "Nexora Platform Scale Target"
[3]: ../research/postgres-scale-review.md "Nexora: مراجعة PostgreSQL القابلة للتوسع"
[4]: ../research/nosql-when-and-why.md "Nexora: NoSQL وcache وvector/search"
