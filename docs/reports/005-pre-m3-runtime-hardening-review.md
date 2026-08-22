# مراجعة تقوية عقد Runtime قبل M3

**التاريخ:** 2026-08-22
**النطاق:** إعادة عمل Runtime قبل قرار عميل Unity M3.
**القرار النهائي:** **M3 REWORK**.

> هذا التقرير يوثق عقد محاكاة تكويني S0 وقياسات هندسية محلية فقط. لا يمثل صحة سريرية أو فعالية تعليمية أو صلاحية لتقييم عالي العواقب أو توصية علاجية.

## الملخص التنفيذي

استجابت حزمة إعادة العمل لمخاطر الاعتماد المبكر لعميل UI على عقد Runtime غير مستقر. فصلت النواة اللقطات الكانونية الخفيفة عن artifacts checkpoints القابلة للاستعادة، ومنعت حذف أوامر لاحقة عند فشل أمر في الطابور، ونقلت التحقق البنيوي قبل أي أثر ممكن على Pulse، وأدخلت `request_id` محدودًا داخل الجلسة لمنع تكرار الأوامر ذات الأثر. كما رُفع عقد السيناريو إلى v1.2 ليحفظ كل الحقول المؤلفة ويمنع إسقاطها الصامت، وفُصلت فرضية النزف الداخلي المنظمة عن نية أخذ التاريخ.

النتيجة الهندسية قوية لمسار S0 المحدود، لكن لا تزال شروط القرار غير التقنية مفتوحة: Gate 0 غير مختبرة، والمراجعة الطبية/التعليمية المستقلة لم تنفذ، وعقد النقل وlifecycle لواجهة M3 لم ينفذ بعد، واستعادة checkpoint عبر إعادة تشغيل Runtime غير مثبتة. لذلك لا يكفي النجاح البرمجي لإصدار **M3 GO**.

## النتائج المعالجة

| الملاحظة السابقة | المعالجة | حالة الدليل |
|---|---|---|
| كل `Snapshot` كان يستدعي `adapter.save_state()`. | أزيلت `adapter_state` من `Snapshot`؛ ينشئ `CREATE_CHECKPOINT` وحده `CheckpointArtifact` منفصلًا. | **VERIFIED** بوحدة وتكامل Pulse فعلي. |
| فشل الأمر B قد يزيل C وD من الطابور. | عند فشل B يُستهلك B كرفض نهائي، وتبقى C وD بالترتيب الأصلي لطرد صريح لاحق. | **VERIFIED** باختبار `valid → invalid → valid`. |
| actor/payload قد يفشلان عند حفظ الدليل بعد أثر Pulse. | أضيف `_validate_command()` قبل `advance` و`apply_intervention`؛ يفحص actor وpayload والقواميس ومدة زمن منتهية. | **VERIFIED** لا تغير في الزمن أو الأحداث أو اللقطات للاختبارات السالبة. |
| لا حماية من double-click/retry في عميل مستقبلي. | أضيف `request_id` ثابت داخل الجلسة؛ الطلب المتطابق يعيد `command_id` القائم وoutcome المسجل ولا يعيد التنفيذ. | **VERIFIED** بوحدة وPulse فعلي؛ **PARTIAL** عبر الجلسات أو النقل. |
| الحقول المؤلفة في JSON لا تحفظ جميعًا. | عقد 1.2 ومخطط JSON وloader صارم يرفض المفاتيح الزائدة/الناقصة والتكرارات ويحفظ الأهداف والملاحظات والـcompletion والفرضيات. | **VERIFIED** باختبارات parity ورفض حقل زخرفي. |
| observations كانت hardcoded في Runtime. | `VITALS` مدمج صراحة؛ `FAST` و`CBC` من `observations.allowed` المؤلفة فقط. | **VERIFIED**؛ CBC مرفوض في السيناريو الحالي. |
| اشتباه النزف كان نية تاريخ. | أضيف `record_clinical_hypothesis(INTERNAL_BLEEDING)` وحدث `clinical.hypothesis.recorded`. | **VERIFIED**؛ لا نص حر ولا تشخيص واقعي. |
| مصفوفة Gate A بقيت PRE-EXPERIMENT. | نُشرت [مصفوفة ما بعد Gate A](../research/pulse-s0-capability-matrix-post-gate-a.md) مع الأدلة والقيود والبدائل. | **PUBLISHED**. |

## الكود والعقود المعدلة

| المجال | عناصر رئيسية |
|---|---|
| نماذج Runtime | `Snapshot` خفيف، `CheckpointArtifact` منفصل، و`Command.request_id` اختياري. |
| Runtime | احتفاظ آمن بطابور الأوامر، تحقق قبل الأثر، فهرس requests داخل الجلسة، outcome مقبول، observations من السيناريو، وأحداث الفرضية. |
| السيناريو | `S0Scenario` v1.2، `ObservationDefinition`، فرضيات مسموحة، أهداف تعلم وcompletion صريحان. |
| التحميل والمخطط | `scenario_io.py` يرفض الانحراف الصامت؛ أضيف `schemas/s0-scenario.schema.json` وعدل event schema. |
| العقود | [PulseAdapter](../contracts/pulse-adapter-process-contract.md) يفرق replay عن checkpoint؛ [VPE Client Facade](../contracts/vpe-client-facade-contract.md) يوثق request_id ومنع retry الأعمى. |

## الاختبارات المنفذة فعليًا

نفذ الأمر التالي بعد جميع التعديلات، مع جعل `ResourceWarning` خطأ:

```bash
PULSE_ROOT=/home/ubuntu/pulse-build/install \
PYTHONPATH=src \
python3 -W error::ResourceWarning -m unittest discover -s tests -v
```

