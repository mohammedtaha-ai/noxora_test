# Nexora VPE — Virtual Patient Engine

Nexora VPE هو أساس **محاكاة تعليمية تكوينية** لمريض افتراضي. يركز نطاق **S0** الحالي على حالة واحدة: إصابة بطنية لدى بالغ مع تمزق طحال ونزف داخلي قائم ومتفاقم. لا يقدّم هذا المستودع تشخيصًا أو توصية علاجية لمريض حقيقي، ولا يدعم تقييمًا عالي العواقب أو قرار نجاح/رسوب.

> **مبدأ معماري:** طبقة VPE هي المالك الوحيد لزمن المحاكاة وطلبات الفسيولوجيا. يمثل Pulse حقيقة فيزيولوجية محاكاة مثبتة الإصدار؛ ولا تملك واجهة مستقبلية أو طبقة لغة حق تغييرها مباشرة.

## ما يعمل الآن

| المكوّن | الحالة | الدليل |
|---|---|---|
| Gate A headless مع Pulse | **VERIFIED** | [تقرير Gate A](docs/reports/002-pulse-gate-a.md) وCSVs الخام المحفوظة. |
| نزف داخلي طحالي، إيقاف نزف، Saline، PackedRBC | **VERIFIED** في محرك Pulse المثبت | [`experiments/pulse_gate_a/`](experiments/pulse_gate_a/). |
| حفظ/استعادة Pulse | **VERIFIED** | تطابق رقمي في 121 صفًا متداخلًا؛ انظر التقرير. |
| نواة S0 headless | **IMPLEMENTED + TESTED** بعقد أوامر منظم وبديل حتمي لاختبارات الوحدة | [`src/nexora_vpe/`](src/nexora_vpe/). |
| PulseAdapter إنتاجي | **IMPLEMENTED + INTEGRATION TESTED** مع عملية Pulse واحدة وrevision pin وcheckpoint | [عقد العملية](docs/contracts/pulse-adapter-process-contract.md) و[تقرير التكامل](docs/reports/004-pulse-adapter-integration.md). |
| تصعيد منظم في S0 | **IMPLEMENTED + TESTED** بمعرف مؤلف ودليل حدث؛ لا يغير Pulse أو الزمن | [عقد التصعيد](docs/contracts/s0-escalation-contract.md). |
| Facade وDTOs آمنة للمتعلم | **IMPLEMENTED + TESTED** | لا تعيد الحقيقة الداخلية أو checkpoint أو telemetry الخفية؛ [العقد](docs/contracts/vpe-client-facade-contract.md). |
| نقل عميل محلي وhost paced | **IMPLEMENTED HEADLESS** | HTTP/JSON loopback وVPE يملك clock عند tick 0.5s؛ [ADR-002](docs/decisions/ADR-002-local-client-facade-transport.md). |
| Gate 0 والمراجعة الطبية/التعليمية | **READY_FOR_EXECUTION / UNTESTED / UNVALIDATED** | [حزمة Gate 0](docs/gate0/README.md) و[حزمة المراجعة](docs/validation/s0-medical-review-packet.md). |
| Bridge C++ مباشر إلى SDK Pulse | **VERIFIED** محليًا | [`src/physiology/pulse_bridge/`](src/physiology/pulse_bridge/) وartifact صغير. |
| Unity وFAST ثلاثي الأبعاد وLLM | **DEFERRED** | Unity لا يبدأ قبل مراجعة Gate 0 والمحتوى وقرار مستقل. |
| صلاحية سريرية أو تقييم high-stakes | **NOT IMPLEMENTED** | خارج نطاق S0. |

## المعمارية الحالية

```text
عميل Unity مستقبلي (لا يوجد في هذه الدفعة)
        ↓ HTTP/JSON محلي آمن
VPE Client Facade + loopback transport
        ↓ أوامر منظمة فقط
VPE Host + Runtime (clock، طابور، سيناريو، أدلة، لقطات)
        ↓
Physiology Adapter ضيق ومثبت الإصدار
        ↓
Pulse SDK / حالة مريض مرجعية
        ↓
Telemetry + Evidence + Replay artifacts
```

يحتفظ `VpeRuntime` بعقد orchestration وبديل حتمي لاختبارات الوحدة السريعة. أما مسار التشغيل الإنتاجي المختبر فهو `PulseAdapter`: يشغل عملية C++ محلية واحدة تمتلك Pulse SDK، ويتحقق من revision المثبت، ولا يقبل إلا حالة S0 الموجودة وتدخلات Saline وPackedRBC المعرّفة في السيناريو، ويثبت checkpoint والاستعادة. لا يعني ذلك صلاحية سريرية أو determinism عامًا.

## المتطلبات

لتشغيل اختبارات النواة فقط: Python 3.11 أو أحدث. لا توجد تبعيات Python خارج المكتبة القياسية.

لتشغيل bridge Pulse الحقيقي: CMake 3.20+، مترجم C++17، وSDK Pulse مبني محليًا عند revision المثبت `e8a36497b8ba78e788dc201a6baf74e1c297c56f`، مع وجود `StandardMale@0s.json` تحت `PULSE_ROOT/bin/states/`. راجع [توثيق provenance والترخيص](docs/research/pulse-provenance-and-license.md) قبل أي توزيع.

## البدء السريع

