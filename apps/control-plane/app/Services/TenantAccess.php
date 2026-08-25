<?php

declare(strict_types=1);

namespace App\Services;

use App\Exceptions\ControlPlaneException;
use App\Models\TenantMembership;
use App\Models\User;

final class TenantAccess
{
    public function activeMembership(User $user, string $tenantId): TenantMembership
    {
        $membership = TenantMembership::query()
            ->where('tenant_id', $tenantId)
            ->where('user_id', $user->id)
            ->where('status', 'active')
            ->first();

        if ($membership === null) {
            throw new ControlPlaneException('TENANT_ACCESS_DENIED', 'The authenticated user has no active membership in this tenant.', 403);
        }

        return $membership;
    }
}
