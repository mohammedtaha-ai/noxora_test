# ADR-003: Backend متعدد اللغات وحدود الخدمات

**الحالة:** Accepted as target architecture; implementation deferred.  
**التاريخ:** 2026-08-23.

## السياق

أثبتت Nexora نواة S0 في Python مع Pulse C++، لكنها تحتاج مسار منصة متعددة المستأجرين لا يحوّل Python إلى default لكل backend responsibility. وفي المقابل، لا تبرر الحاجة المستقبلية إلى realtime أو worker coordination عشرات microservices أو إعادة كتابة VPE. يجب أن تتبع اللغة domain ownership وworkload وfailure/scaling boundaries.

## القرار

تستهدف Nexora نموذجًا polyglot صغير الوحدات:

| اللغة | تملك | لا تملك | سبب القرار |
|---|---|---|---|
| Laravel/PHP | Control Plane business/application backend: auth integration، tenants/memberships/RBAC policy، programs/courses/cohorts، assignments، scenario catalog metadata، authoring/admin/instructor workflows، notifications، billing later، business audit | Pulse، simulation clock، physiology، live worker lifecycle، high-rate telemetry، high-frequency realtime gateway، AI/ML | Laravel يوفر authorization policies/gates، migrations وqueue/workflow ecosystem المناسب لـbusiness CRUD؛ لا يختار لمسار physiology الحي.[1] [2] |
| Go | Platform Plane: edge/realtime when justified، session coordinator/registry، lease/heartbeat/fencing، routing، command relay، backpressure، rate-limit coordination، operational APIs | medical truth، Pulse logic، scenario medical semantics، billing/course workflows | cancellation/deadline/request context وconcurrent I/O/service coordination أسباب مناسبة، لا benchmark شعاري.[3] |
| Python | VPE Runtime، simulation orchestration، scenario/observation logic، formative algorithms، future AI/ML orchestration، research/data tooling | global auth، billing، institutions، mass edge routing، uncontrolled business tables | يحافظ على S0 المثبت ويملك ecosystem AI/simulation، ولا يعاد كتابة VPE. |
| C++ | Pulse/native bridge، numerical/scientific core، future native solvers بعد requirement+benchmark | tenant/auth/business/control plane | Pulse بالفعل native boundary؛ لا parallel ownership للـsession. |
| C#/Unity | future rendering/FAST/visualization/animation/input | business truth، medical truth، clock، direct Pulse access | client responsibility فقط؛ Unity لم يبدأ. |

## مسارات الملكية

**Hot simulation path:** Unity/Web future → Go realtime/platform → Python VPE worker → C++ Pulse. لا Laravel ولا analytics ولا LLM في physiology progression.

**Control path:** User → Laravel authorization/business mutation → owner transactional outbox → Go platform allocation/session coordination → Python worker. لا direct database cross-write ولا Laravel-commit + unreliable direct Go call.

**Async path:** owner outbox → queue/bus at trigger → Go/Python/analytics consumers. لا AI أو analytics consumer يملك truth أو يوقف live simulation.

## deployment rule

الهدف الأولي أربع ownership units فقط: `control-plane` و`platform-plane` و`simulation-worker` و`unity-client` future. يصبح module deployable service عندما يثبت تميز lifecycle أو trust boundary أو failure domain أو scaling profile أو deployment cadence، مع contract وSLO/measurement وobservability وrollback/load-failure tests (`PLAT-BOUNDARY-01`).

| workload classification | primary target | basis | non-conclusion |
|---|---|---|---|
| business CRUD/workflows | Laravel/PHP | productivity، authorization، migrations، domain ownership | Laravel ليس physiology worker. |
| high-connection / I/O coordination | Go when evidence | cancellation/concurrency/operational boundary | Go ليس default business backend. |
| CPU/native numerical science | C++/Pulse | native scientific ownership | لا native rewrite بلا benchmark. |
| simulation/AI/ML orchestration | Python | existing VPE/AI tooling boundary | Python ليس global platform default. |
| rendering/interactive client | C#/Unity future | client ecosystem | لا client truth. |

## البدائل المرفوضة

| البديل | سبب الرفض |
|---|---|
| Python لكل backend | يخلط S0/AI strengths مع auth/business/realtime/platform responsibilities ويجعل reference platform helpers production default بلا قرار. |
| Laravel لكل backend | يضع Control Plane على hot physiology/realtime/worker-coordination paths غير المناسبة لملكيته. |
| Go لكل backend | يعيد بناء business workflows وS0 بلا workload evidence وينقل domain complexity بدل حلها. |
| full microservices immediately | يخلق distributed transactions/failures/ops قبل owners/contracts/SLOs. |
| rewrite VPE in Go/C# | يهدد S0/Pulse evidence ولا يحل session ownership أو product validation. |
| Unity now | Gate 0 UNTESTED وMedical Review UNVALIDATED؛ خارج هذه الدفعة. |

## العواقب

1. `src/nexora_vpe/platform` هو **portable reference/test semantics** الآن، وليس ownership claim أن Python سينفذ Platform Plane production.
2. Laravel وGo لا يبدآن قبل دفعة مستقلة تشمل contract, schema ownership, auth grant, observability, failure and load tests.
3. لا تغير هذه ADR transport HTTP/JSON loopback المحلي المثبت لـS0؛ يقيّم gRPC/Protobuf فقط للعقود الداخلية عالية القيمة لاحقًا.
4. تبقى اللغة قرارًا قابلًا للمراجعة عند evidence، لا تصبح migration automation.

## المراجع

[1]: https://laravel.com/docs/13.x/authorization "Laravel 13.x: Authorization"
[2]: https://laravel.com/docs/13.x/migrations "Laravel 13.x: Database Migrations"
[3]: https://go.dev/blog/context "Go Concurrency Patterns: Context"
[4]: ../architecture/polyglot-platform-target-v0.1.md "Nexora Polyglot Platform Target"
