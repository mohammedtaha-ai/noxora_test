# جرد تفاعلات S0

## التفاعلات المعتمدة للنواة الرأسية

| المعرف | فئة التفاعل | المدخل الموثوق | أثر النواة | الدليل المنشور | الحالة |
|---|---|---|---|---|---|
| `history.intent` | تاريخ منظم | معرف نية من القائمة | لا يغير Pulse | `clinical.intent.recorded` | قابل للتنفيذ headless |
| `observation.request` | طلب ملاحظة | معرف ملاحظة معتمد | لا يغير Pulse مباشرة | `observation.requested` | قابل للتنفيذ headless |
| `advance.time` | تقدم الزمن | مدة موجبة محدودة | يدفع ساعة VPE ثم adapter | `clock.advanced` + `snapshot.published` | قابل للتنفيذ headless |
| `intervention.apply` | تدخل من قاموس محدود | معرف تدخل وparameters مصادق عليها | يضع أمر adapter مرتبًا | `intervention.applied` + لقطة | قابل للتنفيذ بعقد adapter |
| `checkpoint.create` | نقطة استعادة | اسم checkpoint مصادق عليه | يطلب حفظ adapter | `checkpoint.created` + لقطة | قابل للتنفيذ بعقد adapter |
| `fast.acquire` | FAST spatial | نتيجة resolver مستقبلية | لا يغير Pulse | `fast.acquisition.recorded` | مؤجل إلى M4 |
| `escalation.record` | تصعيد منظم | معرف تصعيد محدود | لا يغير Pulse | `escalation.recorded` | مؤجل عن مسار المحرك الأول |

## قاموس التاريخ الأولي

`PAIN_ONSET`, `PAIN_LOCATION`, `PAIN_RADIATION`, `PAIN_SEVERITY`, `ASSOCIATED_SYMPTOMS`, `MECHANISM_OF_INJURY`, `MEDICATIONS`, `ALLERGIES`, `PAST_MEDICAL_HISTORY`, `ANTICOAGULANT_USE`, و`SUSPECT_INTERNAL_BLEEDING` هي قيم منظمة مقترحة. لا تقبل النواة نصًا حرًا كقيمة معتمدة.

## التفاعلات المؤجلة صراحة

لا تنفذ هذه المرحلة إنشاء إصابة، جراحة، قطع نسيج، خياطة، haptics، استكشاف تشريحي حر، إجراءات IV مكانية، تصوير فيزيائي حر، أو محادثة LLM. لا توجد طبقة Unity عاملة في هذا المستودع بعد؛ سيبقى أي عميل مستقبلي مستهلكًا لأوامر VPE فقط.
