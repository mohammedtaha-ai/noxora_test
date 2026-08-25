<?php

declare(strict_types=1);

namespace App\Models;

class Tenant extends ControlPlaneModel
{
    protected $table = 'tenants';

    public function memberships()
    {
        return $this->hasMany(TenantMembership::class);
    }
}
