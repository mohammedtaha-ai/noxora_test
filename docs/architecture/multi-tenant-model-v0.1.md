# Nexora Multi-Tenant Model v0.1

**الحالة:** target data/authorization model — لا يوجد enterprise SSO أو RLS منشور في هذه الدفعة.  
**الغرض:** جعل العزل والتدقيق وtenant-scoped ownership صريحة قبل توسع المنصة، من دون تغيير مسارات S0 الحالية.

## تعريف tenant والهرمية

الـ**tenant** هو المؤسسة/المنظمة صاحبة نطاق البيانات والسياسات. تحوي المؤسسة برامج، ومقررات، وcohorts، ومتعلمين، وstaff roles. قد تظهر cross-tenant operations إدارية لاحقًا، لكنها لا تعني tenant-less tables ولا access بلا principal context.

```text
Institution / Organization (tenant)
 ├─ Programs
 │   └─ Courses
 │       └─ Cohorts
 │           └─ Learner memberships
 ├─ Staff / tenant roles
 ├─ Scenario catalog visibility
 └─ Assignments ─► scenario-version / session policy
```

| الكيان | owner المنطقي | يحمل `tenant_id` | ملاحظات integrity |
|---|---|---:|---|
| institution/organization | platform/control | نعم، وهو الـtenant root | `tenant_id` هو ID المؤسسة نفسها أو FK صريح وفق schema المختار. |
| program/course/cohort | tenant | نعم | كل FK child يثبت نفس tenant عبر application/database constraints. |
| user identity | platform identity | ليس بالضرورة | identity قد تكون global؛ membership هي boundary. |
| membership/role | tenant + identity | نعم | `UNIQUE (tenant_id, user_id, role_scope)` حسب model. |
| learner profile | tenant-scoped | نعم | لا external global ID كصلاحية دخول. |
| scenario catalog/visibility | platform أو tenant | حسب ownership | global authored scenario لا يرث tenant data؛ tenant custom copy/version يحمل tenant. |
| assignment/session | tenant | نعم | assignment/session يثبتان cohort/learner/scenario version في tenant واحد. |
| artifact/event/audit | tenant when tenant-owned | نعم | null فقط لأحداث platform internal المعتمدة صراحة. |

## identifiers

تستعمل الكيانات العامة وexternal APIs **UUIDv7-style identifiers** أو strategy مكافئة time-sortable distributed. لا تعتمد المنصة على DB-local sequence لإصدار ID خارجي أو routing key. المعرّف opaque؛ لا يعد timestamp في الـUUID authorization signal أو evidence أو ordering كامل.

| ID | المصدر | الغرض | قاعدة الأمان |
|---|---|---|---|
| `tenant_id` | control plane | ownership boundary | مطلوب في data/event tenant-owned. |
| `user_id` | identity service future | identity global | لا يمنح role من دون membership. |
| `membership_id` | control plane | authorization/audit link | immutable historical reference. |
| `session_id` | session registry | worker routing/lease/event key | لا يكشف Pulse ID. |
| `scenario_id` + `scenario_version_id` | catalog | immutable pinning | session لا تتبع authored mutable head. |
| `event_id` | platform envelope | idempotency/dedupe | immutable، لا semantic rewrite. |
| `object_id` | artifact plane | storage reference | يحمي hash/version metadata، وليس direct public URL. |
| `request_id`/`trace_id` | edge/service | correlation | لا يحتوى PII/secrets. |

يعرف RFC 9562 UUIDv7 كـUnix-epoch time-based UUID، ويعرض الحاجة إلى IDs موزعة دون coordination مركزي وتحسين index locality مقارنةً بمعرّفات عشوائية غير مرتبة زمنيًا.[1] تطبيق Python في هذه الدفعة يلتزم بالـlayout والـopacity ولا يدعي monotonic global order.

## authorization flow المستهدف

```text
Authenticated principal
        │
        ▼
Resolve tenant membership + role + scope
        │
        ▼
Authorize command against tenant/course/cohort/session
        │
        ├─ deny: audited access decision / generic error
        └─ allow: tenant-aware command → owning plane
                                  │
                                  ▼
                   typed query/transaction with tenant filter
                   + optional RLS defense-in-depth later
```

لا يظهر authorization logic في Unity client ولا في `tenant_id` supplied blindly من client. يشتق service context tenant/principal من authentication/session token أو trusted internal credential متى أصبح ذلك ضمن scope، ثم يتحقق من membership وrole/scope. لا ينفذ enterprise SSO في هذه الدفعة.

## isolation controls

