# Governance provenance

هذا المجلد يحفظ نسخًا ثابتة داخل المستودع من مراجع الحوكمة التي زودها مالك المشروع عبر ملفات المشروع المشتركة. النسخ هنا **مرجعية فقط**؛ لا تحول حالة أي وثيقة من `Proposed` إلى `Accepted`، ولا تلغي ADRs اللاحقة أو قرارات المالك الموثقة في المستودع.

| الملف داخل المستودع | مصدر النسخ وقت الإدخال | SHA-256 للنسخة داخل المستودع | ملاحظة الحالة |
|---|---|---|---|
| `nexora_vpe_master_plan_v0.3.md` | `/home/ubuntu/.manus/config/project-file/nexora_vpe_master_plan_v0.3.md` | `edadb7b11f8b761c66fe7620eaea3c15231e6b96a3d7a62c35b8cd1713847472` | الوثيقة نفسها تقول `Status: Proposed for review`. |
| `nexora_vpe_decisions_DEC-007_to_DEC-011.md` | `/home/ubuntu/.manus/config/project-file/nexora_vpe_decisions_DEC-007_to_DEC-011.md` | `0296a48db2543832a479aa27c11bce5a8b444b68070ef6cbf640af696b31a475` | تبقى القرارات كما صيغت في المصدر. |

تم النسخ حرفيًا في 2026-08-26. عند تحديث أي من الوثيقتين المصدرية، يجب إجراء تغيير مراجَع داخل هذا المجلد وتحديث hash وهذا السجل؛ لا يجوز ربط وثائق حوكمة repository بمسار إعدادات خارجي متغير.
