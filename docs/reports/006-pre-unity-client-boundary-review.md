# 006 — مراجعة حدود العميل قبل Unity

**التاريخ:** 2026-08-22.
**النطاق:** حزمة ما قبل M3 التي تنفذ حدود عميل آمنة، نقلًا محليًا ضيقًا، ومضيف VPE مالكًا للزمن. لا تتضمن هذه الدفعة مشروع Unity أو FAST مكانيًا أو LLM/debrief أو تقييمًا عالي العواقب.

> يثبت هذا التقرير سلوكًا هندسيًا محليًا للمسارات المختبرة. لا يثبت دقة سريرية، فعالية تعليمية، صلاحية تقييم، أو جاهزية استخدام مع مرضى حقيقيين.

## الحكم التنفيذي المنفصل

| البعد | الحكم | الأساس | ما لا يعنيه الحكم |
|---|---|---|---|
| **TECHNICAL M3 READINESS** | **READY** لبدء scaffold Unity محدود ومراجع فقط | DTOs آمنة، Facade، نقل loopback، host paced، tests وbenchmark موثقة. | لا يعني أن Unity منفذ أو أن المستخدمين/المحتوى وافقوا. |
| **GATE 0** | **UNTESTED** | الحزمة التشغيلية وقوالب القرار جاهزة، ولا توجد جلسات أو مشاركون فعليون. | لا يعني PASS أو PIVOT. |
| **MEDICAL REVIEW** | **UNVALIDATED** | حزمة مراجعة مستقلة جاهزة، ولا توجد مراجعة أو توقيع خارجي موثق. | لا يعني ACCEPTED أو REWORK. |

لا تتحول هذه الأحكام الثلاثة إلى PASS موحد. ووفق قرار إيقاف الدفعة، **لا يبدأ Unity قبل مراجعة Gate 0 والمراجعة الطبية/التعليمية وقرار صريح لاحق**.

## تصميم إسقاط العميل

`VpeClientFacade` هو السطح headless الوحيد للعميل. لا يعيد `VpeRuntime` أو `Snapshot` الداخلي أو `CheckpointArtifact` أو `PulseAdapter` أو مسار حالة Pulse. الأنواع العامة مستقلة في `client_contracts.py`، وتشمل `ClientScenarioManifest` و`ClientRuntimeState` و`ClientSnapshot` و`ClientEvent` وطلبات/نتائج الأوامر.

| سطح العميل | البيانات المسموح بها | البيانات المحجوبة عمدًا |
|---|---|---|
| Manifest | المعرّف والعنوان التعليمي وLearning Mode وقوائم الأفعال/الملاحظات والـtelemetry المرئية. | pathology، flow rate، Pulse revision، controlled FAST finding، completion، تفاصيل intervention الفيزيولوجية. |
| Snapshot | `snapshot_id` ووقت المحاكاة وحالة Runtime وHR/MAP/SpO₂ المؤلفة فقط. | blood volume، hemorrhaged volume، engine version، سبب النشر، adapter state، checkpoint. |
| Event | نوع الدليل وpayload مقتصر على identifier أو `duration_s` حسب النوع. | actor، source، `command_id` داخل الحدث، compound/rate/volume، رسائل محرك. |
| Command | تاريخ/فرضية/observation/escalation/intervention مؤلفة فقط مع `request_id`. | advance_time، checkpoint، restore، وأي payload حر. |

اختبارات التسريب تثبت أن snapshot الداخلي لا يعاد استخدامه، وأن `blood_volume_ml` و`total_hemorrhaged_volume_ml` والـpathology والـFAST finding والـPulse metadata لا تصل إلى manifest أو snapshot أو event العميل. [1]

## النقل المختار وADR

اختير **HTTP/JSON محلي على loopback فقط**. يربط `LocalFacadeHttpServer` بـ`127.0.0.1` أو loopback فقط، ويستخدم token محليًا قصير العمر في `X-Nexora-Client-Token`، ويعرض `/v1/scenario` و`/v1/state` و`/v1/snapshot` و`/v1/events` ومسارات الأوامر المنظمة. لا يوجد endpoint لتقدم الزمن أو drain أو Pulse.

