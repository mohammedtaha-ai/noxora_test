# مراجعة تقنية لـ Pulse من أجل Gate A

**تاريخ الوصول الأولي:** 2026-08-22
**تاريخ التحديث التجريبي:** 2026-08-22
**الغرض:** فصل ما توثقه المصادر الرسمية عن نتائج Gate A المحلية القابلة لإعادة الإنتاج.
**الوثيقة المكملة:** [تقرير Gate A](../reports/002-pulse-gate-a.md) هو سجل التنفيذ والمخرجات الخام، وليس هذا التقرير بديلًا عنه.

> **النتيجة الهندسية:** Pulse مناسب كمرشح فيزيولوجي لـS0 ضمن عقد ضيق ومثبت الإصدار. ثبت محليًا النزف الطحالي الداخلي والإيقاف وSaline وPackedRBC والمخرجات الأساسية والحفظ/الاستعادة. لا تثبت هذه النتائج صحة سريرية أو ملاءمة نهائية أو أمانًا سريريًا.

## هوية المكون ومنشأ البناء

| البند | النتيجة | حالة الدليل |
|---|---|---|
| الاسم والمشرف | **Pulse Physiology Engine** من Kitware، وهو محرك C++ لمحاكاة فيزيولوجيا بشرية. | **UPSTREAM DOCUMENTED** [1] |
| المصدر الرسمي | مستودع Kitware GitLab: `physiology/engine`. | **UPSTREAM DOCUMENTED** [2] |
| المصدر المختبر | فرع `stable` عند `e8a36497b8ba78e788dc201a6baf74e1c297c56f`. | **VERIFIED** محليًا |
| نسخة SDK الناتجة | `4.3.2`، hash مختصر `e8a3649`. | **VERIFIED** من `PulseBuildInformation` وartifact bridge |
| وضع البناء | Release مع Java وPython مفعّلين. | **VERIFIED** محليًا |
| الترخيص | Apache License 2.0 في ملف المصدر المحلي. | **VERIFIED**؛ راجع [سجل provenance](pulse-provenance-and-license.md). |

## واجهة التحكم وعلاقة ذلك بقيود VPE

توثق Pulse أن مثيل المحرك يمثّل مريضًا واحدًا وأن واجهة `PhysiologyEngine` تدعم إنشاء المحرك وتقدم الزمن وتنفيذ الأفعال واسترداد المخرجات [3]. فرضت Nexora فوق ذلك قاعدة أكثر تقييدًا: VPE هو المالك الوحيد لترتيب الأوامر وتقدم الزمن؛ لا يصل العميل المستقبلي أو طبقة لغة إلى Pulse مباشرة.

| مطلب S0 | دليل المصدر الرسمي | نتيجة Gate A / bridge |
|---|---|---|
| مالك واحد للزمن | API يعرض تقدم الزمن؛ `ScenarioDriver` ينفذ ملفات JSON. [3] | **VERIFIED** أن تقدم الزمن يعمل headlessly؛ يفترض runtime مالكًا واحدًا. سلامة مشاركة مثيل بين خيوط ليست مثبتة. |
| مريض ابتدائي | API تسمح بتهيئة مريض أو تحميل حالة محفوظة. [3] | **VERIFIED** عبر `StandardMale@0s.json` المولدة محليًا. |
| حفظ/تحميل | API تعرض `SerializeToFile` و`SerializeFromFile`. [3] | **VERIFIED**: تطابق 121 صف CSV متداخل، وbridge C++ يطابق استمرارية 60 ثانية تمامًا. |
| سيناريوهات دفعة | JSON و`PulseScenarioDriver` متاحان. [1] | **VERIFIED** عبر 3 سيناريوهات CSV مراقبة وحفظ/استعادة. |
| مخرجات منظمة | API تعرض بيانات فسيولوجية وطلبات بيانات. [3] | **VERIFIED** لـ HR وMAP وحجم/فقد الدم والأكسجة في artifacts Gate A. |

## النزف والإنعاش والمخرجات

تصف منهجية القلب والأوعية `hemorrhage` كفعل ضمن دورة القلب والأوعية، وتصف حساب الضغط والتدفق والحجم [4]. يعرّف مصدر `stable` المحلي موضع `Spleen` ونوع `Internal`؛ ويذكر مثال C++ الرسمي أن النزف الداخلي يجمع الدم في التجويف البطني [5]. جرى اختبار تلك الواجهة محليًا بدل الاكتفاء بالقراءة.

