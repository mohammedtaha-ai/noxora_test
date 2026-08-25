<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        DB::unprepared(<<<'SQL'
ALTER TABLE control_plane.outbox_events
    ADD COLUMN claimed_by varchar(128) NULL,
    ADD COLUMN claim_expires_at timestamptz NULL;
ALTER TABLE control_plane.outbox_events
    ADD CONSTRAINT outbox_events_claim_state_check CHECK (
        (claim_token IS NULL AND claimed_at IS NULL AND claimed_by IS NULL AND claim_expires_at IS NULL)
        OR
        (claim_token IS NOT NULL AND claimed_at IS NOT NULL AND claimed_by IS NOT NULL AND claim_expires_at IS NOT NULL AND claim_expires_at > claimed_at)
    );
CREATE INDEX outbox_events_claimable_idx
    ON control_plane.outbox_events (occurred_at, claim_expires_at)
    WHERE published_at IS NULL;
SQL);
    }

    public function down(): void
    {
        DB::unprepared(<<<'SQL'
DROP INDEX IF EXISTS control_plane.outbox_events_claimable_idx;
ALTER TABLE control_plane.outbox_events DROP CONSTRAINT IF EXISTS outbox_events_claim_state_check;
ALTER TABLE control_plane.outbox_events
    DROP COLUMN IF EXISTS claim_expires_at,
    DROP COLUMN IF EXISTS claimed_by;
SQL);
    }
};
