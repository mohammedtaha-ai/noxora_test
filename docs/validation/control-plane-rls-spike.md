# Control Plane PostgreSQL RLS Spike

**Status:** Executed as a local PostgreSQL integration test; not enabled for Control Plane production tables.  
**Decision:** **APPLICATION AUTHORIZATION ONLY FOR NOW**. See ADR-008.

## Scope

`tests/Feature/ControlPlane/RlsSpikeTest.php` creates a temporary `control_plane.rls_spike_records` table during the test. It enables RLS, applies `FORCE ROW LEVEL SECURITY`, and creates a policy keyed by `current_setting('app.tenant_id', true)`. The test then demonstrates three properties.

| Condition | Observed result | Interpretation |
|---|---|---|
| No transaction tenant context | zero visible rows | Enabled RLS with no matching policy context is default-deny for normal access. |
| `SET LOCAL app.tenant_id = tenant A` | only tenant A row | Context-based filtering works inside one transaction. |
| `SET LOCAL app.tenant_id = tenant B` | only tenant B row | Tenant A context does not expose tenant B rows. |

The test uses `FORCE ROW LEVEL SECURITY` deliberately because PostgreSQL table owners normally bypass RLS. PostgreSQL superusers and roles with `BYPASSRLS` retain broader bypass implications; the spike does not make them safe.[1]

## Why it is not baseline

The shipped Control Plane uses authenticated Laravel membership checks, tenant-scoped queries, foreign keys, unique constraints, database ownership tests, and audit. Adopting RLS for real tables requires a reviewed design for connection pooling, transaction context reset, service roles, migrations, background relays, backups, and negative tests. RLS would be defense in depth, never a replacement for Laravel policies.

## Evidence

The executed Laravel PostgreSQL suite includes the RLS spike alongside tenant isolation, outbox atomicity, idempotency, and database ownership tests. It is a local verification result, not a production security certification.

## Reference

[1]: https://www.postgresql.org/docs/current/ddl-rowsecurity.html "PostgreSQL Row Security Policies"
