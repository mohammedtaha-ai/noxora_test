# Nexora Platform Scale Target v0.1

**الحالة:** target architecture — **Scale-ready, not scale-now**.  
**المالك:** فريق المنصة.  
**حدود الدفعة:** لا Unity، ولا FastAPI/Pydantic service، ولا PostgreSQL/Redis/Kafka/ClickHouse/MongoDB/DynamoDB/Cassandra/Kubernetes/AWS provisioning في هذه الدفعة.

## قرار التصميم

تصمم Nexora كمنصة متعددة المستأجرين تفصل بوضوح بين **Control Plane** الذي يملك الحقيقة التجارية والـOLTP، و**Simulation Data Plane** الذي يدير التنفيذ الحي للمحاكاة وPulse وtelemetry وartifacts. لا يعني هذا البدء بـmicroservices أو نشر 15 قاعدة بيانات؛ يبدأ المنتج modular monolith أو وحدات تشغيلية محددة العقد حول outbox وobject storage وsession worker lease. يصبح الفصل التشغيلي أو الخدمة المستقلة قرارًا لاحقًا عندما تثبت الحدود ببيانات الحمل والفشل والملكية.

> **قاعدة لا تقبل التفاوض:** يبقى VPE مالك simulation time، ويظل Pulse single-owner داخل session worker. لا تملك واجهة العميل أو Control Plane أو event consumer ساعة المحاكاة أو Pulse state أو LLM truth.

## المنظر المنطقي

```text
                         ┌─────────────────────────────────────────┐
                         │              Control Plane              │
                         │  tenants · users · roles · courses      │
                         │  scenarios · assignments · audit        │
                         │  PostgreSQL OLTP + transactional outbox │
                         └───────────────┬─────────────────────────┘
                                         │ authorized command / event contract
                                         ▼
┌──────────────┐               ┌─────────────────────────────────────────┐
│ Learner      │  client-safe  │           Simulation Data Plane          │
│ client future├──────────────►│ session registry · worker lease/heartbeat│
│ Unity later  │    facade     │ VPE/Pulse single-owner · snapshot view   │
└──────────────┘               │ artifacts · allowed platform events      │
                               └───────┬───────────────────┬─────────────┘
                                       │                   │
                                       ▼                   ▼
                            Object storage refs      Outbox / future relay
                            hashes + metadata             │
                                                           ▼
                                              derived analytics / AI async
                                              (never blocks a live session)
```

لا يعرض الرسم process topology منشورًا؛ بل يحدد **ownership boundaries**. في S0 الحالي تكون `VpeClientFacade` و`LocalFacadeHttpServer` و`VpePacedHost` داخل boundary محلي headless فقط، ويظل هذا صحيحًا حتى يعتمد transport/service منفصل بعد gate مناسب.

## مسؤوليات الطائرات

| المجال | يملك | لا يملك | source of truth المستهدف |
|---|---|---|---|
| Control Plane | tenant/org، identities، roles، program/course/cohort، scenario catalog، assignment، consent/policy metadata، audit، command authorization | Pulse، simulation time، raw client UI state، derived analytics truth | PostgreSQL OLTP. |
| Simulation Data Plane | session lifecycle الحي، worker lease، VPE queue/clock، Pulse single owner، client-safe projection، session-local checkpoint policy | tenant membership policy source، global reporting truth، enterprise identity provider، AI judgment | VPE/Pulse في التنفيذ؛ session registry/metadata في OLTP؛ artifacts references في object store. |
| Event/async plane | reliable handoff من committed truth، routing، consumers idempotent | transaction ownership للـsimulation، synchronous business decision | transactional outbox ثم broker عند trigger. |
| Analytics plane | cohort/product/operational projections وrollups | student/session canonical state، safety decision، writeback truth | derived and rebuildable. |
| Object/Artifact plane | immutable bytes، content hash، version/retention/classification metadata | authorization by raw key وحده، relational joins/business status | object storage + OLTP reference. |
| AI future plane | optional async enrichment/search/debrief assistance بعد scope مستقل | clinical recommendation، session truth، required path لإنهاء session | derived output only. |

