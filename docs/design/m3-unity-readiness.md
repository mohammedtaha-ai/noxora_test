# حزمة جاهزية M3 — عميل Unity الأدنى

**الحالة:** حدود العميل التقنية منفذة headless؛ Unity نفسه **غير منفذ** ولا يملك إذن البدء في هذه الدفعة.
**النطاق المستهدف:** عميل مرئي أدنى يستهلك سطح VPE منظم وآمن للمتعلم لحالة S0 الوحيدة.
**مبدأ السلطة:** VPE Runtime والـhost يملكان الزمن والطابور والأدلة والوصول إلى Pulse؛ لا يصل Unity إلى `VpeRuntime` الداخلي أو `PulseAdapter` أو Pulse SDK.

> تظل التجربة Learning Mode تكوينية فقط. لا تقدم تشخيصًا أو توصية أو قبول/نقل حقيقيًا أو نجاحًا/فشلًا سريريًا أو تقييمًا عالي العواقب.

## 1. حالة شروط الدخول

| شرط الدخول | الحالة الحالية | الدليل أو الإجراء |
|---|---|---|
| Gate A وPulseAdapter | **VERIFIED / INTEGRATION TESTED** | مسار S0 المحلي المثبت الإصدار. |
| نواة Runtime والأدلة والcheckpoints | **IMPLEMENTED + TESTED** | snapshots خفيفة وartifacts منفصلة داخل الجلسة. |
| DTOs وFacade آمنة | **IMPLEMENTED + TESTED** | `VpeClientFacade` و`client_contracts.py` واختبارات منع التسريب. |
| النقل بين العميل وVPE | **IMPLEMENTED HEADLESS** | HTTP/JSON loopback و[ADR-002](../decisions/ADR-002-local-client-facade-transport.md). |
| lifecycle وسياسة الزمن | **IMPLEMENTED + MEASURED** | `VpePacedHost` عند 0.5s، لا catch-up. |
| Gate 0 | **UNTESTED** | [حزمة التشغيل](../gate0/README.md) جاهزة؛ لا توجد جلسات فعلية. |
| مراجعة طبية/تعليمية مستقلة | **UNVALIDATED** | [حزمة المراجعة](../validation/s0-medical-review-packet.md) جاهزة؛ لا رد خارجي. |
| قرار بدء Unity | **OPEN / WAIT_FOR_REVIEW** | لا تبدأ Unity قبل البوابتين وقرار صريح لاحق. |

## 2. حد العميل المنفذ

```text
Unity Client (مستقبلي)
    ↓ HTTP/JSON DTOs محلية فقط
LocalFacadeHttpServer  ← loopback /v1، لا يملك الساعة
    ↓ VpeClientFacade  ← projection + command validation
VpePacedHost           ← process_pending + advance tick فقط
    ↓
VpeRuntime → PhysiologyAdapter → PulseAdapter → Pulse
```

| سطح العميل | ما يتلقاه أو يرسله | ما لا يراه أو يملكه |
|---|---|---|
| `ClientScenarioManifest` | عنوان تعلمي، وضع learning، قوائم أفعال وملاحظات، telemetry مرئية. | pathology، flow rate، Pulse revision، FAST finding، completion. |
| `ClientSnapshot` | وقت VPE وحالة Runtime وHR/MAP/SpO₂ المؤلفة. | blood volume، hemorrhaged volume، engine version، reason، adapter/checkpoint state. |
| `ClientEvent` | نوع دليل وidentifier أو `duration_s` محدود. | actor/source وبيانات Pulse/compound/rate/volume وstack trace. |
| `CommandRequest` | history/hypothesis/observation/escalation/intervention مؤلفة مع `request_id`. | `advance_time` وcheckpoint/restore وpayload حر. |
| `CommandOutcome` | ACCEPTED/PENDING/COMPLETED/REJECTED/AMBIGUOUS وخطأ منظم آمن. | retry ضمني أو تفاصيل داخلية. |

## 3. النقل المحلي المختار

النقل المختار HTTP/JSON محلي على loopback فقط. يطلب كل عميل token قصير العمر في `X-Nexora-Client-Token`، وهو حاجز تطوير محلي وليس مصادقة إنتاجية. لا يوجد cloud أو TLS أو multi-user أو endpoint لتقدم الزمن أو `drain` أو Pulse.

| endpoint | العملية | الاستجابة |
|---|---|---|
| `/v1/scenario` | `GET` | manifest آمن |
| `/v1/state` | `GET` | حالة وزمن VPE |
| `/v1/snapshot` | `GET` | snapshot آمن أو 404 منظم |
| `/v1/events?after=` | `GET` | events مرئية فقط |
| `/v1/commands` | `POST` | command accepted أو outcome منظم |
| `/v1/commands/<request_id>` | `GET` | outcome أو pending منظم |

