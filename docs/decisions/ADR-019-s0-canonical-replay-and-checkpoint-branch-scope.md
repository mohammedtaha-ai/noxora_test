# ADR-019: replay الكانوني مقابل checkpoint branch replay في S0

**Status:** Accepted.
**Date:** 2026-08-26.
**Scope:** M6-Headless وS0 Learning Mode فقط؛ لا يضيف durable storage أو خدمة أو client feature.

## Context

يخزن `EvidenceStore` أحداثًا append-ordered وsnapshots خفيفة تصلح لقراءة replay. بينما checkpoint لمحرك Pulse هو artifact خاص بالـadapter، ويحتوي مسار state file محليًا. الاستعادة المختبرة تعمل داخل Runtime قائم فقط. عند استخدام state directory الافتراضي ينشئ `PulseAdapter` مجلدًا مؤقتًا ويحذفه عند `close()`؛ لذلك لا توجد استعادة موثوقة عبر Runtime جديد أو جلسة جديدة.[1]

المسار الكانوني يحتاج قراءة ما سجل بالفعل، لا إعادة تشغيل Pulse. وقد أضيف في M6 قارئ timeline بالزمن المحاكى وevaluator تكويني pure على events/snapshots. هذا يحقق debrief structured من دون جعل artifact محرك محدود العمر وعدًا لميزة branch/retry للمتعلم.[2]

## Decision

> **يُزال checkpoint branch replay عبر runtime restart من نطاق S0.** لا يملك S0 ميزة productية لاستعادة checkpoint أو إنشاء future branch بعد إغلاق Runtime.

| المجال | القرار |
|---|---|
| canonical replay | معتمد لـS0: events + lightweight snapshots → timeline مهيكل بالـsimulation time، مع branch marker عند restore المسجل. |
| evaluator/debrief | معتمد لـS0: findings منظمة وغير مسجلة كدرجات، وإشارات `UNMEASURABLE` صريحة؛ لا LLM ولا narration في هذه الدفعة. |
| checkpoint داخل Runtime قائم | يبقى primitive هندسيًا لتكامل Pulse/debug فقط؛ ليس API للمتعلم أو قدرة S0 معلنة. |
| restart/session جديدة | خارج نطاق S0. لا state directory durable، ولا artifact resolver، ولا credential أو storage policy أو migration. |
| future branch replay | يتطلب ADR جديدًا وحزمة منفصلة: lifecycle artifact durable، سلامة/version binding، access control، retention/delete، restart test، وقرار تعليمي/طبي مستقل. |

## Consequences

يوفر M6 للـdebrief **قراءة timeline ثابتة، ربطًا بالأدلة واللقطات، وfinding تكوينيًا قابلاً للتكرار**. لا يوفر إعادة تنفيذ Pulse أو اقتراح بديل أو simulation counterfactual للمتعلم. لذلك لن يعرض المنتج المستقبلي زر "retry from checkpoint" بوصفه قدرة S0 اعتمادًا على checkpoint in-session وحده.

تنتهي حالة checkpoint عبر restart في capability matrix من `PARTIAL` إلى `OUT_OF_SCOPE FOR S0`، بدل إبقائها فجوة تنفيذ مفتوحة. لا يغير القرار دعم save/restore في الاختبارات القائمة، ولا يدّعي أن artifact لا يمكن جعله durable في مرحلة أخرى.

## References

[1] [PulseAdapter save/restore وstate-directory lifecycle](../../src/nexora_vpe/pulse_adapter.py).
[2] [قارئ canonical replay](../../src/nexora_vpe/replay.py) و[مخطط timeline](../../schemas/canonical-timeline.schema.json).
[3] [Master Plan v0.3، §8 Replay](../governance/nexora_vpe_master_plan_v0.3.md#8-replay).
