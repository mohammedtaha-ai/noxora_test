# جرد تفاعلات S0

## التفاعلات المعتمدة للنواة الرأسية

| المعرف | فئة التفاعل | المدخل الموثوق | أثر النواة | الدليل المنشور | الحالة |
|---|---|---|---|---|---|
| `history.intent` | تاريخ منظم | معرف نية من `history.allowed_intents` | لا يغير Pulse | `clinical.intent.recorded` | قابل للتنفيذ headless |
| `clinical.hypothesis` | فرضية منظمة | معرف من `clinical_hypotheses.allowed` | لا يغير Pulse أو الزمن | `clinical.hypothesis.recorded` | قابل للتنفيذ headless |
| `observation.request` | طلب ملاحظة | `VITALS` المدمج أو معرف من `observations.allowed` | لا يغير Pulse مباشرة | `observation.requested` | قابل للتنفيذ headless |
| `advance.time` | تقدم الزمن | مدة موجبة محدودة | يدفع ساعة VPE ثم adapter | `clock.advanced` + `snapshot.published` | قابل للتنفيذ headless |
| `intervention.apply` | تدخل من قاموس محدود | معرف تدخل وparameters مصادق عليها | يضع أمر adapter مرتبًا | `intervention.applied` + لقطة | قابل للتنفيذ بعقد adapter |
| `checkpoint.create` | نقطة استعادة | اسم checkpoint مصادق عليه | ينشئ artifact محرك منفصل؛ لا تحفظ اللقطة العادية المحرك | `checkpoint.created` + لقطة خفيفة | قابل للتنفيذ داخل الجلسة بعقد adapter |
| `fast.acquire` | FAST spatial | نتيجة resolver مستقبلية | لا يغير Pulse | `fast.acquisition.recorded` | مؤجل إلى M4 |
| `escalation.record` | تصعيد منظم | معرف مصرح به في `escalations.allowed` | لا يغير Pulse أو زمن VPE | `escalation.recorded` | قابل للتنفيذ headless |

## قاموس التاريخ الأولي

`PAIN_ONSET`, `PAIN_LOCATION`, `PAIN_RADIATION`, `PAIN_SEVERITY`, `ASSOCIATED_SYMPTOMS`, `MECHANISM_OF_INJURY`, `MEDICATIONS`, `ALLERGIES`, `PAST_MEDICAL_HISTORY`، و`ANTICOAGULANT_USE` هي قيم منظمة مقترحة لسؤال أو محاولة استجلاء معلومة من المريض. لا تقبل النواة نصًا حرًا كقيمة معتمدة.

`INTERNAL_BLEEDING` فرضية سريرية منظمة مستقلة تسجل عبر `record_clinical_hypothesis`، وليست نية تاريخ. هذا التسجيل دليل تكويني على اختيار المتعلم داخل السيناريو فقط، ولا يمثل تشخيصًا أو حكمًا سريريًا واقعيًا.

## التفاعلات المؤجلة صراحة

لا تنفذ هذه المرحلة إنشاء إصابة، جراحة، قطع نسيج، خياطة، haptics، استكشاف تشريحي حر، إجراءات IV مكانية، تصوير فيزيائي حر، أو محادثة LLM. لا توجد طبقة Unity عاملة في هذا المستودع بعد؛ يظل FAST spatial مؤجلًا إلى M4، بينما يبقى أي عميل مستقبلي مستهلكًا لأوامر VPE فقط.
