# Traceability لعقد أحداث S0 v1.1

**الحالة:** `COMPLETE FOR M6 CONTRACT FREEZE`.
**النطاق:** S0 Learning Mode وcanonical replay فقط؛ لا Unity أو AI أو transport أو تقييم عالي العواقب.

> كل صف أدناه يبين لماذا يبقى field في العقد. `UNMEASURABLE` ليس عدمًا صامتًا: evaluator يخرجه صراحة عندما لا يملك stream الإشارة المطلوبة. لا يخرج evaluator score أو pass/fail أو ترتيب متعلم.[1]

## مبدأ الربط

| الرمز | المعنى |
|---|---|
| `LO-01` | التعرف على التدهور واشتباك فرضية النزف الداخلي. |
| `LO-02` | بناء تاريخ موجّه محدود. |
| `LO-03` | طلب FAST؛ اكتساب FAST الفعلي خارج S0 حتى M4. |
| `LO-04` | فهم أثر زمن المحاكاة. |
| `LO-05` | تطبيق إنعاش من قاموس مقيد. |
| `LO-06` | مراجعة timeline والأدلة واللقطات بلا اختراع أحداث. |
| `CONTRACT` | field تشغيلي لازم للـvalidation/provenance/migration أو replay integrity، وليس دليل أداء للمتعلم. |

## Envelope traceability — صف صريح لكل event type/field

الجدول التالي هو cross-product الصريح للحقول المشتركة على الأنواع العشرة في v1.1. لكل صف مستهلك أو سبب احتفاظ قابل للمراجعة؛ لا يعتمد freeze على اختزال «كل الأنواع» ضمنيًا.

