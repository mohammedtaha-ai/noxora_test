# مقارنة منصة الأحداث: outbox أولًا، backbone عند الدليل

**الحالة:** بحث وتصميم تعاقدي.  
**غير منفذ:** لا Kafka ولا Redpanda ولا MSK ولا Kinesis ولا SQS منشأ في هذه الدفعة.

## القرار

تعتمد Nexora **transactional outbox** بجانب الحقيقة العلائقية كمسار أول لإخراج أحداث المنصة. لا تكتب أي عملية business truth إلى قاعدة البيانات وbroker منفصلين بصورة dual-write. يبدأ relay بسيطًا قابلاً للاستبدال، وتحدد الحاجة لاحقًا بين queue managed مبكر أو event backbone طويل الاحتفاظ بواسطة عتبات قابلة للقياس. لا يملك event bus simulation clock أو Pulse أو session state.

> invariant: **فشل queue أو analytics أو AI consumer لا يوقف تقدم session worker الحي؛ يؤثر فقط في freshness/availability للمشتقات مع تسجيل lag وretry policy.**

## semantics التي يلتزم بها العقد

نمط outbox يكتب domain mutation والـevent في معاملة واحدة ثم ينشرهما relay منفصل؛ لا يلزم 2PC مع broker، لكنه يعترف بإمكان نشر relay للرسالة أكثر من مرة بعد crash، ولذلك يلزم idempotent consumer قائم على event ID.[1] ويبين Debezium أن بنية outbox الشائعة تحتاج event ID وaggregate type/id وevent type وpayload، وأن aggregate ID يمثل مفتاحًا صالحًا للحفاظ على ترتيب partition عند استخدام Kafka لاحقًا.[2]

| الضمان | ما يعد به التصميم | ما لا يعد به التصميم |
|---|---|---|
| commit | domain mutation وoutbox row ينجحان أو يتراجعان معًا في OLTP | لا `publish-to-bus` ضمن transaction موزعة. |
| delivery | relay يعيد المحاولة بعد failure؛ pending event لا يضيع بسبب فشل publisher | لا exactly-once end-to-end. |
| duplication | event ID ثابت ومستهلكون idempotent | لا افتراض أن `published_at` وحده يمنع duplicate. |
| ordering | ordering داخل aggregate/session key حيث يدعمه relay/broker | لا global total order بين جميع sessions أو tenants. |
| payload | immutable، versioned، مصنف، أدنى معلومة لازمة | لا PII أو Pulse internals أو clinical truth في platform event. |
| backpressure | غير حرج للـlive simulation؛ backlog يقاس ويخضع drop/rollup policy للـtelemetry | لا حظر worker في انتظار consumer بطيء. |

## مقارنة المسارات

| الخيار | مكانه الصحيح | مزايا ذات صلة | التكلفة/الحدود | trigger الدخول |
|---|---|---|---|---|
| OLTP outbox + polling relay | البداية | ذرية مع truth، minimal operations، قابل للترقية | ليس broadcast backbone طويلًا بنفسه؛ polling وإدارة retry | الحاجة لإخراج asynchronous projection واحدة أو أكثر مع business mutation. |
| Managed queue، مثل SQS في AWS mapping | asynchronous work مبكر | isolation بين producer وworker، retry/DLQ semantics بعد تصميمها | ليس بديلًا تلقائيًا لـreplay stream؛ يحتاج idempotency | heavy/slow work مثل export أو derived processor يحتاج decoupling قبل broker دائم. |
| Kafka / managed Kafka (MSK) | event backbone عند evidence | topics، partitions، retention، consumers مستقلة؛ ordering داخل partition-key.[3] | تشغيل/حوكمة schema/retention/consumers | replay متعدد consumers مستقلين، sustained telemetry/event traffic، أو ecosystem connectors مثبتة. |
| Redpanda | Kafka-compatible alternative قيد تقييم | Kafka clients 0.11+ متوافقة عمومًا مع استثناءات موثقة، وpartition-key ordering | implementation وcompatibility exceptions وoperations تخصه؛ لا يُفترض التطابق الكامل | benchmarking وoperational evaluation مع contract Kafka مطلوب فعليًا. |
| Kinesis Data Streams | AWS-native managed stream | service managed، partition keys، ordering في shard؛ throttling/retry capacity model موثق.[5] | AWS coupling وlimits/retention/consumer model | AWS-native event/analytics stream مع consumer/retention يحتاجان توافقًا أدق مع النموذج. |

تصف وثائق Kafka events كـkey/value/timestamp/headers، وتوضح أن events ذات المفتاح نفسه تكتب في partition واحد وأن المستهلك يقرأ ذلك partition بالترتيب نفسه.[3] وهذا يبرر وضع `session_id` أو aggregate key صريحًا في envelope حتى قبل ظهور Kafka. توثق Redpanda أن Kafka clients الحديثة تعمل عادةً معها، لكنها تسجل استثناءات محددة في SCRAM وHTTP proxy وquotas وtransaction protocol؛ لذا يظل التوافق موضوع اختبار contract لا افتراضًا.[4] وتوضح AWS أن Kinesis يطبق partition key وordering داخل shard، وأن تجاوز سعة stream يولد throttling ويتطلب retry؛ لذا لا يعالج عدم وجود backpressure في المنتج وإنما يجعله أكثر ضرورة.[5]

