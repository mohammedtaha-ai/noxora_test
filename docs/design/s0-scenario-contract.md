# عقد سيناريو S0 — v1.2

## الغرض

يعرّف هذا العقد الحد الأدنى الذي يستطيع مؤلف سيناريو غير مبرمج فهمه ومراجعته. لا يعرّف بروتوكولًا علاجيًا، ولا يتيح أوامر Pulse خامة من العميل، ولا ينشئ نتيجة نجاح أو فشل للمتعلم.

> ملف السيناريو authoritative: إمّا أن يحفظه نموذج `S0Scenario` ويتحقق منه loader، أو يرفضه loader. لا توجد حقول زخرفية أو صامتة في عقد v1.2.

## نموذج السيناريو

```yaml
schema_version: "1.2"
id: "trauma_splenic_01"
title: "Abdominal trauma: active splenic hemorrhage"
mode: "learning"
pulse_revision: "<pinned revision>"
patient:
  template: "adult_male_standard"
pathology:
  existing_internal_hemorrhage:
    compartment: "Spleen"
    flow_rate_ml_min: 60
learning_objectives:
  - "identify_deterioration"
  - "suspect_internal_bleeding"
  - "request_fast"
  - "begin_resuscitation"
  - "reassess"
history:
  allowed_intents:
    - "PAIN_ONSET"
    - "PAIN_LOCATION"
    - "MECHANISM_OF_INJURY"
clinical_hypotheses:
  allowed:
    - "INTERNAL_BLEEDING"
observations:
  allowed:
    - id: "FAST"
      enabled: true
      controlled_finding: "free_fluid_positive"
interventions:
  allowed:
    - id: "crystalloid_saline"
      pulse_compound: "Saline"
      volume_ml: 500
      rate_ml_min: 100
    - id: "blood_packed_rbc"
      pulse_compound: "PackedRBC"
      volume_ml: 250
      rate_ml_min: 5
escalations:
  allowed:
    - id: "trauma_team_escalation"
telemetry:
  - "heart_rate_bpm"
  - "mean_arterial_pressure_mmhg"
  - "blood_volume_ml"
  - "total_hemorrhaged_volume_ml"
  - "oxygen_saturation"
completion:
  success_rules: []
  failure_rules: []
```

المخطط المنشور هو [`schemas/s0-scenario.schema.json`](../../schemas/s0-scenario.schema.json). يفرض loader تساوي مفاتيح المستوى الأعلى، ويرفض المفاتيح الزائدة أو الناقصة أو معرفات القوائم المتكررة قبل بناء نموذج المجال.

## قواعد التحقق

| القاعدة | سببها |
|---|---|
| `schema_version` يساوي `1.2`. | منع تفسير ملف قديم أو غير معروف. |
| `mode` يساوي `learning`. | يمنع تسرب وضع تقييم عالي العواقب. |
| النزف جزء من `pathology` عند البدء. | الإصابة موجودة قبل البداية، وليست أمر متعلم. |
| `learning_objectives` تحفظ كنصوص مؤلفة غير فارغة. | يمنع فقد الهدف التعليمي من الملف المصدر. |
| `history.allowed_intents` يقتصر على أسئلة/محاولات استجلاء معلومة من المريض. | يفصل جمع التاريخ عن الاستدلال. |
| `clinical_hypotheses.allowed` يصرح بفرضيات منظمة فقط. | يسجل استدلال المتعلم دون نص حر أو ادعاء تشخيص واقعي. |
| `VITALS` قدرة monitor مدمجة؛ `FAST` و`CBC` لا يظهران إلا عند تأليفهما في `observations.allowed`. | مصدر حقيقة واحد لقائمة الملاحظات. |
| تدخلات Pulse تشير إلى قاموس محدود. | يمنع نصوص أو أوامر Pulse خامة. |
| `escalations.allowed` قاموس ثابت غير فارغ. | يمنع نصوص التصعيد الحرة ويحفظ دليلًا قابلًا للمراجعة. |
| قواعد `completion` فارغة في S0. | تبقي النتيجة تكوينية ولا تصنع نجاحًا/فشلًا عالي العواقب. |

## عقد الحدث

يلزم أن يطابق كل حدث [`schemas/event-envelope.schema.json`](../../schemas/event-envelope.schema.json). تشمل الأحداث المنظمة: `clinical.intent.recorded` و`clinical.hypothesis.recorded` و`observation.requested` و`escalation.recorded`، إضافة إلى أحداث الزمن والتدخل واللقطات والـcheckpoint. لا يغير history أو hypothesis أو observation أو escalation محرك Pulse أو زمن المحاكاة في S0.

## Snapshot وcheckpoint

`Snapshot` حدث عرض/مراجعة خفيف يحوي الهوية والزمن وإصدار المحرك وtelemetry وسبب النشر؛ لا يحمل state قابلًا للاستعادة. `CREATE_CHECKPOINT` فقط ينشئ artifact محرك منفصل. وتبقى استعادة checkpoint داخل الجلسة مثبتة، أما الاستعادة عبر إعادة تشغيل Runtime فغير مثبتة في S0. التفاصيل في [عقد PulseAdapter](../contracts/pulse-adapter-process-contract.md).
