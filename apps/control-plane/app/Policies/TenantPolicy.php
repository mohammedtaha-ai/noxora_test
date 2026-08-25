<?php

declare(strict_types=1);

namespace App\Policies;

use App\Models\Tenant;
use App\Models\TenantMembership;
use App\Models\User;

class TenantPolicy
{
    public function manageTenant(User $user, Tenant $tenant, TenantMembership $membership): bool
    {
        return $membership->isActive()
            && $membership->user_id === $user->id
            && $membership->tenant_id === $tenant->id
            && $membership->role === 'tenant_admin';
    }

    public function manageGlobalPlatform(User $user, TenantMembership $membership): bool
    {
        return false;
    }
}
