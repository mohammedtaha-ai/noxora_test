package persistence

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/contracts"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/session"
)

var (
	ErrEventIntegrityConflict = errors.New("event integrity conflict")
	ErrLeaseConflict          = errors.New("lease conflict")
	ErrLeaseExpired           = errors.New("lease expired")
	ErrLeaseStateNotEligible  = errors.New("session state is not lease eligible")
	ErrStaleGeneration        = errors.New("stale generation")
	ErrSessionNotFound        = errors.New("session not found")
)

type Repository struct {
	pool *pgxpool.Pool
}

func New(pool *pgxpool.Pool) *Repository {
	return &Repository{pool: pool}
}

func (r *Repository) Ping(ctx context.Context) error {
	return r.pool.Ping(ctx)
}

func (r *Repository) Allocate(ctx context.Context, event contracts.Event) (session.AllocationResult, error) {
	tx, err := r.pool.BeginTx(ctx, pgx.TxOptions{IsoLevel: pgx.ReadCommitted})
	if err != nil {
		return session.AllocationResult{}, fmt.Errorf("begin allocation: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	inserted, err := r.insertReceipt(ctx, tx, event)
	if err != nil {
		return session.AllocationResult{}, err
	}
	if !inserted {
		existing, err := r.lookupReceipt(ctx, tx, event)
		if err != nil {
			return session.AllocationResult{}, err
		}
		if existing.eventID != event.EventID || existing.commandID != event.CommandID || existing.tenantID != event.TenantID || existing.payloadHash != event.PayloadHash {
			return session.AllocationResult{}, ErrEventIntegrityConflict
		}
		existingSession, err := r.getSessionByCommand(ctx, tx, event.CommandID)
		if err != nil {
			return session.AllocationResult{}, err
		}
		if err := tx.Commit(ctx); err != nil {
			return session.AllocationResult{}, fmt.Errorf("commit duplicate allocation: %w", err)
		}
		return session.AllocationResult{Session: existingSession, Duplicate: true}, nil
	}

	manifest, err := json.Marshal(event.Manifest)
	if err != nil {
		return session.AllocationResult{}, fmt.Errorf("marshal validated execution manifest: %w", err)
	}
	created := session.Session{
		ID:                     uuid.New(),
		EventID:                event.EventID,
		CommandID:              event.CommandID,
		TenantID:               event.TenantID,
		AssignmentID:           event.AssignmentID,
		ScenarioVersionID:      event.ScenarioID,
		ScenarioArtifactID:     event.ArtifactID,
		ScenarioArtifactSHA256: event.ArtifactSHA256,
		RuntimeContractVersion: event.RuntimeVersion,
		ExecutionManifest:      event.Manifest,
		State:                  session.StateRequested,
		Generation:             0,
	}
	row := tx.QueryRow(ctx, `
INSERT INTO platform.sessions (
    id, event_id, command_id, tenant_id, assignment_id, scenario_version_id,
    scenario_artifact_id, scenario_artifact_sha256, runtime_contract_version,
    execution_manifest, state, generation
) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11,$12)
RETURNING created_at, updated_at`,
		created.ID, created.EventID, created.CommandID, created.TenantID, created.AssignmentID,
		created.ScenarioVersionID, created.ScenarioArtifactID, created.ScenarioArtifactSHA256,
		created.RuntimeContractVersion, manifest, created.State, created.Generation,
	)
	if err := row.Scan(&created.CreatedAt, &created.UpdatedAt); err != nil {
		return session.AllocationResult{}, fmt.Errorf("insert session: %w", err)
	}
	if _, err := tx.Exec(ctx, `UPDATE platform.command_receipts SET processed_at = now(), status = 'PROCESSED' WHERE event_id = $1`, event.EventID); err != nil {
		return session.AllocationResult{}, fmt.Errorf("mark command receipt processed: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		return session.AllocationResult{}, fmt.Errorf("commit allocation: %w", err)
	}
	return session.AllocationResult{Session: created}, nil
}

type receipt struct {
	eventID     uuid.UUID
	commandID   uuid.UUID
	tenantID    uuid.UUID
	payloadHash string
}

func (r *Repository) insertReceipt(ctx context.Context, tx pgx.Tx, event contracts.Event) (bool, error) {
	var eventID uuid.UUID
	err := tx.QueryRow(ctx, `
INSERT INTO platform.command_receipts (
    event_id, command_id, tenant_id, event_type, schema_version, payload_hash, status
) VALUES ($1,$2,$3,$4,$5,$6,'RECEIVED')
ON CONFLICT DO NOTHING
RETURNING event_id`, event.EventID, event.CommandID, event.TenantID, event.EventType, event.SchemaVersion, event.PayloadHash).Scan(&eventID)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, fmt.Errorf("insert command receipt: %w", err)
	}
	return true, nil
}

func (r *Repository) lookupReceipt(ctx context.Context, tx pgx.Tx, event contracts.Event) (receipt, error) {
	var existing receipt
	err := tx.QueryRow(ctx, `
SELECT event_id, command_id, tenant_id, payload_hash
FROM platform.command_receipts
WHERE event_id = $1 OR command_id = $2
ORDER BY received_at
LIMIT 1
FOR UPDATE`, event.EventID, event.CommandID).Scan(&existing.eventID, &existing.commandID, &existing.tenantID, &existing.payloadHash)
	if err != nil {
		return receipt{}, fmt.Errorf("lookup duplicate command receipt: %w", err)
	}
	return existing, nil
}

func (r *Repository) GetSession(ctx context.Context, sessionID uuid.UUID) (session.Session, error) {
	return r.getSessionByID(ctx, r.pool, sessionID)
}

func (r *Repository) getSessionByCommand(ctx context.Context, querier rowQuerier, commandID uuid.UUID) (session.Session, error) {
	return r.scanSession(querier.QueryRow(ctx, sessionSelect+` WHERE command_id = $1`, commandID))
}

func (r *Repository) getSessionByID(ctx context.Context, querier rowQuerier, sessionID uuid.UUID) (session.Session, error) {
	return r.scanSession(querier.QueryRow(ctx, sessionSelect+` WHERE id = $1`, sessionID))
}

const sessionSelect = `
SELECT id, event_id, command_id, tenant_id, assignment_id, scenario_version_id,
       scenario_artifact_id, scenario_artifact_sha256, runtime_contract_version,
       execution_manifest, state, generation, created_at, updated_at
FROM platform.sessions`

type rowQuerier interface {
	QueryRow(context.Context, string, ...any) pgx.Row
}

func (r *Repository) scanSession(row pgx.Row) (session.Session, error) {
	var found session.Session
	var manifest []byte
	if err := row.Scan(
		&found.ID, &found.EventID, &found.CommandID, &found.TenantID, &found.AssignmentID,
		&found.ScenarioVersionID, &found.ScenarioArtifactID, &found.ScenarioArtifactSHA256,
		&found.RuntimeContractVersion, &manifest, &found.State, &found.Generation,
		&found.CreatedAt, &found.UpdatedAt,
	); err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return session.Session{}, ErrSessionNotFound
		}
		return session.Session{}, fmt.Errorf("scan session: %w", err)
	}
	if err := json.Unmarshal(manifest, &found.ExecutionManifest); err != nil {
		return session.Session{}, fmt.Errorf("decode stored execution manifest: %w", err)
	}
	return found, nil
}

