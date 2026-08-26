package testsupport

import (
	"context"
	"errors"
	"testing"

	"github.com/jackc/pgx/v5/pgconn"
)

func TestResetPlatformSchemaRejectsNonTestDatabaseBeforeDrop(t *testing.T) {
	t.Setenv(DestructiveTestOptInEnv, "1")
	executor := &recordingExecutor{}
	err := ResetPlatformSchema(context.Background(), "postgres://user:password@127.0.0.1:5432/nexora_control_plane", executor)
	if !errors.Is(err, ErrUnsafeDestructiveTestTarget) {
		t.Fatalf("ResetPlatformSchema() error = %v, want unsafe target error", err)
	}
	if executor.called {
		t.Fatal("DROP SCHEMA was attempted for a non-test database")
	}
}

func TestResetPlatformSchemaRequiresExplicitOptInBeforeDrop(t *testing.T) {
	t.Setenv(DestructiveTestOptInEnv, "")
	executor := &recordingExecutor{}
	err := ResetPlatformSchema(context.Background(), "postgres://user:password@127.0.0.1:5432/nexora_control_plane_test", executor)
	if !errors.Is(err, ErrUnsafeDestructiveTestTarget) {
		t.Fatalf("ResetPlatformSchema() error = %v, want unsafe target error", err)
	}
	if executor.called {
		t.Fatal("DROP SCHEMA was attempted without explicit opt-in")
	}
}

func TestResetPlatformSchemaAllowsExplicitLocalTestTarget(t *testing.T) {
	t.Setenv(DestructiveTestOptInEnv, "1")
	executor := &recordingExecutor{}
	if err := ResetPlatformSchema(context.Background(), "postgres://user:password@127.0.0.1:5432/nexora_control_plane_test", executor); err != nil {
		t.Fatalf("ResetPlatformSchema() unexpected error: %v", err)
	}
	if !executor.called {
		t.Fatal("expected DROP SCHEMA for explicit local test target")
	}
}

type recordingExecutor struct {
	called bool
}

func (e *recordingExecutor) Exec(_ context.Context, _ string, _ ...any) (pgconn.CommandTag, error) {
	e.called = true
	return pgconn.NewCommandTag("DROP SCHEMA"), nil
}
