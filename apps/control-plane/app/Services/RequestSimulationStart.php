<?php

declare(strict_types=1);

namespace App\Services;

use App\Exceptions\ControlPlaneException;
use App\Models\Assignment;
use App\Models\AuditLog;
use App\Models\CohortMembership;
use App\Models\OutboxEvent;
use App\Models\ScenarioVersion;
use App\Models\SimulationStartIntent;
use App\Models\TenantMembership;
use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\Str;

final class RequestSimulationStart
{
    /**
     * @return array{intent: SimulationStartIntent, created: bool}
     */
    public function handle(
        User $actor,
        string $tenantId,
        string $assignmentId,
        string $idempotencyKey,
        string $requestId,
        string $correlationId,
        bool $forceOutboxFailure = false,
    ): array {
        return DB::transaction(function () use ($actor, $tenantId, $assignmentId, $idempotencyKey, $requestId, $correlationId, $forceOutboxFailure): array {
            // This PostgreSQL transaction-scoped lock serializes concurrent retries of one actor/idempotency key.
            DB::select('SELECT pg_advisory_xact_lock(hashtext(?))', [$actor->id.'|'.$idempotencyKey]);

            $membership = TenantMembership::query()
                ->where('tenant_id', $tenantId)
                ->where('user_id', $actor->id)
                ->where('status', 'active')
                ->lockForUpdate()
                ->first();

            if ($membership === null) {
                throw new ControlPlaneException('SIMULATION_START_FORBIDDEN', 'The authenticated membership is not allowed to request this simulation.', 403);
            }

            $assignment = Assignment::query()
                ->where('id', $assignmentId)
                ->where('tenant_id', $tenantId)
                ->with('scenarioVersion')
                ->lockForUpdate()
                ->first();

            if ($assignment === null) {
                throw new ControlPlaneException('ASSIGNMENT_NOT_FOUND', 'The assignment is not available in this tenant.', 404);
            }

            if (! Gate::forUser($actor)->allows('requestSimulationStart', [$assignment, $membership])) {
                throw new ControlPlaneException('SIMULATION_START_FORBIDDEN', 'The authenticated membership is not allowed to request this simulation.', 403);
            }

            if (! $assignment->isAvailableAt(now())) {
                throw new ControlPlaneException('ASSIGNMENT_NOT_AVAILABLE', 'The assignment is not currently available.');
            }

            $scenarioVersion = $assignment->scenarioVersion;
            if ($scenarioVersion === null || $scenarioVersion->tenant_id !== $tenantId || ! $scenarioVersion->isPublished()) {
                throw new ControlPlaneException('INVALID_SCENARIO_VERSION', 'The assignment does not reference a published tenant scenario version.');
            }

            if ($membership->role === 'learner' && $assignment->cohort_id !== null) {
                $hasCohortAccess = CohortMembership::query()
                    ->where('tenant_id', $tenantId)
                    ->where('cohort_id', $assignment->cohort_id)
                    ->where('user_id', $actor->id)
                    ->exists();
                if (! $hasCohortAccess) {
                    throw new ControlPlaneException('SIMULATION_START_FORBIDDEN', 'The learner is not enrolled in the assigned cohort.', 403);
                }
            }

            $executionManifest = $this->executionManifest($scenarioVersion);
            $fingerprint = hash('sha256', implode('|', [$assignment->id, $scenarioVersion->id]));
            $existing = SimulationStartIntent::query()
                ->where('user_id', $actor->id)
                ->where('idempotency_key', $idempotencyKey)
                ->lockForUpdate()
                ->first();

            if ($existing !== null) {
                if (! hash_equals($existing->intent_fingerprint, $fingerprint)) {
                    throw new ControlPlaneException('IDEMPOTENCY_KEY_REUSED', 'The request identifier was reused with a different simulation intent.', 409);
                }

                return ['intent' => $existing, 'created' => false];
            }

            $commandId = (string) Str::uuid7();
            $intent = SimulationStartIntent::query()->create([
                'command_id' => $commandId,
                'tenant_id' => $tenantId,
                'user_id' => $actor->id,
                'assignment_id' => $assignment->id,
                'scenario_version_id' => $scenarioVersion->id,
                'idempotency_key' => $idempotencyKey,
                'request_id' => $requestId,
                'correlation_id' => $correlationId,
                'intent_fingerprint' => $fingerprint,
                'status' => 'requested',
                'requested_at' => now(),
            ]);

            $event = [
                'event_id' => (string) Str::uuid7(),
                'event_type' => 'control.simulation_start.requested',
                'schema_version' => 1,
                'occurred_at' => now()->toISOString(),
                'producer' => 'control-plane.laravel',
                'tenant_id' => $tenantId,
                'aggregate_type' => 'SimulationStartIntent',
                'aggregate_id' => $intent->id,
                'routing_key' => $tenantId,
                'classification' => 'INTERNAL',
                'payload' => [
                    'command_id' => $commandId,
                    'assignment_id' => $assignment->id,
                    'scenario_version_id' => $scenarioVersion->id,
                    'requester_user_id' => $actor->id,
                    'execution_manifest' => $executionManifest,
                ],
                'correlation_id' => $correlationId,
                'causation_id' => $idempotencyKey,
            ];
            PortableEventEnvelope::assertValid($event);

            if ($forceOutboxFailure) {
                throw new ControlPlaneException('OUTBOX_WRITE_FAILED', 'Forced outbox failure for transactional verification.', 500);
            }

            OutboxEvent::query()->create([
                'event_id' => $event['event_id'],
                'command_id' => $commandId,
                'tenant_id' => $tenantId,
                'event_type' => $event['event_type'],
                'schema_version' => $event['schema_version'],
                'aggregate_type' => $event['aggregate_type'],
                'aggregate_id' => $event['aggregate_id'],
                'routing_key' => $event['routing_key'],
                'classification' => $event['classification'],
                'payload' => $event['payload'],
                'correlation_id' => $correlationId,
                'causation_id' => $idempotencyKey,
                'occurred_at' => $event['occurred_at'],
            ]);

            AuditLog::query()->create([
                'tenant_id' => $tenantId,
                'actor_user_id' => $actor->id,
                'action' => 'simulation_start.authorized',
                'target_type' => 'SimulationStartIntent',
                'target_id' => $intent->id,
                'request_id' => $requestId,
                'correlation_id' => $correlationId,
                'metadata' => ['assignment_id' => $assignment->id, 'scenario_version_id' => $scenarioVersion->id],
                'occurred_at' => now(),
            ]);

            return ['intent' => $intent, 'created' => true];
        }, attempts: 3);
    }

