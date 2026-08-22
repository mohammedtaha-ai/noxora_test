# Platform Event Envelope v0.1

**الحالة:** عقد جديد مستقل للمنصة.  
**غير بديل:** لا يستبدل `schemas/event-envelope.schema.json` الخاص بـS0، ولا ينشر Kafka أو broker في هذه الدفعة.

## الهدف

يوحد هذا العقد الحد الأدنى للأحداث التي تنتجها حدود المنصة بعد commit موثوق، بحيث يمكن لـoutbox local الآن وqueue/bus لاحقًا حملها بلا تغيير semantic. لا يعيد تعريف internal runtime events أو Pulse data. كل event immutable، versioned، ومصنف، وله ID يصلح للـidempotency.

## envelope

| الحقل | النوع | مطلوب | الدلالة |
|---|---|---:|---|
| `event_id` | UUIDv7-style string | نعم | ID ثابت للـdedupe؛ لا يعاد استخدامه. |
| `event_type` | dot-separated string | نعم | مثل `simulation.session.started`. |
| `schema_version` | positive integer | نعم | version للـpayload + envelope contract. |
| `occurred_at` | UTC ISO-8601 string | نعم | wall-clock وقت الحدث؛ ليس simulation time. |
| `producer` | constrained string | نعم | boundary المنطقي المنتج، مثل `simulation.data-plane`. |
| `tenant_id` | ID string | نعم للأحداث tenant-owned | ownership/audit/routing وليس credential. |
| `aggregate_type` | string | نعم | مثل `simulation_session`. |
| `aggregate_id` | ID string | نعم | session/assignment/entity owner. |
| `routing_key` | string | نعم | key لordering/partition future؛ session ID غالبًا. |
| `classification` | enum | نعم | `PUBLIC`/`INTERNAL`/`RESTRICTED`. |
| `payload` | JSON object | نعم | minimal semantic data بلا PII أو secrets. |
| `correlation_id` | ID string | لا | سياق عملية/flow. |
| `causation_id` | ID string | لا | event/command سبب الحدث. |
| `trace_id` | string | لا | observability فقط. |

```json
{
  "event_id": "018f3c5b-89a0-7d18-9cb8-c1f68fbb4ef8",
  "event_type": "simulation.session.started",
  "schema_version": 1,
  "occurred_at": "2026-08-23T12:00:00.000Z",
  "producer": "simulation.data-plane",
  "tenant_id": "018f3c58-726e-7fa3-8491-58204a8a0e2c",
  "aggregate_type": "simulation_session",
  "aggregate_id": "018f3c5a-0e7b-7e9d-af27-11040f2dd0ae",
  "routing_key": "018f3c5a-0e7b-7e9d-af27-11040f2dd0ae",
  "classification": "INTERNAL",
  "payload": {
    "scenario_version_id": "018f3c59-0f10-73fc-b3a9-a86d1a649a0f"
  }
}
```

القيم مثال تركيبي للـshape فقط ولا تمثل بيانات تشغيل أو throughput أو حالة مريض.

## أسماء events المسجلة

| event type | producer owner | payload المسموح | لا يحمل |
|---|---|---|---|
| `simulation.session.started` | Simulation Data Plane | scenario version ID، policy-safe session metadata | Pulse state/learner PII. |
| `simulation.intent.recorded` | Simulation Data Plane | allowed intent code/reference | raw free text حساس افتراضيًا. |
| `simulation.hypothesis.recorded` | Simulation Data Plane | normalized learning-hypothesis reference إذا اعتمد | hidden diagnosis/truth. |
| `simulation.observation.recorded` | Simulation Data Plane | observation reference/client-safe code | full internal physiology state. |
| `simulation.intervention.recorded` | Simulation Data Plane | action code/outcome classification | unrestricted clinical decision claim. |
| `simulation.snapshot.available` | Simulation Data Plane | artifact reference/metadata فقط | snapshot bytes في payload. |
| `simulation.session.completed` | Simulation Data Plane | completion status/summary reference | analytics/AI result كشرط completion. |
| `assessment.evidence.recorded` | future assessment owner | evidence reference عند اعتماد scope | conclusion أو score غير معتمد. |
| `debrief.generated` | future debrief owner | derived artifact reference/model provenance | authoritative assessment or medical truth. |

## versioning rules

1. لا يتغير معنى field قائم في version موجود. الإضافة optional متوافقة؛ الإزالة أو تغيير type/meaning يستلزم version جديدًا.
2. `event_type` يمثل semantic event، و`schema_version` يمثل تطور شكله. لا تستعمل topic name لإخفاء version.
3. producer يكتب نسخة واحدة صالحة لكل event ID. لا تحدث outbox record لتعديل payload بعد commit.
4. consumer يصرح بالـversions المقبولة، ويعزل unknown version/quarantine بدلاً من إسقاطه بصمت.
5. serialization الحالي JSON-compatible؛ قرار Avro/schema registry مؤجل حتى `EVT-SCHEMA-04`.[1]

## delivery وordering

تكون delivery **at-least-once**. يتعين على كل consumer حفظ أو التحقق من `event_id` قبل الأثر غير القابل للتكرار. يحافظ broker مستقبلي، إن استخدم، على الترتيب في حدود `routing_key`/partition لا على ترتيب عالمي. لذلك تستخدم أحداث session نفس `routing_key=session_id`، وتبقى cross-session consumers designed for reordering.

نمط outbox يزيل dual-write بين database وbroker عبر commit واحد للـdomain/outbox، لكنه لا يمنع تكرار relay بعد crash؛ وهذا سبب أن idempotency requirement جزء من العقد لا implementation detail.[2]

## privacy وsecurity

| قاعدة | سبب |
|---|---|
| لا PII، secrets، tokens، أو raw internal Pulse state في `payload`. | events قد تصل إلى analytics/queue/logs متعددة. |
| tenant ID وclassification مطلوبان قبل export/relay. | routing/audit لا يساويان permission. |
| artifact bytes لا تدخل payload؛ يوضع object reference مصرح به. | volume/retention/access policy خارج broker envelope. |
| AI events مشتقة وasync فقط. | لا LLM-owned truth ولا gating لـlive simulation. |
| لا topic per tenant. | يمنع explosion تشغيلي؛ tenant filtering/auth تبقى في consumers/stores. |

## outbox-to-bus path

```text
owner transaction
   ├─ canonical mutation
   └─ immutable platform event row
             │ commit together
             ▼
     outbox claim + publisher
             │ at-least-once
             ├─ local in-memory/SQLite spike now
             ├─ managed queue later
             └─ Kafka/Redpanda/MSK/Kinesis only at trigger
```

## separation from S0 envelope

`schemas/event-envelope.schema.json` يبقى contract S0. لا تمرر Platform Event Envelope إلى `VpeRuntime` ولا تفرض حقول tenant/producer على Pulse or scenario events. أي adapter مستقبلي يختار فقط event data المصنف والمصرح به عند boundary؛ لا ينسخ event الداخلي بشكل انعكاسي.

## المراجع

[1]: ../research/event-platform-comparison.md "Nexora: مقارنة منصة الأحداث"
[2]: https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html "Debezium Outbox Event Router"
[3]: https://datatracker.ietf.org/doc/rfc9562/ "RFC 9562: UUIDs"
