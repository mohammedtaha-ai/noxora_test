# ADR-015: Platform Redelivery Integrity and Schema Readiness

**Status:** Accepted.  
**Date:** 2026-08-26.  
**Scope:** Go Platform Plane Phase 1 only.

## Context

A PostgreSQL-backed command receipt must recognize an actual redelivery without accepting a different semantic command under a reused `event_id` or `command_id`. Separately, `/readyz` must say more than that the database socket is reachable: the Platform Plane cannot perform its Phase-1 responsibility until its own migrations and relations exist.

## Decision

A receipt persists `immutable_envelope_hash`, a SHA-256 canonical JSON hash of this immutable semantic projection:

| Included in immutable identity | Reason |
|---|---|
| `event_id`, `command_id`, `tenant_id` | Delivery and business-command identity/ownership. |
| `event_type`, `schema_version` | Contract semantics. |
| `producer` | Authoritative source identity. |
| `aggregate_type`, `aggregate_id` | Aggregate binding. |
| `routing_key`, `classification` | Ordering/partition and data-handling semantics. |
| Validated `payload` | Command and immutable execution manifest semantics. |

`occurred_at`, `correlation_id`, `causation_id`, and `trace_id` are excluded because they are transport/observability metadata. A delivery that changes only these fields can return the original allocation. Any mismatch of the stored immutable hash returns `EVENT_INTEGRITY_CONFLICT`. Existing legacy receipts without this field are intentionally **not** treated as safe duplicates.

The repository uses PostgreSQL `clock_timestamp()` for lease creation, expiry comparison, reclaim, renewal, and route fencing. Go provides only a validated duration in microseconds; it does not supply an expiry timestamp or compare application wall time with a stored lease timestamp. PostgreSQL documents `clock_timestamp()` as changing during statement execution, unlike transaction-start `now()`/`current_timestamp`, which makes the check appropriate for this short current-time predicate.[1]

`PENDING_WORKER` is the only lease-eligible Phase-1 session state. `REQUESTED`, `FAILED`, and `CANCELLED` cannot claim, renew, or mutate a future-worker route. Repository predicates enforce this behavior and `platform` triggers reject direct lease insertion for terminal states.

`/readyz` first checks reachability and then verifies `platform.goose_db_version` with applied version at least `3`, plus the required `command_receipts`, `sessions`, and `session_leases` relations. Goose is reused as the existing incremental SQL migration mechanism; no custom migration/version infrastructure is introduced.[2]

## Consequences

The Platform Plane remains at-least-once and duplicate-aware, not exactly-once. Broker delivery, service authentication, worker launch, artifact retrieval, realtime transport, VPE/Pulse ownership, and production database role governance remain deferred. This ADR introduces no worker and no additional state such as `RUNNING`.

## References

[1] [PostgreSQL Date/Time Functions — current time semantics](https://www.postgresql.org/docs/current/functions-datetime.html).  
[2] [Pressly Goose — SQL migration overview](https://pressly.github.io/goose/).
