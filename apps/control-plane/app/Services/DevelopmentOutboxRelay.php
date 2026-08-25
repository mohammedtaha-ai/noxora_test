<?php

declare(strict_types=1);

namespace App\Services;

use App\Models\OutboxEvent;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Throwable;

final class DevelopmentOutboxRelay
{
    /** @return list<OutboxEvent> */
    public function claimPending(int $limit = 10): array
    {
        return DB::transaction(function () use ($limit): array {
            $events = OutboxEvent::query()
                ->whereNull('published_at')
                ->whereNull('claimed_at')
                ->orderBy('occurred_at')
                ->lock('FOR UPDATE SKIP LOCKED')
                ->limit($limit)
                ->get();

            $claimToken = (string) Str::uuid7();
            foreach ($events as $event) {
                $event->forceFill([
                    'claimed_at' => now(),
                    'claim_token' => $claimToken,
                    'attempt_count' => $event->attempt_count + 1,
                ])->save();
            }

            return $events->all();
        });
    }

    /** @param callable(array<string, mixed>): void $publisher */
    public function relay(callable $publisher, int $limit = 10): int
    {
        $delivered = 0;
        foreach ($this->claimPending($limit) as $event) {
            try {
                $envelope = [
                    'event_id' => $event->event_id,
                    'event_type' => $event->event_type,
                    'schema_version' => $event->schema_version,
                    'occurred_at' => $event->occurred_at->toISOString(),
                    'producer' => 'control-plane.laravel',
                    'tenant_id' => $event->tenant_id,
                    'aggregate_type' => $event->aggregate_type,
                    'aggregate_id' => $event->aggregate_id,
                    'routing_key' => $event->routing_key,
                    'classification' => $event->classification,
                    'payload' => $event->payload,
                    'correlation_id' => $event->correlation_id,
                    'causation_id' => $event->causation_id,
                ];
                PortableEventEnvelope::assertValid($envelope);
                $publisher($envelope);
                $event->forceFill([
                    'published_at' => now(),
                    'claimed_at' => null,
                    'claim_token' => null,
                    'last_error' => null,
                ])->save();
                $delivered++;
            } catch (Throwable $error) {
                $event->forceFill([
                    'claimed_at' => null,
                    'claim_token' => null,
                    'last_error' => substr($error->getMessage(), 0, 500),
                ])->save();
            }
        }

        return $delivered;
    }
}
