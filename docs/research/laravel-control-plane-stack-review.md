# Laravel Control Plane Stack Review

**Date:** 2026-08-25.  
**Purpose:** establish a reviewed baseline for the Laravel Control Plane Foundation only. This review does not authorize Go Platform Plane, Unity, cloud deployment, or a rewrite of the verified Python VPE.

## Decision summary

| Concern | Evidence-based decision for this batch | Explicitly deferred |
|---|---|---|
| Framework/runtime | Laravel `^13.0` on PHP 8.3 minimum; local Docker uses PHP 8.3 because it is available in the verification environment. | Laravel Octane, resident worker runtime tuning. |
| Authoritative database | PostgreSQL integration tests run against a real local PostgreSQL server. The supported local package is PostgreSQL 16; the target architecture's then-current PostgreSQL documentation is version 18. The schema uses portable PG features that are supported by both. | Managed database and cloud provisioning. |
| Authentication | Laravel Sanctum personal access tokens for narrow development/testing API authentication. Token abilities do not replace membership-aware policies. | Enterprise SSO, SAML, OIDC federation, login UI. |
| Authorization | Laravel policies/gates with authenticated user + membership-derived tenant authorization. Client `tenant_id` is never authorization input. | Configurable permissions engine. |
| Data isolation | Application authorization first plus a small, separately tested PostgreSQL RLS spike. RLS is not the baseline access-control mechanism. | RLS rollout until connection/role/background-worker context is designed and tested. |
| Outbox | Laravel-owned PostgreSQL transactional outbox with claim/publish/mark/retry relay contract and at-least-once semantics. | SQS, Redis, Kafka, production Go relay. |
| Queue/pooling | Laravel's built-in facilities are researched but are not adopted as an outbox substitute. | Queue infrastructure and PgBouncer; introduce only with an operational trigger. |
| JSONB | Bounded metadata, audit metadata and minimal portable event payloads only. | telemetry, session history and large scenario blobs. |
| Tests | PHPUnit feature/integration tests plus actual PostgreSQL migrations and transaction assertions. | SQLite-only proof for PostgreSQL behaviors. |

## Findings

Laravel 13 is the current stable major release in the official documentation, released on 2026-03-17. Its supported PHP range is 8.3–8.5 and it requires PHP 8.3 at minimum.[1] The scaffold therefore uses a Laravel 13-compatible dependency constraint and avoids third-party packages when Laravel capabilities are sufficient.

Laravel provides gates for non-resource-centric authorization and policies for resource/model authorization. The control plane uses policies for assignments, scenarios, and start intents, with membership as the tenant-authority source.[2] Sanctum supports API tokens with abilities and `auth:sanctum`; its documentation also makes clear that resource authorization remains a separate policy concern.[3]

Laravel migrations support PostgreSQL connections and offer `jsonb` and UUID relationship column types. PostgreSQL-specific schema operations used in this foundation—such as `CREATE SCHEMA`, CHECK constraints, partial indexes, and the RLS spike—are deliberately placed in Laravel-owned migrations rather than disguised as portable behavior.[4]

The current PostgreSQL documentation is version 18. PostgreSQL documents Read Committed as the default isolation level and documents the concurrency behavior of `INSERT ... ON CONFLICT`; nevertheless idempotency here is protected with unique constraints and a request fingerprint, not by isolation alone.[5] PostgreSQL documents `jsonb` as indexable and generally appropriate for JSON processing, but warns that updating a JSON document locks the whole row; this constrains JSONB use to bounded documents.[6]

RLS is not enabled by default in PostgreSQL. With RLS enabled and no policy, normal table access is default-deny, while superusers, `BYPASSRLS` roles and normally the table owner bypass policies. Therefore policies cannot substitute for Laravel authorization and are treated as a safety-in-depth spike only.[7]

Laravel queues have database, SQS, Redis and other drivers, but a queue is not a proof that a business mutation and an external message have one atomic commit. The implementation stores business intent plus outbox command in one PostgreSQL transaction and keeps relay delivery at-least-once.[8] Laravel's test stack includes PHPUnit/Pest and feature tests; this foundation uses PHPUnit, real PostgreSQL and feature-style HTTP tests.[9]

Octane persists the Laravel application in memory and has specific request/container state caveats. No measured need exists in this batch, so it is researched but not installed.[10] PgBouncer is a PostgreSQL connection pooler but is deferred until evidence requires pooling and transaction/session tenant context is specified.[11]

## Branch baseline

This branch is `manus/control-plane-foundation`, created from accepted commit `b5054e5deba1ad3fdac2664cad8a2720038c6777` on `manus/s0-foundation`. Existing Python/Pulse paths are not moved or modified by this batch.

## References

[1]: https://laravel.com/docs/13.x/releases "Laravel 13.x Release Notes"
[2]: https://laravel.com/docs/13.x/authorization "Laravel 13.x Authorization"
[3]: https://laravel.com/docs/13.x/sanctum "Laravel 13.x Sanctum"
[4]: https://laravel.com/docs/13.x/migrations "Laravel 13.x Database Migrations"
[5]: https://www.postgresql.org/docs/current/transaction-iso.html "PostgreSQL Transaction Isolation"
[6]: https://www.postgresql.org/docs/current/datatype-json.html "PostgreSQL JSON Types"
[7]: https://www.postgresql.org/docs/current/ddl-rowsecurity.html "PostgreSQL Row Security Policies"
[8]: https://laravel.com/docs/13.x/queues "Laravel 13.x Queues"
[9]: https://laravel.com/docs/13.x/testing "Laravel 13.x Testing"
[10]: https://laravel.com/docs/13.x/octane "Laravel 13.x Octane"
[11]: https://www.pgbouncer.org/usage.html "PgBouncer Usage"
