<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        DB::unprepared(<<<'SQL'
ALTER TABLE control_plane.simulation_start_intents
    RENAME COLUMN request_id TO idempotency_key;
ALTER TABLE control_plane.simulation_start_intents
    RENAME CONSTRAINT simulation_start_idempotency_unique TO simulation_start_user_idempotency_key_unique;
ALTER TABLE control_plane.simulation_start_intents
    ADD COLUMN request_id uuid;
UPDATE control_plane.simulation_start_intents
    SET request_id = idempotency_key
    WHERE request_id IS NULL;
ALTER TABLE control_plane.simulation_start_intents
    ALTER COLUMN request_id SET NOT NULL;
CREATE INDEX simulation_start_intents_request_id_idx
    ON control_plane.simulation_start_intents (request_id, requested_at DESC);
SQL);
    }

    public function down(): void
    {
        DB::unprepared(<<<'SQL'
DROP INDEX IF EXISTS control_plane.simulation_start_intents_request_id_idx;
ALTER TABLE control_plane.simulation_start_intents DROP COLUMN request_id;
ALTER TABLE control_plane.simulation_start_intents
    RENAME CONSTRAINT simulation_start_user_idempotency_key_unique TO simulation_start_idempotency_unique;
ALTER TABLE control_plane.simulation_start_intents
    RENAME COLUMN idempotency_key TO request_id;
SQL);
    }
};
