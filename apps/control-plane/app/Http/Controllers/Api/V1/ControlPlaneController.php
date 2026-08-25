<?php

declare(strict_types=1);

namespace App\Http\Controllers\Api\V1;

use App\Exceptions\ControlPlaneException;
use App\Http\Controllers\Controller;
use App\Models\Assignment;
use App\Models\Scenario;
use App\Models\Tenant;
use App\Services\RequestSimulationStart;
use App\Services\TenantAccess;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;

class ControlPlaneController extends Controller
{
    private function tenantId(Request $request): string
    {
        $tenantId = (string) $request->header('X-Tenant-Id', '');
        if ($tenantId === '') {
            throw new ControlPlaneException('TENANT_CONTEXT_REQUIRED', 'A tenant selection is required.', 422);
        }
        if (! Str::isUuid($tenantId)) {
            throw new ControlPlaneException('MALFORMED_TENANT_IDENTIFIER', 'X-Tenant-Id must be a UUID.', 400);
        }

        return $tenantId;
    }

    public function me(Request $request): JsonResponse
    {
        $user = $request->user();

        return response()->json([
            'data' => [
                'id' => $user->id,
                'name' => $user->name,
                'email' => $user->email,
                'memberships' => $user->memberships()->where('status', 'active')->get(['id', 'tenant_id', 'role', 'status']),
            ],
        ]);
    }

    public function currentTenant(Request $request, TenantAccess $access): JsonResponse
    {
        $tenantId = $this->tenantId($request);
        $membership = $access->activeMembership($request->user(), $tenantId);
        $tenant = Tenant::query()->findOrFail($membership->tenant_id);

        return response()->json(['data' => ['id' => $tenant->id, 'name' => $tenant->name, 'slug' => $tenant->slug, 'role' => $membership->role]]);
    }

    public function scenarios(Request $request, TenantAccess $access): JsonResponse
    {
        $tenantId = $this->tenantId($request);
        $access->activeMembership($request->user(), $tenantId);

        return response()->json(['data' => Scenario::query()->where('tenant_id', $tenantId)->orderBy('title')->get(['id', 'title', 'status'])]);
    }

    public function scenario(Request $request, string $scenarioId, TenantAccess $access): JsonResponse
    {
        $tenantId = $this->tenantId($request);
        $access->activeMembership($request->user(), $tenantId);
        $scenario = Scenario::query()->where('tenant_id', $tenantId)->findOrFail($scenarioId);

        return response()->json(['data' => $scenario->only(['id', 'title', 'status', 'created_at'])]);
    }

    public function assignments(Request $request, TenantAccess $access): JsonResponse
    {
        $tenantId = $this->tenantId($request);
        $access->activeMembership($request->user(), $tenantId);

        return response()->json(['data' => Assignment::query()->where('tenant_id', $tenantId)->orderByDesc('available_from')->get(['id', 'scenario_version_id', 'available_from', 'available_until', 'status'])]);
    }

    public function requestSimulationStart(Request $request, RequestSimulationStart $service): JsonResponse
    {
        $data = $request->validate([
            'assignment_id' => ['required', 'uuid'],
        ]);
        $idempotencyKey = (string) $request->header('Idempotency-Key', '');
        if ($idempotencyKey === '') {
            throw new ControlPlaneException('IDEMPOTENCY_KEY_REQUIRED', 'Idempotency-Key is required for simulation start.', 422);
        }
        if (! Str::isUuid($idempotencyKey)) {
            throw new ControlPlaneException('MALFORMED_IDEMPOTENCY_KEY', 'Idempotency-Key must be a UUID.', 400);
        }
        $tenantId = $this->tenantId($request);
        $result = $service->handle(
            $request->user(),
            $tenantId,
            $data['assignment_id'],
            $idempotencyKey,
            (string) $request->attributes->get('request_id'),
            (string) $request->attributes->get('correlation_id'),
        );
        $intent = $result['intent'];

        return response()->json([
            'data' => [
                'id' => $intent->id,
                'command_id' => $intent->command_id,
                'status' => $intent->status,
                'scenario_version_id' => $intent->scenario_version_id,
            ],
        ], $result['created'] ? 202 : 200);
    }
}
