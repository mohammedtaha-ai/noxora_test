# ADR-009: Laravel Outbox and Platform Command Contract

**Status:** Accepted.  
**Date:** 2026-08-25.

## Context

`RequestSimulationStart` is a cross-plane business operation. Calling a future Go service synchronously after a business database write would create a dual-write failure mode. The repository already defines a portable, language-neutral event envelope in `schemas/platform-event-envelope.schema.json`; the existing Python SQLite outbox is semantic reference only.

## Decision

Laravel atomically writes a `simulation_start_intents` business row, a `control.simulation_start.requested` outbox row, and an audit row in one PostgreSQL transaction. Outbox events use UUIDv7 identities, schema version, tenant/aggregate/routing context, classification, minimal JSONB payload, correlation ID, causation ID, claim state, publication state, and attempt count. The serialized shape conforms to the portable schema rather than inventing a PHP-only event format.

A narrow local relay claims unclaimed rows using row locking, invokes an injected publisher, marks success, or clears the claim after recording an error. Delivery is **at least once**; consumers must deduplicate by `event_id` or `command_id`. No SQS, Kafka, Redis, or production Go relay is deployed in this batch.

`Idempotency-Key` is the UUID business retry identity, unique per requester and fingerprinted with assignment/scenario version. Repeating the same key returns the same start intent and command identity; reuse with a changed intent is rejected. `X-Request-Id` and `X-Correlation-Id` are separate UUID transport tracing identifiers and are retained for audit, not deduplication.

## Consequences

A future Go consumer can be added without changing the business transaction. Exactly-once end-to-end delivery is not claimed. Event payloads exclude tokens, passwords, secrets, raw profiles, runtime physiology, and artifact bytes. The immutable execution reference for `control.simulation_start.requested` is specified by [ADR-010](ADR-010-simulation-start-execution-manifest.md).

## References

[Laravel Queues](https://laravel.com/docs/13.x/queues), [PostgreSQL Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html), and [`platform-event-envelope.schema.json`](../../schemas/platform-event-envelope.schema.json).
