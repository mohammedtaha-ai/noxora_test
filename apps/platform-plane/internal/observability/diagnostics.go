package observability

import (
	"context"
	"log/slog"
	"os"
	"strings"
)

type Fields struct {
	EventID         string
	CommandID       string
	TenantID        string
	SessionID       string
	LeaseGeneration int64
	StateTransition string
	DurationMS      int64
	ErrorCode       string
}

type Diagnostics interface {
	Info(context.Context, string, Fields)
	Error(context.Context, string, Fields)
}

type SlogDiagnostics struct {
	logger *slog.Logger
}

func New(logLevel string) *SlogDiagnostics {
	level := new(slog.LevelVar)
	switch strings.ToLower(logLevel) {
	case "debug":
		level.Set(slog.LevelDebug)
	case "warn":
		level.Set(slog.LevelWarn)
	case "error":
		level.Set(slog.LevelError)
	default:
		level.Set(slog.LevelInfo)
	}
	return &SlogDiagnostics{logger: slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: level}))}
}

func (d *SlogDiagnostics) Info(ctx context.Context, message string, fields Fields) {
	d.logger.LogAttrs(ctx, slog.LevelInfo, message, fields.attrs()...)
}

func (d *SlogDiagnostics) Error(ctx context.Context, message string, fields Fields) {
	d.logger.LogAttrs(ctx, slog.LevelError, message, fields.attrs()...)
}

func (f Fields) attrs() []slog.Attr {
	attrs := make([]slog.Attr, 0, 8)
	if f.EventID != "" {
		attrs = append(attrs, slog.String("event_id", f.EventID))
	}
	if f.CommandID != "" {
		attrs = append(attrs, slog.String("command_id", f.CommandID))
	}
	if f.TenantID != "" {
		attrs = append(attrs, slog.String("tenant_id", f.TenantID))
	}
	if f.SessionID != "" {
		attrs = append(attrs, slog.String("session_id", f.SessionID))
	}
	if f.LeaseGeneration != 0 {
		attrs = append(attrs, slog.Int64("lease_generation", f.LeaseGeneration))
	}
	if f.StateTransition != "" {
		attrs = append(attrs, slog.String("state_transition", f.StateTransition))
	}
	if f.DurationMS != 0 {
		attrs = append(attrs, slog.Int64("duration_ms", f.DurationMS))
	}
	if f.ErrorCode != "" {
		attrs = append(attrs, slog.String("error_code", f.ErrorCode))
	}
	return attrs
}
