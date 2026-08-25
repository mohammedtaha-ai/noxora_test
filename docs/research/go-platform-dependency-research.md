# Go Platform Plane — Dependency Research Notes

**Status:** Working evidence for Phase 1; final decision will be recorded in ADRs and Report 010.

## PostgreSQL and JSON Schema

`github.com/jackc/pgx/v5` is a native PostgreSQL driver/toolkit with a concurrency-safe `pgxpool`, context-aware connection/query/transaction APIs, PostgreSQL-specific features, tracing/logging hooks, MIT license, and documented stable v5 semantic-version policy.[1] This fits the Phase-1 requirement for PostgreSQL-only platform ownership and explicit lease transactions.

`github.com/santhosh-tekuri/jsonschema/v6` compiles schemas according to their `$schema`, supports Draft 2020-12, and exposes `Compiler.AssertFormat()` with built-in UUID and date-time format checks. The package is Apache-2.0 licensed and its project reports coverage of the JSON Schema Test Suite (excluding optional tests).[2] The intended use is to compile repository-root canonical schemas at startup; it prevents a hand-written Go-only interpretation.

## Migrations

Goose v3 is MIT licensed, provides both a CLI and a library, manages incremental SQL migrations, supports context-aware migration APIs, and allows a custom version table name for a non-public schema.[3] `golang-migrate/migrate` is an alternative with an MIT license, stable v4 API, PostgreSQL/PGX v5 driver support, and filesystem/iofs sources.[4] Phase 1 prefers **Goose with SQL-only migrations** because it retains repository-visible SQL, can use `platform.goose_db_version`, and avoids custom runner logic. No Go migrations or data migrations are needed.

## HTTP, logging, telemetry, and security

The Go standard library `net/http` supplies server/handler primitives, request-context propagation, request body limits through `MaxBytesReader`, explicit server read/write/idle timeouts, and graceful `Server.Shutdown`.[5] It is adequate for a loopback-only test ingress; no third-party router is justified. `log/slog` is the standard structured logger with contextual key-value attributes and JSON output.[6]

OpenTelemetry Go has stable traces and metrics, while logs remain beta.[7] Phase 1 will expose a minimal internal diagnostics interface and use `slog`; it will not deploy an SDK exporter, collector, or backend. The official Go vulnerability tooling documents `govulncheck ./...` as the code-aware dependency scan to run in CI.[8]

## References

[1] [pgx v5 package documentation](https://pkg.go.dev/github.com/jackc/pgx/v5).  
[2] [santhosh-tekuri/jsonschema v6 package documentation](https://pkg.go.dev/github.com/santhosh-tekuri/jsonschema/v6) and [repository](https://github.com/santhosh-tekuri/jsonschema).  
[3] [Goose documentation](https://pressly.github.io/goose/) and [Goose v3 package](https://pkg.go.dev/github.com/pressly/goose/v3).  
[4] [golang-migrate repository](https://github.com/golang-migrate/migrate).  
[5] [Go `net/http` documentation](https://pkg.go.dev/net/http).  
[6] [Go `log/slog` documentation](https://pkg.go.dev/log/slog).  
[7] [OpenTelemetry Go documentation](https://opentelemetry.io/docs/languages/go/).  
[8] [Go Vulnerability Management](https://go.dev/doc/security/vuln/).

## UUID

`github.com/google/uuid` v1.6.0 is BSD-3-Clause licensed, widely imported, exposes parse/validation APIs and includes UUIDv7 generation.[9] `github.com/gofrs/uuid/v5` is a maintained MIT alternative with RFC 9562 support and UUID versions 1–8, but its documented Go requirement is Go 1.25 or later.[10] Phase 1 chooses **google/uuid v1.6.0** for parsing the externally supplied contract IDs and for locally generated session/lease IDs: it is adequate for the current repository Go toolchain and does not require custom parsers. IDs arriving in canonical events remain schema-validated as UUIDv7 first; parsing is a typed boundary safeguard.

[9] [google/uuid package](https://pkg.go.dev/github.com/google/uuid) and [repository](https://github.com/google/uuid).  
[10] [gofrs/uuid repository](https://github.com/gofrs/uuid).

## Internal RPC

gRPC-Go is a mature Apache-2.0 RPC implementation, but its normal flow introduces `protoc`, Go generator plugins, `.proto` definitions, and generated client/server code.[11] The current authoritative cross-language contract is already JSON Schema and Phase 1 has no worker route to call. Therefore gRPC/Protobuf is **DEFERRED**: a future trusted Go-to-Python worker command boundary may evaluate it only after a concrete worker orchestration milestone.

[11] [gRPC Go quick start](https://grpc.io/docs/languages/go/quickstart/), [gRPC-Go package](https://pkg.go.dev/google.golang.org/grpc), and [Protobuf Go generated-code guide](https://protobuf.dev/reference/go/go-generated/).

## Decision Matrix

| Area | Decision | Phase-1 outcome |
|---|---|---|
| HTTP ingress/routing | **REUSE** standard `net/http` | Loopback-only bounded local/test ingress and `/healthz`, `/readyz`; no Gin/Fiber/Chi/Echo. |
| PostgreSQL access | **REUSE** `pgx/v5` | `pgxpool`, explicit context-bounded transactions, native PostgreSQL errors and a platform-only schema. |
| JSON Schema | **REUSE** `santhosh-tekuri/jsonschema/v6` | Compile canonical root schemas, enable format assertion, and validate generic envelope plus type-specific payload. |
| PostgreSQL migrations | **REUSE** Goose v3 | SQL-only migrations under `apps/platform-plane/migrations` with `platform.goose_db_version`; no thin custom runner. |
| UUID | **REUSE** `google/uuid` | Typed boundary parsing plus generated session/lease identifiers; never custom UUID code. |
| Diagnostics | **REUSE** `log/slog`; **WRAP** internal diagnostic interface | JSON structured logs and a small no-op/OTel-compatible interface; no exporter/backend. |
| OpenTelemetry | **DEFER** SDK/exporter | Preserve context and diagnostic boundary only; no collector, backend, or cloud configuration. |
| Internal RPC | **DEFER** gRPC/Protobuf | No worker process exists and canonical JSON Schema is the source of truth for this milestone. |
| Transport/broker | **IMPLEMENT** a narrow in-process/local HTTP test adapter | No production broker and no Laravel table polling. |
| Session allocation/state/lease | **IMPLEMENT** narrow domain logic | PostgreSQL-backed receipts, sessions, and lease fencing only; no simulation orchestration. |
| Security scan | **REUSE** `govulncheck` | Run after module creation and add to Go CI. |

## Toolchain

The sandbox initially had no Go binary. Go **1.27.0** for Linux/amd64 was installed from the official release archive only after SHA-256 verification against the value published by Go.[12] The repository will declare `go 1.27.0`; no toolchain archive or binary is committed.

[12] [Go downloads](https://go.dev/dl/).
