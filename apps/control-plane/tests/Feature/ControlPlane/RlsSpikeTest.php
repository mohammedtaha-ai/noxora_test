<?php

declare(strict_types=1);

namespace Tests\Feature\ControlPlane;

use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class RlsSpikeTest extends TestCase
{
    public function test_forced_rls_uses_transaction_tenant_context_and_denies_without_context(): void
    {
        DB::unprepared(<<<'SQL'
DROP TABLE IF EXISTS control_plane.rls_spike_records;
CREATE TABLE control_plane.rls_spike_records (tenant_id uuid NOT NULL, value text NOT NULL);
INSERT INTO control_plane.rls_spike_records (tenant_id, value) VALUES
 ('11111111-1111-7111-8111-111111111111', 'tenant-a'),
 ('22222222-2222-7222-8222-222222222222', 'tenant-b');
ALTER TABLE control_plane.rls_spike_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE control_plane.rls_spike_records FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_spike_tenant_policy ON control_plane.rls_spike_records
 USING (tenant_id::text = current_setting('app.tenant_id', true))
 WITH CHECK (tenant_id::text = current_setting('app.tenant_id', true));
SQL);

        $withoutContext = DB::select('SELECT value FROM control_plane.rls_spike_records ORDER BY value');
        $this->assertSame([], $withoutContext);

        $tenantA = DB::transaction(function (): array {
            DB::statement("SET LOCAL app.tenant_id = '11111111-1111-7111-8111-111111111111'");

            return DB::select('SELECT value FROM control_plane.rls_spike_records ORDER BY value');
        });
        $tenantB = DB::transaction(function (): array {
            DB::statement("SET LOCAL app.tenant_id = '22222222-2222-7222-8222-222222222222'");

            return DB::select('SELECT value FROM control_plane.rls_spike_records ORDER BY value');
        });

        $this->assertSame('tenant-a', $tenantA[0]->value);
        $this->assertSame('tenant-b', $tenantB[0]->value);
        DB::statement('DROP TABLE control_plane.rls_spike_records');
    }
}