| الطبقة | control مطلوب | anti-pattern |
|---|---|---|
| API/command | principal + tenant membership + scope authorization | قبول `tenant_id` من caller كحقيقة. |
| ORM/query repository future | mandatory tenant predicate/bound context | query عام ثم filter في الواجهة. |
| database | `tenant_id NOT NULL`، composite uniqueness، tenant-aware FK design، RLS candidate | global unique business key يخلط tenants بلا سبب. |
| event | tenant ID + classification + data minimization | topic per tenant أو payload يحمل PII/Pulse truth. |
| object storage | opaque object ref + metadata authorization + prefix/policy future | public bucket/key كـauthorization. |
| cache | namespaced keys + TTL + tenant identity | cache key بلا tenant أو cached authorization بلا invalidation. |
| analytics/search | tenant filter tested ومعزول كمشتق | derived index يتحول source of truth أو يسرب cohorts. |

RLS في PostgreSQL يمكنه تقييد الصفوف حسب policy، لكنه ليس مفعلًا افتراضيًا وقد تتجاوزه أدوار superuser و`BYPASSRLS` ومالك الجدول؛ ولذلك يبقى application authorization وdatabase role model شرطين سابقين لأي تفعيل.[2]

## constraints وأثر التقسيم

تكون unique constraints ذات المعنى التجاري tenant-scoped، مثل `UNIQUE (tenant_id, course_code)` أو `UNIQUE (tenant_id, external_reference)` حيث تتطلب semantics ذلك. أما UUID primary key فلا يمنع إضافة `tenant_id` إلى FK/query path؛ وجود UUID لا يثبت ownership.

لا تقسم جداول OLTP على `tenant_id` الآن. إذا قُسم جدول زمني لاحقًا، فإن PostgreSQL يقيد unique/primary key على partitioned table بأن يشمل partition key؛ لذا لا بد من فحص constraint design قبل أي partitioning.[3]

## audit وclassification

كل mutation authoritative تحمل، حيث تنطبق، `created_at` و`created_by` و`updated_at` و`updated_by` و`source_request_id` و`correlation_id` و`tenant_id`. الأحداث والأشياء تحمل data classification واحدة على الأقل: `PUBLIC` أو `INTERNAL` أو `RESTRICTED`. لا تعني `RESTRICTED` تلقائيًا أن payload مسموح؛ يبقى مبدأ minimum necessary data، ويمنع secrets وinternal Pulse state وPII غير المصرح بها من platform event envelope.

| التصنيف | أمثلة مقبولة | قواعد التوزيع |
|---|---|---|
| `PUBLIC` | docs/assets مرخصة public | لا تتجاوز copyright/license policy. |
| `INTERNAL` | product telemetry مجمعة، scenario manifest آمن | tenant/role policy، لا public URLs افتراضيًا. |
| `RESTRICTED` | tenant artifact reference، audit metadata مقيدة | access محكوم، retention/deletion/exports policy. |

## RLS adoption gate

| الشرط | حالة هذه الدفعة | المطلوب لاحقًا |
|---|---|---|
| schema tenant-scoped | design only | migration review وcomposite constraints. |
| connection role model | غير موجود | app role ليس owner وليس `BYPASSRLS`. |
| tenant context | غير موجود | transaction-scoped context موثق ومختبر. |
| policy test suite | غير موجود | allow/deny cross-tenant وowner/admin/backup tests. |
| operator runbook | غير موجود | break-glass/audit/export/restore process. |

## عتبات قرار مسماة

| المعرّف | evidence | القرار |
|---|---|---|
| `TENANT-RLS-01` | roles/context/tests/runbook مكتملة ومراجعة تهديدات | enable RLS تدريجيًا. |
| `TENANT-SSO-02` | requirements مؤسسات موثقة (IdP, SCIM, domains, lifecycle) | enterprise SSO/SCIM discovery وADR، لا implementation مسبق. |
| `TENANT-REGION-03` | data residency/contract يحدد boundary وRPO/RTO/legal owner | tenant placement/multi-region design. |
| `TENANT-SEARCH-04` | derived search index يظهر cross-tenant filter risk أو SLO | isolation/indexing benchmark وsecurity test gate. |

## حدود S0

لا تدخل هذه الوثيقة `tenant_id` في S0 scenario schema أو Pulse state أو client DTOs الحالية. أي mapping من S0 local learner shell إلى platform tenant/session لاحقًا يكون adapter عند Control/Data Plane boundary مع اختبارات عدم تسريب، لا تعديل لمعنى scenario أو simulation time.

## المراجع

[1]: https://datatracker.ietf.org/doc/rfc9562/ "RFC 9562: Universally Unique IDentifiers"
[2]: ../research/postgres-scale-review.md "Nexora: مراجعة PostgreSQL القابلة للتوسع"
[3]: https://www.postgresql.org/docs/current/ddl-partitioning.html "PostgreSQL: Table Partitioning"
