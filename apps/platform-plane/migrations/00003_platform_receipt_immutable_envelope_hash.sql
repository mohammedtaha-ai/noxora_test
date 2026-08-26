-- +goose Up
ALTER TABLE platform.command_receipts
    ADD COLUMN immutable_envelope_hash char(64) NULL,
    ADD CONSTRAINT command_receipts_immutable_envelope_hash_check
        CHECK (immutable_envelope_hash IS NULL OR immutable_envelope_hash ~ '^[a-f0-9]{64}$');

-- A legacy receipt without this field is intentionally not a safe duplicate match.
-- New inserts from the Phase-1 consumer always persist a non-null canonical hash.

-- +goose Down
ALTER TABLE platform.command_receipts
    DROP CONSTRAINT IF EXISTS command_receipts_immutable_envelope_hash_check,
    DROP COLUMN IF EXISTS immutable_envelope_hash;
