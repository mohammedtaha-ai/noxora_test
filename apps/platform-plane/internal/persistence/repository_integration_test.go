package persistence_test

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	_ "github.com/jackc/pgx/v5/stdlib"
	"github.com/pressly/goose/v3"

	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/contracts"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/persistence"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/session"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/testsupport"
)

func TestPostgresAllocationDeduplicatesAndFencesConflicts(t *testing.T) {
	repository, pool := newIntegrationRepository(t)
	event := validEvent(t)

	first, err := repository.Allocate(context.Background(), event)
	if err != nil {
		t.Fatalf("first allocation: %v", err)
	}
	if first.Duplicate || first.Session.State != session.StateRequested {
		t.Fatalf("unexpected first allocation: %+v", first)
	}
	second, err := repository.Allocate(context.Background(), event)
	if err != nil {
		t.Fatalf("redelivery allocation: %v", err)
	}
	if !second.Duplicate || second.Session.ID != first.Session.ID {
		t.Fatalf("redelivery did not return original session: first=%s second=%s duplicate=%t", first.Session.ID, second.Session.ID, second.Duplicate)
	}

	conflicting := event
	conflicting.TenantID = uuid.MustParse("018f5f54-8c8e-7000-8000-000000000099")
	_, err = repository.Allocate(context.Background(), conflicting)
	if !errors.Is(err, persistence.ErrEventIntegrityConflict) {
		t.Fatalf("cross-tenant duplicate should conflict, got %v", err)
	}
	assertCount(t, pool, "SELECT count(*) FROM platform.command_receipts", 1)
	assertCount(t, pool, "SELECT count(*) FROM platform.sessions", 1)
}

func TestPostgresConcurrentSameEventCreatesOneReceiptAndSession(t *testing.T) {
	repository, pool := newIntegrationRepository(t)
	event := validEvent(t)

	const deliveries = 16
	start := make(chan struct{})
	errorsByDelivery := make(chan error, deliveries)
	results := make(chan session.AllocationResult, deliveries)
	var workers sync.WaitGroup
	for range deliveries {
		workers.Add(1)
		go func() {
			defer workers.Done()
			<-start
			result, err := repository.Allocate(context.Background(), event)
			errorsByDelivery <- err
			results <- result
		}()
	}
	close(start)
	workers.Wait()
	close(errorsByDelivery)
	close(results)

	var sessionID uuid.UUID
	for err := range errorsByDelivery {
		if err != nil {
			t.Fatalf("concurrent allocation error: %v", err)
		}
	}
	for result := range results {
		if sessionID == uuid.Nil {
			sessionID = result.Session.ID
		}
		if result.Session.ID != sessionID {
			t.Fatalf("more than one session allocated: %s and %s", sessionID, result.Session.ID)
		}
	}
	assertCount(t, pool, "SELECT count(*) FROM platform.command_receipts", 1)
	assertCount(t, pool, "SELECT count(*) FROM platform.sessions", 1)
}

func TestPostgresLeaseRaceExpiryReclaimAndStaleFencing(t *testing.T) {
	repository, pool := newIntegrationRepository(t)
	allocation, err := repository.Allocate(context.Background(), validEvent(t))
	if err != nil {
		t.Fatalf("allocate session: %v", err)
	}
	setSessionState(t, pool, allocation.Session.ID, session.StatePendingWorker)

	owners := []string{"allocator-a", "allocator-b"}
	start := make(chan struct{})
	outcomes := make(chan error, len(owners))
	var workers sync.WaitGroup
	for _, owner := range owners {
		owner := owner
		workers.Add(1)
		go func() {
			defer workers.Done()
			<-start
			_, claimError := repository.ClaimLease(context.Background(), allocation.Session.ID, owner, 50*time.Millisecond)
			outcomes <- claimError
		}()
	}
	close(start)
	workers.Wait()
	close(outcomes)

	var wins int
	for outcome := range outcomes {
		if outcome == nil {
			wins++
			continue
		}
		if !errors.Is(outcome, persistence.ErrLeaseConflict) {
			t.Fatalf("unexpected lease race outcome: %v", outcome)
		}
	}
	if wins != 1 {
		t.Fatalf("lease race winners = %d, want 1", wins)
	}
	assertCount(t, pool, "SELECT count(*) FROM platform.session_leases", 1)

	var oldLease session.Lease
	if err := pool.QueryRow(context.Background(), `SELECT session_id, owner_id, lease_token, lease_generation, lease_expires_at, updated_at FROM platform.session_leases WHERE session_id=$1`, allocation.Session.ID).Scan(
		&oldLease.SessionID, &oldLease.OwnerID, &oldLease.LeaseToken, &oldLease.LeaseGeneration, &oldLease.LeaseExpiresAt, &oldLease.UpdatedAt,
	); err != nil {
		t.Fatalf("load old lease: %v", err)
	}
	if _, err := pool.Exec(context.Background(), `
		UPDATE platform.session_leases
		SET updated_at = clock_timestamp() - interval '1 hour',
		    lease_expires_at = clock_timestamp() - interval '1 microsecond'
		WHERE session_id = $1`, allocation.Session.ID); err != nil {
		t.Fatalf("force lease expiry on PostgreSQL clock: %v", err)
	}
	newClaim, err := repository.ClaimLease(context.Background(), allocation.Session.ID, "allocator-reclaimer", time.Second)
	if err != nil {
		t.Fatalf("reclaim expired lease: %v", err)
	}
	if !newClaim.Reclaimed || newClaim.Lease.LeaseGeneration <= oldLease.LeaseGeneration {
		t.Fatalf("invalid reclaimed lease: old=%+v new=%+v", oldLease, newClaim.Lease)
	}
	if err := repository.SetFutureWorkerRoute(context.Background(), oldLease, "future://stale-worker"); !errors.Is(err, persistence.ErrStaleGeneration) {
		t.Fatalf("stale owner route update should be fenced, got %v", err)
	}
	if _, err := repository.RenewLease(context.Background(), oldLease, time.Second); !errors.Is(err, persistence.ErrStaleGeneration) {
		t.Fatalf("stale owner renewal should be fenced, got %v", err)
	}
	if err := repository.SetFutureWorkerRoute(context.Background(), newClaim.Lease, "future://worker-route"); err != nil {
		t.Fatalf("current owner route update: %v", err)
	}
}

