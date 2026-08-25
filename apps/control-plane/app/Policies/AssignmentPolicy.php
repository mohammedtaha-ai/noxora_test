<?php

declare(strict_types=1);

namespace App\Policies;

use App\Models\Assignment;
use App\Models\TenantMembership;
use App\Models\User;

class AssignmentPolicy
{
    public function requestSimulationStart(User $user, Assignment $assignment, TenantMembership $membership): bool
    {
        if (! $membership->isActive() || $membership->user_id !== $user->id || $membership->tenant_id !== $assignment->tenant_id) {
            return false;
        }

        return in_array($membership->role, ['learner', 'instructor', 'tenant_admin'], true);
    }
}
