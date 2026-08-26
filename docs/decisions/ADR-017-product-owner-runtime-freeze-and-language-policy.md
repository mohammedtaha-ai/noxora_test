# ADR-017: تجميد مسارات المنصة وسياسة اللغات بأمر مالك المنتج

**Status:** Accepted.
**Date:** 2026-08-26.
**Scope:** قرارات تسلسل التنفيذ والحدود المعمارية؛ لا يغير كود التطبيق أو database schema.

## Context

قُبلت Go Platform Foundation Phase 1 كـengineering spike موثق، لكن قيمة S0 ما زالت غير مثبتة بشريًا: Gate 0 `READY_FOR_EXECUTION / UNTESTED` والمراجعة الطبية/التعليمية `READY_FOR_REVIEW / UNVALIDATED`. كما أن القياس المحلي لـVPE/Pulse لا يقدم حجة لبناء worker أو transport أو platform plane جديد؛ بل يحدد ضغط CPU محليًا عند كثافات Pulse عالية فقط.[1] [2]

توسيع Go أو Laravel قبل أن يثبت Gate 0 والمراجعة المستقلة القيمة والمحتوى يزيد عدد المسارات التشغيلية ويفرض قرارات host/queue/identity/schema بلا حاجة S0 مثبتة.

## Decision

| المجال | القرار الملزم |
|---|---|
| `apps/platform-plane` | **FROZEN** عند حالة spike الموثقة. لا worker ولا transport ولا broker ولا Pulse/VPE integration ولا Go→Python RPC ولا public API ولا cloud/Kubernetes. |
| `apps/control-plane` | **FROZEN**. لا features ولا migrations ولا تغيير ORM/schema. يسمح فقط بـADR بحثي يقارن Laravel بالبديل المستقبلي. |
| C#/Unity | عميل thin مستقبلي فقط؛ لا مشروع Unity أو client implementation قبل اكتمال Gate 0 والمراجعة الطبية/التعليمية المستقلة. |
| Python | المالك المستقبلي لـVPE والساعة والأوامر والسيناريوهات والملاحظات والأدلة والـAI عند وجود قرار لاحق يبرره؛ لا يبدأ worker أو transport الآن. |
| C++ | Pulse والـbridge الضيق فقط. لا تنقل الحقيقة الفيزيولوجية إلى Go/Laravel/Unity. |
| لغة/إطار رابع | ممنوع ما لم يوجد ADR سابق وtrigger مقاس يوضح الحاجة. |

## Triggers لإعادة فتح Go فقط

لا تعاد مناقشة Go بسبب تفضيل لغوي أو تخمين scale. يلزم دليل مكرر، قابل للمراجعة، على أحد الشرطين التاليين **وإثبات أن Python supervisor هو عنق الزجاجة**:

1. أكثر من نحو `2,000` اتصال متزامن غير مُلبّى بواسطة عملية Python `asyncio` واحدة في workload ممثل؛ أو
2. أكثر من نحو `200` عملية Pulse متزامنة على مضيف واحد مع evidence يبين أن supervisor Python، لا CPU/RAM/Pulse/network، هو القيد.

قياس N=96 الحالي لا يفي بأي trigger: أثبت overrun مرتبطًا بـCPU على مضيف محلي، ولا يقيس supervisor production أو اتصالات عامة أو broker.[1]

## Consequences

العمل المسموح في هذه الدفعة محصور في benchmark، توثيق الحوكمة، ADRs، وخطة التشغيل البشرية لـGate 0. لا يعني التجميد رفضًا دائمًا لـGo أو Laravel ولا قبولًا ضمنيًا لهجرة Python؛ إنه يمنع الالتزام الهندسي المبكر. تبقى سلطة المحاكاة كما هي: Python/VPE وقت تنفيذ مستقبلي، Pulse/C++ فيزيولوجيا، والعميل/المنصات ليست حقيقة المحاكاة.

## References

[1] [قياس سعة Pulse/VPE على مضيف واحد v0.1](../architecture/pulse-one-host-capacity-benchmark-v0.1.md).
[2] [الحالة الحالية](../status/CURRENT_STATUS.md).
[3] [بروتوكول Gate 0](../research/gate-0-value-discovery-protocol.md).
[4] [حزمة المراجعة الطبية لـS0](../validation/s0-medical-review-packet.md).