func (r *Repository) ClaimLease(ctx context.Context, sessionID uuid.UUID, ownerID string, duration time.Duration) (session.LeaseClaimResult, error) {
	leaseDurationMicros := duration.Microseconds()
	if ownerID == "" || len(ownerID) > 128 || leaseDurationMicros <= 0 {
		return session.LeaseClaimResult{}, ErrLeaseConflict
	}
	tx, err := r.pool.BeginTx(ctx, pgx.TxOptions{IsoLevel: pgx.ReadCommitted})
	if err != nil {
		return session.LeaseClaimResult{}, fmt.Errorf("begin lease claim: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	var currentGeneration int64
	var currentState session.State
	if err := tx.QueryRow(ctx, `SELECT generation, state FROM platform.sessions WHERE id = $1 FOR UPDATE`, sessionID).Scan(&currentGeneration, &currentState); err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return session.LeaseClaimResult{}, ErrSessionNotFound
		}
		return session.LeaseClaimResult{}, fmt.Errorf("lock session for lease: %w", err)
	}
	if !currentState.LeaseEligible() {
		return session.LeaseClaimResult{}, ErrLeaseStateNotEligible
	}

	var existing session.Lease
	var existingLeaseActive bool
	err = tx.QueryRow(ctx, `
	SELECT session_id, owner_id, lease_token, lease_generation, lease_expires_at, updated_at,
	       lease_expires_at > clock_timestamp()
	FROM platform.session_leases WHERE session_id = $1 FOR UPDATE`, sessionID).Scan(
		&existing.SessionID, &existing.OwnerID, &existing.LeaseToken, &existing.LeaseGeneration, &existing.LeaseExpiresAt, &existing.UpdatedAt, &existingLeaseActive,
	)
	hasExisting := err == nil
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return session.LeaseClaimResult{}, fmt.Errorf("lock current lease: %w", err)
	}
	if hasExisting && existingLeaseActive {
		return session.LeaseClaimResult{}, ErrLeaseConflict
	}

	nextGeneration := currentGeneration + 1
	if _, err := tx.Exec(ctx, `UPDATE platform.sessions SET generation = $2, future_worker_route = NULL, future_worker_route_generation = NULL, updated_at = clock_timestamp() WHERE id = $1`, sessionID, nextGeneration); err != nil {
		return session.LeaseClaimResult{}, fmt.Errorf("advance session generation: %w", err)
	}
	lease := session.Lease{
		SessionID:       sessionID,
		OwnerID:         ownerID,
		LeaseToken:      uuid.New(),
		LeaseGeneration: nextGeneration,
	}
	if hasExisting {
		err = tx.QueryRow(ctx, `
	UPDATE platform.session_leases
	SET owner_id = $2, lease_token = $3, lease_generation = $4,
	    lease_expires_at = clock_timestamp() + ($5 * interval '1 microsecond'),
	    updated_at = clock_timestamp()
	WHERE session_id = $1
	RETURNING lease_expires_at, updated_at`, lease.SessionID, lease.OwnerID, lease.LeaseToken, lease.LeaseGeneration, leaseDurationMicros).Scan(&lease.LeaseExpiresAt, &lease.UpdatedAt)
	} else {
		err = tx.QueryRow(ctx, `
	INSERT INTO platform.session_leases (session_id, owner_id, lease_token, lease_generation, lease_expires_at)
	VALUES ($1,$2,$3,$4,clock_timestamp() + ($5 * interval '1 microsecond'))
	RETURNING lease_expires_at, updated_at`, lease.SessionID, lease.OwnerID, lease.LeaseToken, lease.LeaseGeneration, leaseDurationMicros).Scan(&lease.LeaseExpiresAt, &lease.UpdatedAt)
	}
	if err != nil {
		return session.LeaseClaimResult{}, fmt.Errorf("persist lease: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		return session.LeaseClaimResult{}, fmt.Errorf("commit lease claim: %w", err)
	}
	return session.LeaseClaimResult{Lease: lease, Reclaimed: hasExisting}, nil
}

