<?php

declare(strict_types=1);

namespace App\Services;

use App\Exceptions\ControlPlaneException;

final class PortableEventEnvelope
{
    /** @param array<string, mixed> $event */
    public static function assertValid(array $event): void
    {
        $required = [
            'event_id', 'event_type', 'schema_version', 'occurred_at', 'producer',
            'tenant_id', 'aggregate_type', 'aggregate_id', 'routing_key',
            'classification', 'payload',
        ];

        foreach ($required as $field) {
            if (! array_key_exists($field, $event) || $event[$field] === '' || $event[$field] === null) {
                throw new ControlPlaneException('MALFORMED_EVENT_PAYLOAD', 'Portable event is missing '.$field.'.');
            }
        }

        if (! in_array($event['classification'], ['PUBLIC', 'INTERNAL', 'RESTRICTED'], true)) {
            throw new ControlPlaneException('MALFORMED_EVENT_PAYLOAD', 'Portable event classification is invalid.');
        }

        if (! is_array($event['payload'])) {
            throw new ControlPlaneException('MALFORMED_EVENT_PAYLOAD', 'Portable event payload must be an object.');
        }

        foreach (['password', 'token', 'secret'] as $forbidden) {
            if (array_key_exists($forbidden, $event['payload'])) {
                throw new ControlPlaneException('MALFORMED_EVENT_PAYLOAD', 'Portable event payload contains a forbidden field.');
            }
        }
    }
}