## stateless مقابل stateful

| نوع المكون | التصنيف | أسلوب التوسع المستهدف | شرط الأمان |
|---|---|---|---|
| catalog/assignment API future | stateless | scale-out خلف load balancer بعد transport/auth contract | كل request يحمل tenant/principal context موثقًا. |
| client facade endpoint future | stateless حول session routing | scale-out؛ لا يملك clock | يمرر أوامر منظّمة فقط ولا يسرّب internal truth. |
| session worker/VPE/Pulse | stateful per active session | one active lease/owner لكل session؛ workers متعددة عبر sessions لا داخل Pulse instance | no concurrent owner؛ fencing/heartbeat/recovery. |
| relay/consumer | stateless-ish مع delivery state | scale-out بالقفل/lease وidempotency | at-least-once وdedupe event ID. |
| analytics queries | derived/stateful store | isolate from OLTP | لا writeback truth. |
| object storage | stateful managed/provider | provider scaling لا يغير contract | hash/metadata/retention/reference authorization. |

## ملكية البيانات

| البيانات | owner | canonical location | publisher/consumer policy |
|---|---|---|---|
| tenant، org، membership، role | Control Plane | OLTP | لا tenant access من دون authorization؛ RLS candidate بعد contract. |
| scenario definition/catalog | Control Plane | versioned OLTP metadata + authored asset references | session pins immutable scenario version. |
| active simulation state | session worker/VPE | memory/Pulse/VPE runtime الحالي | لا consumer خارجي يكتبها. |
| client projection | facade/session worker | ephemeral request/response | minimal learner-safe DTOs فقط. |
| session lifecycle metadata | Control + worker contract | OLTP | transitions audited؛ worker lease fenced. |
| checkpoint/replay/export bytes | artifact plane | object storage future/local dev implementation | DB يخزن reference/hash/classification، لا blob. |
| platform event | committed owner | outbox ثم broker | immutable/versioned/minimized/idempotent. |
| telemetry/analytics | data plane derived | future analytics/lake | sampling/rollup/retention؛ لا يعيق simulation. |

## session lifecycle وfailure model

1. Control Plane يأذن ببدء session ويخصص `session_id` وscenario version وtenant context ضمن OLTP transaction.
2. worker allocator يطالب session lease مع `lease_generation` fencing token وheartbeat. لا يسمح token قديم بالكتابة بعد handoff.
3. worker واحد يبدأ VPE/Pulse محليًا ويملك clock وcommand queue؛ العميل لا يتصل بـPulse.
4. يبث worker فقط events مصرحًا بها وartifact references بعد policy، ولا ينتظر analytics/AI consumer.
5. عند crash أو heartbeat expiry، تصبح session `RECOVERY_REQUIRED` أو `PAUSED_BY_SYSTEM` حسب contract؛ لا يوجد handoff شفاف مزعوم حتى يثبت checkpoint/replay safety. يعاد claim فقط بعد fencing والتدقيق.
6. إكمال session يسجل summary metadata وحدثًا معتمدًا؛ لا تصبح derived projection شرطًا للـcompletion.

| الفشل | المجال المحتوي | الأثر المسموح | التعافي المستهدف |
|---|---|---|---|
| client disconnect | client/facade | لا يقتل worker تلقائيًا | reconnect/projection contract، policy لاحقًا. |
| worker process crash | session | session واحدة أو shard محدود | lease expiry + audit + controlled pause/recovery. |
| Pulse failure | session | لا يمتد إلى Control Plane | `PAUSED_BY_SYSTEM` والـevidence/report؛ لا auto-heal ادعائي. |
| OLTP unavailable | Control Plane | لا بدء/assignment mutation جديدة | live worker لا يكتب truth جديدًا بلا durable policy؛ fail safe. |
| relay/broker unavailable | async plane | derived data stale/backlog | outbox pending + retry؛ live simulation لا ينتظر. |
| analytics/AI outage | derived plane | dashboards/insights متأخرة | rebuild/retry؛ لا تغيير simulation. |
| object storage unavailable | artifact plane | artifact upload/export يتأجل أو session policy توقف مسار artifact فقط | local/session-safe fallback إن اعتمد؛ لا corruption. |

