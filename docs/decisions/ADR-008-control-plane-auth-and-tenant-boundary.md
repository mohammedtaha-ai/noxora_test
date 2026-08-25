# ADR-008: Control Plane Authentication and Tenant Boundary

**Status:** Accepted.  
**Date:** 2026-08-25.

## Context

A person may belong to multiple institutions. A tenant identifier supplied by a client cannot be accepted as proof of authority. PostgreSQL RLS is powerful but has owner, superuser, `BYPASSRLS`, transaction-context, and background-worker implications.

## Decision

Use Laravel Sanctum for development/testing API authentication. Resolve tenant authority from an active `tenant_memberships` record for the authenticated user. `X-Tenant-Id` is only a requested context selector and must be checked against this membership before every tenant-scoped query or command. Initial roles are `learner`, `instructor`, `tenant_admin`, and `platform_admin`; Laravel policies/gates hold the operation-level rules. No enterprise SSO, SAML, federation, or generic permission engine is included.

The baseline is **application authorization only**, reinforced by foreign keys, tenant columns, tenant-scoped unique constraints, scoped queries, feature tests, and audit. A small PostgreSQL RLS spike is retained as documented evidence only. It uses `SET LOCAL app.tenant_id` and `FORCE ROW LEVEL SECURITY` on an isolated spike table. RLS is not applied to production Control Plane relations until roles, pooling, migrations, background jobs, and bypass behavior have a tested runbook.

## Consequences

Cross-tenant denial is testable at the API and service level even when a caller supplies another tenant UUID. A later RLS rollout must preserve Laravel policy checks and add service-role/connection-pool governance; it cannot silently replace authorization.

## References

[Laravel Authorization](https://laravel.com/docs/13.x/authorization), [Laravel Sanctum](https://laravel.com/docs/13.x/sanctum), and [PostgreSQL Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).
