# ADR-020: تجميد عقد أحداث S0 v1.1 بعد traceability تكويني

**Status:** Accepted.
**Date:** 2026-08-26.
**Scope:** Python S0 canonical evidence/replay contract فقط؛ لا Unity أو transport أو Laravel/Go schema.

## Context

كان event contract v1.0 يسجل events وsnapshots لكن بلا consumer يثبت أن حقوله تكفي لـrubric/debrief. يفرض Master Plan v0.3 أن تسبق متطلبات assessment تجميد schema وأن يحمل كل field سبب تعلم أو evidence. أضاف M6 evaluator deterministic وcanonical replay reader، ثم طبق matrix traceability على كل event type/field وsnapshot field.[1] [2]

أظهر pass traceability أن `fast.acquisition.recorded` لا يملك producer **في M6 الحالي**. كان حذفه سيصطدم بخطة v0.3 وDEC-009: FAST probe placement هي التفاعل المكاني الإلزامي الوحيد في S0، وM4—وهو داخل S0—ينهي السلسلة بـstructured evidence event. وفي المقابل كان `PAUSED_BY_SYSTEM` قابلًا للوصول كحالة حية، لا كدليل مسجل؛ لذا لا يمكن replay/evaluator من معرفة أن command انتهى ambiguity مع تجميد الزمن.[1] [2]

تختار هذه الدفعة التصحيحية **Option A**: حجز FAST event داخل v1.1 الآن، بدل التخطيط لكسر v1.2 في نافذة تكلفة إعادة عمل العميل بعد M3. لا يضيف الحجز Anatomy Target Resolver أو spatial input أو observation generation أو producer M4.

## Decision

| القرار | تفاصيله |
|---|---|
| إصدار العقد | `SCHEMA_VERSION` ينتقل من `1.0` إلى `1.1`، و`schemas/event-envelope.schema.json` يفرض `1.1`. |
| FAST محجوز لـM4 | `fast.acquisition.recorded` موجود في enum/schema v1.1 بحالة `RESERVED` و`current_production=false`. يستهلكه evaluator عندما يوجد مستقبلًا؛ حتى ذلك الوقت يصدر `fast_acquisition` كـ`UNMEASURABLE`، لا absent ولا out-of-scope. |
| إضافة لازمة لـreplay | يضاف `runtime.paused_by_system` مع `payload.reason` عندما يجمد Runtime الزمن لحماية ambiguity أو host failure. ليس event سريريًا ولا grade. |
| consumer freeze | evaluator وreplay reader هما consumerان مرجعيان للعقد. findings تبقى evidence/`UNMEASURABLE` فقط، بلا score أو pass/fail. |
| client boundary | **هذا هو العقد الذي يستهلكه عميل Unity المستقبلي عبر projection آمنة، لا وصول مباشر إلى Pulse.** |

## Migration

لا توجد migration قاعدة بيانات أو event bus أو public API في هذه الدفعة. `EvidenceStore.validate_event` يرفض v1.0 لمنع تفسير التسجيل القديم كأنه يملك semantics v1.1. raw artifacts السابقة محفوظة كدليل تاريخي، لكن لا تُحمّل داخل قارئ v1.1 من دون converter صريح في ADR مستقل.

| من | إلى | الإجراء |
|---|---|---|
| `1.0` | `1.1` | لا silent compatibility. يعاد تشغيل scenario لتوليد artifact v1.1 أو يبنى converter موثق لاحقًا عند requirement حقيقي. |
| `fast.acquisition.recorded` المحجوز | producer M4 مستقبلي | لا schema bump لمجرد بدء M4: يلزم فقط producer `future_fast_resolver` وtests للـvalid/invalid acquisition وconsumer evidence. أي تغيير في payload semantics أو enum يظل ADR/schema change مستقلًا. |
| حالة حية `PAUSED_BY_SYSTEM` | `runtime.paused_by_system` مسجل | يستهلك replay/evaluator marker، ولا يعرضه client كتعليم أو نتيجة سريرية. |

## Consequences

بعد بدء M3، يلتزم أي Unity client مستقبلي بprojection هذا العقد ولا يعرف Pulse أو state artifact. تغيير event field أو enum أو semantics بعد بدء M3 يفرض **تكلفة إعادة عمل عميل**: تحديث DTO/projection، fixtures، timeline/debrief consumer tests، والتوافق/المigration للـrecordings. حجز FAST event في v1.1 يخفض هذه الكلفة عند M4 لأنه يثبت enum وprojection shape مسبقًا؛ لكنه لا يعفي producer M4 من tests أو من ADR إذا تغيّرت semantics/payload. أي تغيير لاحق يتطلب ADR سابقًا، traceability matrix محدثة، producer وconsumer tests، وإصدار schema واضح.

لا يعني freeze أن العقد public أو stable خارجيًا، ولا يسمح بتجاوز حدود Gate 0 أو medical review أو إطلاق Unity. ويبقى تغيير المحتوى السريري أو الأكسجة أو التحكم بالنزف خاضعًا لـADR-016 والمراجعة المستقلة.

## References

[1] [Traceability عقد v1.1](../design/s0-event-contract-traceability.md).
[2] [Master Plan v0.3، §4C و§11–12 و§24](../governance/nexora_vpe_master_plan_v0.3.md) و[DEC-009](../governance/nexora_vpe_decisions_DEC-007_to_DEC-011.md#decision).
[3] [مخطط event envelope v1.1](../../schemas/event-envelope.schema.json).
[4] [اختبارات evaluator/replay](../../tests/test_evidence_evaluator.py) و[قارئ replay](../../src/nexora_vpe/replay.py).
