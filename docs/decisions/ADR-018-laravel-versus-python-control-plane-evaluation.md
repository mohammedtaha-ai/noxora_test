# ADR-018: تقييم إبقاء Laravel مقابل Python/FastAPI + SQLAlchemy + Alembic

**Status:** Accepted — evaluation only; migration deferred.
**Date:** 2026-08-26.
**Scope:** `apps/control-plane` مستقبليًا فقط. لا يضيف Python web service أو FastAPI أو SQLAlchemy أو Alembic أو migrations في هذه الدفعة.

## Context

لدى المستودع Laravel Control Plane قائم ومجمد بأمر مالك المنتج. السؤال ليس «أي إطار أفضل عمومًا؟»؛ بل هل توجد الآن قيمة مثبتة من تحويله إلى Python كي تشترك طبقة التحكم لغة مع VPE المستقبلية. لا توجد بعد قيمة Gate 0 مثبتة أو مراجعة مستقلة تسمح بتوسيع control plane، ولا توجد حاجة تشغيلية حالية إلى service boundary جديد.[1] [2]

Laravel يوفر Eloquent ORM لكل جدول model وmigrations تصف وتطبق تغييرات schema.[3] [4] البديل المقترح سيضيف FastAPI كطبقة HTTP وSQLAlchemy كـORM وAlembic كبيئة change-management scripts مرتبطة بـSQLAlchemy.[5] هذا البديل ممكن تقنيًا، لكنه ليس هجرة صفرية: بيئة Alembic تتضمن script/configuration وrevision history خاصين بالمشروع.[5]

## الخيارات

| الخيار | الوصف | الموقف |
|---|---|---|
| A — إبقاء Laravel مجمدًا | الحفاظ على `apps/control-plane` الحالي بلا features أو migrations حتى يظهر work ملموس ومبرر. | **المعتمد الآن** |
| B — هجرة كاملة مستقبلية | إيقاف Laravel كمالك control-plane ثم نقل الحدود والبيانات والاختبارات إلى FastAPI + SQLAlchemy + Alembic عبر خطة انتقال مقبولة. | مؤجل؛ لا تنفيذ الآن |
| C — تشغيل الاثنين معًا | Laravel وFastAPI يتشاركان PostgreSQL ويمتلك كل منهما ORM/migration history. | مرفوض كحالة مستقرة |

## المقارنة العملية

| معيار القرار | A — Laravel مجمد | B — هجرة كاملة مستقبلية | لماذا لا يكفي معيار لغة واحد |
|---|---|---|---|
| runtimes وCI | يبقي PHP/Composer وCI قائمين فقط؛ لا يضيف Python web runtime أو dependency set جديدًا. | يضيف Python web runtime، lock/pinning، lint/test/security workflow، وخطة cutover؛ بعد الإزالة قد يقلل runtime واحدًا فقط. | لا توجد فائدة اليوم لأن VPE لا يحتاج control-plane web API. |
| schema/migrations على PostgreSQL | مالك واحد لـmigrations الحالية. | يلزم تعيين owner واحد وخطة baseline/cutover واعتماد Alembic revisions. | Laravel migrations وAlembic كلاهما أدوات تغيير schema؛ لا يجوز أن يديرا قاعدة الإنتاج نفسها استقلاليًا.[4] [5] |
| ORM وحدود البيانات | Eloquent قائم؛ لا mapping ثانٍ أو اختلاف transactions/serialization. | SQLAlchemy mapping واختبارات data access جديدة، ثم إزالة Eloquent من الحدود المنقولة. | وجود ORMين لنفس الجداول يزيد drift ولا يثبت قيمة للمتعلم. |
| security/audit | يظل `composer audit` وpolicy قائمين؛ Composer يدعم audit وتطبيق policy للـadvisories.[6] | يستلزم برنامج security مكافئًا لـPython dependencies وCI وincident ownership؛ لا يصح افتراض أن تغيير اللغة يتحسن أمنيًا بذاته. | الأمن عملية dependencies/configuration/review لا خاصية إطار. |
| language-boundary cost | boundary يبقى Laravel ↔ VPE مستقبلية ولا يُبنى الآن. | قد يقلل PHP↔Python داخل control-plane لاحقًا، لكنه يخلق migration/contract/cutover boundary الآن. | لا يوجد traffic أو worker أو contract يستحق الكلفة الآن. |
| صيانة فريق صغير | أقل surface area في فترة التحقق؛ يحافظ على معرفة وأدوات قائمة. | يصبح مناسبًا فقط إذا أزيل Laravel فعلًا وتم توحيد الملكية والـoperational practice. | تشغيل الاثنين هو الأسوأ: runtimes وORMs وmigration chains وon-call paths متعددة. |

## Decision

> **يبقى Laravel Control Plane مجمدًا؛ لا تبدأ هجرة Python الآن.**

لا يُنشأ FastAPI أو SQLAlchemy أو Alembic في المستودع ولا في بيئة production. لا تُضاف migrations ولا schemas ولا bridges بين Laravel وVPE. الخيار C، أي dual-write أو dual-migrations على PostgreSQL، غير مقبول كتصميم مستقر.

تجوز إعادة فتح القرار فقط بعد: (1) نجاح Gate 0 بمشاركين حقيقيين وفق البروتوكول، و(2) مراجعة طبية/تعليمية مستقلة موثقة، و(3) وجود domain/control-plane requirement محدد لا يلبيه التجميد، و(4) مذكرة انتقال تحتوي owner واحد للـschema، خطة read/write cutover وrollback، export/verification، security parity، costed CI/runbook، وقرار إزالة Laravel أو إبقائه بحدود لا تشارك الجداول.

## Consequences

لا تدّعي هذه ADR أن Laravel هو الاختيار النهائي أو أن FastAPI أقل/أكثر أمانًا. النتيجة ضيقة: **المخاطر والكلفة الفورية للهجرة أو للتشغيل المزدوج غير مبررة قبل إثبات القيمة البشرية ووجود requirement واضح.** لذلك لا يغير هذا القرار كود Laravel، ولا يبدأ Python service، ولا يعد بمسار هجرة أو تاريخ لها.

## References

[1] [الحالة الحالية](../status/CURRENT_STATUS.md).
[2] [خطة تشغيل Gate 0](../gate0/2026-08-26-gate-0-execution-plan.md).
[3] [Laravel Eloquent — Getting Started](https://laravel.com/docs/13.x/eloquent).
[4] [Laravel Database: Migrations](https://laravel.com/docs/13.x/migrations).
[5] [Alembic Tutorial — change-management scripts using SQLAlchemy](https://alembic.sqlalchemy.org/en/latest/tutorial.html).
[6] [Composer configuration — dependency policy and audit](https://getcomposer.org/doc/06-config.md).
