<?php

declare(strict_types=1);

namespace Tests\Feature\ControlPlane;

use App\Models\OutboxEvent;
use App\Models\Tenant;
use App\Services\DevelopmentOutboxRelay;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use RuntimeException;
use Tests\TestCase;

class DevelopmentOutboxRelayTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        DB::unprepared('TRUNCATE TABLE control_plane.audit_logs, control_plane.outbox_events, control_plane.simulation_start_intents, control_plane.assignments, control_plane.scenario_versions, control_plane.scenarios, control_plane.cohort_memberships, control_plane.cohorts, control_plane.courses, control_plane.programs, control_plane.tenant_memberships, control_plane.tenants, control_plane.personal_access_tokens, control_plane.users RESTART IDENTITY CASCADE');
    }

    public function test_failure_leaves_event_unpublished_and_retry_delivers_same_identity(): void
    {
        $tenant = Tenant::query()->create(['name' => 'Tenant', 'slug' => 'tenant-'.substr((string) Str::uuid7(), 0, 8), 'status' => 'active']);
        $eventId = (string) Str::uuid7();
        OutboxEvent::query()->create([
            'event_id' => $eventId,
            'command_id' => (string) Str::uuid7(),
            'tenant_id' => $tenant->id,
            'event_type' => 'control.simulation_start.requested',
            'schema_version' => 1,
            'aggregate_type' => 'SimulationStartIntent',
            'aggregate_id' => (string) Str::uuid7(),
            'routing_key' => $tenant->id,
            'classification' => 'INTERNAL',
            'payload' => ['assignment_id' => (string) Str::uuid7()],
            'correlation_id' => (string) Str::uuid7(),
            'causation_id' => (string) Str::uuid7(),
            'occurred_at' => now(),
        ]);

        $relay = app(DevelopmentOutboxRelay::class);
        $this->assertSame(0, $relay->relay(static function (): void {
            throw new RuntimeException('publisher unavailable');
        }));
        $failed = OutboxEvent::query()->findOrFail($eventId);
        $this->assertNull($failed->published_at);
        $this->assertSame(1, $failed->attempt_count);

        $received = [];
        $this->assertSame(1, $relay->relay(static function (array $event) use (&$received): void {
            $received[] = $event;
        }));
        $published = OutboxEvent::query()->findOrFail($eventId);
        $this->assertNotNull($published->published_at);
        $this->assertSame(2, $published->attempt_count);
        $this->assertSame($eventId, $received[0]['event_id']);
    }
}
