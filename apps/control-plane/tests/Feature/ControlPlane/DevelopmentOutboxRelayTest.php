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

    public function test_publisher_failure_releases_fenced_claim_and_retry_delivers_same_identity(): void
    {
        $event = $this->newEvent();
        $relay = app(DevelopmentOutboxRelay::class);

        $this->assertSame(0, $relay->relay('worker-failure', static function (): void {
            throw new RuntimeException('publisher unavailable');
        }));
        $failed = OutboxEvent::query()->findOrFail($event->event_id);
        $this->assertNull($failed->published_at);
        $this->assertNull($failed->claim_token);
        $this->assertNull($failed->claimed_by);
        $this->assertSame(1, $failed->attempt_count);

        $received = [];
        $this->assertSame(1, $relay->relay('worker-retry', static function (array $envelope) use (&$received): void {
            $received[] = $envelope;
        }));
        $published = OutboxEvent::query()->findOrFail($event->event_id);
        $this->assertNotNull($published->published_at);
        $this->assertSame(2, $published->attempt_count);
        $this->assertSame($event->event_id, $received[0]['event_id']);
    }

    public function test_crash_after_publish_before_mark_is_reclaimed_and_consumer_deduplicates_same_event_id(): void
    {
        $event = $this->newEvent();
        $relay = app(DevelopmentOutboxRelay::class);

        $crashedClaim = $relay->claimPending('worker-crashed', 1, 1);
        $this->assertCount(1, $crashedClaim);
        $externallyPublishedEventIds = [$crashedClaim[0]->event_id];

        DB::table('outbox_events')->where('event_id', $event->event_id)->update([
            'claimed_at' => now()->subSeconds(2),
            'claim_expires_at' => now()->subSecond(),
        ]);

        $consumerDedupe = array_fill_keys($externallyPublishedEventIds, true);
        $deliveries = [];
        $this->assertSame(1, $relay->relay('worker-reclaimer', static function (array $envelope) use (&$consumerDedupe, &$deliveries): void {
            $deliveries[] = $envelope['event_id'];
            $consumerDedupe[$envelope['event_id']] = true;
        }));

        $published = OutboxEvent::query()->findOrFail($event->event_id);
        $this->assertNotNull($published->published_at);
        $this->assertSame(2, $published->attempt_count);
        $this->assertSame([$event->event_id], $deliveries);
        $this->assertCount(1, $consumerDedupe, 'A consumer deduplicates at-least-once delivery by event_id.');
    }

    private function newEvent(): OutboxEvent
    {
        $tenant = Tenant::query()->create(['name' => 'Tenant', 'slug' => 'tenant-'.substr((string) Str::uuid7(), 0, 8), 'status' => 'active']);

        return OutboxEvent::query()->create([
            'event_id' => (string) Str::uuid7(),
            'command_id' => (string) Str::uuid7(),
            'tenant_id' => $tenant->id,
            'event_type' => 'control.simulation_start.requested',
            'schema_version' => 1,
            'aggregate_type' => 'SimulationStartIntent',
            'aggregate_id' => (string) Str::uuid7(),
            'routing_key' => $tenant->id,
            'classification' => 'INTERNAL',
            'payload' => [
                'command_id' => (string) Str::uuid7(),
                'assignment_id' => (string) Str::uuid7(),
                'scenario_version_id' => (string) Str::uuid7(),
                'requester_user_id' => (string) Str::uuid7(),
                'execution_manifest' => [
                    'manifest_version' => 1,
                    'scenario_contract_version' => 'nexora.scenario.s0.v1',
                    'runtime_contract_version' => 'nexora.vpe.s0.v1',
                    'time_authority' => 'vpe-runtime-owned',
                    'artifact' => [
                        'artifact_id' => (string) Str::uuid7(),
                        'sha256' => str_repeat('a', 64),
                        'content_type' => 'application/json',
                        'size_bytes' => 64,
                        'classification' => 'INTERNAL',
                        'storage_reference' => 'local://scenario/outbox.json',
                    ],
                ],
            ],
            'correlation_id' => (string) Str::uuid7(),
            'causation_id' => (string) Str::uuid7(),
            'occurred_at' => now(),
        ]);
    }
}
