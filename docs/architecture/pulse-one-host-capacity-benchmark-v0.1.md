# قياس سعة Pulse/VPE على مضيف واحد v0.1

**الحالة:** `MEASURED / LOCAL HEADLESS ENGINEERING EVIDENCE`.
**تاريخ القياس:** 2026-08-26.
**السيناريو:** `trauma_splenic_01`، Pulse المثبت عند revision `e8a36497b8ba78e788dc201a6baf74e1c297c56f`.
**الغرض:** استبدال التخمين عن كثافة جلسات Pulse على مضيف واحد بقياس قابل لإعادة التشغيل. هذا ليس sizing إنتاجيًا ولا SLA ولا قياس Unity أو شبكة أو cloud أو تحقق طبي.

## القرار المستخلص

> لا يوجد دليل من هذه النتائج على أن Python هي عنق التِك. كل جلسة تستعمل `VpeRuntime` و`VpePacedHost` الحقيقيين، وتملك عملية PulseAdapter/Pulse C++ مستقلة. ضغط المضيف الذي ظهر عند السعات العالية هو **CPU**؛ لم يظهر ضغط RAM أو I/O ولم يحدث فشل عمليات خلال N=96.

عند `N=96` ظهر أول **hard saturation** وفق تعريف التجربة: `max_overrun_s=0.0941`، أي أن بعض جولات تِك 0.5 ثانية تجاوزت الميزانية. CPU المضيف كان مشبعًا تقريبًا (`p50=98.15%`, `p95=98.62%`) بينما بقيت الذاكرة المتاحة الدنيا `20.44 GiB` من `23.85 GiB`، وI/O القرصي عند `p95=0.55%`. لذلك **مصدر عتبة التشبع المرصودة هو CPU**، لا الذاكرة أو القرص.

## المنهج

يحافظ harness `scripts/benchmark_pulse_session_capacity.py` على الحدود القائمة: لا يعرف العميل Pulse، ولا يملك benchmark ساعة مستقلة، ولا يوجد Go/Laravel/broker/Unity في المسار. لكل جلسة ينشئ harness `PulseAdapter` حقيقيًا و`VpeRuntime` و`VpePacedHost` بتِك محاكاة `0.5s`، ثم يدير جلسات المستوى نفسه بخيوط متزامنة لقياس ضغط عمليات مستقلة. يقيس RSS لكل subprocess وRSS المجموع، زمن التِك، overrun، CPU/I/O والذاكرة المتاحة على المضيف، وبدء/إنهاء الجلسة وحفظ/استعادة checkpoint.

استخدم القياس `psutil 7.2.2` لقراءة RSS وCPU وذاكرة/I/O المضيف. توثق psutil أنها واجهة لمعلومات العمليات واستخدام النظام، وأن `memory_info()` وعدادات CPU/الذاكرة متاحة لمراقبة العمليات والنظام.[1] مجموع RSS مقصود في الجدول لأنه يجيب على السؤال المطلوب عن العمليات، لكنه **قد يكرر** الصفحات المشتركة ولا يساوي ذاكرة فيزيائية فريدة.

| معلمة | القيمة |
|---|---:|
| المضيف | Linux `6.18.38+`، 6 logical CPU، 3 physical CPU، 23.85 GiB RAM |
| المستويات الأساسية | N = 1، 2، 4، 8، 16، 32 |
| امتداد التشبع | N = 48، 64، 96؛ يتوقف عند أول failure أو overrun |
| التِك | 0.5s simulation time، بلا sleep متعمد أثناء القياس |
| المستوى الأساسي | 3 trials، 3 warm-up ticks، 15 measured ticks لكل جلسة |
| امتداد التشبع | 2 trials، 2 warm-up ticks، 10 measured ticks لكل جلسة |
| hard saturation | فشل عملية أو `overrun_s > 0` |
| resource pressure فقط | CPU ≥90% أو available RAM <10% أو disk busy ≥90%؛ لا يوقف وحده الاختبار |

## جدول السعة المقاس