func (r *Repository) RenewLease(ctx context.Context, lease session.Lease, duration time.Duration) (session.Lease, error) {
	leaseDurationMicros := duration.Microseconds()
	if leaseDurationMicros <= 0 {
		return session.Lease{}, ErrLeaseConflict
	}
	err := r.pool.QueryRow(ctx, `
	UPDATE platform.session_leases AS l
	SET lease_expires_at = clock_timestamp() + ($5 * interval '1 microsecond'),
	    updated_at = clock_timestamp()
	FROM platform.sessions AS s
	WHERE l.session_id = $1
	  AND l.session_id = s.id
	  AND s.state = 'PENDING_WORKER'
	  AND l.owner_id = $2
	  AND l.lease_token = $3
	  AND l.lease_generation = $4
	  AND l.lease_expires_at > clock_timestamp()
	RETURNING l.lease_expires_at, l.updated_at`, lease.SessionID, lease.OwnerID, lease.LeaseToken, lease.LeaseGeneration, leaseDurationMicros).Scan(&lease.LeaseExpiresAt, &lease.UpdatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return session.Lease{}, r.leaseMiss(ctx, lease)
	}
	if err != nil {
		return session.Lease{}, fmt.Errorf("renew lease: %w", err)
	}
	return lease, nil
}

func (r *Repository) SetFutureWorkerRoute(ctx context.Context, lease session.Lease, route string) error {
	if route == "" || len(route) > 256 {
		return ErrLeaseConflict
	}
	commandTag, err := r.pool.Exec(ctx, `
UPDATE platform.sessions AS s
SET future_worker_route = $5, future_worker_route_generation = $4, updated_at = clock_timestamp()
	WHERE s.id = $1
	  AND s.state = 'PENDING_WORKER'
	  AND s.generation = $4

  AND EXISTS (
      SELECT 1 FROM platform.session_leases AS l
      WHERE l.session_id = s.id
        AND l.owner_id = $2
        AND l.lease_token = $3
        AND l.lease_generation = $4
        AND l.lease_expires_at > now()
  )`, lease.SessionID, lease.OwnerID, lease.LeaseToken, lease.LeaseGeneration, route)
	if err != nil {
		return fmt.Errorf("set future worker route: %w", err)
	}
	if commandTag.RowsAffected() != 1 {
		return r.leaseMiss(ctx, lease)
	}
	return nil
}

func (r *Repository) leaseMiss(ctx context.Context, lease session.Lease) error {
	var state session.State
	var leaseActive bool
	err := r.pool.QueryRow(ctx, `
	SELECT s.state, COALESCE(l.lease_expires_at > clock_timestamp(), false)
	FROM platform.sessions AS s
	LEFT JOIN platform.session_leases AS l ON l.session_id = s.id
	WHERE s.id = $1`, lease.SessionID).Scan(&state, &leaseActive)
	if errors.Is(err, pgx.ErrNoRows) {
		return ErrLeaseExpired
	}
	if err != nil {
		return fmt.Errorf("inspect lease miss: %w", err)
	}
	if !state.LeaseEligible() {
		return ErrLeaseStateNotEligible
	}
	if !leaseActive {
		return ErrLeaseExpired
	}
	return ErrStaleGeneration
}
