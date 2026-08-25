# ADR-010: Simulation-Start Execution Manifest

**Status:** Accepted.  
**Date:** 2026-08-26.

## Context

A future Go Platform Plane must consume an authorized simulation-start command without querying Laravel's PostgreSQL tables directly. The command therefore needs a complete, immutable execution reference at authorization time. Scenario artifacts are already represented as immutable identifiers, SHA-256 integrity values, content metadata, classification, and storage references; artifact bytes must remain outside relational rows and event payloads.[1]

Two designs were considered. **Option A** freezes an execution manifest inside `control.simulation_start.requested`. **Option B** sends only an intent ID and requires the future Platform Plane to fetch a manifest synchronously from a new Control Plane internal API. Option B would introduce a runtime dependency and a new availability/authorization boundary before a simulation can start.

## Decision

Nexora adopts **Option A**. Laravel validates the generic event envelope and the event-specific payload JSON Schema, then writes the immutable execution manifest in the PostgreSQL outbox transaction. The manifest contains only the following execution references: a manifest version, scenario-contract version, runtime-contract version, `vpe-runtime-owned` time authority, and the artifact identifier, SHA-256, content type, byte length, classification, and storage reference. It contains no artifact bytes, bearer credentials, Pulse state, raw physiology, or client-supplied execution configuration.[2]

A published scenario version is eligible for simulation start only when that immutable data is present and schema-valid. The database lifecycle trigger prevents changes to published and retired execution content; `published → retired` is the sole permitted lifecycle transition. The future Go consumer receives the command from the outbox transport and obtains artifact bytes through a separately authorized artifact-access mechanism. It does not receive direct PostgreSQL access, and this ADR does not implement Go, an internal manifest API, object storage, or a message broker.

| Concern | Decision |
|---|---|
| Start authorization | Laravel membership, policy, and Sanctum ability checks occur before manifest creation. |
| Immutable reference | The outbox payload copies the published version's artifact and runtime metadata inside the same transaction as the intent and audit record. |
| Integrity | The consumer validates the SHA-256 after authorized artifact retrieval; a mismatched artifact must not execute. |
| Delivery | Outbox delivery remains at least once; consumers deduplicate with `event_id` or `command_id` as defined by ADR-009.[3] |
| Runtime ownership | The manifest explicitly records `vpe-runtime-owned`; it does not grant a client or HTTP reader access to Pulse. |

## Consequences

This design permits an independently deployed future Platform Plane to execute a fully identified scenario version without a direct database reach-in or a synchronous Control Plane round trip. It also makes an authorization-time decision auditable and reproducible from the command payload. Changing the manifest requires a new event schema version and a new scenario version, rather than mutating published content.

The chosen contract does not solve artifact availability, consumer authorization, branch replay, exactly-once delivery, or runtime recovery. Those concerns remain explicit future work and cannot be implied by the presence of a manifest.

## References

[1] [Object storage contract v0.1](../contracts/object-storage-contract-v0.1.md).  
[2] [Simulation-start payload JSON Schema](../../contracts/events/control.simulation_start.requested.v1.schema.json).  
[3] [ADR-009: Laravel Outbox and Platform Command Contract](ADR-009-laravel-outbox-and-platform-command-contract.md).