## حوكمة المستأجرين والأمن

كل resource tenant-owned يحمل `tenant_id` صريحًا، ويخضع كل command إلى principal authorization قبل routing. يكون `tenant_id` في event envelope لأغراض العزل والتدقيق لكنه ليس credential. تسجل mutation audit fields مثل actor/request/correlation/time، مع classification للـpayload/artifact. ولا يدخل PII أو secrets أو internal Pulse state في platform event payload.

تكون RLS طبقة دفاع إضافية ممكنة في PostgreSQL، لكن لا تفعّل قبل توثيق database role model وtenant context transaction-bound واختبارات negative cross-tenant؛ لأن أدوار owner أو `BYPASSRLS` قد تتجاوز RLS.[1]

## AWS mapping الإيضاحي المحايد للعقد

| capability | AWS mapping محتمل | قرار الدفعة |
|---|---|---|
| OLTP | RDS PostgreSQL / Aurora PostgreSQL | deferred؛ لا provision. |
| object artifacts | S3 | `ObjectStorage` contract فقط. |
| cache/lease | ElastiCache Redis/Valkey | deferred؛ ليس truth. |
| early async | SQS | deferred؛ outbox contract أولًا. |
| event backbone | MSK أو Kinesis | deferred إلى trigger. |
| workers/services | ECS/Fargate أولًا | deferred؛ EKS فقط بعد trigger تشغيلي. |
| edge/static assets | CloudFront | deferred. |
| secrets/telemetry | Secrets Manager، CloudWatch، OpenTelemetry | requirements future، لا integration. |

## عتبات فصل deployment أو service

| المعرّف | الدليل المطلوب | القرار المسموح |
|---|---|---|
| `PLAT-BOUNDARY-01` | module يملك lifecycle/failure domain/scale profile مختلفًا ويحتاج deployment cadence مستقلًا | فصل service أو worker deployment بعد contract وobservability. |
| `PLAT-WORKER-02` | عدد active sessions أو failure blast radius يتجاوز process-host المحدد بالقياس | allocator/worker pool مع lease/fencing spike. |
| `PLAT-REGION-03` | data residency/latency/resilience requirement مكتوب وممول مع RPO/RTO وwrite ownership | multi-region design ADR؛ لا active-active افتراضي. |
| `PLAT-K8S-04` | ECS/Fargate أو equivalent لا يلبي workload scheduling/networking/operations المقاسة | Kubernetes evaluation، لا adoption من البداية. |

## حدود الدفعة

لا تغير هذه الوثيقة `runtime.py` أو عقد السيناريو S0 أو Pulse integration أو Facade/transport المحلي. لا تعطي صلاحية Unity ولا تعدل أحكام Gate 0 أو medical review. إنها تثبت مسارًا معماريًا يتيح النمو التدريجي، وليس برهان صلاحية سريرية أو ضمان سعة إنتاجية.

## المراجع

[1]: ../research/postgres-scale-review.md "Nexora: مراجعة PostgreSQL القابلة للتوسع"
[2]: ../research/event-platform-comparison.md "Nexora: مقارنة منصة الأحداث"
[3]: ../research/analytics-store-comparison.md "Nexora: مقارنة مخازن التحليلات ومسار lakehouse"
[4]: ../research/nosql-when-and-why.md "Nexora: NoSQL وcache وvector/search"
