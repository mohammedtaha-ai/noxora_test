<?php

declare(strict_types=1);

namespace App\Models;

class TenantMembership extends ControlPlaneModel
{
    protected $table = 'tenant_memberships';

    public function tenant()
    {
        return $this->belongsTo(Tenant::class);
    }

    public function user()
    {
        return $this->belongsTo(User::class);
    }

    public function isActive(): bool
    {
        return $this->status === 'active';
    }
}
