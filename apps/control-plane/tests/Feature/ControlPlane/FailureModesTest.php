<?php

declare(strict_types=1);

namespace Tests\Feature\ControlPlane;

use App\Exceptions\ControlPlaneException;
use App\Models\Assignment;
use App\Models\Cohort;
use App\Models\CohortMembership;
use App\Models\Course;
use App\Models\OutboxEvent;
use App\Models\Program;
use App\Models\Scenario;
use App\Models\ScenarioVersion;
use App\Models\Tenant;
use App\Models\TenantMembership;
use App\Models\User;
use App\Services\RequestSimulationStart;
use Illuminate\Database\QueryException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class FailureModesTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        DB::unprepared('TRUNCATE TABLE control_plane.audit_logs, control_plane.outbox_events, control_plane.simulation_start_intents, control_plane.assignments, control_plane.scenario_versions, control_plane.scenarios, control_plane.cohort_memberships, control_plane.cohorts, control_plane.courses, control_plane.programs, control_plane.tenant_memberships, control_plane.tenants, control_plane.personal_access_tokens, control_plane.users RESTART IDENTITY CASCADE');
    }

    public function test_postgresql_connection_failure_is_reported_as_a_database_failure_not_silently_retried_as_sqlite(): void
    {
        config(['database.connections.unavailable_pg' => array_merge(config('database.connections.pgsql'), ['port' => 1])]);

        $this->expectException(QueryException::class);
        DB::connection('unavailable_pg')->select('SELECT 1');
    }

    public function test_assignment_with_nonpublished_scenario_version_is_rejected_without_outbox(): void
    {
        $user = User::query()->create(['name' => 'Learner', 'email' => Str::uuid7().'@example.test', 'password' => 'test-password']);
        $tenant = Tenant::query()->create(['name' => 'Tenant', 'slug' => 'tenant-'.substr((string) Str::uuid7(), 0, 8), 'status' => 'active']);
        TenantMembership::query()->create(['tenant_id' => $tenant->id, 'user_id' => $user->id, 'role' => 'learner', 'status' => 'active']);
        $program = Program::query()->create(['tenant_id' => $tenant->id, 'code' => 'P1', 'title' => 'Program', 'status' => 'active']);
        $course = Course::query()->create(['tenant_id' => $tenant->id, 'program_id' => $program->id, 'code' => 'C1', 'title' => 'Course', 'status' => 'active']);
        $cohort = Cohort::query()->create(['tenant_id' => $tenant->id, 'course_id' => $course->id, 'code' => 'H1', 'title' => 'Cohort', 'status' => 'active']);
        CohortMembership::query()->create(['tenant_id' => $tenant->id, 'cohort_id' => $cohort->id, 'user_id' => $user->id]);
        $scenario = Scenario::query()->create(['tenant_id' => $tenant->id, 'title' => 'Scenario', 'status' => 'draft', 'created_by' => $user->id]);
        $version = ScenarioVersion::query()->create(['tenant_id' => $tenant->id, 'scenario_id' => $scenario->id, 'version_number' => 1, 'status' => 'draft', 'title' => 'Draft', 'metadata' => [], 'created_by' => $user->id]);
        $assignment = Assignment::query()->create(['tenant_id' => $tenant->id, 'course_id' => $course->id, 'cohort_id' => $cohort->id, 'scenario_version_id' => $version->id, 'available_from' => now()->subMinute(), 'available_until' => now()->addHour(), 'status' => 'active', 'created_by' => $user->id]);

        try {
            app(RequestSimulationStart::class)->handle($user, $tenant->id, $assignment->id, (string) Str::uuid7(), (string) Str::uuid7(), (string) Str::uuid7());
            $this->fail('Expected invalid scenario version failure.');
        } catch (ControlPlaneException $exception) {
            $this->assertSame('INVALID_SCENARIO_VERSION', $exception->errorCode);
        }

        $this->assertSame(0, OutboxEvent::query()->count());
    }
}
