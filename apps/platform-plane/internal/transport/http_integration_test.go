package transport_test

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
	_ "github.com/jackc/pgx/v5/stdlib"
	"github.com/pressly/goose/v3"

	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/contracts"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/ingestion"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/observability"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/persistence"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/testsupport"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/transport"
)

func TestLoopbackAdapterProcessesValidEventAndDuplicate(t *testing.T) {
	adapter, cleanup := newAdapter(t, 1024*1024)
	defer cleanup()
	handler := adapter.Handler()
	fixture := readFixture(t, "simulation_start_requested_v1.valid.json")

	first := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodPost, "/internal/test-events/simulation-start", bytes.NewReader(fixture))
	request.Header.Set("Content-Type", "application/json")
	handler.ServeHTTP(first, request)
	if first.Code != http.StatusCreated {
		t.Fatalf("first ingress status = %d, body=%s", first.Code, first.Body.String())
	}

	second := httptest.NewRecorder()
	redelivery := httptest.NewRequest(http.MethodPost, "/internal/test-events/simulation-start", bytes.NewReader(fixture))
	redelivery.Header.Set("Content-Type", "application/json")
	handler.ServeHTTP(second, redelivery)
	if second.Code != http.StatusOK {
		t.Fatalf("duplicate ingress status = %d, body=%s", second.Code, second.Body.String())
	}
	var body struct {
		Duplicate bool `json:"duplicate"`
	}
	if err := json.Unmarshal(second.Body.Bytes(), &body); err != nil || !body.Duplicate {
		t.Fatalf("duplicate response = %s, error=%v", second.Body.String(), err)
	}
}

func TestLoopbackAdapterRejectsMalformedAndOversizedIngress(t *testing.T) {
	adapter, cleanup := newAdapter(t, 128)
	defer cleanup()
	handler := adapter.Handler()

	malformed := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodPost, "/internal/test-events/simulation-start", bytes.NewBufferString("{"))
	request.Header.Set("Content-Type", "application/json")
	handler.ServeHTTP(malformed, request)
	assertErrorCode(t, malformed, http.StatusBadRequest, "INVALID_EVENT")

	oversized := httptest.NewRecorder()
	request = httptest.NewRequest(http.MethodPost, "/internal/test-events/simulation-start", bytes.NewReader(bytes.Repeat([]byte("a"), 129)))
	request.Header.Set("Content-Type", "application/json")
	handler.ServeHTTP(oversized, request)
	assertErrorCode(t, oversized, http.StatusRequestEntityTooLarge, "PAYLOAD_TOO_LARGE")

	wrongType := httptest.NewRecorder()
	request = httptest.NewRequest(http.MethodPost, "/internal/test-events/simulation-start", bytes.NewBufferString("{}"))
	handler.ServeHTTP(wrongType, request)
	assertErrorCode(t, wrongType, http.StatusUnsupportedMediaType, "INVALID_EVENT")
}

func newAdapter(t *testing.T, maxEventBytes int64) (*transport.HTTPAdapter, func()) {
	t.Helper()
	databaseURL := testsupport.TestDatabaseURL()
	poolConfig, err := pgxpool.ParseConfig(databaseURL)
	if err != nil {
		t.Fatalf("parse test database URL: %v", err)
	}
	pool, err := pgxpool.NewWithConfig(context.Background(), poolConfig)
	if err != nil {
		t.Fatalf("open test pool: %v", err)
	}
	if err := testsupport.ResetPlatformSchema(context.Background(), databaseURL, pool); err != nil {
		pool.Close()
		t.Fatalf("reset platform schema: %v", err)
	}
	applyMigrations(t, databaseURL)
	validator, err := contracts.Load(repositoryRoot(t))
	if err != nil {
		pool.Close()
		t.Fatalf("load contracts: %v", err)
	}
	repository := persistence.New(pool)
	service := ingestion.NewService(validator, repository, observability.New("error"))
	return transport.NewHTTPAdapter(service, repository, maxEventBytes), func() {
		if err := testsupport.ResetPlatformSchema(context.Background(), databaseURL, pool); err != nil {
			t.Errorf("reset platform schema during cleanup: %v", err)
		}
		pool.Close()
	}
}

func applyMigrations(t *testing.T, databaseURL string) {
	t.Helper()
	database, err := goose.OpenDBWithDriver("pgx", databaseURL)
	if err != nil {
		t.Fatalf("open Goose database: %v", err)
	}
	defer database.Close()
	if _, err := database.ExecContext(context.Background(), "CREATE SCHEMA IF NOT EXISTS platform"); err != nil {
		t.Fatalf("create platform schema: %v", err)
	}
	goose.SetTableName("platform.goose_db_version")
	if err := goose.SetDialect("postgres"); err != nil {
		t.Fatalf("set Goose dialect: %v", err)
	}
	if err := goose.UpContext(context.Background(), database, filepath.Join(repositoryRoot(t), "apps", "platform-plane", "migrations")); err != nil {
		t.Fatalf("apply migrations: %v", err)
	}
}

func readFixture(t *testing.T, filename string) []byte {
	t.Helper()
	contents, err := os.ReadFile(filepath.Join(repositoryRoot(t), "contracts", "fixtures", filename))
	if err != nil {
		t.Fatalf("read fixture: %v", err)
	}
	return contents
}

func repositoryRoot(t *testing.T) string {
	t.Helper()
	workingDirectory, err := os.Getwd()
	if err != nil {
		t.Fatalf("get working directory: %v", err)
	}
	return filepath.Clean(filepath.Join(workingDirectory, "..", "..", "..", ".."))
}

func assertErrorCode(t *testing.T, recorder *httptest.ResponseRecorder, status int, code string) {
	t.Helper()
	if recorder.Code != status {
		t.Fatalf("status = %d, want %d, body=%s", recorder.Code, status, recorder.Body.String())
	}
	var body struct {
		Error struct {
			Code string `json:"code"`
		} `json:"error"`
	}
	if err := json.Unmarshal(recorder.Body.Bytes(), &body); err != nil || body.Error.Code != code {
		t.Fatalf("error body = %s, parse error=%v, want code=%s", recorder.Body.String(), err, code)
	}
}
