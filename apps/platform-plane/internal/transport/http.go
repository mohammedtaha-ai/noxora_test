package transport

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"time"

	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/ingestion"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/persistence"
)

type HTTPAdapter struct {
	service       *ingestion.Service
	repository    *persistence.Repository
	maxEventBytes int64
}

func NewHTTPAdapter(service *ingestion.Service, repository *persistence.Repository, maxEventBytes int64) *HTTPAdapter {
	return &HTTPAdapter{service: service, repository: repository, maxEventBytes: maxEventBytes}
}

func (a *HTTPAdapter) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", a.health)
	mux.HandleFunc("GET /readyz", a.ready)
	mux.HandleFunc("POST /internal/test-events/simulation-start", a.ingestSimulationStart)
	return mux
}

func NewServer(address string, handler http.Handler) *http.Server {
	return &http.Server{
		Addr:              address,
		Handler:           handler,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       30 * time.Second,
		MaxHeaderBytes:    8 << 10,
	}
}

func (a *HTTPAdapter) health(response http.ResponseWriter, _ *http.Request) {
	writeJSON(response, http.StatusOK, map[string]string{"status": "ok"})
}

func (a *HTTPAdapter) ready(response http.ResponseWriter, request *http.Request) {
	ctx, cancel := context.WithTimeout(request.Context(), 2*time.Second)
	defer cancel()
	if err := a.repository.Ping(ctx); err != nil {
		writeError(response, http.StatusServiceUnavailable, "DATABASE_UNAVAILABLE", "platform database is unavailable")
		return
	}
	writeJSON(response, http.StatusOK, map[string]string{"status": "ready"})
}

func (a *HTTPAdapter) ingestSimulationStart(response http.ResponseWriter, request *http.Request) {
	if request.Header.Get("Content-Type") != "application/json" {
		writeError(response, http.StatusUnsupportedMediaType, "INVALID_EVENT", "content type must be application/json")
		return
	}
	request.Body = http.MaxBytesReader(response, request.Body, a.maxEventBytes)
	defer request.Body.Close()
	rawEvent, err := io.ReadAll(request.Body)
	if err != nil {
		var maxBytesError *http.MaxBytesError
		if errors.As(err, &maxBytesError) {
			writeError(response, http.StatusRequestEntityTooLarge, "PAYLOAD_TOO_LARGE", "event exceeds configured size limit")
			return
		}
		writeError(response, http.StatusBadRequest, "INVALID_EVENT", "event body could not be read")
		return
	}
	result, err := a.service.Accept(request.Context(), rawEvent)
	if err != nil {
		var platformError *ingestion.Error
		if errors.As(err, &platformError) {
			writePlatformError(response, platformError.Code)
			return
		}
		writeError(response, http.StatusInternalServerError, "INTERNAL_ERROR", "platform command could not be processed")
		return
	}
	status := http.StatusCreated
	if result.Duplicate {
		status = http.StatusOK
	}
	writeJSON(response, status, map[string]any{
		"session_id": result.Session.ID.String(),
		"state":      result.Session.State,
		"duplicate":  result.Duplicate,
	})
}

func writePlatformError(response http.ResponseWriter, code string) {
	switch code {
	case "INVALID_EVENT":
		writeError(response, http.StatusBadRequest, code, "event does not satisfy the platform contract")
	case "UNSUPPORTED_SCHEMA":
		writeError(response, http.StatusUnprocessableEntity, code, "event type or schema version is unsupported")
	case "EVENT_INTEGRITY_CONFLICT", "SESSION_ALLOCATION_CONFLICT", "LEASE_CONFLICT", "LEASE_EXPIRED", "STALE_GENERATION":
		writeError(response, http.StatusConflict, code, "platform command conflicts with durable state")
	case "DATABASE_UNAVAILABLE":
		writeError(response, http.StatusServiceUnavailable, code, "platform database is unavailable")
	default:
		writeError(response, http.StatusInternalServerError, "INTERNAL_ERROR", "platform command could not be processed")
	}
}

func writeError(response http.ResponseWriter, status int, code, message string) {
	writeJSON(response, status, map[string]any{"error": map[string]string{"code": code, "message": message}})
}

func writeJSON(response http.ResponseWriter, status int, body any) {
	response.Header().Set("Content-Type", "application/json")
	response.WriteHeader(status)
	_ = json.NewEncoder(response).Encode(body)
}
