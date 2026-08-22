# ADR-003: حدود الخدمة وملكية اللغات

**الحالة:** Accepted for the scale-ready target.  
**التاريخ:** 2026-08-23.

## السياق

تملك Nexora نواة S0 Python تعمل مع Pulse C++17 عبر `PulseAdapter`، وحدًا client-safe محليًا headless. يلزم مسار نمو إلى منصة متعددة المستأجرين من دون إعادة كتابة VPE أو إدخال microservices/Kubernetes مبكرًا أو بدء Unity في هذه الدفعة.

## القرار

تبقى **Python** مالكة VPE وfacade والمنطق المنسق وabstractions المنصة الحالية. يبقى **C++17/Pulse** مالك engine الفيزيولوجي داخل process/session owner. تكون **C#/Unity** مستقبلية ومستهلكة لـclient-safe contracts فقط، ولا تدخل في هذه الدفعة. تُقيَّم **Go** لاحقًا لخدمات محددة كثيفة الاتصال أو relay/worker إذا برهنت benchmark/operations أن Python لا يلبيان boundary المطلوب؛ لا تُعاد كتابة core لأجل توحيد اللغة.

| boundary | اللغة/التقنية الآن | سبب الملكية | ممنوع |
|---|---|---|---|
| simulation time, action queue, Pulse adapter | Python VPE + C++ Pulse | S0 مثبت واختبارات integration حقيقية | rewrite أو multi-owner Pulse. |
| client view/commands | Python facade/DTO | isolation من internals قائم | Unity direct runtime/Pulse. |
| Control Plane service future | Python أولًا إذا scope مناسب | reuse contracts/domain knowledge | FastAPI/Pydantic service في الدفعة. |
| worker/relay future | Python أو Go بعد evidence | workload-specific decision | language-based microservice split. |
| learner client | C#/Unity future | client rendering/input | clock/clinical truth/safety ownership. |

## البدائل المرفوضة

| البديل | سبب الرفض الآن |
|---|---|
| إعادة كتابة Python VPE بـGo أو C# | تهدد S0 المعتمد ولا تحل capacity problem مثبتًا. |
| تحويل كل module إلى microservice | تضيف network/distributed failure قبل ownership/SLO. |
| Go كخيار افتراضي للbackend | لا توجد benchmark أو profile يبرر migration. |
| Unity الآن | Gate 0 غير منفذ وMedical Review غير validated؛ والدفعة تحظره. |
| giant process كهدف نهائي | يخلط Control Plane وSimulation state وanalytics failures. |

## العواقب

يجب أن تكون boundaries contract-first، مع process/service split فقط حين يملك المكون lifecycle أو failure domain أو scale profile مختلفًا (`PLAT-BOUNDARY-01`). يبدأ نشر services مستقبلًا بعملية بسيطة/managed compute مثل ECS/Fargate في AWS mapping؛ لا يكون EKS قرارًا افتراضيًا، بل يحتاج `PLAT-K8S-04` evidence.

لا يغير هذا القرار Python runtime الحالي أو يدعي أن Python/Pulse أثبتا سعة production. إنه يحدد ملكية وتوقيت التغيير فقط.

## المراجع

[1]: ../architecture/platform-scale-target-v0.1.md "Nexora Platform Scale Target"
[2]: ../architecture/simulation-session-scaling-v0.1.md "Nexora Simulation Session Scaling"
[3]: ../reports/006-pre-unity-client-boundary-review.md "Nexora: Pre-Unity Client Boundary Review"
