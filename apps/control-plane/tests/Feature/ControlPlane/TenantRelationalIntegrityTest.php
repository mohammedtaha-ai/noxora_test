<?php

declare(strict_types=1);

namespace Tests\Feature\ControlPlane;

use App\Models\Assignment;
use App\Models\Cohort;
use App\Models\Course;
use App\Models\Program;
use App\Models\Scenario;
use App\Models\ScenarioVersion;
use App\Models\Tenant;
use App\Models\User;
use Illuminate\Database\QueryException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class TenantRelationalIntegrityTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        DB::unprepared('TRUNCATE TABLE control_plane.audit_logs, control_plane.outbox_events, control_plane.simulation_start_intents, control_plane.assignments, control_plane.scenario_versions, control_plane.scenarios, control_plane.cohort_memberships, control_plane.cohorts, control_plane.courses, control_plane.programs, control_plane.tenant_memberships, control_plane.tenants, control_plane.personal_access_tokens, control_plane.users RESTART IDENTITY CASCADE');
    }

    public function test_postgresql_rejects_cross_tenant_relational_graph_edges(): void
    {
        $user = User::query()->create(['name' => 'Author', 'email' => Str::uuid7().'@example.test', 'password' => 'test-password']);
        $a = $this->graph('a', $user);
        $b = $this->graph('b', $user);

        $this->assertRejected(fn () => DB::table('courses')->insert([
            'id' => (string) Str::uuid7(), 'tenant_id' => $a['tenant']->id, 'program_id' => $b['program']->id,
            'code' => 'C-cross-1', 'title' => 'Cross course', 'status' => 'active', 'created_at' => now(), 'updated_at' => now(),
        ]));
        $this->assertRejected(fn () => DB::table('cohorts')->insert([
            'id' => (string) Str::uuid7(), 'tenant_id' => $a['tenant']->id, 'course_id' => $b['course']->id,
            'code' => 'H-cross-1', 'title' => 'Cross cohort', 'status' => 'active', 'created_at' => now(), 'updated_at' => now(),
        ]));
        $this->assertRejected(fn () => DB::table('cohort_memberships')->insert([
            'id' => (string) Str::uuid7(), 'tenant_id' => $a['tenant']->id, 'cohort_id' => $b['cohort']->id,
            'user_id' => $user->id, 'created_at' => now(), 'updated_at' => now(),
        ]));
        $this->assertRejected(fn () => DB::table('scenario_versions')->insert([
            'id' => (string) Str::uuid7(), 'tenant_id' => $a['tenant']->id, 'scenario_id' => $b['scenario']->id,
            'version_number' => 2, 'status' => 'draft', 'title' => 'Cross version', 'metadata' => json_encode([]),
            'artifact_classification' => 'INTERNAL', 'created_by' => $user->id, 'created_at' => now(), 'updated_at' => now(),
        ]));
        $this->assertRejected(fn () => DB::table('assignments')->insert([
            'id' => (string) Str::uuid7(), 'tenant_id' => $a['tenant']->id, 'course_id' => $b['course']->id,
            'cohort_id' => $b['cohort']->id, 'scenario_version_id' => $b['version']->id,
            'available_from' => now()->subMinute(), 'status' => 'active', 'created_by' => $user->id,
            'created_at' => now(), 'updated_at' => now(),
        ]));
        $this->assertRejected(fn () => DB::table('simulation_start_intents')->insert([
            'id' => (string) Str::uuid7(), 'command_id' => (string) Str::uuid7(), 'tenant_id' => $a['tenant']->id,
            'user_id' => $user->id, 'assignment_id' => $b['assignment']->id, 'scenario_version_id' => $b['version']->id,
            'idempotency_key' => (string) Str::uuid7(), 'request_id' => (string) Str::uuid7(), 'correlation_id' => (string) Str::uuid7(), 'intent_fingerprint' => str_repeat('a', 64),
            'status' => 'requested', 'requested_at' => now(), 'created_at' => now(), 'updated_at' => now(),
        ]));
    }

    public function test_published_version_allows_only_retirement_then_rejects_retired_content_mutation(): void
    {
        $user = User::query()->create(['name' => 'Author', 'email' => Str::uuid7().'@example.test', 'password' => 'test-password']);
        $graph = $this->graph('lifecycle', $user);
        $version = $graph['version'];

        $this->assertRejected(fn () => $version->update(['title' => 'Mutated published title']));
        $version = $version->fresh();
        $this->assertRejected(fn () => $version->update(['artifact_hash' => str_repeat('f', 64)]));
        $version = $version->fresh();

        $version->update(['status' => 'retired']);
        $this->assertSame('retired', $version->fresh()->status);
        $this->assertRejected(fn () => $version->update(['title' => 'Mutated retired title']));
    }

    /** @return array{tenant: Tenant, program: Program, course: Course, cohort: Cohort, scenario: Scenario, version: ScenarioVersion, assignment: Assignment} */
    private function graph(string $suffix, User $user): array
    {
        $tenant = Tenant::query()->create(['name' => 'Tenant '.$suffix, 'slug' => 'tenant-'.$suffix.'-'.substr((string) Str::uuid7(), 0, 8), 'status' => 'active']);
        $program = Program::query()->create(['tenant_id' => $tenant->id, 'code' => 'P-'.$suffix, 'title' => 'Program', 'status' => 'active']);
        $course = Course::query()->create(['tenant_id' => $tenant->id, 'program_id' => $program->id, 'code' => 'C-'.$suffix, 'title' => 'Course', 'status' => 'active']);
        $cohort = Cohort::query()->create(['tenant_id' => $tenant->id, 'course_id' => $course->id, 'code' => 'H-'.$suffix, 'title' => 'Cohort', 'status' => 'active']);
        $scenario = Scenario::query()->create(['tenant_id' => $tenant->id, 'title' => 'Scenario', 'status' => 'draft', 'created_by' => $user->id]);
        $version = ScenarioVersion::query()->create([
            'tenant_id' => $tenant->id, 'scenario_id' => $scenario->id, 'version_number' => 1, 'status' => 'published', 'title' => 'Published',
            'metadata' => ['scenario_contract_version' => 'nexora.scenario.s0.v1', 'runtime_contract_version' => 'nexora.vpe.s0.v1'], 'artifact_id' => (string) Str::uuid7(), 'artifact_hash' => str_repeat('b', 64),
            'artifact_content_type' => 'application/json', 'artifact_size_bytes' => 1, 'artifact_classification' => 'INTERNAL',
            'artifact_storage_reference' => 'dev://scenario/'.$suffix, 'created_by' => $user->id, 'published_at' => now(),
        ]);
        $assignment = Assignment::query()->create([
            'tenant_id' => $tenant->id, 'course_id' => $course->id, 'cohort_id' => $cohort->id, 'scenario_version_id' => $version->id,
            'available_from' => now()->subMinute(), 'status' => 'active', 'created_by' => $user->id,
        ]);

        return compact('tenant', 'program', 'course', 'cohort', 'scenario', 'version', 'assignment');
    }

    /** @param callable(): mixed $operation */
    private function assertRejected(callable $operation): void
    {
        try {
            $operation();
            $this->fail('Expected PostgreSQL tenant-aware foreign key rejection.');
        } catch (QueryException) {
            $this->addToAssertionCount(1);
        }
    }
}
