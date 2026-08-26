# Nexora Go Platform Plane — Phase 1

This directory contains the **single** Go Platform Plane process introduced by Phase 1. It validates the canonical portable event contracts, stores an idempotent command receipt, allocates a `platform.*` session record, and proves PostgreSQL lease/fencing behavior. It does **not** start Python VPE, call Pulse, advance simulation time, retrieve artifact bytes, provide realtime transport, or expose a public API.

## Configuration

Copy `.env.example` into local environment management without committing credentials. `DATABASE_URL` is required and must be a PostgreSQL URL. `PLATFORM_LISTEN_ADDR` defaults to `127.0.0.1:8090` and is validated as loopback only. `PLATFORM_LEASE_DURATION` defaults to `30s`; `PLATFORM_MAX_EVENT_BYTES` defaults to `1048576` bytes. Set `PLATFORM_REPOSITORY_ROOT` only when invoking the binary from outside the repository tree.

| Variable | Purpose | Phase-1 constraint |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection for `platform.*` only | Required; no `control_plane.*` reads/writes. |
| `PLATFORM_LISTEN_ADDR` | Local diagnostic ingress address | Loopback only; not a public listener. |
| `PLATFORM_LOG_LEVEL` | Structured `slog` threshold | `debug`, `info`, `warn`, or `error`. |
| `PLATFORM_LEASE_DURATION` | Lease interval for a future internal owner | Greater than zero and at most 24h. |
| `PLATFORM_MAX_EVENT_BYTES` | Maximum event request body | Greater than zero and at most 8 MiB. |

## Runbook

Run commands from `apps/platform-plane` after exporting a local/test `DATABASE_URL`.

```bash
go run ./cmd/platform-plane migrate
go run ./cmd/platform-plane
```

The migration command creates/updates only `platform.*` and its Goose version table. The service then exposes loopback-only diagnostic endpoints:

```bash
curl -fsS http://127.0.0.1:8090/healthz
curl -fsS http://127.0.0.1:8090/readyz
curl -i -X POST http://127.0.0.1:8090/internal/test-events/simulation-start \
  -H 'Content-Type: application/json' \
  --data-binary @../../contracts/fixtures/simulation_start_requested_v1.valid.json
```

The first valid fixture delivery returns `201 Created`; replay returns `200 OK` with the same `session_id` and `duplicate: true`. The endpoint is a local/test adapter only. It has no end-user authentication and must not be exposed through public networking, an ingress, or a load balancer.

```bash
# Malformed JSON: 400 / INVALID_EVENT
curl -i -X POST http://127.0.0.1:8090/internal/test-events/simulation-start \
  -H 'Content-Type: application/json' --data '{'

# Oversized body: 413 / PAYLOAD_TOO_LARGE, with default configuration
head -c 1048577 /dev/zero | tr '\0' a | curl -i -X POST \
  http://127.0.0.1:8090/internal/test-events/simulation-start \
  -H 'Content-Type: application/json' --data-binary @-
```

## Data and Delivery Semantics

The Platform Plane validates `schemas/platform-event-envelope.schema.json` and `contracts/events/control.simulation_start.requested.v1.schema.json` at startup, with JSON Schema format assertions enabled. A command is accepted transactionally into `platform.command_receipts` and a session is created in `platform.sessions`. Replaying the same event/command returns the original session. Reusing the event/command identity with different payload or tenant data produces an integrity conflict.

PostgreSQL leases are at-least-once coordination, not exactly-once delivery. Claim/reclaim increments the session generation and rotates the opaque lease token. Renewals and future-worker-route mutations require current owner, token, generation, and non-expired lease predicates. A stale owner is fenced and cannot update a reclaimed session.

## Verification

```bash
PLATFORM_DESTRUCTIVE_TESTS=1 go test -p 1 ./...
PLATFORM_DESTRUCTIVE_TESTS=1 go test -race -p 1 ./...
go vet ./...
govulncheck ./...
```

The integration tests require `PLATFORM_DESTRUCTIVE_TESTS=1` and a `PLATFORM_TEST_DATABASE_URL` whose PostgreSQL database name ends in `_test` and whose host is loopback or the CI `postgres` service. The guard rejects the reset before `DROP SCHEMA` for every other target. They use real PostgreSQL migrations, transactions, concurrent allocation attempts, PostgreSQL-clock lease expiry/reclaim, stale-owner fencing, and the shared contract fixtures. No platform test claims a Docker/broker/VPE/Pulse integration.

## Deferred Work

Production transport/broker selection, authenticated Control Plane service origin, consumer acknowledgements/poison-event policy, worker launch/routing, artifact resolution, VPE/Pulse lifecycle integration, public API/authentication, connection scale, gRPC/Protobuf, OpenTelemetry exporter/backend, tenant RLS governance, Unity, cloud deployment, and clinical/S0 expansion remain explicitly deferred. See ADR-011 through ADR-014.
