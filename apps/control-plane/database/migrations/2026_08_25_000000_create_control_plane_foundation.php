<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        DB::statement('CREATE SCHEMA IF NOT EXISTS control_plane');

        DB::unprepared(<<<'SQL'
CREATE TABLE control_plane.users (
    id uuid PRIMARY KEY,
    name varchar(160) NOT NULL,
    email varchar(320) NOT NULL UNIQUE,
    password varchar(255) NOT NULL,
    email_verified_at timestamptz NULL,
    remember_token varchar(100) NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE control_plane.personal_access_tokens (
    id bigserial PRIMARY KEY,
    tokenable_type varchar(255) NOT NULL,
    tokenable_id uuid NOT NULL,
    name varchar(255) NOT NULL,
    token char(64) NOT NULL UNIQUE,
    abilities text NULL,
    last_used_at timestamptz NULL,
    expires_at timestamptz NULL,
    created_at timestamptz NULL,
    updated_at timestamptz NULL
);
CREATE INDEX personal_access_tokens_tokenable_idx ON control_plane.personal_access_tokens (tokenable_type, tokenable_id);

CREATE TABLE control_plane.tenants (
    id uuid PRIMARY KEY,
    name varchar(160) NOT NULL,
    slug varchar(96) NOT NULL UNIQUE,
    status varchar(32) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE control_plane.tenant_memberships (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES control_plane.tenants(id) ON DELETE RESTRICT,
    user_id uuid NOT NULL REFERENCES control_plane.users(id) ON DELETE RESTRICT,
    role varchar(32) NOT NULL CHECK (role IN ('learner', 'instructor', 'tenant_admin', 'platform_admin')),
    status varchar(32) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT tenant_memberships_tenant_user_unique UNIQUE (tenant_id, user_id)
);
CREATE INDEX tenant_memberships_user_tenant_idx ON control_plane.tenant_memberships (user_id, tenant_id);

CREATE TABLE control_plane.programs (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES control_plane.tenants(id) ON DELETE RESTRICT,
    code varchar(64) NOT NULL,
    title varchar(200) NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT programs_tenant_code_unique UNIQUE (tenant_id, code)
);

CREATE TABLE control_plane.courses (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES control_plane.tenants(id) ON DELETE RESTRICT,
    program_id uuid NOT NULL REFERENCES control_plane.programs(id) ON DELETE RESTRICT,
    code varchar(64) NOT NULL,
    title varchar(200) NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT courses_tenant_code_unique UNIQUE (tenant_id, code)
);
CREATE INDEX courses_tenant_program_idx ON control_plane.courses (tenant_id, program_id);

CREATE TABLE control_plane.cohorts (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES control_plane.tenants(id) ON DELETE RESTRICT,
    course_id uuid NOT NULL REFERENCES control_plane.courses(id) ON DELETE RESTRICT,
    code varchar(64) NOT NULL,
    title varchar(200) NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT cohorts_tenant_code_unique UNIQUE (tenant_id, code)
);
CREATE INDEX cohorts_tenant_course_idx ON control_plane.cohorts (tenant_id, course_id);

CREATE TABLE control_plane.cohort_memberships (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES control_plane.tenants(id) ON DELETE RESTRICT,
    cohort_id uuid NOT NULL REFERENCES control_plane.cohorts(id) ON DELETE RESTRICT,
    user_id uuid NOT NULL REFERENCES control_plane.users(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT cohort_memberships_cohort_user_unique UNIQUE (cohort_id, user_id)
);
CREATE INDEX cohort_memberships_tenant_user_idx ON control_plane.cohort_memberships (tenant_id, user_id);

CREATE TABLE control_plane.scenarios (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES control_plane.tenants(id) ON DELETE RESTRICT,
    title varchar(200) NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'archived')),
    created_by uuid NOT NULL REFERENCES control_plane.users(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX scenarios_tenant_status_idx ON control_plane.scenarios (tenant_id, status);

CREATE TABLE control_plane.scenario_versions (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES control_plane.tenants(id) ON DELETE RESTRICT,
    scenario_id uuid NOT NULL REFERENCES control_plane.scenarios(id) ON DELETE RESTRICT,
    version_number integer NOT NULL CHECK (version_number > 0),
    status varchar(32) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'retired')),
    title varchar(200) NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    artifact_id uuid NULL,
    artifact_hash char(64) NULL,
    artifact_content_type varchar(160) NULL,
    artifact_size_bytes bigint NULL CHECK (artifact_size_bytes IS NULL OR artifact_size_bytes >= 0),
    artifact_classification varchar(32) NOT NULL DEFAULT 'INTERNAL' CHECK (artifact_classification IN ('PUBLIC', 'INTERNAL', 'RESTRICTED')),
    artifact_storage_reference varchar(512) NULL,
    published_at timestamptz NULL,
    created_by uuid NOT NULL REFERENCES control_plane.users(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT scenario_versions_scenario_version_unique UNIQUE (scenario_id, version_number)
);
CREATE INDEX scenario_versions_tenant_scenario_idx ON control_plane.scenario_versions (tenant_id, scenario_id, status);

CREATE TABLE control_plane.assignments (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES control_plane.tenants(id) ON DELETE RESTRICT,
    course_id uuid NOT NULL REFERENCES control_plane.courses(id) ON DELETE RESTRICT,
    cohort_id uuid NULL REFERENCES control_plane.cohorts(id) ON DELETE RESTRICT,
    scenario_version_id uuid NOT NULL REFERENCES control_plane.scenario_versions(id) ON DELETE RESTRICT,
    available_from timestamptz NOT NULL,
    available_until timestamptz NULL,
    status varchar(32) NOT NULL DEFAULT 'active' CHECK (status IN ('draft', 'active', 'cancelled')),
    created_by uuid NOT NULL REFERENCES control_plane.users(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT assignments_availability_range CHECK (available_until IS NULL OR available_until > available_from)
);
CREATE INDEX assignments_tenant_course_availability_idx ON control_plane.assignments (tenant_id, course_id, available_from, available_until);

CREATE TABLE control_plane.simulation_start_intents (
    id uuid PRIMARY KEY,
    command_id uuid NOT NULL UNIQUE,
    tenant_id uuid NOT NULL REFERENCES control_plane.tenants(id) ON DELETE RESTRICT,
    user_id uuid NOT NULL REFERENCES control_plane.users(id) ON DELETE RESTRICT,
    assignment_id uuid NOT NULL REFERENCES control_plane.assignments(id) ON DELETE RESTRICT,
    scenario_version_id uuid NOT NULL REFERENCES control_plane.scenario_versions(id) ON DELETE RESTRICT,
    request_id uuid NOT NULL,
    correlation_id uuid NOT NULL,
    intent_fingerprint char(64) NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'requested' CHECK (status IN ('requested', 'cancelled')),
    requested_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT simulation_start_idempotency_unique UNIQUE (user_id, request_id)
);
CREATE INDEX simulation_start_intents_tenant_assignment_idx ON control_plane.simulation_start_intents (tenant_id, assignment_id, requested_at DESC);

CREATE TABLE control_plane.outbox_events (
    event_id uuid PRIMARY KEY,
    command_id uuid NOT NULL UNIQUE,
    tenant_id uuid NOT NULL REFERENCES control_plane.tenants(id) ON DELETE RESTRICT,
    event_type varchar(128) NOT NULL,
    schema_version integer NOT NULL CHECK (schema_version >= 1),
    aggregate_type varchar(64) NOT NULL,
    aggregate_id uuid NOT NULL,
    routing_key varchar(128) NOT NULL,
    classification varchar(32) NOT NULL CHECK (classification IN ('PUBLIC', 'INTERNAL', 'RESTRICTED')),
    payload jsonb NOT NULL,
    correlation_id uuid NOT NULL,
    causation_id uuid NULL,
    occurred_at timestamptz NOT NULL,
    claimed_at timestamptz NULL,
    claim_token uuid NULL,
    published_at timestamptz NULL,
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    last_error varchar(500) NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX outbox_events_pending_idx ON control_plane.outbox_events (published_at, claimed_at, occurred_at) WHERE published_at IS NULL;

CREATE TABLE control_plane.audit_logs (
    id uuid PRIMARY KEY,
    tenant_id uuid NULL REFERENCES control_plane.tenants(id) ON DELETE RESTRICT,
    actor_user_id uuid NULL REFERENCES control_plane.users(id) ON DELETE RESTRICT,
    action varchar(128) NOT NULL,
    target_type varchar(64) NOT NULL,
    target_id uuid NULL,
    request_id uuid NOT NULL,
    correlation_id uuid NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX audit_logs_tenant_occurred_idx ON control_plane.audit_logs (tenant_id, occurred_at DESC);

CREATE OR REPLACE FUNCTION control_plane.prevent_published_scenario_version_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status = 'published' AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'published scenario versions are immutable';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER scenario_versions_immutable_when_published
BEFORE UPDATE OR DELETE ON control_plane.scenario_versions
FOR EACH ROW EXECUTE FUNCTION control_plane.prevent_published_scenario_version_mutation();
SQL);
    }

    public function down(): void
    {
        DB::statement('DROP SCHEMA IF EXISTS control_plane CASCADE');
    }
};
