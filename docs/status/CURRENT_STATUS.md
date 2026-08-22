# الحالة الحالية

## المرحلة الحالية

**المرحلة:** اكتملت Gate A ونواة S0 headless وPulseAdapter الإنتاجي، ثم تقوية Runtime وحدود العميل قبل Unity. لا يوجد مشروع Unity في هذه الدفعة.
**الفرع العامل:** `manus/s0-foundation`.

> النجاح الهندسي المحلي لا يثبت صحة سريرية أو فعالية تعليمية أو صلاحية تقييم عالي العواقب.

## الأحكام المنفصلة الحالية

| البعد | الحكم | التفسير الدقيق |
|---|---|---|
| **TECHNICAL M3 READINESS** | **READY** لبدء scaffold Unity محدود ومراجع فقط | Facade وDTOs آمنة، نقل loopback، host paced، tests وbenchmark موجودة. لا يعني أن Unity منفذ أو مُثبت على منصات مستهدفة. |
| **GATE 0** | **UNTESTED** | توجد حزمة تشغيل وقوالب، ولا توجد جلسات أو مشاركون أو مذكرة قرار مكتملة. |
| **MEDICAL REVIEW** | **UNVALIDATED** | توجد حزمة مراجعة مستقلة، ولا يوجد رد أو توقيع خارجي موثق. |

لا تتحد هذه الأحكام إلى PASS واحد. لا يبدأ Unity قبل مراجعة Gate 0 والمحتوى ثم قرار صريح لاحق.

## تم التحقق منه

| البند | الحالة | الدليل |
|---|---|---|
| Pulse 4.3.2 عند revision `e8a3649…` شُغل محليًا لمسارات S0 المحددة. | **VERIFIED** | [Gate A](../reports/002-pulse-gate-a.md) ومصفوفة ما بعد Gate A. |
| Canonical snapshots خفيفة؛ checkpoint صريح فقط ينشئ artifact محرك داخل الجلسة. | **VERIFIED** للمسارات المختبرة | [مراجعة Runtime](../reports/005-pre-m3-runtime-hardening-review.md). |
| فشل الطابور يحتفظ بالأوامر اللاحقة؛ يتحقق Runtime قبل أثر Pulse؛ `request_id` يمنع التكرار داخل الجلسة. | **VERIFIED** للمسارات المختبرة | اختبارات Runtime وPulse. |
| عقد سيناريو 1.2 يرفض الحقول/الأنواع/التكرارات غير المدعومة ويقيد telemetry المرئية للمتعلم. | **VERIFIED** | `s0-scenario.schema.json` واختبارات contract. |
| Facade لا يعيد الحقيقة الداخلية أو checkpoint أو telemetry الخفية، ويعرض manifest/snapshot/event/command DTOs صريحة. | **VERIFIED** | [تقرير 006](../reports/006-pre-unity-client-boundary-review.md) واختبارات Facade. |
| النقل HTTP/JSON محلي على loopback فقط ولا يملك endpoint للساعة أو Pulse. | **VERIFIED** headless | [ADR-002](../decisions/ADR-002-local-client-facade-transport.md). |
| VPE Host يملك تقدم الزمن؛ `PAUSED_BY_SYSTEM` لا يتقدم؛ لا catch-up بعد overrun. | **VERIFIED** للوحدة ومسار Pulse المحدد | [تقرير 006](../reports/006-pre-unity-client-boundary-review.md). |
| tick `0.5s` يطابق تقدم Pulse المقاس؛ `0.25s` يتبدل بين 0.24/0.26s في البيئة المقاسة. | **OBSERVED** محليًا | [ملخص benchmark](../../artifacts/benchmarks/pre_unity_client_boundary_tick_policy/pulse_tick_summary.json). |
| الحزمة الكاملة شغلت مع Pulse الحقيقي. | **VERIFIED** | **43 اختبارًا نجح في 25.540s**، منها **8** تكاملات Pulse SDK فعلية. |

## قيود ومخاطر مفتوحة

| البند | الحالة | الأثر/المعالجة |
|---|---|---|
| Unity وFAST spatial resolver | **NOT IMPLEMENTED / DEFERRED** | لا يبدأان في هذه الدفعة. |
| Gate 0 | **UNTESTED** | استخدم [حزمة Gate 0](../gate0/README.md) وفق اعتماد المؤسسة ثم وثق PASS/PIVOT/INCONCLUSIVE. |
| مراجعة المحتوى الطبية/التعليمية | **UNVALIDATED** | أرسل [حزمة المراجعة](../validation/s0-medical-review-packet.md) لمراجع مستقل وسجل القرار. |
| frame/render/network cost | **UNMEASURED** | benchmark headless لا يثبت FPS أو UnityWebRequest أو نظامًا مستهدفًا. |
| checkpoint أو idempotency عبر جلسات/عمليات | **PARTIAL / ABSENT BY DESIGN** | يمنع retry الأعمى؛ يتطلب تصميمًا منفصلًا عند تغير النطاق. |
| صلاحية سريرية أو تقييم عالي العواقب | **PROHIBITED في S0** | Learning Mode تكويني فقط. |

## القرارات السارية

1. يثبت revision Pulse؛ أي تحديث يحتاج إعادة دليل Gate A والمسار الإنتاجي.
2. VPE يملك الزمن وترتيب الأوامر والوصول إلى Pulse؛ Unity المستقبلي لا يصل إلى Pulse أو `PulseAdapter` مباشرة.
3. client projection لا يعيد snapshot داخليًا أو checkpoint أو hidden telemetry/pathology.
4. النقل المحلي المختار HTTP/JSON loopback؛ DTOs وFacade يبقيان قابلين للاستبدال.
5. `request_id` يحمي داخل جلسة Runtime فقط؛ لا retry أعمى بعد نتيجة غامضة.
6. سياسة host المختارة 1× عند 0.5 ثانية، من دون catch-up؛ لا تدعي أنها عامة خارج البيئة المقاسة.
7. لا يبدأ Unity حتى Gate 0 والمراجعة الطبية/التعليمية وقرار بدء مستقل.

## أحدث الأدلة

- [تقرير حدود العميل قبل Unity](../reports/006-pre-unity-client-boundary-review.md).
- [ADR-002 النقل المحلي](../decisions/ADR-002-local-client-facade-transport.md) و[ملاحظات مصادر النقل](../research/transport-spike-source-notes.md).
- [عقد Facade](../contracts/vpe-client-facade-contract.md) و[حزمة جاهزية M3](../design/m3-unity-readiness.md).
- [benchmark tick](../../artifacts/benchmarks/pre_unity_client_boundary_tick_policy/pulse_tick_summary.json) و[عيناته](../../artifacts/benchmarks/pre_unity_client_boundary_tick_policy/pulse_tick_samples.csv).
- [حزمة Gate 0](../gate0/README.md) و[حزمة المراجعة الطبية](../validation/s0-medical-review-packet.md).

## الخطوة التالية المخططة

تتوقف الدفعة قبل Unity. نفذ Gate 0، واطلب مراجعة مستقلة للمحتوى الطبي/التعليمي، ثم سجل قرارًا يفتح scaffold Unity المحدود أو يطلب REWORK. لا تبدأ Unity في نفس الدفعة.