تم اختيار HTTP/JSON على IPC مخصص لأن Unity توثق `UnityWebRequest` لطلبات HTTP/الردود، بينما يتطلب IPC framing وعقد توافق مخصصين. [1] [2]

## 4. lifecycle وسياسة tick

يعالج host طابور الأفعال ثم يضيف تقدم زمن داخليًا. العميل لا يملك ساعة محاكاة، ولا يرسم catch-up عند stall. إذا فشل host أو المحرك، ينتقل Runtime إلى `PAUSED_BY_SYSTEM`; لا يتقدم الزمن حتى استئناف صريح، ولا يحول الفرق الجداري إلى زمن سريري.

**السياسة المقاسة:** 1× عند `0.5s` simulation tick. جرب benchmark Pulse الحقيقي 0.1 و0.25 و0.5 و1 و2 ثانية. أعطى 0.25 تقدمًا متناوبًا 0.24/0.26 ثانية، لذا لا يستخدم كافتراضي؛ تطابق 0.5 الثانية مع الزيادة المطلوبة في العينات. تظل هذه نتيجة sandbox/headless محلية وليست SLA أو قياس Unity. [3]

## 5. قاموس تفاعلات M3

| عنصر الواجهة المستقبلي | أمر Facade المسموح | النتيجة المرئية | حالة المحتوى |
|---|---|---|---|
| نية تاريخ | `record_history_intent` | `clinical.intent.recorded` | مؤلف ومختبر |
| فرضية سريرية | `record_clinical_hypothesis` | `clinical.hypothesis.recorded` | دليل تكويني لا تشخيص آلي |
| VITALS | `request_observation` | `observation.requested` + snapshot | قدرة مدمجة ومقيدة |
| FAST | `request_observation` | `observation.requested` فقط | طلب منظم؛ لا FAST spatial/resolver في M3 |
| تدخل مقيد | `apply_intervention` | `intervention.applied` + snapshot | Saline/PackedRBC بمعرف فقط، لا جرعة/compound حر |
| تصعيد | `record_escalation` | `escalation.recorded` | دليل غير فيزيولوجي فقط |
| clock | لا أمر عميل | state/snapshot من VPE | host فقط عند 0.5s |

## 6. الفجوات المغلقة والمفتوحة

| الفجوة السابقة | الحالة | الملاحظة |
|---|---|---|
| Facade وDTOs | **CLOSED FOR HEADLESS** | لا تسرب للحقائق المخفية في المسارات المختبرة. |
| نقل محلي وعقد أخطاء | **CLOSED FOR HEADLESS** | loopback HTTP/JSON قابل للاستبدال. |
| lifecycle وstop semantics | **CLOSED FOR HEADLESS** | host paced و`PAUSED_BY_SYSTEM` بلا catch-up. |
| قائمة observations | **CLOSED FOR S0** | `VITALS` مدمج، FAST مؤلف، CBC غير معروض. |
| مدد تقدم الزمن | **CLOSED FOR S0 HOST** | 0.5s سياسة host؛ ليست زر تقدم زمن للمتعلم. |
| Unity shell / play-mode | **OPEN / NOT IMPLEMENTED** | لا ينفذ قبل قرار البدء. |
| Gate 0 | **OPEN / UNTESTED** | يحتاج جلسات فعلية وفق البروتوكول. |
| مراجعة المحتوى | **OPEN / UNVALIDATED** | يحتاج ردًا مستقلًا موثقًا. |
| cross-session recovery | **OPEN / OUT_OF_SCOPE** | لا retry أعمى أو exactly-once خارج الجلسة. |

## 7. قرار GO-M3 اللاحق

يمكن اعتبار الجاهزية التقنية للـscaffold **READY** فقط، لكن لا يوجد GO شامل. قبل إنشاء مشروع Unity يجب تسجيل: (1) قرار Gate 0 PASS/PIVOT/INCONCLUSIVE، (2) قرار مراجعة محتوى ACCEPT/REWORK/OUT_OF_SCOPE، (3) اعتماد النسخة المعروضة من الأفعال والنصوص، (4) تأكيد Learning Mode بلا high-stakes assessment، و(5) خطة اختبار Unity على المنصة المستهدفة. إذا بقي Gate 0 أو المراجعة غير مكتملين، يظل Unity متوقفًا.

## المراجع

[1]: https://docs.unity3d.com/6000.5/Documentation/Manual/web-request.html "Unity Manual: Interacting with web servers"
[2]: https://learn.microsoft.com/en-us/dotnet/standard/io/how-to-use-named-pipes-for-network-interprocess-communication "Microsoft Learn: Named pipes"
[3]: ../../artifacts/benchmarks/pre_unity_client_boundary_tick_policy/pulse_tick_summary.json "ملخص benchmark سياسة tick"
