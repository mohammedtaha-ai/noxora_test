<?php

declare(strict_types=1);

namespace App\Services;

use App\Exceptions\ControlPlaneException;
use JsonException;
use Opis\JsonSchema\CompliantValidator;
use Opis\JsonSchema\Helper;
use stdClass;

final class PortableEventEnvelope
{
    /** @var array<string, string> */
    private const EVENT_PAYLOAD_SCHEMAS = [
        'control.simulation_start.requested' => '../../contracts/events/control.simulation_start.requested.v1.schema.json',
    ];

    private static ?CompliantValidator $validator = null;

    /** @var array<string, stdClass> */
    private static array $schemas = [];

    /** @param array<string, mixed> $event */
    public static function assertValid(array $event): void
    {
        self::assertMatchesSchema($event, '../../schemas/platform-event-envelope.schema.json');

        $eventType = $event['event_type'] ?? null;
        if (! is_string($eventType) || ! array_key_exists($eventType, self::EVENT_PAYLOAD_SCHEMAS)) {
            throw new ControlPlaneException('UNSUPPORTED_EVENT_SCHEMA', 'No portable payload schema is registered for this event type.', 422);
        }

        self::assertMatchesSchema($event['payload'] ?? null, self::EVENT_PAYLOAD_SCHEMAS[$eventType]);
    }

    private static function assertMatchesSchema(mixed $value, string $relativePath): void
    {
        $result = self::validator()->validate(Helper::toJSON($value), self::schema($relativePath));
        if (! $result->isValid()) {
            throw new ControlPlaneException('MALFORMED_EVENT_PAYLOAD', 'Portable event violates its JSON Schema contract.', 422);
        }
    }

    private static function validator(): CompliantValidator
    {
        return self::$validator ??= new CompliantValidator;
    }

    private static function schema(string $relativePath): stdClass
    {
        if (isset(self::$schemas[$relativePath])) {
            return self::$schemas[$relativePath];
        }

        $path = base_path($relativePath);
        $contents = file_get_contents($path);
        if ($contents === false) {
            throw new \LogicException('Required portable event schema could not be read: '.$path);
        }

        try {
            $schema = json_decode($contents, false, 512, JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new \LogicException('Required portable event schema is invalid JSON: '.$path, previous: $exception);
        }

        if (! $schema instanceof stdClass) {
            throw new \LogicException('Required portable event schema must be a JSON object: '.$path);
        }

        return self::$schemas[$relativePath] = $schema;
    }
}
