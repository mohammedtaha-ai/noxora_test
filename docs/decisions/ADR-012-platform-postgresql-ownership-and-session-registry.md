# ADR-012: Platform PostgreSQL Ownership and Session Registry

**Status:** Accepted.  
**Date:** 2026-08-26.

## Context

The Control Plane database already owns business authorization, scenario versions, assignments, start intents, audits, and outbox events in `control_plane.*`. A Go consumer must preserve at-least-once delivery semantics without sharing those tables or relying on memory for deduplication and session allocation.

## Decision

Phase 1 creates a separate PostgreSQL schema: **`platform`**. Its SQL migrations are owned only by `apps/platform-plane/migrations` and tracked with `platform.goose_db_version`. The schema contains:

| Table | Owner purpose |
|---|---|
| `platform.command_receipts` | Immutable event/command receipt, tenant ownership, payload hash, status, and processed timestamps. |
| `platform.sessions` | Allocated future session registry, immutable execution-manifest references, tenant key, lifecycle state, and monotonic generation. |
| `platform.session_leases` | One current lease per session with owner identity, opaque lease token, lease generation, expiry, and update timestamp. |

The receipt table has unique `event_id` and `command_id` constraints. The session table has unique `event_id` and `command_id` constraints plus tenant-scoped allocation metadata. Inserts and allocation occur in one PostgreSQL transaction under a `pgx` transaction. A redelivery of the same event/command returns the existing session; a mismatching payload hash or incompatible identity is an integrity conflict.

## Alternatives Considered

| Alternative | Outcome |
|---|---|
| Reuse `control_plane.*` or Laravel migrations | Rejected; Go would write Control Plane business storage and violate data ownership. |
| In-memory receipt/session maps | Rejected; a restart or concurrent replica would lose deduplication/fencing evidence. |
| Redis-based registry | Rejected; Phase 1 has no measured need and PostgreSQL already provides transactional constraints. |
| `session_registry.*` schema | Rejected for now; `platform.*` aligns owner/lifecycle tables and keeps a stable future namespace. |

## Consequences

The platform has a durable, independently migratable owner area while remaining logically isolated from Laravel business records. Cross-schema foreign keys to `control_plane.*` are intentionally absent: validated event fields are copied as immutable references. The database connection principal should receive only `USAGE` plus CRUD permissions on `platform.*` in a production rollout; role governance is deferred from this local Phase-1 proof.

## Security Considerations

All platform-authoritative rows carry `tenant_id` where applicable. The platform never accepts an untrusted client-created tenant/session request; it accepts only a validated Control Plane event. The artifact storage reference is retained as metadata and is not interpreted as credentials or authorization.

## Scaling Trigger

Revisit when migrations must run under separate deployment credentials, when tenant RLS governance is explicitly approved, or when session rows need partitioning based on measured retention/load.

## Revisit Trigger

Revisit before a platform service is deployed outside local/test, before direct user requests reach the platform, or before platform data needs external replication/analytics.

## References

[1] [ADR-004: Platform Data Ownership](ADR-004-platform-data-ownership.md).  
[2] [ADR-009: Laravel Outbox and Platform Command Contract](ADR-009-laravel-outbox-and-platform-command-contract.md).  
[3] [ADR-010: Simulation-Start Execution Manifest](ADR-010-simulation-start-execution-manifest.md).  
[4] [pgx v5 documentation](https://pkg.go.dev/github.com/jackc/pgx/v5).
