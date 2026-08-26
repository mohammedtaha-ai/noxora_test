# جرد أدلة S0

## مبادئ السلطة

الدليل الموثوق في S0 منظم وقابل للنسبة إلى حدث أو لقطة أو مخرج محرك. تظل الحقيقة الفسيولوجية في Pulse، وتظل معرفة المتعلم متميزة عن حالة العالم. لا يمكن لطبقة اللغة إنشاء دليل أو تعديل حالة المحاكاة.

| معرف الدليل | المصدر الموثوق | الحدث الناشر | المستهلك | حدود التفسير |
|---|---|---|---|---|
| `E-STATE` | لقطة محرك/تيليمترية | `snapshot.published` | timeline، monitor، debrief | قيمة محاكاة مثبتة بالإصدار، وليست قيمة مريض حقيقي. |
| `E-HISTORY` | نية تاريخ منظمة | `clinical.intent.recorded` | debrief | يوثق محاولة استجلاء معلومة، لا جودة الحوار الحر. |
| `E-HYPOTHESIS` | فرضية سريرية منظمة | `clinical.hypothesis.recorded` | debrief | يسجل اختيارًا ضمن السيناريو، لا تشخيصًا واقعيًا أو نصًا حرًا. |
| `E-OBSERVATION` | `VITALS` المدمج أو طلب مؤلف في السيناريو | `observation.requested` | debrief، واجهة مستقبلية | لا يساوي نتيجة فحص حر قبل وجود resolver محدد. |
| `E-FAST` | resolver + finding مضبوط بالسيناريو | `fast.acquisition.recorded` **RESERVED في S0 v1.1**؛ producer `future_fast_resolver` غير منفذ حتى M4 | debrief لاحق | الحجز يمنع كسر enum/projection لاحقًا؛ لا يمثل تصويرًا طبيًا حرًا ولا يتيح M6 producer أو resolver. |
| `E-ESCALATION` | معرف مصرح به في قاموس السيناريو | `escalation.recorded` | timeline، debrief | يثبت نية منظمة فقط؛ لا يغير Pulse ولا يثبت ملاءمة القرار واقعيًا. |
| `E-INTERVENTION` | أمر مقبول وقاموس تدخلات | `intervention.applied` | Pulse adapter، timeline | قبول المحرك ليس توصية أو مصادقة طبية. |
| `E-TIMELINE` | ساعة VPE وتسلسل أوامر | جميع أحداث envelope | replay، debrief | زمن محاكاة فقط؛ لا يضم زمن شبكي أو LLM. |
| `E-CHECKPOINT` | artifact محرك منفصل وdigest | `checkpoint.created` | debug/integration فقط | artifact داخل Runtime قائم؛ ADR-019 يخرج restart/branch replay من S0 ولا يقدمه كميزة متعلم. |
| `E-REQUEST` | `request_id` وoutcome داخل الجلسة | event مقبول مرتبط بالأمر | Facade مستقبلي | يمنع التكرار داخل Runtime فقط، ولا يثبت exactly-once موزعًا أو عبر جلسة جديدة. |

## الحد الأدنى لنشر لقطة

ينشر runtime لقطة منظمة بعد تقدم زمن أو تدخل مقبول أو إنشاء checkpoint. تتضمن اللقطة معرف السيناريو، زمن المحاكاة، نسخة engine، قيم telemetry مسموحة، وسبب النشر فقط. لا تتضمن `adapter_state` أو مسار artifact أو digest checkpoint، ولا تحفظ نص LLM أو استنتاجات غير منظمة. يمثل artifact checkpoint مجالًا منفصلًا داخل Runtime قائم فقط، وليس جزءًا من replay الكانوني أو قدرة S0 على branch/restart replay. M6 يستهلك events/لقطات canonical إلى timeline وfindings فقط.

## ارتباط Gate A

تؤكد أدلة Gate A أن Pulse ينتج حقولًا مستخدمة في S0، منها معدل القلب وMAP وحجم الدم ومعدل/حجم النزف والأكسجة، وأن artifact checkpoint للمحرك يمكن استعادته في المسار المختبر. لذلك يفصل العقد بين **الاسم الدلالي الداخلي** و**اسم عمود Pulse الخارجي** كي لا يتسرب تمثيل CSV إلى بقية النواة.
