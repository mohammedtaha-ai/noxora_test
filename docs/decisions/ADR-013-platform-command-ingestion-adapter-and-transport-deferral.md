# ADR-013: Platform Command Ingestion Adapter and Transport Deferral

**Status:** Accepted.  
**Date:** 2026-08-26.

## Context

The Laravel outbox provides an at-least-once portable event but the production broker/transport is deliberately not selected. Phase 1 must prove the Go consumer boundary without treating a development endpoint, Laravel database polling, or a one-off fixture mechanism as the eventual domain architecture.

## Decision

The Go application defines a narrow `EventSource`/ingestion boundary that hands a raw portable event to the command service. Phase 1 provides two non-production implementations only: direct fixture ingestion used by tests and a loopback-only HTTP endpoint used for local diagnostic ingress. Both call the same canonical schema validation and durable allocation flow.

The HTTP adapter defaults to `127.0.0.1:8090`, permits only `POST /internal/test-events/simulation-start`, limits request bodies, has explicit server timeouts, and exposes `/healthz` and `/readyz`. It does not implement end-user authentication, public routing, WebSocket, or a protocol for a future client. It is not a production API.

## Alternatives Considered

| Alternative | Outcome |
|---|---|
| Poll `control_plane.outbox_events` from Go | Rejected; Go must not query Laravel-owned tables. |
| Introduce Kafka/NATS/RabbitMQ/SQS/Redis now | Rejected; no production transport selection or measured requirement exists. |
| Embed direct HTTP controller logic in the session domain | Rejected; transport would leak into allocation logic and make replacement harder. |
| Define gRPC/Protobuf now | Rejected; it adds generated-code/toolchain/API surface with no worker route. |
| Use only an in-memory test call | Rejected; tests use real PostgreSQL and the local adapter proves bounded HTTP handling as well. |

## Consequences

A future broker adapter can receive an envelope and invoke the same service without rewriting session allocation. Phase 1 has no durable outbound acknowledgement to a broker and therefore makes no claim of production delivery completeness. Local HTTP diagnostics must never be exposed through an ingress/load balancer without a separate identity and threat-model decision.

## Security Considerations

The adapter validates maximum event bytes before decoding, rejects malformed JSON/schema/unsupported versions, returns sanitized codes without SQL or stack traces, and binds only to loopback by default. Artifact storage references are treated as opaque metadata, never credentials.

## Scaling Trigger

Revisit when a production event source is chosen, a durable consumer acknowledgment/poison-event policy is required, or multiple Go replicas are planned.

## Revisit Trigger

Revisit before exposing any platform endpoint outside loopback, before adding mutual/service authentication, or before introducing Go-to-Python worker dispatch.

## References

[1] [ADR-009: Laravel Outbox and Platform Command Contract](ADR-009-laravel-outbox-and-platform-command-contract.md).  
[2] [ADR-011: Go Platform Plane — Phase-1 Responsibility Boundary](ADR-011-go-platform-plane-phase-one-responsibility-boundary.md).  
[3] [Go `net/http` documentation](https://pkg.go.dev/net/http).  
[4] [Go platform dependency research](../research/go-platform-dependency-research.md).