| مجموعة الاختبار | النتيجة الفعلية | ما تغطيه |
|---|---:|---|
| Runtime الحتمي | 19 اختبارًا ضمن المجموعة الكاملة | snapshots مقابل checkpoints، ترتيب الطابور، تحقق قبل الأثر، تكرار الطلب، parity السيناريو، observations، فرضيات التاريخ/التشخيص. |
| تكامل Pulse SDK الحقيقي | 7 اختبارات ضمن المجموعة الكاملة | نزف طحالي، Saline، PackedRBC، checkpoint/restore، عدم حفظ state للقطات العادية، وrequest_id مكرر لا يكرر الزمن. |
| الإجمالي | **26 اختبارًا نجح في 22.934s** | لا توجد اختبارات Pulse متخطاة في هذا التشغيل. |

لا تثبت هذه النتائج صلاحية سريرية أو تعليمية؛ تثبت فقط السلوك البرمجي للمسارات والمدخلات المشغلة.

## benchmark عمليات العميل الحرجة

شغل [`scripts/benchmark_pulse_client_operations.py`](../../scripts/benchmark_pulse_client_operations.py) بخمس تكرارات على Pulse المثبت محليًا. المخرجات الخام في [`pulse_client_operation_samples.csv`](../../artifacts/benchmarks/pre_m3_runtime_hardening/pulse_client_operation_samples.csv) والملخص في [`pulse_client_operation_summary.json`](../../artifacts/benchmarks/pre_m3_runtime_hardening/pulse_client_operation_summary.json).

| العملية | الوسيط (ms) | P95 (ms) | تغير زمن المحاكاة | ملاحظة |
|---|---:|---:|---:|---|
| قراءة telemetry | 0.071 | 0.073 | 0 | طلب محلي بعد bootstrap. |
| `advance 1s` | 37.243 | 37.637 | +1s | عملية حقيقية على SDK. |
| `advance 10s` | 349.649 | 351.103 | +10s | عملية حقيقية على SDK. |
| `advance 60s` | 2094.951 | 2107.608 | +60s | يجب ألا تنفذ على Unity rendering/main thread. |
| `advance 120s` | 4210.104 | 4363.489 | +120s | يجب ألا تنفذ على Unity rendering/main thread. |
| checkpoint save | 24.573 | 25.875 | 0 | artifact حجمه `2,334,123` bytes. |
| checkpoint restore | 54.382 | 58.665 | −30s | القياس بعد تقدم إضافي 30s ثم استعادة. |

هذه القياسات محلية في sandbox؛ لا تشمل bootstrap أو بناء CMake أو نقل شبكة أو زمن إطار Unity. تستخدم لاتخاذ قرار عدم حجب خيط عرض مستقبلي، لا كـSLA أو أداء إنتاج.

## حدود باقية

| البند | الحالة | الأثر على M3 |
|---|---|---|
| Gate 0 وقيمة المنتج | **UNTESTED** | لا دليل على أن الواجهة المقترحة تحل حاجة تعليمية ذات أولوية. |
| مراجعة طبية وتعليمية مستقلة | **UNTESTED** | لا يجوز تحويل telemetry أو الأفعال إلى دلالات تعليمية معتمدة بعد. |
| Facade والنقل وlifecycle | **DOCUMENTED ONLY** | عقد التخطيط موجود، لكن لا توجد عملية host أو DTOs تشغيلية أو مشروع Unity. |
| checkpoint عبر إعادة تشغيل Runtime | **PARTIAL** | لا ادعاء branch replay عبر الجلسة؛ الافتراضي يحذف artifacts عند الإغلاق. |
| exactly-once عبر الشبكة/الجلسات | **ABSENT BY DESIGN** | `request_id` يحمي الذاكرة داخل Runtime فقط؛ لا retry تلقائي غامض. |
| FAST المكاني | **DEFERRED** | يبقى FAST طلب observation منظمًا فقط؛ resolver مؤجل إلى M4. |
| الصلاحية السريرية/التعليمية والتقييم | **UNVALIDATED / PROHIBITED** | المنتج S0 Learning Mode تكويني فقط. |

## حالة البوابات

| البوابة أو الحكم | الحالة |
|---|---|
| Gate A الهندسية | **اجتياز هندسي مشروط**؛ لا ترقية إلى تحقق سريري. |
| Runtime contract hardening | **VERIFIED** للمسارات المختبرة محليًا. |
| Gate 0 | **UNTESTED**. |
| التحقق الطبي | **UNVALIDATED**. |
| الفعالية التعليمية | **UNVALIDATED**. |
| تنفيذ Unity / M3 | **NOT STARTED**. |

## التزامات Git لهذه الحزمة

| الالتزام | الموضوع |
|---|---|
| `0554a24` | `refactor(runtime): separate snapshots from engine checkpoints` |
| `dd06ca5` | `test(pulse): cover explicit checkpoint state creation` |
| `d59e305` | `fix(runtime): preserve queue and validate before side effects` |
| `3743e3e` | `feat(runtime): add minimal command idempotency` |
| `92c2cd2` | `refactor(scenario): enforce authored scenario contract parity` |
| `9e3f253` | `perf(runtime): benchmark Pulse client-critical operations` |
| `eba0862` | `docs(gate-a): publish final Pulse capability matrix` |

## التوصية الوحيدة

# **M3 REWORK**

لا تبدأ Unity في هذه الحزمة. أُغلق خطر اعتماد العميل على Snapshot ثقيل أو طابور غير آمن أو request مكرر داخل الجلسة، لكن قرار M3 ما زال يتطلب إغلاق Gate 0، مراجعة المحتوى طبيًا وتعليميًا، واعتماد/تنفيذ عقد Facade وخطة lifecycle قبل أن يصبح عميل Unity مستهلكًا لعقد مستقر.
