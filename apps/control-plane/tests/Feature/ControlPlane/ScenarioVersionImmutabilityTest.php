<?php

declare(strict_types=1);

namespace Tests\Feature\ControlPlane;

use App\Models\Scenario;
use App\Models\ScenarioVersion;
use App\Models\Tenant;
use App\Models\User;
use Illuminate\Database\QueryException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class ScenarioVersionImmutabilityTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        DB::unprepared('TRUNCATE TABLE control_plane.audit_logs, control_plane.outbox_events, control_plane.simulation_start_intents, control_plane.assignments, control_plane.scenario_versions, control_plane.scenarios, control_plane.cohort_memberships, control_plane.cohorts, control_plane.courses, control_plane.programs, control_plane.tenant_memberships, control_plane.tenants, control_plane.personal_access_tokens, control_plane.users RESTART IDENTITY CASCADE');
    }

    public function test_published_scenario_version_cannot_be_edited_in_place(): void
    {
        $user = User::query()->create(['name' => 'Author', 'email' => Str::uuid7().'@example.test', 'password' => 'test-password']);
        $tenant = Tenant::query()->create(['name' => 'Tenant', 'slug' => 'tenant-'.substr((string) Str::uuid7(), 0, 8), 'status' => 'active']);
        $scenario = Scenario::query()->create(['tenant_id' => $tenant->id, 'title' => 'Scenario', 'status' => 'draft', 'created_by' => $user->id]);
        $version = ScenarioVersion::query()->create(['tenant_id' => $tenant->id, 'scenario_id' => $scenario->id, 'version_number' => 1, 'status' => 'published', 'title' => 'Published', 'metadata' => [], 'created_by' => $user->id, 'published_at' => now()]);

        $this->expectException(QueryException::class);
        $version->update(['title' => 'Mutated in place']);
    }
}
