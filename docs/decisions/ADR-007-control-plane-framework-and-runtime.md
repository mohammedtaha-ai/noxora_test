# ADR-007: Laravel Control Plane Framework and Runtime

**Status:** Accepted.  
**Date:** 2026-08-25.

## Context

The accepted Nexora target assigns Laravel/PHP to the business Control Plane, Go to a future platform/realtime plane, Python to VPE/simulation/AI, C++ to Pulse/native numerical work, and C#/Unity to a future client. The verified S0 paths must not be moved or rewritten in this batch.

## Decision

Create `apps/control-plane` as a Laravel 13 application using PostgreSQL for tenant, membership, learning metadata, assignments, simulation start intents, audit, and Laravel-owned outbox data. The application owns only `control_plane.*`; its migration repository is also `control_plane.migrations`. Laravel is a REST JSON Control Plane, not an owner of simulation time, Pulse state, session worker state, or real-time transport.

Laravel Sanctum is used as the smallest first-party API token foundation for development/testing. Laravel policies/gates remain the authorization mechanism. PHP 8.3 is the minimum runtime; local verification uses PHP 8.3 and PostgreSQL 16 because these are locally available, while the architecture research records the current documented PostgreSQL 18 target line.

## Consequences

Laravel can issue durable portable commands through an outbox without invoking future Go as a synchronous source of truth. Moving existing S0 code into `/services` or `/native` is deliberately deferred to a later migration decision. Octane, Redis, queues, brokers, cloud services, and a Go implementation remain deferred.

## References

[Laravel 13 Release Notes](https://laravel.com/docs/13.x/releases) and [Laravel Migrations](https://laravel.com/docs/13.x/migrations).