| البديل | القرار | السبب المختصر |
|---|---|---|
| HTTP/JSON loopback | **SELECTED** | Unity توثق `UnityWebRequest` لطلبات HTTP والردود، ويسهل اختبار JSON/الخطأ المنظم محليًا. [2] |
| Named pipes / IPC مخصص | **NOT_SELECTED** لهذه الدفعة | ممكن، لكنه يضيف framing وعقد توافق خاصًا؛ وتوثق .NET أن تطبيقه على Linux يستخدم Unix Domain Sockets. [3] |

لا يمثل token مصادقة إنتاجية، ولا يمثل HTTP اختيار نشر cloud أو TLS. ينحصر القرار في spike محلي قابل للاستبدال مع بقاء DTOs وFacade مستقلين.

## lifecycle وسياسة الزمن

`VpePacedHost` يملك تقدم الزمن وحده. يسجل العميل فعلًا في Facade، وينفذ host `process_pending()` ثم يضيف `ADVANCE_TIME` داخليًا ويستنزف الطابور. عند خطأ host/engine ينتقل Runtime إلى `PAUSED_BY_SYSTEM` ولا يتقدم الزمن؛ الاستئناف صريح ولا يحول الفجوة الجدارية إلى catch-up سريري. لا يمكن للعميل إرسال `advance_time`.

**سياسة S0 المختارة:** `tick_simulation_s = 0.5` عند pacing 1×. حُجبت زيادة `0.25` كاختيار افتراضي لأن القياس على Pulse الفعلي أعطى تقدمًا متناوبًا `0.24/0.26` ثانية، بينما طابقت زيادات `0.5` و`1.0` و`2.0` الزمن المطلوب في كل عينات القياس. لا يدعي ذلك تحديدًا عامًا لدقة Pulse خارج البيئة والمسار المقاسين.

## benchmark الفعلي

شغل `scripts/benchmark_pulse_tick_policy.py` على Pulse المثبت محليًا (`4.3.2`، revision `e8a3649…`) لثلاث تكرارات وخمس ticks لكل قيمة. قياس النوم معطل داخل benchmark؛ لذلك sleep budget هو حساب pacing 1× وليس قياسًا لجدولة Unity أو OS. [4] [5]

| Tick مطلوب | عينات | وسيط العمل النشط (ms) | P95 العمل النشط (ms) | وسيط إسقاط snapshot (ms) | وسيط sleep budget (ms) | تقدم Pulse المرصود |
|---:|---:|---:|---:|---:|---:|---|
| 0.10s | 15 | 3.927 | 5.837 | 0.004 | 96.140 | 0.10s |
| 0.25s | 15 | 9.659 | 10.116 | 0.003 | 240.408 | **VARIES** (`0.24/0.26s`) |
| 0.50s | 15 | 17.835 | 19.612 | 0.004 | 482.228 | 0.50s |
| 1.00s | 15 | 35.209 | 37.220 | 0.004 | 964.862 | 1.00s |
| 2.00s | 15 | 69.213 | 73.066 | 0.006 | 1930.869 | 2.00s |

لا سجل overrun في العينات المقاسة، لكن الاختبارات تحققت من سياسة عدم catch-up باصطناع overrun. هذه أرقام sandbox محلية، وليست SLA ولا قياس FPS أو rendering أو transport Unity.

## الأخطاء والتكرار

يرجع Facade والنقل أخطاء JSON منظمة برموز محددة (`INVALID_COMMAND`، `NOT_ALLOWED`، `INVALID_STATE`، `DUPLICATE_REQUEST_CONFLICT`، `AMBIGUOUS_OUTCOME`، وغيرها). لا يعيدوا مسار ملف أو Traceback أو اسم adapter أو بروتوكول Pulse. لا يسمح بإعادة المحاولة التلقائية بعد outcome غامض.

`request_id` يمنع التكرار داخل جلسة Runtime في الذاكرة. الطلب المتطابق يعيد `command_id` القائم وoutcome مسجلًا ولا يعيد الأثر. إعادة استعماله مع طلب مختلف ترفض. هذه ليست exactly-once عبر شبكة أو إعادة تشغيل أو عملية جديدة.

