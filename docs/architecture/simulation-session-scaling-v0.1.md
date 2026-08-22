# Simulation Session Scaling v0.1

**الحالة:** target design.  
**الثابت:** لا تعديل لـS0 VPE/Pulse ownership، ولا Unity، ولا multi-worker Pulse، ولا ادعاء recovery شفاف قبل إثبات checkpoint/replay contract.

## الغرض

توضح هذه الوثيقة كيف يتوسع **عدد** جلسات Nexora عبر workers مستقلة مع إبقاء كل session stateful ومملوكًا لمالك واحد. لا يتوسع Pulse داخل session بالـhorizontal fan-out، ولا يتحول الـclient إلى simulator. يكون نمو العدد عبر allocator وsession registry وlease/heartbeat/fencing، لا عبر parallel ticks داخل VPE.

> **Session ownership invariant:** لا يوجد في لحظة واحدة أكثر من owner صالح واحد يستطيع تمرير command أو advance clock أو كتابة lifecycle transition لـ`session_id` واحد.

## حدود الملكية القائمة

| الأصل | المالك الآن | قاعدة الاستمرار |
|---|---|---|
| simulation time | `VpePacedHost` / VPE | client أو API لا يقدمان time advance. |
| Pulse process/state | `PulseAdapter` داخل VPE owner | single owner؛ لا shared in-process Pulse. |
| queued learner actions | VPE runtime/host | commands مصرح بها ومنظمة فقط. |
| client projection | `VpeClientFacade` | learner-safe DTOs؛ لا internal state leak. |
| local HTTP | `LocalFacadeHttpServer` | loopback/local token فقط؛ ليس cloud endpoint. |
| session registry future | Control/Data Plane boundary | metadata وlease فقط، لا Pulse state. |

## session registry المستهدف

| الحقل | المعنى | mutable؟ |
|---|---|---:|
| `session_id` | opaque distributed ID | لا. |
| `tenant_id`, `learner_id`, `assignment_id` | ownership/authorization links | لا بعد creation إلا controlled migration. |
| `scenario_version_id` | immutable scenario pin | لا. |
| `status` | lifecycle state | نعم، transition guard. |
| `owner_worker_id` | owner التشغيلي الحالي | نعم مع lease. |
| `lease_generation` | fencing token monotonic per claim | نعم عند claim فقط. |
| `lease_expires_at`, `last_heartbeat_at` | liveness | نعم. |
| `last_safe_artifact_ref` | reference اختياري إلى artifact policy معتمد | نعم؛ لا يعني replay capability تلقائية. |
| `created_at`, `updated_at`, `ended_at` | audit/time | نعم وفق lifecycle. |
| `failure_code`, `failure_detail_ref` | evidence/reporting | نعم، لا يسرّب internals للمتعلم. |

`lease_generation` يمنع worker قديمًا من إكمال writes بعد فقد lease أو network partition. كل write صاحب أثر lifecycle يطابق `(session_id, lease_generation)` الحالية. لا يكفي heartbeat timestamp وحده لمنع split-brain.

## lifecycle وstate machine المستهدف

```text
ALLOCATED ──claim──► STARTING ──VPE ready──► ACTIVE ──completion──► COMPLETED
   │                     │                       │
   │                     └─startup failure──────► PAUSED_BY_SYSTEM
   │                                             │
   └─cancel/expiry──────────────────────────────► CANCELLED

ACTIVE / STARTING ──heartbeat expiry, crash, Pulse error──► RECOVERY_REQUIRED
RECOVERY_REQUIRED ──approved recoverable procedure──► STARTING
RECOVERY_REQUIRED ──no approved recovery──► PAUSED_BY_SYSTEM / FAILED
```

الحالات الدقيقة تراعي عقد S0 الموجود؛ هذه state machine منصة مستقبلية ولا تعيد تعريف `RuntimeStatus`. لا يسوغ `RECOVERY_REQUIRED` إعادة بناء Pulse state بلا دليل. التفريق مقصود بين **snapshot** خفيف للعرض و**checkpoint** محتمل للاسترجاع؛ لا يحمل أحدهما وعد الآخر.

## claim، heartbeat، وhandoff

1. يبدأ allocator من session مؤهلة (`ALLOCATED` أو `RECOVERY_REQUIRED` بموافقة policy).
2. ينفذ worker claim ذريًا في registry: يعين `owner_worker_id`، يزيد `lease_generation`، ويحدد expiry.
3. لا يبدأ VPE/Pulse إلا بعد نجاح claim؛ worker يرسل heartbeat قبل expiry.
4. كل command وstatus write يحوي fencing token/owner context؛ token قديم يرفض.
5. إذا فشل heartbeat أو crash، لا يأخذ worker جديد session إلا بعد expiry أو explicit revocation مع audit.
6. worker الجديد يدخل `STARTING` أو `RECOVERY_REQUIRED` طبق artifact/recovery policy؛ لا handoff live memory/Pulse process بوعد غير مثبت.
7. عند pause/failure، تعرض facade error/client-safe state فقط، وتحفظ التفاصيل التقنية في restricted evidence reference.

