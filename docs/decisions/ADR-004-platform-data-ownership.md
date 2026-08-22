# ADR-004: ملكية بيانات منصة Nexora

**الحالة:** Accepted as target architecture; PostgreSQL deployment and migrations deferred.  
**التاريخ:** 2026-08-23.

## السياق

تحتاج Nexora إلى PostgreSQL transactional truth، لكن اعتماد Laravel للـControl Plane وGo للـPlatform Plane وPython للمحاكاة يخلق خطر shared-write database anti-pattern. يجب الحفاظ على عزل المستأجرين، outbox موثوق، artifact lifecycle، وanalytics مشتقة من دون جعل cluster مشترك integration mechanism.

## القرار

يظل **PostgreSQL** target OLTP authoritative، ويمكن أن يبدأ كـphysical cluster واحد. لكنه يقسم منطقيًا إلى schemas/tables يملك كل منها service واحد. يكتب كل owner في جداولها فقط؛ لا توجد writes عابرة للخدمة أو reads مباشرة غير موثقة.

| owner | PostgreSQL logical area | يكتب | لا يكتب |
|---|---|---|---|
| Laravel Control Plane | `control_plane.*` | institutions, tenants, users, memberships, RBAC policy, programs/courses/cohorts, assignments, catalog metadata, authoring/admin/billing later, audit | platform session registry، worker lease، simulation state. |
| Go Platform Plane | `platform.*`, `session_registry.*` | session allocation/lifecycle/lease/fencing/routing, platform operational state | Laravel membership/course/billing tables، Python simulation internals. |
| transactional domain owner | owner outbox schema/table | its own immutable domain events/commands in same transaction | another owner's outbox. |
| Python simulation worker | session-local/runtime persistence only by explicit contract | VPE/Pulse session-local data/artifact candidates | users, tenants, memberships, assignments, course/business records. |
| analytics consumers | derived analytics/lake | projections/rollups only | canonical OLTP command truth. |

### Control-to-platform consistency

Laravel commits authorized assignment/start intent plus a **Laravel-owned transactional outbox** record in one transaction. A relay delivers the command at-least-once to Go, which validates/deduplicates and commits Go-owned session registry change plus a Go-owned outcome outbox event. Python receives a trusted Go command or portable event—not a cross-schema SQL privilege.

This avoids `Laravel DB commit + direct Go call` dual-write loss. If relay/queue fails, outbox accumulates/retries. If a command redelivers, Go uses the stable command/event ID. If Go fails after allocation but before response delivery, Laravel may be stale and reconciles by command ID/event; it does not read Go tables directly. The existing SQLite outbox is a reference/test semantics spike only, not an assertion that Python owns production relay.[1]

### Tenant/security rules

Every tenant-owned record carries `tenant_id`, tenant-scoped constraints, audit fields, and explicit authorization context. Laravel owns membership/RBAC policy. Go verifies a scoped session grant and does not trust arbitrary client `tenant_id`. RLS remains a later defense-in-depth candidate after connection role/context/runbook/negative tests; it never replaces application authorization.[2]

### Data technology ownership

| technology | target owner/use | prohibited interpretation |
|---|---|---|
| PostgreSQL/JSONB | transaction truth; JSONB bounded for versioned metadata only | JSONB as unbounded telemetry/history document. |
| Redis/Valkey | owner-scoped cache, rate limit, ephemeral routing/lease optimization | canonical history/tenant policy/physiology truth. |
| Object storage | immutable bytes + hash/classification/retention intent; owner stores authorized reference | object key or bucket as authorization. |
| ClickHouse | derived analytics when `ANL-CH-01` evidence exists | primary truth or command source. |
| S3/Parquet/Iceberg | governed future lake/export when `ANL-LAKE-02`/`ANL-ICE-03` | lake before owner/lineage/lifecycle. |
| DynamoDB/Cassandra | only after `KV-02` access-pattern/consistency evidence | response to generic scale narrative. |
| pgvector/OpenSearch | pgvector first for approved non-clinical retrieval; OpenSearch after trigger | LLM/clinical truth or default search database. |

## alternatives rejected

| alternative | reason |
|---|---|
| all services write a shared public schema | hides coupling, destroys ownership/audit/migration safety. |
| Laravel writes session registry directly | violates Go Platform lifecycle/fencing ownership. |
| Python mutates business tables | creates uncontrolled second business backend. |
| direct shared reads as default integration | turns schemas into unpublished APIs and blocks independent evolution. |
| MongoDB because scenarios are JSON | ignores transaction/constraint/ownership needs. |
| Redis as history | cache failure/eviction semantics conflict with truth. |

## consequences

Any future PostgreSQL implementation needs schema-specific migration ownership, database roles/grants, migration ordering across owners, backup/restore, query/pool monitoring, tenant/RLS tests, outbox relay and reconciliation runbooks. A physical shared cluster is a deployment convenience, not shared ownership. Contract migrations require compatibility and consumer rollout discipline.

## references

[1]: ../validation/transactional-outbox-sqlite-spike.md "Transactional Outbox SQLite Spike"
[2]: https://www.postgresql.org/docs/current/ddl-rowsecurity.html "PostgreSQL: Row Security Policies"
[3]: ../architecture/polyglot-data-and-deployables-v0.1.md "Nexora Polyglot Data Ownership and Deployables"
[4]: ../research/postgres-scale-review.md "Nexora: مراجعة PostgreSQL القابلة للتوسع"
