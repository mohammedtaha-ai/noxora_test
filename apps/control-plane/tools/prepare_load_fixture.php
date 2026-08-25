<?php

declare(strict_types=1);

use App\Models\Assignment;
use App\Models\Cohort;
use App\Models\CohortMembership;
use App\Models\Course;
use App\Models\Program;
use App\Models\Scenario;
use App\Models\ScenarioVersion;
use App\Models\Tenant;
use App\Models\TenantMembership;
use App\Models\User;
use App\Support\LocalDestructiveOperationGuard;
use Illuminate\Contracts\Console\Kernel;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

require __DIR__.'/../vendor/autoload.php';
$app = require __DIR__.'/../bootstrap/app.php';
$app->make(Kernel::class)->bootstrap();

$connectionName = (string) config('database.default');
$connection = (array) config('database.connections.'.$connectionName, []);
LocalDestructiveOperationGuard::assertAllowed(
    (string) $app->environment(),
    (string) ($connection['host'] ?? ''),
    (string) ($connection['database'] ?? ''),
    env('NEXORA_ALLOW_DESTRUCTIVE_LOCAL'),
);

DB::unprepared('TRUNCATE TABLE control_plane.audit_logs, control_plane.outbox_events, control_plane.simulation_start_intents, control_plane.assignments, control_plane.scenario_versions, control_plane.scenarios, control_plane.cohort_memberships, control_plane.cohorts, control_plane.courses, control_plane.programs, control_plane.tenant_memberships, control_plane.tenants, control_plane.personal_access_tokens, control_plane.users RESTART IDENTITY CASCADE');
$user = User::query()->create(['name' => 'Load Learner', 'email' => 'load-'.Str::uuid7().'@example.test', 'password' => 'test-password']);
$tenant = Tenant::query()->create(['name' => 'Load Tenant', 'slug' => 'load-'.substr((string) Str::uuid7(), 0, 8), 'status' => 'active']);
TenantMembership::query()->create(['tenant_id' => $tenant->id, 'user_id' => $user->id, 'role' => 'learner', 'status' => 'active']);
$program = Program::query()->create(['tenant_id' => $tenant->id, 'code' => 'LOAD', 'title' => 'Load Program', 'status' => 'active']);
$course = Course::query()->create(['tenant_id' => $tenant->id, 'program_id' => $program->id, 'code' => 'LOAD-101', 'title' => 'Load Course', 'status' => 'active']);
$cohort = Cohort::query()->create(['tenant_id' => $tenant->id, 'course_id' => $course->id, 'code' => 'LOAD-A', 'title' => 'Load Cohort', 'status' => 'active']);
CohortMembership::query()->create(['tenant_id' => $tenant->id, 'cohort_id' => $cohort->id, 'user_id' => $user->id]);
$scenario = Scenario::query()->create(['tenant_id' => $tenant->id, 'title' => 'Load Scenario', 'status' => 'draft', 'created_by' => $user->id]);
$version = ScenarioVersion::query()->create([
    'tenant_id' => $tenant->id,
    'scenario_id' => $scenario->id,
    'version_number' => 1,
    'status' => 'published',
    'title' => 'Load Scenario v1',
    'metadata' => ['scenario_contract_version' => 'nexora.scenario.s0.v1', 'runtime_contract_version' => 'nexora.vpe.s0.v1'],
    'artifact_id' => (string) Str::uuid7(),
    'artifact_hash' => str_repeat('a', 64),
    'artifact_content_type' => 'application/json',
    'artifact_size_bytes' => 1,
    'artifact_storage_reference' => 'local://scenario/load.json',
    'created_by' => $user->id,
    'published_at' => now(),
]);
$assignment = Assignment::query()->create(['tenant_id' => $tenant->id, 'course_id' => $course->id, 'cohort_id' => $cohort->id, 'scenario_version_id' => $version->id, 'available_from' => now()->subMinute(), 'available_until' => now()->addHour(), 'status' => 'active', 'created_by' => $user->id]);
$token = $user->createToken('local-load-test', ['control-plane:read', 'control-plane:simulation-start'])->plainTextToken;

echo json_encode(['token' => $token, 'tenant_id' => $tenant->id, 'assignment_id' => $assignment->id], JSON_THROW_ON_ERROR).PHP_EOL;