| الحدث | action مطلوب | ما يمنع |
|---|---|---|
| duplicate claim | conditional update/fencing rejection | two workers advancing same VPE. |
| delayed heartbeat | expiry + owner validation | stale worker writeback. |
| worker crash | mark recovery-needed بعد timeout | auto-complete أو fabricated state. |
| process succeeds but event relay fails | committed state + outbox pending | blocking simulation على analytics. |
| checkpoint write fails | policy-driven pause/defer للفئة المحتاجة | silent loss أو ادعاء durability. |
| client retries command | command/request ID dedupe policy future | duplicate intervention/action. |

## session commands وإدارة backpressure

تنفذ الأوامر القادمة من client داخل session owner فقط. تُقاس command queue depth وcommand age وactive tick time وhost sleep budget وPulse error rate، ولا يطبق host catch-up كي لا يدّعي simulation time غير منفذ. benchmark S0 الحالي يدعم tick 0.5s كـlocal host policy فقط؛ لا يساوي Unity FPS أو cloud SLO أو multi-session capacity.

| signal | حماية فورية/مستقبلية | invariant |
|---|---|---|
| queue depth/age مرتفع | admission control أو bounded command queue | لا loss صامت للأوامر المتفق عليها. |
| tick duration أعلى من cadence | no-catch-up + event/metric | لا يسرّع simulation clock لتعويض wall time. |
| consumer lag | outbox backlog/async retry | لا توقف VPE. |
| worker saturation | allocator limits/new session throttling | لا oversubscription يسبب cross-session failure. |
| artifact pipeline lag | async upload/backoff/policy status | لا يكون artifact consumer شرط tick. |

## artifacts، checkpoints، وreplay

يتعامل `ObjectStorage` مع checkpoint/replay/export/assets كفئات artifact منفصلة، وDB يحتفظ بالـreference/hash/metadata/version/retention/classification. لكن **لا يوجد في S0 الحالي durable checkpoint workflow إلى object storage**. لذلك يصف `last_safe_artifact_ref` إمكانية مستقبلية، وليس feature active.

| artifact class | التفسير | policy المستقبلية |
|---|---|---|
| `session_checkpoint` | artifact استرجاع إذا عرّف/اختبر | restricted + lifecycle/retention; لا يفترض. |
| `session_replay` | sequence/inputs/evidence قابلة للمراجعة | immutable/versioned؛ rebuild/compatibility rules. |
| `session_export` | user/admin export | approval/scoped authorization/expiry. |
| `scenario_asset` | authored content asset | hash/license/version. |
| `research_export` | de-identified aggregate عند اعتماد policy | strict classification/provenance. |

## crash recovery assertions

| مستوى الادعاء | مسموح الآن؟ | السبب |
|---|---:|---|
| detect worker/Pulse failure | نعم، ضمن VPE failure status الحالي | S0 runtime ينقل failure إلى paused/system state. |
| safely pause session | نعم، على حدود runtime الحالية | لا يفترض resume. |
| recreate session from durable checkpoint | لا | لا artifact/replay compatibility contract أو end-to-end proof. |
| seamless ownership handoff | لا | live state وPulse single ownership لا يدعمانه مثبتًا. |
| active-active region session | لا | لا write/session ownership/residency design. |

## عتبات قرار مسماة

| المعرّف | evidence | قرار محتمل |
|---|---|---|
| `SIM-POOL-01` | active sessions تتجاوز host capacity المقاسة أو failure blast radius غير مقبول | introduce session registry + allocator/lease spike. |
| `SIM-FENCE-02` | أكثر من worker process أو distributed deployment مطلوب | durable lease generation/fencing implementation وchaos tests. |
| `SIM-RECOVER-03` | product requires resume after crash | durable artifact format + compatibility + replay/checkpoint validation قبل promise. |
| `SIM-QUEUE-04` | queue age/depth أو tick telemetry تثبت overload | admission/backpressure policy ثم load test. |
| `SIM-REGION-05` | latency/residency/RPO-RTO requirement معتمد | region placement/DR architecture؛ لا portable session افتراضي. |

## S0 compatibility statement

هذا هدف adapter/registry خارج `nexora_vpe.runtime`. لا يستبدل `VpePacedHost` ولا `PulseAdapter` ولا يغير معنى `PAUSED_BY_SYSTEM`. وتظل نتائج Pulse integration الفعلية وbenchmark الحالي evidence محلية فقط؛ لا تتحول إلى production capacity forecast.

## المراجع

[1]: ../reports/006-pre-unity-client-boundary-review.md "Nexora: Pre-Unity Client Boundary Review"
[2]: ../contracts/vpe-client-facade-contract.md "Nexora VPE Client Facade Contract"
[3]: ../research/event-platform-comparison.md "Nexora: مقارنة منصة الأحداث"
[4]: platform-scale-target-v0.1.md "Nexora Platform Scale Target"
