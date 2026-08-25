<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        DB::unprepared(<<<'SQL'
ALTER TABLE control_plane.programs
    ADD CONSTRAINT programs_tenant_id_unique UNIQUE (tenant_id, id);
ALTER TABLE control_plane.courses
    ADD CONSTRAINT courses_tenant_id_unique UNIQUE (tenant_id, id);
ALTER TABLE control_plane.cohorts
    ADD CONSTRAINT cohorts_tenant_id_unique UNIQUE (tenant_id, id);
ALTER TABLE control_plane.scenarios
    ADD CONSTRAINT scenarios_tenant_id_unique UNIQUE (tenant_id, id);
ALTER TABLE control_plane.scenario_versions
    ADD CONSTRAINT scenario_versions_tenant_id_unique UNIQUE (tenant_id, id);
ALTER TABLE control_plane.assignments
    ADD CONSTRAINT assignments_tenant_id_unique UNIQUE (tenant_id, id);

ALTER TABLE control_plane.courses
    ADD CONSTRAINT courses_tenant_program_fk
    FOREIGN KEY (tenant_id, program_id)
    REFERENCES control_plane.programs (tenant_id, id)
    ON DELETE RESTRICT;
ALTER TABLE control_plane.cohorts
    ADD CONSTRAINT cohorts_tenant_course_fk
    FOREIGN KEY (tenant_id, course_id)
    REFERENCES control_plane.courses (tenant_id, id)
    ON DELETE RESTRICT;
ALTER TABLE control_plane.cohort_memberships
    ADD CONSTRAINT cohort_memberships_tenant_cohort_fk
    FOREIGN KEY (tenant_id, cohort_id)
    REFERENCES control_plane.cohorts (tenant_id, id)
    ON DELETE RESTRICT;
ALTER TABLE control_plane.scenario_versions
    ADD CONSTRAINT scenario_versions_tenant_scenario_fk
    FOREIGN KEY (tenant_id, scenario_id)
    REFERENCES control_plane.scenarios (tenant_id, id)
    ON DELETE RESTRICT;
ALTER TABLE control_plane.scenario_versions
    ADD CONSTRAINT scenario_versions_executable_published_manifest_check CHECK (
        status NOT IN ('published', 'retired') OR (
            artifact_id IS NOT NULL
            AND artifact_hash ~ '^[a-f0-9]{64}$'
            AND artifact_content_type IS NOT NULL AND length(artifact_content_type) > 0
            AND artifact_size_bytes IS NOT NULL AND artifact_size_bytes >= 0
            AND artifact_storage_reference IS NOT NULL AND length(artifact_storage_reference) > 0
            AND jsonb_typeof(metadata->'scenario_contract_version') = 'string'
            AND jsonb_typeof(metadata->'runtime_contract_version') = 'string'
        )
    );
ALTER TABLE control_plane.assignments
    ADD CONSTRAINT assignments_tenant_course_fk
    FOREIGN KEY (tenant_id, course_id)
    REFERENCES control_plane.courses (tenant_id, id)
    ON DELETE RESTRICT;
ALTER TABLE control_plane.assignments
    ADD CONSTRAINT assignments_tenant_cohort_fk
    FOREIGN KEY (tenant_id, cohort_id)
    REFERENCES control_plane.cohorts (tenant_id, id)
    ON DELETE RESTRICT;
ALTER TABLE control_plane.assignments
    ADD CONSTRAINT assignments_tenant_scenario_version_fk
    FOREIGN KEY (tenant_id, scenario_version_id)
    REFERENCES control_plane.scenario_versions (tenant_id, id)
    ON DELETE RESTRICT;
ALTER TABLE control_plane.simulation_start_intents
    ADD CONSTRAINT simulation_start_intents_tenant_assignment_fk
    FOREIGN KEY (tenant_id, assignment_id)
    REFERENCES control_plane.assignments (tenant_id, id)
    ON DELETE RESTRICT;
ALTER TABLE control_plane.simulation_start_intents
    ADD CONSTRAINT simulation_start_intents_tenant_scenario_version_fk
    FOREIGN KEY (tenant_id, scenario_version_id)
    REFERENCES control_plane.scenario_versions (tenant_id, id)
    ON DELETE RESTRICT;

CREATE OR REPLACE FUNCTION control_plane.prevent_published_scenario_version_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.status IN ('published', 'retired') THEN
            RAISE EXCEPTION 'published or retired scenario versions cannot be deleted';
        END IF;
        RETURN OLD;
    END IF;

    IF OLD.status = 'published' THEN
        IF NEW.status <> 'retired' THEN
            RAISE EXCEPTION 'published scenario versions may only transition to retired';
        END IF;
        IF (to_jsonb(NEW) - 'status' - 'updated_at') IS DISTINCT FROM (to_jsonb(OLD) - 'status' - 'updated_at') THEN
            RAISE EXCEPTION 'published scenario version execution content is immutable';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status = 'retired' THEN
        IF (to_jsonb(NEW) - 'updated_at') IS DISTINCT FROM (to_jsonb(OLD) - 'updated_at') THEN
            RAISE EXCEPTION 'retired scenario versions are immutable';
        END IF;
        RETURN NEW;
    END IF;

    RETURN NEW;
END;
$$;
SQL);
    }

    public function down(): void
    {
        DB::unprepared(<<<'SQL'
ALTER TABLE control_plane.simulation_start_intents DROP CONSTRAINT IF EXISTS simulation_start_intents_tenant_scenario_version_fk;
ALTER TABLE control_plane.simulation_start_intents DROP CONSTRAINT IF EXISTS simulation_start_intents_tenant_assignment_fk;
ALTER TABLE control_plane.assignments DROP CONSTRAINT IF EXISTS assignments_tenant_scenario_version_fk;
ALTER TABLE control_plane.assignments DROP CONSTRAINT IF EXISTS assignments_tenant_cohort_fk;
ALTER TABLE control_plane.assignments DROP CONSTRAINT IF EXISTS assignments_tenant_course_fk;
ALTER TABLE control_plane.scenario_versions DROP CONSTRAINT IF EXISTS scenario_versions_executable_published_manifest_check;
ALTER TABLE control_plane.scenario_versions DROP CONSTRAINT IF EXISTS scenario_versions_tenant_scenario_fk;
ALTER TABLE control_plane.cohort_memberships DROP CONSTRAINT IF EXISTS cohort_memberships_tenant_cohort_fk;
ALTER TABLE control_plane.cohorts DROP CONSTRAINT IF EXISTS cohorts_tenant_course_fk;
ALTER TABLE control_plane.courses DROP CONSTRAINT IF EXISTS courses_tenant_program_fk;
ALTER TABLE control_plane.assignments DROP CONSTRAINT IF EXISTS assignments_tenant_id_unique;
ALTER TABLE control_plane.scenario_versions DROP CONSTRAINT IF EXISTS scenario_versions_tenant_id_unique;
ALTER TABLE control_plane.scenarios DROP CONSTRAINT IF EXISTS scenarios_tenant_id_unique;
ALTER TABLE control_plane.cohorts DROP CONSTRAINT IF EXISTS cohorts_tenant_id_unique;
ALTER TABLE control_plane.courses DROP CONSTRAINT IF EXISTS courses_tenant_id_unique;
ALTER TABLE control_plane.programs DROP CONSTRAINT IF EXISTS programs_tenant_id_unique;
SQL);
    }
};
