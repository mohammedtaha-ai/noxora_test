# تقرير تكامل PulseAdapter الإنتاجي

> **الحالة:** اجتازت طبقة `PulseAdapter` واختبارات تكاملها على SDK Pulse المثبت. يثبت التقرير مسارًا هندسيًا headless لنواة S0، ولا يثبت صحة سريرية أو ملاءمة تعليمية أو جاهزية واجهة مستخدم.

## الهدف

استبدلت هذه المرحلة الاعتماد التشغيلي لنواة S0 على `DeterministicPhysiologyAdapter` بــadapter إنتاجي اختياري يملك عملية Pulse SDK حقيقية واحدة. يبقى البديل الحتمي موجودًا لاختبارات الوحدة السريعة، لكن اختبار التكامل ينفذ `VpeRuntime → PulseAdapter → C++ server → Pulse SDK`.

## بيئة التحقق

| العنصر | القيمة |
|---|---|
| Pulse SDK | `4.3.2` |
| Pulse hash | `e8a3649`، متوافق مع scenario pin `e8a36497b8ba78e788dc201a6baf74e1c297c56f` |
| حالة البداية | `StandardMale@0s.json` المولدة محليًا |
| خادم العملية | `nexora_pulse_adapter_server`، مبني من `adapter_server.cpp` |
| عقد السيناريو | `trauma_splenic_01.json`، Learning Mode فقط |
| النقل | local stdio tab-delimited؛ لا شبكة ولا LLM |

## التحقق المنفذ

نفذ الأمر التالي بنجاح:

```bash
PULSE_ROOT=/home/ubuntu/pulse-build/install \
PYTHONPATH=src \
python3 -W error::ResourceWarning -m unittest discover -s tests -v
```

أكمل الأمر **13 اختبارًا** في `22.418s`: 8 اختبارات نواة حتمية و5 اختبارات تكامل على Pulse SDK. كما اكتمل مشغل الإعادة `scripts/test_pulse_adapter_integration.sh` بنجاح، حيث يعيد بناء الخادم قبل التنفيذ.

| اختبار التكامل | النتيجة | ما يثبته |
|---|---|---|
| تقدم الزمن والنزف القائم | PASS | يقوم runtime بطلب تقدم 120 ثانية، فيرتفع إجمالي حجم النزف وتبقى القيم المراقبة finite. |
| Saline المقيد | PASS | يعبر `crystalloid_saline` من قاموس السيناريو إلى Pulse ثم يواصل المسار. |
| PackedRBC المقيد | PASS | يعبر `blood_packed_rbc` من قاموس السيناريو إلى Pulse ثم يواصل المسار. |
| checkpoint والاستعادة | PASS | تعود اللقطة إلى زمن 120 ثانية وتطابق telemetry؛ ثم تتطابق استمرارية 60 ثانية لاحقة ضمن ست منازل عشرية. |
| رفض compound غير معتمد | PASS | يرفض adapter المركب قبل وصوله إلى Pulse ولا يتقدم زمن المحاكاة. |

## الحواجز المنفذة

يتحقق adapter من executable وخانات SDK، وحالة البداية، وتطابق hash SDK مع pin السيناريو. لا يقبل إلا `Spleen` في bootstrap و`Saline` أو`PackedRBC` في التدخل. يحفظ `save_state` ملف state محليًا مع SHA-256 وإصدار المحرك ومعرف السيناريو وزمن المحاكاة؛ ترفض `restore_state` أي نوع adapter أو SDK أو سيناريو أو digest أو مسار غير مطابق.

لا يعد فحص digest آلية أمنية أو تشفيرًا؛ بل يمنع اختلاط artifact محلي غير مقصود في مسار replay. لا ينفذ adapter إعادة محاولة صامتة بعد timeout أو crash، لأن إعادة الأمر قد تعيد تقدم الزمن. تظل معالجة crash/recovery المتقدمة، وإدارة عمليات متعددة، وIPC عبر خدمة منشورة خارج نطاق S0 الحالي.

## ما لا يثبته التقرير

لا تثبت الاختبارات تفسير قيم vital signs، أو اختيار تدخل مناسب، أو صحة زمن/معدل السيناريو طبيًا، أو سلوك المريض الحقيقي. لا توجد Unity أو FAST spatial resolver أو AI Patient أو debrief في هذا التنفيذ. لا يدّعي التقرير determinism عامًا؛ التحقق يقتصر على النسخة المثبتة وحالة البداية وترتيب الأوامر والمسار المختبر.

## مراجع داخل المستودع

- [عقد عملية PulseAdapter](../contracts/pulse-adapter-process-contract.md)
- [تقرير Gate A](002-pulse-gate-a.md)
- [تحقق نواة S0 والـbridge](003-s0-core-verification.md)
- [provenance وترخيص Pulse](../research/pulse-provenance-and-license.md)