| event type | field | المستهلك أو التبرير الصريح | هدف التعلم |
|---|---|---|---|
| `clock.advanced` | `event_id` | evaluator finding link وtimeline cursor. | LO-06 |
| `clock.advanced` | `scenario_id` | replay stream binding. | LO-06 / CONTRACT |
| `clock.advanced` | `simulation_time_s` | timeline axis للـclock increment. | LO-04, LO-06 |
| `clock.advanced` | `event_type` | parser/evaluator dispatch. | LO-06 / CONTRACT |
| `clock.advanced` | `actor` | authority provenance. | CONTRACT |
| `clock.advanced` | `source` | producer provenance. | CONTRACT |
| `clock.advanced` | `schema_version` | validator/migration boundary. | CONTRACT |
| `clinical.intent.recorded` | `event_id` | evaluator finding link وtimeline cursor. | LO-06 |
| `clinical.intent.recorded` | `scenario_id` | replay stream binding. | LO-06 / CONTRACT |
| `clinical.intent.recorded` | `simulation_time_s` | timeline axis للـintent. | LO-04, LO-06 |
| `clinical.intent.recorded` | `event_type` | parser/evaluator dispatch. | LO-06 / CONTRACT |
| `clinical.intent.recorded` | `actor` | authority provenance. | CONTRACT |
| `clinical.intent.recorded` | `source` | producer provenance. | CONTRACT |
| `clinical.intent.recorded` | `schema_version` | validator/migration boundary. | CONTRACT |
| `clinical.hypothesis.recorded` | `event_id` | evaluator finding link وtimeline cursor. | LO-06 |
| `clinical.hypothesis.recorded` | `scenario_id` | replay stream binding. | LO-06 / CONTRACT |
| `clinical.hypothesis.recorded` | `simulation_time_s` | timeline axis للـhypothesis. | LO-04, LO-06 |
| `clinical.hypothesis.recorded` | `event_type` | parser/evaluator dispatch. | LO-06 / CONTRACT |
| `clinical.hypothesis.recorded` | `actor` | authority provenance. | CONTRACT |
| `clinical.hypothesis.recorded` | `source` | producer provenance. | CONTRACT |
| `clinical.hypothesis.recorded` | `schema_version` | validator/migration boundary. | CONTRACT |
| `observation.requested` | `event_id` | evaluator finding link وtimeline cursor. | LO-06 |
| `observation.requested` | `scenario_id` | replay stream binding. | LO-06 / CONTRACT |
| `observation.requested` | `simulation_time_s` | timeline axis للـobservation. | LO-04, LO-06 |
| `observation.requested` | `event_type` | parser/evaluator dispatch. | LO-06 / CONTRACT |
| `observation.requested` | `actor` | authority provenance. | CONTRACT |
| `observation.requested` | `source` | producer provenance. | CONTRACT |
| `observation.requested` | `schema_version` | validator/migration boundary. | CONTRACT |
| `intervention.applied` | `event_id` | evaluator finding link وtimeline cursor. | LO-06 |
| `intervention.applied` | `scenario_id` | replay stream binding. | LO-06 / CONTRACT |
| `intervention.applied` | `simulation_time_s` | timeline axis للـintervention. | LO-04, LO-06 |
| `intervention.applied` | `event_type` | parser/evaluator dispatch. | LO-06 / CONTRACT |
| `intervention.applied` | `actor` | authority provenance. | CONTRACT |
| `intervention.applied` | `source` | producer provenance. | CONTRACT |
| `intervention.applied` | `schema_version` | validator/migration boundary. | CONTRACT |
| `snapshot.published` | `event_id` | evaluator finding link وtimeline cursor. | LO-06 |
| `snapshot.published` | `scenario_id` | replay stream binding. | LO-06 / CONTRACT |
| `snapshot.published` | `simulation_time_s` | timeline axis للـsnapshot. | LO-04, LO-06 |
| `snapshot.published` | `event_type` | parser/evaluator dispatch. | LO-06 / CONTRACT |
| `snapshot.published` | `actor` | authority provenance. | CONTRACT |
| `snapshot.published` | `source` | producer provenance. | CONTRACT |
| `snapshot.published` | `schema_version` | validator/migration boundary. | CONTRACT |
| `checkpoint.created` | `event_id` | evaluator finding link وtimeline cursor. | LO-06 |
| `checkpoint.created` | `scenario_id` | replay stream binding. | LO-06 / CONTRACT |
| `checkpoint.created` | `simulation_time_s` | timeline axis للـcheckpoint. | LO-04, LO-06 |
| `checkpoint.created` | `event_type` | parser/evaluator dispatch. | LO-06 / CONTRACT |
| `checkpoint.created` | `actor` | authority provenance. | CONTRACT |
| `checkpoint.created` | `source` | producer provenance. | CONTRACT |
| `checkpoint.created` | `schema_version` | validator/migration boundary. | CONTRACT |
| `checkpoint.restored` | `event_id` | evaluator finding link وtimeline cursor. | LO-06 |
| `checkpoint.restored` | `scenario_id` | replay stream binding. | LO-06 / CONTRACT |
| `checkpoint.restored` | `simulation_time_s` | timeline axis عند branch boundary. | LO-04, LO-06 |
| `checkpoint.restored` | `event_type` | parser/evaluator dispatch. | LO-06 / CONTRACT |
| `checkpoint.restored` | `actor` | authority provenance. | CONTRACT |
| `checkpoint.restored` | `source` | producer provenance. | CONTRACT |
| `checkpoint.restored` | `schema_version` | validator/migration boundary. | CONTRACT |
| `escalation.recorded` | `event_id` | evaluator finding link وtimeline cursor. | LO-06 |
| `escalation.recorded` | `scenario_id` | replay stream binding. | LO-06 / CONTRACT |
| `escalation.recorded` | `simulation_time_s` | timeline axis للـescalation. | LO-04, LO-06 |
| `escalation.recorded` | `event_type` | parser/evaluator dispatch. | LO-06 / CONTRACT |
| `escalation.recorded` | `actor` | authority provenance. | CONTRACT |
| `escalation.recorded` | `source` | producer provenance. | CONTRACT |
| `escalation.recorded` | `schema_version` | validator/migration boundary. | CONTRACT |
| `runtime.paused_by_system` | `event_id` | evaluator marker link وtimeline cursor. | LO-06 |
| `runtime.paused_by_system` | `scenario_id` | replay stream binding. | LO-06 / CONTRACT |
| `runtime.paused_by_system` | `simulation_time_s` | يثبت تجميد الزمن عند safety boundary. | LO-04, LO-06 |
| `runtime.paused_by_system` | `event_type` | parser/evaluator dispatch. | LO-06 / CONTRACT |
| `runtime.paused_by_system` | `actor` | authority provenance: system فقط. | CONTRACT |
| `runtime.paused_by_system` | `source` | producer provenance: `vpe_core`. | CONTRACT |
| `runtime.paused_by_system` | `schema_version` | validator/migration boundary. | CONTRACT |