### 1. اختبارات نواة S0

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 scripts/run_s0_demo.py
```

ينتج العرض artifact صغيرًا في `artifacts/representative-small-results/s0_runtime_demo.json`. هذا العرض **هندسي تكويني فقط** ويستخدم `DeterministicPhysiologyAdapter`، لا نموذجًا سريريًا. تدعم النواة كذلك `record_escalation` لمعرف موجود في قاموس السيناريو؛ يوثق الفعل كدليل ولا يغير Pulse أو زمن المحاكاة، كما يبين [عقد التصعيد](docs/contracts/s0-escalation-contract.md).

### 2. PulseAdapter واختبارات التكامل الإنتاجية

بعد بناء Pulse وتوليد بياناته وحالات البداية (`gendata` ثم `genStates`):

```bash
PULSE_ROOT=/path/to/pulse/install scripts/test_pulse_adapter_integration.sh
```

يبني هذا الأمر خادم adapter C++ ثم يشغّل اختبارات `VPE Runtime → PulseAdapter → Pulse SDK`. تتحقق الاختبارات من تقدم الزمن والنزف القائم وSaline وPackedRBC وcheckpoint والاستعادة ورفض compound غير معتمد. راجع [عقد العملية](docs/contracts/pulse-adapter-process-contract.md) قبل تغيير البروتوكول.

### 3. حدود العميل وbenchmark host headless

```bash
PULSE_ROOT=/path/to/pulse/install PYTHONPATH=src \
  python3 scripts/benchmark_pulse_tick_policy.py \
  --pulse-root /path/to/pulse/install --trials 3 --ticks 5 \
  --output-dir artifacts/benchmarks/pre_unity_client_boundary_tick_policy
```

ينفذ هذا benchmark headless زيادات 0.1 و0.25 و0.5 و1 و2 ثانية على Pulse الحقيقي. السياسة المحلية المختارة هي 0.5 ثانية لأن 0.25 أظهرت quantization متناوبًا في البيئة المقاسة. لا يقيس الأمر FPS أو rendering أو Unity. راجع [تقرير حدود العميل](docs/reports/006-pre-unity-client-boundary-review.md) و[عقد Facade](docs/contracts/vpe-client-facade-contract.md).

### 4. Bridge Pulse SDK التشخيصي

```bash
PULSE_ROOT=/path/to/pulse/install scripts/run_pulse_bridge.sh
python3 scripts/verify_pulse_bridge_artifact.py
```

يبني السكربت البرنامج C++، ويحمّل `StandardMale@0s.json`، ويطبق نزفًا داخليًا طحاليًا اختباريًا، ويحفظ لقطة، ويقارن المسار الأصلي بالمسار المستعاد. يحفظ `pulse_sdk_bridge.json` فقط؛ تبقى لقطة الحالة الكبيرة في `.build/` وغير ملتزمة.

### 5. تحقق Gate A المحفوظ

```bash
python3 experiments/pulse_gate_a/scripts/summarize_gate_a.py
cd experiments/pulse_gate_a/results/2026-08-22
sha256sum --check SHA256SUMS.txt
```

## الهيكل

| المسار | الغرض |
| --- | --- |
| `docs/design/` | نواتج Design Sprint: الأهداف، rubric التكويني، جرد الأدلة والتفاعلات والعقد. |
| `docs/reports/` | تدقيق المستودع وتقارير Gate A. |
| `docs/decisions/` | قرارات معمارية قابلة للمراجعة. |
| `docs/research/` | بحث المكونات، provenance، والترخيص. |
| `docs/status/` | الحالة الصادقة الحالية والمخاطر والبوابات. |
| `docs/gate0/` | حزمة تنفيذ Gate 0 وقوالب الدليل والقرار؛ لا تحتوي نتائج مشاركين. |
| `docs/validation/` | حزمة مراجعة طبية/تعليمية مستقلة؛ لا تحمل قبولًا فعليًا. |
| `schemas/` | مخططات versioned للأحداث. |
| `scenarios/` | تعريف سيناريو S0 قابل للمراجعة دون تعديل شيفرة النواة. |
| `src/nexora_vpe/` | runtime headless: clock، queue، adapter boundary، events، snapshots. |
| `src/physiology/pulse_bridge/` | bridge C++ التشخيصي وخادم PulseAdapter طويل العمر إلى SDK. |
| `docs/contracts/` | عقود process وadapter القابلة للمراجعة. |
| `tests/` | اختبارات وحدة وتكامل عقود النواة. |
| `experiments/pulse_gate_a/` | سيناريوهات Gate A وCSVs الخام ومحللها. |
| `artifacts/representative-small-results/` | artifacts صغيرة ومقصودة الحفظ. |
| `scripts/` | مشغلات قابلة لإعادة الإنتاج والتحقق. |

## الحدود الحالية

لا توجد واجهة Unity، أو resolver لـ FAST، أو محادثة LLM، أو debrief، أو إدارة مستخدمين، أو authoring UI في هذه المرحلة. الحدود التقنية للعميل وtransport المحلي والـhost headless موجودة، لكن لا تحول جاهزية Gate 0 أو المراجعة الطبية غير المكتملة إلى إذن تنفيذ Unity. التصعيد المتاح هنا حدث منظم headless فقط، وليس تكاملًا تشغيليًا مع فريق أو خدمة خارجية. لا تُقرأ الأحداث المنظمة على أنها تقييم للكفاءة؛ فهي مواد تغذية راجعة تكوينية مستقبلية فقط. لا يجوز استخدام قيم Pulse أو السيناريوهات المحفوظة لتوجيه علاج أو اتخاذ قرار عن شخص حقيقي.

## الترخيص

لم يُختر ترخيص للمستودع نفسه بعد. يُستخدم Pulse عند revision محدد تحت Apache License 2.0؛ يسجل [سجل provenance والترخيص](docs/research/pulse-provenance-and-license.md) المصدر والالتزامات الواجب مراجعتها قبل التوزيع. لا تُضمّن مكتبات Pulse أو بياناته أو حالات المرضى الكبيرة في هذا المستودع.