| جلسات Pulse المتزامنة | RSS المجموع الأقصى | tick p50 / p95 / p99 (ms) | CPU p50 / p95 (%) | checkpoint save p95 (ms) | checkpoint restore p95 (ms) | overrun / فشل | النتيجة |
|---:|---:|---:|---:|---:|---:|---|---|
| 1 | 24.9 MiB | 39.1 / 42.5 / 43.8 | 17.1 / 21.3 | 46.0 | 118.9 | 0 / 0 | PASS ضمن التجربة |
| 2 | 45.6 MiB | 39.9 / 42.4 / 46.3 | 36.4 / 44.0 | 46.0 | 124.0 | 0 / 0 | PASS ضمن التجربة |
| 4 | 87.0 MiB | 40.3 / 45.1 / 47.7 | 64.3 / 74.7 | 48.9 | 129.5 | 0 / 0 | PASS ضمن التجربة |
| 8 | 173.7 MiB | 44.6 / 61.0 / 63.4 | 80.5 / 86.3 | 67.8 | 187.1 | 0 / 0 | PASS؛ CPU يقترب من الضغط |
| 16 | 335.3 MiB | 81.1 / 107.7 / 115.8 | 90.0 / 95.0 | 124.2 | 338.3 | 0 / 0 | PASS وظيفي؛ CPU pressure |
| 32 | 696.7 MiB | 138.9 / 199.5 / 230.0 | 95.1 / 96.8 | 219.5 | 641.0 | 0 / 0 | PASS وظيفي؛ CPU pressure |
| 48 | 1,057.8 MiB | 194.1 / 279.8 / 304.3 | 96.6 / 97.7 | 343.4 | 884.0 | 0 / 0 | PASS وظيفي؛ CPU pressure |
| 64 | 1,401.6 MiB | 227.3 / 342.3 / 386.3 | 97.6 / 98.6 | 410.0 | 1,129.7 | 0 / 0 | PASS وظيفي؛ CPU pressure |
| 96 | 2,132.5 MiB | 316.0 / 521.8 / 560.0 | 98.2 / 98.6 | 532.3 | 1,570.2 | max overrun 94.1ms / 0 | **CPU saturation observed** |

كل checkpoint كان تقريبًا `2,334,678–2,334,823 bytes` في هذه الحالة. لا يثبت ذلك حجم artifact لسيناريو آخر أو سياسة تخزين durable. عينات CSV وJSON الكاملة، بما فيها كل RSS/tick/checkpoint/failure، محفوظة في [`artifacts/benchmarks/pulse_one_host_capacity_v0.1/`](../../artifacts/benchmarks/pulse_one_host_capacity_v0.1/).

## ما يحل محل النموذج التوضيحي

`capacity-model-v0.1` يبقى نموذج طلب/حجم توضيحي فقط. أما قرار كثافة جلسات Pulse على مضيف واحد فيجب أن يبدأ الآن من هذا benchmark، لا من نسبة متعلمين أو افتراض لغة. الدليل الحالي يثبت أن:

| السؤال | الجواب المسموح به الآن |
|---|---|
| هل ثبتت 50,000 جلسة نشطة؟ | **لا**؛ الرقم لم يقس ولا يمكن استنتاجه خطيًا من هذا المضيف. |
| هل memory هي القيد حتى N=96؟ | **لا** في هذا المضيف/السيناريو؛ بقيت >20 GiB متاحة. |
| ما أول قيد مقاس؟ | **CPU**؛ overrun ظهر عند N=96 مع CPU ≈98%. |
| ما أقصى مستوى بلا overrun في العينة؟ | **N=64**؛ لكنه يملك CPU p95≈98.6% ولا يعادل توصية تشغيلية أو headroom production. |
| هل أثبت القياس Go أو Python كقرار performance؟ | **لا**؛ يثبت أن مسار VPE/Pulse الحالي يحتاج قياس supervisor/network منفصل فقط عند trigger مقاس. |

## حدود وحدود إعادة القياس

لا يحدد هذا القياس كثافة تشغيلية آمنة أو blast radius أو HA أو تكلفة مضيف أو SLO. قبل أي قرار نشر لاحق، يعاد القياس على hardware المستهدف مع soak أطول، cgroup/CPU pinning، telemetry workload، persistence policy، ونموذج failure/restart. ولا يتحول `N=64` إلى target؛ هو فقط آخر مستوى خالٍ من overrun في هذه العينة القصيرة قبل ظهور overrun عند N=96.

## إعادة التشغيل

```bash
PULSE_ROOT=/home/ubuntu/pulse-build/install PYTHONPATH=src \
python3 scripts/benchmark_pulse_session_capacity.py \
  --pulse-root /home/ubuntu/pulse-build/install \
  --output-dir artifacts/benchmarks/pulse_one_host_capacity_v0.1 \
  --session-counts 1,2,4,8,16,32 \
  --trials 3 --warmup-ticks 3 --measure-ticks 15 --tick-s 0.5
```

ولإيجاد أول hard saturation بعد المستوى الأساسي، شغل `48,64,96` في مجلد `extended_saturation` بالـtrials والـticks المسجلة في `capacity_summary.json`.

## المراجع

[1] [psutil documentation — process and system CPU/memory/I/O information](https://psutil.readthedocs.io/).
[2] [الـartifacts الخام للـbenchmark](../../artifacts/benchmarks/pulse_one_host_capacity_v0.1/capacity_summary.json).
[3] [الـbenchmark الممتد إلى saturation](../../artifacts/benchmarks/pulse_one_host_capacity_v0.1/extended_saturation/capacity_summary.json).
