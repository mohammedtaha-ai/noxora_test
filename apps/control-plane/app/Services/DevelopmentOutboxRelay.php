<?php

declare(strict_types=1);

namespace App\Services;

use App\Models\OutboxEvent;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use InvalidArgumentException;
use Throwable;

final class DevelopmentOutboxRelay
{
    public const DEFAULT_LEASE_SECONDS = 30;

    /**
     * Claims unpublished rows that are unclaimed or whose prior lease has expired.
     * Every row receives an independent claim token so a stale worker cannot fence
     * a later worker's publication or failure cleanup.
     *
     * @return list<OutboxEvent>
     */
    public function claimPending(string $workerId, int $limit = 10, int $leaseSeconds = self::DEFAULT_LEASE_SECONDS): array
    {
        $this->assertClaimArguments($workerId, $limit, $leaseSeconds);

        return DB::transaction(function () use ($workerId, $limit, $leaseSeconds): array {
            $claimedAt = now();
            $events = OutboxEvent::query()
                ->whereNull('published_at')
                ->where(function ($query) use ($claimedAt): void {
                    $query->whereNull('claimed_at')
                        ->orWhere('claim_expires_at', '<=', $claimedAt);
                })
                ->orderBy('occurred_at')
                ->lock('FOR UPDATE SKIP LOCKED')
                ->limit($limit)
                ->get();

            foreach ($events as $event) {
                $event->forceFill([
                    'claimed_at' => $claimedAt,
                    'claimed_by' => $workerId,
                    'claim_token' => (string) Str::uuid7(),
                    'claim_expires_at' => $claimedAt->copy()->addSeconds($leaseSeconds),
                    'attempt_count' => $event->attempt_count + 1,
                    'last_error' => null,
                ])->save();
            }

            return $events->all();
        });
    }

    /** @param callable(array<string, mixed>): void $publisher */
    public function relay(string $workerId, callable $publisher, int $limit = 10, int $leaseSeconds = self::DEFAULT_LEASE_SECONDS): int
    {
        $delivered = 0;
        foreach ($this->claimPending($workerId, $limit, $leaseSeconds) as $event) {
            try {
                $envelope = $this->envelope($event);
                PortableEventEnvelope::assertValid($envelope);
                $publisher($envelope);

                if ($this->completeClaim($event, $workerId)) {
                    $delivered++;
                }
            } catch (Throwable $error) {
                $this->releaseClaim($event, $workerId, $error);
            }
        }

        return $delivered;
    }

    private function completeClaim(OutboxEvent $event, string $workerId): bool
    {
        return OutboxEvent::query()
            ->where('event_id', $event->event_id)
            ->whereNull('published_at')
            ->where('claim_token', $event->claim_token)
            ->where('claimed_by', $workerId)
            ->where('claim_expires_at', '>', now())
            ->update([
                'published_at' => now(),
                'claimed_at' => null,
                'claimed_by' => null,
                'claim_token' => null,
                'claim_expires_at' => null,
                'last_error' => null,
            ]) === 1;
    }

    private function releaseClaim(OutboxEvent $event, string $workerId, Throwable $error): void
    {
        OutboxEvent::query()
            ->where('event_id', $event->event_id)
            ->whereNull('published_at')
            ->where('claim_token', $event->claim_token)
            ->where('claimed_by', $workerId)
            ->update([
                'claimed_at' => null,
                'claimed_by' => null,
                'claim_token' => null,
                'claim_expires_at' => null,
                'last_error' => substr($error->getMessage(), 0, 500),
            ]);
    }

    /** @return array<string, mixed> */
    private function envelope(OutboxEvent $event): array
    {
        return [
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
    }

    private function assertClaimArguments(string $workerId, int $limit, int $leaseSeconds): void
    {
        if ($workerId === '' || strlen($workerId) > 128 || $limit < 1 || $limit > 100 || $leaseSeconds < 1 || $leaseSeconds > 3600) {
            throw new InvalidArgumentException('Outbox worker, limit, or lease duration is invalid.');
        }
    }
}
