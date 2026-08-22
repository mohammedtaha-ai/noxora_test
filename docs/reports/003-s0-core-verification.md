# تقرير تحقق نواة S0 وPulse Bridge

> **الحالة:** تم التحقق من نواة headless المصغرة وbridge SDK حقيقي داخل البيئة الحالية. يظل runtime Python مستخدمًا بدلًا حتميًا لاختبار orchestration، بينما يثبت bridge C++ تفاعل Pulse المباشر. لا يثبت ذلك جاهزية منتج كامل أو صحة سريرية.

## 1. ما تم اختباره

| الطبقة | الاختبار | النتيجة | الدليل |
|---|---|---|---|
| عقد السيناريو | تحميل `trauma_splenic_01.json` والتحقق من وضع Learning وقاموس التدخلات | PASS | `test_versioned_source_scenario_loads_and_is_learning_mode_only` |
| ساعة runtime | لا تتغير الساعة مع التاريخ/الملاحظة؛ تتقدم فقط بأمر موجب | PASS | `test_non_physiology_actions_do_not_advance_simulation_time` |
| طابور الأوامر | يحتفظ runtime بترتيب الإرسال عند تفريغ queue | PASS | `test_command_submission_order_is_preserved` |
| عزل الأفعال | يرفض النية والتدخل غير المعتمدين من السيناريو | PASS | `test_rejects_unapproved_intent_and_intervention` |
| نشر اللقطات | ينشر runtime snapshots بعد البدء والتدخل وتقدم الزمن والـcheckpoint | PASS | اختبارات runtime و`s0_runtime_demo.json` |
| checkpoint في النواة | استعادة checkpoint تعيد telemetry المحفوظة وتعلن حد فرع | PASS | `test_checkpoint_restore_reproduces_saved_telemetry_and_marks_branch` |
| Bridge SDK | تحميل Pulse state، نزف طحالي داخلي، تقدم، حفظ، استعادة، تقدم | PASS | `pulse_sdk_bridge.json` |
| استمرارية Pulse الحقيقية | تطابق `original_continued` و`restored_continued` في artifact | PASS | `verify_pulse_bridge_artifact.py` |
| صحة JSON | parsing لمخطط event وscenario وartifact العرض | PASS | حزمة التحقق المنفذة |

## 2. النتائج الفعلية

نفذت حزمة التحقق في 2026-08-22:

```text
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/verify_pulse_bridge_artifact.py
python3 -m json.tool schemas/event-envelope.schema.json
python3 -m json.tool scenarios/trauma_splenic_01.json
python3 -m json.tool artifacts/representative-small-results/s0_runtime_demo.json
```

أكملت **8 اختبارات runtime** بنجاح. كما أعاد verifier العبارة `PASS: Pulse bridge artifact has pinned provenance and exact continuation equality`.

يعرض artifact المباشر لـ Pulse revision `e8a3649` وإصدار `4.3.2`. بعد 120 ثانية من النزف الطحالي الداخلي التجريبي سجّل المحرك حجم نزف كلي `119.980000 mL`. بعد الحفظ ثم تقدم 60 ثانية، تطابقت قيم المسار الأصلي والمسار المستعاد عند `180 s` في الوقت ومعدل القلب وMAP وحجم الدم وإجمالي النزف والأكسجة. هذه حقائق تشغيل محلي مسجلة في artifact، وليست قياسات من مريض أو توقعات علاجية.

## 3. التغطية والحدود

| الموضوع | التغطية | ما يزال غير منفذ أو غير مثبت |
|---|---|---|
| ملكية الزمن | runtime يملك إصدار أمر التقدم؛ adapter لا يستدعى إلا من runtime | adapter Pulse Python production أو IPC. |
| أوامر المتعلم | تاريخ، ملاحظات، تدخلات مقيدة، checkpoints | تصعيد منظم وFAST resolver في مرحلة لاحقة. |
| إعادة التشغيل | أحداث وsnapshots وcheckpoint branch في النواة؛ استعادة مباشرة في bridge | إدارة فروع/واجهة replay للمستخدم. |
| Pulse | bridge C++ حقيقي وGate A scenario runner | تغليف adapter الإنتاجي طويل العمر وربطه بالـruntime. |
| العميل | لا شيء | Unity round-trip غير منفذ ولا يدّعى. |
| AI | لا شيء | LLM وintent mapping حر وdebrief مؤجلون. |
| سلامة الاستخدام | قيود Learning Mode في عقد السيناريو واختبارات الرفض | تحقق سريري وتعليمي مستقل، وreview خبراء. |

## 4. ملاحظات قبول هندسية

يعتمد bridge على SDK Pulse محلي تم بناؤه عند revision المثبت، وعلى حالة `StandardMale@0s.json` مولدة محليًا. لا يلتزم المستودع بالمكتبات أو ملف الحالة الكبير؛ يعيد [`scripts/run_pulse_bridge.sh`](../../scripts/run_pulse_bridge.sh) البناء والتشغيل عندما توفر بيئة عمل `PULSE_ROOT` صحيحًا. يثبت [`scripts/verify_pulse_bridge_artifact.py`](../../scripts/verify_pulse_bridge_artifact.py) الـprovenance واستمرارية المسار، لا مطابقة مسار طبي أو قرار علاجي.

يجب أن يبقى أي تنفيذ لاحق لـ adapter Pulse متوافقًا مع العقد الضيق: حالة بداية معلنة، تقدم زمن VPE، قاموس تدخلات معتمد، telemetry محدد، لقطات موثقة بالإصدار، واستعادة تتحقق من الزمن المطلق. يمنع runtime إدخال أوامر Pulse خامة من عميل مستقبلي أو من طبقة لغة.

## المراجع

[1]: https://pulse.kitware.com/ "Pulse Physiology Engine"
[2]: https://gitlab.kitware.com/physiology/engine "Pulse source repository"
