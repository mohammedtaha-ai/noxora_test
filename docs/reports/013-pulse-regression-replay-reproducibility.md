# تقرير 013: قابلية إعادة مسار Pulse/VPE الكانوني v0.1

**الحالة:** `MEASURED / LOCAL REPRODUCIBILITY EVIDENCE`.
**تاريخ القياس:** 2026-08-26.
**الغرض:** اختبار قابلية إعادة مسار واحد مثبت من VPE/Pulse، لا إثبات determinism عام أو SLA أو صلاحية سريرية.

## السؤال والنتيجة

> هل تتطابق trajectory المسجلة لمسار أوامر محدد ومثبت عند إعادة تشغيله خمس مرات على المضيف نفسه، داخل tolerance معلن، حين يملك VPE زمن المحاكاة؟

**النتيجة:** ضمن هذه العينة الضيقة، نعم. شُغّل المسار خمس مرات مع revision Pulse وscenario وinitial state وأوامر مثبتة. كانت recorded sessions وcanonical timelines متطابقة byte-for-byte، ولم يظهر فرق في telemetry عن tolerance `1e-9`.[1]

هذه النتيجة لا تغير سياسة المشروع من **reproducibility لا determinism**. لم تُختبر سيناريوهات أخرى أو مضيف آخر أو نظام تشغيل آخر أو revision آخر أو checkpoint branch أو restart recovery؛ لا يمكن تعميم الصفر المرصود خارج مجموعة الإدخال هذه.[1]

## المدخلات المقيدة

| العنصر | القيمة المثبتة |
|---|---|
| عدد التشغيلات | 5 |
| Pulse revision | `e8a36497b8ba78e788dc201a6baf74e1c297c56f` |
| scenario | `trauma_splenic_01.json`، SHA-256 `ffeb09ceaf0904bb01e6423ae039d5c71cea3e415e8e9cbf2dae634007a91bbb` |
| initial state | `StandardMale@0s.json`، SHA-256 `f30f7fbb2167f61c7fbe31dc1eab4714e07b80e6c319176dbfeb13f574133b18` |
| clock owner | VPE؛ لا wall-clock أو client clock يدخل trajectory |
| الأمر المثبت | ثلاثة intents تاريخ، VITALS، فرضية نزف داخلي، FAST، تقدم 60s، saline، تقدم 60s، VITALS، escalation |
| tolerance | `1e-9` absolute divergence لكل telemetry channel |

## divergence المرصود

| قناة telemetry | المقارنات مع baseline | max absolute divergence | داخل tolerance؟ |
|---|---:|---:|---|
| `blood_volume_ml` | 16 | 0.0 | نعم |
| `heart_rate_bpm` | 16 | 0.0 | نعم |
| `mean_arterial_pressure_mmhg` | 16 | 0.0 | نعم |
| `oxygen_saturation` | 16 | 0.0 | نعم |
| `total_hemorrhaged_volume_ml` | 16 | 0.0 | نعم |

**شكل trajectory:** snapshot counts، أسباب النشر، محاور زمن المحاكاة، ومجموعات القنوات كانت قابلة للمقارنة. `byte_identical_recorded_sessions=true` و`byte_identical_timelines=true` في العينة.[1]

## ما يثبته وما لا يثبته

| يثبته القياس | لا يثبته القياس |
|---|---|
| المسار المثبت أعاد trajectory مسجلة متطابقة داخل tolerance على هذا المضيف. | determinism عبر المنصات أو السيناريوهات أو revisions أو runtimes. |
| سجل canonical يمكن قراءته إلى timeline بالزمن المحاكى فقط. | checkpoint branch replay عبر restart أو استمرارية durable. |
| VPE يملك تقدم الزمن في مسار الاختبار. | Unity/network/client latency أو worker/broker/cloud behavior. |
| الفرق المرصود صفر للقنوات الخمس في العينة. | صحة طبية أو أثر تعليمي أو توصية علاجية. |

## إعادة التشغيل

```bash
PULSE_ROOT=/home/ubuntu/pulse-build/install PYTHONPATH=src \
python3 scripts/benchmark_pulse_regression_replay.py \
  --pulse-root /home/ubuntu/pulse-build/install \
  --output-dir artifacts/benchmarks/pulse_regression_replay_v0.1 \
  --runs 5 --tolerance 1e-9
```

يخرج harness برمز غير صفري إذا لم تتطابق shape أو تجاوزت أي قناة tolerance. ومن الدفعة التصحيحية، يعامل baseline بلا snapshots أو baseline بلا telemetry channels كـ`non-comparable` بأسباب صريحة، وتكون نتيجته خارج tolerance؛ لذلك لا يمكن لمسار بلا evidence أن يخرج باعتباره `reproducible_within_declared_tolerance`. النتيجة السلبية تبقى دليلًا صالحًا يجب تقريره، لا سببًا لزيادة tolerance بعد القياس.

## References

[1] [ملخص الخمس تشغيلات الخام](../../artifacts/benchmarks/pulse_regression_replay_v0.1/reproducibility_summary.json).
[2] [مثال canonical recorded session حقيقي](../../artifacts/benchmarks/pulse_regression_replay_v0.1/run_01.recorded_session.json).
[3] [مثال timeline حقيقي](../../artifacts/benchmarks/pulse_regression_replay_v0.1/run_01.timeline.json).
[4] [schema لـcanonical timeline](../../schemas/canonical-timeline.schema.json).
