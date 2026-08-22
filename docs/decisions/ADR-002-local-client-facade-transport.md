# ADR-002: نقل محلي لواجهة عميل VPE

**الحالة:** Accepted for the headless pre-Unity boundary.
**التاريخ:** 2026-08-22.

## السياق

يحتاج عميل Unity مستقبلي إلى استعلام manifest وحالة ولقطات وأحداث آمنة للمتعلم، وإرسال أفعال منظمة واستعلام outcome. لا يجوز له الوصول إلى `VpeRuntime` أو `PulseAdapter` أو SDK أو ملفات checkpoint. يجب أن يبقى النقل محليًا، صغيرًا، قابلًا للاختبار، وقابلًا للاستبدال؛ وليس منصة خدمة أو نشرًا سحابيًا.

## البدائل المقارنة

| المعيار | HTTP/JSON على loopback | Named pipes / IPC مخصص |
|---|---|---|
| بساطة Unity/C# | `UnityWebRequest` موثق رسميًا لطلبات HTTP والردود. [1] | يحتاج عميل pipe وframing وإدارة قراءة/كتابة خاصة. |
| الاختبار headless | يمكن اختبار الطلب/الرد عبر `urllib` القياسي. | يحتاج عميل IPC وfixture بروتوكوليًا مخصصًا. |
| أخطاء منظمة | status code + JSON DTO واضحان. | يلزم تعريف framing وerror envelope من الصفر. |
| lifecycle | loopback server قابل للبدء/الإيقاف وport محدد. | أسماء pipes وcleanup تختلف باختلاف المنصة. |
| cross-platform | HTTP/JSON محايد للعملية والمنصة. | .NET على Linux ينفذ named pipes فوق Unix Domain Sockets. [2] |
| dependency cost | Python stdlib في spike؛ Unity لديه دعم رسمي. | stdlib ممكن، لكن كلفة العقد والتوافق أعلى. |
| replaceability | يمكن استبداله لاحقًا مع بقاء DTOs وFacade. | البروتوكول يربط العميل والنظام المحلي أكثر. |

## القرار

يُختار **HTTP/JSON محلي على loopback فقط** للنقل الضيق في هذه المرحلة.

* ينشئ `LocalFacadeHttpServer` خادمًا محليًا على `127.0.0.1` فقط.
* يستخدم URI النسخة `/v1/` وJSON DTOs المعرفة في `client_contracts.py`.
* يقرأ النقل من `VpeClientFacade` ويستدعي فقط `facade.submit()` للأفعال المسموحة. لا يملك endpoint لتقدم الزمن أو checkpoint أو Pulse.
* يطبق الخادم token محليًا قصير العمر في header `X-Nexora-Client-Token` كحاجز تطويري ضد عمليات محلية عارضة. لا يمثل ذلك نظام مصادقة أو صلاحيات إنتاجية.
* تبقى معالجة queue والتقدم الزمني في VPE Host. لا يستدعي HTTP `runtime.drain()` ولا يملك Unity ساعة المحاكاة.

## المسارات المختارة

| المسار | العملية | DTO أو الاستجابة |
|---|---|---|
| `/v1/scenario` | `GET` | `ClientScenarioManifest` |
| `/v1/state` | `GET` | `ClientRuntimeState` |
| `/v1/snapshot` | `GET` | `ClientSnapshot` أو `404` آمن |
| `/v1/events?after=<event_id>` | `GET` | قائمة `ClientEvent` |
| `/v1/commands` | `POST` | `CommandAccepted` أو `CommandOutcome` |
| `/v1/commands/<request_id>` | `GET` | `CommandOutcome` |

## العواقب والحدود

لا يثبت هذا القرار أن Unity يعمل أو أن HTTP هو النقل النهائي للإصدار المنتج. لا يوجد TLS أو شبكة أو cloud أو authentication متعدد المستخدمين. يجب ألا يربط عميل Unity مستقبلي network callback بخيط الرسم بطريقة حاجبة؛ يحصل على الحالة والنتائج بصورة async، بينما يتم تقدم الزمن من host paced loop.

## المراجع

[1]: https://docs.unity3d.com/6000.5/Documentation/Manual/web-request.html "Unity Manual: Interacting with web servers"
[2]: https://learn.microsoft.com/en-us/dotnet/standard/io/how-to-use-named-pipes-for-network-interprocess-communication "Microsoft Learn: Named pipes"
