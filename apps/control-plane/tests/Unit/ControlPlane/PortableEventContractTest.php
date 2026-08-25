<?php

declare(strict_types=1);

namespace Tests\Unit\ControlPlane;

use App\Exceptions\ControlPlaneException;
use App\Services\PortableEventEnvelope;
use Illuminate\Support\Str;
use Tests\TestCase;

class PortableEventContractTest extends TestCase
{
    public function test_php_executes_generic_and_event_specific_json_schemas_for_a_valid_event(): void
    {
        $event = $this->validEvent();

        PortableEventEnvelope::assertValid($event);
        $this->addToAssertionCount(1);
    }

    public function test_laravel_validates_shared_platform_contract_fixtures(): void
    {
        PortableEventEnvelope::assertValid($this->fixture('simulation_start_requested_v1.valid.json'));
        $this->addToAssertionCount(1);

        foreach ([
            'simulation_start_requested_v1.invalid_extra_property.json',
            'simulation_start_requested_v1.invalid_uuid.json',
            'simulation_start_requested_v1.invalid_manifest.json',
        ] as $fixture) {
            $this->assertMalformed($this->fixture($fixture));
        }
    }

    public function test_schema_rejects_malformed_uuid_datetime_and_unknown_event_type(): void
    {
        $malformedUuid = $this->validEvent();
        $malformedUuid['event_id'] = 'not-a-uuid';
        $this->assertMalformed($malformedUuid);

        $malformedDatetime = $this->validEvent();
        $malformedDatetime['occurred_at'] = 'not-a-datetime';
        $this->assertMalformed($malformedDatetime);

        $unknownType = $this->validEvent();
        $unknownType['event_type'] = 'control.unknown.requested';
        try {
            PortableEventEnvelope::assertValid($unknownType);
            $this->fail('Expected unknown event schema rejection.');
        } catch (ControlPlaneException $exception) {
            $this->assertSame('UNSUPPORTED_EVENT_SCHEMA', $exception->errorCode);
        }
    }

    public function test_event_payload_schema_rejects_missing_fields_and_recursive_unknown_fields(): void
    {
        $missingCommand = $this->validEvent();
        unset($missingCommand['payload']['command_id']);
        $this->assertMalformed($missingCommand);

        $extraPayloadProperty = $this->validEvent();
        $extraPayloadProperty['payload']['token'] = 'must-not-pass';
        $this->assertMalformed($extraPayloadProperty);

        $nestedSecret = $this->validEvent();
        $nestedSecret['payload']['execution_manifest']['artifact']['secret'] = 'must-not-pass';
        $this->assertMalformed($nestedSecret);
    }

    /** @param array<string, mixed> $event */
    private function assertMalformed(array $event): void
    {
        try {
            PortableEventEnvelope::assertValid($event);
            $this->fail('Expected JSON Schema rejection.');
        } catch (ControlPlaneException $exception) {
            $this->assertSame('MALFORMED_EVENT_PAYLOAD', $exception->errorCode);
        }
    }

    /** @return array<string, mixed> */
    private function fixture(string $filename): array
    {
        $contents = file_get_contents(base_path('../../contracts/fixtures/'.$filename));
        self::assertIsString($contents);
        $decoded = json_decode($contents, true, 512, JSON_THROW_ON_ERROR);
        self::assertIsArray($decoded);

        return $decoded;
    }

    /** @return array<string, mixed> */
    private function validEvent(): array
    {
        return [
            'event_id' => (string) Str::uuid7(),
            'event_type' => 'control.simulation_start.requested',
            'schema_version' => 1,
            'occurred_at' => '2026-08-25T00:00:00.000Z',
            'producer' => 'control-plane.laravel',
            'tenant_id' => (string) Str::uuid7(),
            'aggregate_type' => 'SimulationStartIntent',
            'aggregate_id' => (string) Str::uuid7(),
            'routing_key' => (string) Str::uuid7(),
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
                        'storage_reference' => 'local://scenario/v1.json',
                    ],
                ],
            ],
            'correlation_id' => (string) Str::uuid7(),
            'causation_id' => (string) Str::uuid7(),
        ];
    }
}
