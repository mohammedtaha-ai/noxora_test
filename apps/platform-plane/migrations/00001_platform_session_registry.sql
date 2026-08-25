-- +goose Up
CREATE SCHEMA IF NOT EXISTS platform;

CREATE TABLE platform.command_receipts (
    event_id uuid PRIMARY KEY,
    command_id uuid NOT NULL UNIQUE,
    tenant_id uuid NOT NULL,
    event_type varchar(160) NOT NULL,
    schema_version integer NOT NULL CHECK (schema_version >= 1),
    payload_hash char(64) NOT NULL CHECK (payload_hash ~ '^[a-f0-9]{64}$'),
    status varchar(32) NOT NULL CHECK (status IN ('RECEIVED', 'PROCESSED')),
    received_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz NULL
);

CREATE INDEX command_receipts_tenant_received_idx
    ON platform.command_receipts (tenant_id, received_at DESC);

CREATE TABLE platform.sessions (
    id uuid PRIMARY KEY,
    event_id uuid NOT NULL UNIQUE,
    command_id uuid NOT NULL UNIQUE,
    tenant_id uuid NOT NULL,
    assignment_id uuid NOT NULL,
    scenario_version_id uuid NOT NULL,
    scenario_artifact_id uuid NOT NULL,
    scenario_artifact_sha256 char(64) NOT NULL CHECK (scenario_artifact_sha256 ~ '^[a-f0-9]{64}$'),
    runtime_contract_version varchar(128) NOT NULL,
    execution_manifest jsonb NOT NULL,
    state varchar(32) NOT NULL CHECK (state IN ('REQUESTED', 'PENDING_WORKER', 'FAILED', 'CANCELLED')),
    generation bigint NOT NULL DEFAULT 0 CHECK (generation >= 0),
    future_worker_route varchar(256) NULL,
    future_worker_route_generation bigint NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT sessions_receipt_event_fk
        FOREIGN KEY (event_id) REFERENCES platform.command_receipts(event_id) ON DELETE RESTRICT,
    CONSTRAINT sessions_route_fence_check
        CHECK (
            (future_worker_route IS NULL AND future_worker_route_generation IS NULL)
            OR (future_worker_route IS NOT NULL AND future_worker_route_generation IS NOT NULL AND future_worker_route_generation = generation)
        )
);

CREATE INDEX sessions_tenant_created_idx
    ON platform.sessions (tenant_id, created_at DESC);

CREATE TABLE platform.session_leases (
    session_id uuid PRIMARY KEY REFERENCES platform.sessions(id) ON DELETE RESTRICT,
    owner_id varchar(128) NOT NULL,
    lease_token uuid NOT NULL UNIQUE,
    lease_generation bigint NOT NULL CHECK (lease_generation > 0),
    lease_expires_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT session_leases_expiry_check CHECK (lease_expires_at > updated_at)
);

CREATE INDEX session_leases_expiry_idx
    ON platform.session_leases (lease_expires_at);

-- +goose Down
DROP SCHEMA IF EXISTS platform CASCADE;
