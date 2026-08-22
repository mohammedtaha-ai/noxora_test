# عقد عملية PulseAdapter — الإصدار 1.0

> **الغرض:** يحدد هذا العقد طبقة بنية تحتية لمحاكاة تعليمية تكوينية. لا يصف بروتوكولًا علاجيًا، ولا يقدّم تشخيصًا أو توصية لمريض حقيقي، ولا ينشئ تقييمًا عالي العواقب.

## الموضع المعماري

ينشئ `PulseAdapter` في Python عملية محلية واحدة باسم `nexora_pulse_adapter_server`. تحتفظ العملية بمثيل `PhysiologyEngine` واحد فقط، وتصل إليها نواة VPE عبر أوامر محدودة ومتحقق منها. لا يملك العميل المستقبلي أو Unity أو طبقة لغة أو المتعلم قناة مباشرة إلى SDK Pulse.

```text
VPE Runtime
    ↓ PhysiologyAdapter contract
PulseAdapter (Python process client)
    ↓ tab-delimited local stdio protocol
nexora_pulse_adapter_server (C++ / one Pulse engine)
    ↓ pinned local Pulse SDK
Pulse state + telemetry
```

## شرط provenance

عند `bootstrap` يطلب Python من الخادم `VERSION`. يقارن adapter hash المختصر من SDK مع بادئة `scenario.pulse_revision`. يرفض البدء عند عدم التطابق. في الاختبار المرجعي كان revision المثبت `e8a3649` من Pulse `4.3.2`، بما يتوافق مع تعريف السيناريو S0.

| الأصل | الآلية | الحاجز |
|---|---|---|
| حالة البداية | `StandardMale@0s.json` ضمن Pulse installation المحلية | يجب أن توجد قبل التشغيل. |
| المرض الموجود مسبقًا | `BOOTSTRAP` يطبّق نزفًا داخليًا طحاليًا فقط | لا يوجد أمر متعلم لإنشاء إصابة. |
| التقدم | `ADVANCE` يقبل مدة موجبة فقط | VPE هو صاحب القرار الوحيد لطلب التقدم. |
| التدخل | `APPLY` يقبل `Saline` و`PackedRBC` فقط، مع حجم ومعدل موجبين | لا تمر أفعال Pulse خامة. |
| اللقطة | `SAVE` يكتب state محليًا ويحفظ SHA-256 | لا تقبل الاستعادة ملفًا خارج مجلد حالة adapter. |
| الاستعادة | `RESTORE` ينشئ مثيل Pulse جديدًا ويحمل state المثبتة | يتحقق adapter من version وscenario وdigest والزمن المستعاد. |

## بروتوكول النقل

كل طلب ورد هو سطر UTF-8 واحد بحقول مفصولة بـtab. لا يسمح الحقل بعلامة tab أو newline. يرد الخادم بسطر واحد يبدأ بـ`OK` أو `ERR`. لا توجد شبكات أو HTTP أو أوامر shell في البروتوكول.

| الأمر | حقول الطلب بعد الاسم | الرد الناجح | الدلالة |
|---|---|---|---|
| `VERSION` | لا شيء | `PulseVersion`, `PulseHash` | يثبت revision SDK. |
| `BOOTSTRAP` | state file، `Spleen`، flow `mL/min` | زمن محاكاة | يحمل الحالة ويطبّق مرض S0 الموجود. |
| `ADVANCE` | مدة موجبة بالثواني | زمن محاكاة | يتقدم المحرك. |
| `APPLY` | compound، حجم `mL`، معدل `mL/min` | زمن محاكاة | ينفذ infusion من القاموس الضيق. |
| `TELEMETRY` | مفاتيح S0 المطلوبة | الزمن ثم `key=value` | يعيد values المنظمة فقط. |
| `TIME` | لا شيء | زمن محاكاة | يزامن ساعة Python مع المحرك. |
| `SAVE` | مسار محلي | زمن محاكاة | يسلسل حالة Pulse. |
| `RESTORE` | مسار محلي | زمن محاكاة | يستعيد حالة سابقة موثقة. |
| `QUIT` | لا شيء | `OK` | يغلق العملية المنظمة. |

المفاتيح المسموح بها للـtelemetry هي `heart_rate_bpm` و`mean_arterial_pressure_mmhg` و`blood_volume_ml` و`total_hemorrhaged_volume_ml` و`oxygen_saturation`. لا تسرب أسماء أعمدة CSV أو طلبات بيانات Pulse إلى عقد العميل.

## دورة الحياة والفشل

ينشئ adapter عملية منفصلة عند `bootstrap`، ويوقفها في `close` أو عند الخروج من context manager. مهلة كل طلب معرفة في `PulseAdapterConfig`؛ إذا تجاوزت العملية المهلة يغلق adapter العملية ويرفع `PulseAdapterError`. لا تعيد النواة تشغيل العملية خفية أو تعيد تنفيذ أمر زمني تلقائيًا، لأن ذلك قد يكسر دليل الترتيب. أي تعافٍ لاحق يجب أن يبدأ من checkpoint صريح ومسجل.

يلزم أن تكون ملفات الحالة المؤقتة داخل `state_directory` الخاص بالـadapter، وأن تطابق SHA-256 المسجلة قبل `RESTORE`. لا يمثّل digest تشفيرًا أو حماية وصول؛ إنه فحص سلامة ونسبة artifact فقط.

## العلاقة بإعادة التشغيل

التسلسل القانوني للـcheckpoint هو حفظ state، ثم استمرار مسار أصلي، ثم استعادة state نفسها، ثم تقدم بديل أو مكرر. لا تصف Nexora هذا كضمان determinism عام. يثبت اختبار التكامل فقط أن القيم الخمس المراقبة تتطابق ضمن دقة `assertAlmostEqual(..., places=6)` للمسار والنسخة والمدخلات المختبرة.

## التنفيذ والاختبار

يبني [`scripts/test_pulse_adapter_integration.sh`](../../scripts/test_pulse_adapter_integration.sh) الخادم عبر CMake ثم يشغّل اختبارات التكامل عند توفير `PULSE_ROOT`. تسجل النتائج في [تقرير تكامل PulseAdapter](../reports/004-pulse-adapter-integration.md). يبقى Bridge Gate A المنفصل دليلًا إضافيًا على SDK ولا يحل محل هذا العقد.