    /** @return array<string, mixed> */
    private function executionManifest(ScenarioVersion $scenarioVersion): array
    {
        $metadata = $scenarioVersion->metadata;
        $scenarioContractVersion = is_array($metadata) ? ($metadata['scenario_contract_version'] ?? null) : null;
        $runtimeContractVersion = is_array($metadata) ? ($metadata['runtime_contract_version'] ?? null) : null;
        $artifactId = $scenarioVersion->artifact_id;
        $artifactHash = $scenarioVersion->artifact_hash;
        $contentType = $scenarioVersion->artifact_content_type;
        $sizeBytes = $scenarioVersion->artifact_size_bytes;
        $storageReference = $scenarioVersion->artifact_storage_reference;

        if (! is_string($scenarioContractVersion) || ! is_string($runtimeContractVersion)
            || ! is_string($artifactId) || ! Str::isUuid($artifactId)
            || ! is_string($artifactHash) || ! preg_match('/^[a-f0-9]{64}$/', $artifactHash)
            || ! is_string($contentType) || $contentType === ''
            || ! is_numeric($sizeBytes) || (int) $sizeBytes < 0
            || ! is_string($storageReference) || $storageReference === '') {
            throw new ControlPlaneException('INVALID_EXECUTION_MANIFEST', 'The published scenario version lacks immutable execution manifest metadata.', 422);
        }

        return [
            'manifest_version' => 1,
            'scenario_contract_version' => $scenarioContractVersion,
            'runtime_contract_version' => $runtimeContractVersion,
            'time_authority' => 'vpe-runtime-owned',
            'artifact' => [
                'artifact_id' => $artifactId,
                'sha256' => $artifactHash,
                'content_type' => $contentType,
                'size_bytes' => (int) $sizeBytes,
                'classification' => $scenarioVersion->artifact_classification,
                'storage_reference' => $storageReference,
            ],
        ];
    }
}
