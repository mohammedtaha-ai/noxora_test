<?php

declare(strict_types=1);

namespace Tests\Feature\ControlPlane;

use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class DatabaseOwnershipTest extends TestCase
{
    public function test_laravel_migration_repository_and_application_relations_stay_in_control_plane_schema(): void
    {
        $this->assertSame('control_plane.migrations', config('database.migrations.table'));
        $forbiddenSchemas = DB::select("SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('platform', 'session_registry')");
        $this->assertSame([], $forbiddenSchemas);
        $outboxSchema = DB::selectOne("SELECT table_schema FROM information_schema.tables WHERE table_name = 'outbox_events'");
        $this->assertSame('control_plane', $outboxSchema->table_schema);
    }
}
