package ingestion

import (
	"context"
	"errors"
	"time"

	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/contracts"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/observability"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/persistence"
	"github.com/mohammedtaha-ai/noxora_test/apps/platform-plane/internal/session"
)

type Service struct {
	validator   *contracts.Validator
	repository  *persistence.Repository
	diagnostics observability.Diagnostics
}

type Error struct {
	Code string
	Err  error
}

func (e *Error) Error() string {
	return e.Code
}

func (e *Error) Unwrap() error {
	return e.Err
}

func NewService(validator *contracts.Validator, repository *persistence.Repository, diagnostics observability.Diagnostics) *Service {
	return &Service{validator: validator, repository: repository, diagnostics: diagnostics}
}

func (s *Service) Accept(ctx context.Context, rawEvent []byte) (session.AllocationResult, error) {
	started := time.Now()
	event, err := s.validator.Validate(rawEvent)
	if err != nil {
		var validationError *contracts.ValidationError
		if errors.As(err, &validationError) {
			s.diagnostics.Error(ctx, "platform command rejected", observability.Fields{ErrorCode: validationError.Code, DurationMS: time.Since(started).Milliseconds()})
			return session.AllocationResult{}, &Error{Code: validationError.Code, Err: err}
		}
		return session.AllocationResult{}, &Error{Code: "INVALID_EVENT", Err: err}
	}
	result, err := s.repository.Allocate(ctx, event)
	if err != nil {
		code := errorCode(err)
		s.diagnostics.Error(ctx, "platform command allocation failed", observability.Fields{
			EventID: event.EventID.String(), CommandID: event.CommandID.String(), TenantID: event.TenantID.String(),
			ErrorCode: code, DurationMS: time.Since(started).Milliseconds(),
		})
		return session.AllocationResult{}, &Error{Code: code, Err: err}
	}

	s.diagnostics.Info(ctx, "platform command allocated", observability.Fields{
		EventID: event.EventID.String(), CommandID: event.CommandID.String(), TenantID: event.TenantID.String(),
		SessionID: result.Session.ID.String(), StateTransition: "ALLOCATED:" + string(result.Session.State),
		DurationMS: time.Since(started).Milliseconds(),
	})
	return result, nil
}

func (s *Service) MarkPendingWorker(ctx context.Context, sessionID string) error {
	return &Error{Code: "INTERNAL_ERROR", Err: errors.New("worker lifecycle is not implemented in phase 1")}
}

func errorCode(err error) string {
	switch {
	case errors.Is(err, persistence.ErrEventIntegrityConflict):
		return "EVENT_INTEGRITY_CONFLICT"
	case errors.Is(err, persistence.ErrSessionNotFound):
		return "SESSION_ALLOCATION_CONFLICT"
	default:
		return "DATABASE_UNAVAILABLE"
	}
}
