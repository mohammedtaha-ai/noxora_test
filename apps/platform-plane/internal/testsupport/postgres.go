package testsupport

import (
	"context"
	"errors"
	"fmt"
	"net"
	"net/url"
	"os"
	"strings"

	"github.com/jackc/pgx/v5/pgconn"
)

const DestructiveTestOptInEnv = "PLATFORM_DESTRUCTIVE_TESTS"

var ErrUnsafeDestructiveTestTarget = errors.New("unsafe destructive test database target")

type SchemaExecutor interface {
	Exec(context.Context, string, ...any) (pgconn.CommandTag, error)
}

func TestDatabaseURL() string {
	if value := os.Getenv("PLATFORM_TEST_DATABASE_URL"); value != "" {
		return value
	}
	return "postgres://nexora_control:nexora_control_local_only@127.0.0.1:5432/nexora_control_plane_test?sslmode=disable"
}

func RequireSafeDestructiveTestTarget(databaseURL string) error {
	if os.Getenv(DestructiveTestOptInEnv) != "1" {
		return fmt.Errorf("%w: %s must equal 1", ErrUnsafeDestructiveTestTarget, DestructiveTestOptInEnv)
	}
	parsed, err := url.Parse(databaseURL)
	if err != nil {
		return fmt.Errorf("%w: parse database URL: %v", ErrUnsafeDestructiveTestTarget, err)
	}
	if parsed.Scheme != "postgres" && parsed.Scheme != "postgresql" {
		return fmt.Errorf("%w: database URL must use PostgreSQL", ErrUnsafeDestructiveTestTarget)
	}
	databaseName := strings.TrimPrefix(parsed.Path, "/")
	if !strings.HasSuffix(strings.ToLower(databaseName), "_test") {
		return fmt.Errorf("%w: database name must end in _test", ErrUnsafeDestructiveTestTarget)
	}
	hostname := parsed.Hostname()
	if !isLocalOrCIHost(hostname) {
		return fmt.Errorf("%w: host must be loopback or CI postgres service", ErrUnsafeDestructiveTestTarget)
	}
	return nil
}

func ResetPlatformSchema(ctx context.Context, databaseURL string, executor SchemaExecutor) error {
	if err := RequireSafeDestructiveTestTarget(databaseURL); err != nil {
		return err
	}
	if _, err := executor.Exec(ctx, "DROP SCHEMA IF EXISTS platform CASCADE"); err != nil {
		return fmt.Errorf("drop platform schema: %w", err)
	}
	return nil
}

func isLocalOrCIHost(hostname string) bool {
	if strings.EqualFold(hostname, "postgres") || strings.EqualFold(hostname, "localhost") {
		return true
	}
	parsed := net.ParseIP(hostname)
	return parsed != nil && parsed.IsLoopback()
}