## تحقق العقد والاختبارات

يطبق محمل سيناريو 1.2 فحوصًا مكافئة للـschema للأنواع، والحقول الناقصة/الزائدة، والتكرارات، والـtelemetry المرئية الآمنة. اختبرت المسارات السالبة: learning objectives وtelemetry وhistory/hypothesis types، finding، intervention number، duplicate observation id، ومحاولة عرض blood volume.

**نتيجة الحزمة الكاملة:** **43 اختبارًا نجح في 25.540s** مع `PULSE_ROOT=/home/ubuntu/pulse-build/install` و`-W error::ResourceWarning`. تحتوي على **8 اختبارات تكامل فعلية مع Pulse SDK**؛ لم تقبل نتيجة نهائية مع skipped integration tests.

## Gate 0 والمراجعة الطبية

تم نشر حزمة Gate 0 التشغيلية: README، نص الميسر، قالب معلومات/موافقة محلي، CSV فارغ لالتقاط الدليل، codebook، وقالب مذكرة قرار. لا توجد بيانات مشاركين أو قرار مملوء. [6]

كما نشرت حزمة مراجعة طبية/تعليمية مستقلة تحدد المواد وأسئلة المراجع وسجل القرار. لا يوجد مراجع خارجي أو قبول أو توقيع محفوظ. [7]

## المخاطر المتبقية وقرار الإيقاف

| الخطر أو الفجوة | الحالة | الإجراء المطلوب قبل Unity |
|---|---|---|
| Gate 0 | UNTESTED | تشغيل الجلسات وفق اعتماد المؤسسة وتسجيل قرار PASS/PIVOT/INCONCLUSIVE. |
| مراجعة المحتوى | UNVALIDATED | تلقي قرار خارجي موثق ACCEPT/REWORK/OUT_OF_SCOPE ومعالجة المطلوب. |
| Unity runtime | NOT_IMPLEMENTED | لا يبدأ قبل الأحكام الحاكمة وقرار بدء منفصل. |
| Frame/render/network cost | UNMEASURED | يقاس في Unity لاحقًا؛ لا تستنتج من benchmark headless. |
| Cross-session idempotency/checkpoint | ABSENT/PARTIAL BY DESIGN | لا retry أعمى؛ يتطلب تصميمًا مستقلًا إن تغير النطاق. |
| صلاحية سريرية أو تقييمية | PROHIBITED في S0 | تبقى Learning Mode تكويني فقط. |

## الالتزامات الرئيسية

| الالتزام | المضمون |
|---|---|
| `9b9356c` | learner-safe state projection وFacade. |
| `3071f2b` | نقل HTTP/JSON محلي وADR-002. |
| `8089584` | host paced مملوك لـVPE وإيقاف نظامي. |
| `31a6f57` | benchmark tick policy وتكامل Pulse عند 0.5s. |
| `e1d0653` | تقوية تحقق عقد السيناريو. |
| `a299dd0` | حزمة Gate 0 والمراجعة الطبية. |

## المراجع

[1]: ../../tests/test_client_facade.py "اختبارات منع تسريب الحالة الداخلية"
[2]: https://docs.unity3d.com/6000.5/Documentation/Manual/web-request.html "Unity Manual: Interacting with web servers"
[3]: https://learn.microsoft.com/en-us/dotnet/standard/io/how-to-use-named-pipes-for-network-interprocess-communication "Microsoft Learn: Named pipes"
[4]: ../../artifacts/benchmarks/pre_unity_client_boundary_tick_policy/pulse_tick_summary.json "ملخص benchmark سياسة tick"
[5]: ../../artifacts/benchmarks/pre_unity_client_boundary_tick_policy/pulse_tick_samples.csv "عينات benchmark سياسة tick"
[6]: ../gate0/README.md "حزمة تنفيذ Gate 0"
[7]: ../validation/s0-medical-review-packet.md "حزمة مراجعة طبية وتعليمية مستقلة"