| قدرة Gate A | الدليل المحلي | الحالة |
|---|---|---|
| نزف داخلي/طحالي | عند `31 s` يسجل CSV معدل نزف `1.000 mL/s`؛ عند الإيقاف يصبح `0.000 mL/s` في الصف التالي. | **SUPPORTED** في revision المثبت. |
| HR وBP/MAP | حقول مسجلة في كل CSV Gate A وbridge المباشر. | **SUPPORTED**. |
| حجم/فقد الدم | `TotalHemorrhagedVolume` و`BloodVolume` مسجلان؛ يبلغ النزف الطحالي التجريبي `1229.980 mL` قبل الإيقاف. | **SUPPORTED**. |
| الأكسجة | `OxygenSaturation` مسجلة في سيناريوهات Gate A. | **SUPPORTED** كمخرج محاكاة؛ تفسيره الطبي ليس ضمن هذا التقرير. |
| Saline | نفذ `SubstanceCompoundInfusion` للمركب `Saline` بعد النزف، وسجل المحرك اكتمال التسريب. | **SUPPORTED**. |
| PackedRBC | نفذ `SubstanceCompoundInfusion` للمركب `PackedRBC` بعد النزف وسجل CSV المسار. | **SUPPORTED**. |
| إيقاف/ضبط النزف | إرسال فعل نزف بالمعدل صفر يوقف معدل النزف المراقب. | **SUPPORTED**. |
| حفظ/استعادة | CSV وbridge يثبتان استمرارًا متطابقًا ضمن التجارب المحددة. | **SUPPORTED** مع ضابط زمني موثق أدناه. |

## ملاحظات بناء وتشغيل

| الموضوع | ما هو موثق أو مقاس | الدلالة لـ S0 |
|---|---|---|
| اللغة والبناء | C++ هو المحرك الأساسي ويدعم SDK CMake؛ بني بنجاح محليًا. [1] | bridge C++ حقيقي قابل للبناء عبر `find_package(Pulse)`. |
| توليد البيانات | وثائق Pulse تصف `gendata` و`genStates` لتوليد حالات الاستخدام. [6] | يلزم التشغيل قبل استخدام `StandardMale@0s.json`. |
| البدء | يحتاج تثبيت الحالة الأولى وقتًا؛ استخدام حالة مولدة سابقًا يتجنب إعادة الاستقرار لكل تشغيل. | يجب حفظ provenance للحالة ولا يُلتزم الملف الكبير في Git. |
| الأداء | Gate A أكمل سيناريوهات 1140–2880 ثانية محاكاة headlessly؛ التقرير يحتوي السجلات. | لا يترجم ذلك إلى هدف أداء منتج أو multi-user. |
| التزامن | لا توجد تجربة سلامة خيوط لمثيل واحد. | runtime يحتفظ بمالك واحد ويمنع التقدم المتزامن. |

## حدود ومخاطر مثبتة

1. يعرض `PulseScenarioDriver` تشخيصًا لزمن النهاية عند استعادة state: يقارن زمن تقدم نسبي بزمن محاكاة مطلق. لم يمنع ذلك الاستعادة، لأن CSV المتداخل والـbridge أثبتا تطابق المسار؛ لكن أي adapter إنتاجي يجب أن يتحقق من الزمن المطلق والبيانات، لا من رسالة السائق وحدها.
2. لا تثبت تجارب Gate A إعادة تشغيل bit-for-bit عامة خارج المدخلات والنسخة والإعداد وترتيب الأوامر المختبرة. تستخدم Nexora كلمة **reproducibility** لا **determinism**.
3. لا توجد صلاحية سريرية أو تعليمية ولا معايرة حالة S0 من خبراء في هذا المستودع. لا تتحول أسماء المركبات أو معدلات السيناريو إلى توصيات.
4. لم يبدأ Unity أو FAST spatial resolver أو LLM؛ وهي لا تدخل دليل الملاءمة headless.
5. لا توزع Nexora مكتبات Pulse أو بياناته أو حالات المرضى الكبيرة حاليًا. يجب إكمال مراجعة توزيع وترخيص قبل الإطلاق.

## قرار البحث

**RECOMMEND — استخدم Pulse كقاعدة فيزيولوجية قابلة للاستبدال لنواة S0 headless، مع تثبيت revision وعقد adapter ضيق ومالك زمن واحد.** يظل القرار مشروطًا بمراجعة المحتوى الطبي/التعليمي وبإنجاز adapter إنتاجي وخطة توزيع قبل أي منتج مستخدم.

## المراجع

[1]: https://pulse.kitware.com/ "Pulse Physiology Engine — official"
[2]: https://gitlab.kitware.com/physiology/engine "Pulse source repository — official"
[3]: https://pulse.kitware.com/physeng.html "Pulse Physiology Engine Interface — official"
[4]: https://pulse.kitware.com/_cardiovascular_methodology.html "Pulse Cardiovascular Methodology — official"
[5]: https://gitlab.kitware.com/physiology/engine/-/tree/stable "Pulse stable source — official"
[6]: https://pulse.kitware.com/_docs.html "Pulse documentation and build guidance — official"
