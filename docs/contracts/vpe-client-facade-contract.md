# عقد VPE Client Facade — S0 headless قبل Unity

**الحالة:** `IMPLEMENTED_HEADLESS / CLIENT-SAFE TESTED`. لا يعني ذلك أن عميل Unity منفذ أو معتمد.

> الغرض من العقد إبقاء VPE والـhost المالكين الوحيدين للزمن والطابور والوصول إلى Pulse. هو عقد محاكاة تكوينية فقط، وليس بروتوكول علاج أو نظام قرار أو تقييم عالي العواقب.

## حدود الواجهة

يتصل أي عميل مستقبلي بـ`VpeClientFacade` عبر `LocalFacadeHttpServer` على loopback فقط. لا يصل إلى `VpeRuntime` الداخلي أو `PulseAdapter` أو Pulse SDK أو ملفات checkpoint. لا يعيد Facade snapshot الداخلي أو سيناريو المصدر بالكامل؛ بل ينشئ DTOs صريحة في `client_contracts.py`.

| DTO | الحقول المسموح بها | محظورات صريحة |
|---|---|---|
| `ClientScenarioManifest` | scenario id، عنوان تعليمي، mode، القوائم المسموحة، telemetry المرئية. | pathology، flow rate، Pulse revision، controlled FAST finding، completion. |
| `ClientRuntimeState` | runtime state وsimulation time. | adapter/Pulse state. |
| `ClientSnapshot` | snapshot id، scenario id، simulation time، runtime state، HR/MAP/SpO₂. | blood volume، hemorrhaged volume، engine version، reason، checkpoint. |
| `ClientEvent` | event id/type/time وpayload محدود لكل event type. | actor، source، command metadata الداخلي، compound/volume/rate. |
| `CommandRequest` | kind/payload/request_id مؤلفة ومتحقق منها. | advance/checkpoint/restore أو payload حر. |

## العمليات

| العملية | المسار المحلي | سلطة العميل | سلطة VPE/Host |
|---|---|---|---|
| عرض السيناريو | `GET /v1/scenario` | العرض فقط | إسقاط manifest آمن. |
| عرض الحالة/اللقطة | `GET /v1/state`, `GET /v1/snapshot` | العرض فقط | نشر حالة VPE وsnapshot آمنين. |
| قراءة أدلة جديدة | `GET /v1/events?after=` | cursor مرئي فقط | فلترة events والـpayloads. |
| إرسال فعل | `POST /v1/commands` | اختيار مؤلف فقط | التحقق، ترتيب الطابور، outcome. |
| استعلام النتيجة | `GET /v1/commands/<request_id>` | قراءة نتيجة موجودة | PENDING/COMPLETED/REJECTED/AMBIGUOUS. |
| تقدم الزمن | **لا endpoint** | لا يملك العميل clock. | `VpePacedHost` يعالج ثم يتقدم عند 0.5s. |

## request_id وحماية التكرار

يجب أن يحمل كل فعل عميل `request_id` آمنًا وثابتًا. يعمل الفهرس داخل جلسة Runtime في الذاكرة فقط.

| الحالة | السلوك | واجب العميل |
|---|---|---|
| request جديد صالح | يقبل Facade الطلب ويرجع `command_id` و`ACCEPTED`. | يعرض انتظارًا ثم يستعلم عن outcome. |
| إعادة إرسال متطابقة | يعاد المعرف/النتيجة ولا ينفذ الأثر مجددًا. | لا ينشئ نية ثانية. |
| request_id مع دلالات مختلفة | يرفض بـ`DUPLICATE_REQUEST_CONFLICT`. | يستخدم معرفًا جديدًا لنية جديدة. |
| فشل بعد القبول | outcome `AMBIGUOUS` إن أمكن أن يكون أثر وقع. | لا retry تلقائي؛ يعرض تعافيًا يدويًا/حالة لاحقة. |

لا يثبت العقد exactly-once عبر النقل أو توقف العملية أو جلسة جديدة. هذه حدود S0 مقصودة.

## الأخطاء والحماية

الأخطاء تعاد كـJSON برموز: `INVALID_COMMAND`، `NOT_ALLOWED`، `INVALID_STATE`، `DUPLICATE_REQUEST_CONFLICT`، `AMBIGUOUS_OUTCOME`، `ENGINE_UNAVAILABLE`، `ENGINE_TIMEOUT`، أو `INTERNAL_ERROR`. لا تعاد stack trace أو مسارات محلية أو سطور Pulse أو state digest.

يرتبط النقل بـloopback وtoken محلي قصير العمر. لا يشكل token نظام هوية أو مصادقة إنتاجية أو TLS أو تحكم وصول متعدد المستخدمين.

## lifecycle

يشغل host Facade والنقل ويعالج الأفعال ثم يتقدم clock. إذا تعذر tick ينتقل Runtime إلى `PAUSED_BY_SYSTEM`; لا يتحرك الزمن ولا يطبق catch-up عند الاستئناف. tick المقاس المختار هو 0.5 ثانية في البيئة headless المحلية؛ لا يعمم على Unity أو منصات أخرى.

## الحالة قبل Unity

اختبارات Facade والنقل والـhost تغطي منع تسريب الحقيقة، الأخطاء المنظمة، التكرار، loopback، عدم وجود clock endpoint، الإيقاف النظامي، وعدم catch-up. يبقى Unity play-mode وGate 0 والمراجعة الطبية/التعليمية خارج حالة التنفيذ. لا يبدأ Unity من هذا العقد وحده.
