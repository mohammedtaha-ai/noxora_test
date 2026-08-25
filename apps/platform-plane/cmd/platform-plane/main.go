package main

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	_ "github.com/jackc/pgx/v5/stdlib"
	"github.com/pressly/goose/v3"

	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/config"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/contracts"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/ingestion"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/observability"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/persistence"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/transport"
)

func main() {
	if err := run(); err != nil {
		slog.Error("platform plane exited", "error", err.Error())
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load()
	if err != nil {
		return err
	}
	root, err := findRepositoryRoot()
	if err != nil {
		return err
	}
	if len(os.Args) > 1 && os.Args[1] == "migrate" {
		return migrate(cfg, root)
	}
	if len(os.Args) > 1 {
		return fmt.Errorf("unsupported command %q", os.Args[1])
	}

	validator, err := contracts.Load(root)
	if err != nil {
		return err
	}
	poolConfig, err := pgxpool.ParseConfig(cfg.DatabaseURL)
	if err != nil {
		return fmt.Errorf("parse DATABASE_URL: %w", err)
	}
	poolConfig.MaxConns = 10
	poolConfig.MinConns = 1
	pool, err := pgxpool.NewWithConfig(context.Background(), poolConfig)
	if err != nil {
		return fmt.Errorf("open platform PostgreSQL pool: %w", err)
	}
	defer pool.Close()
	readinessContext, cancelReadiness := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancelReadiness()
	if err := pool.Ping(readinessContext); err != nil {
		return fmt.Errorf("verify platform PostgreSQL readiness: %w", err)
	}

	diagnostics := observability.New(cfg.LogLevel)
	repository := persistence.New(pool)
	service := ingestion.NewService(validator, repository, diagnostics)
	adapter := transport.NewHTTPAdapter(service, repository, cfg.MaxEventBytes)
	server := transport.NewServer(cfg.ListenAddr, adapter.Handler())

	serverErrors := make(chan error, 1)
	go func() {
		diagnostics.Info(context.Background(), "platform plane listening", observability.Fields{})
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			serverErrors <- err
		}
	}()

	signalContext, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	select {
	case err := <-serverErrors:
		return fmt.Errorf("serve platform ingress: %w", err)
	case <-signalContext.Done():
		shutdownContext, cancelShutdown := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancelShutdown()
		return server.Shutdown(shutdownContext)
	}
}

func migrate(cfg config.Config, root string) error {
	db, err := sql.Open("pgx", cfg.DatabaseURL)
	if err != nil {
		return fmt.Errorf("open migration database: %w", err)
	}
	defer db.Close()
	context, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if err := db.PingContext(context); err != nil {
		return fmt.Errorf("verify migration database: %w", err)
	}
	if _, err := db.ExecContext(context, "CREATE SCHEMA IF NOT EXISTS platform"); err != nil {
		return fmt.Errorf("create platform schema for migration tracking: %w", err)
	}
	if err := goose.SetDialect("postgres"); err != nil {
		return fmt.Errorf("set goose dialect: %w", err)
	}
	goose.SetTableName("platform.goose_db_version")
	if err := goose.UpContext(context, db, filepath.Join(root, "apps", "platform-plane", "migrations")); err != nil {
		return fmt.Errorf("apply platform migrations: %w", err)
	}
	return nil
}

func findRepositoryRoot() (string, error) {
	if configured := os.Getenv("PLATFORM_REPOSITORY_ROOT"); configured != "" {
		if hasCanonicalSchemas(configured) {
			return configured, nil
		}
		return "", fmt.Errorf("PLATFORM_REPOSITORY_ROOT does not contain canonical schemas")
	}
	current, err := os.Getwd()
	if err != nil {
		return "", fmt.Errorf("get working directory: %w", err)
	}
	for {
		if hasCanonicalSchemas(current) {
			return current, nil
		}
		parent := filepath.Dir(current)
		if parent == current {
			return "", fmt.Errorf("could not find repository root containing canonical schemas")
		}
		current = parent
	}
}

func hasCanonicalSchemas(root string) bool {
	_, envelopeError := os.Stat(filepath.Join(root, "schemas", "platform-event-envelope.schema.json"))
	_, eventError := os.Stat(filepath.Join(root, "contracts", "events", "control.simulation_start.requested.v1.schema.json"))
	return envelopeError == nil && eventError == nil
}
