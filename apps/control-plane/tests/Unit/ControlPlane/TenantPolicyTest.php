<?php

declare(strict_types=1);

namespace Tests\Unit\ControlPlane;

use App\Models\Tenant;
use App\Models\TenantMembership;
use App\Models\User;
use App\Policies\TenantPolicy;
use Tests\TestCase;

class TenantPolicyTest extends TestCase
{
    public function test_learner_cannot_perform_tenant_admin_operation(): void
    {
        $policy = new TenantPolicy;
        $user = new User(['id' => '018f73b4-8a2e-7c11-8123-0123456789ab']);
        $tenant = new Tenant(['id' => '018f73b4-8a2f-7c11-8123-0123456789ab']);
        $membership = new TenantMembership(['user_id' => $user->id, 'tenant_id' => $tenant->id, 'role' => 'learner', 'status' => 'active']);

        $this->assertFalse($policy->manageTenant($user, $tenant, $membership));
    }

    public function test_instructor_from_another_tenant_cannot_mutate_this_tenant(): void
    {
        $policy = new TenantPolicy;
        $user = new User(['id' => '018f73b4-8a2e-7c11-8123-0123456789ab']);
        $tenant = new Tenant(['id' => '018f73b4-8a2f-7c11-8123-0123456789ab']);
        $membership = new TenantMembership(['user_id' => $user->id, 'tenant_id' => '018f73b4-8a30-7c11-8123-0123456789ab', 'role' => 'instructor', 'status' => 'active']);

        $this->assertFalse($policy->manageTenant($user, $tenant, $membership));
    }

    public function test_tenant_admin_cannot_gain_global_platform_authority_from_tenant_membership(): void
    {
        $policy = new TenantPolicy;
        $user = new User(['id' => '018f73b4-8a2e-7c11-8123-0123456789ab']);
        $membership = new TenantMembership(['user_id' => $user->id, 'tenant_id' => '018f73b4-8a2f-7c11-8123-0123456789ab', 'role' => 'tenant_admin', 'status' => 'active']);

        $this->assertFalse($policy->manageGlobalPlatform($user, $membership));
    }
}