## Payload traceability — صف لكل event field

| event type | field | evaluator/replay consumer أو تبرير الاحتفاظ | هدف التعلم |
|---|---|---|---|
| `clock.advanced` | `payload.command_id` | CONTRACT: يربط الدليل بأمر VPE مقبول ويحافظ على trace/debug/reproducibility؛ لا score. | CONTRACT |
| `clock.advanced` | `payload.duration_s` | timeline/reproducibility يستهلكانه لشرح increment المحاكى؛ لا wall-clock. | LO-04, LO-06 |
| `clinical.intent.recorded` | `payload.command_id` | CONTRACT: correlates accepted structured intent. | CONTRACT |
| `clinical.intent.recorded` | `payload.intent_id` | evaluator يحفظ evidence تاريخ موجّه؛ يغطي intents الثلاثة المسموح بها. | LO-02 |
| `clinical.hypothesis.recorded` | `payload.command_id` | CONTRACT: correlates accepted structured hypothesis. | CONTRACT |
| `clinical.hypothesis.recorded` | `payload.hypothesis_id` | evaluator يستهلك `INTERNAL_BLEEDING` لبعد اشتباه النزف الداخلي. | LO-01 |
| `observation.requested` | `payload.command_id` | CONTRACT: correlates observation request. | CONTRACT |
| `observation.requested` | `payload.observation_id` | evaluator يستهلك `VITALS` لملاحظة التدهور/إعادة التقييم و`FAST` لطلب الدليل. | LO-01, LO-03, LO-06 |
| `intervention.applied` | `payload.command_id` | CONTRACT: links accepted intervention to submitted command and replay trace. | CONTRACT |
| `intervention.applied` | `payload.intervention_id` | evaluator يستهلكه كدليل إنعاش مقيد. | LO-05 |
| `intervention.applied` | `payload.compound` | CONTRACT: execution manifest لما وصل إلى adapter؛ يلزم audit/reproducibility ولا يحول إلى توصية. | CONTRACT |
| `intervention.applied` | `payload.volume_ml` | CONTRACT: payload تنفيذي مقيد يثبت ما طبق؛ لا evaluator ولا جرعة علاجية. | CONTRACT |
| `intervention.applied` | `payload.rate_ml_min` | CONTRACT: payload تنفيذي مقيد يثبت ما طبق؛ لا evaluator ولا جرعة علاجية. | CONTRACT |
| `snapshot.published` | `payload.snapshot_id` | replay reader يربطه باللقطة المسجلة ويرفض المرجع المفقود. | LO-06 / CONTRACT |
| `snapshot.published` | `payload.reason` | timeline يستهلك سبب النشر لتمييز بداية/وقت/intervention/checkpoint؛ لا narration. | LO-04, LO-06 |
| `checkpoint.created` | `payload.command_id` | CONTRACT: trace للـprimitive الهندسي in-session فقط. | CONTRACT |
| `checkpoint.created` | `payload.checkpoint_id` | replay/timeline يربطان boundary/diagnostic artifact؛ لا product branch replay. | LO-06 / CONTRACT |
| `checkpoint.restored` | `payload.command_id` | CONTRACT: trace للـrestore المقبول داخل Runtime. | CONTRACT |
| `checkpoint.restored` | `payload.checkpoint_id` | timeline يحدد branch boundary؛ ADR-019 يمنع تفسيره كميزة restart/learner branch. | LO-06 / CONTRACT |
| `escalation.recorded` | `payload.command_id` | CONTRACT: correlates structured escalation. | CONTRACT |
| `escalation.recorded` | `payload.escalation_id` | evaluator يثبت وجود نية escalation؛ لا حكم قبول/رفض أو outcome. | LO-06 |
| `runtime.paused_by_system` | `payload.reason` | evaluator يستهلك event كـsession marker `PAUSED_BY_SYSTEM`؛ reason سجل safety context لا finding للمتعلم. | LO-06 / CONTRACT |

## Snapshot traceability

