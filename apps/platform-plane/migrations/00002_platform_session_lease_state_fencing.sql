-- +goose Up
ALTER TABLE platform.sessions
    ADD CONSTRAINT sessions_route_requires_pending_worker_check
    CHECK (
        state = 'PENDING_WORKER'
        OR (future_worker_route IS NULL AND future_worker_route_generation IS NULL)
    );

-- +goose StatementBegin
CREATE OR REPLACE FUNCTION platform.require_lease_eligible_session_state()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    current_state varchar(32);
BEGIN
    SELECT state INTO current_state
    FROM platform.sessions
    WHERE id = NEW.session_id
    FOR KEY SHARE;

    IF current_state IS NULL THEN
        RAISE EXCEPTION 'platform session % does not exist', NEW.session_id
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    IF current_state <> 'PENDING_WORKER' THEN
        RAISE EXCEPTION 'platform session % state % is not lease eligible', NEW.session_id, current_state
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$;
-- +goose StatementEnd

CREATE TRIGGER session_leases_require_pending_worker
BEFORE INSERT OR UPDATE ON platform.session_leases
FOR EACH ROW
EXECUTE FUNCTION platform.require_lease_eligible_session_state();

-- +goose StatementBegin
CREATE OR REPLACE FUNCTION platform.prevent_terminal_session_ownership()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.state <> 'PENDING_WORKER'
       AND EXISTS (SELECT 1 FROM platform.session_leases WHERE session_id = NEW.id) THEN
        RAISE EXCEPTION 'platform session % cannot leave PENDING_WORKER while a lease exists', NEW.id
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$;
-- +goose StatementEnd

CREATE TRIGGER sessions_prevent_terminal_ownership
BEFORE UPDATE OF state ON platform.sessions
FOR EACH ROW
EXECUTE FUNCTION platform.prevent_terminal_session_ownership();

-- +goose Down
DROP TRIGGER IF EXISTS sessions_prevent_terminal_ownership ON platform.sessions;
DROP FUNCTION IF EXISTS platform.prevent_terminal_session_ownership();
DROP TRIGGER IF EXISTS session_leases_require_pending_worker ON platform.session_leases;
DROP FUNCTION IF EXISTS platform.require_lease_eligible_session_state();
ALTER TABLE platform.sessions
    DROP CONSTRAINT IF EXISTS sessions_route_requires_pending_worker_check;
