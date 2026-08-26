# مصفوفة قدرات Pulse لحالة S0 — ما بعد Gate A

**تاريخ التحديث:** 2026-08-22
**الحالة:** **POST-EXPERIMENT** — مصفوفة هندسية نهائية لمسار S0 المحدود، بديلة عن القراءة التشغيلية لمصفوفة ما قبل التجربة فقط؛ تبقى وثيقة ما قبل التجربة محفوظة في [`pulse-s0-capability-matrix.md`](pulse-s0-capability-matrix.md).
**منشأ المحرك:** Pulse `4.3.2`، revision `e8a36497b8ba78e788dc201a6baf74e1c297c56f`.

> **قاعدة الحكم:** تعني `SUPPORTED` أن القدرة نفذت محليًا على الإصدار المثبت ضمن التجربة أو الاختبار المشار إليه. لا تعني صحة سريرية، أو ملاءمة علاجية، أو فعالية تعليمية، أو جاهزية لتقييم عالي العواقب. وتعني `PARTIAL` أن جانبًا محددًا فقط ثبت مع قيد معلن. وتعني `ABSENT` أنها غير منفذة في S0 أو لم تجمع لها أدلة محلية كافية.

| القدرة المطلوبة | الحالة | الدليل المحلي الدقيق | القيد المعروف | الحل البديل | تكلفة الحل البديل المقدرة |
|---|---|---|---|---|---|
| بناء وتشغيل Pulse headless | **SUPPORTED** | [تقرير Gate A، §1–2](../reports/002-pulse-gate-a.md#1-الهدف-وحدود-الادعاء)؛ سجل البناء والحالة المرجعية. | البيئة محلية مقيدة وليست حزمة نشر. | لا يلزم داخل S0. | غير منطبق. |
| زمن محاكاة مملوك لـVPE | **SUPPORTED** | [اختبارات Runtime](../../tests/test_runtime.py) و[تكامل Pulse](../../tests/test_pulse_adapter_integration.py) يثبتان `advance_time` عبر adapter. | التقدم `60s` و`120s` حاجب في القياس المحلي. | يبقى التشغيل داخل VPE، ويستهلك أي عميل مستقبلي projection فقط؛ لا يعالج ذلك latency المحرك. | **غير منطبق**؛ VPE/host/Facade قائم، ولا يبدأ Unity قبل Gate 0 والمراجعة. |
| نزف داخلي طحالي | **SUPPORTED** | [Gate A، §4.1](../reports/002-pulse-gate-a.md#41-النزف-الداخلي-الطحالي): معدل `1.000 mL/s` عند `1260s` وحجم `1229.980 mL`. | تجربة هندسية لحالة واحدة فقط؛ لا تمثل تنوع إصابات أو صحة سريرية. | لا يلزم للحالة S0 الحالية. | غير منطبق. |
| إيقاف النزف | **SUPPORTED** | [Gate A، §4.1](../reports/002-pulse-gate-a.md#41-النزف-الداخلي-الطحالي): يصبح المعدل `0.000 mL/s` عند `1261s`. | مسار Gate A تشخيصي؛ ليس فعلًا مكشوفًا كخيار متعلم في S0. | **استبعاد S0 مقصود**: لا يضاف إلى قاموس المتعلم قبل M7؛ S0 لا يحاكي التحكم/الإجراء النهائي للنزف. أي تغيير يتطلب ADR، فعل scenario-authorized ضيق، ومراجعة محتوى/طبية. | **>5 أيام** إذا فُتح النطاق؛ **غير منطبق** داخل S0 المجمد. |
| معدل القلب HR | **SUPPORTED** | أعمدة CSV Gate A في [§4.1](../reports/002-pulse-gate-a.md#41-النزف-الداخلي-الطحالي)؛ مفتاح telemetry محصور في السيناريو. | لا توجد معايرة أو مقارنة سريرية. | لا يلزم لعرض S0 المحدود. | غير منطبق. |
| ضغط الدم / MAP | **SUPPORTED** | أعمدة MAP في [§4.1](../reports/002-pulse-gate-a.md#41-النزف-الداخلي-الطحالي). | لا توصية أو عتبة قرار من هذه القيم. | لا يلزم. | غير منطبق. |
| حجم الدم وفقده | **SUPPORTED** | أعمدة `blood_volume` و`total_hemorrhaged_volume` في [Gate A، §4.1](../reports/002-pulse-gate-a.md#41-النزف-الداخلي-الطحالي). | خاص بالتجربة والحالة المثبتة. | لا يلزم. | غير منطبق. |
| مخرج الأكسجة | **PARTIAL** | `oxygen_saturation` ضمن مفاتيح telemetry المحصورة، وتتحقق اختبارات Pulse من أن القيم منتهية. | لا توجد تجربة Gate A مستقلة تفسر سلوكه أو مراجعته طبيًا. | **يُخفى من أي projection/عميل S0** حتى تجربة مستقلة ومراجعة محتوى؛ لا يعرض كدليل متعلم حاليًا. | **≤2 أيام** لتجربة هندسية مستقلة؛ **3–5 أيام** مع مراجعة محتوى قبل أي عرض. |
| Saline مقيد | **SUPPORTED** | [Gate A، §4.2](../reports/002-pulse-gate-a.md#42-saline-وpackedrbc) واختبار `test_runtime_applies_constrained_saline_then_tracks_further_time`. | قيم المحاكاة ليست جرعة أو بروتوكول علاج. | لا يلزم في الحالة المعتمدة. | غير منطبق. |
| PackedRBC مقيد | **SUPPORTED** | [Gate A، §4.2](../reports/002-pulse-gate-a.md#42-saline-وpackedrbc) واختبار `test_runtime_applies_constrained_packed_rbc_then_tracks_further_time`. | قيم المحاكاة ليست جرعة أو بروتوكول علاج. | لا يلزم في الحالة المعتمدة. | غير منطبق. |
| Snapshot الكانوني الخفيف | **SUPPORTED** | `Snapshot` لا يحمل `adapter_state`؛ اختبار `test_only_explicit_checkpoint_serializes_engine_state` واختبار Pulse `test_normal_runtime_snapshots_do_not_create_pulse_state_files`؛ M6 يقرأه إلى timeline/evidence. | اللقطة لا تستعيد محرك Pulse بذاتها. | استخدم timeline/evaluator للتفريغ؛ لا يعرض S0 branch replay منتجيًا. | غير منطبق؛ متاح للـdebrief. |
| حفظ checkpoint لمحرك Pulse | **SUPPORTED** | اختبار Pulse `test_normal_runtime_snapshots_do_not_create_pulse_state_files` يثبت ملفًا واحدًا فقط بعد `CREATE_CHECKPOINT`؛ benchmark خمس عينات وحجم `2,334,123` bytes. | artifact محلي وخاص بالadapter. | لا يلزم لفرع داخل الجلسة. | غير منطبق. |
| استعادة checkpoint واستمرار المسار | **SUPPORTED** | [Gate A، §4.3](../reports/002-pulse-gate-a.md#43-استمرارية-الحفظ-والاستعادة): 121 صفًا ومتوسط فرق `0.0000`؛ اختبار `test_checkpoint_restore_continues_on_the_same_pulse_trajectory`. | دليل مسار واحد؛ `PulseScenarioDriver` له فرق زمن مطلق/نسبي موثق. | تحقق الغلاف من الزمن والـtelemetry لا من رسالة السائق فقط. | منفذ في Runtime؛ لا تكلفة إضافية. |
| checkpoint عبر إغلاق Runtime / جلسة جديدة | **OUT_OF_SCOPE FOR S0** | `PulseAdapterConfig.state_directory` يسمح بمسار مُعد صراحة، لكن الافتراضي مؤقت ويحذف عند `close()`؛ [ADR-019](../decisions/ADR-019-s0-canonical-replay-and-checkpoint-branch-scope.md). | لا توجد استعادة durable عبر Runtime جديد، ولا يجوز تحويل primitive محلي إلى promise للمتعلم. | M6 يقدم canonical timeline + evidence findings فقط؛ checkpoint in-session يبقى debug/integration primitive. | **غير منطبق داخل S0**؛ فتحه لاحقًا **>5 أيام** (durability/security/restart review). |
| التكرارية العامة | **PARTIAL** | [Gate A، §4.3](../reports/002-pulse-gate-a.md#43-استمرارية-الحفظ-والاستعادة) يثبت مسارًا محددًا؛ [M6 regression](../reports/013-pulse-regression-replay-reproducibility.md) يثبت 5 تشغيلات لمسار مثبت داخل `1e-9`. | لا يوجد ادعاء حتمية عامة عبر منصات أو مسارات أو إصدارات. | تثبيت revision والحالة والأوامر وتسجيل evidence لكل تجربة. | **3–5 أيام** لتوسيع harness إلى مصفوفة مسارات/بيئات محددة؛ لا يثبت determinism عامًا. |
| TXA | **ABSENT** | خارج قاموس S0 واختبارات Gate A. | لا يوجد تحقق محلي أو مراجعة محتوى. | يبقى مؤجلًا خارج S0. | **>5 أيام**؛ يحتاج نطاقًا ومراجعة مستقلة. |
| تعديل وعائي / vasopressor | **ABSENT** | خارج قاموس S0 واختبارات Gate A. | لا يوجد تحقق محلي أو مراجعة محتوى. | يبقى مؤجلًا خارج S0. | **>5 أيام**؛ يحتاج نطاقًا ومراجعة مستقلة. |

## دلالة المصفوفة على Gate A وM3

يثبت الدليل أن محرك Pulse يمكن تشغيله عبر عقد S0 الضيق، وأن مسارات النزف، التدخلات المحددة، الحفظ والاستعادة متاحة **هندسيًا** على المرجع المثبت. لا ترفع هذه المصفوفة Gate A إلى مصادقة طبية، ولا تغلق Gate 0، ولا تثبت أن واجهة Unity يجب أن تبدأ. وخصوصًا، تبقى التكرارية العامة عبر منصات ومسارات متعددة، مراجعة محتوى العميل، وصلاحية العرض التعليمي مسائل منفصلة. أما checkpoint عبر restart فقد أغلق كـ**خارج نطاق S0** في ADR-019، ولا يبقى PARTIAL مفتوحًا.

## مراجع الأدلة

1. [`docs/reports/002-pulse-gate-a.md`](../reports/002-pulse-gate-a.md) — نتائج Gate A الخام وملخصها.
2. [`tests/test_pulse_adapter_integration.py`](../../tests/test_pulse_adapter_integration.py) — تكامل VPE وPulseAdapter وPulse SDK.
3. [`tests/test_runtime.py`](../../tests/test_runtime.py) — اختبارات عقد Runtime الحتمية.
4. [`artifacts/benchmarks/pre_m3_runtime_hardening/pulse_client_operation_summary.json`](../../artifacts/benchmarks/pre_m3_runtime_hardening/pulse_client_operation_summary.json) — قياس محلي بخمس عينات.
5. [`docs/contracts/pulse-adapter-process-contract.md`](../contracts/pulse-adapter-process-contract.md) — حدود عملية PulseAdapter واستمرارية الحالة.