| snapshot field | consumer أو تبرير الاحتفاظ | هدف التعلم |
|---|---|---|
| `snapshot_id` | `snapshot.published` references it; replay verifies linkage. | LO-06 / CONTRACT |
| `scenario_id` | replay stream binding. | LO-06 / CONTRACT |
| `simulation_time_s` | timeline axis وموضع telemetry في المسار. | LO-04, LO-06 |
| `engine_version` | reproducibility/provenance؛ يمنع مقارنة trajectory من engine مجهول. | CONTRACT |
| `telemetry.heart_rate_bpm` | timeline/debrief visual evidence فقط؛ لا threshold أو grade. | LO-01, LO-04, LO-06 |
| `telemetry.mean_arterial_pressure_mmhg` | timeline/debrief visual evidence فقط؛ لا threshold أو grade. | LO-01, LO-04, LO-06 |
| `telemetry.blood_volume_ml` | canonical trajectory/reproducibility evidence؛ ليس client-visible. | LO-04, LO-06 |
| `telemetry.total_hemorrhaged_volume_ml` | canonical trajectory/reproducibility evidence؛ ليس recommendation. | LO-01, LO-04, LO-06 |
| `telemetry.oxygen_saturation` | يبقى في internal reproducibility stream فقط؛ لا projection/client evidence حتى مراجعة مستقلة وفق ADR-016. | CONTRACT |
| `reason` | timeline يميز سبب النشر بلا narration. | LO-06 / CONTRACT |

## pass 1: fields غير المستهلكة

لم يبق field بلا evaluator أو replay consumer أو تبرير `CONTRACT` محدد. أزيل من enum/schema v1.1 الحدث غير المنتج `fast.acquisition.recorded` بدل إبقائه كـplaceholder؛ acquisition الفعلي لا يملك producer في S0 ولا يجوز لعقد العميل أن يعد به قبل M4.

## pass 2: rubric dimensions غير القابلة للقياس

| بُعد rubric | قرار M6 |
|---|---|
| ملاحظة التدهور | قابل للقياس فقط عندما يوجد `VITALS` ولقطتان منشورتان على الأقل؛ وإلا `UNMEASURABLE`. |
| اشتباه النزف الداخلي | قابل للقياس فقط عندما يوجد `clinical.hypothesis.recorded:INTERNAL_BLEEDING`؛ وإلا `UNMEASURABLE`. |
| طلب FAST | قابل للقياس عندما يوجد `observation.requested:FAST`؛ وإلا `UNMEASURABLE`. |
| اكتساب FAST صالح | **OUT OF S0 SCOPE** حتى M4؛ يبقى `UNMEASURABLE` بمفتاح signal صريح، ولا يضاف event بلا producer. |
| الإنعاش | قابل للقياس عند `intervention.applied`؛ لا يقيّم الجودة السريرية. |
| إعادة التقييم | قابل للقياس عند observation مسجل بعد intervention؛ وإلا `UNMEASURABLE`. |
| التصعيد | قابل للقياس عند `escalation.recorded`؛ لا يثبت ملاءمة واقعية. |

## قرار نوايا التاريخ الثلاثة

لا تتوسع قائمة S0 الآن. يقتصر `LO-02` الحالي على **تاريخ موجّه أساسي** تتوافر له ثلاث إشارات evidence: `MECHANISM_OF_INJURY`، `PAIN_ONSET`، و`PAIN_LOCATION`. لا يحتاج `LO-01` أو `LO-03` أو `LO-04` أو `LO-05` نية تاريخ إضافية كشرط evidence؛ و`LO-06` يقرأ ما سجل فقط. لذلك تكون intents الأخرى (`PAIN_RADIATION`، `PAIN_SEVERITY`، `ASSOCIATED_SYMPTOMS`، `MEDICATIONS`، `ALLERGIES`، `PAST_MEDICAL_HISTORY`، `ANTICOAGULANT_USE`) خارج S0 الحالي، لا ناقصة بصمت. فتح أي منها يتطلب هدفًا/دليلًا جديدين ومراجعة محتوى، لا مجرد توسيع قاموس.[2]

## References

[1] [مسودة rubric S0](s0-draft-rubric.md)، [جرد الأدلة](s0-evidence-inventory.md)، و[implementation evaluator](../../src/nexora_vpe/evidence_evaluator.py).
[2] [أهداف تعلم S0](s0-learning-objectives.md) و[scenario contract](s0-scenario-contract.md).
[3] [ADR-016: حد الأكسجة/النزف](../decisions/ADR-016-s0-hemorrhage-control-and-oxygen-display-boundary.md) و[ADR-019: scope replay](../decisions/ADR-019-s0-canonical-replay-and-checkpoint-branch-scope.md).
