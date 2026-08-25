<?php

declare(strict_types=1);

namespace Tests\Feature\ControlPlane;

use App\Exceptions\ControlPlaneException;
use App\Models\Assignment;
use App\Models\AuditLog;
use App\Models\Cohort;
use App\Models\CohortMembership;
use App\Models\Course;
use App\Models\OutboxEvent;
use App\Models\Program;
use App\Models\Scenario;
use App\Models\ScenarioVersion;
use App\Models\SimulationStartIntent;
use App\Models\Tenant;
use App\Models\TenantMembership;
use App\Models\User;
use App\Services\RequestSimulationStart;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Laravel\Sanctum\Sanctum;
use Tests\TestCase;

class SimulationStartTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        DB::unprepared('TRUNCATE TABLE control_plane.audit_logs, control_plane.outbox_events, control_plane.simulation_start_intents, control_plane.assignments, control_plane.scenario_versions, control_plane.scenarios, control_plane.cohort_memberships, control_plane.cohorts, control_plane.courses, control_plane.programs, control_plane.tenant_memberships, control_plane.tenants, control_plane.personal_access_tokens, control_plane.users RESTART IDENTITY CASCADE');
    }

    /** @return array<string, mixed> */
    private function world(string $role = 'learner', ?User $user = null): array
    {
        $user ??= User::query()->create(['name' => 'Learner', 'email' => Str::uuid7().'@example.test', 'password' => 'test-password']);
        $tenant = Tenant::query()->create(['name' => 'Tenant '.Str::uuid7(), 'slug' => strtolower(str_replace('-', '', (string) Str::uuid7())), 'status' => 'active']);
        TenantMembership::query()->create(['tenant_id' => $tenant->id, 'user_id' => $user->id, 'role' => $role, 'status' => 'active']);
        $program = Program::query()->create(['tenant_id' => $tenant->id, 'code' => 'P'.substr((string) Str::uuid7(), 0, 8), 'title' => 'Program', 'status' => 'active']);
        $course = Course::query()->create(['tenant_id' => $tenant->id, 'program_id' => $program->id, 'code' => 'C'.substr((string) Str::uuid7(), 0, 8), 'title' => 'Course', 'status' => 'active']);
        $cohort = Cohort::query()->create(['tenant_id' => $tenant->id, 'course_id' => $course->id, 'code' => 'H'.substr((string) Str::uuid7(), 0, 8), 'title' => 'Cohort', 'status' => 'active']);
        CohortMembership::query()->create(['tenant_id' => $tenant->id, 'cohort_id' => $cohort->id, 'user_id' => $user->id]);
        $scenario = Scenario::query()->create(['tenant_id' => $tenant->id, 'title' => 'Scenario', 'status' => 'draft', 'created_by' => $user->id]);
        $version = ScenarioVersion::query()->create([
            'tenant_id' => $tenant->id,
            'scenario_id' => $scenario->id,
            'version_number' => 1,
            'status' => 'published',
            'title' => 'Scenario v1',
            'metadata' => [
                'learning_mode' => true,
                'scenario_contract_version' => 'nexora.scenario.s0.v1',
                'runtime_contract_version' => 'nexora.vpe.s0.v1',
            ],
            'artifact_id' => (string) Str::uuid7(),
            'artifact_hash' => str_repeat('a', 64),
            'artifact_content_type' => 'application/json',
            'artifact_size_bytes' => 64,
            'artifact_storage_reference' => 'local://scenario/v1.json',
            'created_by' => $user->id,
            'published_at' => now(),
        ]);
        $assignment = Assignment::query()->create([
            'tenant_id' => $tenant->id,
            'course_id' => $course->id,
            'cohort_id' => $cohort->id,
            'scenario_version_id' => $version->id,
            'available_from' => now()->subMinute(),
            'available_until' => now()->addHour(),
            'status' => 'active',
            'created_by' => $user->id,
        ]);

        return compact('user', 'tenant', 'assignment', 'version', 'cohort');
    }

    public function test_authorized_start_writes_intent_outbox_and_audit_in_one_postgres_flow(): void
    {
        $world = $this->world();
        Sanctum::actingAs($world['user'], ['control-plane:simulation-start']);
        $requestId = (string) Str::uuid7();
        $idempotencyKey = (string) Str::uuid7();

        $response = $this->withHeaders([
            'X-Tenant-Id' => $world['tenant']->id,
            'X-Request-Id' => $requestId,
            'Idempotency-Key' => $idempotencyKey,
        ])->postJson('/api/v1/simulation-start-requests', ['assignment_id' => $world['assignment']->id]);

        $response->assertStatus(202)->assertJsonPath('data.status', 'requested')->assertHeader('X-Request-Id', $requestId);
        $this->assertSame(1, SimulationStartIntent::query()->count());
        $this->assertSame(1, OutboxEvent::query()->count());
        $this->assertSame(1, AuditLog::query()->count());
        $event = OutboxEvent::query()->firstOrFail();
        $this->assertSame('control.simulation_start.requested', $event->event_type);
        $this->assertSame($world['tenant']->id, $event->tenant_id);
        $this->assertArrayNotHasKey('password', $event->payload);
        $this->assertArrayNotHasKey('token', $event->payload);
        $this->assertSame('nexora.vpe.s0.v1', $event->payload['execution_manifest']['runtime_contract_version']);
        $this->assertSame($world['version']->artifact_hash, $event->payload['execution_manifest']['artifact']['sha256']);
    }

    public function test_repeated_idempotency_key_returns_same_start_intent_and_no_second_outbox_command(): void
    {
        $world = $this->world();
        $service = app(RequestSimulationStart::class);
        $idempotencyKey = (string) Str::uuid7();
        $first = $service->handle($world['user'], $world['tenant']->id, $world['assignment']->id, $idempotencyKey, (string) Str::uuid7(), (string) Str::uuid7());
        $second = $service->handle($world['user'], $world['tenant']->id, $world['assignment']->id, $idempotencyKey, (string) Str::uuid7(), (string) Str::uuid7());

        $this->assertTrue($first['created']);
        $this->assertFalse($second['created']);
        $this->assertSame($first['intent']->id, $second['intent']->id);
        $this->assertSame(1, SimulationStartIntent::query()->count());
        $this->assertSame(1, OutboxEvent::query()->count());
    }

    public function test_reused_idempotency_key_with_different_assignment_is_rejected(): void
    {
        $world = $this->world();
        $other = $this->world('learner', $world['user']);
        $service = app(RequestSimulationStart::class);
        $idempotencyKey = (string) Str::uuid7();
        $service->handle($world['user'], $world['tenant']->id, $world['assignment']->id, $idempotencyKey, (string) Str::uuid7(), (string) Str::uuid7());

        $this->expectException(ControlPlaneException::class);
        $this->expectExceptionMessage('reused with a different simulation intent');
        $service->handle($world['user'], $other['tenant']->id, $other['assignment']->id, $idempotencyKey, (string) Str::uuid7(), (string) Str::uuid7());
    }

    public function test_cross_tenant_selection_is_denied_even_when_client_supplies_tenant_id(): void
    {
        $world = $this->world();
        $other = $this->world();
        Sanctum::actingAs($world['user'], ['control-plane:simulation-start']);
        $idempotencyKey = (string) Str::uuid7();

        $this->withHeaders(['X-Tenant-Id' => $other['tenant']->id, 'Idempotency-Key' => $idempotencyKey])
            ->postJson('/api/v1/simulation-start-requests', ['assignment_id' => $other['assignment']->id])
            ->assertStatus(403)->assertJsonPath('error.code', 'SIMULATION_START_FORBIDDEN');
    }

    public function test_forced_outbox_failure_rolls_back_business_intent_and_audit(): void
    {
        $world = $this->world();
        $service = app(RequestSimulationStart::class);

        try {
            $service->handle($world['user'], $world['tenant']->id, $world['assignment']->id, (string) Str::uuid7(), (string) Str::uuid7(), (string) Str::uuid7(), true);
            $this->fail('Expected forced outbox failure.');
        } catch (ControlPlaneException $exception) {
            $this->assertSame('OUTBOX_WRITE_FAILED', $exception->errorCode);
        }

        $this->assertSame(0, SimulationStartIntent::query()->count());
        $this->assertSame(0, OutboxEvent::query()->count());
        $this->assertSame(0, AuditLog::query()->count());
    }

    public function test_expired_assignment_is_rejected_without_outbox_command(): void
    {
        $world = $this->world();
        $world['assignment']->update(['available_until' => now()->subSecond()]);
        Sanctum::actingAs($world['user'], ['control-plane:simulation-start']);

        $this->withHeaders(['X-Tenant-Id' => $world['tenant']->id, 'Idempotency-Key' => (string) Str::uuid7()])
            ->postJson('/api/v1/simulation-start-requests', ['assignment_id' => $world['assignment']->id])
            ->assertStatus(422)->assertJsonPath('error.code', 'ASSIGNMENT_NOT_AVAILABLE');
        $this->assertSame(0, OutboxEvent::query()->count());
    }

    public function test_malformed_transport_or_idempotency_identifier_returns_structured_400_before_writes(): void
    {
        $world = $this->world();
        Sanctum::actingAs($world['user'], ['control-plane:simulation-start']);

        $this->withHeaders([
            'X-Tenant-Id' => $world['tenant']->id,
            'X-Request-Id' => 'not-a-uuid',
            'Idempotency-Key' => (string) Str::uuid7(),
        ])->postJson('/api/v1/simulation-start-requests', ['assignment_id' => $world['assignment']->id])
            ->assertStatus(400)->assertJsonPath('error.code', 'MALFORMED_REQUEST_IDENTIFIER');

        $this->withHeaders([
            'X-Tenant-Id' => $world['tenant']->id,
            'X-Request-Id' => (string) Str::uuid7(),
            'Idempotency-Key' => 'not-a-uuid',
        ])->postJson('/api/v1/simulation-start-requests', ['assignment_id' => $world['assignment']->id])
            ->assertStatus(400)->assertJsonPath('error.code', 'MALFORMED_IDEMPOTENCY_KEY');

        $this->assertSame(0, SimulationStartIntent::query()->count());
        $this->assertSame(0, OutboxEvent::query()->count());
    }

    public function test_simulation_start_requires_explicit_sanctum_ability(): void
    {
        $world = $this->world();
        Sanctum::actingAs($world['user'], ['control-plane:read']);

        $this->withHeaders([
            'X-Tenant-Id' => $world['tenant']->id,
            'Idempotency-Key' => (string) Str::uuid7(),
        ])->postJson('/api/v1/simulation-start-requests', ['assignment_id' => $world['assignment']->id])
            ->assertStatus(403);

        $this->assertSame(0, SimulationStartIntent::query()->count());
    }
}
