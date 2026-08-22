# ملاحظات مصادر: منصة Nexora متعددة اللغات

**الغرض:** أدلة أولية لقرار لغات وحدود خدمات Nexora. لا تقارن هذه الملاحظات throughput بين اللغات ولا تعد بنشر framework/service.

## Laravel/PHP للـControl Plane

| المصدر | الملاحظة التي تدعم القرار | القيد المعماري |
|---|---|---|
| [Laravel Authorization][1] | يقدم Laravel gates وpolicies لتنظيم authorization حول actions/resources، ويفصل authorization عن authentication. | لا يكفي `tenant_id` من client؛ يلزم model membership/role/tenant وسياسات tested. |
| [Laravel Migrations][2] | migrations version-control schema؛ توثق دعم PostgreSQL وخيار `--isolated` لتجنب concurrent migration execution. | migrations لا تسمح بملكية مشتركة للجداول: يملك Laravel فقط `control_plane` schema. |
| [Laravel Queues][3] | يوفر API لطوابير عدة منها SQS وRedis/database، ويشرح priorities/failures/after-commit behavior. | Laravel queue لا يصبح owner للتنسيق الحي، Pulse، أو session worker lifecycle. |
| [Laravel Octane][4] | يمكن تشغيل app workers مقيمين في الذاكرة عبر عدة application servers، مع caveats لحالة request/state ومع عداد/إعادة تشغيل workers. | لا نستنتج منه صلاحية Laravel لمسار physiology الساخن أو WebSocket gateway واسع؛ يبقى control/business API. |

**الاستنتاج:** Laravel مرشح قوي لـbusiness/control-plane CRUD، identity/authorization policy، migrations، workflows وnotifications، إذا بقي stateless خلف replicas ولا يتجاوز logical data ownership. هذا اختيار productivity/domain ownership، لا حكم أن PHP «أبطأ» أو «أسرع» من Go.

## Go للـplatform/realtime

| المصدر | الملاحظة التي تدعم القرار | القيد المعماري |
|---|---|---|
| [Go Context][5] | يعالج Go requests في goroutines؛ يحمل `Context` deadlines/cancellation/request-scoped values عبر API boundaries، وآمن للاستخدام المتزامن. | لا يجعل Go تلقائيًا owner للـmedical simulation truth أو domain business workflows. |
| [Go net/http][6] | package HTTP الرسمي يوضح request/response concurrency في HTTP/2. | لا يمثل benchmark أو سببًا كافيًا لفصل edge service منذ اليوم الأول. |

**الاستنتاج:** Go مرشح لمنسق sessions/lease/fencing، relay، rate-limit coordination، أو realtime gateway عند وجود connection/concurrency/failure evidence. كل مكون يظل module/deployable candidate لا microservice مفروضًا.

## gRPC وProtocol Buffers

| المصدر | الملاحظة التي تدعم القرار | القيد المعماري |
|---|---|---|
| [gRPC supported languages][7] | توثق gRPC دعم C#، C++، Go، PHP، Python وغيرها. | support لا يثبت أن كل external API يجب أن يكون gRPC. |
| [Protocol Buffers overview][8] | Protobuf language/platform-neutral، يولد bindings، ويدعم evolution بإضافة fields وتوافق متعدد اللغات. | ليس مناسبًا للـartifacts الكبيرة أو self-describing legal interchange؛ لا يُخزن Pulse internals آليًا. |
| [Proto best practices][9] | لا تعاد tag numbers ولا تغير field types؛ تحفظ deleted tags؛ تنصح بفصل API messages عن storage messages. | يلزم contract repository، codegen CI، review، compatibility policy قبل adoption. |

**الاستنتاج:** external product API يبقى HTTPS REST/JSON، وrealtime client path مستقبلًا WebSocket عبر Go boundary، وgRPC/Protobuf مرشح internal لـLaravel↔Go وGo↔Python/Go فقط عند قيمة typed contract/streaming واضحة. يظل S0 HTTP/JSON loopback transport ثابتًا لمهمته المحلية؛ لا يستبدل الآن.

## authorization context

تحتاج Laravel إلى إصدار authorization decision/session grant بعد membership/RBAC، ويحتاج Go إلى **تحقق** scoped principal/session context من trusted token أو service identity، لا قبول arbitrary tenant ID من Unity. لا تنفذ هذه الدفعة auth stack أو JWT issuer. أي token design لاحق يتطلب issuer/audience/expiry/key rotation/revocation/authorization tests وthreat model منفصل.

## المراجع

[1]: https://laravel.com/docs/13.x/authorization "Laravel 13.x: Authorization"
[2]: https://laravel.com/docs/13.x/migrations "Laravel 13.x: Database Migrations"
[3]: https://laravel.com/docs/13.x/queues "Laravel 13.x: Queues"
[4]: https://laravel.com/docs/13.x/octane "Laravel 13.x: Octane"
[5]: https://go.dev/blog/context "Go Concurrency Patterns: Context"
[6]: https://pkg.go.dev/net/http "Go standard library: net/http"
[7]: https://grpc.io/docs/languages/ "gRPC: Supported languages"
[8]: https://protobuf.dev/overview/ "Protocol Buffers: Overview"
[9]: https://protobuf.dev/best-practices/dos-donts/ "Protocol Buffers: Best Practices"
