# ADR-011: Go Platform Plane — Phase-1 Responsibility Boundary

**Status:** Accepted.  
**Date:** 2026-08-26.

## Context

Laravel Control Plane authorizes a durable simulation-start intent and publishes the immutable portable event defined by ADR-009 and ADR-010. The platform needs a narrow receiving boundary that can deduplicate at-least-once delivery and allocate a future session without requiring Go to read `control_plane.*`, call Pulse, or act as a simulation runtime.

## Decision

Phase 1 introduces **one Go deployable** under `apps/platform-plane/`. It receives only `control.simulation_start.requested` version 1 through a local/test ingestion adapter, validates the canonical repository JSON Schemas, records the command, and allocates a platform-owned session in `platform.*`.

The Go Platform Plane owns only command receipt/deduplication, the truthful allocation state machine (`REQUESTED → PENDING_WORKER`, plus `FAILED` and `CANCELLED`), session registry metadata, PostgreSQL leases/fencing, future worker route metadata placeholders, health/readiness, and structured diagnostics. `PENDING_WORKER` is intentionally not `RUNNING`: no VPE worker or physiology process exists in this milestone.

## Alternatives Considered

| Alternative | Outcome |
|---|---|
| Let Laravel allocate future runtime state | Rejected; it mixes Control Plane authorization records with Platform lifecycle ownership. |
| Have Go query or write `control_plane.*` | Rejected; it violates owner boundaries and creates direct coupling to Laravel schema. |
| Start Python VPE/Pulse from Go now | Rejected; worker lifecycle integration is a later milestone; VPE/Pulse retain simulation authority. |
| Add a broker, WebSocket gateway, or public API | Rejected; there is no measured Phase-1 requirement and the local adapter demonstrates only the boundary. |
| Defer Go completely | Rejected; Phase 1 needs a tested consumer-side allocation/fencing contract before worker integration. |

## Consequences

The platform can prove durable session-allocation semantics while remaining unable to advance physiology, access artifact bytes, or start a worker. Laravel remains the owner of authorization/business records and Python VPE remains the future orchestration authority. A production transport, worker launch, service identity, artifact resolver, connection scale, and realtime client API remain deferred.

## Security Considerations

The local ingress binds loopback only, uses bounded bodies/timeouts, produces sanitized structured errors, and is explicitly not public authentication. The event `tenant_id` is trusted only as a validated Control Plane event attribute, not as a credential. Logs contain identifiers and lifecycle metadata only; they do not log payload secrets, artifact credentials, physiology, or medical hidden truth.

## Scaling Trigger

Revisit when a measured need exists for multiple platform replicas, a durable production event transport, or worker-route dispatch. Those needs require a separate transport/service-identity/operational design rather than widening this process opportunistically.

## Revisit Trigger

Revisit before any Python VPE worker orchestration, external client ingress, Pulse access, simulation-clock integration, public realtime endpoint, or gRPC boundary.

## References

[1] [ADR-009: Laravel Outbox and Platform Command Contract](ADR-009-laravel-outbox-and-platform-command-contract.md).  
[2] [ADR-010: Simulation-Start Execution Manifest](ADR-010-simulation-start-execution-manifest.md).  
[3] [Portable event envelope schema](../../schemas/platform-event-envelope.schema.json).  
[4] [Simulation-start payload schema](../../contracts/events/control.simulation_start.requested.v1.schema.json).