func TestPostgresTerminalSessionsRejectLeaseAndRouteOwnership(t *testing.T) {
	repository, pool := newIntegrationRepository(t)
	allocation, err := repository.Allocate(context.Background(), validEvent(t))
	if err != nil {
		t.Fatalf("allocate session: %v", err)
	}

	for _, terminal := range []session.State{session.StateFailed, session.StateCancelled} {
		t.Run(string(terminal), func(t *testing.T) {
			setSessionState(t, pool, allocation.Session.ID, terminal)
			if _, err := repository.ClaimLease(context.Background(), allocation.Session.ID, "terminal-owner", time.Second); !errors.Is(err, persistence.ErrLeaseStateNotEligible) {
				t.Fatalf("ClaimLease() error = %v, want terminal-state rejection", err)
			}
			forgedLease := session.Lease{SessionID: allocation.Session.ID, OwnerID: "terminal-owner", LeaseToken: uuid.New(), LeaseGeneration: 1}
			if _, err := repository.RenewLease(context.Background(), forgedLease, time.Second); !errors.Is(err, persistence.ErrLeaseStateNotEligible) {
				t.Fatalf("RenewLease() error = %v, want terminal-state rejection", err)
			}
			if err := repository.SetFutureWorkerRoute(context.Background(), forgedLease, "future://terminal"); !errors.Is(err, persistence.ErrLeaseStateNotEligible) {
				t.Fatalf("SetFutureWorkerRoute() error = %v, want terminal-state rejection", err)
			}
		})
	}
}

func setSessionState(t *testing.T, pool *pgxpool.Pool, sessionID uuid.UUID, state session.State) {
	t.Helper()
	if _, err := pool.Exec(context.Background(), `UPDATE platform.sessions SET state = $2, updated_at = clock_timestamp() WHERE id = $1`, sessionID, state); err != nil {
		t.Fatalf("set session state %s: %v", state, err)
	}
}

func newIntegrationRepository(t *testing.T) (*persistence.Repository, *pgxpool.Pool) {
	t.Helper()
	databaseURL := testsupport.TestDatabaseURL()
	poolConfig, err := pgxpool.ParseConfig(databaseURL)
	if err != nil {
		t.Fatalf("parse test database URL: %v", err)
	}
	poolConfig.MaxConns = 32
	pool, err := pgxpool.NewWithConfig(context.Background(), poolConfig)
	if err != nil {
		t.Fatalf("open test pool: %v", err)
	}
	cleanupPlatformSchema(t, databaseURL, pool)
	migratePlatform(t, databaseURL)
	t.Cleanup(func() {
		cleanupPlatformSchema(t, databaseURL, pool)
		pool.Close()
	})
	return persistence.New(pool), pool
}

func migratePlatform(t *testing.T, databaseURL string) {
	t.Helper()
	root := repositoryRoot(t)
	database, err := goose.OpenDBWithDriver("pgx", databaseURL)
	if err != nil {
		t.Fatalf("open goose database: %v", err)
	}
	defer database.Close()
	if _, err := database.ExecContext(context.Background(), "CREATE SCHEMA IF NOT EXISTS platform"); err != nil {
		t.Fatalf("create platform schema for Goose: %v", err)
	}
	goose.SetTableName("platform.goose_db_version")
	if err := goose.SetDialect("postgres"); err != nil {
		t.Fatalf("set goose dialect: %v", err)
	}
	if err := goose.UpContext(context.Background(), database, filepath.Join(root, "apps", "platform-plane", "migrations")); err != nil {
		t.Fatalf("apply platform migrations: %v", err)
	}
}

func cleanupPlatformSchema(t *testing.T, databaseURL string, pool *pgxpool.Pool) {
	t.Helper()
	if err := testsupport.ResetPlatformSchema(context.Background(), databaseURL, pool); err != nil {
		t.Fatalf("reset platform schema: %v", err)
	}
}

func validEvent(t *testing.T) contracts.Event {
	t.Helper()
	validator, err := contracts.Load(repositoryRoot(t))
	if err != nil {
		t.Fatalf("load canonical contracts: %v", err)
	}
	contents, err := os.ReadFile(filepath.Join(repositoryRoot(t), "contracts", "fixtures", "simulation_start_requested_v1.valid.json"))
	if err != nil {
		t.Fatalf("read valid fixture: %v", err)
	}
	event, err := validator.Validate(contents)
	if err != nil {
		t.Fatalf("validate fixture: %v", err)
	}
	return event
}

func repositoryRoot(t *testing.T) string {
	t.Helper()
	workingDirectory, err := os.Getwd()
	if err != nil {
		t.Fatalf("get working directory: %v", err)
	}
	return filepath.Clean(filepath.Join(workingDirectory, "..", "..", "..", ".."))
}

func assertCount(t *testing.T, pool *pgxpool.Pool, query string, want int) {
	t.Helper()
	var got int
	if err := pool.QueryRow(context.Background(), query).Scan(&got); err != nil {
		t.Fatalf("count query: %v", err)
	}
	if got != want {
		t.Fatalf("count = %d, want %d for %s", got, want, query)
	}
}
