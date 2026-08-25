# Nexora Laravel Control Plane

This directory is the **Control Plane** foundation. It owns only `control_plane.*` PostgreSQL relations and business metadata. It does not own Go platform state, Python VPE runtime state, Pulse state, telemetry history, or Unity.

## Local Docker workflow

Use Docker Compose when Docker is available. The composition starts only PHP/Laravel and PostgreSQL; it deliberately excludes Redis, Kafka, ClickHouse, SQS, Go, and cloud resources.

```bash
cd apps/control-plane
cp .env.example .env
# Set a local APP_KEY and a non-committed CONTROL_PLANE_DB_PASSWORD, then:
export CONTROL_PLANE_DB_PASSWORD='choose-a-local-secret'
docker compose up --build
```

The API is available at `http://localhost:8000/api/v1`. Apply migrations explicitly when not using the compose app command:

```bash
docker compose run --rm control-plane php artisan migrate --force
```

## Non-Docker PostgreSQL workflow

Create an isolated PostgreSQL database and role, copy `.env.example` to `.env`, set `DB_*`, and run:

```bash
composer install
php artisan key:generate
php artisan migrate --force
php artisan serve
```

## PostgreSQL integration tests

The test suite must use a real PostgreSQL database, never SQLite as proof. Create `.env.testing` from local values with `DB_DATABASE` pointing at an isolated test database, then run:

```bash
php artisan migrate:fresh --force
./vendor/bin/phpunit
```

The production-style transaction path is: authenticated request → membership-derived tenant authorization → assignment and scenario-version validation → one PostgreSQL transaction that writes `simulation_start_intents`, `outbox_events`, and `audit_logs`.

## Contracts and boundaries

* Public REST contract: [`../../contracts/control-plane.openapi.yaml`](../../contracts/control-plane.openapi.yaml).
* Portable outbox event contract: [`../../schemas/platform-event-envelope.schema.json`](../../schemas/platform-event-envelope.schema.json).
* A client-supplied `X-Tenant-Id` is context selection only. Authorization comes from the authenticated active membership.
* The local relay is at-least-once; consumers must deduplicate by `event_id` / `command_id`.
