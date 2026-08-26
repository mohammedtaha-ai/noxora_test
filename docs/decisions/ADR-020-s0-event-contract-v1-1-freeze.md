# ADR-020: تجميد عقد أحداث S0 v1.1 بعد traceability تكويني

**Status:** Accepted.
**Date:** 2026-08-26.
**Scope:** Python S0 canonical evidence/replay contract فقط؛ لا Unity أو transport أو Laravel/Go schema.

## Context

كان event contract v1.0 يسجل events وsnapshots لكن بلا consumer يثبت أن حقوله تكفي لـrubric/debrief. يفرض Master Plan v0.3 أن تسبق متطلبات assessment تجميد schema وأن يحمل كل field سبب تعلم أو evidence. أضاف M6 evaluator deterministic وcanonical replay reader، ثم طبق matrix traceability على كل event type/field وsnapshot field.[1] [2]

أظهر pass traceability حدثًا غير منتج (`fast.acquisition.recorded`) لا يملك producer في S0. وفي المقابل كان `PAUSED_BY_SYSTEM` قابلًا للوصول كحالة حية، لا كدليل مسجل؛ لذا لا يمكن replay/evaluator من معرفة أن command انتهى ambiguity مع تجميد الزمن. v1.1 يزيل الأول ويضيف الثاني كتسجيل تشغيل/سلامة ضيق.[1]

## Decision

| القرار | تفاصيله |
|---|---|
| إصدار العقد | `SCHEMA_VERSION` ينتقل من `1.0` إلى `1.1`، و`schemas/event-envelope.schema.json` يفرض `1.1`. |
| إزالة غير منتج | يحذف `fast.acquisition.recorded` من enum/schema. FAST في S0 هو `observation.requested:FAST` فقط؛ acquisition خارج S0 حتى M4. |
| إضافة لازمة لـreplay | يضاف `runtime.paused_by_system` مع `payload.reason` عندما يجمد Runtime الزمن لحماية ambiguity أو host failure. ليس event سريريًا ولا grade. |
| consumer freeze | evaluator وreplay reader هما consumerان مرجعيان للعقد. findings تبقى evidence/`UNMEASURABLE` فقط، بلا score أو pass/fail. |
| client boundary | **هذا هو العقد الذي يستهلكه عميل Unity المستقبلي عبر projection آمنة، لا وصول مباشر إلى Pulse.** |

## Migration

لا توجد migration قاعدة بيانات أو event bus أو public API في هذه الدفعة. `EvidenceStore.validate_event` يرفض v1.0 لمنع تفسير التسجيل القديم كأنه يملك semantics v1.1. raw artifacts السابقة محفوظة كدليل تاريخي، لكن لا تُحمّل داخل قارئ v1.1 من دون converter صريح في ADR مستقل.

| من | إلى | الإجراء |
|---|---|---|
| `1.0` | `1.1` | لا silent compatibility. يعاد تشغيل scenario لتوليد artifact v1.1 أو يبنى converter موثق لاحقًا عند requirement حقيقي. |
| `fast.acquisition.recorded` | لا حدث في S0 | لا replacement وهمي؛ M4 فقط قد يضيف producer/schema بإصدار وADR جديدين. |
| حالة حية `PAUSED_BY_SYSTEM` | `runtime.paused_by_system` مسجل | يستهلك replay/evaluator marker، ولا يعرضه client كتعليم أو نتيجة سريرية. |

## Consequences

بعد بدء M3، يلتزم أي Unity client مستقبلي بprojection هذا العقد ولا يعرف Pulse أو state artifact. تغيير event field أو enum أو semantics بعد بدء M3 يفرض **تكلفة إعادة عمل عميل**: تحديث DTO/projection، fixtures، timeline/debrief consumer tests، والتوافق/المigration للـrecordings. لذلك يتطلب أي تغيير ADR سابقًا، traceability matrix محدثة، producer وconsumer tests، وإصدار schema واضح.

لا يعني freeze أن العقد public أو stable خارجيًا، ولا يسمح بتجاوز حدود Gate 0 أو medical review أو إطلاق Unity. ويبقى تغيير المحتوى السريري أو الأكسجة أو التحكم بالنزف خاضعًا لـADR-016 والمراجعة المستقلة.

## References

[1] [Traceability عقد v1.1](../design/s0-event-contract-traceability.md).
[2] [Master Plan v0.3، §11–12 و§24](../governance/nexora_vpe_master_plan_v0.3.md).
[3] [مخطط event envelope v1.1](../../schemas/event-envelope.schema.json).
[4] [اختبارات evaluator/replay](../../tests/test_evidence_evaluator.py) و[قارئ replay](../../src/nexora_vpe/replay.py).
