<?php

declare(strict_types=1);

namespace Tests\Unit\ControlPlane;

use App\Exceptions\ControlPlaneException;
use App\Services\PortableEventEnvelope;
use Tests\TestCase;

class PortableEventContractTest extends TestCase
{
    public function test_laravel_event_shape_covers_canonical_schema_required_fields_and_rejects_secrets(): void
    {
        $schema = json_decode((string) file_get_contents(base_path('../../schemas/platform-event-envelope.schema.json')), true, flags: JSON_THROW_ON_ERROR);
        $event = [
            'event_id' => '018f73b4-8a2e-7c11-8123-0123456789ab',
            'event_type' => 'control.simulation_start.requested',
            'schema_version' => 1,
            'occurred_at' => '2026-08-25T00:00:00.000Z',
            'producer' => 'control-plane.laravel',
            'tenant_id' => '018f73b4-8a2f-7c11-8123-0123456789ab',
            'aggregate_type' => 'SimulationStartIntent',
            'aggregate_id' => '018f73b4-8a30-7c11-8123-0123456789ab',
            'routing_key' => '018f73b4-8a2f-7c11-8123-0123456789ab',
            'classification' => 'INTERNAL',
            'payload' => ['assignment_id' => '018f73b4-8a31-7c11-8123-0123456789ab'],
            'correlation_id' => '018f73b4-8a32-7c11-8123-0123456789ab',
            'causation_id' => '018f73b4-8a33-7c11-8123-0123456789ab',
        ];

        foreach ($schema['required'] as $field) {
            $this->assertArrayHasKey($field, $event);
        }
        PortableEventEnvelope::assertValid($event);

        $event['payload']['token'] = 'must-not-pass';
        $this->expectException(ControlPlaneException::class);
        $this->expectExceptionObject(new ControlPlaneException('MALFORMED_EVENT_PAYLOAD', 'Portable event payload contains a forbidden field.'));
        PortableEventEnvelope::assertValid($event);
    }
}
