# عقد سيناريو S0 — v1

## الغرض

يعرّف هذا العقد الحد الأدنى الذي يستطيع مؤلف سيناريو غير مبرمج فهمه ومراجعته. لا يعرّف بروتوكولًا علاجيًا ولا يتيح أوامر Pulse خامة من العميل.

## نموذج السيناريو

```yaml
schema_version: "1.0"
id: "trauma_splenic_01"
title: "Abdominal trauma: active splenic hemorrhage"
mode: "learning"
patient:
  template: "adult_male_standard"
pathology:
  existing_internal_hemorrhage:
    compartment: "spleen"
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
    - "SUSPECT_INTERNAL_BLEEDING"
observations:
  fast:
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
telemetry:
  - "heart_rate_bpm"
  - "mean_arterial_pressure_mmhg"
  - "blood_volume_ml"
  - "total_hemorrhaged_volume_ml"
completion:
  success_rules: []
  failure_rules: []
```

## قواعد التحقق

| القاعدة | سببها |
|---|---|
| `schema_version` يجب أن يساوي النسخة المعروفة للنواة. | منع تفسير ملف مجهول. |
| `mode` في S0 يساوي `learning`. | يمنع تسرب وضع تقييم عال العواقب. |
| النزف جزء من `pathology` عند البدء لا من أمر المتعلم. | الإصابة موجودة قبل البداية. |
| التدخلات تشير إلى قاموس محدود. | يمنع إرسال نصوص أو أوامر Pulse خامة. |
| قائمة telemetry عبارة عن مفاتيح داخلية مسموحة. | تفصل واجهة S0 عن أسماء أعمدة Pulse. |
| لا توجد قواعد نجاح/فشل في S0. | يبقى التقييم تكوينيًا. |

## عقد الحدث

يلزم أن يطابق كل حدث مخطط `schemas/event-envelope.schema.json` وأن يحتوي على: `event_id`، `scenario_id`، `simulation_time_s`، `event_type`، `actor`، `payload`، `source`، و`schema_version`. يرفض runtime الأنواع غير المعروفة أو الأفعال غير المبررة بعقد السيناريو.

## عقد adapter

يقبل adapter الداخلي أربعة آثار محكومة: تطبيق تدخل من قاموس، تقدم زمن، حفظ snapshot، واستعادة snapshot. تدير VPE ساعة المحاكاة وترتيب الأوامر؛ لا تملك Unity أو طبقة اللغة Pulse مباشرة.