## عقد التسمية والتوجيه

أسماء events تكون dot-separated وversioned في `schema_version`، ولا تخلق topic لكل tenant. الأمثلة المخططة تشمل `simulation.session.started`، `simulation.intent.recorded`، `simulation.hypothesis.recorded`، `simulation.observation.recorded`، `simulation.intervention.recorded`، `simulation.snapshot.available`، `simulation.session.completed`، ثم مستقبلًا `assessment.evidence.recorded` و`debrief.generated` بعد ownership/review مستقلين.

| الحقل | الهدف | قاعدة الخصوصية/التشغيل |
|---|---|---|
| `event_id` | idempotency/dedup | UUIDv7-style؛ immutable. |
| `event_type` و`schema_version` | evolution/compatibility | breaking change = version جديد، لا تفسير صامت. |
| `occurred_at` | chronology | لا يعادل simulation time ما لم يعرّف الحقل ذلك صراحة. |
| `tenant_id` | isolation/routing/audit | required للـtenant-owned event؛ ليس principal credential. |
| `aggregate_type`, `aggregate_id`, `routing_key` | order/partition future | `session_id` للـsimulation event غالبًا. |
| `classification` | policy | `PUBLIC/INTERNAL/RESTRICTED` كحد أدنى في العقد؛ لا PII في payload. |
| `payload` | semantic data محدودة | JSON-compatible immutable؛ لا Pulse state، لا secrets، لا medical claim. |
| `trace_id`, `causation_id`, `correlation_id` | observability | optional، لا تحمل data business حساسة. |

## failure domains وbackpressure

| المجال | failure المتوقع | سلوك المنتج |
|---|---|---|
| OLTP transaction | failure قبل commit | لا domain mutation ولا outbox event. |
| relay | publish failure أو timeout | يبقى event pending أو يعاد claimه بعد lease؛ لا يوقف simulation. |
| broker/queue | throttle/outage | backlog وalarm وexponential backoff؛ priority للأحداث critical، sampling/rollup للـtelemetry المسموح. |
| consumer analytics | lag/schema failure | consumer يعيد المحاولة/DLQ وفق policy؛ projection قابلة لإعادة البناء. |
| consumer AI | timeout/model failure | AI نتيجة async advisory فقط؛ لا تملك truth أو safety decision. |
| live session worker | crash | recovery من session registry/checkpoint policy، لا انتظار event consumers. |

## عتبات قرار مسماة

| المعرّف | دليل الدخول | التغيير المسموح |
|---|---|---|
| `EVT-QUEUE-01` | outbox relay يشغل work بطيئًا أو يحتاج retry/DLQ مستقلين | اختيار queue managed مع consumer idempotency. |
| `EVT-BUS-02` | ≥2 consumers مستقلين يحتاجون replay وretention موثقين، أو polling relay لا يحقق SLO backlog | evaluation Kafka/MSK/Redpanda/Kinesis عبر spike قابل للقياس. |
| `EVT-PART-03` | hot routing key أو skew يثبت بالحجم/lag | اختيار/تغيير partition key أو تقسيم stream؛ لا tenant-topic proliferation. |
| `EVT-SCHEMA-04` | consumer جديد يحتاج توافقًا رسميًا أو breaking payload change | schema governance/registry evaluation. |
| `EVT-TELEM-05` | telemetry raw يهدد OLTP أو outbox latency | فصل telemetry ingest/rollups أو stream/lake path، مع عدم إعاقة simulation. |

## AWS mapping الإيضاحي

في بيئة AWS فقط، يمكن أن يربط OLTP outbox بـRDS/Aurora لاحقًا، وqueue مبكر بـSQS، وevent backbone بـMSK أو Kinesis عند trigger، وmetrics بـCloudWatch/OTel. هذا **ليس deployment plan ولا commitment cloud**؛ العقد لا يعتمد على SDK أو خدمة بعينها.

## المراجع

[1]: https://microservices.io/patterns/data/transactional-outbox.html "Transactional outbox pattern"
[2]: https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html "Debezium Outbox Event Router"
[3]: https://kafka.apache.org/documentation/ "Apache Kafka Documentation"
[4]: https://docs.redpanda.com/streaming/current/develop/kafka-clients/ "Redpanda: Kafka Compatibility"
[5]: https://aws.amazon.com/kinesis/data-streams/faqs/ "Amazon Kinesis Data Streams FAQ"
[6]: https://docs.aws.amazon.com/whitepapers/latest/build-modern-data-streaming-analytics-architectures/key-considerations-while-building-streaming-analytics.html "AWS streaming analytics considerations (historical reference)"
